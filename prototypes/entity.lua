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
local space_age = base ~= nil
if not base then
  base = data.raw["electric-turret"]["laser-turret"]
end

local source = table.deepcopy(base)
local head = require("prototypes.graphics")

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
  icon = space_age and "__space-age__/graphics/icons/rocket-turret.png" or "__base__/graphics/icons/laser-turret.png",
  icon_size = 64,
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
  rotation_speed = 0.006,
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
    pipe_connections =
    {
      {direction = defines.direction.west, position = {-1.2, 0}},
      {direction = defines.direction.east, position = {1.2, 0}}
    }
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
    -- synthesised jet exhaust + sizzle (sound/_generator/melta_sounds.py): a
    -- high-pressure stream, not a flame loop borrowed from the flamethrower.
    -- Loudness, measured (ffmpeg astats, effective = file dBFS + 20log10(volume)):
    --   before  loop -26.4 dBFS RMS x 0.45 = -33.3 dBFS in the mix  (why it was quiet:
    --           the generator normalises by PEAK, and this noise bed has a 25 dB crest)
    --   after   loop -15.2 dBFS RMS x 0.70 = -18.3 dBFS in the mix
    -- Reference points: vanilla flamethrower-turret-mid is -13.2 dBFS RMS x 0.5 =
    -- -19.2 dBFS, gun-turret gunshot -17.6 x 0.4. So the melta now sits level with a
    -- vanilla flamer loop and still under gun-turret spam, and its file peak (-1.6 dBFS)
    -- leaves -4.7 dBFS per voice, i.e. two loops cannot sum over full scale.
    -- `aggregation` is the anti-clipping clamp: at most 2 loops / 2 cues at once, so a
    -- 5-turret wall raises the level instead of stacking. `audible_distance_modifier`
    -- widens the falloff so it also *carries* further.
    cyclic_sound =
    {
      begin_sound =
      {
        filename = "__lilys-melta__/sound/melta-start.ogg",
        volume = 0.7,
        audible_distance_modifier = 1.3,
        aggregation = {max_count = 2, remove = true, count_already_playing = true}
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
    icon = turret.icon,
    icon_size = 64,
    subgroup = "defensive-structure",
    order = "e[melta-turret]",
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
