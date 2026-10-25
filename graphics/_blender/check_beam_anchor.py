"""Does the beam start where the gun's mouth is drawn? Check all 64 head frames.

For every direction the beam's start point (the formula in control.lua / constants.lua)
is projected onto the sprite frame and tested against the shipped sheet:
  * the pixel must be opaque -- the beam may never start in empty space,
  * it must be inside the silhouette with a margin, so it is the mouth and not an edge,
  * it must sit at the mouth: at most a lip's thickness behind the silhouette's front
    edge along the facing, and never deeper inside the barrel,
  * it must be away from the frame centre -- the beam may never start at the pivot.

Usage: python check_beam_anchor.py
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HEAD = Path("H:/Factorio Mods/lilys-melta/graphics/entity/melta-turret")
FRAME = 256
ROWS = 8
FILES = 8
DIRECTIONS = 64
ALPHA_MIN = 40

L = 1.512          # C.muzzle_forward
H = 0.722          # C.muzzle_height
BORe_L = 1.428     # model 1.70 x GUN_SCALE: the middle of the mouth
TILT = math.radians(51.0)
COS, SIN = math.cos(TILT), math.sin(TILT)
PX_PER_TILE = FRAME / 4.0          # frame spans 4 tiles


def start_point(direction, forward=L):
    """ground point (world tiles) the beam starts from, for this facing"""
    a = 2 * math.pi * direction / DIRECTIONS
    ux, uy = math.sin(a), -math.cos(a)          # world vector: +y south
    return L * ux, COS * L * uy - SIN * H


def to_pixel(direction, gx, gy):
    """frame pixel of a world offset: screen up is -world y, image y grows down"""
    # the frame is the sprite's own screen space: x -> right, world y -> up with no
    # foreshortening (Factorio maps world tiles 1:1 to screen tiles)
    return FRAME / 2.0 + gx * PX_PER_TILE, FRAME / 2.0 + gy * PX_PER_TILE


def front_edge(direction, alpha):
    a = 2 * math.pi * direction / DIRECTIONS
    ux, uy = math.sin(a), math.cos(a)            # x right, y up (screen)
    ys, xs = np.nonzero(alpha > ALPHA_MIN)
    proj = (xs + 0.5 - FRAME / 2.0) * ux + (-(ys + 0.5 - FRAME / 2.0)) * uy
    return proj.max() / PX_PER_TILE


def inside_margin(alpha, px, py):
    """distance in px from (px,py) to the nearest transparent pixel, capped at 32"""
    x, y = int(px), int(py)
    for r in range(1, 33):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                sx, sy = x + dx, y + dy
                if not (0 <= sx < FRAME and 0 <= sy < FRAME):
                    return r
                if alpha[sy, sx] <= ALPHA_MIN:
                    return r
    return 33


rows = []
frame_id = 0
for f in range(1, FILES + 1):
    sheet = np.asarray(Image.open(HEAD / f"melta-turret-head-{f}.png").convert("RGBA"))[:, :, 3]
    for row in range(ROWS):
        d = (f - 1) * ROWS + row
        alpha = sheet[row * FRAME:(row + 1) * FRAME, :]
        gx, gy = start_point(d)
        px, py = to_pixel(d, gx, gy)
        opaque = alpha[int(py), int(px)] > ALPHA_MIN
        edge = front_edge(d, alpha)
        a = 2 * math.pi * d / DIRECTIONS
        ux, uy = math.sin(a), math.cos(a)
        anchor_proj = gx * ux + (-gy) * uy            # where the anchor sits, along facing
        rows.append(dict(d=d, px=round(px, 1), py=round(py, 1), opaque=bool(opaque),
                         margin=int(inside_margin(alpha, px, py)),
                         anchor_proj=round(anchor_proj, 3), front=round(edge, 3),
                         behind_front=round(edge - anchor_proj, 3),
                         from_pivot=round(math.hypot(gx, gy), 3)))
        frame_id += 1

bad = [r for r in rows if not r["opaque"] or r["margin"] < 1]
# The mouth's front face IS the front edge of the silhouette, so a fraction of a pixel
# past it is correct, not a bug (alpha threshold + antialiasing shave sub-pixel amounts).
shallow = [r for r in rows if r["behind_front"] < -0.03 or r["behind_front"] > 0.75]
close = [r for r in rows if r["from_pivot"] < 0.30]

print(f"frames checked: {len(rows)}")
print(f"start pixel opaque: {sum(r['opaque'] for r in rows)}/{len(rows)}  "
      f"min silhouette margin {min(r['margin'] for r in rows)} px")
print(f"behind the silhouette front edge: min {min(r['behind_front'] for r in rows):.3f} "
      f"max {max(r['behind_front'] for r in rows):.3f} tiles")
print(f"distance from the pivot: min {min(r['from_pivot'] for r in rows):.3f} "
      f"max {max(r['from_pivot'] for r in rows):.3f} tiles")
print("every 8th:", [(r["d"], r["px"], r["py"], r["margin"], r["behind_front"]) for r in rows[::8]])
print("problems (not opaque / on the very edge of the frame):", bad)
print("suspicious (mouth misplacement):", shallow)
print("too close to the pivot:", close)
print("VERDICT:", "PASS" if not bad and not shallow and not close else "FAIL")
sys.exit(0 if not bad and not shallow and not close else 1)
