"""Verify the icon files the way the atlas would, without launching the GUI.

No headless Factorio run builds sprites, so an icon that is the wrong size, has a
rect that falls outside its image, or points at a file nobody wrote only fails when
the game is launched with a window. This script closes the three failure classes
that can be checked on disk:

  1. every declared icon file exists, and `icon_size` fits inside the image (the
     "sprite rectangle ... is outside the actual sprite size" family),
  2. the packed mip chain to the right of the base square really is the base, so the
     GUI's 32 px level is authored rather than garbage,
  3. nothing is drawn on the frame border (clipping), and the content fills the icon
     cell (no dead padding) -- the two things the icon is judged on.

Run:  python check_icons.py [<mod_dir>]
Exit code 0 = all checks pass.
"""

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", ".."))

# (relative path, declared icon_size, expected number of packed mips)
ICONS = [
    ("graphics/icons/melta-turret.png", 64, 3),
    ("graphics/icons/melta-turret-technology.png", 256, 3),
]
THUMBNAILS = [("thumbnail.png", 512), ("thumbnail-144.png", 144)]

failures = []


def fail(msg):
    failures.append(msg)
    print("  FAIL " + msg)


def note(msg):
    print("  ok   " + msg)


def premult(im):
    a = np.asarray(im, dtype=np.float32) / 255.0
    a[:, :, :3] *= a[:, :, 3:4]
    return a


def check_icon(rel, size, mips):
    path = os.path.join(MOD, rel)
    print("\n%s (icon_size %d, %d packed mips)" % (rel, size, mips))
    if not os.path.exists(path):
        return fail("missing file")
    im = Image.open(path)
    if im.mode != "RGBA":
        fail("mode is %s, expected RGBA" % im.mode)
    w, h = im.size
    if h != size:
        fail("height %d != icon_size %d" % (h, size))
    if size > min(w, h):
        fail("icon_size %d does not fit the %dx%d image (atlas rect error)" % (size, w, h))
    expected_w = size + sum(size >> (i + 1) for i in range(mips))
    if w != expected_w:
        fail("width %d != %d (base + %d packed mips)" % (w, expected_w, mips))

    base = im.crop((0, 0, size, size))
    a = np.asarray(base)[:, :, 3]
    if (a == 0).all():
        fail("base square is fully transparent")
        return
    # clipping: no opaque pixel on the outer ring
    ring = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    if (ring > 40).any():
        fail("opaque pixels on the frame border (clipping)")
    else:
        note("no opaque pixel on the border")
    # fill: the silhouette should reach most of the cell
    ys, xs = np.nonzero(a > 8)
    cw, ch = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    frac = max(cw, ch) / float(size)
    if frac < 0.85:
        fail("content only %.0f%% of the cell (dead padding)" % (frac * 100))
    else:
        note("content %dx%d = %.0f%% of the cell" % (cw, ch, frac * 100))

    # packed mips: each region must be a downsample of the base
    x = size
    cur = base
    for i in range(mips):
        lvl = size >> (i + 1)
        region = im.crop((x, 0, x + lvl, lvl)).convert("RGBA")
        a_ref = cur.convert("RGBA")
        pm = premult(a_ref)
        built = Image.fromarray((np.clip(pm, 0, 1) * 255).astype(np.uint8), "RGBA")
        built = built.resize((lvl, lvl), Image.LANCZOS)
        mine = np.asarray(built, dtype=np.float32)[:, :, 3]
        theirs = np.asarray(region, dtype=np.float32)[:, :, 3]
        if mine.std() < 1e-6:
            fail("mip %d is flat" % lvl)
        else:
            corr = float(np.corrcoef(mine.ravel(), theirs.ravel())[0, 1])
            if corr < 0.90:
                fail("mip %d at x=%d does not match a downsample of the base (corr %.3f)"
                     % (lvl, x, corr))
            else:
                note("mip %3d px at x=%3d matches the base (corr %.3f)" % (lvl, x, corr))
        cur = region
        x += lvl


def check_thumbnail(rel, size):
    path = os.path.join(MOD, rel)
    print("\n%s (%dx%d)" % (rel, size, size))
    if not os.path.exists(path):
        return fail("missing file")
    im = Image.open(path)
    if im.size != (size, size):
        fail("size %s != %dx%d" % (im.size, size, size))
    else:
        note("size %dx%d" % im.size)
    if im.mode != "RGB":
        note("mode %s (fine for a thumbnail)" % im.mode)
    a = np.asarray(im.convert("RGB"), dtype=np.float32)
    if a.std() < 12:
        fail("thumbnail is nearly flat (std %.1f) -- wrong image?" % a.std())
    else:
        note("contrast present (std %.1f, mean %.1f)" % (a.std(), a.mean()))


def check_prototypes():
    """The prototypes must point at the files this script just verified."""
    print("\nprototype references")
    ent = open(os.path.join(MOD, "prototypes", "entity.lua"), encoding="utf-8").read()
    tech = open(os.path.join(MOD, "prototypes", "technology.lua"), encoding="utf-8").read()
    if "graphics/icons/melta-turret.png" not in ent:
        fail("entity.lua does not reference graphics/icons/melta-turret.png")
    else:
        note("entity.lua -> graphics/icons/melta-turret.png")
    if "graphics/icons/melta-turret-technology.png" not in tech:
        fail("technology.lua does not reference the technology icon")
    else:
        note("technology.lua -> graphics/icons/melta-turret-technology.png")
    for whole in (ent, tech):
        for stale in ("rocket-turret.png", "laser-turret.png"):
            if stale in whole:
                fail("stale vanilla icon reference: " + stale)


for rel, size, mips in ICONS:
    check_icon(rel, size, mips)
for rel, size in THUMBNAILS:
    check_thumbnail(rel, size)
check_prototypes()

print("\n%s" % ("ALL CHECKS PASSED" if not failures else "%d FAILURE(S)" % len(failures)))
sys.exit(1 if failures else 0)
