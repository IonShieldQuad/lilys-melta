"""Compose the FINAL sheets (base + head) on a ground tile at 2x for review."""
import os
import sys

from PIL import Image, ImageDraw

SHEETS = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else "final_preview.png"
DIRS = [0, 8, 16, 24, 32, 40, 48, 56]
ZOOM = 2

base = Image.open(os.path.join(SHEETS, "melta-turret-base.png")).convert("RGBA")


def head_frame(d):
    sheet = Image.open(os.path.join(SHEETS, "melta-turret-head-{}.png".format(d // 8 + 1)))
    f = sheet.convert("RGBA").crop((0, (d % 8) * 256, 256, (d % 8 + 1) * 256))
    return f


def ground(w, h):
    img = Image.new("RGBA", (w, h), (62, 78, 46, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, h, 64):
        for x in range(0, w, 64):
            v = 5 if ((x // 64 + y // 64) % 2) else 0
            d.rectangle([x, y, x + 63, y + 63], fill=(62 + v, 78 + v, 46 + v, 255))
    return img


cw = 256 * ZOOM
canvas = ground(cw * len(DIRS), 256 * ZOOM)
for i, d in enumerate(DIRS):
    cell = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    cell.alpha_composite(base)
    cell.alpha_composite(head_frame(d))
    canvas.alpha_composite(cell.resize((cw, cw), Image.LANCZOS), (i * cw, 0))
canvas.save(OUT)
print("wrote", OUT, canvas.size)
