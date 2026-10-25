"""Review image for the icons: the shipped ones next to the vanilla turret icons
they sit beside, at 64 px and at the 32 px GUI size, plus the technology icon and
the mod thumbnail.

Run:  python preview_icons.py [<out.png>]
Writes graphics/_blender/preview-icons.png (same convention as
preview-rotations.png / preview-vs-vanilla.png) and reads the installed game's own
icons, so it only runs on this machine.
"""

import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", ".."))
GAME = "E:/SteamLibrary/steamapps/common/Factorio/data"
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "preview-icons.png")

VANILLA = [("gun-turret", "base/graphics/icons/gun-turret.png"),
           ("flamer-turret", "base/graphics/icons/flamethrower-turret.png"),
           ("rocket-turret", "space-age/graphics/icons/rocket-turret.png")]

BG = (40, 41, 44)
PAD = 10


def base_square(path):
    """Vanilla icon files are base + packed mips; keep the base square only."""
    im = Image.open(path).convert("RGBA")
    return im.crop((0, 0, im.height, im.height))


def cell(im, size, zoom, bg=BG):
    """Draw `im` at `size` px (LANCZOS) over a flat background, zoomed for review."""
    small = im.resize((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size * zoom, size * zoom), bg)
    big = small.resize((size * zoom, size * zoom), Image.NEAREST)
    canvas.paste(big, (0, 0), big)
    return canvas


icons = [(name, base_square(os.path.join(GAME, rel))) for name, rel in VANILLA]
ours = Image.open(os.path.join(MOD, "graphics/icons/melta-turret.png")).convert("RGBA")
icons.append(("melta-turret", ours.crop((0, 0, 64, 64))))
tech = Image.open(os.path.join(MOD, "graphics/icons/melta-turret-technology.png")).convert("RGBA")
thumb = Image.open(os.path.join(MOD, "thumbnail.png")).convert("RGB")
thumb144 = Image.open(os.path.join(MOD, "thumbnail-144.png")).convert("RGB")

Z = 5
CELL = 64 * Z
rows = ["64 px art (x%d)" % Z, "32 px GUI size (x10)"]
W = PAD + (CELL + PAD) * len(icons)
tech_w = 256
H = 22 + CELL + 6 + CELL + 26 + tech_w + 26 + 144 + 4 * PAD
sheet = Image.new("RGB", (max(W, tech_w + 3 * PAD + 160), H), (28, 29, 31))
draw = ImageDraw.Draw(sheet)

y = PAD
for label, size, zoom in (("icons at 64 px (x5 nearest)", 64, 5), ("same icons at 32 px GUI size (x10)", 32, 10)):
    draw.text((PAD, y), label, fill=(226, 226, 226))
    y += 16
    x = PAD
    for name, im in icons:
        sheet.paste(cell(im, size, zoom), (x, y))
        draw.text((x + 2, y + 64 * 5 - 12), name, fill=(190, 190, 150))
        x += 64 * 5 + PAD
    y += 64 * 5 + PAD

draw.text((PAD, y), "technology icon, 256 px base from a 480x256 file with packed mips",
          fill=(226, 226, 226))
y += 16
sheet.paste(tech.crop((0, 0, 256, 256)), (PAD, y), tech.crop((0, 0, 256, 256)))
sheet.paste(thumb144, (PAD + 256 + PAD, y))
draw.text((PAD + 256 + PAD, y + 144 + 4), "thumbnail.png at 144 (portal size)", fill=(190, 190, 150))
draw.text((PAD, y + 256 + 4), "melta-turret-technology.png (256 px base)", fill=(190, 190, 150))

sheet.save(OUT)
print(OUT, sheet.size)
