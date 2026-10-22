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

---------------------------------------------------------------- fuel ---------
-- Liquid pyrum, brewed from light oil. One light oil stretches into several units,
-- so a turret holding a beam costs a steady trickle of oil rather than a belt of
-- shells -- which is the point: liquid input, no ammo logistics.
data:extend(
{
  {
    type = "fluid",
    name = C.fluid,
    icons = {{icon = "__base__/graphics/icons/fluid/light-oil.png", icon_size = 64, tint = {r = 1.0, g = 0.55, b = 0.20}}},
    default_temperature = 25,
    max_temperature = 100,
    base_color = {r = 0.85, g = 0.32, b = 0.06},
    flow_color = {r = 1.00, g = 0.66, b = 0.32},
    auto_barrel = false
  },
  {
    type = "recipe",
    name = C.fluid,
    enabled = false,
    energy_required = 2,
    categories = {"chemistry"},
    ingredients =
    {
      {type = "fluid", name = "light-oil", amount = 10}
    },
    results = {{type = "fluid", name = C.fluid, amount = 40}},
    allow_productivity = true,
    crafting_machine_tint =
    {
      primary = {r = 0.98, g = 0.45, b = 0.10, a = 1.0},
      secondary = {r = 1.00, g = 0.70, b = 0.35, a = 1.0}
    }
  }
})

---------------------------------------------------------------- stream -------
-- A fluid turret is only allowed stream attacks, and that is what lets it drink
-- from a pipe at all. This stream is deliberately invisible and near-harmless:
-- control.lua owns the beam, the pierce and the damage. The engine keeps the
-- aiming, the attack state and the fluid burn natively.
local stream = table.deepcopy(data.raw["stream"]["flamethrower-fire-stream"])
stream.name = C.stream
stream.particle_buffer_size = 1
stream.particle_spawn_interval = 600
stream.particle_spawn_timeout = 0
stream.particle_start_alpha = 0
stream.particle_end_alpha = 0
stream.particle_start_scale = 0.01
stream.smoke_sources = nil
stream.action =
{
  {
    type = "direct",
    action_delivery =
    {
      type = "instant",
      target_effects =
      {
        {type = "damage", damage = {amount = 1, type = C.damage_type}}
      }
    }
  }
}
data:extend({stream})
