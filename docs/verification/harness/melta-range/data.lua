-- Range / quality / rotation probe for Lily's melta turret (never shipped).
--
-- Data stage: one static dummy -- a biter spawner that spawns nothing, fights
-- nothing and has 100 000 health, so a few beam pulses move its health by an
-- amount that is measurable (a float32 quantum of 0.008 at that size) without
-- ever killing it.
--
-- Why a spawner rather than a unit: `is_military_target` is what the turret's own
-- corridor test and the engine's targeting both filter on, and a spawner has no
-- movement code to fight the harness.

data:extend(
{
  (function()
    local dummy = table.deepcopy(data.raw["unit-spawner"]["biter-spawner"])
    dummy.name = "melta-dummy"
    dummy.max_health = 100000
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

-- A deliberately silly quality, to prove the mod's clamp: the engine would happily
-- scale the melta's range by 3 (48 tiles), the mod's beam stops at C.range_max (24)
-- and its retarget logic refuses a target it cannot burn. Only defined when the
-- quality mod is loaded -- without it there is no quality prototype table at all.
if data.raw["quality"] and data.raw["quality"]["legendary"] then
  data:extend(
  {
    {
      type = "quality",
      name = "melta-overclocked",
      level = 7,
      color = {255, 0, 255},
      order = "z[test]",
      subgroup = "qualities",
      icon = "__quality__/graphics/icons/quality-legendary.png",
      range_multiplier = 3
    }
  })
end
