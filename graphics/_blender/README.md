# Melta turret art pipeline

The turret has no hand-drawn sprites: the whole emplacement is modelled and
rendered procedurally, so it can be re-rendered at a different size, palette or
damage level by changing numbers instead of pixels.

    melta_render.py   builds the model in Blender, renders the hull once and the
                      cannon 64 times (5.625 deg apart)
    assemble.py       downsamples, applies the tone curve, bakes cast shadows,
                      writes the sheets the prototype loads
    render_icons.py   imports that same model and renders the ICON stills (one
                      direction at a time, supersampled, transparent)
    assemble_icons.py fits those stills into vanilla-shaped icon files, including
                      the packed mip chain, plus the mod thumbnail
    check_icons.py    offline stand-in for the atlas: sizes, packed mips, framing,
                      and that the prototypes point at these files
    pipe_sockets.py   measures the hull/pipe join on all four sides from the sprites,
                      and draws the docs/pipe-sockets views
    preview.py        (scratch tool) lays renders on a ground tile for review

## Requirements

* Blender **2.79b** (`D:/blender/blender_2.79b/blender.exe` on this box) — the
  script is written against the 2.79 Python 3.5 API (no f-strings, Mapping node
  has properties instead of sockets, `scene.cycles.film_transparent`).
* Pillow + numpy for `assemble.py` (any Python 3 will do).

## Render

```bash
blender -b --factory-startup -P melta_render.py -- \
    --out C:/tmp/melta/raw --dirs all --res 512 --samples 40
```

Native Windows paths are required for the Blender binary (MSYS paths are not
translated). ~11 s per direction on 8 CPU threads, so ~12 minutes for 64.

## Assemble

```bash
python assemble.py C:/tmp/melta/raw C:/tmp/melta/sheets
```

Copies nothing: point the second argument at a scratch dir, then copy
`sheets/graphics/entity/melta-turret/*.png` into the mod.

Two options matter for the hull:

```bash
# only the static base sprite (a hull-only change needs one 13 s render, not 64)
blender -b --factory-startup -P melta_render.py -- --out C:/tmp/melta/raw --dirs none
python assemble.py C:/tmp/melta/raw C:/tmp/melta/sheets --only base
```

`BASE_DESQUASH_Y` in `assemble.py` stretches the **base layer only** in Y about the
frame centre (1.26 at the time of writing): the camera's 51 deg pitch draws the round
hull squashed, and the pipe ports on its north/south walls need the silhouette deeper
than that. `shift` stays `{0, 0}` and the head sheets are never resampled, so the pivot
does not move. Measure the result, do not eyeball it:

```bash
python pipe_sockets.py --check        # gap table per side, exit 1 over 0.22 tiles
```

## Icons and thumbnail

The icon is a separate render of the whole machine, not a crop of a sheet frame
(a sheet frame is one 4-tile-wide square of a 64-direction loop; an icon wants the
whole turret fitted to 64 px, in a different colour register).

```bash
blender -b --factory-startup -P render_icons.py -- \
    --out C:/tmp/melta/iconraw --dirs 40 --res 1024 --samples 56 --tilt 34
python assemble_icons.py C:/tmp/melta/iconraw 40 --out "H:/Factorio Mods/lilys-melta"
python check_icons.py "H:/Factorio Mods/lilys-melta"
```

`render_icons.py` imports `melta_render` rather than copying it, so `GUN_SCALE`, the
materials and every part stay in one place: change the turret and the icon changes
with it. `iconraw/icon-040.png` is the render the shipped icons came from, kept so
the icons can be re-derived without Blender.

Three things are deliberately different from the sheets:

| | sheets | icon |
|---|---|---|
| camera pitch | 51 deg | **34 deg** -- at 51 the 2x2 emplacement only fills 63x44 of the 64 px box (a dead band); at 34 it fills 63x53 and the muzzle still reads |
| tone | fitted to the vanilla base *sprites* (mean ~50, half near black) | fitted to the vanilla *icons* (mean 85-97, ~10% near black) -- the sprite curve on an icon reads as a murky disc at 32 px |
| file shape | 256x2048 sheets | vanilla icon shape: 120x64 = 64 px icon + 32/16/8 mips packed right; 480x256 for the technology |

The packed mip layout is measured, not assumed: vanilla's own `gun-turret.png` (120x64)
and `technology/gun-turret.png` (480x256) are exactly base + halvings to the right, and
a downsample of their base square matches the packed regions at alpha correlation 1.000.
`icon_size` therefore stays 64 / 256 (the base square), never the file width.

No headless Factorio run builds sprites, so `check_icons.py` stands in for the atlas:
`icon_size` fits inside the image, each packed mip matches the base, no opaque pixel
touches the frame border (no clipping), the silhouette fills >= 85% of the cell (no
dead padding), and the prototypes reference these files rather than a vanilla icon.

## The contract with prototypes/graphics.lua

| item | value | consequence if it drifts |
|---|---|---|
| frame | 256 x 256 px | sheet rect errors, atlas failure |
| directions | 64, `line_length = 1`, `lines_per_file = 8` | frames in the wrong order |
| sheets | 8 files, 256 x 2048 each (power of two) | mipmap/atlas warnings |
| `scale` | 0.5 | 128 px on screen per frame = 4 tiles |
| `shift` | `{0, 0}` | pivot must be the frame centre; anything else wobbles |
| pivot | world origin, camera aimed at it | the gun must rotate about z = 0 |

Model space is **tiles**: 1 Blender unit = 1 tile, +Y is north (direction 0), and
the camera is pitched 51 deg from vertical (vertical squash 0.63) which is what
makes the turret sit on the ground the way vanilla turrets do.

The number the beam code needs lives here too, and it is **not** a distance in front
of the pivot. The head sprite is a pitched-camera image, so a muzzle that is 1.512
tiles forward *in the model* is drawn:

| facing | drawn distance from the pivot |
|---|---|
| north | 1.51 tiles |
| north-east / east | 1.63 / 1.61 tiles |
| south-east | 1.08 tiles |
| south | 0.39 tiles |

because the forward reach is foreshortened by cos(51°) on the screen's vertical axis
and the raised muzzle (barrel axis 0.722 tiles up) sits sin(51°) * 0.722 tiles further
"up" the screen, i.e. north. `control.lua` computes the per-direction point from
`C.muzzle_forward` (1.512), `C.muzzle_height` (0.722) and `C.camera_tilt_deg` (51);
`prototypes/entity.lua` uses `C.muzzle_forward` for `gun_barrel_length`.

Two scripts keep that honest — run them after any re-render:

```bash
D:/blender/blender_2.79b/blender.exe -b --factory-startup -P muzzle_marker.py
python check_beam_anchor.py
```

* `muzzle_marker.py` builds the same camera as `melta_render.py` and projects the
  model's own muzzle points (pivot / bore / front face / lip top) through Blender's
  camera for all 64 directions. It prints where each one lands in the frame; the
  formula in `control.lua` agrees with it to **< 0.001 tiles (0.02 art px)**.
* `check_beam_anchor.py` takes that beam-start point for each of the 64 directions,
  projects it onto the shipped sheet and asserts the pixel is on the gun, sits at the
  mouth (at most a hair in front of the silhouette's front edge, never deeper than
  0.75 tiles inside it) and is never at the pivot. It passes 64/64.

## Blender 2.79 quirks that cost time (do not "fix" them back)

* Sun lamps: this build ignores `lamp.energy` for Cycles (energy 0 and 8 render
  identically), so the directional key light cannot be trusted to shape the model.
  Contrast is therefore made deterministic: shader-level Ambient Occlusion in the
  material, plus the tone curve in `assemble.py`. If you move to Blender 3.x/4.x,
  delete the AO node and drive the look from the lights again.
* `scene.render.layers[0].material_override` does nothing in Cycles here.
* `primitive_cube_add` takes `radius`, not `size` (a size=1 cube is radius 0.5).
* A brand-new `bpy.data.worlds.new()` has an **empty** node tree; reuse the scene's
  world or the background node will not exist.
* `util.by_pixel` divides by 32; at `scale = 0.5` one art pixel is 1/64 tile, which
  is why the pivot sits on the frame centre and no shift is needed at all.

## Review images

* `preview-rotations.png` — the eight cardinal/diagonal frames of the assembled
  turret on a ground tile (`preview_rotations.py <sheet_dir> <out.png>`)
* `preview-vs-vanilla.png` — vanilla gun turret, vanilla laser turret, the old drawn
  head and the new turret at the same pixels-per-tile
  (`compare_with_vanilla.py <sheet_dir> <out.png>`); both scripts read the installed
  game's own sprites, so they only run on this machine
