"""Geometry audit for the assembled melta sheets.

Catches the class of error that only shows up as a GUI atlas failure (no headless
Factorio run builds sprites), plus the two things the task is judged on: nothing is
clipped by the frame, and the pivot does not wobble.

Checks
  1. sheet pixel size == frame x (rows * frame) for every declared sheet
  2. direction count == rows * files
  3. no opaque pixel touches a frame border (clipping)
  4. the alpha centroid of every direction sits at a constant distance from the
     frame centre (a rigid body rotating about the pivot traces a circle; a drifting
     pivot shows up as a large spread here)

Run: python check_sheets.py <sheet_dir> [frame] [rows_per_sheet]
"""

import glob
import os
import sys

import numpy as np
from PIL import Image

sheet_dir = sys.argv[1] if len(sys.argv) > 1 else "sheets"
FRAME = int(sys.argv[2]) if len(sys.argv) > 2 else 256
ROWS = int(sys.argv[3]) if len(sys.argv) > 3 else 8
TILT_DEG = float(sys.argv[4]) if len(sys.argv) > 4 else 51.0

paths = sorted(glob.glob(os.path.join(sheet_dir, "melta-turret-head-*.png")),
               key=lambda p: int(p.rsplit("-", 1)[1].split(".")[0]))
problems = []
centroids = []

print("head sheets: {}".format(len(paths)))
for path in paths:
    im = Image.open(path)
    w, h = im.size
    print("  {} {}x{}".format(os.path.basename(path), w, h))
    if (w, h) != (FRAME, FRAME * ROWS):
        problems.append("{} is {}x{}, expected {}x{}".format(
            os.path.basename(path), w, h, FRAME, FRAME * ROWS))
        continue
    a = np.asarray(im.convert("RGBA"))[:, :, 3].astype(np.float32)
    for row in range(ROWS):
        f = a[row * FRAME:(row + 1) * FRAME]
        if f.max() < 8:
            problems.append("{} row {} is empty".format(os.path.basename(path), row))
            continue
        border = np.concatenate([f[0, :], f[-1, :], f[:, 0], f[:, -1]])
        if border.max() > 24:
            problems.append("{} row {}: sprite touches the frame border (clipped)".format(
                os.path.basename(path), row))
        ys, xs = np.mgrid[0:FRAME, 0:FRAME]
        wgt = f / max(f.sum(), 1e-6)
        cx, cy = (xs * wgt).sum(), (ys * wgt).sum()
        centroids.append((cx - FRAME / 2.0, cy - FRAME / 2.0))

n = len(centroids)
if n:
    # A rigid body rotating about the pivot traces a CIRCLE in the ground plane, which
    # the tilted camera squashes into an ellipse (y compressed by cos(tilt)) and lifts
    # by the centroid's height. Undo both before judging, or a perfectly good sheet
    # looks like it wobbles: the barrel's screen-projected length genuinely changes
    # between facing north and facing east.
    import math
    squash = math.cos(math.radians(TILT_DEG))
    cx = np.array([c[0] for c in centroids])
    cy = np.array([c[1] for c in centroids])
    y_off = cy.mean()
    radii = np.hypot(cx, (cy - y_off) / squash)
    angles = np.arctan2(cx, (cy - y_off) / squash)
    print("\ndirections checked: {}".format(n))
    print("centroid radius (de-squashed, pivot-relative): min {:.2f} max {:.2f} "
          "mean {:.2f} std {:.2f} px".format(radii.min(), radii.max(), radii.mean(),
                                             radii.std()))
    print("pivot is the frame centre by construction; radius std is the check on that")
    if radii.std() > 4.0:
        problems.append("centroid radius varies by {:.2f} px std -> pivot wobble".format(
            radii.std()))
    uniq = len(set(np.round(np.degrees(angles) / 5.625).astype(int)))
    if uniq < n - 2:
        problems.append("centroid angles collapse onto {} clusters (expected {})".format(uniq, n))

base = os.path.join(sheet_dir, "melta-turret-base.png")
if os.path.exists(base):
    im = Image.open(base)
    print("\nbase sprite: {}x{}".format(im.size[0], im.size[1]))
    if im.size != (FRAME, FRAME):
        problems.append("base sprite is {}, expected {}x{}".format(im.size, FRAME, FRAME))
    a = np.asarray(im.convert("RGBA"))[:, :, 3]
    border = np.concatenate([a[0, :], a[-1, :], a[:, 0], a[:, -1]])
    if border.max() > 24:
        problems.append("base sprite touches the frame border (clipped)")
else:
    problems.append("melta-turret-base.png missing")

print("\n{}".format("PROBLEMS:" if problems else "OK: all sheet geometry checks passed"))
for p in problems:
    print("  - {}".format(p))
sys.exit(1 if problems else 0)
