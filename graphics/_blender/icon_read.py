"""Measure how a turret ICON reads at the GUI's 32 px size, next to vanilla's.

The melta icon's problem at small size is shape budget, not camera: the hull
dominates the silhouette and the weapon is a minority of it, so at 32 px the whole
thing collapses into one warm oval. "Reads as a turret" is therefore turned into
numbers this script can print for any icon in the game's own folder:

  form        how the silhouette is proportioned -- coverage, bbox, elongation,
              how far the outline reaches past the body (reach, protrusion share)
  weapon      whether anything projects and is thinner than the body: the neck
              ratio (width of the outer third along the long axis over the width of
              the middle third) and how much of the mask lives in that outer third
  masses      how many big shapes the eye has to work with at 32 px: connected
              components of a 3-level luma quantisation that are each at least 5 %
              of the silhouette, plus the share of near-white (the focal element
              vanilla puts on the muzzle)
  contrast    mean luma of the projecting part against the body, i.e. whether the
              barrel separates from the hull at all

Reads the packed file exactly as the GUI does: the base square (64 px) and each
mip packed to the right (32/16/8).

Run:  python icon_read.py <icon.png> [<icon.png> ...]
      python icon_read.py --vanilla [--ours <icon.png>]     # the reference family
"""

import os
import sys

import numpy as np
from PIL import Image

BASE = "E:/SteamLibrary/steamapps/common/Factorio/data/base/graphics/icons"
SPACE_AGE = "E:/SteamLibrary/steamapps/common/Factorio/data/space-age/graphics/icons"

VANILLA = ["gun-turret", "flamethrower-turret", "laser-turret", "artillery-turret"]
VANILLA_SA = ["rocket-turret"]


def mip_level(im, level):
    """The authored mip inside a vanilla-shaped icon file (base + halvings right)."""
    return im.crop((64, 0, 64 + level, level)).convert("RGBA")


def luma(rgb):
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def components(mask):
    """Connected components (4-connectivity) of a boolean mask -> list of area."""
    h, w = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not seen[y, x]:
                stack = [(y, x)]
                seen[y, x] = True
                n = 0
                while stack:
                    cy, cx = stack.pop()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                            seen[ny, nx] = True
                            stack.append((ny, nx))
                out.append(n)
    return sorted(out, reverse=True)


def measure(im, size=32):
    cell = mip_level(im, size) if size != 64 else im.crop((0, 0, 64, 64)).convert("RGBA")
    a = np.asarray(cell, dtype=np.float32) / 255.0
    rgb = np.where(a[:, :, 3:4] > 0.004, a[:, :, :3] / np.maximum(a[:, :, 3:4], 1e-4), 0.0)
    alpha = a[:, :, 3]
    mask = alpha > 0.12
    m = dict(size=size, coverage=float(mask.mean() * 100))
    if mask.sum() < 8:
        return m

    ys, xs = np.nonzero(mask)
    h, w = ys.max() - ys.min() + 1, xs.max() - xs.min() + 1
    m["bbox"] = (int(w), int(h))
    m["aspect"] = w / float(h)

    # principal axes, weighted by the mask
    cy, cx = ys.mean(), xs.mean()
    dy, dx = ys - cy, xs - cx
    cov = np.cov(np.vstack([dx, dy]))
    ev = np.sort(np.linalg.eigvalsh(cov))[::-1]
    m["elongation"] = float(np.sqrt(max(ev[0], 1e-6) / max(ev[1], 1e-6)))

    r = np.sqrt(dx ** 2 + dy ** 2)
    med = np.median(r)
    m["reach"] = float(r.max() / max(med, 1e-6))
    m["protrusion_pct"] = float((r > 1.30 * med).sum() / float(mask.sum()) * 100)

    # width profile along the long axis: a turret has a thin projecting barrel, a pod does not
    vec = np.array([dx, dy]).T
    # long axis from the covariance eigenvector
    _, evecs = np.linalg.eigh(cov)
    axis = evecs[:, -1]
    proj = vec @ axis
    lo, hi = proj.min(), proj.max()
    span = max(hi - lo, 1e-6)
    u = (proj - lo) / span                      # 0 = one end, 1 = the other
    widths = []
    for a0, a1 in ((0.0, 0.34), (0.34, 0.67), (0.67, 1.0)):
        band = (u >= a0) & (u < a1)
        widths.append(float(band.sum()))
    # normalise each third by its own length so it is a mean thickness
    thick = [widths[0] / 0.34, widths[1] / 0.33, widths[2] / 0.33]
    core = max(thick[1], 1e-6)
    outer = min(thick[0] / core, thick[2] / core)
    m["neck"] = float(outer)                    # 1.0 = same thickness as the body
    m["outer_share_pct"] = float((widths[0] + widths[2]) / max(sum(widths), 1e-9) * 100)

    L = luma(rgb) * 255.0
    m["mean"] = float(L[mask].mean())
    m["white_pct"] = float((L[mask] >= 200).mean() * 100)
    m["near_black_pct"] = float((L[mask] < 20).mean() * 100)
    body = np.zeros_like(mask)
    limb = np.zeros_like(mask)
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
    body = mask & (rr <= 1.0 * med)
    limb = mask & (rr > 1.30 * med)
    if limb.sum() >= 4 and body.sum() >= 4:
        m["limb_contrast"] = float(abs(L[limb].mean() - L[body].mean()))
        m["limb_dark"] = float(L[body].mean() - L[limb].mean())   # >0 = barrel darker than hull
    else:
        m["limb_contrast"] = 0.0
        m["limb_dark"] = 0.0

    # big shapes: 3-level luma quantisation, components >= 5 % of the silhouette
    q1, q2 = np.percentile(L[mask], [33.3, 66.7])
    masses = 0
    for lo_b, hi_b in ((-1, q1), (q1, q2), (q2, 1000)):
        bandm = mask & (L >= lo_b) & (L < hi_b)
        for area in components(bandm):
            if area >= 0.05 * mask.sum():
                masses += 1
    m["masses"] = masses
    return m


def show(name, m):
    if "bbox" not in m:
        print("%-24s %2dpx  empty" % (name, m["size"]))
        return
    print("%-24s %2dpx  cov %4.1f%%  bbox %dx%d (%.2f)  elong %4.2f  reach %4.2f  "
          "protr %4.1f%%  neck %4.2f  outer %4.1f%%  masses %d  luma %3.0f  white %4.1f%%  "
          "darklimb %+5.1f"
          % (name, m["size"], m["coverage"], m["bbox"][0], m["bbox"][1], m["aspect"],
             m["elongation"], m["reach"], m["protrusion_pct"], m["neck"],
             m["outer_share_pct"], m["masses"], m["mean"], m["white_pct"],
             m["limb_dark"]))


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--vanilla":
        ours = None
        if "--ours" in args:
            ours = args[args.index("--ours") + 1]
        rows = []
        for name in VANILLA:
            rows.append((name, Image.open(os.path.join(BASE, name + ".png"))))
        for name in VANILLA_SA:
            rows.append((name, Image.open(os.path.join(SPACE_AGE, name + ".png"))))
        if ours:
            rows.append(("melta (ours)", Image.open(ours)))
        for size in (64, 32):
            print("\n--- %d px ---" % size)
            for name, im in rows:
                show(name, measure(im, size))
        return
    for path in args:
        im = Image.open(path)
        for size in (64, 32):
            show(os.path.basename(path), measure(im, size))


if __name__ == "__main__":
    main()
