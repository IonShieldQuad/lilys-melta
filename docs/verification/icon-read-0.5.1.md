# The 64/32 px melta icon: giving the weapon a share of the silhouette

The 0.5.1 finalisation measured the item icon and found a real gap: at the 32 px size the
crafting menu draws, the melta collapsed into a warm brown oval while the vanilla gun,
flamethrower and rocket turret icons next to it stayed readable. Five cameras were rendered
from the same model in that pass and the shipped one (34° pitch, direction 40) was the best
of them, so the cause was proportional, not photographic: a 3.1-tile emplacement with a
1.51-tile cannon leaves the weapon a minority of the silhouette.

This pass changes the icon's **shape budget** instead of the camera. Nothing in world was
re-rendered: `git show --stat` on the commit touches `graphics/icons/melta-turret.png`, the
icon pipeline and the evidence only — `graphics/entity/melta-turret/` (64 directions), the
entity size, `collision_box`, `scale`, mipmaps and the beam anchors are byte-identical.

## 1. "Reads as a turret" is now measured

`graphics/_blender/icon_read.py` prints, for any vanilla-shaped icon file, at 64 px and at
the authored 32 px mip:

| metric | what it means | the turret it separates |
|---|---|---|
| coverage | silhouette area / cell | pod vs. gappy weapon shape |
| elongation | major/minor axis of the mask | a projecting weapon vs. a disc |
| reach | max radius / median radius | how far anything sticks out |
| protrusion % | mask beyond 1.3x the median radius | how much of the shape IS the weapon |
| neck | thickness of the outer thirds / the middle third | a thin barrel on a fat body vs. one lump |
| masses | big (>=5 % of the mask) shapes in a 3-level luma quantisation | "two or three big shapes" |
| white % | pixels at luma >= 200 | the focal element (vanilla's white-hot nozzle) |
| darklimb | body luma - limb luma | whether the weapon separates by value at all |

Calibrated on the five vanilla turret icons, the old melta icon sat outside the family on
exactly the axes that matter:

| icon (32 px) | reach | protrusion | neck | elongation | masses | white | darklimb |
|---|---|---|---|---|---|---|---|
| gun-turret | 1.75 | 21.4 % | 0.56 | 1.20 | 3 | 9.8 % | -94 |
| flamethrower-turret | 1.81 | 22.3 % | 0.52 | 1.26 | 4 | 13.7 % | -139 |
| laser-turret | 1.71 | 22.2 % | 0.94 | 1.24 | 5 | 19.9 % | -110 |
| artillery-turret | 2.53 | 24.3 % | 0.33 | 1.48 | 4 | 19.1 % | -84 |
| rocket-turret | 1.69 | 20.4 % | 0.72 | 1.22 | 3 | 6.9 % | -55 |
| **melta, 0.5.1 (before)** | **1.58** | **15.3 %** | **0.71** | **1.15** | 3 | **2.4 %** | **-7** |

The old icon was the least protruding, the most isotropic, and its barrel read only 7 luma
units brighter than its body — so at 32 px there was no edge to find the weapon by.

## 2. The shape budget: an icon-only gun scale

`render_icons.py --icon-gun-scale` multiplies the gun root about the pivot in the ICON render
only. The sheets call `melta_render.build_gun()` directly and never see the factor, and the
root is dropped in Z by exactly the amount that keeps the bore at `GUN_Z * GUN_SCALE`, so
the cannon grows about its axis instead of floating off the bearing. The frame widens with
the gun so nothing clips before the assembler fits the silhouette.

Screened at 512 px / 32 samples, all through the shipped assembler and tone fit, measured
at 64 px:

| gun scale | coverage | reach | protrusion | neck | elongation |
|---|---|---|---|---|---|
| 1.00 (shipped) | 59.6 % | 1.61 | 16.2 % | 0.68 | 1.17 |
| 1.25 | 58.3 % | 1.70 | 16.3 % | 0.59 | 1.22 |
| 1.50 | 52.4 % | 1.89 | 18.9 % | 0.48 | 1.34 |
| **1.75** | **50.2 %** | **2.04** | **23.5 %** | **0.46** | **1.52** |
| 2.00 | 49.6 % | 2.12 | 26.5 % | 0.52 | 1.73 |

1.75 is the smallest factor that lands reach, protrusion, neck and elongation inside the
vanilla band; 2.0 overshoots it (elongation 1.73 against vanilla's 1.20-1.53) and 1.5 leaves
the weapon at the bottom edge of the family. Renders of 1.5/1.6/1.7 were also compared at
32 px: they trade a little muzzle punch for a little more mount, and none of them measures
better than 1.75. The shipped icon (1024 px / 56 samples, detail pass and emissive boost on)
measures 50.7 % / 2.03 / 23.1 % / 0.46 / 1.52 in the same terms.

## 3. The focal element: done in the render, not in the tone curve

The first attempt at a focal point was a tone pass (`assemble_icons.hot_focal`: push the
hottest 7 % of the mask toward white). It measured fine and read badly — quantile matching
then re-normalised the rest of the image, the muzzle went pale cream instead of yellow-hot,
and the icon turned into a glowing blob.

`render_icons.py --icon-emit "<material>=<mult>[ :white]"` lifts the actual emissive
material in the icon render instead, so the muzzle lip and bore really are hot and keep
their hue and their 3D form. Measured on the final icon:

| icon pass | limb vs body (luma) | white % at 64 px |
|---|---|---|
| no boost | -38 | 8.8 % |
| hotmetal x3 (+lamp x2), orange | -44 | 8.9 % |
| **hotmetal 0.6-white x3, lamp 0.3-white x2** | **-50** | **7.7 %** |
| same, x6 / x3 | -47 | 8.7 % |

The white-blend, x3 version was the one that read as "muzzle like the flamer's nozzle" in a
side-by-side at 32 px; x6 bloomed and made the barrel one lit mass. No in-world material
changed: `melta_render.MATS` still ships its own strengths.

## 4. Detail budget at 32 px

`assemble_icons.py` gained an icon-only simplification that runs at the final 64 px, after
the tone fit: luma is split into a low-pass and a detail layer, and detail below a threshold
is flattened. Big edges survive; plate seams, rivets and vent slats merge into their plate.

| threshold | masses at 32 px | read |
|---|---|---|
| off | 6 | noisiest: speckled bands, no clean masses |
| 6 | 5 | marginal win |
| **10 (shipped)** | **5** | best 32 px read that still looks like sharp art |
| 14 | 5 | starts to smear the muzzle and the banding |
| 14 + sigma 2 | 4 | soft object with hard edges — processed-looking |

## 5. The result

Final numbers, from the committed `graphics/icons/melta-turret.png` (full table in
`art/icon-turret-read.txt`):

| | reach | protrusion | neck | elongation | masses | white | darklimb |
|---|---|---|---|---|---|---|---|
| before, 64 px | 1.60 | 15.5 % | 0.69 | 1.16 | 4 | 8.9 % | -21 |
| before, 32 px | 1.58 | 15.3 % | 0.71 | 1.15 | 3 | 2.4 % | -7 |
| **after, 64 px** | **2.03** | **23.1 %** | **0.46** | **1.52** | 4 | 7.7 % | **-50** |
| **after, 32 px** | **2.01** | **24.1 %** | **0.47** | **1.52** | 5 | 4.7 % | **-44** |

Every shape metric is now inside the vanilla turret family (protrusion 20-24 %, reach
1.7-2.5, neck 0.33-0.94, elongation 1.20-1.53). Palette stays in the icon band: mean 87.8,
8.0 % of pixels below luma 20 at 64 px (vanilla 85-99 and 9-11 %); the 32 px mip measures
mean 82.2 against vanilla's 85-98, i.e. at the bottom of the family but not outside it.

Evidence, all built from committed files:

* `art/icon-turret-read.png` — melta beside gun / flamethrower / laser / artillery / rocket
  at 64 px, at the authored 32 px mip, and both at true size on the GUI panel grey.
  Rebuild: `python docs/verification/harness/build_icon_read_sheet.py`.
* `art/icon-before-after-32.png` — the previous icon (from `7b352ff`) against the new one at
  64 px and 32 px, in the vanilla lineup.
* `art/icon-gui-crafting-after.png` — the real crafting menu, searched "turret", with the row
  at the melta and at 4x. Before, for comparison: `../item-order/01-crafting-search-turret.png`.
* `art/icon-gui-placed.jpg` — the turret placed in world from the same commit
  (`harness/run_look.py`, `look-melta`).

## 6. Gates

```
python graphics/_blender/check_icons.py .            -> ALL CHECKS PASSED
python graphics/_blender/icon_read.py --vanilla ...   -> table above
python assemble_icons.py graphics/_blender/iconraw 40 --out <elsewhere>
    melta-turret.png           acfa32f9b50c86ef745f5475eeae4d7a
    melta-turret-technology.png b7ba9d0c126354132a84e2d76109240a  (unchanged)
    thumbnail.png               83c9b7e468baecafc91e0c4f62cadb83  (unchanged)
    -> 3/3 md5 identical to the committed files
```

`iconraw/` now holds both renders the pipeline needs: `icon-040.png` is the icon shape budget
(gun x1.75, emissive boost) and `icon-040-ship.png` is the same rig at shipping proportions,
which is what the technology icon and the portal thumbnail are built from — at 256/512 px the
barrel was never the problem, and those two stay an honest portrait of the machine.

## 7. In the real game

Two GUI passes on `git archive HEAD` (isolated write-data, Steam launch, `max-texture-size`
4096 — the only place Factorio builds the sprite atlas):

* crafting menu: `harness/melta-itemorder/stage.sh official HEAD`, `--create`, then
  `run_gui.py <env> <out> plan-hover-turret.json`. The row reads gun, laser, artillery,
  flamethrower, melta, and the melta cell now shows a projecting barrel with a bright muzzle
  instead of the pod.
* placed turret: `harness/run_look.py <run> --tree <archive of HEAD>`, five shots
  (`look-wide`, `look-pairs`, `look-melta`, `look-vanilla`, `look-melta-close`), all clean:
  the in-world art is unchanged and still reads as the same machine as the sheets.

## 8. What this does not fix

The mount is still the weakest element. The melta is a flat 2x2 emplacement with the cannon
on a collar, while the vanilla gun and artillery icons sit on a tall visible base; at 32 px
ours is read as a weapon on a low pad, and a viewer who already knows the turret is what
fills in the base. Making the chassis read at 32 px means changing its shape in the icon
render too (a taller modeled mount), which is a model change, not an icon pass — worth a
card of its own if it bothers her in play.
