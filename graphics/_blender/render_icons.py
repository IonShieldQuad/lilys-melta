"""Render the melta turret's ICON and THUMBNAIL frames from the same model.

The sprite sheets are assembled from two separate renders (hull once, gun 64x).
An icon is the opposite problem: one still image of the whole machine, seen the
way vanilla ships turret icons -- the 51 deg pitch camera, the turret turned to a
three-quarter pose, transparent background, supersampled so assemble_icons.py can
fit and downsample it.

This script deliberately imports the model out of melta_render.py instead of
copying it: the icon must show the same turret the sheets show, and a second model
file would drift the moment GUN_SCALE or a part moves.

Run (native Windows paths; Blender 2.79b):

  blender -b --factory-startup -P render_icons.py -- \
      --out C:/tmp/melta/iconraw --dirs 40,44,48 --res 1024 --samples 48

Outputs icon-<dir>.png per requested direction, pivot at the frame centre.

Framing notes:
  * ortho_scale is in TILES (1 Blender unit = 1 tile). The turret is ~3.1 tiles
    across at its widest and the cannon reaches 1.51 tiles from the pivot, so 4.2
    tiles of frame leaves margin on every side -- assemble_icons.py then fits the
    silhouette to the icon box, which is what makes "no clipping, no dead padding"
    deterministic instead of eyeballed.
"""

import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import melta_render as M   # noqa: E402  (the model, materials, camera and lights)


def argval(flag, default=None):
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if flag in argv:
        return argv[argv.index(flag) + 1]
    return default


OUT_DIR = argval("--out", os.path.join(HERE, "iconraw"))
RES = int(argval("--res", "1024"))
SAMPLES = int(argval("--samples", "48"))
ORTHO = float(argval("--ortho", "4.2"))
DIRS = [int(x) for x in argval("--dirs", "40").split(",")]
# Camera pitch from vertical, degrees. The sprite sheets use 51 (melta_render.TILT);
# an icon is a still, and a lower pitch (more top-down) makes the round pedestal
# project rounder, which is what gets a wide 2x2 emplacement to fill a square frame
# -- measured on this model: 51 deg leaves 63x44 of content in the 64 px box, 34 deg
# gives 63x53, i.e. the same icon with no dead band.
TILT = float(argval("--tilt", "34"))


def main():
    M.purge()
    M.build_materials()
    M.setup_render()
    cam = M.setup_camera()
    cam.data.ortho_scale = ORTHO
    cam.rotation_euler = (math.radians(TILT), 0, 0)
    # camera sits south of the origin, above it, aimed at the world origin: +Y stays
    # "up" on screen and the pivot lands on the pixel centre at any pitch
    cam.location = Vector((0.0, math.sin(math.radians(TILT)),
                           -math.cos(math.radians(TILT)))) * -22.0
    M.setup_lights()

    scene = bpy.context.scene
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.cycles.samples = SAMPLES

    M.build_hull()
    root = bpy.data.objects.new("gun_root", None)
    M.link(root)
    M.build_gun(root)
    # scale AFTER parenting, exactly like melta_render.main(): build_gun stores the
    # parent inverse matrix, so a scale set before parenting is cancelled out
    root.scale = (M.GUN_SCALE, M.GUN_SCALE, M.GUN_SCALE)

    os.makedirs(OUT_DIR, exist_ok=True)
    for d in DIRS:
        root.rotation_euler = (0, 0, -2.0 * math.pi * d / M.DIRECTIONS)
        scene.render.filepath = os.path.join(OUT_DIR, "icon-{:03d}.png".format(d))
        bpy.ops.render.render(write_still=True)
        print("rendered icon direction", d, "->", scene.render.filepath)


if __name__ == "__main__":
    main()
