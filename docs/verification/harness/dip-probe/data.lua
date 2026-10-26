-- An immortal, stationary, harmless target so a turret can be measured.
local dummy = table.deepcopy(data.raw["unit"]["small-biter"])
dummy.name = "dip-dummy"
dummy.max_health = 1000000
dummy.healing_per_tick = 0
dummy.movement_speed = 0
dummy.vision_distance = 0
dummy.max_pursue_distance = 0
dummy.distance_per_frame = 0
dummy.resistances = {}
dummy.attack_parameters = dummy.attack_parameters or {}
dummy.attack_parameters.cooldown = 600000
dummy.attack_parameters.range = 1
dummy.attack_parameters.min_range = 0

local dummy2 = table.deepcopy(dummy)
dummy2.name = "dip-dummy-flame"
dummy2.resistances = {}

data:extend({dummy, dummy2})
