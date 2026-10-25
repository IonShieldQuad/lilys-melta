"""Check the pipe join: does the port art reach the pipe on every side?

Draws the composite the game draws -- ground, hull (base sprite, priority high),
the neighbouring pipe sprite, then the port sprite (extra-high, so it sits over the
pipe end) -- at 64 px/tile, which is exactly Factorio zoom 2.0, and measures the
seam.

The measurement that matters is not "how far does the hull reach" but **is there any
pixel of bare ground between the machine's port and the pipe's own art**. A gap of
even 0.1 tiles over the pipe's axis reads as a floating pipe end, which is the
reported bug. So:

  * `seam`   = the longest run of ground-only pixels along the pipe axis between the
               hull/port silhouette and the pipe sprite, in tiles. Any value > 0 is
               a visible seam.
  * `reach`  = how far the hull+port silhouette gets along the axis (tiles).
  * `pipe`   = where the pipe's own art starts (its near edge), same measurement.
  * `overlap`= reach - pipe. Negative means the port meets the pipe; we want >= 0.

Both the open port (`pipe_picture`, shown when a pipe is connected) and the capped
one (`pipe_covers`, shown when nothing is) are checked; the cap only has to be
opaque past the pipe's near edge would-be location, i.e. closed.

Run:
  python pipe_join.py --check        # exit 1 if any side has a seam
  python pipe_join.py                # also write docs/pipe-join/*.png for review
"""

import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TILE = 64                                    # px/tile == Factorio zoom 2.0
BAND = TILE // 2                             # +-0.5 tile slot around the pipe axis
PIPE_TILES = 2.0                             # nearest legal pipe distance
MAX_SEAM = 0.0                               # no bare ground is acceptable

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
GAME = os.environ.get("FACTORIO_DATA",
                      "E:/SteamLibrary/steamapps/common/Factorio/data")
TEX = os.path.join(MOD, "graphics", "entity", "melta-turret")
DOCS = os.path.join(MOD, "docs", "pipe-join")

SIDES = ("north", "east", "south", "west")
# which vanilla pipe sprite a pipe in the neighbouring tile is drawn with (it also
# connects onward, away from the turret, so it is a straight run) and the tile offset
PIPE_SPRITE = {
    "north": ("pipe-straight-vertical.png", (0, -1)),
    "south": ("pipe-straight-vertical.png", (0, 1)),
    "east": ("pipe-straight-horizontal.png", (1, 0)),
    "west": ("pipe-straight-horizontal.png", (-1, 0)),
}
# the pipe extent that faces the turret
NEAR = {"north": "south", "south": "north", "east": "west", "west": "east"}


def load(path):
    return Image.open(path).convert("RGBA")


def put(target, sprite, cx, cy):
    target.alpha_composite(sprite, (int(round(cx - sprite.width / 2.0)),
                                    int(round(cy - sprite.height / 2.0))))


def alpha_of(img):
    return np.asarray(img, dtype=np.uint8)[:, :, 3]


def ground(w, h, tile=TILE):
    img = Image.new("RGBA", (w, h), (62, 78, 46, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            v = 4 if ((x // tile + y // tile) % 2) else 0
            d.rectangle([x, y, x + tile - 1, y + tile - 1],
                        fill=(62 + v, 78 + v, 46 + v, 255))
    return img


def font(size=15):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def label(img, text, xy=(6, 4), fill=(240, 236, 200, 255)):
    ImageDraw.Draw(img).text(xy, text, font=font(), fill=fill)


# ---------------------------------------------------------------- composite ---
def scene(side, port_kind="port", with_pipe=True, tiles=7, head=None):
    """Ground, hull, pipe, then the port sprite -- the game's own draw order.

    Returns (layers, flat): `layers` is the machines only, on transparency, which is
    what the measurement needs (ground is opaque, so measuring the flat image would
    find "covered" everywhere); `flat` is that over ground, for the review images.
    """
    n = int(round(tiles * TILE))
    layers = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    cx = cy = n / 2.0
    if head is not None:
        put(layers, head, cx, cy)
    put(layers, load(os.path.join(TEX, "melta-turret-base.png")), cx, cy)
    dx = dy = 0
    if with_pipe:
        sprite_name, (dx, dy) = PIPE_SPRITE[side]
        put(layers, load(os.path.join(GAME, "base", "graphics", "entity", "pipe",
                                      sprite_name)),
            cx + dx * PIPE_TILES * TILE, cy + dy * PIPE_TILES * TILE)
    port_path = os.path.join(TEX, "melta-pipe-{}-{}.png".format(port_kind, side))
    port = load(port_path)
    # drawn at the connection point plus C.pipe_shift, exactly like the prototype
    reach = pipe_reach()
    ox, oy = pipe_shift()[side]
    put(layers, port, cx + (SIGN[side][0] * reach + ox) * TILE,
        cy + (SIGN[side][1] * reach + oy) * TILE)
    flat = ground(n, n)
    flat.alpha_composite(layers)
    return layers, flat


SIGN = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}


def pipe_reach():
    """C.pipe_reach, read out of constants.lua so the docs cannot drift."""
    import re
    with open(os.path.join(MOD, "constants.lua"), "r", encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"^\s*C\.pipe_reach\s*=\s*([0-9.]+)", text, re.M)
    if not m:
        raise SystemExit("could not find C.pipe_reach in constants.lua")
    return float(m.group(1))


def pipe_shift():
    """C.pipe_shift, ditto: the per-side screen offset the prototype draws with."""
    import re
    with open(os.path.join(MOD, "constants.lua"), "r", encoding="utf-8") as fh:
        text = fh.read()
    block = re.search(r"C\.pipe_shift\s*=\s*\{(.*?)\n\}", text, re.S)
    if not block:
        raise SystemExit("could not find C.pipe_shift in constants.lua")
    out = {}
    for side in SIDES:
        m = re.search(r"%s\s*=\s*\{\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\}" % side,
                      block.group(1))
        if not m:
            raise SystemExit("no C.pipe_shift entry for " + side)
        out[side] = (float(m.group(1)), float(m.group(2)))
    return out


# the port's outward offset from its connection point, in tiles, per side
def port_offset(side, shifts=None):
    shifts = shifts or pipe_shift()
    sx, sy = SIGN[side][0], SIGN[side][1]
    x, y = shifts[side]
    return sx * x + sy * y          # how much further out the art is drawn


port_reach = pipe_reach       # the old name, kept for the call sites below


# ------------------------------------------------------------------ measure ---
def axis_profile(alpha, side, band=BAND):
    """Perpendicular band around the pipe axis, reduced to 'is any pixel opaque here',
    indexed by distance from the frame centre in px (signed along the axis)."""
    m = alpha >= 8
    h, w = m.shape
    cy, cx = h // 2, w // 2
    if side in ("north", "south"):
        banded = m[:, cx - band:cx + band]
        prof = banded.any(axis=1)                      # one value per row
        idx = np.arange(h) - cy                        # row offset from centre
    else:
        banded = m[cy - band:cy + band, :]
        prof = banded.any(axis=0)
        idx = np.arange(w) - cx
    return idx, prof


def signed_tiles(idx, prof, side):
    """Map the profile onto 'tiles out along the pipe axis' (positive = outward)."""
    sx, sy = SIGN[side]
    sign = sy if sy else sx
    return idx * sign / float(TILE), prof


def outward_run(img, side):
    """Furthest covered pixel along the pipe axis, in tiles, on an isolated sprite.

    Isolated matters: on the composite the hull would answer for the port, so the
    reach of the port and the near edge of the pipe are measured on their own
    sprites and compared, and the composite is used only for the seam scan.
    """
    dist, prof = signed_tiles(*axis_profile(alpha_of(img), side), side=side)
    keep = dist >= 0
    d, p = dist[keep], prof[keep]
    if not p.any():
        return 0.0
    return float(d[p].max())


def seam_run(img, side, limit=2.6):
    """Longest run of bare ground *between* covered stretches, within `limit` tiles.

    This is the one that decides the bug: a collar one pixel off the pipe end reads
    as a floating pipe, and that is a ground run in the path the pipe takes. Leading
    and trailing ground (outside the machine and past the far side of the pipe) is not
    a seam, so it is trimmed first.
    """
    dist, prof = signed_tiles(*axis_profile(alpha_of(img), side), side=side)
    order = np.argsort(dist)
    d, p = dist[order], prof[order]
    keep = (d >= 0) & (d <= limit)
    d, p = d[keep], p[keep]
    if not p.any():
        return float(limit)
    first = int(np.argmax(p))
    last = len(p) - 1 - int(np.argmax(p[::-1]))
    best = run = 0
    for covered in p[first:last + 1]:
        if covered:
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best / float(TILE)


def port_sprite(side, port_kind="port"):
    return load(os.path.join(TEX, "melta-pipe-{}-{}.png".format(port_kind, side)))


def pipe_sprite(side):
    sprite_name, _ = PIPE_SPRITE[side]
    return load(os.path.join(GAME, "base", "graphics", "entity", "pipe", sprite_name))


def cap_added(side):
    """How many pixels the blanking plate adds over the open port's art.

    An alpha test at the mouth centre cannot tell a lit plate from the dark inside of
    an open bore, so this compares the two sprites instead: the capped one must carry
    extra opaque pixels at the outboard end, i.e. there really is a plate there.
    """
    cap = alpha_of(port_sprite(side, "cap")) >= 8
    open_ = alpha_of(port_sprite(side, "port")) >= 8
    extra = cap & ~open_
    if extra.sum() < 1:
        return 0
    dist, _prof = signed_tiles(*axis_profile(alpha_of(port_sprite(side, "cap")), side),
                               side=side)
    # weight by how far outboard the extra pixels sit: a plate lives at the mouth
    h, w = extra.shape
    cy, cx = h // 2, w // 2
    sx, sy = SIGN[side]
    weight = 0
    for y, x in zip(*np.nonzero(extra)):
        out = ((y - cy) * sy + (x - cx) * sx) / float(TILE)
        if out > 0.2:
            weight += 1
    return weight


def measure_side(side, port_kind="port"):
    """Port reach, pipe near edge (both tiles from the centre) and the seam.

    The pipe sprite is measured on its own frame, i.e. from the *pipe's* tile centre,
    so its near edge relative to the turret is PIPE_TILES minus that extent.
    """
    with_pipe = port_kind == "port"
    layers, _flat = scene(side, port_kind=port_kind, with_pipe=with_pipe)
    # the port sprite's frame centre IS the connection point, so its own outward
    # reach is measured from there and the port's distance adds to it
    port = port_sprite(side, port_kind)
    reach = port_reach() + port_offset(side) + outward_run(port, side)
    pipe = PIPE_TILES - outward_run(pipe_sprite(side), NEAR[side])
    out = {"port": round(reach, 3), "pipe": round(pipe, 3),
           "overlap": round(reach - pipe, 3),
           "seam": round(seam_run(layers, side), 3) if with_pipe else None}
    if not with_pipe:
        out["cap_px"] = cap_added(side)
    return out


def measure_all(port_kind="port"):
    return {side: measure_side(side, port_kind) for side in SIDES}


def print_table(table, port_kind="port"):
    print("{} sprites".format(port_kind))
    capped = port_kind.startswith("cap")
    print("side     port    pipe   overlap    {}"
          .format("cap px" if capped else "seam"))
    bad = []
    for side in SIDES:
        r = table[side]
        extra = r["cap_px"] if capped else r["seam"]
        print("{:<6} {:6.2f} {:6.2f} {:9.2f} {:7.0f}".format(
            side, r["port"], r["pipe"], r["overlap"], extra))
        # the port must reach the pipe's near edge, leave no bare ground in between
        # and, when capped, carry a real plate (extra pixels) at the mouth
        if r["overlap"] < -0.02:
            bad.append(side)
        if capped and r["cap_px"] < 60:
            bad.append(side)
        if not capped and r["seam"] > MAX_SEAM:
            bad.append(side)
    if bad:
        print("FAIL: {}".format(", ".join(sorted(set(bad)))))
    elif capped:
        print("OK: every bare port is blanked off, not hollow")
    else:
        print("OK: port meets the pipe on all four sides, no bare ground in between")
    return not bad


# ------------------------------------------------------------------- images ---
def write_docs(table_open, table_cap):
    os.makedirs(DOCS, exist_ok=True)
    for side in SIDES:
        _l, img = scene(side, port_kind="port", with_pipe=True, tiles=7)
        r = table_open[side]
        label(img, "{}: port {}  pipe {}  seam {}".format(
            side, r["port"], r["pipe"], r["seam"]))
        img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(
            os.path.join(DOCS, "{}-open-2x.png".format(side)))

        _l, cap = scene(side, port_kind="cap", with_pipe=False, tiles=7)
        label(cap, "{}: bare port, capped".format(side))
        cap.resize((cap.width * 2, cap.height * 2), Image.NEAREST).save(
            os.path.join(DOCS, "{}-cap-2x.png".format(side)))

    # one overview with all four sides at once, open ports
    n = int(round(7 * TILE))
    grid = Image.new("RGBA", (n * 2 + 8, n * 2 + 8), (28, 30, 26, 255))
    for i, side in enumerate(SIDES):
        grid.alpha_composite(scene(side, tiles=7)[1], ((i % 2) * (n + 8),
                                                    (i // 2) * (n + 8)))
    grid.save(os.path.join(DOCS, "overview.png"))

    with open(os.path.join(DOCS, "join.json"), "w") as fh:
        json.dump({"pipe_reach": port_reach(), "max_seam": MAX_SEAM,
                   "open": table_open, "cap": table_cap}, fh, indent=2)
    print("wrote", DOCS)


def main(argv):
    table_open = measure_all("port")
    table_cap = measure_all("cap")
    ok = print_table(table_open, "port (pipe_picture)") and True
    ok = print_table(table_cap, "cap (pipe_covers)") and ok
    if "--check" in argv:
        return 0 if ok else 1
    write_docs(table_open, table_cap)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
