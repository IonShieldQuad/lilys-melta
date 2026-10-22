local C = require("constants")

-- The melta borrows the rocket turret's hull and its 64-direction head rig, so it
-- has the same 2x2 footprint and the same heavy-emplacement animation. Anything
-- below that touches `name`/`attack_parameters` is the melta part.
--
-- NOTE: with no Space Age installed the mod falls back to the base laser turret
-- hull (1x1). The beam maths in control.lua are footprint independent.

local base = data.raw["ammo-turret"] and data.raw["ammo-turret"]["rocket-turret"]
local space_age = base ~= nil
if not base then
  base = data.raw["electric-turret"]["laser-turret"]
end

local turret = table.deepcopy(base)

if not space_age then
  turret.type = "ammo-turret"
  turret.energy_source = nil
  turret.energy_per_shot = nil
  turret.icon = "__base__/graphics/icons/laser-turret.png"
else
  turret.icon = "__space-age__/graphics/icons/rocket-turret.png"
  -- the rocket pod is recoloured to a hot patina: same silhouette she asked to
  -- reuse, different reading (this is an emitter, not a launcher)
  local hot = {r = 1.00, g = 0.72, b = 0.45}
  local glow = {r = 1.00, g = 0.55, b = 0.22}
  for _, animation in pairs({turret.attacking_animation, turret.prepared_animation, turret.preparing_animation, turret.folded_animation}) do
    for _, layer in pairs(animation and animation.layers or {}) do
      if layer.draw_as_light then
        layer.tint = glow
      elseif not layer.draw_as_shadow and not (layer.flags and layer.flags[1] == "mask") then
        layer.tint = hot
      end
    end
  end
end

turret.name = C.turret
turret.icon_size = 64
turret.minable = {mining_time = 0.6, result = C.turret}
turret.max_health = 1200
turret.inventory_size = 1
turret.automated_ammo_count = 5
turret.attacking_speed = 0.55
turret.rotation_speed = 0.006
turret.alert_when_attacking = true

turret.attack_parameters =
{
  type = "beam",
  ammo_category = C.ammo_category,
  cooldown = C.cooldown,
  range = C.range,
  range_mode = "center-to-bounding-box",
  -- close range: the melta wants anything in front of it, not a 24 tile killbox
  min_range = 0,
  source_direction_count = 64,
  source_offset = {0, space_age and -1.6 or -0.9},
  damage_modifier = 1,
  -- a beam keeps its sound while it is being held down, so a cyclic sound with a
  -- looping middle section fits: light-up, roar, shut-down
  cyclic_sound =
  {
    begin_sound = {filename = "__base__/sound/fight/flamethrower-turret-start-1.ogg", volume = 0.4},
    middle_sound =
    {
      variations =
      {
        {filename = "__base__/sound/fight/flamethrower-turret-mid-1.ogg", volume = 0.35},
        {filename = "__base__/sound/fight/flamethrower-turret-mid-2.ogg", volume = 0.35},
        {filename = "__base__/sound/fight/flamethrower-turret-mid-3.ogg", volume = 0.35}
      },
      aggregation = {max_count = 2, remove = true, count_already_playing = true}
    },
    end_sound = {filename = "__base__/sound/fight/flamethrower-turret-end-1.ogg", volume = 0.4}
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
