# In-game verification of the 0.4.0 melta rework

> **0.5.1 icon shape budget:** the 64/32 px item icon read as a rounded pod because the
> 3.1-tile hull left the 1.5-tile cannon a minority of the silhouette. The icon pass now
> scales the gun root in the icon render only and gives it a white-hot muzzle; every shape
> metric lands inside the vanilla turret family (protrusion 15.5 → 23.1 %, reach 1.60 → 2.03,
> neck 0.69 → 0.46) and the crafting-menu row was re-photographed. Report:
> [`icon-read-0.5.1.md`](icon-read-0.5.1.md); evidence in `art/icon-*.png`, measurement in
> `graphics/_blender/icon_read.py`, sheet builder
> `harness/build_icon_read_sheet.py`.

> **0.5.1 finalisation:** the five 0.5.1 passes (item order, text, cannon art, pipe ports,
> sound) were checked together on the merged commit — headless load + 300-tick run on the
> exact tree, the palette/port/icon gates re-run from the committed files, the changelog
> completed, and the icon camera question settled (five cameras rendered; the shipped one
> is the best of them, and the icon's weakness is proportional, not photographic). Report:
> [`finalisation-0.5.1.md`](finalisation-0.5.1.md); evidence in `art/icon-*.png`.

> **Art rework (0.5.1, pre-release):** the cannon model, muzzle and palette were
> rebuilt toward vanilla. Report:
> [`art-rework-verification.md`](art-rework-verification.md); evidence in `art/`,
> harness in `harness/run_look.py` + `harness/melta-look` + `harness/build_art_evidence.py`.

> **Later pass (0.5.0, tree `f5aa887`):** the five improvement cards were re-verified
> together — pipes, range/quality/rotation, damage description, beam, asteroids — in one
> scene with space-age and quality loaded at once. Report:
> [`melta-improvements-verification.md`](melta-improvements-verification.md); evidence in
> `in-game-combined/`, harness in `harness/melta-combined` + `harness/{setup_combined_run.sh,
> run_combined.py,hover_combined.py}`.

> **Connector rework (post-0.5.0):** the pipe ports were re-sized and moved inboard. That
> pass is measured rather than described — `tools/check_pipe_connections.py` reads the
> prototype's `pipe_connections`, measures the sprites against vanilla's own pipe cover and
> writes an annotated debug PNG per rotation; the numbers, the engine connectivity probe and
> the in-game shots are in [`../pipe-connections/README.md`](../pipe-connections/README.md)
> and `in-game-connectors/`. Harness: `harness/melta-connprobe` +
> `harness/{run_connprobe.sh,run_conngui.py}`.

Everything below in this folder was produced by one real Factorio launch plus three headless
runs on 2026-10-25 against the tree at `97a327b`. Nothing here is a mock-up: the
screenshots are `game.take_screenshot` output from the running game, and the numbers in
`melta-end-to-end-verification.md` are measured from those files or from the logs in
`logs/`.

## What was run

| run | mode | mods | what it did |
|---|---|---|---|
| visual | normal GUI launch through Steam, `--load-game` | base + lilys-melta + `melta-verify` | builds the scene on a concrete pad (melta + 4 pipes + the three vanilla turrets + a static dummy target), walks the turret through N/E/S/W and screenshots the swing and the shot; also puts the four item icons on the ground |
| regression | headless `--load-game --until-tick` | base + lilys-melta + `melta-regress` | feed, kill, `rotate()`, clone-as-paste, deconstruction order/cancel |
| persistence | headless `--create` then `--load-game` | base + lilys-melta + `melta-persist` | writes a map that already contains a fuelled, east-facing turret, then reloads it and reports what survived |
| determinism | headless `--benchmark --benchmark-consistency` | base + lilys-melta + `melta-regress` | 600 ticks, two passes, checksum comparison |

Both headless and GUI runs used an isolated write directory
(`--config …/config.ini` with `[path] write-data=…`), so her own saves, blueprint
storage and `factorio-current.log` were not touched.

The three probe mods are in `harness/`. They are never shipped — copy them into a mod
directory next to `lilys-melta` if you want to re-run any of it.

### Why the launch goes through Steam

This install is the Steam build. Started any other way it prints
`Steam requires game restart, restarting...` and exits, and every headless mode
(`--create`, `--benchmark`, `--load-game --until-tick`) logs "Running in headless mode"
and never initialises the renderer — `game.take_screenshot` returns `true` and writes
nothing. So the visual pass needs a normal Steam launch (the launch dialog accepts the
`--config/--mod-directory/--load-game` arguments).

## What is in here

`melta-end-to-end-verification.md` — the report: every checklist item as PASS/FAIL with
the evidence, the files touched, and the open issues.

`in-game/` — 13 screenshots, 1280x720 JPEG q92 (the 1920x1080 PNG originals are 3-5 MB
each and do not belong in a repo):

| file | shows |
|---|---|
| `01-scale-row.jpg` | melta next to gun, flamethrower and laser turrets, same zoom — the scale comparison |
| `02-melta-closeup.jpg` | the turret at 2x zoom, rust/grime/brass read |
| `03-pipes-overview.jpg` | the turret with its four pipes, mid zoom |
| `04-icon-row.jpg` | melta / gun / laser / flamethrower item icons lying on the ground, drawn by the game |
| `05-beam-north.jpg`, `06-beam-north-b.jpg` | beam up, turret already aligned north |
| `07-windup-east.jpg` | mid-swing to the east: charge glow, no beam |
| `08-beam-east.jpg` | beam east, on target |
| `09-windup-south.jpg`, `10-beam-south.jpg` | same pair pointing south |
| `11-windup-west.jpg`, `12-beam-west.jpg` | same pair pointing west |
| `13-gui.jpg` | GUI shown (quickbar with the melta item in slot 1) |

`detail/` — 1:1 crops, PNG, for the things a downscale would hide:

* `pipe-join-1to1.png` — the four pipe joins at 64 px/tile
* `muzzle-north-1to1.png` — where the lance meets the barrel
* `item-icons-1to1.png` — the item icons at their in-world size

`icon-sheet-native.png`, `icon-sheet-6x-nearest.png` — our 64 px and 32 px icon next to
vanilla gun and laser turret icons on the game's slot background, native size and 6x
nearest-neighbour.

`logs/` — the evidence lines out of each run's `factorio-current.log`
(`gui-run.txt` keeps the mod-load, sound-load and atlas lines too, which is what proves
the sprite atlas and the sound files were actually accepted).
