"""Ground truth for the muzzle: project the model's own points with the SAME ortho
camera melta_render.py uses, and print where they land in the frame.

Run (native paths):
  D:/blender/blender_2.79b/blender.exe -b --factory-startup -P muzzle_marker.py

Points are in *scaled* model space (the gun root is scaled by GUN_SCALE = 0.84):
  pivot        (0, 0, 0)
  bore axis    (0, 1.70*0.84, 0.86*0.84)   gun_bore_ring, the middle of the mouth
  front face   (0, 1.80*0.84, 0.86*0.84)   the lip's front face = C.muzzle_forward
"""
import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

TILT = math.radians(51.0)
TILES_IN_FRAME = 4.0
RES = 512
DIRECTIONS = 64
GUN_SCALE = 0.84
GUN_Z = 0.86

POINTS = {
    "pivot": (0.0, 0.0, 0.0),
    "bore": (0.0, 1.70 * GUN_SCALE, GUN_Z * GUN_SCALE),
    "front": (0.0, 1.80 * GUN_SCALE, GUN_Z * GUN_SCALE),
    "lip_top": (0.0, 1.802 * GUN_SCALE, (GUN_Z + 0.5) * GUN_SCALE),
}

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.render.resolution_x = RES
scene.render.resolution_y = RES
scene.render.resolution_percentage = 100

cam_data = bpy.data.cameras.new("cam")
cam_data.type = 'ORTHO'
cam_data.ortho_scale = TILES_IN_FRAME
cam = bpy.data.objects.new("cam", cam_data)
scene.objects.link(cam)
cam.rotation_euler = (TILT, 0, 0)
view_dir = Vector((0.0, math.sin(TILT), -math.cos(TILT)))
cam.location = view_dir * -22.0
scene.camera = cam
bpy.context.scene.update()

print("MARKER scale_tiles_per_px=%.6f" % (TILES_IN_FRAME / RES))
for d in range(DIRECTIONS):
    a = -2.0 * math.pi * d / DIRECTIONS
    for key, p in POINTS.items():
        x = p[0] * math.cos(a) - p[1] * math.sin(a)
        y = p[0] * math.sin(a) + p[1] * math.cos(a)
        z = p[2]
        ndc = world_to_camera_view(scene, cam, Vector((x, y, z)))
        off_x = (ndc.x - 0.5) * TILES_IN_FRAME
        off_up = (ndc.y - 0.5) * TILES_IN_FRAME
        print("MARKER d=%02d %-7s x=%+.4f up=%+.4f px=(%.1f,%.1f)"
              % (d, key, off_x, off_up, off_x * 64.0, -off_up * 64.0))
