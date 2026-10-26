"""Numeric palette comparison: an assembled melta sheet vs the vanilla turrets.

    python palette_vs_vanilla.py <tex_dir> [--tex2 <dir>]

`<tex_dir>` holds melta-turret-base.png + melta-turret-head-1..8.png. Prints the same
luma/colour table for the melta layers and for the vanilla gun/laser/flamer sprites,
so "too dark / too pale" is a number and not an opinion.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

DATA = "E:/SteamLibrary/steamapps/common/Factorio/data/base/graphics/entity"


def stat(arr, label):
    a = np.asarray(arr).astype(np.float32)
    m = a[:, :, 3] > 128
    if m.sum() == 0:
        return None
    rgb = a[:, :, :3][m]
    lum = 0.2126 * rgb[:, 0] + 0.7152 * rgb[:, 1] + 0.0722 * rgb[:, 2]
    q = np.percentile(lum, [10, 25, 50, 75, 90])
    r, g, b = rgb.mean(axis=0)
    return (label, int(m.sum()), lum.mean(), q, (r - b),
            (lum < 16).mean() * 100, (rgb.min(axis=1) > 225).mean() * 100)


def show(s):
    if not s:
        print("  (empty)")
        return
    label, n, mean, q, warm, dark, white = s
    print("%-28s %7d  mean %5.1f  p10 %5.1f p25 %5.1f p50 %5.1f p75 %5.1f p90 %5.1f"
          "  warm %+5.1f  dark %4.1f%%  white %4.2f%%"
          % (label, n, mean, q[0], q[1], q[2], q[3], q[4], warm, dark, white))


def melta(tex):
    out = []
    p = os.path.join(tex, "melta-turret-base.png")
    if os.path.exists(p):
        out.append(stat(Image.open(p), "MELTA base"))
    frames = []
    for i in range(1, 9):
        p = os.path.join(tex, "melta-turret-head-%d.png" % i)
        if os.path.exists(p):
            im = np.asarray(Image.open(p).convert("RGBA"))
            for r in range(8):
                frames.append(im[r * 256:(r + 1) * 256])
    if frames:
        stacked = np.concatenate(frames, axis=0)          # (n*256, 256, 4)
        out.append(stat(stacked, "MELTA head (64 frames)"))
        for d in (0, 16, 32, 48):
            out.append(stat(frames[d], "MELTA head dir %d" % d))
    return out


def main():
    tex = sys.argv[1]
    print("%-28s %7s  %s" % ("sprite", "px", "luma / colour"))
    for s in melta(tex):
        show(s)
    print("-" * 120)
    show(stat(Image.open(DATA + "/gun-turret/gun-turret-base.png"), "vanilla gun base"))
    im = np.asarray(Image.open(DATA + "/gun-turret/gun-turret-shooting-1.png").convert("RGBA"))
    fr = [im[r * 130:(r + 1) * 130, c * 132:(c + 1) * 132] for r in range(16) for c in range(2)]
    show(stat(np.concatenate([f.reshape(-1, 4) for f in fr]).reshape(1, -1, 4),
              "vanilla gun head"))
    show(stat(Image.open(DATA + "/laser-turret/laser-turret-base.png"), "vanilla laser base"))
    show(stat(Image.open(DATA + "/flamethrower-turret/flamethrower-turret-base-north.png"),
              "vanilla flamer base N"))
    show(stat(Image.open(DATA + "/flamethrower-turret/flamethrower-turret-base-east.png"),
              "vanilla flamer base E"))


main()
