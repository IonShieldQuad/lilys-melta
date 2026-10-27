-- Visual probe data stage (never shipped): a target that survives a beam for the whole run.
data:extend(
{
  (function()
    local dummy = table.deepcopy(data.raw["unit-spawner"]["biter-spawner"])
    dummy.name = "melta-dummy"
    dummy.max_health = 5000000
    dummy.healing_per_tick = 0
    dummy.max_count_of_owned_units = 0
    dummy.max_group_size = 1
    dummy.spawning_cooldown = {3600, 3600}
    dummy.absorptions_per_second = nil
    dummy.corpse = nil
    dummy.dying_sound = nil
    dummy.dying_animation = nil
    return dummy
  end)()
})
