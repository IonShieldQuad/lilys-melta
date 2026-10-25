"""Assemble the melta turret sprite sheets from the Blender renders.

Steps, in order (each one matters for the in-game result):

 1. downscale the supersampled frames (512 -> 256) in premultiplied alpha, so the
    silhouette edges do not pick up a dark fringe
 2. tone curve: the Cycles 2.79 render comes out compressed (see notes in
    melta_render.py), so a monotone curve maps the render's measured range onto
    the range vanilla turret art actually uses (p10 ~4, p50 ~26, p90 ~120)
 3. bake a soft cast shadow from each frame's own silhouette, offset to the lower
    right, since the vanilla key light comes from the upper left
 4. write 8 sheets of 8 rows (256 x 2048 each, power-of-two both ways), 64
    directions total, and the static hull sprite

Run:  python assemble.py <raw_dir> <out_dir>
"""

import json
import os
import sys

import numpy as np
from PIL import Image

FRAME = 256                    # final art px per frame
ROWS_PER_SHEET = 8             # 8 rows x 256 = 2048 px tall (power of two)
DIRECTIONS = 64

# De-squash of the base layer only. The hull is rendered through a 51 deg pitched
# orthographic camera, so its round footprint is drawn compressed in Y: the base
# sprite measures 3.05 tiles wide but only ~2.1 tiles tall (aspect ~1.45), where
# vanilla turret hulls sit near 1.2. Harmless while the hull was only an icon
# back-drop, but the pipe ports sit on the hull's north/south walls, and a shallow
# hull leaves the north pipe ~0.42 tiles of bare ground (vanilla's
# assembling-machine-2, same collision box, leaves 0.22).
#
# Stretching the base layer's Y about the frame centre is exactly an un-squash: the
# pivot stays dead centre (shift {0, 0}, head stays concentric) and no geometry has to
# move. 1.26 takes the hull silhouette measured in a +-0.5 tile band around the pipe
# axis from 1.09 to 1.38 tiles north and 1.03 to 1.28 south, i.e. the north ground gap
# from 0.41 to 0.12 tiles (vanilla assembling-machine-2 leaves 0.24) and the south from
# 0.16 to an overlap. Measured, not guessed: graphics/_blender/pipe_sockets.py prints
# the table and fails if a gap goes back over 0.22.
BASE_DESQUASH_Y = 1.26

# tone curve control points, render-luma -> final luma (both 0..255 sRGB).
# Fitted by quantile matching (graphics/_blender was developed alongside a scratch
# fit_curve.py): the Cycles 2.79 render comes out compressed around 35..70 because the
# lights in this build barely shape the model, so the curve is steep in the middle --
# it maps the render's own quantiles onto the quantiles measured from the vanilla
# gun/laser turret base sprites (p10 ~1, p25 ~8, p50 ~22, p75 ~56, p90 ~113).
CURVE = [(0, 0), (25, 3), (35, 8), (43, 18), (51, 34), (60, 70), (69, 125),
         (84, 195), (105, 240), (140, 252), (255, 255)]

# A touch of warmth: vanilla's turrets are grey-brown, and the render leans blue-grey.
# Applied after the curve, on sRGB values.
TINT = (1.12, 0.99, 0.90)


def tone_lut():
    xs = np.array([p[0] for p in CURVE], dtype=np.float32)
    ys = np.array([p[1] for p in CURVE], dtype=np.float32)
    grid = np.arange(256, dtype=np.float32)
    return np.interp(grid, xs, ys)


LUT = tone_lut()


def load_frame(path, desquash_y=1.0):
    """Load, premultiply, optionally de-squash in Y, downscale to FRAME, unpremultiply.

    The de-squash runs at the raw (supersampled) resolution and about the frame
    centre, so the stretch costs one resample instead of two and the pivot stays at
    the centre of the frame.
    """
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im, dtype=np.float32) / 255.0
    rgb, alpha = a[:, :, :3], a[:, :, 3:4]
    pm = rgb * alpha
    if desquash_y != 1.0:
        h, w = alpha.shape[:2]
        tall = int(round(h * desquash_y))
        # keep the extra rows even so the crop is symmetric: an odd count would shift
        # the sprite half a raw pixel off the pivot
        if (tall - h) % 2:
            tall += 1
        stretched = Image.fromarray(
            (np.concatenate([pm, alpha], axis=2) * 255.0).astype(np.uint8),
            mode="RGBA").resize((w, tall), Image.LANCZOS)
        top = (tall - h) // 2
        b = np.asarray(stretched.crop((0, top, w, top + h)), dtype=np.float32) / 255.0
        rgb2, alpha2 = b[:, :, :3], b[:, :, 3:4]
        # renormalise: the stretch is not area preserving, alpha is the weight
        pm = np.where(alpha2 > 0.004, rgb2, 0.0)
        alpha = alpha2
    pm_img = Image.fromarray((np.concatenate([pm, alpha], axis=2) * 255.0).astype(np.uint8),
                             mode="RGBA").resize((FRAME, FRAME), Image.LANCZOS)
    b = np.asarray(pm_img, dtype=np.float32) / 255.0
    rgb2, alpha2 = b[:, :, :3], b[:, :, 3:4]
    rgb2 = np.where(alpha2 > 0.004, rgb2 / np.maximum(alpha2, 1e-4), 0.0)
    rgb2 = np.clip(rgb2, 0.0, 1.0)
    return rgb2, np.clip(alpha2[:, :, 0], 0.0, 1.0)


def apply_curve(rgb):
    """Tone curve applied on sRGB luma, hue preserved."""
    srgb = np.clip(rgb, 0.0, 1.0) * 255.0
    lum = 0.2126 * srgb[:, :, 0] + 0.7152 * srgb[:, :, 1] + 0.0722 * srgb[:, :, 2]
    new_lum = LUT[np.clip(lum, 0, 255).astype(np.uint8)].astype(np.float32)
    scale = np.where(lum > 2.0, new_lum / np.maximum(lum, 1e-3), 0.0)
    scale = np.clip(scale, 0.0, 8.0)
    out = np.clip(srgb * scale[:, :, None], 0.0, 255.0)
    out = np.clip(out * np.array(TINT, dtype=np.float32)[None, None, :], 0.0, 255.0)
    return out


def shadow_layer(alpha, offset=(5, 3), blur=2.2, strength=0.55):
    """Cast shadow from the frame's own silhouette: shift down-right, blur, darken."""
    a = Image.fromarray((np.clip(alpha, 0, 1) * 255).astype(np.uint8), mode="L")
    shifted = Image.new("L", a.size, 0)
    shifted.paste(a, offset)
    shifted = shifted.filter(ImageFilter.GaussianBlur(blur))
    arr = np.asarray(shifted, dtype=np.float32) / 255.0 * strength
    rgb = np.zeros(arr.shape + (3,), dtype=np.float32)
    rgb[:, :] = (10.0 / 255.0, 9.0 / 255.0, 9.0 / 255.0)   # 0..1 like the rest
    return rgb, arr


from PIL import ImageFilter  # noqa: E402  (imported late so the helper reads top-down)


def compose(rgb, alpha, with_shadow=True):
    """Sprite OVER shadow (the shadow is the backdrop): the sprite must stay untouched
    where it is opaque, and the shadow only shows where the sprite is not."""
    if not with_shadow:
        return rgb, alpha
    s_rgb, s_a = shadow_layer(alpha)
    a_out = alpha + s_a * (1.0 - alpha)
    safe = np.maximum(a_out, 1e-4)
    rgb_out = (rgb * alpha[:, :, None]
               + s_rgb * (s_a * (1.0 - alpha))[:, :, None]) / safe[:, :, None]
    return rgb_out, a_out


def to_image(rgb, alpha):
    arr = np.concatenate([np.clip(rgb, 0, 1) * 255.0,
                          np.clip(alpha, 0, 1)[:, :, None] * 255.0],
                         axis=2).astype(np.uint8)
    return Image.fromarray(arr, mode="RGBA")


def parse_args(argv):
    """Positional: raw_dir out_dir.  --only all|heads|base (default all)."""
    only, positional, i = "all", [], 0
    while i < len(argv):
        a = argv[i]
        if a == "--only":
            only = argv[i + 1] if i + 1 < len(argv) else "all"
            i += 2
            continue
        if a.startswith("--only="):
            only = a.split("=", 1)[1]
        else:
            positional.append(a)
        i += 1
    if only not in ("all", "heads", "base"):
        raise SystemExit("--only must be all, heads or base (got {!r})".format(only))
    return positional, only


def main():
    positional, only = parse_args(sys.argv[1:])
    raw = positional[0] if positional else "raw"
    out = positional[1] if len(positional) > 1 else "sheets"
    tex = os.path.join(out, "graphics", "entity", "melta-turret")
    os.makedirs(tex, exist_ok=True)

    names = []
    if only in ("all", "heads"):
        frames = []
        for d in range(DIRECTIONS):
            path = os.path.join(raw, "gun", "gun-{:03d}.png".format(d))
            rgb, alpha = load_frame(path)
            rgb = apply_curve(rgb) / 255.0
            rgb, alpha = compose(rgb, alpha)
            frames.append(to_image(rgb, alpha))

        # head sheets: ROWS_PER_SHEET rows of one frame, line_length = 1
        sheet_h = FRAME * ROWS_PER_SHEET
        idx = 0
        for part in range(DIRECTIONS // ROWS_PER_SHEET):
            sheet = Image.new("RGBA", (FRAME, sheet_h), (0, 0, 0, 0))
            for row in range(ROWS_PER_SHEET):
                sheet.paste(frames[idx], (0, row * FRAME))
                idx += 1
            name = "melta-turret-head-{}.png".format(part + 1)
            sheet.save(os.path.join(tex, name), optimize=True)
            names.append(name)
        assert idx == DIRECTIONS, idx

    # static hull sprite (de-squashed in Y: see BASE_DESQUASH_Y)
    if only in ("all", "base"):
        rgb, alpha = load_frame(os.path.join(raw, "base", "hull.png"),
                                desquash_y=BASE_DESQUASH_Y)
        rgb = apply_curve(rgb) / 255.0
        rgb, alpha = compose(rgb, alpha, with_shadow=True)
        to_image(rgb, alpha).save(os.path.join(tex, "melta-turret-base.png"),
                                  optimize=True)

    meta = {
        "frame": FRAME,
        "rows_per_sheet": ROWS_PER_SHEET,
        "sheet_size": [FRAME, FRAME * ROWS_PER_SHEET],
        "sheets": names,
        "directions": DIRECTIONS,
        "line_length": 1,
        "scale": 0.5,
        "shift": [0, 0],
        "only": only,
        "base_desquash_y": BASE_DESQUASH_Y,
    }
    with open(os.path.join(out, "sheets.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
