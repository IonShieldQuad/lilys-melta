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
  the pipe sheets and `pipe-cover-*.png`) at 64 px/tile, which is Factorio's zoom 2.0,
  so they are pixel-exact with the game's own art;
- the positions are the ones the engine resolved at runtime in a headless probe, not
  guesses: turret centre on a tile centre, pipes 2.0 tiles out (the only legal tile),
  covers at `C.pipe_reach = 1.12`;
- the draw order matches the prototypes: head `medium` < base `high` < pipes and
  covers `extra-high`.

| file | what it shows |
|---|---|
| `overview.png` | all four pipes with their sockets, zoom 2.0 |
| `north.png` … `west.png` | one side each, 4x4 tiles |
| `*-2x.png` | the same crops blown up 2x with nearest-neighbour (no resampling blur) |
| `variants.png` | why 1.12: sockets at 1.05 sink into the hull, 1.20 float off it, and the 0.3.0 look (no covers) is the "pipe runs over the turret" state |

Functional side (proved headlessly, not visually): a pipe on each of the four sides is
built 2.0 tiles out, the fluid box reports that pipe as its connection target and
fluid neighbour, a filled pipe hands 66.7 of its 100 units to the turret on the next
tick, and the port refills from empty. Rotating the turret leaves the four connection
positions unchanged (they are symmetric), so a socket cannot slide off its pipe.

Known residual: measured from the sprites, the hull's silhouette is 1.62 tiles out on
X but only 1.02-1.09 on Y (the render camera is pitched), so the north pipe leaves
0.42 tiles of ground and the south 0.17, while east overlaps the hull by 0.12 and west
is flush. Vanilla `assembling-machine-2` — same collision box, same pipe distance —
leaves 0.22 on its north side, so a deeper north/south silhouette is the fix; it is
tracked separately because it is a model change, not a plumbing one.
