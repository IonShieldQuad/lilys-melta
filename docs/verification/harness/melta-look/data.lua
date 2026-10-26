-- A stationary, harmless, targetable dummy: the melta aims at it without firing
-- (the scene never fuels the turrets, and a fluid turret with an empty box cannot
-- shoot), so every head can be pointed at a chosen bearing without any beam art
-- covering the turret itself. Same shape as the melta-probe dummy, see
-- docs/verification/harness in the skill notes.
local dummy = table.deepcopy(data.raw.unit["small-biter"])
dummy.name = "look-dummy"
dummy.max_health = 100000
dummy.healing_per_tick = 0
dummy.movement_speed = 0
dummy.vision_distance = 0
dummy.max_pursue_distance = 0
dummy.distance_per_cycle = 0
dummy.resistances = {}
-- 2.1 renamed this field: `pollution_to_join_attack` is a data-stage error now.
dummy.absorptions_to_join_attack = {pollution = 0}
dummy.attack_parameters = table.deepcopy(dummy.attack_parameters or {})
dummy.attack_parameters.cooldown = 60 * 60 * 10
dummy.attack_parameters.range = 0
dummy.attack_parameters.damage_modifier = 0
-- Keep `ammo_type`: 2.1 refuses the whole data stage with "Key ammo_type not found in
-- property tree at ROOT.unit.<name>.attack_parameters" if it is set to nil. The dummy
-- never fires (cooldown is ten minutes and range is zero), so the deepcopy's own ammo
-- type is harmless -- it only has to exist.
data:extend{dummy}
