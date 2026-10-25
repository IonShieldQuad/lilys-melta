"""Crop the inspect panel and the world area out of the hover captures.

The captures are whole-virtual-desktop grabs (3840x1080 here: the game window occupies
x 1920..3840, the other monitor 0..1920), so both crops need the window's own offset.
Usage: python crop_panels.py <hover dir> <out dir>
"""
import os
import sys

from PIL import Image

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, "crop")
os.makedirs(out, exist_ok=True)

names = sorted(f for f in os.listdir(src) if f.endswith(".png") and "_leg" in f
               and not f.endswith("_b.png"))
for name in names:
    im = Image.open(os.path.join(src, name))
    w, h = im.size
    right = w                      # game window's right edge
    im.crop((right - 720, 0, right, h)).save(os.path.join(out, "panel_" + name))
    im.crop((w - 1920 + 560, 196, w - 1920 + 1360, 756)).save(os.path.join(out, "world_" + name))
    print("%s -> panel_%s, world_%s" % (name, name, name))
