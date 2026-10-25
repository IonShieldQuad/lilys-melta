-- Beam probe harness (never shipped with the mod).
--
-- Data stage: a dummy target with the health of a small mountain, so a beam can be
-- photographed mid-burn without the target evaporating.
--
-- Control stage: six meltas in a row, each with its own dummy, all firing at once;
-- then it kills one dummy and one *turret* out from under a live beam to prove the
-- lance fades instead of sticking, then counts render objects to prove nothing leaked.

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
