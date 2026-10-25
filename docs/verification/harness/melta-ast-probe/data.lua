-- Data stage for the asteroid-damage probe (never shipped).
--
-- Two stationary dummy *units* stand in for pawns so the beam dps can be read off
-- their health curve: one with no resistances at all, one wearing the vanilla
-- behemoth-biter armour (physical decrease 12 / 10 %). Both are copies of
-- small-biter with no movement, no vision and no attack, so they neither chase nor
-- fight back; max_health 1e6 keeps the float32 damage quantum at 0.06 (a 1e9 health
-- pool would quantise every pulse to 64 and hide the spin-up ramp).

local function dummy(name, resistances)
  local unit = table.deepcopy(data.raw["unit"]["small-biter"])
  unit.name = name
  unit.max_health = 1000000
  unit.healing_per_tick = 0
  unit.movement_speed = 0
  unit.max_pursue_distance = 0
  unit.vision_distance = 0
  unit.distraction_cooldown = 0
  unit.absorptions_per_second = nil
  unit.resistances = resistances or {}
  -- a unit prototype must carry attack_parameters; make it harmless instead of absent
  unit.attack_parameters.cooldown = 100000
  unit.attack_parameters.range = 1
  for _, action in pairs(unit.attack_parameters.ammo_type and unit.attack_parameters.ammo_type.action or {}) do
    if type(action) == "table" and action.action_delivery then
      action.action_delivery.target_effects = nil
    end
  end
  unit.corpse = nil
  unit.dying_sound = nil
  unit.dying_animation = nil
  unit.working_sound = nil
  unit.alternative_attacking_animation = nil
  unit.attacking_animation = nil
  unit.running_animation = nil
  return unit
end

data:extend(
{
  dummy("ast-probe-plain", {}),
  dummy("ast-probe-behemoth",
  {
    {type = "physical", decrease = 12, percent = 10},
    {type = "explosion", decrease = 15, percent = 10},
    {type = "fire", decrease = 0, percent = 0}
  })
})
