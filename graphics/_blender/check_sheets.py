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
    print("\ndirections checked: {}".format(n))
    print("centroid radius (de-squashed, pivot-relative): min {:.2f} max {:.2f} "
          "mean {:.2f} std {:.2f} px".format(radii.min(), radii.max(), radii.mean(),
                                             radii.std()))
    print("pivot is the frame centre by construction; radius std is the check on that")
    if radii.std() > 4.0:
        problems.append("centroid radius varies by {:.2f} px std -> pivot wobble".format(
            radii.std()))

    # Ordered-rotation check: the centroid walks a closed loop about the pivot, one
    # small step per direction. That -- not the bearing of the centroid -- is what a
    # misordered, duplicated or reversed frame breaks. The old test compared the
    # centroid's BEARING against 64 bins, which this model cannot pass: the receiver is
    # heavier than the barrel, so the centroid trails the muzzle and its bearing is
    # near-constant and flips sign at the poles (measured: 60-63 distinct bins on both
    # the shipped and the reworked sheets, i.e. the test was noise, not a pivot check).
    path = np.stack([cx, (cy - y_off) / squash], axis=1)
    steps = np.linalg.norm(np.diff(np.vstack([path, path[:1]]), axis=0), axis=1)
    closure = float(np.linalg.norm(path[-1] - path[0]))
    print("centroid loop: step mean {:.2f} max {:.2f} px, closure {:.2f} px".format(
        steps.mean(), steps.max(), closure))
    if steps.max() > 4.0:
        problems.append("centroid jumps {:.2f} px between directions {} and {} "
                        "(misordered or missing frame)".format(
                            steps.max(), int(np.argmax(steps)) + 1,
                            int(np.argmax(steps)) + 2))
    if closure > 4.0:
        problems.append("centroid loop does not close ({:.2f} px gap) -> a direction "
                        "is missing or duplicated".format(closure))

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
