#!/usr/bin/env python3
"""Static checks for the Zombie Outbreak mod (no game install needed).

    python tools/validate.py

Checks that every script file parses, and that technologies, research
decisions, units, equipment, localisation keys, sprites and textures all
refer to each other correctly. Exits non-zero if it finds problems.
"""

import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clausewitz  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MOD = REPO / "zombie_outbreak"
UNIT_STATS = ("soft_attack", "hard_attack", "defense", "breakthrough", "ap_attack",
              "max_organisation", "default_morale", "maximum_speed", "recon")

errors = []


def err(msg):
    errors.append(msg)


def load(path):
    text = path.read_text(encoding="utf-8-sig")
    try:
        return clausewitz.parse(text)
    except clausewitz.ParseError as e:
        err(f"{path.relative_to(REPO)}: {e}")
        return clausewitz.Block(None, -1, None)


def merged(pattern, key=None):
    """Second-level blocks of every file matching pattern, keyed by name.

    With key, entries come from inside `key = { ... }` (e.g. technologies);
    without it, from the top level of each file (e.g. decision categories).
    """
    out = {}
    for path in sorted(MOD.glob(pattern)):
        root = load(path)
        for top in (root.get_all(key) if key else [root]):
            for name, blk in top.blocks():
                if name in out:
                    err(f"duplicate entry {name} in {pattern}")
                out[name] = blk
    return out


def find_all(block, key):
    """Every value stored under key anywhere inside block."""
    found = [v for k, v in block.entries if k == key]
    for _, child in block.blocks():
        found += find_all(child, key)
    return found


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
    techs = merged("common/technologies/*.txt", "technologies")
    units = merged("common/units/*.txt", "sub_units")
    equipment = merged("common/units/equipment/*.txt", "equipments")
    categories = merged("common/decisions/categories/*.txt")
    decision_groups = merged("common/decisions/*.txt")
    archetypes = {n for n, b in equipment.items() if b.get("is_archetype") == "yes"}
    if not (techs and units and equipment and categories and decision_groups):
        err("missing technologies, units, equipment, decisions or decision categories")

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
            for eq, _ in sec.entries:
                if eq not in archetypes:
                    err(f"unit {name}: {section} uses {eq!r}, which is not an equipment archetype")
        if blk.get("active") != "no":
            err(f"unit {name}: should be 'active = no' so it has to be researched")

    # ---- technologies ---------------------------------------------------
    unlocked_units, unlocked_eq = set(), set()
    for name, blk in techs.items():
        allow = blk.get("allow")
        if not (isinstance(allow, clausewitz.Block) and allow.get("always") == "no"):
            err(f"tech {name}: needs 'allow = {{ always = no }}' so it is only granted by its decision")
        if blk.get("folder") is not None:
            err(f"tech {name}: has a folder, but the mod has no tech-tree tab")
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
        for key, sub in blk.blocks():
            if key in units:
                for stat, _ in sub.entries:
                    if stat not in UNIT_STATS:
                        err(f"tech {name}: unusual stat {stat!r} for unit {key}")
            elif key not in ("allow", "enable_subunits", "enable_equipments"):
                err(f"tech {name}: unexpected block {key!r}")
    for u in units:
        if u not in unlocked_units:
            err(f"unit {u} is never unlocked by a technology")
    for e in equipment:
        if e not in archetypes and e not in unlocked_eq:
            err(f"equipment {e} is never unlocked by a technology")

    # ---- research decisions ---------------------------------------------
    decisions = {}
    for cat, group in decision_groups.items():
        if cat not in categories:
            err(f"decision group {cat} has no matching decision category")
        for name, blk in group.blocks():
            decisions[name] = blk
    granted, prereqs, tooltips = {}, {}, set()
    for name, blk in decisions.items():
        grants = []
        for st in find_all(blk.get("remove_effect") or clausewitz.Block(None, -1, None), "set_technology"):
            grants += [k for k, _ in st.entries if k != "popup"]
        if len(grants) != 1:
            err(f"decision {name}: remove_effect should grant exactly one technology, got {grants}")
            continue
        tech = grants[0]
        if tech not in techs:
            err(f"decision {name}: grants unknown technology {tech!r}")
        if tech in granted:
            err(f"technology {tech} is granted by both {granted[tech]} and {name}")
        granted[tech] = name
        visible = blk.get("visible")
        hidden_when_done = visible is not None and any(
            isinstance(n, clausewitz.Block) and n.get("has_tech") == tech for n in find_all(visible, "NOT"))
        if not hidden_when_done:
            err(f"decision {name}: should be hidden once {tech} is researched")
        available = blk.get("available") or clausewitz.Block(None, -1, None)
        reqs = [v for v in find_all(available, "has_tech")]
        for r in reqs:
            if r not in techs:
                err(f"decision {name}: requires unknown technology {r!r}")
        prereqs[tech] = reqs
        tooltips.update(find_all(blk, "tooltip"))
        for key in ("cost", "days_remove"):
            if blk.get(key) is None:
                err(f"decision {name}: missing {key}")
        flags_set = find_all(blk.get("complete_effect") or clausewitz.Block(None, -1, None), "set_country_flag")
        flags_clr = find_all(blk.get("remove_effect") or clausewitz.Block(None, -1, None), "clr_country_flag")
        if sorted(flags_set) != sorted(flags_clr):
            err(f"decision {name}: sets flags {flags_set} but clears {flags_clr}")
    for t in techs:
        if t not in granted:
            err(f"technology {t} is not granted by any research decision")
    # prerequisites must form a tree rooted at techs with no requirements
    roots = [t for t, r in prereqs.items() if not r]
    if len(roots) != 1:
        err(f"expected exactly one starting research project, found {roots}")
    done, progress = set(roots), True
    while progress:
        progress = False
        for t, r in prereqs.items():
            if t not in done and r and all(x in done for x in r):
                done.add(t)
                progress = True
    for t in prereqs:
        if t not in done:
            err(f"technology {t} can never be researched (circular or missing prerequisite)")

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
    for group in (techs, units, decisions, categories):
        for key in group:
            wanted += [key, f"{key}_desc"]
    for e in equipment:
        wanted += [e, f"{e}_short", f"{e}_desc"]
    wanted += sorted(tooltips)
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
                sprites[name] = tex
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
    wanted += [f"GFX_decision_{b.get('icon')}" for b in decisions.values()]
    for blk in categories.values():
        icon = blk.get("icon")
        wanted.append(icon if icon.startswith("GFX_") else f"GFX_decision_category_{icon}")
        if blk.get("picture"):
            wanted.append(blk.get("picture"))
    for name in wanted:
        if name not in sprites:
            err(f"missing sprite {name}")
    used = {str(MOD / t) for t in sprites.values()}
    for tex in MOD.glob("gfx/**/*.dds"):
        if str(tex) not in used:
            err(f"texture {tex.relative_to(REPO)} is not used by any sprite")

    # ---- the mod must not override base-game files ------------------------
    for path in MOD.rglob("*"):
        rel = path.relative_to(MOD).as_posix()
        if path.is_file() and rel.startswith(("interface/", "common/")) and "zombie" not in path.name:
            err(f"{rel}: file name does not contain 'zombie'; it may replace a base-game file")

    # ---- descriptor -----------------------------------------------------
    desc = (MOD / "descriptor.mod").read_text(encoding="utf-8")
    if "replace_path" in desc:
        err("descriptor.mod must not replace base-game folders")
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
    print(f"OK: {len(techs)} technologies, {len(decisions)} research decisions, {len(units)} units, "
          f"{len(equipment)} equipment, {len(loc)} localisation keys, {len(sprites)} sprites")
    return 0


if __name__ == "__main__":
    sys.exit(main())
