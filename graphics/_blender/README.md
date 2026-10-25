# Melta turret art pipeline

The turret has no hand-drawn sprites: the whole emplacement is modelled and
rendered procedurally, so it can be re-rendered at a different size, palette or
damage level by changing numbers instead of pixels.

    melta_render.py   builds the model in Blender, renders the hull once and the
                      cannon 64 times (5.625 deg apart)
    assemble.py       downsamples, applies the tone curve, bakes cast shadows,
                      writes the sheets the prototype loads
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

The number the beam code needs lives here too: the muzzle (the front face of the
heat projector) is **1.79 tiles** from the pivot on the barrel axis. `constants.lua`
`C.muzzle_offset` and `entity.lua` `gun_barrel_length` both read that value.

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
