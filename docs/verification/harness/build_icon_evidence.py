"""Build the icon-change evidence images: before/after at GUI size, the real crafting
menu row, and the placed turret.

    python docs/verification/harness/build_icon_evidence.py \
        --old-icon <rev>:graphics/icons/melta-turret.png or a file \
        --gui-shot <50-row.png from run_gui.py on the NEW tree> \
        --placed  <look-melta.png from run_look.py> \
        --out docs/verification/art

Outputs (docs/verification/art/)
  icon-before-after-32.png   old vs new melta icon at 64 px and at the 32 px mip the
                             GUI draws, each beside the vanilla turret icons -- the
                             comparison the card asks for, straight from the icon files
  icon-gui-crafting-after.png  the real crafting menu, row at the melta: native crop and
                             4x nearest, plus a wide shot of the whole panel
  icon-gui-placed.png        the turret placed in world from the same commit
"""
import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GAME = "E:/SteamLibrary/steamapps/common/Factorio/data"
BG = (81, 81, 81)
TEXT = (226, 226, 226)
SUB = (190, 190, 150)


def font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def load_old(spec):
    """`<rev>:<path>` out of git, or a plain file path."""
    if ":" in spec and not os.path.exists(spec):
        rev, path = spec.split(":", 1)
        data = subprocess.check_output(["git", "-C", REPO, "show", "%s:%s" % (rev, path)])
        tmp = os.path.join(os.environ.get("TMPDIR", "."), "old-icon.png")
        with open(tmp, "wb") as fh:
            fh.write(data)
        return Image.open(tmp).convert("RGBA")
    return Image.open(spec).convert("RGBA")


def mip(im, size):
    if size == 64:
        return im.crop((0, 0, 64, 64))
    x, s = 64, 64
    while s > size:
        x += s // 2
        s //= 2
    return im.crop((x - s, 0, x, s))


def cell(im, size, zoom, bg=BG):
    small = im.resize((size, size), Image.LANCZOS)
    big = small.resize((size * zoom, size * zoom), Image.NEAREST)
    canvas = Image.new("RGB", (size * zoom, size * zoom), bg)
    canvas.paste(big, (0, 0), big)
    return canvas


def before_after(old, new, out):
    """Old vs new, 64 px and 32 px, in the vanilla lineup."""
    cols = [("gun", Image.open(os.path.join(GAME, "base/graphics/icons/gun-turret.png")).convert("RGBA")),
            ("flamer", Image.open(os.path.join(GAME, "base/graphics/icons/flamethrower-turret.png")).convert("RGBA")),
            ("before", old, True),
            ("after", new, True)]
    z64, z32, pad = 5, 10, 14
    cw = 64 * z64
    W = pad + (cw + pad) * len(cols)
    H = pad + 40 + cw + 26 + cw + pad
    sheet = Image.new("RGB", (W, H), (28, 29, 31))
    draw = ImageDraw.Draw(sheet)
    f16, f12 = font(16), font(12)
    y = pad
    for label, size, zoom in (("64 px art, x5", 64, z64),
                              ("32 px GUI mip -- what the crafting menu draws, x10", 32, z32)):
        draw.text((pad, y), label, fill=TEXT, font=f16)
        y += 22
        x = pad
        for col in cols:
            name, im = col[0], col[1]
            ours = len(col) > 2
            sheet.paste(cell(mip(im, size), size, zoom), (x, y))
            draw.text((x + 2, y + cw - 14 if size == 64 else y + cw - 14), name,
                      fill=TEXT if ours else SUB, font=f12)
            x += cw + pad
        y += cw + 4
    sheet.save(out)
    print("wrote", out, sheet.size)


def gui_after(shot, out, box=(1128, 96, 1632, 320)):
    """The crafting panel around the turret row: native crop, 4x of the row, wide shot."""
    im = Image.open(shot).convert("RGB")
    w, h = im.size
    if w == 3840:                      # whole-desktop grab: the game is the right monitor
        im = im.crop((1920, 0, 3840, 1080))
    panel = im.crop(box)
    row = im.crop((1170, 140, 1570, 200))
    zoom = row.resize((row.width * 4, row.height * 4), Image.NEAREST)
    pad = 14
    W = max(panel.width + pad * 2, zoom.width + pad * 2)
    H = pad + 22 + panel.height + 18 + 22 + zoom.height + pad
    sheet = Image.new("RGB", (W, H), (28, 29, 31))
    draw = ImageDraw.Draw(sheet)
    f16 = font(16)
    draw.text((pad, pad), "crafting menu, searched \"turret\" (native pixels)", fill=TEXT, font=f16)
    sheet.paste(panel, (pad, pad + 22))
    y = pad + 22 + panel.height + 18
    draw.text((pad, y), "the row at 4x nearest -- melta is the 5th icon", fill=TEXT, font=f16)
    sheet.paste(zoom, (pad, y + 22))
    sheet.save(out)
    print("wrote", out, sheet.size)


def placed(shot, out):
    """In-world shot: JPEG, the same convention as docs/verification/in-game."""
    im = Image.open(shot).convert("RGB")
    im.save(out, quality=92, optimize=True)
    print("wrote", out, im.size)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-icon", required=True, help="<rev>:graphics/icons/melta-turret.png")
    ap.add_argument("--gui-shot", help="50-row.png from run_gui.py")
    ap.add_argument("--placed", help="look-melta.png from run_look.py")
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "verification", "art"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    old = load_old(a.old_icon)
    new = Image.open(os.path.join(REPO, "graphics", "icons", "melta-turret.png")).convert("RGBA")
    before_after(old, new, os.path.join(a.out, "icon-before-after-32.png"))
    if a.gui_shot:
        gui_after(a.gui_shot, os.path.join(a.out, "icon-gui-crafting-after.png"))
    if a.placed:
        placed(a.placed, os.path.join(a.out, "icon-gui-placed.jpg"))


main()
