#!/usr/bin/env python3
"""Install the Zombie Outbreak mod and add its "Necrotech" tab to the tech screen.

HoI4 draws a technology only if the tech-screen GUI file
(interface/countrytechtreeview.gui) has a window for its folder. That file
belongs to the base game and changes with every patch, so this mod cannot ship
a copy of it. This script reads the file from YOUR game install, adds the
zombie folder and tab, and saves the result inside the installed mod.

Usage (Python 3.8+, nothing else needed):

    python tools/install.py                 # auto-detect everything
    python tools/install.py --game-dir "D:/Games/Hearts of Iron IV"
    python tools/install.py --no-copy       # only patch the GUI inside this repo

Run it again after every HoI4 update.
"""

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clausewitz  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MOD_NAME = "zombie_outbreak"
MOD_SRC = REPO / MOD_NAME
SNIPPETS = Path(__file__).resolve().parent / "snippets"
GUI_REL = Path("interface") / "countrytechtreeview.gui"
MARK_BEGIN = "### ZOMBIE OUTBREAK"
MARK_END = "### END ZOMBIE OUTBREAK ###"
TAB_SPACING = 80      # vanilla tabs sit 80px apart
OFFSCREEN_TAB_X = 2500  # tabs parked further right than this are hidden ones


class InstallError(Exception):
    pass


# --------------------------------------------------------------------------
# Locating the game and the user folder
# --------------------------------------------------------------------------

def steam_roots():
    home = Path.home()
    roots = []
    if sys.platform.startswith("win"):
        try:
            import winreg
            for hive, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                              (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
                try:
                    with winreg.OpenKey(hive, key) as k:
                        for value in ("SteamPath", "InstallPath"):
                            try:
                                roots.append(Path(winreg.QueryValueEx(k, value)[0]))
                            except OSError:
                                pass
                except OSError:
                    pass
        except ImportError:
            pass
        for env in ("ProgramFiles(x86)", "ProgramFiles"):
            if os.environ.get(env):
                roots.append(Path(os.environ[env]) / "Steam")
    elif sys.platform == "darwin":
        roots.append(home / "Library/Application Support/Steam")
    else:
        roots += [home / ".steam/steam", home / ".local/share/Steam",
                  home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
    return roots


def steam_libraries():
    libs = []
    for root in steam_roots():
        if not root.is_dir():
            continue
        libs.append(root)
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if vdf.is_file():
            text = vdf.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                libs.append(Path(m.group(1).replace("\\\\", "\\")))
    seen, out = set(), []
    for lib in libs:
        key = str(lib).lower()
        if key not in seen:
            seen.add(key)
            out.append(lib)
    return out


def find_game_dir():
    for lib in steam_libraries():
        candidate = lib / "steamapps" / "common" / "Hearts of Iron IV"
        if (candidate / GUI_REL).is_file():
            return candidate
    return None


def documents_dir():
    if sys.platform.startswith("win"):
        try:  # honours OneDrive / relocated Documents folders
            import ctypes
            from ctypes import wintypes
            buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:
                return Path(buf.value)
        except (ImportError, AttributeError, OSError):
            pass
    return Path.home() / "Documents"


def find_user_dir():
    if sys.platform.startswith("linux"):
        candidates = [Path.home() / ".local/share/Paradox Interactive/Hearts of Iron IV"]
    else:
        candidates = [documents_dir() / "Paradox Interactive" / "Hearts of Iron IV"]
    for c in candidates:
        if c.is_dir():
            return c
    return None


# --------------------------------------------------------------------------
# Patching countrytechtreeview.gui
# --------------------------------------------------------------------------

def strip_previous_patch(text):
    """Remove blocks a previous run of this script inserted."""
    pattern = re.compile(r"[ \t]*" + re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END) + r"[ \t]*\r?\n?",
                         re.DOTALL)
    return pattern.sub("", text)


def line_start(text, pos):
    """Offset of the start of the line containing pos."""
    return text.rfind("\n", 0, pos) + 1


def tab_positions(folder_tabs):
    xs = []
    for key, child in folder_tabs.blocks():
        if key != "buttonType" or not (child.name or "").endswith("_tab"):
            continue
        pos = child.get("position")
        if pos is None or not isinstance(pos, clausewitz.Block):
            continue
        try:
            xs.append(int(float(pos.get("x"))))
        except (TypeError, ValueError):
            continue
    return xs


def patch_gui(vanilla_text, tab_x=None):
    """Return (patched_text, tab_x_used)."""
    text = strip_previous_patch(vanilla_text)
    try:
        root = clausewitz.parse(text)
    except clausewitz.ParseError as e:
        raise InstallError(f"could not read countrytechtreeview.gui: {e}")

    views = clausewitz.find_named(root, "countrytechtreeview", key="containerWindowType")
    if len(views) != 1:
        raise InstallError("could not find the 'countrytechtreeview' window in the GUI file")
    view = views[0]

    if clausewitz.find_named(view, "zombie_folder"):
        raise InstallError("the GUI file already contains a 'zombie_folder' window "
                           "(was it patched by hand?). Point --game-dir at an unmodified game.")

    tabs = [b for b in clausewitz.find_named(view, "folder_tabs") if b.key == "containerWindowType"]
    if len(tabs) != 1:
        raise InstallError("could not find the 'folder_tabs' window in the GUI file")
    folder_tabs = tabs[0]

    if tab_x is None:
        xs = [x for x in tab_positions(folder_tabs) if x < OFFSCREEN_TAB_X]
        if not xs:
            raise InstallError("could not work out where the existing tabs are; "
                               "pass --tab-x <pixels> to place the Necrotech tab yourself")
        tab_x = max(xs) + TAB_SPACING

    newline = "\r\n" if "\r\n" in text else "\n"

    def snippet(name, **subs):
        s = (SNIPPETS / name).read_text(encoding="utf-8")
        for k, v in subs.items():
            s = s.replace("{" + k + "}", str(v))
        if not s.endswith("\n"):
            s += "\n"
        return s.replace("\r\n", "\n").replace("\n", newline)

    # The folder window goes right before the folder_tabs window (where vanilla
    # keeps its folders); the tab button goes at the end of folder_tabs.
    # Apply the later offset first so the earlier one stays valid.
    header = text.rfind("containerWindowType", 0, folder_tabs.open)
    edits = sorted([
        (header, snippet("zombie_folder.gui")),
        (folder_tabs.close, snippet("zombie_folder_tab.gui", TAB_X=tab_x)),
    ], reverse=True)
    for anchor, snip in edits:
        pos = line_start(text, anchor)
        if text[pos:anchor].strip():
            # the anchor shares its line with other content: break the line
            pos = anchor
            snip = newline + snip
        text = text[:pos] + snip + text[pos:]

    # Sanity check: the result must still parse and contain both new windows.
    patched_root = clausewitz.parse(text)
    patched_view = clausewitz.find_named(patched_root, "countrytechtreeview", key="containerWindowType")[0]
    assert clausewitz.find_named(patched_view, "zombie_folder"), "folder window missing after patch"
    assert clausewitz.find_named(patched_view, "zombie_folder_tab"), "tab button missing after patch"
    return text, tab_x


def read_text(path):
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw[3:].decode("utf-8", errors="surrogateescape") if bom else \
        raw.decode("utf-8", errors="surrogateescape")
    return text, bom


def write_text(path, text, bom):
    data = text.encode("utf-8", errors="surrogateescape")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + data)


# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--game-dir", type=Path,
                    help="HoI4 install folder (the one containing 'interface' and 'common')")
    ap.add_argument("--user-dir", type=Path,
                    help="HoI4 user folder (the one containing 'mod' and 'save games')")
    ap.add_argument("--tab-x", type=int, help="x position of the Necrotech tab, in pixels")
    ap.add_argument("--no-copy", action="store_true",
                    help="do not install; only write the patched GUI into this repository's mod folder")
    args = ap.parse_args(argv)

    try:
        game_dir = args.game_dir or find_game_dir()
        if game_dir is None:
            raise InstallError("could not find Hearts of Iron IV. Pass --game-dir \"<install folder>\"")
        vanilla = game_dir / GUI_REL
        if not vanilla.is_file():
            raise InstallError(f"{vanilla} does not exist - is --game-dir the HoI4 install folder?")
        print(f"Game folder:  {game_dir}")

        if args.no_copy:
            mod_dir = MOD_SRC
        else:
            user_dir = args.user_dir or find_user_dir()
            if user_dir is None:
                raise InstallError("could not find the HoI4 user folder (Documents/Paradox Interactive/"
                                   "Hearts of Iron IV). Start the game once, or pass --user-dir.")
            print(f"User folder:  {user_dir}")
            mods = user_dir / "mod"
            mod_dir = mods / MOD_NAME
            if mod_dir.resolve() != MOD_SRC.resolve():
                if mod_dir.exists():
                    shutil.rmtree(mod_dir)
                shutil.copytree(MOD_SRC, mod_dir,
                                ignore=shutil.ignore_patterns("countrytechtreeview.gui"))
            descriptor = (MOD_SRC / "descriptor.mod").read_text(encoding="utf-8").rstrip("\n")
            mod_file = mods / f"{MOD_NAME}.mod"
            mod_file.write_text(f'{descriptor}\npath="{mod_dir.as_posix()}"\n', encoding="utf-8")
            print(f"Installed:    {mod_dir}")
            print(f"Launcher file:{mod_file}")

        text, bom = read_text(vanilla)
        patched, tab_x = patch_gui(text, args.tab_x)
        out = mod_dir / GUI_REL
        write_text(out, patched, bom)
        print(f"Tech screen:  {out} (Necrotech tab at x={tab_x})")
        print("\nDone. Enable 'Zombie Outbreak' in the launcher's playset and start the game.")
        print("Re-run this script after every HoI4 update.")
        return 0
    except InstallError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
