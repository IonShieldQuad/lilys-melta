"""Print a coarse ASCII map of one screenshot region: floor vs not-floor.

Built for the pipe-join question "is there bare floor between the hull rim and the port".
Refined concrete is a low-contrast mid grey; machine art is darker or more saturated with
strong local contrast, so both mean brightness and local variance separate them.

Usage: python floor_map.py <src> <x> <y> <w> <h> [block]
"""
import sys

from PIL import Image

src, x, y, w, h = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
block = int(sys.argv[6]) if len(sys.argv) > 6 else 8

im = Image.open(src).convert("RGB")
px = im.load()


def stats(bx, by):
    vals = []
    for yy in range(by, by + block):
        for xx in range(bx, bx + block):
            r, g, b = px[xx, yy]
            vals.append((r + g + b) / 3.0)
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return mean, var ** 0.5


rows = []
for by in range(y, y + h, block):
    line = ""
    for bx in range(x, x + w, block):
        mean, sd = stats(bx, by)
        if mean > 235:
            line += "#"          # bright (plates, highlight)
        elif mean < 45:
            line += "@"          # very dark (bore, deep shade)
        elif sd < 9:
            line += "."          # flat -> floor tile
        else:
            line += "+"          # textured -> machine art
    rows.append("%4d %s" % (by, line))
print("cols: x from %d, one char = %d px" % (x, block))
print("\n".join(rows))
