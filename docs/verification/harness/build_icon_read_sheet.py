"""Build the icon read sheet: the shipped melta icon next to vanilla's, at 64 px and at
the 32 px GUI mip, from the COMMITTED files, plus the numbers that make the read a
measurement instead of an opinion.

    python docs/verification/harness/build_icon_read_sheet.py
    # -> docs/verification/art/icon-turret-read.png
    # -> docs/verification/art/icon-turret-read.txt   (the metric table)

Every column is measured with graphics/_blender/icon_read.py, the same code the icon
acceptance quotes, so the picture and the numbers cannot disagree.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = "E:/SteamLibrary/steamapps/common/Factorio/data"
OUT_DIR = os.path.join(REPO, "docs", "verification", "art")
sys.path.insert(0, os.path.join(REPO, "graphics", "_blender"))

import icon_read as R  # noqa: E402

VANILLA = [("gun", "base/graphics/icons/gun-turret.png"),
           ("flamer", "base/graphics/icons/flamethrower-turret.png"),
           ("laser", "base/graphics/icons/laser-turret.png"),
           ("artillery", "base/graphics/icons/artillery-turret.png"),
           ("rocket", "space-age/graphics/icons/rocket-turret.png")]
OURS = ("melta", os.path.join(REPO, "graphics", "icons", "melta-turret.png"))

BG = (81, 81, 81)        # Factorio GUI panel grey
TEXT = (226, 226, 226)
SUB = (190, 190, 150)


def font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def mip(im, size):
    if size == 64:
        return im.crop((0, 0, 64, 64))
    x = 64
    s = 64
    while s > size:
        x += s // 2
        s //= 2
    return im.crop((x - s, 0, x, s))


def cell(im, size, zoom):
    small = im.resize((size, size), Image.LANCZOS)
    big = small.resize((size * zoom, size * zoom), Image.NEAREST)
    canvas = Image.new("RGB", (size * zoom, size * zoom), BG)
    canvas.paste(big, (0, 0), big)
    return canvas


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cols = []
    for name, rel in VANILLA:
        cols.append((name, Image.open(os.path.join(GAME, rel)).convert("RGBA"), False))
    cols.append((OURS[0], Image.open(OURS[1]).convert("RGBA"), True))

    z64, z32 = 5, 10
    pad = 14
    cw = 64 * z64
    panes = [("64 px art, x5 nearest", 64, z64),
             ("32 px GUI mip (the size the crafting menu draws), x10 nearest", 32, z32),
             ("both at true size on the GUI panel grey", 0, 0)]
    h_rows = (20 + cw + 8) + (20 + cw + 8) + (20 + 64 + 22 + 64 + 30) + 40
    W = pad + (cw + pad) * len(cols)
    sheet = Image.new("RGB", (W, h_rows + pad), (28, 29, 31))
    draw = ImageDraw.Draw(sheet)
    f16, f13, f12 = font(16), font(13), font(12)

    y = pad
    for label, size, zoom in panes[:2]:
        draw.text((pad, y), label, fill=TEXT, font=f16)
        y += 20
        x = pad
        for name, im, ours in cols:
            sheet.paste(cell(mip(im, size), size, zoom), (x, y))
            m = R.measure(im, size)
            cap = "%s  reach %.2f  protr %.0f%%  neck %.2f" % (
                name, m["reach"], m["protrusion_pct"], m["neck"])
            draw.text((x + 2, y + cw - 14), cap, fill=TEXT if ours else SUB, font=f12)
            x += cw + pad
        y += cw + 8

    # true size, twice: 64 px icons and the 32 px mip, on the panel grey
    draw.text((pad, y), panes[2][0], fill=TEXT, font=f16)
    y += 20
    x = pad
    for name, im, ours in cols:
        draw.text((x, y), name, fill=TEXT if ours else SUB, font=f13)
        x += 90
    y += 18
    x = pad
    for name, im, ours in cols:
        sheet.paste(mip(im, 64), (x, y), mip(im, 64))
        x += 90
    y += 70
    x = pad
    for name, im, ours in cols:
        sheet.paste(mip(im, 32), (x, y), mip(im, 32))
        x += 90

    out = os.path.join(OUT_DIR, "icon-turret-read.png")
    sheet.save(out)
    print("wrote", out, sheet.size)

    lines = []
    for size in (64, 32):
        lines.append("== %d px ==" % size)
        for name, im, _ in cols:
            m = R.measure(im, size)
            lines.append("%-10s cov %4.1f%%  bbox %dx%d  elong %4.2f  reach %4.2f  "
                         "protr %4.1f%%  neck %4.2f  masses %d  luma %3.0f  "
                         "white %4.1f%%  darklimb %+6.1f"
                         % (name, m["coverage"], m["bbox"][0], m["bbox"][1],
                            m["elongation"], m["reach"], m["protrusion_pct"], m["neck"],
                            m["masses"], m["mean"], m["white_pct"], m["limb_dark"]))
        lines.append("")
    txt = os.path.join(OUT_DIR, "icon-turret-read.txt")
    with open(txt, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("wrote", txt)
    print("\n".join(lines))


main()
