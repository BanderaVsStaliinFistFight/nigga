#!/usr/bin/env python3
"""Regenerate every texture shipped with the Zombie Outbreak mod.

The art is drawn procedurally with Pillow so the mod contains no third-party
assets. Run it after changing a drawing:

    python tools/generate_art.py

Requires Pillow (pip install pillow). Textures are written as uncompressed
32-bit BGRA .dds files, the same format the base game uses for UI sprites.
"""

import math
import struct
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MOD = Path(__file__).resolve().parent.parent / "zombie_outbreak"
SS = 4  # supersampling factor; everything is drawn big and scaled down

SKIN = (122, 168, 82, 255)
SKIN_DARK = (70, 105, 46, 255)
BONE = (226, 220, 192, 255)
BLOOD = (150, 22, 22, 255)
GLOW = (170, 255, 90, 255)
INK = (16, 18, 14, 255)
METAL = (58, 62, 58, 255)
METAL_LIGHT = (110, 116, 108, 255)
GLASS = (200, 215, 205, 255)


# --------------------------------------------------------------------------
# File output
# --------------------------------------------------------------------------

def write_dds(img, path):
    """Write an uncompressed A8R8G8B8 DDS (no mipmaps)."""
    img = img.convert("RGBA")
    w, h = img.size
    flags = 0x1 | 0x2 | 0x4 | 0x8 | 0x1000  # CAPS|HEIGHT|WIDTH|PITCH|PIXELFORMAT
    pixel_format = struct.pack(
        "<II4sIIIII",
        32,          # size
        0x41,        # DDPF_RGB | DDPF_ALPHAPIXELS
        b"\0\0\0\0",  # no FourCC
        32,          # bits per pixel
        0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000,
    )
    header = struct.pack("<4sIIIIIII", b"DDS ", 124, flags, h, w, w * 4, 0, 0)
    header += b"\0" * 44  # reserved
    header += pixel_format
    header += struct.pack("<IIIII", 0x1000, 0, 0, 0, 0)  # DDSCAPS_TEXTURE
    assert len(header) == 128
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + img.tobytes("raw", "BGRA"))


def canvas(w, h):
    img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def finish(img, w, h):
    return img.resize((w, h), Image.LANCZOS)


def S(*vals):
    """Scale coordinates into supersampled space."""
    return [v * SS for v in vals]


# --------------------------------------------------------------------------
# Drawing primitives (coordinates are given in final-pixel units)
# --------------------------------------------------------------------------

def skull(d, cx, cy, r, skin=SKIN, eyes=GLOW, jaw_open=False, stitches=False):
    """Zombie head: cranium, sunken eyes, nose hole, ragged jaw."""
    o = max(1, r * 0.12)
    d.ellipse(S(cx - r - o, cy - r - o, cx + r + o, cy + r * 0.85 + o), fill=INK)
    d.rounded_rectangle(S(cx - r * 0.62 - o, cy + r * 0.2, cx + r * 0.62 + o,
                          cy + r * (1.55 if jaw_open else 1.3) + o), radius=r * 0.3 * SS, fill=INK)
    d.ellipse(S(cx - r, cy - r, cx + r, cy + r * 0.85), fill=skin)
    d.rounded_rectangle(S(cx - r * 0.62, cy + r * 0.2, cx + r * 0.62,
                          cy + r * (1.55 if jaw_open else 1.3)), radius=r * 0.3 * SS, fill=skin)
    # rot patches
    d.ellipse(S(cx - r * 0.85, cy - r * 0.55, cx - r * 0.35, cy - r * 0.15), fill=SKIN_DARK)
    d.ellipse(S(cx + r * 0.2, cy - r * 0.9, cx + r * 0.65, cy - r * 0.5), fill=SKIN_DARK)
    # eye sockets
    for sx in (-1, 1):
        ex = cx + sx * r * 0.4
        d.ellipse(S(ex - r * 0.3, cy - r * 0.1, ex + r * 0.3, cy + r * 0.42), fill=INK)
        d.ellipse(S(ex - r * 0.1, cy + r * 0.06, ex + r * 0.1, cy + r * 0.26), fill=eyes)
    # nose
    d.polygon(S(cx, cy + r * 0.38, cx - r * 0.13, cy + r * 0.62, cx + r * 0.13, cy + r * 0.62), fill=INK)
    # mouth + teeth
    top = cy + r * 0.8
    bottom = cy + r * (1.35 if jaw_open else 1.05)
    d.rectangle(S(cx - r * 0.42, top, cx + r * 0.42, bottom), fill=INK)
    if jaw_open:
        d.rectangle(S(cx - r * 0.36, top + r * 0.12, cx + r * 0.36, bottom - r * 0.1), fill=BLOOD)
    n = 5
    tw = r * 0.84 / n
    for i in range(n):
        x0 = cx - r * 0.42 + i * tw + tw * 0.15
        d.rectangle(S(x0, top, x0 + tw * 0.7, top + r * 0.16), fill=BONE)
        if jaw_open:
            d.rectangle(S(x0, bottom - r * 0.16, x0 + tw * 0.7, bottom), fill=BONE)
    if stitches:
        y = cy - r * 0.6
        d.line(S(cx - r * 0.7, y, cx + r * 0.7, y - r * 0.15), fill=INK, width=max(1, int(r * 0.12 * SS)))
        for i in range(5):
            x = cx - r * 0.55 + i * r * 0.28
            yy = y - r * 0.15 * (x - (cx - r * 0.7)) / (r * 1.4)
            d.line(S(x, yy - r * 0.14, x, yy + r * 0.14), fill=INK, width=max(1, int(r * 0.08 * SS)))


def hand(d, cx, base, size, skin=SKIN):
    """A rotting hand bursting up out of the ground."""
    s = size
    # ground
    d.ellipse(S(cx - s * 1.5, base - s * 0.25, cx + s * 1.5, base + s * 0.35), fill=(70, 52, 34, 255))
    d.ellipse(S(cx - s * 1.2, base - s * 0.15, cx + s * 1.2, base + s * 0.2), fill=(96, 72, 46, 255))
    fingers = [(-0.55, 1.55, -8), (-0.18, 1.85, -2), (0.2, 1.75, 4), (0.55, 1.4, 10)]
    for fx, fl, ang in fingers:
        x = cx + fx * s
        top = base - s * 0.9 - fl * s * 0.6
        d.rounded_rectangle(S(x - s * 0.2, top - 1, x + s * 0.2, base - s * 0.6), radius=s * 0.18 * SS, fill=INK)
        d.rounded_rectangle(S(x - s * 0.14, top, x + s * 0.14, base - s * 0.6), radius=s * 0.13 * SS, fill=skin)
    # thumb
    d.polygon(S(cx - s * 0.75, base - s * 0.8, cx - s * 1.25, base - s * 1.45,
                cx - s * 1.05, base - s * 1.55, cx - s * 0.6, base - s * 1.05), fill=INK)
    d.polygon(S(cx - s * 0.72, base - s * 0.85, cx - s * 1.18, base - s * 1.43,
                cx - s * 1.04, base - s * 1.48, cx - s * 0.63, base - s * 1.05), fill=skin)
    # palm + wrist
    d.rounded_rectangle(S(cx - s * 0.8, base - s * 1.2, cx + s * 0.8, base - s * 0.05), radius=s * 0.3 * SS, fill=INK)
    d.rounded_rectangle(S(cx - s * 0.72, base - s * 1.12, cx + s * 0.72, base - s * 0.1), radius=s * 0.25 * SS, fill=skin)
    d.ellipse(S(cx - s * 0.3, base - s * 0.8, cx + s * 0.25, base - s * 0.4), fill=SKIN_DARK)
    d.line(S(cx - s * 0.5, base - s * 0.55, cx + s * 0.1, base - s * 0.3), fill=BLOOD, width=max(1, int(s * 0.1 * SS)))


def syringe(d, cx, cy, length, fill_frac=0.7, liquid=GLOW):
    """Horizontal syringe full of glowing reanimation serum."""
    L = length
    h = L * 0.22
    x0, x1 = cx - L * 0.38, cx + L * 0.28
    # plunger
    d.rectangle(S(x0 - L * 0.16, cy - L * 0.03, x0, cy + L * 0.03), fill=INK)
    d.rectangle(S(x0 - L * 0.2, cy - h * 0.6, x0 - L * 0.14, cy + h * 0.6), fill=INK)
    d.rectangle(S(x0 - L * 0.19, cy - h * 0.5, x0 - L * 0.15, cy + h * 0.5), fill=METAL_LIGHT)
    # barrel
    d.rounded_rectangle(S(x0 - 1, cy - h / 2 - 1, x1 + 1, cy + h / 2 + 1), radius=h * 0.2 * SS, fill=INK)
    d.rectangle(S(x0, cy - h / 2, x1, cy + h / 2), fill=GLASS)
    lx = x1 - (x1 - x0) * fill_frac
    d.rectangle(S(lx, cy - h / 2 + 1, x1, cy + h / 2 - 1), fill=liquid)
    d.rectangle(S(lx, cy - h / 2 + 1, x1, cy - h / 2 + 2.2), fill=(230, 255, 200, 255))
    for i in range(1, 5):
        tx = x0 + (x1 - x0) * i / 5
        d.line(S(tx, cy - h / 2, tx, cy - h * 0.15), fill=INK, width=SS)
    # flanges + needle
    d.rectangle(S(x0 - L * 0.04, cy - h * 0.85, x0 + L * 0.01, cy + h * 0.85), fill=INK)
    d.polygon(S(x1, cy - h * 0.35, x1 + L * 0.08, cy - h * 0.12, x1 + L * 0.08, cy + h * 0.12, x1, cy + h * 0.35), fill=INK)
    d.line(S(x1 + L * 0.08, cy, x1 + L * 0.38, cy), fill=INK, width=int(SS * 2.2))
    d.line(S(x1 + L * 0.08, cy, x1 + L * 0.37, cy), fill=METAL_LIGHT, width=int(SS * 1.0))


def biohazard(d, cx, cy, r, color=GLOW):
    """Simplified biohazard trefoil."""
    for k in range(3):
        a = math.radians(-90 + k * 120)
        px, py = cx + math.cos(a) * r * 0.5, cy + math.sin(a) * r * 0.5
        d.ellipse(S(px - r * 0.62, py - r * 0.62, px + r * 0.62, py + r * 0.62), fill=INK)
    for k in range(3):
        a = math.radians(-90 + k * 120)
        px, py = cx + math.cos(a) * r * 0.5, cy + math.sin(a) * r * 0.5
        d.ellipse(S(px - r * 0.52, py - r * 0.52, px + r * 0.52, py + r * 0.52), fill=color)
    for k in range(3):
        a = math.radians(-90 + k * 120)
        px, py = cx + math.cos(a) * r * 0.68, cy + math.sin(a) * r * 0.68
        d.ellipse(S(px - r * 0.36, py - r * 0.36, px + r * 0.36, py + r * 0.36), fill=INK)
    d.ellipse(S(cx - r * 0.32, cy - r * 0.32, cx + r * 0.32, cy + r * 0.32), fill=INK)
    d.ellipse(S(cx - r * 0.18, cy - r * 0.18, cx + r * 0.18, cy + r * 0.18), fill=color)
    d.ellipse(S(cx - r * 0.09, cy - r * 0.09, cx + r * 0.09, cy + r * 0.09), fill=INK)


def hound(d, cx, cy, s, facing=1, fur=(92, 84, 66, 255)):
    """Snarling infected dog head in profile."""
    f = facing

    def P(*pts):
        out = []
        for i in range(0, len(pts), 2):
            out += [cx + f * pts[i] * s, cy + pts[i + 1] * s]
        return S(*out)

    outline = P(-0.9, -0.2, -0.55, -0.95, -0.35, -0.55, -0.05, -0.65, 0.35, -0.35,
                1.1, -0.15, 1.15, 0.12, 0.55, 0.25, 0.75, 0.45, 0.2, 0.55, -0.6, 0.75, -0.95, 0.3)
    d.polygon(outline, fill=INK)
    inner = P(-0.8, -0.2, -0.53, -0.8, -0.33, -0.45, -0.05, -0.55, 0.33, -0.27,
              1.03, -0.1, 1.06, 0.08, 0.5, 0.2, 0.66, 0.4, 0.2, 0.47, -0.57, 0.66, -0.86, 0.28)
    d.polygon(inner, fill=fur)
    d.polygon(P(-0.6, 0.1, -0.2, -0.2, 0.1, 0.0, -0.3, 0.4), fill=SKIN_DARK)  # rotten patch
    # mouth & fangs
    d.polygon(P(0.3, 0.16, 1.0, 0.1, 0.55, 0.3), fill=BLOOD)
    for tx in (0.45, 0.65, 0.85):
        d.polygon(P(tx, 0.1, tx + 0.06, 0.24, tx + 0.12, 0.1), fill=BONE)
    # nose and eye
    d.ellipse(P(1.0, -0.2, 1.18, -0.05), fill=INK)
    ex, ey = cx + f * 0.25 * s, cy - 0.25 * s
    d.ellipse(S(ex - 0.12 * s, ey - 0.1 * s, ex + 0.12 * s, ey + 0.1 * s), fill=INK)
    d.ellipse(S(ex - 0.06 * s, ey - 0.05 * s, ex + 0.06 * s, ey + 0.05 * s), fill=GLOW)


def bone(d, x0, y0, x1, y1, w):
    d.line(S(x0, y0, x1, y1), fill=INK, width=int((w + 1.5) * SS))
    for x, y in ((x0, y0), (x1, y1)):
        ang = math.atan2(y1 - y0, x1 - x0) + math.pi / 2
        for sgn in (-1, 1):
            bx, by = x + math.cos(ang) * w * 0.55 * sgn, y + math.sin(ang) * w * 0.55 * sgn
            d.ellipse(S(bx - w * 0.75, by - w * 0.75, bx + w * 0.75, by + w * 0.75), fill=INK)
    d.line(S(x0, y0, x1, y1), fill=BONE, width=int(w * SS))
    for x, y in ((x0, y0), (x1, y1)):
        ang = math.atan2(y1 - y0, x1 - x0) + math.pi / 2
        for sgn in (-1, 1):
            bx, by = x + math.cos(ang) * w * 0.55 * sgn, y + math.sin(ang) * w * 0.55 * sgn
            d.ellipse(S(bx - w * 0.55, by - w * 0.55, bx + w * 0.55, by + w * 0.55), fill=BONE)


def shield(d, cx, cy, s):
    pts = S(cx - s, cy - s * 0.9, cx + s, cy - s * 0.9, cx + s, cy + s * 0.1, cx, cy + s * 1.05, cx - s, cy + s * 0.1)
    d.polygon(pts, fill=INK)
    k = 0.85
    d.polygon(S(cx - s * k, cy - s * 0.78, cx + s * k, cy - s * 0.78, cx + s * k, cy + s * 0.05,
                cx, cy + s * 0.88, cx - s * k, cy + s * 0.05), fill=METAL)
    bone(d, cx - s * 0.55, cy - s * 0.45, cx + s * 0.55, cy + s * 0.35, s * 0.16)
    bone(d, cx + s * 0.55, cy - s * 0.45, cx - s * 0.55, cy + s * 0.35, s * 0.16)


def tier_marks(d, x, y, n):
    """Roman-numeral style bars marking an equipment tier."""
    for i in range(n):
        bx = x + i * 5
        d.rectangle(S(bx - 0.5, y - 0.5, bx + 3.5, y + 9.5), fill=INK)
        d.rectangle(S(bx, y, bx + 3, y + 9), fill=BONE)


def crown(d, cx, cy, s):
    pts = S(cx - s, cy + s * 0.4, cx - s, cy - s * 0.4, cx - s * 0.5, cy, cx, cy - s * 0.6,
            cx + s * 0.5, cy, cx + s, cy - s * 0.4, cx + s, cy + s * 0.4)
    d.polygon(pts, fill=INK)
    k = 0.82
    d.polygon(S(cx - s * k, cy + s * 0.3, cx - s * k, cy - s * 0.2, cx - s * 0.5, cy + s * 0.1, cx, cy - s * 0.42,
                cx + s * 0.5, cy + s * 0.1, cx + s * k, cy - s * 0.2, cx + s * k, cy + s * 0.3), fill=(214, 170, 50, 255))


# --------------------------------------------------------------------------
# Icon compositions
# --------------------------------------------------------------------------

TECH_W, TECH_H = 120, 44  # technology and equipment icons


def icon_reanimation():
    img, d = canvas(TECH_W, TECH_H)
    hand(d, 42, 40, 13)
    skull(d, 86, 17, 12)
    return finish(img, TECH_W, TECH_H)


def icon_serum(tier):
    img, d = canvas(TECH_W, TECH_H)
    colours = {1: GLOW, 2: (120, 240, 200, 255), 3: (230, 120, 255, 255)}
    syringe(d, 58, 22, 92, fill_frac=0.45 + 0.2 * tier, liquid=colours[tier])
    tier_marks(d, 116 - tier * 5, 3, tier)
    return finish(img, TECH_W, TECH_H)


def icon_serum_archetype():
    img, d = canvas(TECH_W, TECH_H)
    syringe(d, 58, 22, 92, fill_frac=0.75)
    return finish(img, TECH_W, TECH_H)


def icon_virulent():
    img, d = canvas(TECH_W, TECH_H)
    biohazard(d, 38, 22, 17)
    skull(d, 86, 17, 12)
    return finish(img, TECH_W, TECH_H)


def icon_hounds():
    img, d = canvas(TECH_W, TECH_H)
    hound(d, 60, 22, 26)
    return finish(img, TECH_W, TECH_H)


def icon_pack():
    img, d = canvas(TECH_W, TECH_H)
    hound(d, 42, 24, 20, fur=(76, 70, 56, 255))
    hound(d, 74, 20, 22)
    return finish(img, TECH_W, TECH_H)


def icon_brutes():
    img, d = canvas(TECH_W, TECH_H)
    skull(d, 60, 15, 16, skin=(104, 150, 70, 255), eyes=(255, 80, 60, 255), stitches=True)
    return finish(img, TECH_W, TECH_H)


def icon_hunger():
    img, d = canvas(TECH_W, TECH_H)
    skull(d, 60, 13, 15, jaw_open=True)
    return finish(img, TECH_W, TECH_H)


def icon_bone_plating():
    img, d = canvas(TECH_W, TECH_H)
    shield(d, 60, 21, 19)
    return finish(img, TECH_W, TECH_H)


def icon_apex():
    img, d = canvas(TECH_W, TECH_H)
    biohazard(d, 60, 24, 19, color=(120, 200, 70, 255))
    skull(d, 60, 21, 10, eyes=(255, 60, 60, 255))
    crown(d, 60, 5, 8)
    return finish(img, TECH_W, TECH_H)


# Division designer icons: frame 1 = portrait, frame 2 = NATO-style counter.
UNIT_W, UNIT_H = 76, 42


def nato_counter(d, ox, symbol):
    x0, y0, x1, y1 = ox + 9, 9, ox + 67, 34
    d.rectangle(S(x0 - 1, y0 - 1, x1 + 1, y1 + 1), fill=INK)
    steps = 12
    for i in range(steps):
        c = 205 - i * 5
        yy0 = y0 + (y1 - y0) * i / steps
        yy1 = y0 + (y1 - y0) * (i + 1) / steps
        d.rectangle(S(x0, yy0, x1, yy1), fill=(c - 25, c, c - 35, 255))
    w = int(1.3 * SS)
    if symbol in ("horde", "brute"):
        d.line(S(x0, y0, x1, y1), fill=INK, width=w)
        d.line(S(x0, y1, x1, y0), fill=INK, width=w)
    if symbol == "brute":
        d.rectangle(S(x0, y1 - 5, x1, y1), fill=INK)
    if symbol == "hounds":
        d.line(S(x0, y1, x1, y0), fill=INK, width=w)
    skull(d, (x0 + x1) / 2, (y0 + y1) / 2 - 3.5, 5.2)


def unit_icon(kind):
    img, d = canvas(UNIT_W * 2, UNIT_H)
    if kind == "horde":
        skull(d, 30, 15, 10)
        skull(d, 48, 17, 11)
    elif kind == "brute":
        skull(d, 38, 13, 13, skin=(104, 150, 70, 255), eyes=(255, 80, 60, 255), stitches=True)
    elif kind == "hounds":
        hound(d, 38, 21, 17)
    nato_counter(d, UNIT_W, kind)
    return finish(img, UNIT_W * 2, UNIT_H)


SMALL_W, SMALL_H = 35, 13


def small_icon(kind):
    img, d = canvas(SMALL_W * 2, SMALL_H)
    for ox in (0, SMALL_W):
        if kind == "hounds":
            hound(d, ox + 17, 6.5, 6.5)
        else:
            skull(d, ox + 17.5, 5, 4.6 if kind == "horde" else 5.2,
                  skin=SKIN if kind == "horde" else (104, 150, 70, 255))
    return finish(img, SMALL_W * 2, SMALL_H)


# Tech-tree folder tab: frame 1 = selected, frame 2 = not selected.
TAB_W, TAB_H = 91, 61


def plate(d, x0, y0, x1, y1, bright):
    d.rounded_rectangle(S(x0, y0, x1, y1), radius=4 * SS, fill=(28, 29, 27, 255))
    d.rounded_rectangle(S(x0 + 2, y0 + 2, x1 - 2, y1 - 2), radius=3 * SS,
                        fill=(78, 82, 76, 255) if bright else (62, 64, 60, 255))
    d.rounded_rectangle(S(x0 + 5, y0 + 5, x1 - 5, y1 - 5), radius=2 * SS, fill=(14, 16, 14, 255))
    for i in range(int(x0 + 6), int(x1 - 6), 3):  # mesh texture
        d.line(S(i, y0 + 6, i, y1 - 6), fill=(24, 28, 24, 255), width=SS)
    for rx, ry in ((x0 + 8, y0 + 8), (x1 - 8, y0 + 8), (x0 + 8, y1 - 8), (x1 - 8, y1 - 8)):
        d.ellipse(S(rx - 2, ry - 2, rx + 2, ry + 2), fill=METAL_LIGHT)
        d.ellipse(S(rx - 1, ry - 1, rx + 1, ry + 1), fill=INK)


def folder_tab():
    img, d = canvas(TAB_W * 2, TAB_H)
    plate(d, 3, 3, 88, 61, True)
    skull(d, 45.5, 22, 12)
    plate(d, TAB_W + 6, 9, TAB_W + 85, 46, False)
    skull(d, TAB_W + 45.5, 22, 9, skin=(100, 140, 70, 255), eyes=(120, 200, 70, 255))
    return finish(img, TAB_W * 2, TAB_H)


def thumbnail():
    size = 512
    img, d = canvas(size, size)
    for i in range(size):
        g = int(18 + 30 * (i / size))
        d.rectangle(S(0, i, size, i + 1), fill=(g // 2, g, g // 2, 255))
    biohazard(d, 256, 220, 190, color=(40, 70, 30, 255))
    hand(d, 120, 420, 34)
    hand(d, 400, 430, 28)
    skull(d, 256, 190, 95)
    small = img.resize((size, size), Image.LANCZOS)
    dd = ImageDraw.Draw(small)
    font = ImageFont.load_default(size=58)
    for text, y in (("ZOMBIE", 392), ("OUTBREAK", 448)):
        tw = dd.textlength(text, font=font)
        dd.text(((size - tw) / 2 + 3, y + 3), text, font=font, fill=(0, 0, 0, 255))
        dd.text(((size - tw) / 2, y), text, font=font, fill=(170, 255, 90, 255))
    return small.convert("RGB")


# --------------------------------------------------------------------------

def main():
    tech = MOD / "gfx/interface/technologies"
    icons = {
        "zombie_reanimation": icon_reanimation(),
        "zombie_virulent_strain": icon_virulent(),
        "zombie_stabilised_serum": icon_serum(2),
        "zombie_infected_hounds": icon_hounds(),
        "zombie_necrotic_brutes": icon_brutes(),
        "zombie_relentless_hunger": icon_hunger(),
        "zombie_pack_hunters": icon_pack(),
        "zombie_bone_plating": icon_bone_plating(),
        "zombie_perfected_serum": icon_serum(3),
        "zombie_apex_strain": icon_apex(),
        # equipment
        "zombie_serum_equipment": icon_serum_archetype(),
        "zombie_serum_equipment_1": icon_serum(1),
        "zombie_serum_equipment_2": icon_serum(2),
        "zombie_serum_equipment_3": icon_serum(3),
    }
    for name, img in icons.items():
        write_dds(img, tech / f"{name}.dds")

    for kind in ("horde", "brute", "hounds"):
        write_dds(unit_icon(kind), MOD / f"gfx/interface/counters/divisions_large/zombie_{kind}_icon.dds")
        write_dds(small_icon(kind), MOD / f"gfx/texticons/zombie_{kind}_icon_small.dds")

    write_dds(folder_tab(), MOD / "gfx/interface/techtree/zombie_folder_tab.dds")
    thumbnail().save(MOD / "thumbnail.png")
    print(f"Wrote {len(icons) + 7} textures and thumbnail.png under {MOD}")


if __name__ == "__main__":
    main()
