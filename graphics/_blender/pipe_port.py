"""Render the melta's pipe PORT art (fluid_box.pipe_picture / pipe_covers).

Why this exists
---------------
The turret's four pipe ports are at 1.12 tiles, i.e. *inside* the hull: a
`pipe_connection.position` has to lie inside the collision box (the loader rejects
anything else), so no port art can sit at the pipe's mouth unless it is drawn as a
sprite. Vanilla's answer is `pipe_picture` -- a Sprite4Way drawn per connected side,
which is the machine's own pipe stub (the assembling machine ships
`assembling-machine-2-pipe-N/E/S/W`). Without it the engine falls back to
`always_draw_covers = true`, and `pipe_covers` is by definition the picture for a port
with *nothing* connected: a capped collar. That is exactly the reported look -- a cap
lying on the deck, half a tile short of the pipe end, on every side.

So: model one port (mount pad, neck, bolted clamp collar, socket mouth) and render it
in four orientations, plus a capped variant for `pipe_covers` (the bare-port picture,
so an unused port reads as blanked off rather than as an open hole).

Frame space
-----------
The sprite is drawn AT the connection point, so the frame centre IS the connection
point (`shift = {0, 0}`) and this model is built around it:
    +Y = into the hull (inboard)     -Y = out along the pipe (outboard)
so the socket spans frame y +0.18 .. -0.55, i.e. 1.30 .. 0.57 tiles from the turret
centre once drawn at 1.12. The mouth ends 0.55 tiles out, past the pipe's near edge
(1.50 tiles from the centre), which is what closes the seam.

Run -- native Windows paths required for the Blender binary:

  blender -b --factory-startup -P pipe_port.py -- --out C:/tmp/melta/pipe

Outputs, into --out:
  port/port-{north,east,south,west}.png   pipe_picture  (pipe connected)
  port/cap-{north,east,south,west}.png    pipe_covers   (bare port)
  port.json                               the geometry numbers, for the assembler

Same camera, tilt, light rig, materials and tone curve as the turret itself
(`melta_render.py` / `assemble.py`), so the port sits in the same light as the hull.
128 px frame = 2 tiles at scale 0.5 = 64 art px/tile, the same density as the rest of
the mod's art.
"""

import json
import math
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import melta_render as M            # noqa: E402  (materials, primitives, lights)

# --------------------------------------------------------------- framing ----
FRAME = 128                        # art px per frame edge -> 64 screen px at 0.5
TILES_IN_FRAME = FRAME / 64.0      # 2.0 tiles across the frame
RES = 512                          # 4x supersample
DIRECTIONS = 4

# Port geometry, in frame space (connection point = frame centre). One owner for
# these numbers: the assembler prints them and the checker measures against them.
PORT = {
    "axis_z": 0.30,                # pipe axis height, tiles
    "pad_y": 0.10,                 # mount pad centre (into the hull)
    "pad_sy": 0.16,
    "pad_sx": 0.46,
    "neck_y": -0.05,
    "neck_len": 0.26,
    "neck_r": 0.125,
    "collar_y": -0.26,
    "collar_len": 0.11,
    "collar_r": 0.26,
    "mouth_y": -0.44,
    "mouth_len": 0.24,
    "mouth_r": 0.235,
    "lip_y": -0.575,
    "lip_r": 0.275,
    "lip_len": 0.07,
    "inboard": 0.18,               # furthest point into the hull
    "outboard": -0.605,            # furthest point along the pipe
}
SIDES = (("north", 180.0), ("east", 90.0), ("south", 0.0), ("west", 270.0))

# Extra lip length per side, tiles. The same model is rendered for every direction
# through the same pitched camera, so one world length does not land at the same
# screen distance on all four sides: the pipe itself is drawn with a rim and a baked
# shadow that overhang its tile upward by 0.81 tiles (north pipe near edge 1.52,
# south 1.19). These numbers make each port's mouth land on its own pipe; they are
# measured, not guessed -- pipe_join.py reports the overlap and `--check` fails if it
# goes negative.
LIP_EXT = {"north": 0.0, "east": 0.0, "south": 0.0, "west": 0.0}


def argval(flag, default=None):
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if flag in argv:
        return argv[argv.index(flag) + 1]
    return default


OUT_DIR = argval("--out", os.path.join(HERE, "raw_pipe"))
SAMPLES = int(argval("--samples", "48"))
ONLY = argval("--only", "")        # "cap", "port" or "" (both)


# ---------------------------------------------------------------- camera ----
def setup_camera():
    """Same tilt and aim as the turret, but a 2-tile ortho frame."""
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = TILES_IN_FRAME
    cam = bpy.data.objects.new("cam", cam_data)
    M.link(cam)
    cam.rotation_euler = (M.TILT, 0, 0)
    view_dir = M.Vector((0.0, math.sin(M.TILT), -math.cos(M.TILT)))
    cam.location = view_dir * -22.0
    bpy.context.scene.camera = cam
    return cam


def setup_render():
    M.setup_render()
    scene = bpy.context.scene
    scene.cycles.samples = SAMPLES
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES


# -------------------------------------------------------------- geometry ----
def build_port(capped=False, lip_ext=0.0):
    """One port, south-facing in model space (the render rig turns it: see SIDES).

    Model space: -Y is out along the pipe, +Y into the hull. The first render pass is
    rotated 180 deg for the north sprite, so "south" being the unrotated one is just
    where the numbers were built.
    """
    z = PORT["axis_z"]
    y_axis = (math.pi / 2, 0, 0)          # a cylinder lying along Y
    parts = []
    mouth_len = PORT["mouth_len"] + lip_ext
    mouth_y = PORT["mouth_y"] - lip_ext / 2.0
    lip_y = PORT["lip_y"] - lip_ext
    outboard = PORT["outboard"] - lip_ext

    # mount pad welded to the hull wall (the inboard end, mostly behind the hull art)
    parts.append(M.box("port_pad", PORT["pad_sx"], PORT["pad_sy"], 0.12,
                       (0, PORT["pad_y"], z - 0.19), mat="cast", bev=0.012))
    parts.append(M.box("port_pad_foot", PORT["pad_sx"] + 0.10, 0.06, 0.05,
                       (0, PORT["pad_y"] - 0.03, z - 0.26), mat="steel_dark",
                       bev=0.008))
    parts.append(M.bolt_ring("port_padbolt", (0, z - 0.19), 0.17, 4, PORT["pad_y"],
                             size=0.035, depth=0.05, axis="Y"))

    # neck from the pad out to the clamp collar
    parts.append(M.cyl("port_neck", PORT["neck_r"], PORT["neck_len"],
                       (0, PORT["neck_y"], z), rot=y_axis, mat="steel",
                       verts=16, bev=0.010))
    # ribbed strain relief sleeves on the neck -- reads as flexible plumbing
    for i, yy in enumerate((-0.14, -0.05, 0.04)):
        parts.append(M.torus("port_rib{}".format(i), PORT["neck_r"] + 0.012, 0.017,
                             (0, yy, z), rot=y_axis, mat="steel_dark",
                             maj_seg=16, min_seg=6))

    # clamp collar: the chunky ring the pipe end butts into
    parts.append(M.cyl("port_collar", PORT["collar_r"], PORT["collar_len"],
                       (0, PORT["collar_y"], z), rot=y_axis, mat="steel",
                       verts=18, bev=0.012))
    for i, yy in enumerate((PORT["collar_y"] + 0.05, PORT["collar_y"] - 0.05)):
        parts.append(M.torus("port_collar_band{}".format(i), PORT["collar_r"],
                             0.024, (0, yy, z), rot=y_axis, mat="steel_dark",
                             maj_seg=20, min_seg=6))
    parts.append(M.bolt_ring("port_bolt", (0, z), PORT["collar_r"] - 0.045, 6,
                             PORT["collar_y"], mat="copper", size=0.038,
                             depth=0.06, axis="Y"))

    # socket mouth: a receiver wider than the pipe body, so the pipe visibly runs into
    # a fitting instead of ending in a cap. The pipe's own edges (0.25 tiles from its
    # centreline) still show either side of it, which is what sells "inserted".
    parts.append(M.cyl("port_mouth", PORT["mouth_r"], mouth_len,
                       (0, mouth_y, z), rot=y_axis, mat="steel_dark",
                       verts=18, bev=0.010))
    parts.append(M.cyl("port_lip", PORT["lip_r"], PORT["lip_len"],
                       (0, lip_y, z), rot=y_axis, mat="cast",
                       verts=18, bev=0.008))
    # bolt heads on the visible socket face -- this is the only part of the collar
    # that clears the hull's rim on every side, so it carries the hardware detail
    parts.append(M.bolt_ring("port_lipbolt", (0, z), PORT["lip_r"] - 0.045, 6,
                             lip_y + PORT["lip_len"] / 2.0 + 0.012, mat="copper",
                             size=0.040, depth=0.055, axis="Y"))

    if capped:
        # blanking plate over the mouth: proud of the lip and wider than it, so the
        # cap actually changes the silhouette -- a plate tucked inside the lip is
        # invisible from this camera and the bare port reads as an open socket.
        cap_r = PORT["lip_r"] + 0.035
        parts.append(M.cyl("port_cap", cap_r, 0.06,
                           (0, outboard + 0.015, z), rot=y_axis, mat="steel",
                           verts=18, bev=0.012))
        parts.append(M.cyl("port_cap_nut", 0.06, 0.06, (0, outboard - 0.02, z),
                           rot=y_axis, mat="copper", verts=6, bev=0.0,
                           smooth=False))
        parts.append(M.bolt_ring("port_capbolt", (0, z), cap_r - 0.05, 6,
                                 outboard + 0.03, size=0.032, depth=0.05,
                                 axis="Y"))
    return parts


# ------------------------------------------------------------------ main ----
def main():
    M.purge()
    M.build_materials()
    setup_render()
    setup_camera()
    M.setup_lights()

    scene = bpy.context.scene
    os.makedirs(os.path.join(OUT_DIR, "port"), exist_ok=True)

    # One port per side, each under an empty at the frame centre; the empty turns the
    # whole port about the connection point (rotating the parts themselves would spin
    # each one in place). Per-side lip length: see LIP_EXT.
    for kind, prefix in (("open", "port"), ("cap", "cap")):
        for side, angle in SIDES:
            if ONLY and ONLY != kind:
                continue
            root = bpy.data.objects.new("root_{}_{}".format(kind, side), None)
            M.link(root)
            root.rotation_euler = (0, 0, math.radians(angle))
            parts = build_port(capped=(kind == "cap"), lip_ext=LIP_EXT[side])
            flat = []
            for item in parts:
                flat.extend(item if isinstance(item, list) else [item])
            for ob in flat:
                ob.parent = root
            scene.render.filepath = os.path.join(OUT_DIR, "port",
                                                 "{}-{}.png".format(kind, side))
            bpy.ops.render.render(write_still=True)
            print("rendered", kind, side)
            # drop this port before building the next, so only one is ever in frame
            for ob in flat:
                bpy.data.objects.remove(ob, do_unlink=True)
            bpy.data.objects.remove(root, do_unlink=True)

    meta = {
        "frame_px": FRAME,
        "render_px": RES,
        "tiles_in_frame": TILES_IN_FRAME,
        "art_px_per_tile": FRAME / TILES_IN_FRAME,
        "scale": 0.5,
        "shift": [0, 0],
        "tilt_degrees": round(math.degrees(M.TILT), 2),
        "port": PORT,
        "lip_ext": LIP_EXT,
        "sides": [s for s, _ in SIDES],
    }
    with open(os.path.join(OUT_DIR, "port.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print("META", json.dumps(meta))


if __name__ == "__main__":
    main()
