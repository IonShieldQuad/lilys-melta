-- Measurement harness (never shipped) -- data stage.
--
-- Two stationary, unarmoured dummies with 1e6 hp: one per fuel test. 1e6 rather than
-- 1e9 on purpose: entity health is float32 and at 1e9 the quantum is 64 damage, which
-- would hide the whole spin-up ramp. `resistances = {}` means every point of fire and
-- physical lands, so a measured pulse is the whole truth.
data:extend(
{
  (function()
    local dummy = table.deepcopy(data.raw["unit"]["small-biter"])
    dummy.name = "melta-dummy"
    dummy.max_health = 1000000
    dummy.healing_per_tick = 0
    dummy.movement_speed = 0
    dummy.vision_distance = 0
    dummy.max_pursue_distance = 0
    dummy.resistances = {}
    dummy.dying_sound = nil
    dummy.corpse = nil
    dummy.dying_animation = nil
    dummy.collision_box = {{-0.4, -0.4}, {0.4, 0.4}}
    dummy.selection_box = {{-0.5, -0.5}, {0.5, 0.5}}
    if dummy.attack_parameters then
      dummy.attack_parameters.cooldown = 100000
      dummy.attack_parameters.range = 0
    end
    return dummy
  end)()
})
