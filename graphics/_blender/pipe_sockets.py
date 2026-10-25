"""Pipe socket views and the measured hull/pipe gap table.

Two jobs, both sprite-accurate:

  * measure how far the hull's silhouette reaches along each of the four pipe axes,
    where the pipe's own art starts, and the ground gap between the two;
  * draw the docs/pipe-sockets images from the same composite the game produces
    (turret centre on a tile centre, pipes 2.0 tiles out, covers at C.pipe_reach).

Everything is drawn at 64 px/tile, which is Factorio's zoom 2.0, so the output is
pixel-exact with the game's own art: the mod's base sprite, `__base__`'s pipe sprites
and `__base__`'s pipe covers, pasted where the engine puts them.

These are NOT live screenshots. This install is the Steam build with no standalone
executable: outside Steam it refuses to start a graphics run, and every headless mode
skips the renderer, so `game.take_screenshot` writes nothing. See
docs/pipe-sockets/README.md. The live visual pass belongs to the in-game card.

Measuring convention (the one the gap table in DESIGN.md quotes): the hull's silhouette
on a side is the furthest *visible* pixel (alpha > 8, so soft cast shadow counts as the
machine's mass) inside a +-0.5 tile band around that side's pipe axis, because that is
the slot the pipe has to meet. The pipe's near edge comes from the pipe sprite itself,
pasted on its own tile, measured the same way.

Run:

  python pipe_sockets.py                      # measure, write docs/pipe-sockets
  python pipe_sockets.py --check              # measure only, exit 1 if a gap > 0.22
  python pipe_sockets.py --before OLD.png     # also write the north before/after panel

FACTORIO_DATA overrides the game install path.
"""

import json
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

TILE = 64                        # px per tile == Factorio zoom 2.0
BAND = TILE // 2                 # +-0.5 tile around the pipe axis
PIPE_TILES = 2.0                 # nearest legal pipe distance (1.2 collision box)
MAX_GAP = 0.22                   # vanilla assembling-machine-2 leaves 0.24 north

HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.dirname(os.path.dirname(HERE))
GAME = os.environ.get("FACTORIO_DATA",
                      "E:/SteamLibrary/steamapps/common/Factorio/data")
TEX = os.path.join(MOD, "graphics", "entity", "melta-turret")
BASE = os.path.join(TEX, "melta-turret-base.png")
DOCS = os.path.join(MOD, "docs", "pipe-sockets")
CONSTANTS = os.path.join(MOD, "constants.lua")

# which pipe sprite a pipe in the neighbouring tile is drawn with: the pipe also
# connects onward (away from the turret), so it is a straight run
SIDES = {
    "north": ("pipe-straight-vertical.png", (0, -1)),
    "south": ("pipe-straight-vertical.png", (0, 1)),
    "east": ("pipe-straight-horizontal.png", (1, 0)),
    "west": ("pipe-straight-horizontal.png", (-1, 0)),
}
# the extent that faces the turret, i.e. the pipe's near edge
NEAR_EXTENT = {"north": "south", "south": "north", "east": "west", "west": "east"}
ORDER = ("north", "east", "south", "west")


# ------------------------------------------------------------------ helpers ----
def load(path):
    return Image.open(path).convert("RGBA")


def game_graphic(*parts):
    return load(os.path.join(GAME, "base", "graphics", "entity", *parts))


def pipe_reach():
    """C.pipe_reach, read from constants.lua so the docs cannot drift from the mod."""
    with open(CONSTANTS, "r", encoding="utf-8") as fh:
        text = fh.read()
    m = re.search(r"^\s*C\.pipe_reach\s*=\s*([0-9.]+)", text, re.M)
    if not m:
        raise SystemExit("could not find C.pipe_reach in constants.lua")
    return float(m.group(1))


def canvas(tiles):
    n = int(round(tiles * TILE))
    return Image.new("RGBA", (n, n), (0, 0, 0, 0))


def put(target, sprite, cx, cy):
    """Composite a sprite centred on a pixel position, 1:1 at 64 px/tile."""
    target.alpha_composite(sprite, (int(round(cx - sprite.width / 2.0)),
                                    int(round(cy - sprite.height / 2.0))))


def alpha_of(img):
    return np.asarray(img, dtype=np.uint8)[:, :, 3]


def extents(alpha, threshold=8, band=BAND):
    """Furthest visible pixel per side, in tiles from the canvas centre.

    `band` restricts the search to a +-band px slot around the axis through the centre
    (the slot the pipe occupies). band=None measures the whole frame, which is what a
    single-sprite scene wants.
    """
    m = alpha >= threshold
    h, w = m.shape
    cy, cx = h / 2.0, w / 2.0
    c = int(round(cx))
    band = BAND if band is None else band
    axis_y = m if band <= 0 else m[:, c - band:c + band]   # north / south
    axis_x = m if band <= 0 else m[c - band:c + band, :]   # east / west
    if not axis_y.any() or not axis_x.any():
        raise SystemExit("empty silhouette -- is the sprite loaded?")
    return {
        "north": (cy - np.nonzero(axis_y.any(1))[0].min()) / TILE,
        "south": (np.nonzero(axis_y.any(1))[0].max() + 1 - cy) / TILE,
        "east": (np.nonzero(axis_x.any(0))[0].max() + 1 - cx) / TILE,
        "west": (cx - np.nonzero(axis_x.any(0))[0].min()) / TILE,
    }


def pipe_scene(side):
    """Canvas holding only that side's pipe sprite, on its own 2.0-tile tile.
    Six tiles wide so the whole sprite sits inside the frame with room to measure."""
    pipe_canvas = canvas(6)
    sprite_name, (dx, dy) = SIDES[side]
    put(pipe_canvas, game_graphic("pipe", sprite_name),
        pipe_canvas.width / 2.0 + dx * PIPE_TILES * TILE,
        pipe_canvas.height / 2.0 + dy * PIPE_TILES * TILE)
    return pipe_canvas


def pipe_near_edge(side, threshold=8):
    """Where the pipe's own art starts, measured on its own tile: the sprite is alone
    in the frame, so no axis band is needed. The pipe sits off-centre, so the raw
    extent is signed -- its absolute value is the distance from the turret centre."""
    raw = extents(alpha_of(pipe_scene(side)), threshold=threshold, band=0)
    return abs(raw[NEAR_EXTENT[side]])


def ground(w, h, tile=TILE):
    """Flat grass with a 1-tile checker and a light line every 4 tiles, so a reader can
    count tiles instead of trusting the caption."""
    img = Image.new("RGBA", (w, h), (62, 78, 46, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, h, tile):
        for x in range(0, w, tile):
            v = 4 if ((x // tile + y // tile) % 2) else 0
            d.rectangle([x, y, x + tile - 1, y + tile - 1],
                        fill=(62 + v, 78 + v, 46 + v, 255))
    for x in range(0, w, tile * 4):
        d.line([(x, 0), (x, h)], fill=(96, 112, 74, 255))
    for y in range(0, h, tile * 4):
        d.line([(0, y), (w, y)], fill=(96, 112, 74, 255))
    return img


def font(size=16):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def label(img, text, xy=(8, 6), fill=(240, 236, 200, 255)):
    ImageDraw.Draw(img).text(xy, text, font=font(), fill=fill)


# ---------------------------------------------------------------- composite ----
def socket_composite(tiles, base_sprite, head_sprite=None, reach=None, covers=True,
                     sides=ORDER):
    """One scene: ground, head (priority medium), hull (high), pipes and covers
    (extra-high) -- the same draw order the prototypes use."""
    reach = pipe_reach() if reach is None else reach
    img = ground(int(round(tiles * TILE)), int(round(tiles * TILE)))
    layers = Image.new("RGBA", img.size, (0, 0, 0, 0))
    cx = cy = img.size[0] / 2.0
    if head_sprite is not None:
        put(layers, head_sprite, cx, cy)
    put(layers, base_sprite, cx, cy)
    for side in sides:
        sprite_name, (dx, dy) = SIDES[side]
        put(layers, game_graphic("pipe", sprite_name),
            cx + dx * PIPE_TILES * TILE, cy + dy * PIPE_TILES * TILE)
        if covers:
            put(layers, game_graphic("pipe-covers",
                                     "pipe-cover-{}-shadow.png".format(side)),
                cx + dx * reach * TILE, cy + dy * reach * TILE)
            put(layers, game_graphic("pipe-covers",
                                     "pipe-cover-{}.png".format(side)),
                cx + dx * reach * TILE, cy + dy * reach * TILE)
    img.alpha_composite(layers)
    return img


def head_frame(direction):
    sheet = load(os.path.join(TEX, "melta-turret-head-{}.png".format(direction // 8 + 1)))
    row = direction % 8
    return sheet.crop((0, row * 256, 256, (row + 1) * 256))


# ---------------------------------------------------------------- measuring ----
def measure(base_path=BASE):
    """Hull silhouette, pipe near edge and the gap between them, per side."""
    alpha = alpha_of(load(base_path))
    table = {}
    for side in ORDER:
        p_loose, p_tight = pipe_near_edge(side, 8), pipe_near_edge(side, 200)
        h_loose = extents(alpha, threshold=8)[side]
        h_tight = extents(alpha, threshold=200)[side]
        table[side] = {
            "hull": round(float(h_loose), 3),
            "pipe_near": round(float(p_loose), 3),
            "gap": round(float(p_loose - h_loose), 3),
            "hull_strict": round(float(h_tight), 3),
            "gap_strict": round(float(p_tight - h_tight), 3),
        }
    return table


def print_table(table):
    print("side   hull  pipe-near    gap   gap(strict)")
    for side in ORDER:
        r = table[side]
        line = "{:<6} {:5.2f} {:9.2f} {:6.2f} {:12.2f}".format(
            side, r["hull"], r["pipe_near"], r["gap"], r["gap_strict"])
        print(line + ("" if max(r["gap"], r["gap_strict"]) <= MAX_GAP else "   <-- over"))
    print("(tiles from the turret centre; positive gap = bare ground between the two;")
    print(" strict = alpha >= 200, so no soft cast shadow counts)")
    bad = [s for s in ORDER if max(table[s]["gap"], table[s]["gap_strict"]) > MAX_GAP]
    if bad:
        print("FAIL: gap over {:.2f} tiles on {}".format(MAX_GAP, ", ".join(bad)))
    else:
        print("OK: every side meets its pipe within {:.2f} tiles".format(MAX_GAP))
    return not bad


def gap_line(table):
    return "gap: north {:.2f}  south {:.2f}  east {:.2f}  west {:.2f} tiles".format(
        table["north"]["gap"], table["south"]["gap"], table["east"]["gap"],
        table["west"]["gap"])


# ------------------------------------------------------------------- images ----
def write_overview(table, docs):
    img = socket_composite(9, load(BASE), head_frame(0))
    label(img, "melta turret + one pipe per side; sockets at C.pipe_reach = {:.2f}".format(
        pipe_reach()))
    label(img, gap_line(table), xy=(8, 28), fill=(225, 225, 190, 255))
    img.save(os.path.join(docs, "overview.png"))


def write_sides(table, docs):
    """One crop per side, 4x4 tiles, without the head: at direction 0 the gun points
    north and its muzzle reaches the north pipe, i.e. the head is what hides the seam."""
    scene = socket_composite(4, load(BASE))
    for side in ORDER:
        crop = scene.copy()
        label(crop, "{}: hull {:.2f}, pipe {:.2f}, gap {:.2f}".format(
            side, table[side]["hull"], table[side]["pipe_near"], table[side]["gap"]),
            xy=(6, 4))
        crop.save(os.path.join(docs, "{}.png".format(side)))
        crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST).save(
            os.path.join(docs, "{}-2x.png".format(side)))


def write_variants(docs):
    cells = [(1.05, True, "1.05 - sockets sink into the hull"),
             (pipe_reach(), True, "{:.2f} - chosen".format(pipe_reach())),
             (1.20, True, "1.20 - sockets float off the hull"),
             (pipe_reach(), False, "no pipe_covers: the 0.3.0 look")]
    head = head_frame(0)
    panels = []
    for reach, covers, text in cells:
        img = socket_composite(9, load(BASE), head, reach=reach, covers=covers)
        label(img, text)
        panels.append(img)
    w, h = panels[0].size
    out = Image.new("RGBA", (w * 2 + 8, h * 2 + 8), (28, 30, 26, 255))
    for i, panel in enumerate(panels):
        out.alpha_composite(panel, ((i % 2) * (w + 8), (i // 2) * (h + 8)))
    out.save(os.path.join(docs, "variants.png"))


def write_vanilla_reference(table, docs):
    """assembling-machine-2's north side: same framing, same measurement, so our
    number has a vanilla number next to it."""
    asm = game_graphic("assembling-machine-2", "assembling-machine-2-base.png")
    stub = game_graphic("assembling-machine-2", "assembling-machine-2-pipe-N.png")
    img = ground(9 * TILE, 9 * TILE)
    cx = cy = img.size[0] / 2.0
    # the machine's own art first (sprite + the north pipe stub it draws when a pipe is
    # connected there), measured on its own -- measuring the composite would just
    # find the pipe sprite and call it the hull
    machine = Image.new("RGBA", img.size, (0, 0, 0, 0))
    put(machine, asm, cx, cy)
    # vanilla draws the stub with shift = util.by_pixel(0.5, 11.0) at scale 1
    put(machine, stub, cx + 0.5, cy + 11.0)
    vanilla_north = extents(alpha_of(machine))["north"]
    layers = machine.copy()
    put(layers, game_graphic("pipe", "pipe-straight-vertical.png"),
        cx, cy - PIPE_TILES * TILE)
    img.alpha_composite(layers)
    near = pipe_near_edge("north")
    label(img, "vanilla assembling-machine-2 + pipe")
    label(img, "hull {:.2f}, pipe {:.2f}, north gap {:.2f}  (melta now {:.2f})".format(
        vanilla_north, near, near - vanilla_north, table["north"]["gap"]),
        xy=(8, 28), fill=(225, 225, 190, 255))

    ours = socket_composite(9, load(BASE))
    label(ours, "melta + pipe, same framing")
    label(ours, "hull {:.2f}, pipe {:.2f}, north gap {:.2f}".format(
        table["north"]["hull"], table["north"]["pipe_near"], table["north"]["gap"]),
        xy=(8, 28), fill=(225, 225, 190, 255))

    out = Image.new("RGBA", (img.width * 2 + 8, img.height), (28, 30, 26, 255))
    out.alpha_composite(img, (0, 0))
    out.alpha_composite(ours, (img.width + 8, 0))
    out.save(os.path.join(docs, "reference-vanilla.png"))


def write_before_after(before_path, table, docs):
    before = measure(before_path)
    cell_before = socket_composite(4, load(before_path))
    cell_after = socket_composite(4, load(BASE))
    label(cell_before, "before: north gap {:.2f}".format(before["north"]["gap"]))
    label(cell_after, "after: north gap {:.2f}".format(table["north"]["gap"]))
    pair = Image.new("RGBA", (cell_before.width * 2 + 8, cell_before.height),
                     (28, 30, 26, 255))
    pair.alpha_composite(cell_before, (0, 0))
    pair.alpha_composite(cell_after, (cell_before.width + 8, 0))
    pair = pair.resize((pair.width * 2, pair.height * 2), Image.NEAREST)
    pair.save(os.path.join(docs, "north-before-after-2x.png"))


# --------------------------------------------------------------------- main ----
def main(argv):
    def opt(flag, default=None):
        return argv[argv.index(flag) + 1] if flag in argv else default

    before = opt("--before")
    docs = opt("--docs", DOCS)
    table = measure()
    ok = print_table(table)
    if "--check" in argv:
        return 0 if ok else 1

    os.makedirs(docs, exist_ok=True)
    write_overview(table, docs)
    write_sides(table, docs)
    write_variants(docs)
    write_vanilla_reference(table, docs)
    if before:
        write_before_after(before, table, docs)
    with open(os.path.join(docs, "gaps.json"), "w") as fh:
        json.dump({
            "pipe_reach": pipe_reach(),
            "max_gap": MAX_GAP,
            "measured_at": "64 px/tile, +-0.5 tile band around each pipe axis",
            "sides": table,
            "before": measure(before) if before else None,
        }, fh, indent=2)
    print("wrote", docs)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
