local C = require("constants")

-- Thermal is its own damage type: nothing in vanilla resists it, which is the
-- point of a melta. The turret pays for that with range, fuel and spin-up time.
data:extend(
{
  {
    type = "damage-type",
    name = C.damage_type
  },
  {
    type = "ammo-category",
    name = C.ammo_category
  }
})

---------------------------------------------------------------- beam ---------
-- Built from the vanilla laser beam so the head/tail/body/ground light rig comes
-- free; only the tint, width and the (tiny) contact hit are ours.
local beam = table.deepcopy(data.raw["beam"]["laser-beam"])
beam.name = C.beam
beam.width = 0.9
beam.damage_interval = C.cooldown
beam.random_target_offset = false
beam.action =
{
  type = "direct",
  action_delivery =
  {
    type = "instant",
    target_effects =
    {
      -- The engine lands this cold hit on the turret's own target; control.lua
      -- adds the spin-up part and the pierced bodies behind it.
      {
        type = "damage",
        damage = {amount = C.damage_cold, type = C.damage_type}
      },
      {
        type = "play-sound",
        sound = {filename = "__base__/sound/fire-impact-1.ogg", volume = 0.25}
      }
    }
  }
}

local hot = {r = 1.00, g = 0.62, b = 0.28}
local function tint_directional(directional, tint)
  if not directional then return end
  for _, layer in pairs(directional.layers or {}) do
    layer.tint = tint
  end
end
tint_directional(beam.graphics_set.beam.head, hot)
tint_directional(beam.graphics_set.beam.tail, hot)
for _, segment in pairs(beam.graphics_set.beam.body or {}) do
  tint_directional(segment, hot)
end
-- the floor glow is a light sprite, so tinting it orange is all it takes
for _, part in pairs(beam.graphics_set.ground or {}) do
  part.tint = {r = 0.85, g = 0.30, b = 0.05}
end

data:extend({beam})

---------------------------------------------------------------- fuel ---------
data:extend(
{
  {
    type = "ammo",
    name = C.ammo,
    icons = {{icon = "__base__/graphics/icons/solid-fuel.png", icon_size = 64, tint = {r = 1.0, g = 0.62, b = 0.30}}},
    subgroup = "ammo",
    order = "a[melta-fuel]",
    stack_size = 200,
    magazine_size = C.magazine_size,
    ammo_category = C.ammo_category,
    ammo_type =
    {
      category = C.ammo_category,
      action =
      {
        type = "direct",
        action_delivery =
        {
          type = "beam",
          beam = C.beam,
          max_length = C.range,
          duration = C.cooldown,
          source_offset = {0, 0}
        }
      }
    }
  }
})

data:extend(
{
  {
    type = "recipe",
    name = C.ammo,
    enabled = false,
    energy_required = 4,
    ingredients =
    {
      {type = "item", name = "solid-fuel", amount = 1},
      {type = "item", name = "steel-plate", amount = 1}
    },
    results = {{type = "item", name = C.ammo, amount = 10}},
    allow_productivity = true
  }
})
