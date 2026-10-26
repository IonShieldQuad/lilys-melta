# In-game check of the pipe joins

17 screenshots from one real Factorio launch (Steam build 87750, 2.1.23), taken with
`game.take_screenshot` by the `melta-pipes` harness in `docs/verification/harness/`.
Nothing here is a mock-up or a sprite composite -- these are the game's own frames.

The 0.5.1 frames are kept beside the current ones (`*-0.5.1.jpg`) so the change can be
seen rather than trusted: 0.5.1 drew a ringed port/cap on **every** side, connected or
not, and its art sat at the connection point while the hull's silhouette starts further
out -- so each unused side showed a plate floating half a tile off the deck. The current
build draws the space-age stub **only** where a pipe actually arrives.

## Scene

The harness builds it on a concrete pad at y = 200, far from the crash site:

* **REF / `00-vanilla-ref*`** (-16, 200) -- a vanilla `assembling-machine-2` with a pipe on
  all four sides. Same ±1.2 collision box and the same `pipe_picture` mechanism, so it is
  the yardstick for what a vanilla join looks like: its pipe flange stops ~10-15 px short
  of the hull at 4x zoom. The mod's joins are compared against it, not against a mental
  image.
* **A** (0.5, 200.5) -- the melta with a pipe on **all four sides**, each run continuing
  three tiles out into a storage tank, so every port is a live fluid neighbour.
* **B** (16.5, 200.5) -- a second melta plumbed on **one** side only: the other three
  ports are bare, which is the "an unused port must draw nothing" case.
* **C** (y = 214) -- the four junction shapes on their own (straight run, L corner, T
  junction, 4-way cross) plus a two-tile run that dead-ends in open ground.

## What each file shows

| file | shows |
|---|---|
| `00-vanilla-ref.jpg` | the vanilla assembler, zoom 2.6 -- the reference join |
| `00-vanilla-ref-north.jpg` | the same at 4x: the small seam a vanilla `pipe_picture` leaves |
| `01-overview.jpg` | whole pad, zoom 0.9: the turret, its four tanks, the shapes |
| `02-melta-four-way.jpg` | the turret with one pipe per side, zoom 2.6 (`-0.5.1` = before) |
| `03-join-north.jpg`, `04-join-east.jpg`, `12-join-south.jpg`, `13-join-west.jpg` | each join at zoom 4.0 |
| `05-capped-ports.jpg`, `14-capped-port-north.jpg` | turret B: the three unconnected ports are bare hull (`-0.5.1` = before: floating caps) |
| `06-shapes.jpg` | the junction shapes, zoom 1.6 |
| `07-straight.jpg`, `08-corner.jpg`, `09-t-junction.jpg`, `10-cross.jpg`, `11-dead-end.jpg` | one junction each, zoom 3.2 |
| `15-overview-close.jpg` | the turret and its four joins, zoom 1.8 |

Result: every join reads as a pipe entering hardware that belongs to the turret, with no
bare floor in between and nothing drawn on a side that has no pipe; the straight / L / T
/ cross junctions meet cleanly; the dead end is capped, not an open hole.

## How the run was made (and the traps)

```bash
W=C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest_shot   # scratch write-data
# 0. stage the tree into E:/hermes-melta-env/mods/lilys-melta (never the live mod dir)
# 1. build the scene into a save (the harness builds it in on_init, which --create runs)
Factorio.exe --config E:/hermes-melta-env/config.ini \
             --mod-directory E:/hermes-melta-env/mods --create E:/hermes-melta-env/shot2.zip
# 2. one GUI run: it loads that save, the harness fires the screenshot schedule
SteamAppId=427520 SteamGameId=427520 Factorio.exe \
             --config E:/hermes-melta-env/config.ini \
             --mod-directory E:/hermes-melta-env/mods --load-game E:/hermes-melta-env/shot2.zip
```

1. **A minimal `config.ini` is not enough for a GUI run.** With only `[path]` the game
   dies at startup with `Error Util.cpp:81: Value must be a dictionary in property tree
   at ROOT.sound`. Copy the player's real config and override `write-data=` with the
   scratch path instead of writing a two-line file.
2. **The game pauses when its window is not focused**, so the screenshot schedule stops
   dead mid-list: the log stops, no new frames appear, and the process still reports
   "Responding". Bring the window to the front and send a click or `<Tab>`; the schedule
   resumes at the next scheduled tick. A run that looks hung for minutes is usually this.
3. **Sprite loading dominates the clock** -- 8808 bitmaps, 3-7 min on this box, longer
   while another Factorio instance is running. `--create` is ~10 s; the GUI load is the
   slow part, so put everything you need to see into one save rather than iterating.
4. The probe needs `space-age` enabled in its `mod-list.json`: the stub art comes from
   `__space-age__/prototypes/entity/electromagnetic-plant-pictures`. A base-only install
   deliberately falls back to vanilla `pipecoverspictures()` covers.

The harness writes to `<write>/script-output/pipes/*.png` (1920x1080); the JPEGs here are
those frames, downscaled to 1280x720 at q88.
