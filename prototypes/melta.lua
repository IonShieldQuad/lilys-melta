local C = require("constants")

-- The beam deals vanilla `fire` plus a smaller `physical` slice (see constants.lua:
-- C.damage_type / C.damage_type_hit / C.physical_share), so it needs no damage type
-- of its own -- and no resistance table anywhere has to learn a new name.
data:extend(
{
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
    icons = {{icon = "__base__/graphics/icons/fluid/light-oil.png", icon_size = 64, tint = {r = 0.55, g = 1.0, b = 0.55}}},
    default_temperature = 25,
    max_temperature = 100,
    base_color = {r = 0.20, g = 0.55, b = 0.22},
    flow_color = {r = 0.55, g = 1.00, b = 0.60},
    auto_barrel = false
  },
  {
    type = "recipe",
    name = C.fluid,
    enabled = false,
    energy_required = 4,
    categories = {"chemistry"},
    ingredients =
    {
      {type = "fluid", name = "light-oil", amount = 20},
      {type = "item", name = "uranium-238", amount = 2},
      {type = "item", name = "sulfur", amount = 1}
    },
    results = {{type = "fluid", name = C.fluid, amount = 100}},
    allow_productivity = true,
    crafting_machine_tint =
    {
      primary = {r = 0.40, g = 0.95, b = 0.45, a = 1.0},
      secondary = {r = 0.70, g = 1.00, b = 0.75, a = 1.0}
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
-- The engine's own contact hit is the same split the script applies, scaled down to
-- 1 damage: whichever path lands the hit, the damage type reads fire first and the
-- physical slice is still there (0.85 fire + 0.15 physical).
stream.action =
{
  {
    type = "direct",
    action_delivery =
    {
      type = "instant",
      target_effects =
      {
        {type = "damage", damage = {amount = 1 * (1 - C.physical_share), type = C.damage_type}},
        {type = "damage", damage = {amount = 1 * C.physical_share,       type = C.damage_type_hit}}
      }
    }
  }
}
data:extend({stream})
