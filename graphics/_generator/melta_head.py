"""Melta turret head -- procedurally drawn 64-direction sprite sheet.

Sheet geometry is measured from the vanilla rocket turret head that this turret
replaces (data/space-age/graphics/entity/rocket-turret/rocket-turret-shooting*.lua):

    frame            160 x 164 px
    directions        64, one frame each, line_length = 1
    files             3 files with 22 / 22 / 20 rows (lines_per_file = 22)
    layer shift       by_pixel(0, -8.5) at scale 0.5

so the rotation pivot inside a frame sits at (80, 90.5): the engine draws the
frame centre at entity_center + shift, hence the pivot is 8.5 px below centre.

Run:  python melta_head.py            -> writes the sheets next to this file
The same script renders preview.png (review only, never loaded by the game).
"""

import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- geometry ---
FRAME_W, FRAME_H = 160, 164
SS = 4                      # supersample factor, downscaled at the end
DIRECTIONS = 64
LINES_PER_FILE = (22, 22, 20)
PIVOT = (FRAME_W / 2, FRAME_H / 2 + 8.5)

BARREL_LEN = 38.0           # px from pivot to muzzle (1x scale)
BARREL_W_ROOT = 15.0
BARREL_W_TIP = 12.0
HOUSING_R = 15.0
DEPTH_SQUASH = 0.66         # how much the vertical axis is foreshortened

# ------------------------------------------------------------------ palette --
STEEL_DARK = (43, 47, 51)
STEEL_MID = (74, 81, 87)
STEEL_LIGHT = (109, 117, 124)
STEEL_HI = (154, 162, 168)
RUST = (120, 64, 38)
GLOW_DIM = (196, 88, 30)
GLOW_HOT = (255, 138, 48)
CORE = (255, 226, 176)
SHADOW = (12, 10, 9)

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "entity", "melta-turret")
REVIEW_DIR = os.path.dirname(os.path.abspath(__file__))


def rot(direction):
    """Direction 0 = north, increasing clockwise, as Factorio orders turret heads."""
    theta = direction * (2.0 * math.pi / DIRECTIONS)
    return math.sin(theta), -math.cos(theta)


def project(along, across, direction):
    """Map (distance along the barrel, sideways offset) into screen pixels."""
    dx, dy = rot(direction)
    x = PIVOT[0] + dx * along - dy * across
    y = PIVOT[1] + dy * along * DEPTH_SQUASH + dx * across
    # lift the far end a little so north-facing barrels read as pointing away
    y -= along * 0.16 * max(0.0, -dy)
    return x, y


def quad(draw, direction, along0, along1, half_w0, half_w1, color):
    pts = [
        project(along0, -half_w0, direction),
        project(along1, -half_w1, direction),
        project(along1, half_w1, direction),
        project(along0, half_w0, direction),
    ]
    draw.polygon([(p[0] * SS, p[1] * SS) for p in pts], fill=color)


def ring(draw, direction, along, half_w, thickness, color):
    quad(draw, direction, along, along + thickness, half_w, half_w, color)


def blob(draw, direction, along, across, radius_along, radius_across, color):
    """Ellipse in barrel space, so it rotates with the head instead of the screen."""
    pts = []
    for i in range(20):
        a = 2 * math.pi * i / 20
        pts.append(project(along + math.cos(a) * radius_along,
                           across + math.sin(a) * radius_across, direction))
    draw.polygon([(x * SS, y * SS) for x, y in pts], fill=color)


def draw_dome(draw, direction, img):
    """The housing is rotation-symmetric, so it is drawn in screen space: a rigid
    rotated dome must not change shape as the head turns."""
    hx, hy = PIVOT[0], PIVOT[1] - 1.0
    def ellipse(rad_x, rad_y, cx_off, cy_off, color):
        draw.ellipse([((hx + cx_off - rad_x) * SS), ((hy + cy_off - rad_y) * SS),
                      ((hx + cx_off + rad_x) * SS), ((hy + cy_off + rad_y) * SS)], fill=color)
    ellipse(16.0, 13.0, 0.0, 0.0, STEEL_DARK)
    ellipse(13.4, 10.6, 0.0, -0.8, STEEL_MID)
    ellipse(9.6, 7.4, -0.6, -2.0, STEEL_LIGHT)
    ellipse(5.4, 4.0, -1.0, -2.8, STEEL_HI)
    # sight glass + bolt ride on the dome, so they turn with the barrel heading
    dx, dy = rot(direction)
    gx, gy = -dy * 9.0, dx * 7.2 - 2.0
    ellipse(2.6, 2.2, gx, gy, GLOW_DIM)
    ellipse(1.5, 1.2, gx, gy, GLOW_HOT)
    bx, by = dy * 8.5, -dx * 7.0 - 2.0
    ellipse(1.9, 1.6, bx, by, RUST)


def draw_barrel(draw, direction):
    # barrel + muzzle
    quad(draw, direction, 6, BARREL_LEN - 2, BARREL_W_ROOT * 0.50, BARREL_W_TIP * 0.50, STEEL_DARK)
    quad(draw, direction, 6.5, BARREL_LEN - 2.5, BARREL_W_ROOT * 0.40, BARREL_W_TIP * 0.40, STEEL_MID)
    quad(draw, direction, 7.5, BARREL_LEN - 4, BARREL_W_ROOT * 0.15, BARREL_W_TIP * 0.13, STEEL_LIGHT)
    quad(draw, direction, 7.5, BARREL_LEN - 4, BARREL_W_ROOT * 0.05, BARREL_W_TIP * 0.04, STEEL_HI)
    quad(draw, direction, 6, BARREL_LEN - 3, BARREL_W_ROOT * 0.50, BARREL_W_TIP * 0.50, SHADOW + (70,))

    for along, thick, hot in ((13.0, 2.6, False), (21.0, 2.4, False), (28.5, 2.2, False), (34.0, 2.2, True)):
        half = BARREL_W_ROOT * 0.52 - (along / BARREL_LEN) * 0.8
        quad(draw, direction, along, along + thick, half, half, STEEL_DARK)
        quad(draw, direction, along - 0.9, along, half * 0.94, half * 0.94, STEEL_LIGHT)
        if hot:
            quad(draw, direction, along - 1.4, along - 0.9, half * 0.80, half * 0.80, GLOW_DIM)

    # muzzle rim, then bore sunk inside it
    quad(draw, direction, BARREL_LEN - 1.0, BARREL_LEN + 4.5, BARREL_W_TIP * 0.64, BARREL_W_TIP * 0.70, STEEL_DARK)
    quad(draw, direction, BARREL_LEN - 1.0, BARREL_LEN + 4.0, BARREL_W_TIP * 0.58, BARREL_W_TIP * 0.62, STEEL_LIGHT)
    quad(draw, direction, BARREL_LEN + 0.6, BARREL_LEN + 4.6, BARREL_W_TIP * 0.44, BARREL_W_TIP * 0.48, STEEL_DARK)
    quad(draw, direction, BARREL_LEN + 1.6, BARREL_LEN + 4.2, BARREL_W_TIP * 0.28, BARREL_W_TIP * 0.30, GLOW_DIM)
    quad(draw, direction, BARREL_LEN + 2.4, BARREL_LEN + 3.9, BARREL_W_TIP * 0.15, BARREL_W_TIP * 0.17, GLOW_HOT)
    quad(draw, direction, BARREL_LEN + 2.8, BARREL_LEN + 3.6, BARREL_W_TIP * 0.06, BARREL_W_TIP * 0.07, CORE)
    # collar, drawn last so it visibly seats the barrel in the dome
    quad(draw, direction, 4.2, 7.4, BARREL_W_ROOT * 0.66, BARREL_W_ROOT * 0.60, STEEL_DARK)
    quad(draw, direction, 4.4, 6.0, BARREL_W_ROOT * 0.62, BARREL_W_ROOT * 0.58, STEEL_MID)


def draw_head(direction):
    size = (FRAME_W * SS, FRAME_H * SS)
    img = Image.new("RGBA", size, (0, 0, 0, 0))

    # ---- shadow on the deck --------------------------------------------------
    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sx, sy = PIVOT[0] * SS, (PIVOT[1] + 5) * SS
    sd.ellipse([sx - 22 * SS, sy - 8 * SS, sx + 22 * SS, sy + 10 * SS], fill=SHADOW + (110,))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(3 * SS)))
    draw = ImageDraw.Draw(img)

    # ---- mounting plate + contact shadow: without these the head floats -----
    plate = Image.new("RGBA", size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate)
    pcx, pcy = PIVOT[0], PIVOT[1] + 1.0
    pd.ellipse([(pcx - 18) * SS, (pcy - 12) * SS, (pcx + 18) * SS, (pcy + 12) * SS], fill=(30, 33, 36, 255))
    pd.ellipse([(pcx - 16) * SS, (pcy - 10.5) * SS, (pcx + 16) * SS, (pcy + 10.5) * SS], fill=(52, 57, 62, 255))
    img.alpha_composite(plate)
    contact = Image.new("RGBA", size, (0, 0, 0, 0))
    cd = ImageDraw.Draw(contact)
    cd.ellipse([(pcx - 19) * SS, (pcy + 2) * SS, (pcx + 19) * SS, (pcy + 13) * SS], fill=SHADOW + (150,))
    img.alpha_composite(contact.filter(ImageFilter.GaussianBlur(2.5 * SS)))
    draw = ImageDraw.Draw(img)

    # ---- heat sink behind the dome, turning with the barrel ------------------
    for back, lift in ((20.0, 9.0), (24.0, 2.0), (27.5, -5.0)):
        quad(draw, direction, back - 7.5, back, -lift - 3.0, -lift + 3.0, STEEL_DARK)
        quad(draw, direction, back - 7.0, back - 0.5, -lift - 2.4, -lift + 1.2, STEEL_MID)
        quad(draw, direction, back - 6.0, back - 1.5, -lift - 2.0, -lift + 0.2, STEEL_LIGHT)

    # ---- painter's order: away from camera -> dome over barrel; toward -> under
    toward_camera = rot(direction)[1] > 0
    if toward_camera:
        draw_barrel(draw, direction)
        draw_dome(draw, direction, img)
    else:
        draw_dome(draw, direction, img)
        draw_barrel(draw, direction)

    return img.resize((FRAME_W, FRAME_H), Image.LANCZOS)


def write_sheets():
    os.makedirs(OUT_DIR, exist_ok=True)
    frames = [draw_head(d) for d in range(DIRECTIONS)]
    idx = 0
    names = []
    for part, rows in enumerate(LINES_PER_FILE, start=1):
        sheet = Image.new("RGBA", (FRAME_W, FRAME_H * rows), (0, 0, 0, 0))
        for row in range(rows):
            sheet.paste(frames[idx], (0, row * FRAME_H))
            idx += 1
        name = "melta-turret-head-%d.png" % part
        sheet.save(os.path.join(OUT_DIR, name))
        names.append(name)
    assert idx == DIRECTIONS, idx
    return names


BASE_PNG = "E:/SteamLibrary/steamapps/common/Factorio/data/space-age/graphics/entity/rocket-turret/rocket-turret-base.png"


def composite_turret(zoom, direction, charge, seed=0):
    """Turret = rocket hull (untouched) + drawn head + the beam control.lua draws."""
    rng = random.Random(seed + int(charge * 100))
    cell = Image.new("RGBA", (int(FRAME_W * zoom), int(FRAME_H * zoom)), (34, 38, 33, 255))
    cx, cy = cell.width * 0.40, cell.height * 0.55

    if os.path.exists(BASE_PNG):
        base = Image.open(BASE_PNG).convert("RGBA")
        bw, bh = base.width * 0.5 * zoom, base.height * 0.5 * zoom
        base = base.resize((int(bw), int(bh)), Image.LANCZOS)
        cell.alpha_composite(base, (int(cx - 0.5 * zoom - bw / 2), int(cy + 24.5 * zoom - bh / 2)))

    head = draw_head(direction)
    hw, hh = head.width * zoom, head.height * zoom
    head = head.resize((int(hw), int(hh)), Image.LANCZOS)

    # muzzle in frame coordinates: the same transform the sheet uses
    mx, my = project(BARREL_LEN + 4.5, 0, direction)
    mx = cx + (mx - PIVOT[0]) * zoom
    my = cy + (my - PIVOT[1]) * zoom
    dx, dy = rot(direction)

    if charge > 0:
        beam = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        bd = ImageDraw.Draw(beam)
        length = cell.width
        for width, alpha, color in (
            (2 + 11 * charge, 45 + 55 * charge, (255, 92, 22)),
            (1 + 5.5 * charge, 95 + 70 * charge, (255, 152, 62)),
            (1 + 2.2 * charge, 160 + 90 * charge, (255, 240, 214)),
            (max(1, 1 + 0.8 * charge), 200 + 55 * charge, (255, 255, 250)),
        ):
            bd.line([(mx, my), (mx + dx * length, my + dy * length)],
                    fill=color + (int(min(255, alpha)),), width=max(1, int(width * zoom)))
        cell.alpha_composite(beam.filter(ImageFilter.GaussianBlur(2.5 * zoom * charge + 1)))

        # boiling sheath: short jittered dashes off the axis
        sheath = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(sheath)
        px, py = -dy, dx
        for _ in range(7 + int(6 * charge)):
            start_f = rng.random() * 0.85
            run_f = start_f + 0.06 + rng.random() * 0.22
            off = (rng.random() * 2 - 1) * (0.9 + 3.2 * charge) * zoom
            a = int((28 + 90 * charge) * (0.5 + 0.5 * rng.random()))
            w = max(1, int((0.8 + 2.4 * charge) * zoom * (0.5 + 0.5 * rng.random())))
            sd.line([(mx + dx * length * start_f + px * off, my + dy * length * start_f + py * off),
                     (mx + dx * length * run_f + px * off * 0.4, my + dy * length * run_f + py * off * 0.4)],
                    fill=(255, int(110 + 60 * charge), 30, a), width=w)
        cell.alpha_composite(sheath.filter(ImageFilter.GaussianBlur(1.2 * zoom)))

    cell.alpha_composite(head, (int(cx - hw / 2), int(cy - 8.5 * zoom - hh / 2)))

    if charge > 0:
        flash = Image.new("RGBA", cell.size, (0, 0, 0, 0))
        fd = ImageDraw.Draw(flash)
        fr = (2 + 4.5 * charge) * zoom
        fd.ellipse([mx - fr, my - fr, mx + fr, my + fr],
                   fill=(255, int(200 - 60 * (1 - charge)), 150, int(120 + 90 * charge)))
        cell.alpha_composite(flash.filter(ImageFilter.GaussianBlur(1.5 * zoom)))
    return cell


def write_preview():
    """Review artifact: the turret at rest and at three beam intensities."""
    zoom = 3
    cells = [composite_turret(zoom, 16, c, seed=7) for c in (0.0, 0.35, 0.7, 1.0)]
    w, h = cells[0].size
    canvas = Image.new("RGBA", (w * len(cells), h), (34, 38, 33, 255))
    for i, cell in enumerate(cells):
        canvas.alpha_composite(cell, (i * w, 0))
    out = os.path.join(REVIEW_DIR, "preview.png")
    canvas.resize((canvas.width * 2, canvas.height * 2), Image.NEAREST).save(out)
    return out


if __name__ == "__main__":
    print("sheets:", write_sheets())
    print("preview:", write_preview())
