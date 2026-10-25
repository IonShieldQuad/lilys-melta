-- Verification harness for Lily's melta turret (never shipped).
--
-- Data stage: one dummy target -- a copy of the biter spawner with the health of a
-- small mountain and no ability to spawn units or fight back, so the turret has a
-- static thing to cut for as long as the screenshots need it.
--
-- Control stage: builds one scene on a concrete pad (the melta with a pipe on all
-- four sides, and the three vanilla turrets in a row beside it for scale), then on a
-- fixed tick schedule puts a dummy in front of the turret in each compass direction
-- and grabs a screenshot during the swing (charge glow, no beam) and once the beam is
-- up. Screenshots land in script-output/melta/, everything else is logged with the
-- "[verify]" prefix into factorio-current.log.

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
    dummy.corpse = nil
    return dummy
  end)()
})
