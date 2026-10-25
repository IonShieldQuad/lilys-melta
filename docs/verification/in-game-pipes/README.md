# In-game check of the pipe joins

15 screenshots from one real Factorio launch (Steam build 87750, 2.1.23), taken with
`game.take_screenshot` by the `melta-pipes` harness in `docs/verification/harness/`.
Nothing here is a mock-up or a sprite composite -- these are the game's own frames.

## Scene

The harness builds it on a concrete pad at y = 200, far from the crash site:

* **A** (0.5, 200.5) -- the melta with a pipe on **all four sides**, each run continuing
  three tiles out into a storage tank, so every port is a live fluid neighbour.
* **B** (16.5, 200.5) -- a second melta plumbed on **one** side only: the other three
  ports are bare, which is the "unused port must look blanked off" case.
* **C** (y = 214) -- the four junction shapes on their own (straight run, L corner, T
  junction, 4-way cross) plus a two-tile run that dead-ends in open ground.

## What each file shows

| file | shows |
|---|---|
| `01-overview.jpg` | whole pad, zoom 0.9: the turret, its four tanks, the shapes |
| `02-melta-four-way.jpg` | the turret with one pipe per side, zoom 2.6 |
| `03-join-north.jpg`, `04-join-east.jpg`, `12-join-south.jpg`, `13-join-west.jpg` | each join at zoom 4.0 |
| `05-capped-ports.jpg`, `14-capped-port-north.jpg` | turret B: the three unconnected ports |
| `06-shapes.jpg` | the junction shapes, zoom 1.6 |
| `07-straight.jpg`, `08-corner.jpg`, `09-t-junction.jpg`, `10-cross.jpg`, `11-dead-end.jpg` | one junction each, zoom 3.2 |
| `15-overview-close.jpg` | the turret and its four joins, zoom 1.8 |

Result: every join reads as a pipe entering a metal socket that belongs to the turret,
with no bare floor in between; the bare ports show a bolted blanking plate; the straight
/ L / T / cross junctions meet cleanly; the dead end is capped, not an open hole.

## How the run was made (and why it is not a one-liner)

This install is the Steam build. Two traps, both worked around:

1. **Steam's URL launch truncates the argument string at the first `:`.** Passing
   `--config C:/...` through `steam://run/427520//...` reaches the game as
   `--config C:`, and the game then reads its config from `C:/` (see
   `Error GlobalContext.cpp:1272: C:\: Bad file format`). Percent-encoding the colon
   (`%3A`) does not survive either. The args have to be **colon-free relative paths**,
   which is why the environment sits at `E:\hermes-melta-env` and is passed as
   `--config ../../../../../../hermes-melta-env/config.ini` (working directory is
   `bin/x64`).
2. **A directly started `Factorio.exe` prints "Steam requires game restart" and exits.**
   A `steam_appid.txt` containing `427520` next to the executable makes it start
   normally (Steam API reports `API loaded no`, which is fine for a scratch profile).
   That file is **not** part of this repo and was removed after the run.

```bash
W=C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest_shot   # scratch env
# 1. build the scene into a save (no ticking in --create, so the harness builds in on_init)
Factorio.exe --config $W/config.ini --mod-directory $W/mods --create $W/shot2.zip
# 2. one GUI run: it loads that save, the harness fires the screenshot schedule
Factorio.exe --config $W/config.ini --mod-directory $W/mods --load-game $W/shot2.zip
```

The harness writes to `<write>/script-output/pipes/*.png` (1920x1080); the JPEGs here are
those frames, downscaled to 1280x720 at q88.
