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
# ---- lighting: emissive geometry only -------------------------------------
# Cycles in this Blender build ignores LAMP energy completely. Measured:
# `--sunscale 0` and `--sunscale 1` render pixel-identical, and replacing the suns
# with AREA lamps at 300 / 800 / 1500 W also renders pixel-identical (probe_rig.py
# prints the luma table). The one source that provably works is EMISSIVE GEOMETRY --
# the glow parts visibly light their neighbours -- so the rig is three emissive
# softboxes (warm key upper-left, cool fill right, cool rim behind). Strengths are
# irradiance-like numbers, not watts: a 5-tile plane ~8 tiles away needs ~0.3 to lift
# the hull to vanilla's luma band, and 2.2 blows the frame to pure white.
RIG = {"key": 5.0, "fill": 1.5, "rim": 2.5}
for _k in ("key", "fill", "rim"):
    RIG[_k] = float(argval("--rig" + _k, str(RIG[_k])))
KEYPOWER = float(argval("--keypower", "1.0"))     # master scale, 0 = no rig at all
AOMIX = float(argval("--aomix", "0.35"))
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
    m_patch.inputs["Fac"].default_value = 0.34
    links.new(m_wear.outputs["Color"], m_patch.inputs["Color1"])
    links.new(patch_ramp.outputs["Color"], m_patch.inputs["Fac"])
    m_patch.inputs["Color2"].default_value = (half[0] * 1.02, half[1] * 1.02,
                                             half[2] * 1.02, 1)

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

    # ---- ambient occlusion: a shader closure, mixed under the BSDF ---------
    # Cycles 2.79's AmbientOcclusion node is a *shader* (one Color input, one AO
    # closure output), not a texture node: wiring that closure into a ColorRamp
    # raises "can only connect closure to closure (AmbientOcclusion.AO to
    # ColorRamp.Fac)" and the whole AO stage silently does nothing -- which is what
    # the shipped 0.5.0 art was doing. Since this build also ignores lamp.energy for
    # Cycles (--sunscale 0 and 1 render pixel-identical, measured), the AO closure is
    # the only geometric shading term available, so it is mixed in as a shader, which
    # is the one shape that works. AO_MIX is the weight; 0 disables it.
    links.new(m_grain.outputs["Color"], bsdf.inputs["Base Color"])
    shader_src = bsdf.outputs["BSDF"]
    if AOMIX > 0:
        ao = nodes.new("ShaderNodeAmbientOcclusion")
        # the closure's Color input is the colour of the ambient term it shades with
        for sock in ao.inputs:
            if sock.name == "Color":
                sock.default_value = (0.78, 0.75, 0.70, 1.0)
        mix_ao = nodes.new("ShaderNodeMixShader")
        mix_ao.inputs[0].default_value = AOMIX
        links.new(shader_src, mix_ao.inputs[1])
        links.new(ao.outputs["AO"], mix_ao.inputs[2])
        shader_src = mix_ao.outputs["Shader"]

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
        links.new(shader_src, mix.inputs[0])
        links.new(emit.outputs["Emission"], mix.inputs[1])
        links.new(mix.outputs["Shader"], out.inputs["Surface"])

    return mat


MATS = {}


def build_materials():
    """Palette sits next to vanilla gun/laser/flamethrower turret sprites.

    Measured off vanilla (stats.py --vanilla): the gun turret head is mean luma 75
    with a strong warm bias (r-b = +27), the flamethrower hull mean 56-60 and warm as
    well. The previous palette here was a cool blue-grey (r-b = +12) and every body
    value sat one step darker, which is why the turret read as a dark grey object next
    to vanilla turrets. So: mid-value warm gunmetal for the body, near-black for the
    recesses, brass/copper for everything that carries fluid, and the orange emissive
    kept to the vents and gauge lights.
    """
    MATS["steel"] = weathered_material("steel", paint=(0.300, 0.278, 0.246),
                                       metal=(0.520, 0.495, 0.455),
                                       half=(0.355, 0.335, 0.302),
                                       rough=0.52, chip=0.42, rust_amt=0.40)
    MATS["steel_dark"] = weathered_material("steel_dark", paint=(0.135, 0.126, 0.114),
                                            metal=(0.250, 0.238, 0.220),
                                            half=(0.300, 0.282, 0.256),
                                            rough=0.60, chip=0.30, rust_amt=0.35)
    MATS["cast"] = weathered_material("cast", paint=(0.310, 0.292, 0.258),
                                      metal=(0.520, 0.492, 0.446),
                                      half=(0.345, 0.326, 0.292),
                                      rough=0.68, chip=0.55, rust_amt=0.48,
                                      noise_scale=17.0, metallic=0.32)
    MATS["yellow"] = weathered_material("yellow", paint=(0.620, 0.420, 0.080),
                                        metal=(0.360, 0.240, 0.065),
                                        rust=(0.200, 0.085, 0.032),
                                        half=(0.620, 0.500, 0.240),
                                        rough=0.58, chip=0.80, rust_amt=0.72,
                                        noise_scale=15.0, metallic=0.35)
    MATS["red"] = weathered_material("red", paint=(0.420, 0.080, 0.045),
                                     metal=(0.270, 0.090, 0.048),
                                     rust=(0.180, 0.075, 0.030),
                                     half=(0.470, 0.250, 0.200),
                                     rough=0.62, chip=0.75, rust_amt=0.62,
                                     noise_scale=13.0, metallic=0.40)
    # brass-into-copper: the fluid hardware (tank, compressor, turbine, feed lines,
    # vent rims) is the only saturated thing on the model, so it has to be a real
    # brass value rather than a dark brown, or it reads as rust instead of plumbing
    MATS["brass"] = weathered_material("brass", paint=(0.470, 0.330, 0.115),
                                       metal=(0.640, 0.450, 0.160),
                                       rust=(0.230, 0.130, 0.045),
                                       half=(0.600, 0.472, 0.236),
                                       rough=0.46, chip=0.22, rust_amt=0.26,
                                       noise_scale=20.0, metallic=0.78)
    MATS["copper"] = weathered_material("copper", paint=(0.400, 0.200, 0.090),
                                        metal=(0.560, 0.300, 0.130),
                                        half=(0.520, 0.330, 0.186),
                                        rough=0.54, chip=0.16, rust_amt=0.32,
                                        noise_scale=22.0, metallic=0.70)
    # hot-metal rim: dark iron that is *hot*, not a lamp. Emission stays low enough
    # that it reads as glowing metal inside the vents instead of a white hole.
    MATS["hotmetal"] = weathered_material("hotmetal", paint=(0.150, 0.072, 0.042),
                                          metal=(0.220, 0.120, 0.070),
                                          half=(0.260, 0.150, 0.085),
                                          rough=0.55, chip=0.10, rust_amt=0.20,
                                          metallic=0.55,
                                          emissive=(1.0, 0.17, 0.025),
                                          emissive_strength=1.60)
    MATS["rubber"] = weathered_material("rubber", paint=(0.030, 0.029, 0.028),
                                        metal=(0.042, 0.041, 0.040), rough=0.86,
                                        chip=0.0, rust_amt=0.0, metallic=0.0, bump=0.40)
    MATS["grime"] = weathered_material("grime", paint=(0.014, 0.013, 0.012),
                                       metal=(0.020, 0.018, 0.016), rough=0.95,
                                       chip=0.0, rust_amt=0.0, metallic=0.0)
    MATS["glow"] = weathered_material("glow", paint=(0.40, 0.14, 0.03),
                                      metal=(0.40, 0.14, 0.03), rough=0.5, chip=0.0,
                                      rust_amt=0.0, metallic=0.0,
                                      emissive=(1.0, 0.30, 0.060), emissive_strength=2.2)
    MATS["glow_dim"] = weathered_material("glow_dim", paint=(0.30, 0.09, 0.02),
                                          metal=(0.30, 0.09, 0.02), rough=0.6, chip=0.0,
                                          rust_amt=0.0, metallic=0.0,
                                          emissive=(1.0, 0.24, 0.045), emissive_strength=0.9)
    # Small warm lights: vent bores, gauge faces, the sight lens. Deliberately a
    # separate material from glow_dim, because glow_dim also paints the big heat
    # collar between the barrel rings -- lifting that one washes the barrel and
    # pushes the turret back toward "energy weapon". One vent dot is ~2 art px at
    # sprite scale, so it needs a much hotter source to survive the downsample; at
    # 0.9 the vents vanished entirely in the in-game pass.
    MATS["lamp"] = weathered_material("lamp", paint=(0.45, 0.16, 0.03),
                                      metal=(0.45, 0.16, 0.03), rough=0.5, chip=0.0,
                                      rust_amt=0.0, metallic=0.0,
                                      emissive=(1.0, 0.26, 0.040), emissive_strength=2.4)
    # ---- hull variants: the emplacement keeps the older, darker values ----------
    # Measured against vanilla (stats.py --vanilla): turret BASES sit at mean 42-60
    # while turret HEADS sit at 75-105. The gun's palette above is tuned to the head
    # band; if the same values are used for the 2x2 emplacement the whole turret reads
    # as pale cream next to a vanilla gun turret. build_hull_in_place() swaps these in
    # for the duration of the hull build, so one render still produces both layers.
    MATS["hull_steel"] = weathered_material("hull_steel", paint=(0.150, 0.143, 0.132),
                                            metal=(0.300, 0.287, 0.265),
                                            half=(0.212, 0.201, 0.183),
                                            rough=0.58, chip=0.46, rust_amt=0.46)
    MATS["hull_steel_dark"] = weathered_material("hull_steel_dark",
                                                 paint=(0.082, 0.078, 0.073),
                                                 metal=(0.160, 0.154, 0.145),
                                                 half=(0.196, 0.187, 0.174),
                                                 rough=0.64, chip=0.34, rust_amt=0.42)
    MATS["hull_cast"] = weathered_material("hull_cast", paint=(0.192, 0.183, 0.168),
                                           metal=(0.360, 0.345, 0.320),
                                           half=(0.248, 0.238, 0.219),
                                           rough=0.72, chip=0.58, rust_amt=0.54,
                                           noise_scale=17.0, metallic=0.32)


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
        bev=0.008, taper=None, dents=0.0, hollow=False):
    if taper is None:
        bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=r, depth=depth,
                                            location=loc, rotation=rot,
                                            end_fill_type='NOTHING' if hollow else 'NGON')
    else:
        bpy.ops.mesh.primitive_cone_add(vertices=verts, radius1=r, radius2=taper,
                                        depth=depth, location=loc, rotation=rot,
                                        end_fill_type='NOTHING' if hollow else 'NGON')
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


def orient(ob, direction):
    """Point an object's local +Z along `direction` (used for radial/forward ports)."""
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0.0, 0.0, 1.0)).rotation_difference(
        Vector(direction).normalized())
    return ob


def vent_ports(parts, prefix, count, y, radius, port_r, phase=0.0, axis="radial",
               rim_mat="brass", glow_mat="lamp"):
    """A ring of vents: a dark rim standing proud of the body with a warm dot inside.

    This is the readable form of "a cylinder with radial holes at the front" at sprite
    scale (the muzzle body is ~24 art px across, so each port is ~3 px and has to be a
    dark ring around a bright dot to survive the downsample). `axis="radial"` puts the
    ring around the barrel at height y; `axis="forward"` puts it on the muzzle face.
    """
    for i in range(count):
        a = 2 * math.pi * i / count + phase
        if axis == "radial":
            d = (math.cos(a), 0.0, math.sin(a))
            pos = (radius * d[0], y, GUN_Z + radius * d[2])
        else:
            d = (0.0, 1.0, 0.0)
            pos = (radius * math.cos(a), y, GUN_Z + radius * math.sin(a))
        rim = torus("{}_rim{}".format(prefix, i), port_r, port_r * 0.26, pos,
                    rot=(0, 0, 0), mat=rim_mat, maj_seg=14, min_seg=5)
        orient(rim, d)
        parts.append(rim)
        glow = cyl("{}_glow{}".format(prefix, i), port_r * 0.86, port_r * 0.34,
                   (pos[0] + d[0] * port_r * 0.10, pos[1] + d[1] * port_r * 0.10,
                    pos[2] + d[2] * port_r * 0.10), mat=glow_mat, verts=12, bev=0.0)
        orient(glow, d)
        parts.append(glow)


# ------------------------------------------------------------ the machine ---
def build_hull_in_place():
    """build_hull() with the hull's own darker body materials swapped in.

    The gun and the emplacement share one material set, but they sit at different luma
    bands next to vanilla art (head 75, base 42-60), so the three body materials are
    rebound for the duration of the hull build. Objects capture the material at
    creation, so restoring the bindings afterwards leaves the gun untouched.
    """
    names = ("steel", "steel_dark", "cast")
    saved = {k: MATS[k] for k in names}
    for k in names:
        MATS[k] = MATS["hull_" + k]
    try:
        return build_hull()
    finally:
        for k, v in saved.items():
            MATS[k] = v


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
    """The cannon. Short, wide-bore melta projector: chunky breech, armoured mantlet,
    ribbed copper heat coils, vented shroud, and a WH40K-style cylindrical muzzle with
    a ring of radial vents over a hot core. The fluid hardware hangs off the receiver:
    a brass compressor drum on the right, a turbine drum on the roof, a banded
    pressure tank on the left, and copper lines carrying fuel from the tank into the
    breech. Points +Y at rest; every part parents to `root`."""
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
    # ---- compressor block, turbine housing and pressure tank ---------------
    # The three big masses that say "this thing pressurises a fluid". Sizes are chosen
    # against the sprite scale, not against realism: 1 tile is 32 art px (16 screen px
    # at scale 0.5), so a 0.42-tile-diameter drum is ~13 art px and survives the
    # downsample, while the old 0.33-tile fin wall turned into noise. Each subsystem
    # gets its own silhouette and its own material: brass drum, cast turbine, banded
    # steel tank.
    parts.append(cyl("gun_comp_body", 0.210, 0.44, (0.56, -0.10, Z + 0.14),
                     rot=(math.pi / 2, 0, 0), mat="brass", verts=16))
    for i in range(4):
        parts.append(cyl("gun_comp_fin{}".format(i), 0.262, 0.034,
                         (0.56, -0.28 + i * 0.12, Z + 0.14),
                         rot=(math.pi / 2, 0, 0), mat="steel_dark", verts=16,
                         bev=0.004))
    parts.append(cyl("gun_comp_intake", 0.145, 0.07, (0.56, -0.35, Z + 0.14),
                     rot=(math.pi / 2, 0, 0), mat="grime", verts=14, bev=0.0))
    parts.append(box("gun_comp_mount", 0.22, 0.32, 0.18, (0.44, -0.10, Z + 0.00),
                     mat="cast", bev=0.008, dents=0.008))
    parts.append(cyl("gun_comp_gauge", 0.060, 0.04, (0.775, -0.10, Z + 0.14),
                     rot=(0, math.pi / 2, 0), mat="lamp", verts=12, bev=0.0))

    parts.append(cyl("gun_turbine", 0.245, 0.50, (0.0, -0.34, Z + 0.46),
                     rot=(0, math.pi / 2, 0), mat="cast", verts=18))
    for i in range(3):
        parts.append(cyl("gun_turbine_rib{}".format(i), 0.278, 0.038,
                         (-0.155 + i * 0.155, -0.34, Z + 0.46),
                         rot=(0, math.pi / 2, 0), mat="steel_dark", verts=16,
                         bev=0.004))
    parts.append(cyl("gun_turbine_hub", 0.090, 0.54, (0.0, -0.34, Z + 0.46),
                     rot=(0, math.pi / 2, 0), mat="brass", verts=12, bev=0.0))
    # exhaust stack, tipped back so it breaks the roof line
    parts.append(cyl("gun_turbine_stack", 0.070, 0.34, (0.24, -0.54, Z + 0.64),
                     rot=(0.62, 0, 0.28), mat="steel_dark", verts=12))
    parts.append(cyl("gun_turbine_stack_cap", 0.088, 0.06, (0.30, -0.66, Z + 0.78),
                     rot=(0.62, 0, 0.28), mat="copper", verts=12))

    parts.append(cyl("gun_tank", 0.215, 0.42, (-0.60, -0.22, Z + 0.20),
                     rot=(math.pi / 2, 0, 0), mat="brass", verts=16))
    for i, y in enumerate((-0.36, -0.22, -0.08)):
        parts.append(torus("gun_tank_band{}".format(i), 0.223, 0.026,
                           (-0.60, y, Z + 0.20), rot=(math.pi / 2, 0, 0),
                           mat="steel_dark", maj_seg=16, min_seg=5))
    for i, y in enumerate((-0.415, -0.025)):
        parts.append(cyl("gun_tank_cap{}".format(i), 0.160, 0.07,
                         (-0.60, y, Z + 0.20), rot=(math.pi / 2, 0, 0),
                         mat="steel_dark", verts=14))
    parts.append(cyl("gun_tank_gauge", 0.062, 0.04, (-0.805, -0.22, Z + 0.20),
                     rot=(0, math.pi / 2, 0), mat="lamp", verts=12, bev=0.0))
    # a low heat-sink stack on the left rear keeps the melta "heat" read, now that
    # the tall fin wall is gone
    for i in range(3):
        parts.append(box("gun_fin{}".format(i), 0.06, 0.40, 0.045,
                         (-0.46, -0.34, 0.50 + i * 0.07),
                         mat="steel_dark", bev=0.005))
    # feed block on the rear face: a squared block, not a disc, so the back of the gun
    # cannot be mistaken for a second muzzle
    parts.append(box("gun_feed_block", 0.46, 0.24, 0.36, (0.0, -0.84, Z + 0.02),
                     mat="steel", bev=0.012, dents=0.01))
    parts.append(cyl("gun_feed_port", 0.110, 0.10, (0.0, -0.99, Z + 0.02),
                     rot=(math.pi / 2, 0, 0), mat="copper", verts=12,
                     bev=0.006))
    parts.append(box("gun_feed_lug", 0.12, 0.10, 0.10, (-0.22, -0.98, Z + 0.14),
                     mat="cast", bev=0.006))
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

    # ---- heat coils: three fat steel rings, not five thin copper ones ------
    # Five thin copper rings at 0.072 minor radius were 2-3 screen px apart, so they
    # aliased into a corrugated orange sausage and made the whole turret read as a
    # steampunk boiler. Three rings at 0.10 minor read as one ribbed barrel, and the
    # copper budget goes to the fluid hardware, which is where the brief wants it.
    for i, (y, R) in enumerate(((0.52, 0.395), (0.74, 0.405), (0.96, 0.385))):
        parts.append(torus("gun_coil{}".format(i), R, 0.100, (0, y, Z),
                           rot=(math.pi / 2, 0, 0), mat="cast",
                           maj_seg=24, min_seg=8))
    # glow collar between the coils: a full ring, so it reads from every angle
    parts.append(cyl("gun_glow_core", 0.355, 0.52, (0, 0.74, Z),
                     rot=(math.pi / 2, 0, 0), mat="glow_dim", verts=20, bev=0.0))
    for i in (1, 2):
        parts.append(torus("gun_glow{}".format(i), 0.382, 0.026,
                           (0, 0.52 + i * 0.22, Z), rot=(math.pi / 2, 0, 0),
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

    # ---- barrel into the melta projector ----------------------------------
    parts.append(cyl("gun_barrel", 0.215, 0.58, (0, 1.24, Z),
                     rot=(-math.pi / 2, 0, 0), mat="steel", verts=18, taper=0.205,
                     bev=0.0))
    parts.append(cyl("gun_barrel_band", 0.240, 0.055, (0, 1.34, Z),
                     rot=(math.pi / 2, 0, 0), mat="steel_dark", verts=18))
    # The melta signature, WH40K style: a fat cylindrical projector at the muzzle with
    # a ring of RADIAL VENTS. Deliberately no flat plate at the muzzle face (the old
    # heat-projector flare read as a pale disc from the icon camera and as a white
    # plate in game). One ring of vents only: a second ring on the face turned the
    # muzzle into a "gear" at 128 px, so the face is a plain dark bore with a steel
    # lip and the vents carry the whistle at the sides of the projector.
    parts.append(cyl("gun_proj_shoulder", 0.270, 0.10, (0, 1.45, Z),
                     rot=(-math.pi / 2, 0, 0), mat="cast", verts=20, taper=0.345,
                     bev=0.008))
    parts.append(cyl("gun_proj_body", 0.345, 0.24, (0, 1.62, Z),
                     rot=(math.pi / 2, 0, 0), mat="cast", verts=20, bev=0.012,
                     dents=0.006))
    for i, y in enumerate((1.505, 1.735)):
        parts.append(torus("gun_proj_band{}".format(i), 0.338, 0.028,
                           (0, y, Z), rot=(math.pi / 2, 0, 0), mat="cast",
                           maj_seg=24, min_seg=5))
    parts.append(cyl("gun_proj_chamfer", 0.343, 0.07, (0, 1.775, Z),
                     rot=(-math.pi / 2, 0, 0), mat="steel_dark", verts=20,
                     taper=0.300, bev=0.008))
    parts.append(torus("gun_proj_lip", 0.310, 0.052, (0, 1.798, Z),
                       rot=(math.pi / 2, 0, 0), mat="hotmetal",
                       maj_seg=26, min_seg=6))
    # radial vents around the projector body: this is what the stream jets out of
    vent_ports(parts, "gun_vent", 6, 1.615, 0.347, 0.090, phase=0.30)
    # recessed bore: an actually hollow tube, so the muzzle reads as an opening with a
    # warm floor rather than a capped face. The far end is plugged with a dark disc so
    # you can never see through the gun.
    parts.append(cyl("gun_bore_tube", 0.180, 0.26, (0, 1.680, Z),
                     rot=(math.pi / 2, 0, 0), mat="grime", verts=20, bev=0.0,
                     hollow=True))
    parts.append(cyl("gun_bore_back", 0.184, 0.03, (0, 1.556, Z),
                     rot=(math.pi / 2, 0, 0), mat="grime", verts=20, bev=0.0))
    parts.append(cyl("gun_bore_hot", 0.086, 0.02, (0, 1.600, Z),
                     rot=(math.pi / 2, 0, 0), mat="lamp", verts=14, bev=0.0))

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
                     rot=(math.pi / 2, 0, 0), mat="lamp", verts=12, bev=0.0))
    # ---- fuel / fluid lines: tank -> receiver, compressor -> tank ----------
    # Copper hard lines, not a single rubber hose: the melta's fuel has to be carried
    # from the pressure tank into the breech, and the plumbing is what makes the model
    # read as a combustion weapon at a glance. Radius 0.075 tiles = 4.8 screen px, the
    # thinnest line that still reads at native zoom (the old 0.055 hose read as noise).
    parts.append(tube("gun_line_feed",
                      [(-0.60, 0.00, Z + 0.20), (-0.60, 0.22, Z + 0.14),
                       (-0.46, 0.40, Z + 0.02), (-0.26, 0.50, Z - 0.06)],
                      0.075, mat="copper"))
    parts.append(tube("gun_line_cross",
                      [(0.56, 0.12, Z + 0.14), (0.42, 0.30, Z + 0.34),
                       (0.02, 0.34, Z + 0.44), (-0.44, 0.18, Z + 0.32),
                       (-0.60, 0.02, Z + 0.22)], 0.062, mat="copper"))
    parts.append(tube("gun_line_tank",
                      [(-0.60, -0.42, Z + 0.20), (-0.52, -0.56, Z + 0.06),
                       (-0.34, -0.64, Z - 0.04), (-0.14, -0.68, Z - 0.06)],
                      0.070, mat="copper"))
    parts.append(tube("gun_line_comp",
                      [(0.56, -0.36, Z + 0.14), (0.52, -0.50, Z + 0.00),
                       (0.32, -0.58, Z - 0.06), (0.10, -0.62, Z - 0.08)],
                      0.062, mat="copper"))
    for i, (x, y, z) in enumerate(((-0.55, 0.30, Z + 0.08), (-0.32, 0.46, Z - 0.04),
                                   (-0.44, -0.58, Z + 0.02))):
        parts.append(box("gun_line_clamp{}".format(i), 0.13, 0.11, 0.11, (x, y, z),
                         mat="cast", bev=0.006))
    # pressure dial on the receiver cheek, the second of the two warm accent lights
    parts.append(cyl("gun_gauge", 0.105, 0.05, (0.0, -0.02, Z + 0.40),
                     rot=(math.pi / 2, 0, 0), mat="steel_dark", verts=14, bev=0.006))
    parts.append(cyl("gun_gauge_face", 0.076, 0.02, (0.0, 0.01, Z + 0.40),
                     rot=(math.pi / 2, 0, 0), mat="lamp", verts=14, bev=0.0))
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
    """Kept for a Blender whose Cycles honours lamp energy (3.x+). Inert here: on
    this 2.79b the whole lamp path renders pixel-identical at energy 0 and 8, which
    is why setup_lights uses the emissive rig instead. See the RIG comment."""
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


def add_softbox(name, loc, size, strength, color, aim=(0.0, 0.0, 0.5)):
    """An emissive plane: the only light source this build responds to.

    Placement is constrained by the orthographic camera. The camera's visible volume
    is an infinite prism 4 tiles wide in X and in the screen-up axis
    `(0, cos51, sin51) = (0, 0.629, 0.777)`; anything projecting inside +-2 tiles of
    that axis is photographed as a flat white sheet (which is exactly what the first
    strength-calibration run produced until the plates were pushed up to z >= 5).
    `check_rig_in_frame` verifies the clearance by projecting the plates through the
    real camera, so this cannot regress silently.
    """
    name = "soft:" + name
    bpy.ops.mesh.primitive_plane_add(radius=0.5, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size, size, size)
    apply_scale(ob)
    d = Vector(aim) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('Z', 'Y').to_euler()
    mat = bpy.data.materials.new(name + "_m")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (color[0], color[1], color[2], 1.0)
    em.inputs["Strength"].default_value = strength * KEYPOWER
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    ob.data.materials.append(mat)
    # A lighting plate must light the model and never be photographed itself. Hiding
    # it from camera rays is the only fix that holds for EVERY camera: the sheet rig
    # (51 deg, 4.0 tiles) and the icon rig (34 deg, 4.2 tiles) have different prisms,
    # so a plate that clears one is inside the other -- which is how a flat white
    # triangle ended up in the shipped icon and thumbnail while the sheet camera
    # reported "rig clear". Emission still lights the scene; the plate is just not a
    # camera-visible surface.
    if hasattr(ob, "cycles_visibility"):
        ob.cycles_visibility.camera = False
    ob.hide_render = False
    return ob


def clear_softboxes():
    for ob in list(bpy.data.objects):
        if ob.name.startswith("soft:"):
            bpy.data.objects.remove(ob, do_unlink=True)


def check_rig_in_frame():
    """Fail loudly if a light plate would be photographed (a white sheet in frame)."""
    from bpy_extras.object_utils import world_to_camera_view
    scene = bpy.context.scene
    cam = scene.camera
    bad = []
    for ob in scene.objects:
        if not ob.name.startswith("soft:"):
            continue
        inside = 0
        # Sample the object's REAL bounds, not local +-0.5: add_softbox scales the
        # primitive by `size` and applies it, so a plate's vertices sit at
        # +-0.5*size and a +-0.5 local sample only tests the middle of the plate.
        # That blind spot let a 4.2-tile key plate's corner sit in the icon frame
        # while this function still printed "rig clear".
        pts = [Vector(c) for c in ob.bound_box] + [Vector((0.0, 0.0, 0.0))]
        for co_local in pts:
            co = ob.matrix_world * co_local
            pr = world_to_camera_view(scene, cam, co)
            if 0.0 <= pr.x <= 1.0 and 0.0 <= pr.y <= 1.0 and pr.z > 0:
                inside += 1
        if inside:
            bad.append((ob.name, inside))
    if bad:
        print("DIAG RIG WARNING: light plates inside the frame", bad)
    else:
        print("DIAG rig clear of the frame")
    return not bad


def setup_lights():
    """Three emissive softboxes plus a near-black world.

    Warm key from the upper left (vanilla's sun direction, so the baked cast shadow
    falls to the lower right), cool fill from the right, cool rim from behind. Suns
    are NOT used: this Cycles ignores lamp energy (see add_sun).
    """
    clear_softboxes()
    add_softbox("key", (-3.00, -2.20, 8.00), 4.2, RIG["key"], (1.0, 0.94, 0.84))
    add_softbox("fill", (5.20, -1.20, 5.60), 3.6, RIG["fill"], (0.72, 0.80, 1.0))
    add_softbox("rim", (0.60, 6.20, 5.40), 3.4, RIG["rim"], (0.80, 0.84, 0.95))
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
    check_rig_in_frame()

    hull = build_hull_in_place()
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
