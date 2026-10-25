-- Data stage for the combined probe (never shipped).
--
-- One stationary, harmless dummy *unit*: a copy of small-biter with no movement, no
-- vision, no attack and no resistances. max_health 1e6 keeps the float32 damage
-- quantum at 0.06 so a single pulse is one visible health drop (1e9 would quantise
-- every pulse to 64 and hide the charge ramp).

local unit = table.deepcopy(data.raw["unit"]["small-biter"])
unit.name = "comb-probe-dummy"
unit.max_health = 1000000
unit.healing_per_tick = 0
unit.movement_speed = 0
unit.max_pursue_distance = 0
unit.vision_distance = 0
unit.distraction_cooldown = 0
unit.absorptions_per_second = nil
unit.resistances = {}
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

data:extend({ unit })
