local C = require("constants")

-- The melta is a FLUID turret, not an ammo turret: that is the only turret type the
-- engine lets drink from a pipe (and, symmetrically, the only one restricted to
-- stream attacks -- see prototypes/melta.lua for the invisible stream that makes
-- that restriction harmless). It borrows the rocket turret's hull and its
-- 64-direction head rig, so it keeps the 2x2 footprint and the heavy-emplacement
-- animation she asked for.
--
-- Two engine consequences worth knowing:
--   * fluid turrets must be `turret_base_has_direction` (forced) -- harmless here,
--     because the rocket hull's base is a single non-directional sprite.
--   * they want a 4-entry circuit connector; dropping it is legal and simpler.

local base = data.raw["ammo-turret"] and data.raw["ammo-turret"]["rocket-turret"]
if not base then
  base = data.raw["electric-turret"]["laser-turret"]
end

local source = table.deepcopy(base)
local head = require("prototypes.graphics")

-- Our own icon, rendered from the same model as the sprite sheets
-- (graphics/_blender/render_icons.py + assemble_icons.py). The file is shaped like
-- the base game's turret icons: 120x64 = the 64 px icon plus its 32/16/8 px mip
-- levels packed to the right, which is why icon_size is 64 and not the file width.
local ICON = "__lilys-melta__/graphics/icons/melta-turret.png"
local ICON_SIZE = 64

-- every fuel in constants.lua that actually exists in this install; the turret's
-- fluid box stays unfiltered (like the flamethrower) so any of them can be piped in,
-- and the engine only burns the ones listed here
local fuels = {}
for _, fuel in ipairs(C.fuels) do
  if data.raw["fluid"][fuel.name] then
    fuels[#fuels + 1] = {type = fuel.name, damage_modifier = fuel.damage_modifier}
  end
end
local flamer = data.raw["fluid-turret"]["flamethrower-turret"]

local turret =
{
  type = "fluid-turret",
  name = C.turret,
  icon = ICON,
  icon_size = ICON_SIZE,
  flags = {"placeable-player", "player-creation"},
  minable = {mining_time = 0.6, result = C.turret},
  max_health = 1200,
  corpse = source.corpse,
  dying_explosion = source.dying_explosion,
  damaged_trigger_effect = source.damaged_trigger_effect,
  -- 2x2 footprint, same as the rocket turret it started as, so existing saves and
  -- blueprints place it exactly where they did before. The art overhangs the box
  -- (barrel and skirt), which is normal for turrets -- the boxes only have to hug
  -- the part the player and the enemy can touch.
  collision_box = {{-1.2, -1.2}, {1.2, 1.2}},
  selection_box = {{-1.6, -1.6}, {1.6, 1.6}},
  -- the cannon stands ~1.2 tiles tall and reaches 1.8 tiles out; this keeps it
  -- from being clipped/sorted behind neighbours when it points at them
  drawing_box_vertical_extension = 0.5,
  heating_energy = source.heating_energy,
  resistances = {{type = "fire", percent = 100}},
  turret_base_has_direction = true,
  -- turns per tick; C.rotation_speed = 0.03 (10.8 deg/tick, half a turn in 17 ticks).
  -- The old 0.006 was inherited from the rocket turret and is why the head trailed a
  -- biter crossing at close range -- see constants.lua for the tracking maths.
  rotation_speed = C.rotation_speed,
  preparing_speed = 0.08,
  folding_speed = 0.08,
  attacking_speed = 0.55,
  ending_attack_speed = 0.3,
  alert_when_attacking = true,
  open_sound = source.open_sound,
  close_sound = source.close_sound,
  preparing_sound = source.preparing_sound,
  folding_sound = source.folding_sound,
  rotating_sound = source.rotating_sound,
  call_for_help_radius = 40,
  circuit_connector = nil,
  circuit_wire_max_distance = nil,
  -- the hull (base sprite, shadow, water reflection) is the rocket turret's own,
  -- untouched; only the gun head is replaced with our drawn emitter sheet
  folded_animation = head.folded_animation,
  preparing_animation = head.preparing_animation,
  prepared_animation = head.prepared_animation,
  attacking_animation = head.attacking_animation,
  ending_attack_animation = head.ending_attack_animation,
  folding_animation = head.folding_animation,
  -- the hull (base sprite, cast shadow, water reflection) is our own render now:
  -- base_visualisation is the 2.1 shape, the cannon rides on top of it
  graphics_set =
  {
    base_visualisation =
    {
      animation =
      {
        layers =
        {
          table.deepcopy(head.base)
        }
      }
    },
    water_reflection = source.graphics_set and source.graphics_set.water_reflection or nil
  },

  ---------------------------------------------------------------- plumbing --
  fluid_box =
  {
    production_type = "none",        -- fluid turrets run their own fluid logic
    volume = C.fluid_buffer,
    -- One port per side, so the turret can be plumbed from any direction (it used
    -- to be west+east only). `position` is where the pipe stops; it has to sit on
    -- the emplacement's silhouette, or a 1-tile pipe -- which can only be built 2.0
    -- tiles from the centre -- either buries itself in the hull or floats short of
    -- it. One symmetric number for all four sides so rotating the turret (the ports
    -- rotate with it) cannot slide a socket off its pipe: see C.pipe_reach.
    --
    -- `flow_direction` is left at the engine default ("input-output", confirmed by
    -- reading it back at runtime), exactly like the vanilla flamethrower turret: the
    -- buffer has to be *able* to drain as well as fill (fluid_buffer_input_flow caps
    -- the fill rate), and pinning it to "input" would turn a full turret into a dead
    -- end for the rest of the line.
    pipe_connections =
    {
      {direction = defines.direction.north, position = {0, -C.pipe_reach}},
      {direction = defines.direction.east, position = {C.pipe_reach, 0}},
      {direction = defines.direction.south, position = {0, C.pipe_reach}},
      {direction = defines.direction.west, position = {-C.pipe_reach, 0}}
    },
    -- The stub hardware and the two fields that decide when it shows. Copied from
    -- lilys-cubeine's combustion center (see prototypes/graphics.lua for the art):
    -- `draw_only_when_connected` keeps an unused side bare hull -- no cap plate --
    -- and the negative secondary draw order puts the stub behind the hull so only
    -- the part that pokes past the rim reads. `pipe_covers` is nil whenever the
    -- space-age art is available; a base-only install gets vanilla's covers instead.
    pipe_picture = head.pipe_picture,
    pipe_covers = head.pipe_covers,
    draw_only_when_connected = true,
    secondary_draw_orders = {north = -1, west = -1, east = -1}
  },
  fluid_buffer_size = C.fluid_buffer,
  fluid_buffer_input_flow = 1.6,   -- units/tick: enough to feed ~50/s at full beam
  activation_buffer_ratio = 0.25,
  not_enough_fuel_indicator_light = {intensity = 0.2, size = 1.5, color = {1, 0, 0}},
  enough_fuel_indicator_light = {intensity = 0.2, size = 1.5, color = {0, 1, 0}},
  out_of_ammo_alert_icon = table.deepcopy(flamer.out_of_ammo_alert_icon),

  ---------------------------------------------------------------- attack ----
  attack_parameters =
  {
    type = "stream",
    cooldown = C.cooldown,
    range = C.range,
    min_range = 0,
    -- full circle: the melta tracks like a normal turret, not like a fixed flamer
    turn_range = 1.0,
    fluid_consumption = C.fluid_consumption,
    fluids = fuels,
    ammo_category = C.ammo_category,
    -- muzzle geometry. `gun_barrel_length` is where the engine spawns the (invisible)
    -- stream: the mouth of the projector, 1.512 tiles along the barrel. The *visible*
    -- beam is drawn by control.lua, which also has to account for the sprite camera
    -- (a raised muzzle is drawn further "up" the screen), so the per-direction part of
    -- this lives in C.muzzle_forward / C.muzzle_height rather than in
    -- gun_center_shift: the two must agree, and only one of them can be the owner.
    gun_barrel_length = C.muzzle_forward,
    gun_center_shift = {north = {0, 0}, east = {0, 0}, south = {0, 0}, west = {0, 0}},
    ammo_type =
    {
      action =
      {
        type = "direct",
        action_delivery =
        {
          -- invisible: the beam itself is drawn by control.lua
          type = "stream",
          stream = C.stream,
          source_offset = {0, 0}
        }
      }
    },
    -- SOUND. Every cue is synthesised by sound/_generator/melta_sounds.py -- that
    -- script is the source of truth, so re-run it rather than hand-editing the
    -- OGGs (it re-checks loudness, clipping and layer balance after encoding).
    -- Each cue is built from three layers: a pressure-release burst on sample 0,
    -- a sizzling roar body as the stream burns, and a turbopump hum underneath
    -- that spins up and gives the shot its weight.
    --
    -- Why CyclicSound and not `attack_parameters.sound`: `sound` retriggers on
    -- every shot, and this turret pulses at 7.5/s (C.cooldown = 8), so a 0.6 s cue
    -- would stack five deep and smear -- exactly what the brief says to avoid.
    -- begin/middle/end is the model the vanilla flamethrower turret uses and it
    -- matches what the melta does: one ignition, a held stream, one shut-down.
    -- The three variations sit on the ignition (allow_random_repeat defaults to
    -- false, so consecutive engagements never pick the same one).
    --
    -- Loudness, measured on the shipped files (ffmpeg astats; effective = file
    -- RMS dBFS + 20log10(volume)):
    --   cue                      file RMS   file peak   volume   effective
    --   melta-fire-1/2/3           -15.4      -3.3       0.70      -18.5
    --   melta-burn   (loop)        -15.3      -4.4       0.70      -18.4
    --   melta-stop                 -19.6      -5.7       0.70      -22.7
    --   vanilla flamer igniter     -13.2      -1.2       0.50      -19.2
    --   vanilla flamer loop        -13.7      -2.4       0.50      -19.7
    --   vanilla gun turret shot    -17.9      -0.8       0.40      -25.9
    --   vanilla laser turret shot  -20.2      -3.6       0.50      -26.2
    -- So the melta sits just above a vanilla flamer and far above the gun and
    -- laser turrets: heavier than both, as a fluid weapon firing continuous
    -- pressure should be.
    --
    -- Peaks are what clip, not RMS: the generator gates every file to decode under
    -- -3 dBFS, so one voice at 0.70 peaks at -6.1 dBFS and the worst measured
    -- two-voice sum (any two variations, 0-40 ms apart) is -1.4 dBFS.
    -- `aggregation.max_count` is what limits it to two voices -- a 5-turret wall
    -- raises the level instead of stacking. `progress_threshold` hands the
    -- ignition's slot back once the cue is a third through, so a second turret's
    -- ignition is never dropped because the first one's tail is still ringing.
    -- `audible_distance_modifier` widens the falloff so the cue carries instead of
    -- being pushed louder.
    cyclic_sound =
    {
      begin_sound =
      {
        variations =
        {
          {filename = "__lilys-melta__/sound/melta-fire-1.ogg", volume = 0.7},
          {filename = "__lilys-melta__/sound/melta-fire-2.ogg", volume = 0.7},
          {filename = "__lilys-melta__/sound/melta-fire-3.ogg", volume = 0.7}
        },
        audible_distance_modifier = 1.3,
        aggregation = {max_count = 2, remove = true, count_already_playing = true, progress_threshold = 0.35}
      },
      middle_sound =
      {
        filename = "__lilys-melta__/sound/melta-burn.ogg",
        volume = 0.7,
        audible_distance_modifier = 1.4,
        aggregation = {max_count = 2, remove = true, count_already_playing = true}
      },
      end_sound =
      {
        filename = "__lilys-melta__/sound/melta-stop.ogg",
        volume = 0.7,
        audible_distance_modifier = 1.3,
        aggregation = {max_count = 2, remove = true, count_already_playing = true}
      }
    }
  }
}

data:extend({turret})

----------------------------------------------------------- placing item ----
data:extend(
{
  {
    type = "item",
    name = C.turret,
    icon = ICON,
    icon_size = ICON_SIZE,
    -- Where it sorts in the crafting menu and every item list. 2.1 splits the old
    -- "combat" group into `turret` (subgroup order "i") and `defensive-structure`
    -- (order "h", which holds walls, gates, the radar and land mines) -- the melta
    -- sat in the latter, one slot past the radar, because it kept an order string
    -- written against the old flat group. The order key below is the vanilla turret
    -- ladder's own prefix, so the turret lands directly after the flamethrower turret
    -- it is the bigger cousin of: base uses b[turret]-a[gun-turret], -b[laser-turret],
    -- -c[flamethrower-turret], -d[artillery-turret], and space age adds
    -- -e[rocket-turret], -f[tesla-turret], -g[railgun-turret].
    subgroup = "turret",
    order = "b[turret]-c[flamethrower-turret]-a[melta-turret]",
    place_result = C.turret,
    stack_size = 20
  },
  {
    type = "recipe",
    name = C.turret,
    enabled = false,
    energy_required = 6,
    ingredients =
    {
      {type = "item", name = "steel-plate", amount = 25},
      {type = "item", name = "iron-gear-wheel", amount = 20},
      {type = "item", name = "advanced-circuit", amount = 15},
      {type = "item", name = "processing-unit", amount = 5}
    },
    results = {{type = "item", name = C.turret, amount = 1}}
  }
})
