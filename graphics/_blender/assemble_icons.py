"""Turn the Blender icon renders into the icon files the prototypes load.

Two things make this different from the sprite-sheet assembler next to it.

1. Vanilla 2.1 icon files are not plain squares: the PNG holds the full-size image
   plus its mip levels packed to the right (base, then half, quarter, eighth...).
   Measured on the shipped art: `gun-turret.png` is 120x64 = 64 + 32 + 16 + 8, and
   `technology/gun-turret.png` is 480x256 = 256 + 128 + 64 + 32. Downsampling the
   base and comparing against the packed regions gives an alpha correlation of
   1.000, so that is the layout; matching it means the GUI picks an authored 32 px
   level instead of a runtime filter, and the file has exactly the shape the base
   game's own turret icons have.

2. Icons are NOT sprites. The sheets are tone-matched to the vanilla turret base
   sprites (mean ~50, p50 ~26, half the pixels near black -- in-world art is
   deliberately dark so it sits in terrain). Icons are authored much brighter and
   more saturated so they survive being drawn at 32 px in a GUI: the vanilla turret
   icons measure mean 85-97, p50 66-81, p90 169-207, only ~10% of pixels below 20.
   Running the sprite curve here gave mean 48 and 25% near-black, which is exactly
   what "reads as a murky disc at 32 px" looks like. The icon therefore gets its own
   curve, fitted the same way (quantile matching) against vanilla's own rusted
   fluid turret: flamethrower-turret.png.

Pipeline per image: fit the silhouette into the box (centred, aspect preserved,
61/64 of the frame so nothing clips), map the tone onto the icon targets, lift
chroma, bake the same upper-left cast shadow the sheets use, filter down, and pack
the mip chain to the right.

Run:  python assemble_icons.py [<raw_dir> [<direction>]] [--candidate out.png]
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))

GAME = "E:/SteamLibrary/steamapps/common/Factorio/data"

ICON_BOX = 64                 # item / entity icon base size  (icon_size = 64)
TECH_BOX = 256                # technology icon base size     (icon_size = 256)
THUMB_BOX = 512               # mod thumbnail (portal + mod list)

# Fit: the largest silhouette dimension lands on FIT px inside a BOX cell, the
# rest is margin the baked shadow may use. Vanilla turret icons run 58-64 px of
# content in a 64 px cell, so this is deliberately generous.
FIT = 61
# The silhouette is placed centred with a small downward bias: an emplacement
# reads as standing ON something, and a couple of pixels of headroom above the
# gun look right where the same room below would look like the turret floats.
CENTER_BIAS = 2

# Cast shadow, in the coordinates of the cell it is baked into. The key light is
# upper-left (see melta_render.setup_lights), so the shadow falls lower-right.
ICON_SS = 4                   # the 64 px icon is composed at 4x, then filtered down

# Icon tone targets, measured off the vanilla turret icons. The reference set:
# flamethrower-turret p10 21 / p50 66 / p90 192, gun-turret 19/80/175,
# laser-turret 17/80/206 -- the whole family sits around mean 85-95 with only ~10%
# of pixels below 20. Drift from this shows up as mud (too dark) or a washed-out
# silhouette (too bright); a first pass fitted to the flamer alone still read as
# "dark brown disc" at 32 px, so the fit sits on the brighter half of the family.
ICON_TARGET_Q = (0.10, 0.25, 0.50, 0.75, 0.90)
ICON_TARGET_LUMA = (20.0, 44.0, 76.0, 140.0, 205.0)
# Our render is desaturated steel; vanilla icons keep chroma in rust and hazard
# paint. Lift chroma around the luma axis rather than tinting the hue.
ICON_CHROMA = 1.60
ICON_TINT = (1.10, 1.00, 0.92)   # a touch warmer, same idea as assemble.TINT


# --------------------------------------------------------------- utilities ---
def load_pm(path):
    """RGBA PNG -> float array (h, w, 4) with premultiplied colour."""
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.float32) / 255.0
    a[:, :, :3] *= a[:, :, 3:4]
    return a


def resize_pm(rgba, size, steps=2):
    """Premultiplied, antialiased resize of a float RGBA array to (w, h)."""
    h, w = rgba.shape[:2]
    tw, th = size
    cur = rgba
    for i in range(steps):
        # shrink in powers first when the factor is huge, so LANCZOS never has to
        # throw away 16 pixels at once (that aliases)
        fac = (w / float(tw)) ** (1.0 / (steps - i))
        nw = max(tw, int(round(w / fac)))
        nh = max(th, int(round(h / fac)))
        if (nw, nh) == (w, h):
            continue
        im = Image.fromarray((np.clip(cur, 0, 1) * 255).astype(np.uint8), "RGBA")
        im = im.resize((nw, nh), Image.LANCZOS)
        cur = np.asarray(im, dtype=np.float32) / 255.0
        w, h = nw, nh
    if (w, h) != (tw, th):
        im = Image.fromarray((np.clip(cur, 0, 1) * 255).astype(np.uint8), "RGBA")
        built = im.resize((tw, th), Image.LANCZOS)
    else:
        built = Image.fromarray((np.clip(cur, 0, 1) * 255).astype(np.uint8), "RGBA")
    if tw < 8:
        built = built.filter(ImageFilter.SMOOTH)
    return built


def unpremultiply(im):
    a = np.asarray(im, dtype=np.float32) / 255.0
    rgb, alpha = a[:, :, :3], a[:, :, 3:4]
    rgb = np.where(alpha > 0.004, rgb / np.maximum(alpha, 1e-4), 0.0)
    return np.clip(rgb, 0, 1), np.clip(alpha[:, :, 0], 0, 1)


def fit_cell(src_rgba, box, fit=FIT, bias=CENTER_BIAS):
    """Crop the render to its silhouette, scale it into `box`, centre it.

    Returns (rgb 0..1, alpha 0..1) at box x box, or the same at a supersampled
    size when `box` is the supersampled one -- callers pass what they want.
    """
    alpha = src_rgba[:, :, 3]
    ys, xs = np.nonzero(alpha > 0.02)
    if len(xs) == 0:
        raise SystemExit("render is empty: nothing above 2%% alpha")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    crop = src_rgba[y0:y1, x0:x1]
    ch, cw = crop.shape[:2]
    scale = fit / float(max(cw, ch))
    tw, th = max(1, int(round(cw * scale))), max(1, int(round(ch * scale)))
    small = resize_pm(crop, (tw, th))
    cell = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    cell.paste(small, ((box - tw) // 2, max(0, (box - th) // 2 + bias)), small)
    return unpremultiply(cell), (x0, y0, cw, ch, tw, th)


def premult(rgb, alpha):
    return np.dstack([rgb * alpha[:, :, None], alpha])


def luma(rgb):
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def icon_tone(rgb, alpha, q_ref=None):
    """Map the render's luma quantiles onto vanilla's icon quantiles.

    `q_ref` is the pair whose quantiles define the mapping -- usually the image at
    its final size, so the fit is measured where the icon will actually be looked
    at, even though the tone is applied at the supersampled size.
    """
    ref_rgb, ref_a = (rgb, alpha) if q_ref is None else q_ref
    mask = ref_a > 0.05
    src_l = luma(ref_rgb)[mask] * 255.0
    if src_l.size < 64:
        return rgb
    src_q = np.percentile(src_l, [q * 100.0 for q in ICON_TARGET_Q])
    xs = np.concatenate([[0.0], src_q, [255.0]])
    ys = np.concatenate([[0.0], np.array(ICON_TARGET_LUMA, dtype=np.float32), [255.0]])
    keep = np.concatenate([[True], np.diff(xs) > 0.5])   # a flat render can repeat a knot
    xs, ys = xs[keep], ys[keep]
    lut = np.interp(np.arange(256, dtype=np.float32), xs, ys)

    l = np.clip(luma(rgb) * 255.0, 0, 255)
    new_l = lut[l.astype(np.uint8)]
    scale = np.where(l > 2.0, new_l / np.maximum(l, 1e-3), 0.0)
    out = rgb * np.clip(scale, 0.0, 8.0)[:, :, None]

    # chroma lift around luma, then warmth
    l2 = luma(out)[:, :, None]
    out = l2 + (out - l2) * ICON_CHROMA
    out = out * np.array(ICON_TINT, dtype=np.float32)[None, None, :]
    return np.clip(out, 0.0, 1.0)


def shadow_over(rgb, alpha, box, ss, offset, blur, strength=0.50):
    """Bake the cast shadow the sheets use, at the FINAL resolution.

    The mask is built at `ss` x final size and filtered down, so a 1.5 px offset and
    a 0.75 px blur are still smooth instead of quantising to one hard pixel. Working
    at the final size matters: the shadow must not be dragged through the tone curve
    (it would come out as a grey halo).
    """
    b = box * ss
    a = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), "L")
    a = a.resize((b, b), Image.BICUBIC)
    shifted = Image.new("L", (b, b), 0)
    shifted.paste(a, (int(round(offset[0] * ss)), int(round(offset[1] * ss))))
    s = shifted.filter(ImageFilter.GaussianBlur(blur * ss)).resize((box, box), Image.LANCZOS)
    s_a = np.asarray(s, dtype=np.float32) / 255.0 * strength
    s_rgb = np.empty((box, box, 3), dtype=np.float32)
    s_rgb[:, :] = (10.0 / 255.0, 9.0 / 255.0, 9.0 / 255.0)
    a_out = alpha + s_a * (1.0 - alpha)
    rgb_out = (rgb * alpha[:, :, None]
               + s_rgb * (s_a * (1.0 - alpha))[:, :, None]) / np.maximum(a_out, 1e-4)[:, :, None]
    return np.clip(rgb_out, 0, 1), np.clip(a_out, 0, 1)


def to_img(rgb, alpha):
    return Image.fromarray(np.concatenate(
        [np.clip(rgb, 0, 1) * 255.0, np.clip(alpha, 0, 1)[:, :, None] * 255.0],
        axis=2).astype(np.uint8), "RGBA")


def mip_chain(base, levels):
    """Halve the composed image, premultiplied, to author the mip levels.

    Each lower level gets a light blur after the halving. The GUI shows the 32 px
    level for item icons, and a straight LANCZOS halving of a render this detailed
    turns the plate seams and rivets into speckle there; ~0.5 px of smoothing at the
    level's own scale keeps the masses and drops the noise, which is what a hand-made
    mip looks like.
    """
    out = [base]
    cur = base
    for _ in range(levels):
        w, h = cur.size
        a = np.asarray(cur, dtype=np.float32) / 255.0
        a[:, :, :3] *= a[:, :, 3:4]
        nxt = resize_pm(a, (w // 2, h // 2), steps=1).convert("RGBA")
        nxt = nxt.filter(ImageFilter.GaussianBlur(0.5))
        out.append(nxt)
        cur = nxt
    return out


def pack_mips(base, levels):
    """Vanilla layout: base + each mip pasted to the right, height = base height."""
    chain = mip_chain(base, levels)
    width = sum(m.width * (1 if i == 0 else 1) for i, m in enumerate(chain))
    sheet = Image.new("RGBA", (width, base.height), (0, 0, 0, 0))
    x = 0
    for m in chain:
        sheet.paste(m, (x, 0), m)
        x += m.width
    return sheet, chain


# ------------------------------------------------- icon-only shape budget ---
# The icon is judged at 32 px, where only two or three big masses survive. Vanilla's
# turret icons keep their detail budget by having almost none: the flamethrower icon is
# a hull blob, a plate, and a white-hot nozzle. Our render carries plate seams, rivets
# and vent slats that at 32 px are sub-pixel and turn the whole icon into one warm oval
# (measured: 15.5 % of the mask beyond 1.3x the median radius, against 20-24 % for the
# vanilla turret icons, and the projecting barrel reads only 7 luma brighter than the
# body, against 45-140 for vanilla).
#
# Two passes, both applied at the FINAL icon size, after the tone fit, so they cannot
# disturb the palette band:
#   * suppress detail whose local contrast is below DETAIL_MIN luma: it is texture, not
#     shape. Big edges (silhouette, mantlet, muzzle ring) survive untouched. Measured
#     sweep (icon_read.py at 32 px): 6 is a marginal win, 10 is the largest win that
#     still reads as a sharp machine, 14+ smears the muzzle and banding.
#   * optionally drive the hottest FOCAL_PCT of the mask to a near-white warm highlight.
#     OFF by default (0): a tone-level highlight desaturates the muzzle, while the same
#     job done in the render -- render_icons.py --icon-emit, which lifts the actual
#     emissive material -- keeps the hot metal's hue and its 3D form. Kept as a knob
#     because it is the cheap way to fake the focal element on an older render.
DETAIL_MIN = 10.0         # luma units below which local variation is flattened
DETAIL_SIGMA = 1.0        # px at 64 for the low-pass the detail is measured against
FOCAL_PCT = 0.0           # % of the mask pushed into the white-hot shoulder
FOCAL_LUMA = 246.0        # the value that cluster lands on
FOCAL_WARM = (1.00, 0.965, 0.905)

# The icon's shape budget, as a knob on the render (render_icons.py --icon-gun-scale).
# Measured sweep on this model: 1.0 leaves the barrel at 16 % protrusion / 1.61 reach
# (vanilla 20-24 % / 1.7-2.5), 1.5 reaches 1.89 / 18.9 %, 1.75 reaches 2.04 / 23.5 % --
# inside the vanilla band -- and 2.0 starts to stretch the machine. This constant is the
# value render_icons.py was run with; assemble_icons.py records it in icons.json so a
# mismatch between render and metadata is visible instead of silent.
ICON_GUN_SCALE = 1.75

# Parameters of the two shape passes, read at CALL time (assemble_icons' study driver
# varies them; the defaults are what ships).
SHAPE_CFG = {"detail": DETAIL_MIN, "sigma": DETAIL_SIGMA,
             "focal": FOCAL_PCT, "target": FOCAL_LUMA, "warm": FOCAL_WARM}


def suppress_detail(rgb, alpha, threshold=None, sigma=None):
    """Flatten texture below `threshold` luma, keep every real edge.

    Splits luma into a low-pass and a detail layer and soft-thresholds the detail, so
    plate seams and rivet highlights (2-3 luma units at 64 px) merge into their plate
    while the mantlet edge, the muzzle ring and the silhouette stay crisp.
    """
    threshold = SHAPE_CFG["detail"] if threshold is None else threshold
    sigma = SHAPE_CFG["sigma"] if sigma is None else sigma
    L = luma(rgb) * 255.0
    base = np.asarray(Image.fromarray(np.clip(L, 0, 255).astype(np.uint8), "L")
                      .filter(ImageFilter.GaussianBlur(sigma)), dtype=np.float32)
    d = L - base
    mag = np.maximum(np.abs(d) - threshold, 0.0)
    d2 = np.sign(d) * mag
    L2 = np.clip(base + d2, 1.0, 255.0)
    scale = L2 / np.maximum(L, 1e-3)
    return np.clip(rgb * scale[:, :, None], 0.0, 1.0)


def hot_focal(rgb, alpha, pct=None, target=None, warm=None):
    """Push the brightest `pct` % of the silhouette toward a white-hot highlight."""
    pct = SHAPE_CFG["focal"] if pct is None else pct
    target = SHAPE_CFG["target"] if target is None else target
    warm = SHAPE_CFG["warm"] if warm is None else warm
    mask = alpha > 0.15
    if mask.sum() < 32 or pct <= 0.0:
        return rgb
    L = luma(rgb) * 255.0
    cut = float(np.percentile(L[mask], 100.0 - pct))
    # soft shoulder: 0 at the cut, 1 at the top of the render's range
    top = float(L[mask].max()) if L[mask].max() > cut + 1e-3 else cut + 1.0
    w = np.clip((L - cut) / max(top - cut, 1e-3), 0.0, 1.0) ** 0.7
    w = np.where(mask, w, 0.0)
    tint = np.array(warm, dtype=np.float32)[None, None, :] * (target / 255.0)
    out = rgb * (1.0 - w[:, :, None]) + tint * w[:, :, None]
    return np.clip(out, 0.0, 1.0)


# --------------------------------------------------------------- the parts ---
def compose(src, box, ss=1, shadow_offset=(5.0, 3.0), shadow_blur=2.2, shape=False):
    """Fit -> tone -> filter down -> exact tone pass -> shape pass -> shadow, at `box`.

    The tone is applied twice on purpose. The first pass happens on the big render,
    where it has room to work; the second pass is measured on the finished `box`
    image, which is the only place the quantiles that matter exist (sRGB averaging
    during the downscale pulls the top end in, so a single hi-res pass lands ~60
    levels short of the target p90).

    `shape` is the icon-only simplification (see suppress_detail / hot_focal): it runs
    at `box`, after the fit, so the tone band is already fixed when it starts.
    """
    ss_box = box * ss
    (rgb_hi, alpha_hi), info = fit_cell(
        src, ss_box,
        fit=int(round(FIT * ss_box / float(ICON_BOX))),
        bias=int(round(CENTER_BIAS * ss_box / float(ICON_BOX))))
    rgb_hi = icon_tone(rgb_hi, alpha_hi)
    base = resize_pm(premult(rgb_hi, alpha_hi), (box, box), steps=2)
    rgb, alpha = unpremultiply(base)
    rgb = icon_tone(rgb, alpha)
    if shape:
        rgb = suppress_detail(rgb, alpha)
        rgb = hot_focal(rgb, alpha)
    rgb, alpha = shadow_over(rgb, alpha, box, ss, shadow_offset, shadow_blur)
    return to_img(rgb, alpha), info


def build_icon(src, out_path, box=ICON_BOX, ss=ICON_SS, levels=3, shape=False):
    """Item/entity icon: fitted, toned, shadowed, mips packed -> one PNG."""
    base, info = compose(src, box, ss=ss, shadow_offset=(1.5, 1.0), shadow_blur=0.75,
                         shape=shape)
    sheet, chain = pack_mips(base, levels)
    sheet.save(out_path, optimize=True)
    return sheet, base, info


def build_tech(src, out_path, box=TECH_BOX, levels=3):
    """Technology icon at vanilla size (256 px base + packed mips)."""
    base, info = compose(src, box, ss=2, shadow_offset=(3.0, 2.0), shadow_blur=1.5)
    sheet, chain = pack_mips(base, levels)
    sheet.save(out_path, optimize=True)
    return sheet, base, info


def build_thumbnail(src, out_path, box=THUMB_BOX):
    """Mod thumbnail: the turret on a dark plate, warm haze behind, real shadow."""
    a = src.copy()
    a[:, :, :3] = np.where(a[:, :, 3:4] > 0.004,
                           a[:, :, :3] / np.maximum(a[:, :, 3:4], 1e-4), 0.0)
    rgb, alpha = np.clip(a[:, :, :3], 0, 1), np.clip(a[:, :, 3], 0, 1)
    art = to_img(rgb, alpha)

    ys, xs = np.nonzero(alpha > 0.02)
    crop = art.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    cw, ch = crop.size
    scale = int(round(box * 0.84)) / float(max(cw, ch))
    crop = crop.resize((max(1, int(cw * scale)), max(1, int(ch * scale))), Image.LANCZOS)
    cw, ch = crop.size
    # tone at the size the thumbnail is actually looked at, then place it
    y = box - ch - int(box * 0.10)
    cell = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    cell.paste(crop, ((box - cw) // 2, y), crop)
    rgb, alpha = unpremultiply(cell)
    rgb = icon_tone(rgb, alpha)     # the thumbnail wants the icon palette, not the sprite one
    body = to_img(rgb, alpha)

    # background: dark plate + warm haze behind the machine, plus a floor shade.
    # The plate is deliberately a little lighter than "black": the model's hoses and
    # recesses are near-black, and on a black field the silhouette merges into it.
    yy = np.linspace(0.0, 1.0, box, dtype=np.float32)[:, None]
    top = np.array([0.150, 0.156, 0.166], dtype=np.float32)
    bot = np.array([0.068, 0.070, 0.075], dtype=np.float32)
    bg = top[None, None, :] * (1 - yy[:, :, None]) + bot[None, None, :] * yy[:, :, None]
    bg = np.repeat(bg, box, axis=1)
    gy, gx = np.mgrid[0:box, 0:box].astype(np.float32)
    r = np.sqrt(((gx - box * 0.5) / (box * 0.46)) ** 2 + ((gy - box * 0.44) / (box * 0.38)) ** 2)
    haze = np.clip(1.0 - r, 0.0, 1.0) ** 1.8
    bg = bg + np.array([0.115, 0.080, 0.042], dtype=np.float32)[None, None, :] * haze[:, :, None]
    plate = Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8), "RGB").convert("RGBA")

    # soft contact shadow under the turret, thrown down-right
    sh = Image.new("L", (box, box), 0)
    tmp = Image.new("L", crop.size, 0)
    tmp.paste(crop.split()[3], (int(cw * 0.06) + 12, int(ch * 0.06) + 10))
    blurred = tmp.filter(ImageFilter.GaussianBlur(box * 0.022))
    sh.paste(blurred, ((box - cw) // 2, y))
    shade = Image.new("RGBA", (box, box), (0, 0, 0, 0))
    shade.putalpha(sh.point(lambda v: int(v * 0.62)))
    plate.alpha_composite(shade)

    plate.alpha_composite(body, (0, 0))
    plate.convert("RGB").save(out_path, optimize=True)

    # 144 px copy, the size the portal asks for, kept next to the big one
    small = plate.convert("RGB").resize((144, 144), Image.LANCZOS)
    small.save(out_path.replace(".png", "-144.png"), optimize=True)
    return plate.convert("RGB")


# -------------------------------------------------------------- reporting ---
def stats(img, label):
    a = np.asarray(img.convert("RGBA"), dtype=np.float32)
    al = a[:, :, 3]
    ys, xs = np.nonzero(al > 8)
    box = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    lum = 0.2126 * a[:, :, 0] + 0.7152 * a[:, :, 1] + 0.0722 * a[:, :, 2]
    m = al > 8
    q = np.percentile(lum[m], [10, 50, 90]) if m.any() else [0, 0, 0]
    print("  %-28s %-9s bbox %-18s content %dx%d  cov %4.1f%%  luma p10/p50/p90 %.0f/%.0f/%.0f"
          % (label, "%dx%d" % img.size, str(box),
             box[2] - box[0] + 1, box[3] - box[1] + 1, (al > 8).mean() * 100, q[0], q[1], q[2]))


def main():
    raw = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "iconraw")
    direction = int(sys.argv[2]) if len(sys.argv) > 2 else 44
    candidate = None
    if "--candidate" in sys.argv:
        candidate = sys.argv[sys.argv.index("--candidate") + 1]
    out_root = "H:/Factorio Mods/lilys-melta"
    if "--out" in sys.argv:
        out_root = sys.argv[sys.argv.index("--out") + 1]
    # the icon-only simplification and the icon shape budget are DEFAULTS, so the bare
    # documented command  `python assemble_icons.py graphics/_blender/iconraw 40 --out X`
    # still reproduces the shipped files byte for byte. Override for studies only.
    shape = "--no-shape" not in sys.argv
    gun_scale = ICON_GUN_SCALE
    if "--gun-scale" in sys.argv:
        gun_scale = float(sys.argv[sys.argv.index("--gun-scale") + 1])

    src_path = os.path.join(raw, "icon-{:03d}.png".format(direction))
    print("render:", src_path)
    src = load_pm(src_path)
    # The 64 px item icon is drawn with the icon shape budget (a bigger gun). The
    # technology icon and the portal thumbnail are NOT: at 256/512 px the barrel reads
    # perfectly well, and those two are the mod's honest portrait of the machine, so
    # they keep the shipping proportions from the same render rig (the `-ship` file).
    ship_path = os.path.join(raw, "icon-{:03d}-ship.png".format(direction))
    if not os.path.exists(ship_path):
        ship_path = src_path
    print("ship render:", ship_path)
    ship = load_pm(ship_path)

    icons_dir = os.path.join(out_root, "graphics", "icons")
    os.makedirs(icons_dir, exist_ok=True)

    if candidate:
        sheet, base, info = build_icon(src, candidate, shape=shape)
        print("candidate ->", candidate, "shape" if shape else "raw",
              "gun_scale", gun_scale)
        stats(base, "candidate %d" % direction)
        return

    icon_path = os.path.join(icons_dir, "melta-turret.png")
    sheet, base, info = build_icon(src, icon_path, shape=shape)
    print("wrote", icon_path, "(shape pass %s)" % ("on" if shape else "off"))

    tech_path = os.path.join(icons_dir, "melta-turret-technology.png")
    tech_sheet, tech_base, tech_info = build_tech(ship, tech_path)
    print("wrote", tech_path)

    thumb_path = os.path.join(out_root, "thumbnail.png")
    build_thumbnail(ship, thumb_path)
    print("wrote", thumb_path)

    print("\nframing (render px -> icon px):")
    print("  source silhouette %dx%d at (%d,%d) -> %dx%d in a %d cell"
          % (info[2], info[3], info[0], info[1], info[4], info[5], ICON_BOX))
    print("\nvanilla reference:")
    for f, label in [("base/graphics/icons/gun-turret.png", "gun-turret icon"),
                     ("space-age/graphics/icons/rocket-turret.png", "rocket-turret icon")]:
        p = os.path.join(GAME, f)
        if os.path.exists(p):
            im = Image.open(p).convert("RGBA")
            stats(im.crop((0, 0, 64, 64)), label)
    print("\nours:")
    stats(base, "melta icon base")
    stats(tech_base, "melta tech base")

    meta = {
        "direction": direction,
        "icon_px": ICON_BOX,
        "icon_file_px": list(sheet.size),
        "tech_px": TECH_BOX,
        "tech_file_px": list(tech_sheet.size),
        "thumbnail_px": THUMB_BOX,
        "fit_px": FIT,
        "icon_gun_scale": gun_scale,
        "icon_source": "icon-%03d.png (render_icons.py --icon-gun-scale %.2f%s)"
                       % (direction, gun_scale, " --icon-emit"),
        "tech_thumbnail_source": "icon-%03d-ship.png (shipping proportions, same rig)"
                                 % direction,
        "shape_pass": {"detail_min_luma": SHAPE_CFG["detail"],
                       "detail_sigma_px": SHAPE_CFG["sigma"],
                       "focal_pct": SHAPE_CFG["focal"],
                       "applies_to": "item icon only"},
        "icon_tone": {"reference": "vanilla flamethrower-turret.png icon",
                      "target_p10_90": list(ICON_TARGET_LUMA),
                      "chroma": ICON_CHROMA},
        "mips": {"icon": [64, 32, 16, 8], "technology": [256, 128, 64, 32]},
        "shadow": {"icon_offset_px": [1.5, 1.0], "icon_blur_px": 0.75,
                   "tech_offset_px": [3.0, 2.0], "tech_blur_px": 1.5},
    }
    with open(os.path.join(HERE, "icons.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print("\n" + json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
