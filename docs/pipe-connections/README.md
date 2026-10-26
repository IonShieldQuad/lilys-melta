# Pipe connectors — measured, not eyeballed

The turret's four fluid ports were reported twice as "clearly misaligned", so this
directory holds the two things that decide the question without a screenshot: the
numbers the sprites actually measure, and an annotated debug image per rotation.

## What was wrong

`tools/check_pipe_connections.py` on the art as it shipped in 0.5.0:

```
side   width  pipe   vanil  vs_van  inboard   mouth   pipe_N  overlap  seam  marker
north   0.64   1.11   0.80    0.80     0.96     1.95     1.52     0.43  0.00  ok
east    0.70   1.00   0.80    0.88     0.93     1.79     1.50     0.29  0.00  ok
south   0.64   1.11   0.80    0.80     0.91     1.69     1.19     0.50  0.00  ok
west    0.59   1.00   0.80    0.74     1.09     1.95     1.52     0.43  0.00  ok
```

* `width` — the connector's cross-axis width, tiles. It was **0.59–0.70 against a
  1.00–1.11 tile pipe**, so the pipe was visibly wider than the socket it plugged
  into, and narrower than vanilla's own `pipe-cover` sprite (0.80) — a nub beside
  the pipe, not a receiver.
* `inboard` — how far the art's inboard end sits from the turret centre. It was
  **0.91–1.09 tiles**, i.e. the whole fitting lived in the gap between the hull and
  the pipe instead of being mounted on the housing.
* `mouth` — 1.69–1.95 tiles out, against the pipe's near edge at 1.19–1.52: the
  collar was already overlapping the pipe end by up to half a tile, but because it
  was thin it read as a ring floating at the pipe's mouth.

The join itself was never broken (`seam` 0.00, `overlap` positive on all four
sides, all four are engine-connected — see below). The defect was **size and
placement**, which is exactly what an eye at zoom 0.6 cannot quantify.

## What changed

`pipe_port.py` now renders the fitting at `SCALE = 1.75`, **about its mouth**
instead of about the frame centre:

| | before | after |
|---|---|---|
| connector width | 0.59–0.70 | 1.03–1.08 (1.10–1.35x vanilla's cover) |
| inboard end | 0.91–1.09 | 0.35–0.52 (moved in 0.39–0.59) |
| mouth | 1.69–1.95 | 1.79–2.10 |
| seam | 0.00 | 0.00 |
| overlap | +0.29…+0.50 | +0.31…+0.66 |

Anchoring the scale on the mouth is what makes this legal: the mouth has to stay on
the pipe (the pipe's near edge is fixed by the turret's 1.2 collision box), so
scaling about the frame centre would drag the mouth inboard and open a gap. Grown
from the mouth, the geometry instead expands **back toward the turret**, which is
the "1.5x bigger and nearer the centre" the report asked for. The stated factor is
1.75 because 1.5 measured out at 1.24–1.47x on screen — the on-screen width of the
socket is what the eye compares with the pipe, and at 1.5 the socket still came out
narrower than the pipe it receives.

Frame grew 128 → 192 px (still 64 art px/tile, scale 0.5) so the larger fitting and
its baked shadow fit inside it; `prototypes/graphics.lua`, `assemble_port.py` and
`pipe_port.py` all carry the same number.

`C.pipe_reach` and the collision box are **unchanged** (1.12 / ±1.2). See below for
why they cannot move a full tile.

## The connection point cannot move 1 tile inward

The report also asked to move the connectors ~1 tile toward the centre. That was
tested against the engine, not guessed. `docs/verification/harness/melta-connprobe`
places the turret with a pipe 2.0 tiles out on each side (the nearest a 1-tile pipe
can sit), then reads `LuaEntity::get_fluid_box_neighbours` — the engine's own
connection graph — and the turret's buffer after filling a pipe:

| `C.pipe_reach` | neighbours | turret buffer after 60 ticks |
|---|---|---|
| 1.12 (current) | 4 / 4 | 97.0 fluid |
| 0.75 | 4 / 4 | 97.0 fluid |
| 0.50 | 2 / 4 | 0.0 |
| 0.20 | 0 / 4 | 0.0 |

The engine links a pipe to a fluid box while the two connection points are within
about one tile; at `0.2` (the literal "1 tile inward") the turret is connected to
**nothing** and never receives fluid. A reach of 0.5 sits exactly on the boundary and
loses the north and west sides. So the connection point stays at 1.12 and the port
art carries the move instead — which is what is visible to the player anyway.

## Run the gate

```bash
python tools/check_pipe_connections.py            # measure + rewrite the debug PNGs
python tools/check_pipe_connections.py --check    # gate only, exit 1 on a bad side
python tools/check_pipe_connections.py --record   # also refresh baseline.json
FACTORIO_DATA=<install>/data ...                  # if the game is not at the usual path
```

It fails a side when: the computed connection pixel is not on the port's own art,
the port's mouth falls short of the pipe (`overlap < 0`), bare ground shows in the
join (`seam > 0`), or the connector is narrower than vanilla's `pipe-cover` sprite.
`baseline.json` is the 0.5.0 art, so every later run prints the change in width and
inboard position instead of asking anyone to remember it.

Outputs (rewritten each run, safe to inspect):

* `rot-{north,east,south,west}-2x.png` — the composite the engine draws at 64 px/tile
  (ground, hull, the real vanilla pipe sprite, port sprites), with a cyan cross on
  each computed connection point and a yellow box on each port sprite's frame.
* `capped-2x.png` — the same scene with no pipes, i.e. the `pipe_covers` variant.
* `connections.json` — every number above, per side.

## In-game pass

```bash
bash docs/verification/harness/run_connprobe.sh keep        # headless: connections + flow
python docs/verification/harness/run_conngui.py <run dir>   # GUI: atlas + screenshots
```

The GUI run is the only one that builds the sprite atlas, so it is also the check
for the 192 px sprite rects. It photographs `script-output/conn/`: a four-way
overview plus one close-up per join, over a drawn tile grid, the turret's collision
box (green, ±1.2) and the pipe distance (orange, radius 2.0) — the F4 debug overlays
are not scriptable, so the same information is drawn with `rendering.*`.
