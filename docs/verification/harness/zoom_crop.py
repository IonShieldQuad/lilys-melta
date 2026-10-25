"""Crop and upscale (nearest neighbour) one region of a screenshot for inspection.

Usage: python zoom_crop.py <src> <x> <y> <w> <h> <scale> <out>
Coordinates are in the source image's pixels, origin top-left.
"""
import sys

from PIL import Image

src, x, y, w, h, scale, out = (sys.argv[1], int(sys.argv[2]), int(sys.argv[3]),
                               int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]),
                               sys.argv[7])
im = Image.open(src).convert("RGB")
im.crop((x, y, x + w, y + h)).resize((w * scale, h * scale), Image.NEAREST).save(out)
print("%s -> %s (%dx%d)" % (src, out, w * scale, h * scale))
