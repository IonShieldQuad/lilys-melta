-- Engine mitigation probe (never shipped): what does LuaEntity.damage() do with a
-- prototype's `decrease` and `percent`? Four dummies, one 100-damage hit each, and a
-- second dummy per armour case that gets the melta's compensation trick
-- (`amount + decrease`) so the analysis can show the trick lands on the nominal number.
local CASES =
{
  {key = "no_res",        decrease = 0,  percent = 0},
  {key = "flat12",        decrease = 12, percent = 0},
  {key = "pct10",         decrease = 0,  percent = 10},
  {key = "flat12_pct10",  decrease = 12, percent = 10},
  {key = "flat12_pct100", decrease = 12, percent = 100},
  {key = "neg5_pct10",    decrease = -5, percent = 10}
}

local function logf(fmt, ...) log("[mitprobe] " .. string.format(fmt, ...)) end

script.on_init(function()
  local surface = game.surfaces[1]
  surface.request_to_generate_chunks({x = 0, y = 0}, 2)
  surface.force_generate_chunk_requests()

  local x = 0
  for _, case in ipairs(CASES) do
    local plain = surface.create_entity{name = "mit-probe-plain-" .. case.key, position = {x, 0},
                                        force = game.forces.enemy}
    local comp = surface.create_entity{name = "mit-probe-comp-" .. case.key, position = {x, 4},
                                       force = game.forces.enemy}
    if not plain or not comp then
      logf("%s CREATE FAILED", case.key)
    else
      local before = plain.health
      local ret = plain.damage(100, game.forces.player, "physical")
      local after = plain.health
      local b2 = comp.health
      local ret2 = comp.damage(100 + case.decrease, game.forces.player, "physical")
      local a2 = comp.health
      logf("%-14s decrease=%-4d percent=%-4d | hit 100 -> landed %7.3f (returned %s) | hit %d -> landed %7.3f (returned %s)",
        case.key, case.decrease, case.percent, before - after, tostring(ret),
        100 + case.decrease, b2 - a2, tostring(ret2))
    end
    x = x + 4
  end
end)
