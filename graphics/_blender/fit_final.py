"""Refit assemble.py's tone curve for the reworked model, iteratively.

    python fit_final.py <raw_dir> [--iters 3]

assemble.py applies one global monotone curve (render luma -> final luma) whose
control points were quantile-matched to vanilla turret art for the OLD model. The
reworked model is both brighter (mid-value gunmetal instead of dark grey) and lit by
emissive geometry instead of the (inert) lamps, so the old curve sends p75 to 209 and
p90 to 234 -- near-white highlights, which is exactly the "pale plate" read.

This measures the assembled frames against the vanilla reference and prints a curve
that puts them back in vanilla's band. Iterative: each pass re-measures the previous
pass's output, so LUT clipping cannot leave the fit short.
"""
import os
import sys

import numpy as np
from PIL import Image

BDIR = "H:/Factorio Mods/lilys-melta/graphics/_blender"
DATA = "E:/SteamLibrary/steamapps/common/Factorio/data/base/graphics/entity"
sys.path.insert(0, BDIR)
import assemble as A  # noqa: E402

PROBS = [0.02, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98]


def vanilla(name, sheet, cols, rows, fw, fh, shifts=((0, 0),)):
    im = Image.open(os.path.join(DATA, name, sheet)).convert("RGBA")
    frames = []
    for i in range(cols * rows):
        c, r = i % cols, i // rows
        frames.append(np.asarray(im.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh))))
    px = np.concatenate([f.reshape(-1, 4) for f in frames]).astype(np.float32)
    rgb = px[px[:, 3] > 128][:, :3]
    lum = 0.2126 * rgb[:, 0] + 0.7152 * rgb[:, 1] + 0.0722 * rgb[:, 2]
    r, g, b = rgb.mean(axis=0)
    return ([float(np.percentile(lum, p * 100)) for p in PROBS],
            float(lum.mean()), float(r - b), float((lum < 16).mean() * 100))


def fit(src_q, tgt_q):
    """Monotone piecewise-linear map: render quantiles -> target quantiles."""
    pts = [(0.0, 0.0)]
    for s, t in zip(src_q, tgt_q):
        pts.append((float(max(s, 0.5)), float(t)))
    pts.append((255.0, 255.0))
    clean = [pts[0]]
    for x, y in pts[1:]:
        if x > clean[-1][0] - 0.01 and y >= clean[-1][1]:
            if clean and abs(x - clean[-1][0]) < 1e-6:
                clean[-1] = (x, max(y, clean[-1][1]))
            else:
                clean.append((x, y))
    return [(round(x, 1), round(y, 1)) for x, y in clean]


def main():
    raw = sys.argv[1]
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 3

    tgt_q, tgt_mean, tgt_warm, tgt_dark = vanilla(
        "gun-turret", "gun-turret-shooting-1.png", 2, 32, 132, 130)
    print("vanilla gun head: q %s mean %.1f warm %+.1f dark %.1f%%"
          % (" ".join("%5.1f" % v for v in tgt_q), tgt_mean, tgt_warm, tgt_dark))

    frames = []
    for d in range(A.DIRECTIONS):
        rgb, alpha = A.load_frame(os.path.join(raw, "gun", "gun-%03d.png" % d))
        frames.append((rgb, alpha))
    brgb, balpha = A.load_frame(os.path.join(raw, "base", "hull.png"),
                                desquash_y=A.BASE_DESQUASH_Y)
    base = (brgb, balpha)

    # start from identity, not from the stale curve: fitting on top of the old curve
    # inherits its plateau at 240-252 and flattens the highlights
    CURVE = [(0, 0), (255, 255)]
    for it in range(iters):
        A.CURVE = CURVE
        A.LUT = A.tone_lut()
        px = []
        for rgb, alpha in frames[::4]:
            out = np.clip(A.apply_curve(rgb) / 255.0, 0, 1)
            m = alpha > 0.5
            px.append((out * 255.0)[m])
        P = np.concatenate(px)
        lum = 0.2126 * P[:, 0] + 0.7152 * P[:, 1] + 0.0722 * P[:, 2]
        src_q = [float(np.percentile(lum, p * 100)) for p in PROBS]
        r, g, b = P.mean(axis=0)
        print("pass %d: head q %s mean %.1f warm %+.1f dark %.1f%%"
              % (it, " ".join("%5.1f" % v for v in src_q), lum.mean(), r - b,
                 (lum < 16).mean() * 100))
        if it == iters - 1:
            break
        # compose: feed the residuals into the same quantile match
        new = fit(src_q, tgt_q)

        def compose(a, b):
            lut_a = np.interp(np.arange(256, dtype=np.float32),
                              [p[0] for p in a], [p[1] for p in a])
            lut_b = np.interp(np.arange(256, dtype=np.float32),
                              [p[0] for p in b], [p[1] for p in b])
            both = lut_b[np.clip(lut_a, 0, 255).astype(np.uint8)]
            xs = list(range(256))
            return [(float(x), float(both[x])) for x in xs if x % 8 == 0 or x < 8]

        CURVE = compose(CURVE, new)

    print("CURVE = [")
    for i in range(0, len(CURVE), 4):
        print("    " + ", ".join("(%d, %d)" % (x, y) for x, y in CURVE[i:i + 4]) + ",")
    print("]")

    # report the final base layer too
    A.CURVE = CURVE
    A.LUT = A.tone_lut()
    out = np.clip(A.apply_curve(base[0]) / 255.0, 0, 1)
    m = base[1] > 0.5
    P = (out * 255.0)[m]
    lum = 0.2126 * P[:, 0] + 0.7152 * P[:, 1] + 0.0722 * P[:, 2]
    print("head+base sample after: base mean %.1f p10 %.1f p50 %.1f p90 %.1f"
          % (lum.mean(), np.percentile(lum, 10), np.percentile(lum, 50),
             np.percentile(lum, 90)))


main()
