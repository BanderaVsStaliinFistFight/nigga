#!/usr/bin/env python3
"""Static checks for the Zombie Outbreak mod (no game install needed).

    python tools/validate.py

Checks that every script file parses, and that technologies, units,
equipment, localisation keys, sprites and textures all refer to each other
correctly. Exits non-zero on the first run that finds problems.
"""

import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clausewitz  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MOD = REPO / "zombie_outbreak"
SNIPPETS = Path(__file__).resolve().parent / "snippets"
ITEM_WIDTH_SLOTS = 3  # a full-size tech item is 203px wide, i.e. ~3 slots of 70px

errors = []


def err(msg):
    errors.append(msg)


def load(path):
    text = path.read_text(encoding="utf-8-sig")
    # @variables are file-local constants; substitute them like the game does
    consts = dict(re.findall(r"^\s*(@\w+)\s*=\s*(-?[\d.]+)", text, re.M))
    text = re.sub(r"^\s*@\w+\s*=\s*-?[\d.]+\s*$", "", text, flags=re.M)
    for k in sorted(consts, key=len, reverse=True):
        text = text.replace(k, consts[k])
    try:
        return clausewitz.parse(text)
    except clausewitz.ParseError as e:
        err(f"{path.relative_to(REPO)}: {e}")
        return clausewitz.Block(None, -1, None)


def merged(pattern, key):
    out = {}
    for path in sorted(MOD.glob(pattern)):
        root = load(path)
        for top in root.get_all(key):
            for name, blk in top.blocks():
                if name in out:
                    err(f"duplicate {key} entry {name}")
                out[name] = blk
    return out


def dds_size(path):
    data = path.read_bytes()
    if data[:4] != b"DDS " or len(data) < 128:
        err(f"{path.relative_to(REPO)} is not a DDS file")
        return None
    h, w = struct.unpack("<II", data[12:20])
    bpp = struct.unpack("<I", data[88:92])[0]
    if len(data) != 128 + w * h * bpp // 8:
        err(f"{path.relative_to(REPO)}: size does not match its {w}x{h} header")
    return w, h


def main():
    # ---- tags -----------------------------------------------------------
    tag_files = list(MOD.glob("common/technology_tags/*.txt"))
    categories, folders = set(), set()
    for path in tag_files:
        root = load(path)
        for blk in root.get_all("technology_categories"):
            categories.update(blk.values())
        for blk in root.get_all("technology_folders"):
            folders.update(k for k, _ in blk.entries)

    techs = merged("common/technologies/*.txt", "technologies")
    units = merged("common/units/*.txt", "sub_units")
    equipment = merged("common/units/equipment/*.txt", "equipments")
    archetypes = {n for n, b in equipment.items() if b.get("is_archetype") == "yes"}

    if not techs or not units or not equipment:
        err("missing technologies, units or equipment")

    # ---- equipment ------------------------------------------------------
    for name, blk in equipment.items():
        arch = blk.get("archetype")
        if blk.get("is_archetype") != "yes" and arch not in archetypes:
            err(f"equipment {name}: archetype {arch!r} is not defined")
        parent = blk.get("parent")
        if parent and parent not in equipment:
            err(f"equipment {name}: parent {parent!r} is not defined")

    # ---- units ----------------------------------------------------------
    for name, blk in units.items():
        for section in ("need", "essential"):
            sec = blk.get(section)
            if sec is None:
                continue
            for eq in [k for k, _ in sec.entries]:
                if eq not in archetypes:
                    err(f"unit {name}: {section} uses {eq!r}, which is not an equipment archetype")
        if blk.get("active") != "no":
            err(f"unit {name}: should be 'active = no' so it has to be researched")

    # ---- technologies ---------------------------------------------------
    unlocked_units, unlocked_eq, children = set(), set(), {}
    positions = {}
    for name, blk in techs.items():
        for sec in blk.get_all("enable_subunits"):
            for u in sec.values():
                unlocked_units.add(u)
                if u not in units:
                    err(f"tech {name}: enables unknown unit {u!r}")
        for sec in blk.get_all("enable_equipments"):
            for e in sec.values():
                unlocked_eq.add(e)
                if e not in equipment or e in archetypes:
                    err(f"tech {name}: enables {e!r}, which is not a buildable equipment variant")
        for path in blk.get_all("path"):
            child = path.get("leads_to_tech")
            children.setdefault(name, []).append(child)
            if child not in techs:
                err(f"tech {name}: leads_to_tech {child!r} is not defined")
        for sec in blk.get_all("categories"):
            for c in sec.values():
                if c not in categories:
                    err(f"tech {name}: category {c!r} is not defined in technology_tags")
        for key, sub in blk.blocks():
            if key in units:
                for stat, _ in sub.entries:
                    if stat not in ("soft_attack", "hard_attack", "defense", "breakthrough", "ap_attack",
                                    "max_organisation", "default_morale", "maximum_speed", "recon",
                                    "max_strength", "supply_consumption"):
                        err(f"tech {name}: unusual stat {stat!r} for unit {key}")
        folder = blk.get("folder")
        if folder is None:
            err(f"tech {name}: has no folder, so it will not appear in the tech tree")
            continue
        if folder.get("name") not in folders:
            err(f"tech {name}: folder {folder.get('name')!r} is not defined in technology_tags")
        pos = folder.get("position")
        positions[name] = (float(pos.get("x")), float(pos.get("y")))

    for u in units:
        if u not in unlocked_units:
            err(f"unit {u} is never unlocked by a technology")
    for e, blk in equipment.items():
        if e not in archetypes and e not in unlocked_eq:
            err(f"equipment {e} is never unlocked by a technology")

    # One tree box ("<root>_tree") positions the whole tab, so every tech must
    # be reachable from a single root that has a gridbox in the folder snippet.
    roots = [t for t in techs if not any(t in c for c in children.values())]
    snippet = (SNIPPETS / "zombie_folder.gui").read_text(encoding="utf-8")
    boxes = set(re.findall(r'name\s*=\s*"(\w+)_tree"', snippet))
    for r in roots:
        if r not in boxes:
            err(f"tech {r} is a tree root but the folder snippet has no '{r}_tree' gridbox")
    reach, todo = set(), list(roots)
    while todo:
        t = todo.pop()
        if t not in reach:
            reach.add(t)
            todo += children.get(t, [])
    for t in techs:
        if t not in reach:
            err(f"tech {t} is not reachable from a tree root")

    # tech items must not overlap
    names = sorted(positions)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            (ax, ay), (bx, by) = positions[a], positions[b]
            if ay == by and abs(ax - bx) < ITEM_WIDTH_SLOTS:
                err(f"techs {a} and {b} overlap in the tech tree")
            elif ax == bx and abs(ay - by) < 2:
                err(f"techs {a} and {b} overlap in the tech tree")
    # a child must be below its parent, otherwise the connecting line goes upwards
    for parent, kids in children.items():
        for k in kids:
            if k in positions and positions[k][1] <= positions[parent][1]:
                err(f"tech {k} is not below its parent {parent}")

    # ---- localisation ---------------------------------------------------
    loc = {}
    for path in MOD.glob("localisation/**/*_l_english.yml"):
        raw = path.read_bytes()
        if not raw.startswith(b"\xef\xbb\xbf"):
            err(f"{path.relative_to(REPO)}: localisation must be UTF-8 with BOM")
        text = raw.decode("utf-8-sig")
        if not text.startswith("l_english:"):
            err(f"{path.relative_to(REPO)}: must start with 'l_english:'")
        for n, line in enumerate(text.splitlines()[1:], 2):
            if not line.strip() or line.strip().startswith("#"):
                continue
            m = re.match(r'^ (\w+):\d* "(.*)"\s*(#.*)?$', line)
            if not m:
                err(f"{path.relative_to(REPO)}:{n}: malformed line {line!r}")
                continue
            if m.group(1) in loc:
                err(f"duplicate localisation key {m.group(1)}")
            loc[m.group(1)] = m.group(2)
    wanted = []
    for t in techs:
        wanted += [t, f"{t}_desc"]
    for u in units:
        wanted += [u, f"{u}_desc"]
    for e in equipment:
        wanted += [e, f"{e}_short", f"{e}_desc"]
    for f in folders:
        wanted += [f, f"{f}_desc"]
    wanted += sorted(categories)
    for key in wanted:
        if key not in loc:
            err(f"missing localisation key {key}")

    # ---- sprites and textures -------------------------------------------
    sprites = {}
    for path in MOD.glob("interface/*.gfx"):
        root = load(path)
        for top in root.get_all("spriteTypes"):
            for key, blk in top.blocks():
                if key.lower() != "spritetype":
                    continue
                name = blk.get("name")
                tex = blk.get("texturefile") or blk.get("textureFile")
                frames = int(blk.get("noOfFrames", 1))
                if name in sprites:
                    err(f"duplicate sprite {name}")
                sprites[name] = (tex, frames)
                tpath = MOD / tex
                if not tpath.is_file():
                    err(f"sprite {name}: texture {tex} does not exist")
                    continue
                size = dds_size(tpath)
                if size and size[0] % frames:
                    err(f"sprite {name}: width {size[0]} is not divisible into {frames} frames")
    wanted = [f"GFX_{t}_medium" for t in techs]
    wanted += [f"GFX_{e}_medium" for e in equipment]
    wanted += [f"GFX_unit_{u}_icon_medium" for u in units]
    wanted += [f"GFX_unit_{u}_icon_small" for u in units]
    wanted += [f"GFX_{f}_tab" for f in folders]
    for name in wanted:
        if name not in sprites:
            err(f"missing sprite {name}")

    # ---- GUI ------------------------------------------------------------
    for path in list(MOD.glob("interface/*.gui")) + list(SNIPPETS.glob("*.gui")):
        if path.name == "countrytechtreeview.gui":
            continue  # generated by install.py, not part of the repository
        text = path.read_text(encoding="utf-8").replace("{TAB_X}", "0")
        try:
            clausewitz.parse(text)
        except clausewitz.ParseError as e:
            err(f"{path.relative_to(REPO)}: {e}")
    items = (MOD / "interface/zombie_outbreak_techtree.gui").read_text(encoding="utf-8")
    for f in folders:
        if f'name = "techtree_{f}_item"' not in items:
            err(f"no techtree_{f}_item template for folder {f}")
        if f'name = "{f}"' not in snippet:
            err(f"folder snippet does not define window {f}")
        tab = (SNIPPETS / "zombie_folder_tab.gui").read_text(encoding="utf-8")
        if f'name = "{f}_tab"' not in tab:
            err(f"tab snippet does not define button {f}_tab")

    # ---- descriptor -----------------------------------------------------
    desc = (MOD / "descriptor.mod").read_text(encoding="utf-8")
    pic = re.search(r'picture="([^"]+)"', desc)
    if pic and not (MOD / pic.group(1)).is_file():
        err(f"descriptor picture {pic.group(1)} does not exist")
    launcher = (REPO / "zombie_outbreak.mod").read_text(encoding="utf-8")
    if launcher.replace(re.search(r'path="[^"]*"\n', launcher).group(0), "") != desc:
        err("zombie_outbreak.mod and descriptor.mod differ (apart from path)")

    if errors:
        print(f"{len(errors)} problem(s):")
        for e in errors:
            print("  -", e)
        return 1
    print(f"OK: {len(techs)} technologies, {len(units)} units, {len(equipment)} equipment, "
          f"{len(loc)} localisation keys, {len(sprites)} sprites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
