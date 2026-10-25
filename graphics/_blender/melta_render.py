"""Melta turret -- scripted Blender render (Blender 2.79b, Cycles CPU).

Everything here is procedural: no external assets, no .blend to keep in sync.
It builds a rusted industrial emplacement hull plus a WH40K-melta inspired cannon,
then renders the hull once (static base sprite) and the gun 64 times (rotating
head sheet). Lighting is fixed to the screen the way Factorio authors it, so the
gun casts its shadow consistently whichever way it points.

Run -- native Windows paths required for the Blender binary:

  blender -b --factory-startup -P melta_render.py -- \
      --out C:/tmp/melta/raw --dirs all --res 512 --samples 40

  --dirs none renders the hull pass only (~11 s instead of ~12 min), for a change
  that only touches the static base sprite.

Outputs, into --out:
  base/hull.png            static hull (transparent, FRAME-sized after assembly)
  gun/gun-000..063.png     head frames, pivot at image centre, 0 = north
  meta.json                framing numbers (tile scale, extents) for the prototype

Sheet conventions (consumed by assemble.py and prototypes/graphics.lua):
  * 1 Blender unit = 1 tile; the 256 px frame spans 4 tiles = 64 art px/tile,
    which is Factorio's 2x art density -> `scale = 0.5` draws 32 px/tile.
  * The pivot is the world origin and the camera aims at it, so it lands exactly
    on the frame centre: sprite `shift = {0, 0}` and no pivot wobble.
  * Direction 0 = north (+Y); the gun rotates -Z (clockwise seen from above).
"""

import bpy
import json
import math
import os
import random
import sys
from mathutils import Vector

# --------------------------------------------------------------- framing ----
FRAME = 256                     # art px per frame edge -> 128 screen px at 0.5
RES = 512                       # supersampled render resolution
TILES_IN_FRAME = FRAME / 64.0   # 4.0 tiles across a frame
TILT = math.radians(51.0)       # camera pitch from vertical (vertical squash cos)
DIRECTIONS = 64
GUN_Z = 0.86                    # barrel axis height, tiles
# The frame must hold the cannon at every angle, and the north-pointing pose is the
# worst case (barrel depth AND barrel height both project upward): the projector lip
# reaches 2.22 tiles of screen space unscaled, so 0.84 keeps it inside the 2.0-tile
# frame radius with ~8 px of margin at 256 px.
GUN_SCALE = 0.84


# ------------------------------------------------------------------ args ----
def argval(flag, default=None):
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    if flag in argv:
        return argv[argv.index(flag) + 1]
    return default


OUT_DIR = argval("--out", os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw"))
SAMPLES = int(argval("--samples", "40"))
RES = int(argval("--res", str(RES)))
DIR_ARG = argval("--dirs", "all")
SUN_SCALE = float(argval("--sunscale", "1.0"))   # debug: 0 proves which lights matter
WORLD_SCALE = float(argval("--worldscale", "1.0"))
EMIT_SCALE = float(argval("--emitscale", "1.0"))
FLATMAT = argval("--flatmat", "0") == "1"
ONLY = argval("--only", "")

rng = random.Random(40215)

# ------------------------------------------------------------ scene utils ---
def purge():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.curves,
                  bpy.data.textures, bpy.data.node_groups, bpy.data.lamps):
        for item in list(block):
            block.remove(item)


def link(ob):
    bpy.context.scene.objects.link(ob)
    return ob


def activate(ob):
    bpy.context.scene.objects.active = ob
    for other in bpy.context.scene.objects:
        other.select = (other == ob)
    return ob


def apply_scale(ob):
    activate(ob)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return ob


# ------------------------------------------------------------- materials ----
def _ramp(links, nodes, src, stops):
    ramp = nodes.new("ShaderNodeValToRGB")
    links.new(src, ramp.inputs["Fac"])
    els = ramp.color_ramp.elements
    while len(els) > len(stops):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, col) in zip(els, stops):
        el.position = pos
        el.color = (col, col, col, 1.0)
    return ramp


def weathered_material(name, paint=(0.115, 0.120, 0.128), metal=(0.200, 0.205, 0.215),
                       rust=(0.150, 0.058, 0.022), half=(0.235, 0.240, 0.245),
                       rough=0.62, chip=0.5, rust_amt=0.55, streak_scale=0.55,
                       noise_scale=6.5, metallic=0.30, bump=0.25,
                       paint_only=False, emissive=None, emissive_strength=3.0):
    """One shader family for the whole turret, tuned per part. Four things are
    layered on every surface, which is what makes it read as old metal instead of
    clean sci-fi:

      * chipped paint  -- broad noise mask exposing bare metal under the paint
      * edge wear      -- convex pointiness polished back to bright steel
      * rust           -- noise stretched down Z so patches streak vertically
      * crevice grime  -- concave pointiness multiplied to near-black
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        nodes.remove(n)

    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    coord = nodes.new("ShaderNodeTexCoord")
    geo = nodes.new("ShaderNodeNewGeometry")

    # ---- chipped paint mask --------------------------------------------
    chip_noise = nodes.new("ShaderNodeTexNoise")
    chip_noise.inputs["Scale"].default_value = noise_scale
    chip_noise.inputs["Detail"].default_value = 8.0
    chip_noise.inputs["Distortion"].default_value = 1.6
    links.new(coord.outputs["Object"], chip_noise.inputs["Vector"])
    chip_ramp = _ramp(links, nodes, chip_noise.outputs["Fac"],
                      [(0.50 - chip * 0.20, 0.0), (0.54 - chip * 0.10, 1.0)])

    # ---- fine grain ------------------------------------------------------
    grain = nodes.new("ShaderNodeTexNoise")
    grain.inputs["Scale"].default_value = 16.0
    grain.inputs["Detail"].default_value = 2.0
    links.new(coord.outputs["Object"], grain.inputs["Vector"])

    # ---- rust, stretched along Z to read as running down ----------------
    mapping = nodes.new("ShaderNodeMapping")
    mapping.scale = (2.6, 2.6, streak_scale)   # 2.79: Mapping has no sockets
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    rust_noise = nodes.new("ShaderNodeTexNoise")
    rust_noise.inputs["Scale"].default_value = 4.0
    rust_noise.inputs["Detail"].default_value = 7.0
    rust_noise.inputs["Distortion"].default_value = 1.0
    links.new(mapping.outputs["Vector"], rust_noise.inputs["Vector"])
    rust_ramp = _ramp(links, nodes, rust_noise.outputs["Fac"],
                      [(0.60 - rust_amt * 0.22, 0.0), (0.72 - rust_amt * 0.12, 1.0)])

    # ---- crevice grime (concave) and edge wear (convex) ------------------
    # vanilla turret art keeps ~half its pixels near black in the crevices and
    # punches highlights up to 110-140, so grime is restricted to real concavities
    grime_ramp = _ramp(links, nodes, geo.outputs["Pointiness"],
                       [(0.40, 0.0), (0.49, 1.0)])
    wear_ramp = _ramp(links, nodes, geo.outputs["Pointiness"],
                      [(0.52, 0.0), (0.60, 1.0)])

    # ---- compose base colour --------------------------------------------
    m_paint = nodes.new("ShaderNodeMixRGB")
    m_paint.inputs["Color1"].default_value = (metal[0], metal[1], metal[2], 1)
    m_paint.inputs["Color2"].default_value = (paint[0], paint[1], paint[2], 1)
    if paint_only:
        chip_ramp.color_ramp.elements[0].color = (1, 1, 1, 1)
    links.new(chip_ramp.outputs["Color"], m_paint.inputs["Fac"])

    m_rust = nodes.new("ShaderNodeMixRGB")
    m_rust.inputs["Fac"].default_value = 1.0
    links.new(m_paint.outputs["Color"], m_rust.inputs["Color1"])
    m_rust.inputs["Color2"].default_value = (rust[0], rust[1], rust[2], 1)
    links.new(rust_ramp.outputs["Color"], m_rust.inputs["Fac"])

    m_grime = nodes.new("ShaderNodeMixRGB")
    m_grime.blend_type = 'MULTIPLY'
    m_grime.inputs["Fac"].default_value = 1.0
    links.new(m_rust.outputs["Color"], m_grime.inputs["Color1"])
    links.new(grime_ramp.outputs["Color"], m_grime.inputs["Color2"])

    m_wear = nodes.new("ShaderNodeMixRGB")
    links.new(m_grime.outputs["Color"], m_wear.inputs["Color1"])
    m_wear.inputs["Color2"].default_value = (half[0], half[1], half[2], 1)
    links.new(wear_ramp.outputs["Color"], m_wear.inputs["Fac"])

    # ---- big bare-metal patches: not every plate weathered the same way ----
    patch_noise = nodes.new("ShaderNodeTexNoise")
    patch_noise.inputs["Scale"].default_value = 2.2
    patch_noise.inputs["Detail"].default_value = 3.0
    patch_noise.inputs["Distortion"].default_value = 2.2
    links.new(coord.outputs["Object"], patch_noise.inputs["Vector"])
    patch_ramp = _ramp(links, nodes, patch_noise.outputs["Fac"],
                       [(0.58, 0.0), (0.68, 1.0)])
    m_patch = nodes.new("ShaderNodeMixRGB")
    m_patch.inputs["Fac"].default_value = 0.55
    links.new(m_wear.outputs["Color"], m_patch.inputs["Color1"])
    links.new(patch_ramp.outputs["Color"], m_patch.inputs["Fac"])
    m_patch.inputs["Color2"].default_value = (half[0] * 1.15, half[1] * 1.15,
                                             half[2] * 1.15, 1)

    # ---- oil / soot streaks running down the same way as the rust ---------
    oil_noise = nodes.new("ShaderNodeTexNoise")
    oil_noise.inputs["Scale"].default_value = 3.0
    oil_noise.inputs["Detail"].default_value = 5.0
    oil_mapping = nodes.new("ShaderNodeMapping")
    oil_mapping.scale = (3.4, 3.4, 0.28)   # 2.79's Mapping node has no 3D location socket
    links.new(coord.outputs["Object"], oil_mapping.inputs["Vector"])
    links.new(oil_mapping.outputs["Vector"], oil_noise.inputs["Vector"])
    oil_ramp = _ramp(links, nodes, oil_noise.outputs["Fac"],
                     [(0.66, 0.0), (0.74, 1.0)])
    m_oil = nodes.new("ShaderNodeMixRGB")
    m_oil.inputs["Fac"].default_value = 0.7
    links.new(m_patch.outputs["Color"], m_oil.inputs["Color1"])
    links.new(oil_ramp.outputs["Color"], m_oil.inputs["Fac"])
    m_oil.inputs["Color2"].default_value = (0.020, 0.018, 0.015, 1)

    m_grain = nodes.new("ShaderNodeMixRGB")
    m_grain.blend_type = 'MULTIPLY'
    m_grain.inputs["Fac"].default_value = 0.10
    links.new(m_oil.outputs["Color"], m_grain.inputs["Color1"])
    links.new(grain.outputs["Color"], m_grain.inputs["Color2"])

    # ---- ambient occlusion as a shader, not a light ----------------------
    # Cycles 2.79's sun lamps in this build do not respond to `energy`, so the
    # directional key light cannot be trusted to carve the model. Shader-level AO
    # gives the recesses their darkness deterministically, which is also what
    # vanilla turret art looks like (half its pixels sit near black).
    ao = nodes.new("ShaderNodeAmbientOcclusion")
    # socket layout differs between 2.79 builds: AO distance is the non-colour input
    for sock in ao.inputs:
        if sock.name != "Color":
            sock.default_value = 0.30
    if hasattr(ao, "samples"):
        ao.samples = 8
    ao_out = ao.outputs["AO"] if "AO" in ao.outputs else ao.outputs[-1]
    ao_ramp = _ramp(links, nodes, ao_out,
                    [(0.15, 0.0), (0.85, 1.0)])
    m_ao = nodes.new("ShaderNodeMixRGB")
    m_ao.blend_type = 'MULTIPLY'
    m_ao.inputs["Fac"].default_value = 0.80
    links.new(m_grain.outputs["Color"], m_ao.inputs["Color1"])
    links.new(ao_ramp.outputs["Color"], m_ao.inputs["Color2"])
    links.new(m_ao.outputs["Color"], bsdf.inputs["Base Color"])

    # ---- roughness: paint satin, rust rough, worn edges polished --------
    rough_rust = nodes.new("ShaderNodeMixRGB")
    rough_rust.inputs["Color1"].default_value = (rough * 0.70,) * 3 + (1,)
    rough_rust.inputs["Color2"].default_value = (min(1.0, rough * 1.30),) * 3 + (1,)
    links.new(rust_ramp.outputs["Color"], rough_rust.inputs["Fac"])
    rough_wear = nodes.new("ShaderNodeMixRGB")
    links.new(rough_rust.outputs["Color"], rough_wear.inputs["Color1"])
    rough_wear.inputs["Color2"].default_value = (0.34,) * 3 + (1,)
    links.new(wear_ramp.outputs["Color"], rough_wear.inputs["Fac"])
    links.new(rough_wear.outputs["Color"], bsdf.inputs["Roughness"])
    bsdf.inputs["Metallic"].default_value = metallic

    # ---- bump: grain plus the chip/wear edges ---------------------------
    bump_mix = nodes.new("ShaderNodeMixRGB")
    bump_mix.blend_type = 'ADD'
    bump_mix.inputs["Fac"].default_value = 0.7
    links.new(grain.outputs["Fac"], bump_mix.inputs["Color1"])
    links.new(wear_ramp.outputs["Color"], bump_mix.inputs["Color2"])
    bump_node = nodes.new("ShaderNodeBump")
    bump_node.inputs["Strength"].default_value = bump
    bump_node.inputs["Distance"].default_value = 0.02
    links.new(bump_mix.outputs["Color"], bump_node.inputs["Height"])
    links.new(bump_node.outputs["Normal"], bsdf.inputs["Normal"])

    if emissive is not None:
        emit = nodes.new("ShaderNodeEmission")
        emit.inputs["Color"].default_value = (emissive[0], emissive[1], emissive[2], 1)
        # Emission is a real light in Cycles: too much of it floods the whole
        # turret with orange GI and flattens the sun shading. The glow has to read
        # as hot pixels, not as a lamp, so it stays small and weak.
        emit.inputs["Strength"].default_value = emissive_strength * EMIT_SCALE
        mix = nodes.new("ShaderNodeAddShader")
        links.new(bsdf.outputs["BSDF"], mix.inputs[0])
        links.new(emit.outputs["Emission"], mix.inputs[1])
        links.new(mix.outputs["Shader"], out.inputs["Surface"])

    return mat


MATS = {}


def build_materials():
    """Palette sits next to vanilla gun/laser turret sprites: desaturated dark
    steel, muted warning yellow, rust brown, a little copper plumbing."""
    MATS["steel"] = weathered_material("steel", paint=(0.155, 0.162, 0.172),
                                       metal=(0.330, 0.336, 0.348), rough=0.56,
                                       chip=0.50, rust_amt=0.50)
    MATS["steel_dark"] = weathered_material("steel_dark", paint=(0.092, 0.096, 0.104),
                                            metal=(0.180, 0.188, 0.198), rough=0.66,
                                            chip=0.38, rust_amt=0.45)
    MATS["cast"] = weathered_material("cast", paint=(0.205, 0.210, 0.216),
                                      metal=(0.420, 0.424, 0.430), rough=0.74,
                                      chip=0.66, rust_amt=0.62, noise_scale=17.0,
                                      metallic=0.35)
    MATS["yellow"] = weathered_material("yellow", paint=(0.520, 0.350, 0.060),
                                        metal=(0.300, 0.200, 0.055),
                                        rust=(0.190, 0.080, 0.030), rough=0.62,
                                        chip=0.85, rust_amt=0.80, noise_scale=15.0,
                                        metallic=0.35)
    MATS["red"] = weathered_material("red", paint=(0.340, 0.062, 0.038),
                                     metal=(0.210, 0.070, 0.040), rust=(0.180, 0.075, 0.030),
                                     rough=0.64, chip=0.80, rust_amt=0.70,
                                     noise_scale=13.0, metallic=0.40)
    MATS["copper"] = weathered_material("copper", paint=(0.260, 0.120, 0.052),
                                        metal=(0.380, 0.200, 0.090), rough=0.70,
                                        chip=0.18, rust_amt=0.42, noise_scale=22.0,
                                        metallic=0.55)
    MATS["rubber"] = weathered_material("rubber", paint=(0.022, 0.022, 0.024),
                                        metal=(0.034, 0.034, 0.036), rough=0.86,
                                        chip=0.0, rust_amt=0.0, metallic=0.0, bump=0.40)
    MATS["grime"] = weathered_material("grime", paint=(0.014, 0.013, 0.012),
                                       metal=(0.020, 0.018, 0.016), rough=0.95,
                                       chip=0.0, rust_amt=0.0, metallic=0.0)
    MATS["glow"] = weathered_material("glow", paint=(0.40, 0.14, 0.03),
                                      metal=(0.40, 0.14, 0.03), rough=0.5, chip=0.0,
                                      rust_amt=0.0, metallic=0.0,
                                      emissive=(1.0, 0.34, 0.070), emissive_strength=6.0)
    MATS["glow_dim"] = weathered_material("glow_dim", paint=(0.30, 0.09, 0.02),
                                          metal=(0.30, 0.09, 0.02), rough=0.6, chip=0.0,
                                          rust_amt=0.0, metallic=0.0,
                                          emissive=(1.0, 0.26, 0.040), emissive_strength=1.9)


# -------------------------------------------------------------- geometry ----
DENT_TEX = None


def add_dents(ob, strength=0.02, size=0.42):
    """Real dents, not a bump map: a Simple subdivision first (a cube's 8 corner
    verts cannot be dented), then a GLOBAL-space clouds displace so neighbouring
    plates dent coherently."""
    global DENT_TEX
    if DENT_TEX is None:
        DENT_TEX = bpy.data.textures.new("dents", type='CLOUDS')
        DENT_TEX.noise_scale = size
        DENT_TEX.noise_depth = 2
    sub = ob.modifiers.new(name="dentsub", type='SUBSURF')
    sub.subdivision_type = 'SIMPLE'
    sub.levels = 3
    sub.render_levels = 3
    mod = ob.modifiers.new(name="dents", type='DISPLACE')
    mod.texture = DENT_TEX
    # 2.2x the asked-for strength: at sprite scale anything subtler vanishes
    mod.strength = strength * 2.2
    mod.mid_level = 0.5
    mod.texture_coords = 'GLOBAL'
    return ob


def bevel(ob, width=0.012, segments=2, angle=40.0):
    mod = ob.modifiers.new(name="bevel", type='BEVEL')
    mod.width = width
    mod.segments = segments
    mod.limit_method = 'ANGLE'
    mod.angle_limit = math.radians(angle)
    return ob


def box(name, sx, sy, sz, loc, rot=(0, 0, 0), mat="steel", bev=0.012, dents=0.0):
    bpy.ops.mesh.primitive_cube_add(radius=0.5, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (sx, sy, sz)
    apply_scale(ob)
    if bev:
        bevel(ob, bev)
    if dents:
        add_dents(ob, dents)
    ob.data.materials.append(MATS[mat])
    return ob


def cyl(name, r, depth, loc, rot=(0, 0, 0), mat="steel", verts=18, smooth=True,
        bev=0.008, taper=None, dents=0.0):
    if taper is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                            location=loc, rotation=rot)
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=taper,
                                        depth=depth, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if bev:
        bevel(ob, bev, segments=1)
    if dents:
        add_dents(ob, dents)
    if smooth:
        activate(ob)
        bpy.ops.object.shade_smooth()
        ob.data.use_auto_smooth = True
        ob.data.auto_smooth_angle = math.radians(35)
    ob.data.materials.append(MATS[mat])
    return ob


def torus(name, major, minor, loc, rot=(math.pi / 2, 0, 0), mat="steel",
          maj_seg=20, min_seg=8):
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=minor,
                                     major_segments=maj_seg, minor_segments=min_seg,
                                     location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    activate(ob)
    bpy.ops.object.shade_smooth()
    ob.data.materials.append(MATS[mat])
    return ob


def tube(name, points, radius, mat="rubber", res=6):
    curve = bpy.data.curves.new(name + "_c", type='CURVE')
    curve.dimensions = '3D'
    curve.bevel_depth = radius
    curve.bevel_resolution = res
    curve.resolution_u = 6
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(len(points) - 1)
    for bp, co in zip(spline.bezier_points, points):
        bp.co = Vector(co)
        bp.handle_left_type = 'AUTO'
        bp.handle_right_type = 'AUTO'
    ob = bpy.data.objects.new(name, curve)
    link(ob)
    ob.data.materials.append(MATS[mat])
    activate(ob)
    bpy.ops.object.convert(target='MESH')
    return bpy.context.active_object


def weld(name, loc, sx, sy, sz=0.035, rot=(0, 0, 0), mat="cast"):
    """A raised welded seam: a thin bead that catches light along the join."""
    return box(name, sx, sy, sz, loc, rot=rot, mat=mat, bev=0.008)


def bolt_ring(prefix, center, radius, count, plane, mat="steel_dark", size=0.045,
              depth=0.05, start=0.0, axis='Z'):
    out = []
    for i in range(count):
        a = start + 2 * math.pi * i / count
        dx, dy = math.cos(a) * radius, math.sin(a) * radius
        if axis == 'Z':
            loc, rot = (center[0] + dx, center[1] + dy, plane), (0, 0, 0)
        else:
            loc, rot = (center[0] + dx, plane, center[1] + dy), (math.pi / 2, 0, 0)
        out.append(cyl("{}_{}".format(prefix, i), size, depth, loc, rot=rot,
                       mat=mat, verts=6, bev=0.0, smooth=False))
    return out


# ------------------------------------------------------------ the machine ---
def build_hull():
    """Static emplacement, origin at the turret pivot, ground at z = 0:
    octagonal cast pedestal, layered armour wedges, deck machinery, heavy
    turntable bearing. Two pipe stubs sit at +-1.2 tiles to line up with
    fluid_box.pipe_connections."""
    parts = []
    parts.append(cyl("hull_foot", 1.52, 0.07, (0, 0, 0.035), verts=8, mat="cast",
                     bev=0.02, smooth=False, dents=0.014))
    parts.append(cyl("hull_skirt", 1.44, 0.16, (0, 0, 0.15), verts=8, mat="steel",
                     bev=0.02, smooth=False, dents=0.018))
    parts.append(cyl("hull_deck", 1.16, 0.14, (0, 0, 0.29), verts=8, mat="cast",
                     bev=0.018, smooth=False, dents=0.014))
    # layered armour wedges around the skirt -- eight plates, each slightly off
    for i in range(8):
        a = 2 * math.pi * i / 8 + math.pi / 8
        r = 1.30
        parts.append(box("hull_plate{}".format(i), 0.62, 0.10, 0.15,
                         (math.cos(a) * r, math.sin(a) * r, 0.12),
                         rot=(0, 0, a + math.pi / 2 + rng.uniform(-0.03, 0.03)),
                         mat="steel", bev=0.008, dents=0.008))
        parts.append(weld("hull_weld{}".format(i), (math.cos(a) * 1.40,
                                                   math.sin(a) * 1.40, 0.225),
                          0.55, 0.05, 0.04, rot=(0, 0, a + math.pi / 2)))
    # buttresses tying the skirt to the deck
    for i, a in enumerate((0.6, 1.9, 3.6, 5.2)):
        parts.append(box("hull_buttress{}".format(i), 0.30, 0.58, 0.20,
                         (math.cos(a) * 0.98, math.sin(a) * 0.98, 0.26),
                         rot=(0, 0, a + rng.uniform(-0.05, 0.05)),
                         mat="cast", bev=0.01, dents=0.012))

    # ---- turntable bearing ------------------------------------------------
    parts.append(cyl("hull_ring", 0.82, 0.20, (0, 0, 0.40), mat="steel_dark",
                     verts=20, bev=0.014, dents=0.008))
    parts.append(torus("hull_ring_lip", 0.82, 0.05, (0, 0, 0.50), rot=(0, 0, 0),
                       mat="steel", maj_seg=24, min_seg=6))
    parts.append(cyl("hull_ring_inner", 0.64, 0.10, (0, 0, 0.34), mat="steel_dark",
                     verts=20, bev=0.006))
    # the bearing well is fully visible whenever the gun points away, so it gets
    # spokes, a hub cover and fittings instead of being a flat dark disc
    for i in range(4):
        a = math.pi / 4 + i * math.pi / 2
        parts.append(box("hull_spoke{}".format(i), 0.62, 0.14, 0.10,
                         (0, 0, 0.40), rot=(0, 0, a), mat="cast", bev=0.008,
                         dents=0.008))
    parts.append(cyl("hull_hub", 0.26, 0.10, (0, 0, 0.44), mat="steel_dark",
                     verts=16, bev=0.008))
    parts.extend(bolt_ring("hull_hub_bolt", (0, 0), 0.20, 6, 0.50, size=0.035,
                           depth=0.05))
    parts.append(cyl("hull_well_fitting", 0.10, 0.14, (0.42, 0.42, 0.44),
                     mat="copper", verts=12))
    parts.append(tube("hull_well_hose", [(0.40, 0.40, 0.46), (0.26, 0.52, 0.50),
                                        (0.05, 0.58, 0.44), (-0.12, 0.50, 0.36)],
                      0.035, mat="rubber"))
    parts.extend(bolt_ring("hull_bolt", (0, 0), 0.92, 16, 0.32, size=0.05, depth=0.07))
    # gothic-ish bearing brackets: four chunky ribs climbing onto the ring
    for i, a in enumerate((0.0, math.pi / 2, math.pi, 1.5 * math.pi)):
        parts.append(box("hull_bracket{}".format(i), 0.22, 0.30, 0.26,
                         (math.cos(a) * 0.86, math.sin(a) * 0.86, 0.40),
                         rot=(0, 0, a), mat="cast", bev=0.012, dents=0.01))

    # ---- deck machinery, deliberately asymmetric --------------------------
    parts.append(box("hull_pump", 0.54, 0.74, 0.36, (-0.98, 0.0, 0.46),
                     rot=(0, 0, 0.06), mat="steel", bev=0.016, dents=0.014))
    parts.append(box("hull_pump_cap", 0.46, 0.62, 0.07, (-0.98, 0.0, 0.67),
                     rot=(0, 0, 0.06), mat="cast", bev=0.01))
    for i in range(3):
        parts.append(box("hull_pump_fin{}".format(i), 0.42, 0.05, 0.11,
                         (-0.98, -0.23 + i * 0.23, 0.72), rot=(0, 0, 0.06),
                         mat="steel_dark", bev=0.006))
    # fuel stubs at +-X, aligned with fluid_box.pipe_connections (+-1.2 tiles)
    for sign, tag in ((-1, "w"), (1, "e")):
        parts.append(cyl("hull_pipe{}_flange".format(tag), 0.18, 0.10,
                         (sign * 1.12, 0, 0.46), rot=(0, math.pi / 2, 0),
                         mat="copper", verts=14))
        parts.append(cyl("hull_pipe{}".format(tag), 0.12, 0.32,
                         (sign * 1.29, 0, 0.46), rot=(0, math.pi / 2, 0),
                         mat="copper", verts=14))
        parts.append(cyl("hull_pipe{}_rim".format(tag), 0.15, 0.05,
                         (sign * 1.43, 0, 0.46), rot=(0, math.pi / 2, 0),
                         mat="steel_dark", verts=14))
        parts.append(box("hull_pipe{}_clamp".format(tag), 0.08, 0.30, 0.30,
                         (sign * 1.20, 0, 0.40), mat="cast", bev=0.008))
    parts.append(tube("hull_hose_w", [(-1.04, 0.34, 0.58), (-0.90, 0.48, 0.72),
                                      (-0.60, 0.32, 0.78), (-0.42, 0.14, 0.66)],
                      0.055, mat="rubber"))
    parts.append(tube("hull_hose_e", [(1.04, -0.32, 0.58), (0.94, -0.50, 0.68),
                                      (0.64, -0.46, 0.76), (0.46, -0.26, 0.64)],
                      0.05, mat="rubber"))

    # radiator / vent stack, north-east
    parts.append(box("hull_vent", 0.58, 0.46, 0.38, (0.88, 0.80, 0.46),
                     rot=(0, 0, -0.35), mat="steel_dark", bev=0.012, dents=0.012))
    for i in range(4):
        parts.append(box("hull_vent_slat{}".format(i), 0.48, 0.05, 0.05,
                         (0.88, 0.67 + i * 0.08, 0.65), rot=(0, 0, -0.35),
                         mat="steel", bev=0.005))
    parts.append(torus("hull_vent_fan", 0.17, 0.032, (0.88, 0.80, 0.665),
                       rot=(0, 0, 0), mat="steel", maj_seg=16, min_seg=5))

    # coolant canister, south-east
    parts.append(cyl("hull_tank", 0.25, 0.44, (0.82, -0.80, 0.50), mat="red",
                     verts=16, bev=0.01))
    for z in (0.34, 0.50, 0.66):
        parts.append(torus("hull_tank_band{}".format(int(z * 100)), 0.255, 0.022,
                           (0.82, -0.80, z), rot=(0, 0, 0), mat="steel_dark",
                           maj_seg=16, min_seg=5))
    parts.append(cyl("hull_tank_cap", 0.09, 0.10, (0.82, -0.80, 0.75), mat="copper",
                     verts=12))

    # crate, south-west, kicked out of alignment
    parts.append(box("hull_crate", 0.44, 0.36, 0.26, (-0.76, -0.82, 0.40),
                     rot=(0, 0, 0.42), mat="yellow", bev=0.008, dents=0.016))
    parts.append(box("hull_crate_lid", 0.46, 0.38, 0.05, (-0.76, -0.82, 0.545),
                     rot=(0, 0, 0.42), mat="steel_dark", bev=0.006))
    for i in range(2):
        parts.append(box("hull_crate_band{}".format(i), 0.46, 0.06, 0.05,
                         (-0.76, -0.82 - 0.10 + i * 0.20, 0.52), rot=(0, 0, 0.42),
                         mat="steel_dark", bev=0.004))

    # hydraulic rams on one side only (asymmetry)
    for i, (a, tilt) in enumerate(((2.35, -0.35), (3.05, -0.5))):
        parts.append(cyl("hull_ram{}".format(i), 0.075, 0.52,
                         (math.cos(a) * 0.74, math.sin(a) * 0.74, 0.32),
                         rot=(tilt, 0, a), mat="steel", verts=12))
        parts.append(cyl("hull_ram{}_rod".format(i), 0.042, 0.34,
                         (math.cos(a) * 0.56, math.sin(a) * 0.56, 0.43),
                         rot=(tilt, 0, a), mat="copper", verts=10))

    # hazard stripes, chipped to hell
    parts.append(box("hull_hazard", 1.14, 0.10, 0.11, (0, -1.42, 0.13),
                     mat="yellow", bev=0.006, dents=0.008))
    parts.append(box("hull_hazard2", 0.36, 0.10, 0.11, (1.18, -0.62, 0.13),
                     rot=(0, 0, 0.75), mat="yellow", bev=0.006))
    parts.append(box("hull_hazard3", 0.30, 0.09, 0.09, (-1.34, 0.52, 0.13),
                     rot=(0, 0, -0.9), mat="yellow", bev=0.006))

    # rivets across the skirt and deck
    for i in range(24):
        a = 2 * math.pi * i / 24 + 0.11
        r = 1.36 if i % 2 else 1.06
        z = 0.16 if i % 2 else 0.35
        parts.append(cyl("hull_rivet{}".format(i), 0.036, 0.05,
                         (math.cos(a) * r, math.sin(a) * r, z),
                         mat="steel_dark", verts=6, bev=0.0, smooth=False))
    return parts


def build_gun(root):
    """The cannon. Short, wide-bore heat projector: chunky breech, armoured
    mantlet, ribbed copper heat coils, vented shroud, slotted muzzle brake with a
    white-hot bore. Points +Y at rest; every part parents to `root`."""
    parts = []
    Z = GUN_Z

    # ---- pivot collar seated in the bearing ---------------------------------
    parts.append(cyl("gun_collar", 0.68, 0.18, (0, 0, 0.58), mat="steel_dark",
                     verts=24, bev=0.012))
    parts.append(torus("gun_collar_lip", 0.68, 0.038, (0, 0, 0.68), rot=(0, 0, 0),
                       mat="cast", maj_seg=24, min_seg=6))
    parts.extend(bolt_ring("gun_collar_bolt", (0, 0), 0.56, 12, 0.68, size=0.04,
                           depth=0.05))

    # ---- breech: the chunky mass behind the barrel -------------------------
    parts.append(box("gun_breech", 0.84, 0.96, 0.62, (0, -0.18, Z - 0.06),
                     mat="cast", bev=0.022, dents=0.02))
    parts.append(box("gun_breech_top", 0.62, 0.74, 0.16, (0, -0.20, Z + 0.28),
                     mat="steel", bev=0.016, dents=0.014))
    parts.append(box("gun_breech_rear", 0.70, 0.18, 0.50, (0, -0.64, Z - 0.04),
                     rot=(0.08, 0, 0), mat="steel_dark", bev=0.016, dents=0.016))
    # heat-exchanger fin stack, both sides of the breech (melta heat sink)
    for sign in (-1, 1):
        for i in range(5):
            parts.append(box("gun_fin{}x{}".format(sign, i), 0.07, 0.52, 0.05,
                             (sign * 0.47, -0.30, 0.56 + i * 0.075),
                             rot=(0, 0, 0), mat="steel_dark", bev=0.005))
        parts.append(box("gun_fin_plate{}".format(sign), 0.05, 0.60, 0.44,
                         (sign * 0.45, -0.30, 0.70), mat="cast", bev=0.01,
                         dents=0.008))
    # feed block + cap on the rear face
    parts.append(cyl("gun_feed", 0.22, 0.36, (0.0, -0.80, Z + 0.04),
                     rot=(math.pi / 2, 0, 0), mat="steel", verts=14))
    parts.append(cyl("gun_feed_cap", 0.25, 0.06, (0.0, -0.99, Z + 0.04),
                     rot=(math.pi / 2, 0, 0), mat="copper", verts=14))
    parts.extend(bolt_ring("gun_breech_bolt", (0, -0.18), 0.36, 8, Z + 0.20,
                           size=0.044, depth=0.055))

    # ---- armoured mantlet: the brutal plate the barrel comes out of --------
    parts.append(box("gun_mantlet", 0.96, 0.22, 0.70, (0, 0.34, Z - 0.02),
                     mat="cast", bev=0.02, dents=0.016))
    for i, x in enumerate((-0.34, -0.12, 0.12, 0.34)):
        parts.append(box("gun_mantlet_rib{}".format(i), 0.10, 0.08, 0.66,
                         (x, 0.44, Z - 0.02), mat="steel_dark", bev=0.006))
    parts.append(box("gun_mantlet_lip", 1.0, 0.10, 0.10, (0, 0.44, Z + 0.34),
                     mat="steel_dark", bev=0.008, dents=0.008))
    # trunnions: the barrel visibly hangs off these, so it cannot read as floating
    for sign in (-1, 1):
        parts.append(cyl("gun_trunnion{}".format(sign), 0.16, 0.16,
                         (sign * 0.52, 0.34, Z - 0.02), rot=(0, math.pi / 2, 0),
                         mat="cast", verts=14))
        parts.append(cyl("gun_trunnion_cap{}".format(sign), 0.09, 0.06,
                         (sign * 0.60, 0.34, Z - 0.02), rot=(0, math.pi / 2, 0),
                         mat="steel_dark", verts=12))
    # collar where the barrel leaves the mantlet
    parts.append(cyl("gun_barrel_collar", 0.31, 0.12, (0, 0.50, Z),
                     rot=(math.pi / 2, 0, 0), mat="steel_dark", verts=18, bev=0.008))

    # ---- ribbed copper heat coils -----------------------------------------
    for i, (y, R) in enumerate(((0.50, 0.40), (0.62, 0.415), (0.74, 0.405),
                                (0.86, 0.395), (0.98, 0.375))):
        parts.append(torus("gun_coil{}".format(i), R, 0.072, (0, y, Z),
                           rot=(math.pi / 2, 0, 0), mat="copper",
                           maj_seg=24, min_seg=8))
    # glow collar between the coils: a full ring, so it reads from every angle
    parts.append(cyl("gun_glow_core", 0.36, 0.50, (0, 0.74, Z),
                     rot=(math.pi / 2, 0, 0), mat="glow_dim", verts=20, bev=0.0))
    for i in (1, 2, 3):
        parts.append(torus("gun_glow{}".format(i), 0.385, 0.022,
                           (0, 0.50 + i * 0.12, Z), rot=(math.pi / 2, 0, 0),
                           mat="glow", maj_seg=20, min_seg=5))

    # ---- vented heat shroud -----------------------------------------------
    parts.append(cyl("gun_shroud", 0.34, 0.34, (0, 1.14, Z),
                     rot=(math.pi / 2, 0, 0), mat="steel_dark", verts=18, bev=0.0))
    for i in range(3):
        parts.append(torus("gun_shroud_rib{}".format(i), 0.36, 0.032,
                           (0, 1.03 + i * 0.12, Z), rot=(math.pi / 2, 0, 0),
                           mat="cast", maj_seg=20, min_seg=5))
    for i in range(4):
        y = 1.02 + i * 0.10
        parts.append(box("gun_vent{}".format(i), 0.34, 0.04, 0.07,
                         (0, y, Z + 0.32), mat="grime", bev=0.004))
        parts.append(box("gun_vent_l{}".format(i), 0.04, 0.035, 0.13,
                         (-0.33, y, Z + 0.18), mat="grime", bev=0.004))
        parts.append(box("gun_vent_r{}".format(i), 0.04, 0.035, 0.13,
                         (0.33, y, Z + 0.18), mat="grime", bev=0.004))

    # ---- barrel and wide-bore muzzle projector ----------------------------
    parts.append(cyl("gun_barrel", 0.26, 0.46, (0, 1.32, Z),
                     rot=(-math.pi / 2, 0, 0), mat="steel", verts=18, taper=0.24,
                     bev=0.0))
    parts.append(cyl("gun_barrel_band", 0.28, 0.05, (0, 1.40, Z),
                     rot=(math.pi / 2, 0, 0), mat="steel_dark", verts=18))
    # The melta signature: a short barrel that flares into a wide heat projector.
    # The flare widens forward (rot -pi/2 puts the cone's wide cap at +Y).
    parts.append(cyl("gun_flare", 0.28, 0.30, (0, 1.60, Z),
                     rot=(-math.pi / 2, 0, 0), mat="cast", verts=20, taper=0.52,
                     bev=0.01, dents=0.008))
    parts.append(torus("gun_mouth_lip", 0.50, 0.042, (0, 1.76, Z),
                       rot=(math.pi / 2, 0, 0), mat="cast", maj_seg=24, min_seg=6))
    # throat: a cone read as the inside of the projector, dark, with the hot core
    parts.append(cyl("gun_throat", 0.42, 0.18, (0, 1.70, Z),
                     rot=(math.pi / 2, 0, 0), mat="grime", verts=20, taper=0.24,
                     bev=0.0))
    parts.append(cyl("gun_bore_ring", 0.30, 0.04, (0, 1.68, Z),
                     rot=(math.pi / 2, 0, 0), mat="glow_dim", verts=20, bev=0.0))
    parts.append(cyl("gun_bore_hot", 0.20, 0.04, (0, 1.64, Z),
                     rot=(math.pi / 2, 0, 0), mat="glow", verts=18, bev=0.0))
    # radiating heat-sink fins around the projector mouth
    for i in range(6):
        a = 2 * math.pi * i / 6 + 0.26
        parts.append(box("gun_mouth_fin{}".format(i), 0.075, 0.20, 0.16,
                         (math.cos(a) * 0.44, 1.52, Z + math.sin(a) * 0.44),
                         rot=(0, 0, a), mat="steel_dark", bev=0.006))
    parts.extend(bolt_ring("gun_mouth_bolt", (0.0, Z), 0.60, 8, 1.50,
                           size=0.034, depth=0.06, axis='Y'))

    # ---- hydraulics, sight, hose: the asymmetry ---------------------------
    parts.append(cyl("gun_piston", 0.085, 0.66, (-0.46, 0.24, Z - 0.24),
                     rot=(math.pi / 2, 0, 0), mat="steel", verts=12))
    parts.append(cyl("gun_piston_rod", 0.048, 0.40, (-0.46, 0.72, Z - 0.24),
                     rot=(math.pi / 2, 0, 0), mat="copper", verts=10))
    parts.append(cyl("gun_piston_mount", 0.10, 0.12, (-0.46, -0.12, Z - 0.24),
                     rot=(math.pi / 2, 0, 0), mat="cast", verts=12))
    parts.append(box("gun_sight", 0.18, 0.40, 0.15, (0.42, 0.02, Z + 0.40),
                     rot=(0, 0, -0.10), mat="steel_dark", bev=0.01, dents=0.008))
    parts.append(cyl("gun_sight_lens", 0.06, 0.03, (0.42, 0.24, Z + 0.40),
                     rot=(math.pi / 2, 0, 0), mat="glow_dim", verts=12, bev=0.0))
    parts.append(tube("gun_hose", [(-0.36, -0.70, Z + 0.16), (-0.54, -0.36, Z + 0.34),
                                   (-0.52, 0.20, Z + 0.30), (-0.36, 0.62, Z + 0.12)],
                      0.055, mat="rubber"))
    for i, (y, z) in enumerate(((-0.40, Z + 0.32), (0.10, Z + 0.32))):
        parts.append(box("gun_hose_clamp{}".format(i), 0.10, 0.10, 0.10,
                         (-0.52, y, z), mat="cast", bev=0.006))
    for sign in (-1, 1):
        parts.append(box("gun_gusset{}".format(sign), 0.06, 0.40, 0.26,
                         (sign * 0.43, 0.04, Z - 0.14), mat="cast", bev=0.006,
                         dents=0.01))
    parts.append(weld("gun_weld", (0, 0.44, Z - 0.32), 0.90, 0.06, 0.04))
    # a bent, half-detached armour flap: evidence it has been shot at
    parts.append(box("gun_flap", 0.28, 0.18, 0.025, (-0.46, -0.52, Z + 0.24),
                     rot=(0.22, 0.1, 0.3), mat="yellow", bev=0.004, dents=0.022))
    parts.append(box("gun_scrape", 0.30, 0.06, 0.02, (0.30, -0.52, Z + 0.28),
                     rot=(0, 0, 0.2), mat="steel", bev=0.003))

    for ob in parts:
        ob.parent = root
        ob.matrix_parent_inverse = root.matrix_world.inverted()
    return parts


# ------------------------------------------------------- camera & lights ----
def setup_camera():
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = 'ORTHO'
    cam_data.ortho_scale = TILES_IN_FRAME
    cam = bpy.data.objects.new("cam", cam_data)
    link(cam)
    cam.rotation_euler = (TILT, 0, 0)
    view_dir = Vector((0.0, math.sin(TILT), -math.cos(TILT)))
    cam.location = view_dir * -22.0
    bpy.context.scene.camera = cam
    return cam


def add_sun(name, direction, energy, color, angle_deg=6.0, spec=1.0):
    lamp = bpy.data.lamps.new(name, type='SUN')
    lamp.energy = energy * SUN_SCALE
    lamp.color = color
    if hasattr(lamp, "shadow_soft_size"):
        lamp.shadow_soft_size = math.radians(angle_deg)
    elif hasattr(lamp, "angle"):
        lamp.angle = math.radians(angle_deg)
    if hasattr(lamp, "specular_factor"):
        lamp.specular_factor = spec
    ob = bpy.data.objects.new(name, lamp)
    link(ob)
    d = Vector(direction).normalized()
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


def setup_lights():
    # Key from upper-left, tipped toward the viewer: vanilla's sun direction, so
    # shadows fall to the lower right. Energies are set hot on purpose -- the
    # luminance check (vanilla turret art: p50 ~25, p90 ~120) needs a wide range,
    # so ambient stays low and the key does the work.
    add_sun("key", (0.58, 0.32, -1.0), 8.0, (1.0, 0.96, 0.89), angle_deg=8.0)
    add_sun("fill", (-0.55, -0.45, -0.55), 0.30, (0.72, 0.80, 1.0), angle_deg=20.0,
            spec=0.20)
    add_sun("bounce", (0.0, -0.12, 1.0), 0.10, (0.55, 0.50, 0.42), angle_deg=32.0,
            spec=0.0)
    add_sun("rim", (-0.30, 0.72, -0.35), 0.30, (0.80, 0.84, 0.95), angle_deg=16.0,
            spec=0.5)
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("world")
        bpy.context.scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.030, 0.034, 0.042, 1.0)
    bg.inputs["Strength"].default_value = 0.22 * WORLD_SCALE
    if argval("--worldred", "0") == "1":
        bg.inputs["Color"].default_value = (1.0, 0.0, 0.0, 1.0)
        print("DIAG world forced red")


def setup_render():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = SAMPLES
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transmission_bounces = 2
    scene.cycles.transparent_max_bounces = 8
    scene.cycles.filter_width = 1.7
    scene.cycles.sample_clamp_indirect = 2.0
    scene.cycles.film_transparent = True
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.image_settings.compression = 15
    scene.view_settings.view_transform = 'Default'
    scene.render.threads_mode = 'AUTO'


# ------------------------------------------------------------------- main ---
def main():
    purge()
    build_materials()
    setup_render()
    setup_camera()
    setup_lights()

    hull = build_hull()
    root = bpy.data.objects.new("gun_root", None)
    link(root)
    gun = build_gun(root)
    # scale AFTER parenting: build_gun stores the parent's inverse matrix, so setting
    # the scale first would be cancelled out and the gun would render full size
    root.scale = (GUN_SCALE, GUN_SCALE, GUN_SCALE)

    # one-line diagnostics: confirms the lights/world actually made it into the scene
    lamps = [(o.name, o.type, round(o.data.energy, 2)) for o in bpy.context.scene.objects
             if o.type == 'LAMP']
    bg = bpy.context.scene.world.node_tree.nodes.get("Background") \
        if bpy.context.scene.world and bpy.context.scene.world.use_nodes else None
    print("DIAG sunscale={} lamps={} world={} strength={}".format(
        SUN_SCALE, lamps,
        tuple(round(c, 3) for c in bg.inputs["Color"].default_value) if bg else None,
        round(bg.inputs["Strength"].default_value, 3) if bg else None))
    from collections import Counter
    print("DIAG objects", Counter(o.type for o in bpy.context.scene.objects))
    print("DIAG lamps in data", [(l.name, l.energy) for l in bpy.data.lamps])
    print("DIAG emit_scale", EMIT_SCALE, "film_transparent", bpy.context.scene.cycles.film_transparent)
    if argval("--hidelamps", "0") == "1":
        for ob in scene.objects:
            if ob.type == 'LAMP':
                ob.hide_render = True
        print("DIAG lamps hidden")
    w = bpy.context.scene.world
    print("DIAG world nodes", [(n.name, n.type) for n in w.node_tree.nodes],
          "links", [(l.from_node.name, l.to_node.name) for l in w.node_tree.links],
          "use_nodes", w.use_nodes)
    print("DIAG coloursampling", bpy.context.scene.cycles.use_preview_adaptive_sampling
          if hasattr(bpy.context.scene.cycles, "use_preview_adaptive_sampling") else "n/a")

    os.makedirs(os.path.join(OUT_DIR, "gun"), exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "base"), exist_ok=True)
    scene = bpy.context.scene

    if DIR_ARG == "all":
        dirs = list(range(DIRECTIONS))
    elif DIR_ARG in ("", "none", "base"):
        # base pass only -- the hull sprite is a single still, so a hull-only change
        # does not need the 64 head frames re-rendered
        dirs = []
    else:
        dirs = [int(x) for x in DIR_ARG.split(",")]

    # base sprite: hull only
    for ob in gun + [root]:
        ob.hide_render = True
    if FLATMAT:
        flat = bpy.data.materials.new("flatmat")
        flat.use_nodes = True
        nt = flat.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        o = nt.nodes.new("ShaderNodeOutputMaterial")
        b = nt.nodes.new("ShaderNodeBsdfDiffuse")
        b.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
        nt.links.new(b.outputs["BSDF"], o.inputs["Surface"])
        bpy.context.scene.render.layers[0].material_override = flat
    scene.render.filepath = os.path.join(OUT_DIR, "base", "hull.png")
    bpy.ops.render.render(write_still=True)

    # head sprites: gun only, hull hidden
    for ob in gun + [root]:
        ob.hide_render = False
    for ob in hull:
        ob.hide_render = True
    if ONLY:
        keep = ONLY.split(",")
        for ob in scene.objects:
            if ob.type == 'MESH' and ob.name not in keep:
                ob.hide_render = True

    for d in dirs:
        root.rotation_euler = (0, 0, -2.0 * math.pi * d / DIRECTIONS)
        scene.render.filepath = os.path.join(OUT_DIR, "gun", "gun-{:03d}.png".format(d))
        bpy.ops.render.render(write_still=True)
        print("rendered direction", d)

    meta = {
        "frame_px": FRAME,
        "render_px": RES,
        "tiles_in_frame": TILES_IN_FRAME,
        "art_px_per_tile": FRAME / TILES_IN_FRAME,
        "tilt_degrees": round(math.degrees(TILT), 2),
        "directions": DIRECTIONS,
        "gun_scale": GUN_SCALE,
        "pivot": "image centre -> sprite shift {0, 0}",
        # measured off the model, already multiplied by GUN_SCALE: the muzzle is the
        # front face of the heat projector, which is what the beam starts from
        "muzzle_offset_tiles": round(1.80 * GUN_SCALE, 3),
        "barrel_length_tiles": round((1.80 - (-1.02)) * GUN_SCALE, 3),
        "gun_extent_tiles": {"muzzle_y": round(1.80 * GUN_SCALE, 3),
                             "rear_y": round(-1.02 * GUN_SCALE, 3),
                             "half_width": round(0.50 * GUN_SCALE, 3),
                             "top_z": round(1.36 * GUN_SCALE, 3)},
        "hull_extent_tiles": {"radius": 1.56, "top_z": 0.52},
    }
    with open(os.path.join(OUT_DIR, "meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    print("META", json.dumps(meta))


if __name__ == "__main__":
    main()
