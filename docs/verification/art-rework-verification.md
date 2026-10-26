# Art rework: melta turret model, muzzle and palette (0.5.1)

The 0.5.0 cannon read as a dark grey energy turret with a flat pale plate capping the
barrel. This pass rebuilds the gun in `graphics/_blender/melta_render.py` so it reads
as a combustion weapon in the vanilla palette, re-renders the 64-direction sheets from
it, and refits the tone curve to the new model. Everything below is measured on the
files in this commit; the numbers are reproducible with the commands in each section.

Evidence images live in [`art/`](art/):

| image | what it shows |
|---|---|
| `art/sheet-before-after-4dir.png` | four bearings of the head sheet, HEAD art above the reworked art, native size |
| `art/sheet-before-after-muzzle.png` | 2x muzzle crops for the same four bearings: pale plate vs vented projector |
| `art/ingame-before-after-close.png` | in-game 2.6x close-up, before / after |
| `art/ingame-before-after-pairs.png` | in-game 1x, melta row next to the vanilla gun turret, before / after |
| `art/ingame-vs-vanilla-row.png` | in-game 1.6x of the vanilla turret row, same scene |

## What changed on the model

- **Muzzle.** The projector mouth is a fat cylinder (`gun_proj_body`, 0.345 tiles
  radius, 0.24 long) with a ring of six radial vents over a hollow bore
  (`gun_bore_tube`, open-ended cylinder, dark floor disc behind it) and a hot-metal
  lip (`gun_proj_lip`, emissive). The old flare plus wide flat mouth — the "white
  plate" — is gone. Nothing caps the barrel any more: the brightest surface at the
  muzzle is a 0.052-tile lip and the vent bores.
- **On-gun hardware**, all sized for the sprite (1 tile = 32 art px, so >= 0.4 tiles
  across survives the downsample): brass compressor drum with fins and an intake, cast
  turbine housing with ribbed bands, hub and exhaust stack, a banded brass pressure
  tank with end caps, and four copper hard lines (tank → breech, compressor → tank,
  cross-line over the receiver, tank → rear) with cast clamps. The three big masses
  each get their own silhouette and their own material so they read at 1x zoom.
- **Palette.** Mid-value warm gunmetal body, near-black recesses, brass/copper on
  everything that carries fluid, and a dedicated `lamp` emissive used only on the vent
  bores, the muzzle lip, the two pressure gauges and the sight lens. The big glow
  collar between the heat rings stays on the dim material on purpose — lifting it was
  what made the previous version read as an energy weapon.
- **Lighting rig.** This Blender's Cycles ignores lamp energy, so the model is lit by
  three emissive softboxes. The icon camera sees 4.2 tiles where the sheet camera sees
  4.0, which is how a softbox came to be photographed as a flat white triangle in the
  shipped icon; the plates are hidden from camera rays now and `check_rig_in_frame()`
  fails loudly if one would enter any frame.

## Measurements

Palette against vanilla, from `graphics/_blender/palette_vs_vanilla.py`
(`python graphics/_blender/palette_vs_vanilla.py graphics/entity/melta-turret`):

| sprite | mean | p10 | p50 | p75 | p90 | warm (r-b) | dark <16 | pure white |
|---|---|---|---|---|---|---|---|---|
| melta head, before (HEAD) | 56 | 8 | 32 | 77 | 145 | +12 | 25% | 0.00% |
| melta head, after (64 frames) | 79 | 10 | 63 | 116 | 177 | +27 | 14% | 0.00% |
| melta hull, before | 51 | 9 | 34 | 70 | 113 | +12 | 19% | 0.00% |
| melta hull, after | 61 | 11 | 55 | 88 | 118 | +16 | 15% | 0.00% |
| vanilla gun head | 75 | 15 | 60 | 105 | 160 | +27 | 11% | 0.49% |
| vanilla gun base | 46 | 1 | 25 | 63 | 122 | +6 | 38% | 1.20% |
| vanilla laser base | 63 | 6 | 39 | 85 | 165 | +12 | 21% | 0.94% |

Reading: the head moved from "darker and cooler than vanilla" (mean 56, warm +12) to
vanilla's own register (mean 79 vs 75, warm +27 vs +27), and the hull from 51 to 61,
which is where the vanilla turret bases sit (flamethrower hull measures 56-60 per
rotation, laser base 63). Pure white is 0.00% — the accent is orange, not white, so
the muzzle cannot read as a pale plate again.

Geometry and anchoring gates, all re-run on the reworked sheets:

| gate | result |
|---|---|
| `graphics/_blender/check_sheets.py graphics/entity/melta-turret` | 8 sheets of 256x2048, 64 directions, no clipping, centroid radius std 1.05 px, directions walk one closed loop (step mean 1.77 px, worst 2.11 px, closure 1.56 px) |
| `graphics/_blender/check_beam_anchor.py` | PASS: beam start pixel opaque in 64/64 directions, min silhouette margin 3 px, 0.04-0.32 tiles behind the drawn mouth |
| `graphics/_blender/pipe_join.py --check` | PASS on all four sides, port meets the pipe, no bare ground, every bare port blanked off |
| `tools/check_pipe_connections.py --check` | PASS: connector 1.03-1.08 tiles wide against a 1.00-1.11 pipe, 0.35-0.52 tiles from the centre, seam 0.00 |
| `graphics/_blender/check_icons.py` | ALL CHECKS PASSED (icon 64 + packed mips, technology 256 + packed mips, thumbnails, prototype references) |

Reproducibility: re-running the documented full render and assemble command

```bash
blender -b --factory-startup -P melta_render.py -- --out <raw> --dirs all --res 512 --samples 40
python assemble.py <raw> <out>
```

reproduced the previously shipped 9 sheet files byte for byte (md5 identical on all
nine), i.e. the sheets in this commit are exactly what the committed model emits.
A partial run (`--dirs 0,32`) is *not* comparable: Cycles seeds per frame index, so a
subset render produces different samples.

## In-game pass

`docs/verification/harness/run_look.py <run dir> [--tree <dir>]` stages an isolated
write directory, `--create`s a scene (four melta turrets aimed north/east/south/west
plus the vanilla gun, laser and flamethrower turrets on one stone pad) and then loads
it in a GUI Factorio, which is the only place the sprite atlas is built. Two passes
were run: `--tree <git archive of HEAD>` for the before shots and the working tree for
the after shots. Both passes photograph the turrets dry (no fuel): a fuelled turret
fires its beam at the test dummies, and the beam covers the very art that is being
judged.

Both passes completed with `MELTA LOOK DONE` and 5 screenshots each, no errors in the
log, atlas built at 4096 with `[mipmap, linear-magnification]` bitmaps (unchanged
settings — `mipmap_count = 4`, `scale = 0.5`, `shift = {0, 0}` and the same file names
as before, so no prototype path changed).

## What this does not claim

- "Reads as vanilla quality" is a judgement, not a measurement. The palette, the
  silhouette loop, the beam anchor and the pipe joins are all measured and pass; the
  final call is Lily's to make with the turret in a real base.
- The 64 px icon is re-rendered from the same model (softbox artefact gone, values at
  p10/p50/p90 11/72/190 against vanilla's 19/80/175), but at 64 px it still reads as a
  rounded pod more than as a turret with a projecting barrel — the 34 deg icon camera
  sees a lot of hull and little barrel. That is a framing question for a separate pass,
  not something this one fixed.

## Re-running the evidence

```bash
python docs/verification/harness/run_look.py C:/tmp/look-before --tree <old tree>
python docs/verification/harness/run_look.py C:/tmp/look-after
python docs/verification/harness/build_art_evidence.py   # writes docs/verification/art/
```
