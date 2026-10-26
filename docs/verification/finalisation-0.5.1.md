# 0.5.1 finalisation: the five improvement passes verified together

The 0.5.1 work arrived as five separate passes — item ordering, player-facing text,
cannon art, pipe ports, firing sound — and each one was verified on its own card.
This pass checks the thing none of them could: that the combined tree is what ships,
that every player-facing change is in `changelog.txt`, and that the numbers the other
cards quoted can be reproduced from the committed files.

It also settles the one open question the art pass left behind (the 64 px icon).

## 1. The merged tree loads and runs

```
git archive HEAD | tar -x -C <run>/mods/lilys-melta      # exactly the commit, no probes
Factorio.exe --config <run>/config.ini --mod-directory <run>/mods --create <run>/save.zip
Factorio.exe --config <run>/config.ini --mod-directory <run>/mods \
             --benchmark <run>/save.zip --benchmark-ticks 300
```

* `--create`: `Loading mod lilys-melta 0.5.0 (data.lua)` and `(data-updates.lua)`, exit 0,
  no error and no warning line in `factorio-current.log` (base only, no sibling probe mods).
* `--benchmark`, 300 ticks: `Checksum for script __lilys-melta__/control.lua: 277269224`,
  no Lua errors, 0.188 ms average update (0.085-1.143 ms). The runtime half of the mod —
  the pulse clock, the beam, the fluid logic — runs on the same tree that carries the
  new prototypes, locale, art and sound.

Not repeated here, because the individual cards already did it on this same content and
the evidence is committed: the GUI atlas build and in-game screenshots (`art/`,
`in-game-connectors/`), the crafting-menu row (`item-order/`), the tooltips (`locale/`).

## 2. Numbers re-measured from the committed files

| claim | source card | re-measured here |
|---|---|---|
| head palette in the vanilla register | art rework | `python graphics/_blender/palette_vs_vanilla.py graphics/entity/melta-turret` → head mean **79.2**, p50 63.0, p90 176.7, warm **+27.4**, white 0.00 %; vanilla gun head mean 75.0, p50 60.2, p90 160.1, warm +27.3 |
| pipe ports sized and placed like a fitting | pipe ports | `python tools/check_pipe_connections.py --check` → width 1.03-1.08 (pipe 1.00-1.11, vanilla cover 0.80), inboard 0.35-0.52 from centre (was 0.91-1.09), seam 0.00, "OK ... at least as wide as the pipe" |
| blanked-off ports, not hollow collars | pipe ports | `python graphics/_blender/pipe_join.py --check` → OK, every bare port blanked |
| icon/technology/thumbnail files and their prototype references | art rework | `python graphics/_blender/check_icons.py .` → ALL CHECKS PASSED |
| the item sorts next to the turrets, not at the end of the combat tab | item order | `--dump-data` on this commit + `python docs/verification/harness/melta-itemorder/check_order.py <dump> melta-turret` → subgroup `turret`, 8 entries, `flamethrower-turret <- melta-turret -> artillery-turret`, PASS under both the documented (bracket text ignored) and plain-string comparison; exactly one item prototype places the entity |

## 3. Changelog

`changelog.txt` carried the Graphics and Balance half of 0.5.1 but not the other three
passes, and the item-order card deliberately left the file alone because a sibling had it
open. Added under 0.5.1: `Changes` (item ordering, the text rewrite) and `Fixed` (the pipe
ports, with the engine measurement that makes a 1-tile-inward connection point impossible).
Sound and beam changes already had their 0.5.0 entries.

`info.json` was still 0.5.0 while the changelog's top entry said 0.5.1; the version is
bumped to match, so the tree is self-consistent.

## 4. The 64 px icon: camera study, and why it is a model problem

The art pass reported that the icon "still reads as a rounded pod more than a turret with
a projecting barrel" and called it a framing question. It is not: five cameras were
rendered from the committed model and fitted through the shipped assembler.

| candidate | file | 64 px coverage | read |
|---|---|---|---|
| **shipped** 34 deg pitch, direction 40 | `art/icon-camera-study-34deg.png` (cell 1) | 2441 px = 59.6 % | best of the five: broad body, barrel running diagonally out to the lower left, bright muzzle |
| 34 deg, direction 8 | same sheet, cell 2 | 67.0 % | barrel points up-right and merges into the body |
| 34 deg, direction 16 | same sheet, cell 3 | 64.4 % | muzzle reads as a lit strip flush on the right edge |
| 34 deg, direction 24 | same sheet, cell 4 | 65.1 % | best of the alternatives, still fused to the body |
| 55 deg pitch, direction 40 / 24 | `art/icon-camera-study-55deg.png` | 1958 px = 47.8 % | taller and narrower, barrel more foreshortened, large dead margins |

The 34 deg / direction 40 camera the art pass chose is the strongest of the five, so the
shipped icon stays. The limitation is proportional, not photographic: the hull is ~3.1
tiles across while the cannon reaches 1.51 tiles from the pivot, so the weapon is a
minority of the silhouette, and at the 32 px GUI size
(`art/icon-preview-sheet.png`, second row) it collapses into a warm oval next to the
vanilla turrets, which stay legible because their silhouettes are dominated by their
weapons. Fixing that means changing the icon's shape budget — a larger muzzle/receiver in
the icon render, or an icon-specific simplification pass — not moving the camera. Left as
a follow-up card rather than half-done here.

All three candidate renders are one connected alpha component (checked), so the "detached
bits" a first visual read reports are an artefact of nearest-neighbour upscaling, not stray
pixels in the file.

`graphics/_blender/iconraw/icon-040.png` was still the *pre-rework* render, so the icons
could not actually be re-derived from the repo. It is re-rendered from the committed model
(direction 40, 34 deg, 1024 px, 56 samples) and the derivation now reproduces the shipped
files byte for byte:

```
python assemble_icons.py graphics/_blender/iconraw 40 --out <elsewhere>
# melta-turret.png, melta-turret-technology.png, thumbnail.png: 3/3 md5 identical
```

