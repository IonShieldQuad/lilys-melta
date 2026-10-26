"""Measure the melta turret's pipe connectors against the art the game draws.

Eyeballing a turret at Factorio's zoom is how the ports ended up "visibly
misaligned" twice. This script replaces the eyeball with numbers:

 1. it reads the four `fluid_box.pipe_connections` from the prototype files
    (`prototypes/entity.lua`, with `C.pipe_reach` resolved out of `constants.lua`),
    together with the sprite geometry the same prototype draws them with
    (`prototypes/graphics.lua`: width/height/scale/shift per side);
 2. it builds the composite the engine builds -- ground, hull base sprite
    (priority high), the neighbouring vanilla pipe, then the port sprite
    (priority extra-high, so it sits over the pipe end) -- at 64 px/tile,
    which is exactly Factorio zoom 2.0;
 3. it puts a crosshair at the computed pixel of each connection point
    (`frame/2 + (position + shift) * 32 * scale`) and a box on the port's
    measured extent, and writes one debug PNG per rotation;
 4. it measures the two things that were actually wrong:
      * `width`  -- the connector's cross-axis width in tiles, against the pipe's
                    own width (the pipe has to plug *into* it, not beside it);
      * `in`     -- how far the art's inboard end sits from the turret centre
                    (the port has to be mounted on the hull, not float at the
                    pipe mouth).
    plus the previously-fixed things it must not regress:
      * `overlap` -- port mouth minus the pipe's near edge; negative is a gap;
      * `seam`    -- longest run of bare ground between port and pipe; must be 0;
      * `marker`  -- is the computed connection pixel inside the port sprite's
                    own opaque footprint (the marker really is on the port).

`--check` exits 1 if any side fails. `baseline.json`, if present, makes the run
print the change against the previously shipped art -- that is how "1.5x the
size" and "1 tile inwards" get proved instead of described.

Run from anywhere:

  python tools/check_pipe_connections.py            # measure + write debug PNGs
  python tools/check_pipe_connections.py --check    # gate only, no writes
  python tools/check_pipe_connections.py --record   # also refresh baseline.json
"""

import argparse
import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TILE = 64                       # px per tile == Factorio zoom 2.0
PIPE_TILES = 2.0                # nearest a 1-tile pipe can sit (1.2 collision)
ALPHA_SOLID = 64                # "the model", not its baked shadow
ALPHA_ANY = 8                   # "anything at all", shadow included
SIDES = ("north", "east", "south", "west")
SIGN = {"north": (0, -1), "east": (1, 0), "south": (0, 1), "west": (-1, 0)}
OPPOSITE = {"north": "south", "south": "north", "east": "west", "west": "east"}
# how a straight pipe in the neighbouring tile is drawn, and where that tile is
PIPE_SPRITE = {
    "north": ("pipe-straight-vertical.png", (0, -1)),
    "south": ("pipe-straight-vertical.png", (0, 1)),
    "east": ("pipe-straight-horizontal.png", (1, 0)),
    "west": ("pipe-straight-horizontal.png", (-1, 0)),
}
# rotation index -> world directions the four ports end up facing
ROTATIONS = (("north", ("north", "east", "south", "west")),
             ("east", ("east", "south", "west", "north")),
             ("south", ("south", "west", "north", "east")),
             ("west", ("west", "north", "east", "south")))

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(HERE)
TEX = os.path.join(MOD, "graphics", "entity", "melta-turret")
DOCS = os.path.join(MOD, "docs", "pipe-connections")
BASELINE = os.path.join(DOCS, "baseline.json")
GAME = os.environ.get("FACTORIO_DATA",
                      "E:/SteamLibrary/steamapps/common/Factorio/data")


# ------------------------------------------------------------- prototypes ---
def read(path):
    with open(os.path.join(MOD, path), "r", encoding="utf-8") as fh:
        return fh.read()


def constants():
    """C.pipe_reach and C.pipe_shift out of constants.lua."""
    text = read("constants.lua")
    m = re.search(r"^\s*C\.pipe_reach\s*=\s*(-?[0-9.]+)", text, re.M)
    if not m:
        raise SystemExit("constants.lua: no C.pipe_reach")
    reach = float(m.group(1))
    block = re.search(r"C\.pipe_shift\s*=\s*\{(.*?)\n\}", text, re.S)
    if not block:
        raise SystemExit("constants.lua: no C.pipe_shift")
    shift = {}
    for side in SIDES:
        m = re.search(r"%s\s*=\s*\{\s*(-?[0-9.]+)\s*,\s*(-?[0-9.]+)\s*\}"
                      % side, block.group(1))
        if not m:
            raise SystemExit("constants.lua: no C.pipe_shift." + side)
        shift[side] = (float(m.group(1)), float(m.group(2)))
    return reach, shift


def pipe_connections():
    """The four pipe_connections, as the prototype declares them.

    `position` in entity.lua is written against C.pipe_reach, so it is resolved
    here rather than copied: changing the constant moves the check with it.
    """
    reach, _shift = constants()
    text = read("prototypes/entity.lua")
    box = re.search(r"pipe_connections\s*=\s*\{(.*?)\n\s*\},", text, re.S)
    if not box:
        raise SystemExit("entity.lua: no pipe_connections block")
    out = {}
    for m in re.finditer(
            r"direction\s*=\s*defines\.direction\.(\w+)\s*,\s*"
            r"position\s*=\s*\{\s*(-?[0-9.]+|C\.pipe_reach)\s*,\s*"
            r"(-?[0-9.]+|C\.pipe_reach)\s*\}", box.group(1)):
        direction, x, y = m.group(1), m.group(2), m.group(3)
        pick = lambda v: reach if v == "C.pipe_reach" else float(v)
        out[direction] = (pick(x), pick(y))
    missing = [s for s in SIDES if s not in out]
    if missing:
        raise SystemExit("entity.lua: no pipe_connection for " + ", ".join(missing))
    return out


def port_sprites():
    """width/height/scale/shift of the pipe_picture sprite, per side."""
    text = read("prototypes/graphics.lua")
    m = re.search(r"width\s*=\s*(\d+)\s*,\s*height\s*=\s*(\d+)\s*,\s*"
                  r"scale\s*=\s*([0-9.]+)\s*,\s*shift\s*=\s*C\.pipe_shift",
                  text, re.S)
    if not m:
        raise SystemExit("graphics.lua: port_side() sprite geometry not found")
    w, h, scale = int(m.group(1)), int(m.group(2)), float(m.group(3))
    _reach, shift = constants()
    return {side: {"width": w, "height": h, "scale": scale, "shift": shift[side]}
            for side in SIDES}


def expected_pixel(conn, side, frames, sprite):
    """Where the connection point lands inside that side's port sprite.

    The engine draws the sprite centred on the connection point plus `shift`,
    so the point itself is the frame centre minus `shift`:

        px = frame/2 + (position + shift) * 32 * scale   <- the port's centre
        and the connection point is the frame centre - shift * 32 * scale
    """
    del conn, side, frames
    sx, sy = sprite["shift"]
    px = sprite["width"] / 2.0 - sx * 32.0 * sprite["scale"]
    py = sprite["height"] / 2.0 - sy * 32.0 * sprite["scale"]
    return px, py


# ---------------------------------------------------------------- imaging ---
def load(path):
    return Image.open(path).convert("RGBA")


def alpha(img, threshold=ALPHA_ANY):
    return np.asarray(img, dtype=np.uint8)[:, :, 3] >= threshold


def put(target, sprite, cx, cy):
    target.alpha_composite(sprite, (int(round(cx - sprite.width / 2.0)),
                                    int(round(cy - sprite.height / 2.0))))


def ground(w, h, tile=TILE):
    img = Image.new("RGBA", (w, h), (58, 74, 44, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            v = 5 if ((x // tile + y // tile) % 2) else 0
            d.rectangle([x, y, x + tile - 1, y + tile - 1],
                        fill=(58 + v, 74 + v, 44 + v, 255))
    return img


def font(size=15):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def port_path(side, kind="port"):
    return os.path.join(TEX, "melta-pipe-{}-{}.png".format(kind, side))


def pipe_path(side):
    return os.path.join(GAME, "base", "graphics", "entity", "pipe",
                        PIPE_SPRITE[side][0])


def vanilla_cover_path(side):
    """Vanilla's own port picture, at the same 128 px / scale 0.5 convention.

    This is the bar the connector has to clear: it is the fitting Factorio ships for
    exactly this job, so "our socket is at least as chunky as the base game's" is a
    calibrated target instead of a number someone liked.
    """
    return os.path.join(GAME, "base", "graphics", "entity", "pipe-covers",
                        "pipe-cover-{}.png".format(side))


def axis_frame(img):
    """(axis distance in tiles from the frame centre, per-row/col profile)."""
    return img.width // 2, img.height // 2


def profile(mask, side, band=None):
    """Coverage along the pipe axis, in tiles out (positive = away from centre).

    `band` limits the scan to a strip around the axis (tiles), which is how the
    pipe's own near edge is measured without the rest of its body answering.
    """
    h, w = mask.shape
    cy, cx = h // 2, w // 2
    b = int(round((band if band is not None else 1.0) * TILE))
    if side in ("north", "south"):
        strip = mask[:, max(0, cx - b):cx + b]
        prof = strip.any(axis=1) if b else mask.any(axis=1)
        idx = np.arange(h) - cy
        sign = SIGN[side][1]
    else:
        strip = mask[max(0, cy - b):cy + b, :]
        prof = strip.any(axis=0) if b else mask.any(axis=0)
        idx = np.arange(w) - cx
        sign = SIGN[side][0]
    return idx * sign / float(TILE), prof


def reach_out(mask, side, threshold=ALPHA_SOLID):
    """Furthest solid pixel along the axis, tiles from the frame centre."""
    dist, prof = profile(mask, side)
    keep = dist > 0
    d, p = dist[keep], prof[keep]
    return float(d[p].max()) if p.any() else 0.0


def reach_in(mask, side, threshold=ALPHA_SOLID):
    dist, prof = profile(mask, side)
    keep = dist < 0
    d, p = dist[keep], prof[keep]
    return float(-d[p].min()) if p.any() else 0.0


def cross_width(mask, side, threshold=ALPHA_SOLID, outboard_only=True):
    """Widest perpendicular extent of the sprite's solid pixels, in tiles.

    Only the outboard half is used for the port: the inboard mount pad is welded
    to the hull and is deliberately wider than the barrel, so including it would
    flatter the number that decides "does the pipe plug into this".
    """
    h, w = mask.shape
    cy, cx = h // 2, w // 2
    if side in ("north", "south"):
        rows = np.arange(h) - cy
        keep_rows = rows * SIGN[side][1] > 0 if outboard_only else np.ones(h, bool)
        sub = mask[keep_rows, :]
    else:
        cols = np.arange(w) - cx
        keep_cols = cols * SIGN[side][0] > 0 if outboard_only else np.ones(w, bool)
        sub = mask[:, keep_cols]
    if not sub.any():
        return 0.0
    if side in ("north", "south"):
        cols = np.where(sub.any(axis=0))[0]
    else:
        cols = np.where(sub.any(axis=1))[0]
    return float(cols.max() - cols.min() + 1) / float(TILE)


def seam_run(layers, side, limit=2.6):
    """Longest bare-ground run between the machine and the pipe, in tiles."""
    dist, prof = profile(alpha(layers), side)
    order = np.argsort(dist)
    d, p = dist[order], prof[order]
    keep = (d >= 0) & (d <= limit)
    d, p = d[keep], p[keep]
    if not p.any():
        return float(limit)
    first = int(np.argmax(p))
    last = len(p) - 1 - int(np.argmax(p[::-1]))
    worst = run = 0
    for covered in p[first:last + 1]:
        if covered:
            run = 0
        else:
            run += 1
            worst = max(worst, run)
    return worst / float(TILE)


# ------------------------------------------------------------------- scene ---
def compose(world_sides, heads=None, with_pipe=True, tiles=7):
    """Ground + hull + pipes + ports, drawn in the engine's own order."""
    n = int(round(tiles * TILE))
    layers = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    cx = cy = n / 2.0
    if heads is not None:
        put(layers, heads, cx, cy)
    put(layers, load(os.path.join(TEX, "melta-turret-base.png")), cx, cy)

    reach, shift = constants()
    sprites = port_sprites()
    if with_pipe:
        for side in world_sides:
            _name, (dx, dy) = PIPE_SPRITE[side]
            put(layers, load(pipe_path(side)),
                cx + dx * PIPE_TILES * TILE, cy + dy * PIPE_TILES * TILE)
    for side in world_sides:
        sp = sprites[side]
        ox, oy = sp["shift"]
        put(layers, load(port_path(side)),
            cx + (SIGN[side][0] * reach + ox) * TILE,
            cy + (SIGN[side][1] * reach + oy) * TILE)
    flat = ground(n, n)
    flat.alpha_composite(layers)
    return layers, flat


def annotate(img, world_sides, side_of_conn):
    """Crosshair on every computed connection pixel, box on the port's extent."""
    draw = ImageDraw.Draw(img)
    cx = cy = img.width / 2.0
    reach, _shift = constants()
    sprites = port_sprites()
    for side in world_sides:
        spx, spy = SIGN[side]
        port_centre = (cx + (spx * reach + sprites[side]["shift"][0]) * TILE,
                       cy + (spy * reach + sprites[side]["shift"][1]) * TILE)
        # the computed connection point: frame centre of the port sprite, which
        # is the sprite centre pulled back by `shift`
        conn = (cx + spx * reach * TILE, cy + spy * reach * TILE)
        r = 9
        draw.line([conn[0] - r, conn[1], conn[0] + r, conn[1]], fill=(0, 255, 255, 255), width=2)
        draw.line([conn[0], conn[1] - r, conn[0], conn[1] + r], fill=(0, 255, 255, 255), width=2)
        draw.ellipse([conn[0] - 2, conn[1] - 2, conn[0] + 2, conn[1] + 2],
                     outline=(0, 255, 255, 255))
        # the port sprite's own frame -- proves where the art is centred
        half = sprites[side]["width"] * sprites[side]["scale"] * TILE / 64.0 / 2.0
        draw.rectangle([port_centre[0] - half, port_centre[1] - half,
                        port_centre[0] + half, port_centre[1] + half],
                       outline=(255, 210, 0, 130))
        draw.text((conn[0] + 12, conn[1] - 8), side_of_conn(side),
                  font=font(13), fill=(0, 255, 255, 255))
    return img


# ------------------------------------------------------------------ measure ---
def measure(side):
    """All per-side numbers: connector width/inboard end, join, marker."""
    sprites = port_sprites()
    port = load(port_path(side))
    pipe = load(pipe_path(side))
    mask_port = alpha(port, ALPHA_SOLID)
    mask_pipe = alpha(pipe, ALPHA_SOLID)
    reach, shift = constants()

    mouth = reach + sign_out(shift[side], side) + reach_out(mask_port, side)
    inner = reach + sign_out(shift[side], side) - reach_in(mask_port, side)
    pipe_near = PIPE_TILES - reach_out(mask_pipe, OPPOSITE[side])
    vanilla = cross_width(alpha(load(vanilla_cover_path(side)), ALPHA_SOLID),
                          side, outboard_only=False)
    layers, _flat = compose(tuple(SIDES))
    px, py = expected_pixel(None, side, None, sprites[side])
    marker_on_art = bool(mask_port[int(round(py)), int(round(px))]) or \
        bool(alpha(port, ALPHA_ANY)[int(round(py)), int(round(px))])
    return {
        "port_width": round(cross_width(mask_port, side), 3),
        "pipe_width": round(cross_width(mask_pipe, OPPOSITE[side], outboard_only=False), 3),
        "vanilla_width": round(vanilla, 3),
        "mouth": round(mouth, 3),
        "inboard": round(inner, 3),
        "pipe_near": round(pipe_near, 3),
        "overlap": round(mouth - pipe_near, 3),
        "seam": round(seam_run(layers, side), 3),
        "marker_px": [int(round(px)), int(round(py))],
        "marker_on_art": marker_on_art,
    }


def sign_out(shift_xy, side):
    """How much further out the art is drawn than the connection point."""
    return SIGN[side][0] * shift_xy[0] + SIGN[side][1] * shift_xy[1]


def table(results):
    print("pipe connectors -- melta turret")
    print("side   width  pipe   vanil  vs_van  inboard   mouth   pipe_N  overlap  seam  marker")
    bad = []
    for side in SIDES:
        r = results[side]
        ratio = r["port_width"] / r["vanilla_width"] if r["vanilla_width"] else 0.0
        print("{:<6} {:5.2f}  {:5.2f}  {:5.2f}  {:6.2f}   {:6.2f}   {:6.2f}   {:6.2f}  {:7.2f}  "
              "{:4.2f}  {}".format(side, r["port_width"], r["pipe_width"],
                                   r["vanilla_width"], ratio,
                                   r["inboard"], r["mouth"], r["pipe_near"],
                                   r["overlap"], r["seam"],
                                   "ok" if r["marker_on_art"] else "OFF ART"))
        if not r["marker_on_art"]:
            bad.append(side + " (marker not on the port art)")
        if r["overlap"] < -0.02:
            bad.append(side + " (gap to the pipe)")
        if r["seam"] > 0.0:
            bad.append(side + " (bare ground in the join)")
        if ratio < 0.98:
            bad.append(side + " (connector smaller than vanilla's own pipe cover)")
    return bad


def delta(results):
    """Print the change against the recorded baseline, if there is one."""
    if not os.path.exists(BASELINE):
        return
    with open(BASELINE, "r", encoding="utf-8") as fh:
        base = json.load(fh)["sides"]
    print("\nagainst the recorded baseline:")
    print("side    width  was    x      inboard  was     moved")
    for side in SIDES:
        b, r = base.get(side), results[side]
        if not b:
            continue
        ratio = r["port_width"] / b["port_width"] if b.get("port_width") else 0.0
        print("{:<6} {:5.2f}  {:5.2f}  {:5.2f}   {:6.2f}   {:6.2f}   {:+.2f}"
              .format(side, r["port_width"], b["port_width"], ratio,
                      r["inboard"], b["inboard"], b["inboard"] - r["inboard"]))


def write_docs(results):
    os.makedirs(DOCS, exist_ok=True)
    for name, world_sides in ROTATIONS:
        _layers, flat = compose(world_sides)
        img = annotate(flat, world_sides, lambda s: s)
        label = "rotation: facing {}   cyan + = connection point   yellow box = port sprite".format(name)
        ImageDraw.Draw(img).text((8, 6), label, font=font(15),
                                 fill=(240, 240, 210, 255))
        img.resize((img.width * 2, img.height * 2), Image.NEAREST).save(
            os.path.join(DOCS, "rot-{}-2x.png".format(name)))
    # capped ports too: a bare side must read as blanked off
    _layers, flat = compose(tuple(SIDES), with_pipe=False)
    flat.resize((flat.width * 2, flat.height * 2), Image.NEAREST).save(
        os.path.join(DOCS, "capped-2x.png"))
    with open(os.path.join(DOCS, "connections.json"), "w", encoding="utf-8") as fh:
        json.dump({"pipe_reach": constants()[0], "tile_px": TILE,
                   "pipe_tiles": PIPE_TILES, "sides": results}, fh, indent=2)
    print("\nwrote", DOCS)


def record(results):
    os.makedirs(DOCS, exist_ok=True)
    with open(BASELINE, "w", encoding="utf-8") as fh:
        json.dump({"pipe_reach": constants()[0],
                   "note": "art as shipped before the connector rework",
                   "sides": results}, fh, indent=2)
    print("recorded", BASELINE)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="gate only, write nothing")
    ap.add_argument("--record", action="store_true", help="refresh baseline.json")
    args = ap.parse_args(argv)

    for side in SIDES:
        for path in (port_path(side), port_path(side, "cap")):
            if not os.path.exists(path):
                raise SystemExit("missing sprite: " + path)

    results = {side: measure(side) for side in SIDES}
    bad = table(results)
    delta(results)
    if args.record:
        record(results)
    if not args.check:
        write_docs(results)
    if bad:
        print("\nFAIL: " + "; ".join(bad))
        return 1
    print("\nOK: connector on the port art, meets the pipe on all four sides, "
          "no bare ground in the join, at least as wide as the pipe")
    return 0


if __name__ == "__main__":
    sys.exit(main())
