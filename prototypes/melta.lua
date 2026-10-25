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
-- The engine's own contact hit is deliberately EMPTY. It used to carry 1 damage
-- (0.85 fire + 0.15 physical), which the inspect panel printed as "Damage: 0.09/s
-- Fire" -- a number that has nothing to do with the beam, which is script damage.
-- Measured on an unarmoured dummy before this change: a full-charge pulse took
-- exactly 56.00 hp, i.e. the script's number and not a point more, so those effects
-- never landed and only ever fed the panel a false readout. The delivery stays (a
-- stream action needs one); the damage lives in control.lua and is described by
-- prototypes/tooltip.lua.
stream.action =
{
  {
    type = "direct",
    action_delivery =
    {
      type = "instant",
      -- A stream action rejects an empty target_effects list ("Key \"type\" not
      -- found"), and the engine prints whatever damage is listed here in the
      -- inspect panel's Damage line. Zero is the only honest number for effect
      -- data that cannot land: the list has to exist, but the beam's damage is
      -- script damage (control.lua) and is described by prototypes/tooltip.lua.
      target_effects =
      {
        {type = "damage", damage = {amount = 0, type = C.damage_type}}
      }
    }
  }
}
data:extend({stream})
