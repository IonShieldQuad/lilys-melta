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
# ICON-ONLY shape budget. The hull is ~3.1 tiles across and the cannon reaches 1.51
# tiles from the pivot, so in the fitted 64 px cell the weapon is a minority of the
# silhouette and at 32 px the icon collapses into one oval (measured: 15.5 % of the
# mask beyond 1.3x the median radius against 20-24 % for vanilla's turret icons).
# This knob multiplies the GUN ROOT about the pivot in the icon render only -- the
# sprite sheets call melta_render.build_gun() directly and never see it, so in-world
# art, the beam anchors and the collision box are untouched. The scale is uniform and
# the root is dropped by exactly the amount that keeps the barrel axis at
# GUN_Z * GUN_SCALE, so the gun grows about its bore instead of floating off the
# bearing. Default 1.0 = the machine the sheets show.
GUN_F = float(argval("--icon-gun-scale", "1.0"))
# Icon-only emissive boost, "<material>=<multiplier>,...". At 32 px the muzzle has to
# be the one element the eye lands on -- vanilla's flamethrower icon is a hull blob, a
# plate and a white-hot nozzle -- and the shared materials are deliberately tuned "hot
# pixels, not a lamp" for the sprite sheets. Multiplying the emission here (never in
# melta_render's defaults) keeps the sheets byte-identical while giving the icon a
# white-hot muzzle lip and bore.
EMIT_BOOST = [s for s in argval("--icon-emit", "").split(",") if s]


def main():
    M.purge()
    M.build_materials()
    for spec in EMIT_BOOST:
        head, mul = spec.split("=")
        name, _, white = head.partition(":")
        white = float(white or 0.0)
        mat = bpy.data.materials.get(name)
        if mat is None or not mat.use_nodes:
            raise SystemExit("icon emit: no material " + name)
        hit = 0
        for node in mat.node_tree.nodes:
            if node.type == 'EMISSION':
                node.inputs["Strength"].default_value *= float(mul)
                if white > 0.0:
                    c = list(node.inputs["Color"].default_value)
                    node.inputs["Color"].default_value = tuple(
                        c[i] + (1.0 - c[i]) * white for i in range(3)) + (1,)
                hit += 1
        print("icon emit %s x%s -> %d emission node(s), white %.2f" % (name, mul, hit, white))
    M.setup_render()
    cam = M.setup_camera()
    cam.data.ortho_scale = ORTHO
    cam.rotation_euler = (math.radians(TILT), 0, 0)
    # camera sits south of the origin, above it, aimed at the world origin: +Y stays
    # "up" on screen and the pivot lands on the pixel centre at any pitch
    cam.location = Vector((0.0, math.sin(math.radians(TILT)),
                           -math.cos(math.radians(TILT)))) * -22.0
    M.setup_lights()
    # The icon camera sees MORE than the sheet camera: ortho 4.2 tiles here against the
    # sheets' 4.0, and a steeper 34 deg pitch. A softbox whose corner is outside the
    # sheet frame therefore projects *inside* this one and renders as a flat pale
    # peach tab -- which is what the shipped icons had at 10 o'clock (measured: 224 px
    # of one flat colour, alpha 255, on every generated icon and thumbnail). The sheet
    # pass calls check_rig_in_frame() and prints DIAG; the icon pass never did, so the
    # artefact shipped. Push the plates along the camera's screen-up axis until the
    # real camera reports them clear, then keep the aim on the rig target.
    scene_u = Vector((0.0, math.cos(math.radians(TILT)), math.sin(math.radians(TILT))))
    for attempt in range(8):
        if M.check_rig_in_frame():
            break
        for ob in bpy.data.objects:
            if ob.name.startswith("soft:"):
                ob.location = ob.location + scene_u * 1.5
                aim = Vector((0.0, 0.0, 0.5)) - ob.location
                ob.rotation_euler = aim.to_track_quat('Z', 'Y').to_euler()
        print("icon rig: pushed plates clear, attempt", attempt + 1)
    else:
        raise SystemExit("icon rig: a light plate is still inside the icon frame")

    scene = bpy.context.scene
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.cycles.samples = SAMPLES

    M.build_hull_in_place()
    root = bpy.data.objects.new("gun_root", None)
    M.link(root)
    M.build_gun(root)
    # scale AFTER parenting, exactly like melta_render.main(): build_gun stores the
    # parent inverse matrix, so a scale set before parenting is cancelled out
    s = M.GUN_SCALE * GUN_F
    root.scale = (s, s, s)
    # keep the bore at its sheet height: growing about the pivot would otherwise lift
    # the collar off the bearing and leave daylight between gun and hull
    root.location = Vector((0.0, 0.0, -(GUN_F - 1.0) * M.GUN_Z * M.GUN_SCALE))
    if GUN_F != 1.0:
        # a bigger gun reaches past the sheet frame; widen the frame so nothing clips
        # (assemble_icons fits the silhouette anyway, so this costs no framing)
        reach = 1.80 * s + 0.30
        if reach * 2.0 > cam.data.ortho_scale:
            cam.data.ortho_scale = reach * 2.0
        print("icon gun scale %.2f -> root scale %.3f, z drop %.3f, ortho %.2f"
              % (GUN_F, s, -root.location.z, cam.data.ortho_scale))

    os.makedirs(OUT_DIR, exist_ok=True)
    for d in DIRS:
        root.rotation_euler = (0, 0, -2.0 * math.pi * d / M.DIRECTIONS)
        scene.render.filepath = os.path.join(OUT_DIR, "icon-{:03d}.png".format(d))
        bpy.ops.render.render(write_still=True)
        print("rendered icon direction", d, "->", scene.render.filepath)


if __name__ == "__main__":
    main()
