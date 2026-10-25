"""Side-by-side size/appearance comparison: vanilla gun turret, vanilla laser
turret, the old drawn melta head, the new rendered melta turret.

Everything is drawn at the same pixels-per-tile as the game (art px / 2), centred
on each turret's own content, on one ground tile, so the relative size is honest.
Review artifact only -- nothing here is loaded by the mod.
"""
import os
import sys
import zipfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

F = "E:/SteamLibrary/steamapps/common/Factorio/data"
OLD_ZIP = "H:/Factorio Mods/lilys-melta/lilys-melta_0.3.0.zip"
NEW_TEX = sys.argv[1] if len(sys.argv) > 1 else "sheets"
OUT = sys.argv[2] if len(sys.argv) > 2 else "compare.png"
ZOOM = 3


def paste_center(canvas, img, cx, cy):
    canvas.alpha_composite(img, (int(cx - img.width / 2), int(cy - img.height / 2)))


def frame_from_sheet(path, fw, fh, index, line_length):
    im = Image.open(path).convert("RGBA")
    col = index % line_length
    row = index // line_length
    return im.crop((col * fw, row * fh, (col + 1) * fw, (row + 1) * fh))


def down(img, scale=0.5):
    a = np.asarray(img, dtype=np.float32) / 255.0
    rgb, alpha = a[:, :, :3], a[:, :, 3:4]
    pm = np.concatenate([rgb * alpha, alpha], axis=2)
    im = Image.fromarray((pm * 255).astype(np.uint8), mode="RGBA")
    w, h = int(img.width * scale), int(img.height * scale)
    im = im.resize((w, h), Image.LANCZOS)
    b = np.asarray(im, dtype=np.float32) / 255.0
    al = b[:, :, 3:4]
    out = np.where(al > 0.004, b[:, :, :3] / np.maximum(al, 1e-4), 0.0)
    return Image.fromarray((np.clip(np.concatenate([out, al], axis=2), 0, 1) * 255).astype(np.uint8),
                          mode="RGBA")


def content_center(img):
    a = np.asarray(img.convert("RGBA"))[:, :, 3]
    ys, xs = np.nonzero(a > 8)
    if len(xs) == 0:
        return img.width // 2, img.height // 2
    return int((xs.min() + xs.max()) / 2), int((ys.min() + ys.max()) / 2)


def build_cell(base_img, head_img):
    """Entity-centred composite: base centre and head centre both on the pivot."""
    cell = Image.new("RGBA", (260, 220), (0, 0, 0, 0))
    paste_center(cell, base_img, 130, 118)
    paste_center(cell, head_img, 130, 118)
    return cell


def ground(w, h):
    img = Image.new("RGBA", (w, h), (62, 78, 46, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, h, 32):
        for x in range(0, w, 32):
            v = 5 if ((x // 32 + y // 32) % 2) else 0
            d.rectangle([x, y, x + 31, y + 31], fill=(62 + v, 78 + v, 46 + v, 255))
    return img


def label(cell, text):
    out = Image.new("RGBA", (cell.width, cell.height + 16), (0, 0, 0, 0))
    out.alpha_composite(cell, (0, 16))
    d = ImageDraw.Draw(out)
    d.text((4, 2), text, fill=(235, 235, 230, 255))
    return out


cells = []

# --- vanilla gun turret (2x2), north-facing shooting frame
gun_base = down(Image.open(F + "/base/graphics/entity/gun-turret/gun-turret-base.png").convert("RGBA"))
gun_head = down(frame_from_sheet(F + "/base/graphics/entity/gun-turret/gun-turret-shooting-1.png",
                                 132, 104, 0, 2))
cells.append(label(build_cell(gun_base, gun_head), "vanilla gun turret"))

# --- vanilla laser turret (2x2)
laser_base = down(Image.open(F + "/base/graphics/entity/laser-turret/laser-turret-base.png").convert("RGBA"))
laser_head = down(frame_from_sheet(F + "/base/graphics/entity/laser-turret/laser-turret-shooting.png",
                                   126, 120, 0, 8))
cells.append(label(build_cell(laser_base, laser_head), "vanilla laser turret"))

# --- old melta (head-1.png row 0, vanilla rocket hull underneath)
old_head = None
try:
    with zipfile.ZipFile(OLD_ZIP) as z:
        with z.open("lilys-melta_0.3.0/graphics/entity/melta-turret/melta-turret-head-1.png") as fh:
            old_head = down(Image.open(fh).convert("RGBA").crop((0, 0, 160, 164)))
    rocket_base = Image.open(F + "/space-age/graphics/entity/rocket-turret/rocket-turret-base.png").convert("RGBA")
    # vanilla draws it with shift by_pixel(0, -20) at scale 0.5 -> lift art by 40 px
    rocket_base = down(rocket_base)
    cell = Image.new("RGBA", (260, 220), (0, 0, 0, 0))
    paste_center(cell, rocket_base, 130, 118 + 20)
    paste_center(cell, old_head, 130, 118 + 9)
    cells.append(label(cell, "old drawn head (0.3.0)"))
except Exception as exc:  # noqa: BLE001
    print("old head unavailable:", exc)

# --- new melta
tex = os.path.join(NEW_TEX, "graphics", "entity", "melta-turret")
new_base = down(Image.open(os.path.join(tex, "melta-turret-base.png")).convert("RGBA"))
for direction, name in ((0, "new (north)"), (16, "new (east)")):
    sheet = os.path.join(tex, "melta-turret-head-{}.png".format(direction // 8 + 1))
    head = down(frame_from_sheet(sheet, 256, 256, direction % 8, 1))
    cells.append(label(build_cell(new_base, head), name))

cell_w, cell_h = cells[0].size
canvas = Image.new("RGBA", (cell_w * len(cells), cell_h), (0, 0, 0, 0))
canvas.alpha_composite(ground(canvas.width, canvas.height))
for i, cell in enumerate(cells):
    canvas.alpha_composite(cell, (i * cell_w, 0))
canvas = canvas.resize((canvas.width * ZOOM // 2, canvas.height * ZOOM // 2), Image.LANCZOS)
canvas.save(OUT)
print("wrote", OUT, canvas.size)
