"""Build the before/after evidence images for the turret art pass.

    python build_art_evidence.py --out docs/verification/art \
        --before-sheets <dir with melta-turret-head-*.png from the old art> \
        --after-sheets  <dir with the new sheets> \
        --before-shots  <dir with look-*.png from run_look.py --tree <old tree>> \
        --after-shots   <dir with look-*.png from run_look.py>

Defaults point at the mod's own graphics/ (after) and at the verification output of
the pass recorded in ../art-rework-verification.md. Missing shot directories are
skipped rather than fatal, so the sheet images can be built without a game run.

Outputs
  sheet-before-after-4dir.png    four bearings, old row over new row, native size
  sheet-before-after-muzzle.png  2x muzzle crops for the same bearings
  ingame-before-after-close.png  before/after in-game close-up, side by side
  ingame-before-after-pairs.png  before/after in-game 1x, melta beside vanilla gun
  ingame-vs-vanilla-row.png      after shot of the vanilla row at 1.6x
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw, ImageFont

FRAME = 256
DIRECTIONS = [0, 16, 32, 48]


def font(size=16):
    for name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def frame_of(sheet, direction):
    """One 256x256 frame out of an 8-row head sheet."""
    im = Image.open(sheet).convert("RGBA")
    row = direction // 8
    return im.crop((0, row * FRAME, FRAME, (row + 1) * FRAME))


def sheet_for(sheets_dir, direction):
    return os.path.join(sheets_dir, "melta-turret-head-%d.png" % (direction // 8 + 1))


def label(draw, xy, text, size=16):
    draw.text(xy, text, fill=(245, 238, 224, 255), font=font(size))


def on_bg(im, bg=(38, 42, 46, 255)):
    out = Image.new("RGBA", im.size, bg)
    out.alpha_composite(im)
    return out


def four_dir(sheets, tag):
    pad, top = 10, 26
    canvas = Image.new("RGBA", (pad + len(DIRECTIONS) * (FRAME + pad), top + FRAME + pad),
                       (38, 42, 46, 255))
    d = ImageDraw.Draw(canvas)
    label(d, (pad, 5), tag)
    for i, direction in enumerate(DIRECTIONS):
        f = frame_of(sheet_for(sheets, direction), direction)
        canvas.alpha_composite(on_bg(f), (pad + i * (FRAME + pad), top))
        label(d, (pad + i * (FRAME + pad) + 6, top + 4),
              "%d deg" % (direction * 360 // 64), 14)
    return canvas


def muzzle_crops(sheets, tag, zoom=2):
    pad, top = 8, 24
    tiles = []
    for direction in DIRECTIONS:
        f = frame_of(sheet_for(sheets, direction), direction)
        bbox = f.getbbox()
        top_y = bbox[1]                       # the muzzle is the topmost opaque pixel
        cx = (bbox[0] + bbox[2]) // 2
        box = (max(0, cx - 70), max(0, top_y - 6),
               min(FRAME, cx + 70), min(FRAME, top_y + 134))
        crop = f.crop(box)
        tiles.append(on_bg(crop.resize((crop.width * zoom, crop.height * zoom),
                                       Image.NEAREST)))
    tile_w = max(t.width for t in tiles)
    tile_h = max(t.height for t in tiles)
    canvas = Image.new("RGBA", (pad + len(tiles) * (tile_w + pad), top + tile_h + pad),
                       (38, 42, 46, 255))
    d = ImageDraw.Draw(canvas)
    label(d, (pad, 4), tag)
    for i, t in enumerate(tiles):
        canvas.alpha_composite(t, (pad + i * (tile_w + pad), top))
    return canvas


def stack(*images):
    w = max(i.width for i in images)
    h = sum(i.height for i in images) + 6 * (len(images) - 1)
    out = Image.new("RGBA", (w, h), (24, 26, 28, 255))
    y = 0
    for im in images:
        out.alpha_composite(im, (0, y))
        y += im.height + 6
    return out


def side_by_side(left, right, tag_l="before", tag_r="after"):
    top = 24
    h = max(left.height, right.height)
    out = Image.new("RGBA", (left.width + right.width + 8, top + h), (24, 26, 28, 255))
    d = ImageDraw.Draw(out)
    label(d, (6, 4), tag_l)
    label(d, (left.width + 14, 4), tag_r)
    out.alpha_composite(left, (0, top))
    out.alpha_composite(right, (left.width + 8, top))
    return out


def shot(run_dir, name):
    if not run_dir:
        return None
    path = os.path.join(run_dir, name)
    return Image.open(path).convert("RGBA") if os.path.exists(path) else None


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", "..", ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(here, "..", "art"))
    ap.add_argument("--before-sheets", required=True)
    ap.add_argument("--after-sheets", required=True)
    ap.add_argument("--before-shots")
    ap.add_argument("--after-shots")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    stack(four_dir(args.before_sheets, "before (HEAD art)"),
          four_dir(args.after_sheets, "after (reworked art)")).save(
        os.path.join(out, "sheet-before-after-4dir.png"))

    stack(muzzle_crops(args.before_sheets, "before: muzzle"),
          muzzle_crops(args.after_sheets, "after: muzzle, radial vents")).save(
        os.path.join(out, "sheet-before-after-muzzle.png"))

    left = shot(args.before_shots, "look-melta-close.png")
    right = shot(args.after_shots, "look-melta-close.png")
    if left and right:
        side_by_side(left, right).save(
            os.path.join(out, "ingame-before-after-close.png"))

    left = shot(args.before_shots, "look-pairs.png")
    right = shot(args.after_shots, "look-pairs.png")
    if left and right:
        stack(left, right).save(os.path.join(out, "ingame-before-after-pairs.png"))

    row = shot(args.after_shots, "look-vanilla.png")
    if row:
        row.save(os.path.join(out, "ingame-vs-vanilla-row.png"))

    made = sorted(glob.glob(os.path.join(out, "*.png")))
    print("%d images in %s (repo %s)" % (len(made), out, repo))
    for path in made:
        print("  ", os.path.basename(path), Image.open(path).size)


main()
