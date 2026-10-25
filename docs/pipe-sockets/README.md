# Pipe sockets — how these images were made

These are **not live in-game screenshots**. The Factorio installed on this machine is
the Steam build and has no standalone executable: outside Steam it refuses to start a
graphics run ("Steam requires game restart"), and every headless mode
(`--create`, `--benchmark`, `--until-tick`) logs "Running in headless mode" and never
touches the renderer, so `game.take_screenshot` produces nothing. The live visual pass
is still worth doing from a normal Steam launch — that is what the in-game verification
card is for.

What *is* evidence here:

- the images are assembled from the game's own sprite files (`melta-turret-base.png`,
  `__base__`'s pipe sprites and `pipe-cover-*.png`) at 64 px/tile, which is Factorio's
  zoom 2.0, so they are pixel-exact with the game's own art;
- the positions are the ones the engine resolved at runtime in a headless probe, not
  guesses: turret centre on a tile centre, pipes 2.0 tiles out (the only legal tile),
  covers at `C.pipe_reach = 1.12` (`pipe_sockets.py` reads that number out of
  `constants.lua`, so the images cannot drift from the prototype);
- the draw order matches the prototypes: head `medium` < base `high` < pipes and
  covers `extra-high`.

| file | what it shows |
|---|---|
| `overview.png` | all four pipes with their sockets, zoom 2.0, head pointing north |
| `north.png` … `west.png` | one side each, 4x4 tiles, with the measured gap printed on it |
| `*-2x.png` | the same crops blown up 2x with nearest-neighbour (no resampling blur) |
| `variants.png` | why 1.12: sockets at 1.05 sink into the hull, 1.20 float off it, and the 0.3.0 look (no covers) is the "pipe runs over the turret" state |
| `reference-vanilla.png` | vanilla `assembling-machine-2` + a pipe, same framing and same measurement (north gap 0.24 tiles) |
| `north-before-after-2x.png` | the hull de-squash: north gap 0.41 → 0.14 tiles |
| `gaps.json` | the measured table, so the numbers in `DESIGN.md` can be checked rather than trusted |

The four side views have **no head**: at direction 0 the gun points north and its muzzle
reaches 1.51 tiles out, i.e. the head is exactly what covers the seam on the north side.
`overview.png` keeps the head so the machine is recognisable.

Functional side (proved headlessly, not visually): a pipe on each of the four sides is
built 2.0 tiles out, the fluid box reports that pipe as its connection target and fluid
neighbour, a filled pipe hands 66.7 of its 100 units to the turret on the next tick, and
the port refills from empty. Rotating the turret leaves the four connection positions
unchanged (they are symmetric), so a socket cannot slide off its pipe. This change only
resampled the hull PNG — no prototype moved — and `--create` plus `--benchmark` still
run clean.

## Measured join

Distance from the turret centre to the hull's silhouette vs to the pipe's near edge,
measured in a ±0.5 tile band around each pipe axis (the slot the pipe has to meet):

| side | hull | pipe near edge | gap |
|---|---|---|---|
| north | 1.38 | 1.50 | **+0.12** |
| east | 1.64 | 1.50 | −0.14 |
| south | 1.28 | 1.19 | −0.09 |
| west | 1.53 | 1.50 | −0.03 |

Negative = the pipe's art overlaps the hull. North and south used to leave +0.42 and
+0.17; they came down because the hull is now deeper in Y, not because a port moved —
`C.pipe_reach` is still 1.12 and the covers are unchanged.

The hull was the shallow part: it is rendered through a 51° pitched camera, so the round
footprint was drawn 3.05 tiles wide but ~2.1 tall. `assemble.py` now de-squashes the
**base layer only** in Y (`BASE_DESQUASH_Y = 1.26`) about the frame centre, which keeps
`shift = {0, 0}` and leaves the 64 head frames untouched, so the pivot cannot move —
`check_sheets.py` still reports a centroid radius std of 2.4 px, i.e. no wobble.

## Reproducing

```bash
# measure only; exits 1 if any side is more than 0.22 tiles off its pipe
python graphics/_blender/pipe_sockets.py --check

# measure + redraw everything in this folder (needs base's sprites from the install)
python graphics/_blender/pipe_sockets.py --before <old melta-turret-base.png>
```

`FACTORIO_DATA` overrides the game install path. The vanilla number in
`reference-vanilla.png` comes from the same measurement code, so "0.14 is tighter than
vanilla's 0.24" compares like with like.
