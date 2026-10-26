-- Balance probe (harness, never shipped) -- control stage.
--
-- One scene, six research tiers, four dummies. For each tier it builds a fresh
-- turret + dummy for every dummy kind, measures every pulse drop on every tick and
-- then destroys the pair, so "cold" and "hot" are read from the same pair:
--
--   first drop after the beam starts  = cold barrel (charge 0 at the first pulse)
--   drops after 250 ticks of fire     = fully spun up
--
-- Reported per tier and per dummy kind: per-pulse damage (cold / hot), pulse count
-- and the interval between pulses (which is where the firing-speed research shows
-- up), and the dps both ways. Numbers are the real drops in health, so they carry
-- the engine's resistance maths -- which is the whole point of the armoured and
-- resistant dummies.
--
-- Runs headless: `--create` builds the scene in on_init, `--benchmark` ticks it.

local CASE_DEFS =
{
  {key = "melta-plain", turret = "melta-turret", dummy = "melta-dummy", fuel = "light-oil"},
  {key = "melta-flat", turret = "melta-turret", dummy = "melta-dummy-flat", fuel = "light-oil"},
  {key = "melta-percent", turret = "melta-turret", dummy = "melta-dummy-percent", fuel = "light-oil"},
  {key = "melta-fireimmune", turret = "melta-turret", dummy = "melta-dummy-fireimmune", fuel = "light-oil"},
  -- The gun turret on its best ammo, against the same unarmoured dummy: its damage
  -- and rate come from the engine, so it is the reference the melta is judged by.
  -- (A tesla turret case was tried and dropped: an electric turret needs a powered
  -- grid, and a headless --benchmark scene has none; its numbers are read off
  -- space-age/prototypes/entity/turrets.lua instead.)
  {key = "gun-uranium", turret = "gun-turret", dummy = "melta-dummy", ammo = "uranium-rounds-magazine", count = 10}
}

-- research tier -> the technologies that must be finished. Vanilla 2.1.23 ladders:
-- refined-flammables (fire damage, +20/+20/+20/+30/+30/+40 %) and
-- weapon-shooting-speed (bullet firing speed, +10/+20/+20/+30/+30/+40 %).
local TIERS =
{
  {"refined-flammables-1", "weapon-shooting-speed-1", "physical-projectile-damage-1"},
  {"refined-flammables-2", "weapon-shooting-speed-2", "physical-projectile-damage-2"},
  {"refined-flammables-3", "weapon-shooting-speed-3", "physical-projectile-damage-3"},
  {"refined-flammables-4", "weapon-shooting-speed-4", "physical-projectile-damage-4"},
  {"refined-flammables-5", "weapon-shooting-speed-5", "physical-projectile-damage-5"}
}

local HOT_SAMPLE_TICK = 250
local TURNS = 40   -- tiles between cases: far beyond the beam corridor
local Y = 100

local function logf(fmt, ...)
  log("[balance] " .. string.format(fmt, ...))
end

local function research(tier)
  local force = game.forces.player
  for level = 1, tier do
    for _, name in ipairs(TIERS[level]) do
      local technology = force.technologies[name]
      if technology and not technology.researched then
        technology.researched = true
      end
    end
  end
end

-- What the researched technologies actually carry. Logged from inside the game so the
-- spec table is read off vanilla 2.1.23 rather than off a dump taken in a modpack
-- install (other mods rewrite these ladders, and the numbers differ).
local function report_research(tier)
  local force = game.forces.player
  local damage, rate = 0, 0
  local parts = {}
  for _, technology in pairs(force.technologies) do
    if technology.researched then
      local effects = technology.prototype and technology.prototype.effects
      if effects then
        local level = technology.level or 1
        for _, effect in pairs(effects) do
          if effect.type == "ammo-damage" and effect.ammo_category == "flamethrower" then
            damage = damage + (effect.modifier or 0)
            parts[#parts + 1] = string.format("%s dmg+%.2f", technology.name, effect.modifier or 0)
          elseif effect.type == "gun-speed" and effect.ammo_category == "melta" then
            rate = rate + (effect.modifier or 0)
            parts[#parts + 1] = string.format("%s rate+%.2f", technology.name, effect.modifier or 0)
          end
        end
        logf("  tech %s level=%s max=%s effect0=%s", technology.name, tostring(technology.level),
          tostring(technology.prototype.max_level),
          tostring(effects[1] and (effects[1].type .. "/" .. tostring(effects[1].ammo_category) .. "/" .. tostring(effects[1].modifier))))
      end
    end
  end
  logf("tier %d research: fire damage +%.2f, firing speed +%.2f (the mod compounds the damage bonus by its own exponent; see constants.lua)",
    tier, damage, rate)
  logf("tier %d research parts: %s", tier, table.concat(parts, ", "))
end

local function build()
  local surface = game.surfaces[1]
  pcall(function()
    surface.request_to_generate_chunks({x = 0, y = Y}, 8)
    surface.force_generate_chunk_requests()
  end)
  local tiles = {}
  for y = Y - 10, Y + 10 do
    for x = -10, TURNS * #CASE_DEFS do
      tiles[#tiles + 1] = {name = "refined-concrete", position = {x, y}}
    end
  end
  surface.set_tiles(tiles)

  storage.tier = storage.tier or 0
  research(storage.tier)
  report_research(storage.tier)
  storage.cases = {}
  for index, definition in ipairs(CASE_DEFS) do
    local x = (index - 1) * TURNS
    if not (prototypes.entity[definition.turret] and prototypes.entity[definition.dummy]) then
      logf("tier %d %s SKIPPED (prototype not in this install)", storage.tier or 0, definition.key)
    else
    -- The enemy force, and the turret on the player force, so the engine treats
    -- the dummy as a target without either force being hostile to the other scene.
    local turret = surface.create_entity
    {
      name = definition.turret, position = {x, Y}, force = game.forces.player, raise_built = true
    }
    local dummy = surface.create_entity
    {
      name = definition.dummy, position = {x, Y - 6}, force = game.forces.enemy
    }
    if not turret or not dummy then
      logf("tier %d %s BUILD FAILED turret=%s dummy=%s", storage.tier, definition.key,
        tostring(turret ~= nil), tostring(dummy ~= nil))
    else
      if definition.fuel then
        turret.set_fluid(1, {name = definition.fuel, amount = 1000})
      end
      if definition.ammo then
        turret.insert{name = definition.ammo, count = definition.count or 10}
      end
      -- An electric turret needs a grid to draw from. A creative energy interface
      -- supplies one without a solar/daylight dependency (this scene runs headless,
      -- where the sun position would otherwise decide the answer).
      local power_source
      if definition.power then
        power_source = surface.create_entity{name = "electric-energy-interface",
                                             position = {x + 3, Y}, force = game.forces.player}
        if power_source then
          pcall(function()
            power_source.electric_interface_mode = defines.electric_interface_mode.output
            power_source.power_production = 10000000
          end)
        end
      end
      storage.cases[#storage.cases + 1] =
      {
        key = definition.key, turret = turret, dummy = dummy, power = power_source,
        last = dummy.health, drops = {}, ticks = {}, started = nil
      }
    end
    end
  end
  logf("tier %d built %d cases", storage.tier, #storage.cases)
end

local function sample(tick)
  for _, case in ipairs(storage.cases or {}) do
    local dummy = case.dummy
    if dummy and dummy.valid then
      local health = dummy.health
      if health < case.last - 0.005 then
        local drop = case.last - health
        case.drops[#case.drops + 1] = drop
        case.ticks[#case.ticks + 1] = tick
        case.started = case.started or tick
      end
      case.last = health
    end
  end
end

local function median_interval(case)
  local gaps = {}
  for index = 2, #case.ticks do
    gaps[#gaps + 1] = case.ticks[index] - case.ticks[index - 1]
  end
  if #gaps == 0 then
    return 0
  end
  table.sort(gaps)
  return gaps[math.ceil(#gaps / 2)]
end

local function report()
  local tier = storage.tier or 0
  for _, case in ipairs(storage.cases or {}) do
    local count = #case.drops
    local cold = count > 0 and case.drops[1] or 0
    -- mean of the last three drops: after 250 ticks the charge is pinned at 1
    local hot_sum, hot_n = 0, 0
    for index = math.max(1, count - 2), count do
      hot_sum = hot_sum + case.drops[index]
      hot_n = hot_n + 1
    end
    local hot = hot_n > 0 and (hot_sum / hot_n) or 0
    local interval = median_interval(case)
    local rate = interval > 0 and (60 / interval) or 0
    -- window dps: everything the dummy lost over the whole firing window, which is
    -- the number that does not depend on where a pulse happened to land
    local first = case.ticks[1] or 0
    local last = case.ticks[count] or 0
    local window = last - first
    local total = 0
    for _, drop in ipairs(case.drops) do
      total = total + drop
    end
    local window_dps = window > 0 and (total / (window / 60)) or 0
    logf("tier %d %-16s n=%2d first=%7.3f last=%7.3f interval=%.2f rate=%5.2f window_dps=%8.2f",
      tier, case.key, count, cold, hot, interval, rate, window_dps)
  end
end

local function teardown()
  for _, case in ipairs(storage.cases or {}) do
    for _, entity in ipairs({case.turret, case.dummy, case.power}) do
      if entity and entity.valid then
        pcall(function()
          entity.destroy()
        end)
      end
    end
  end
  storage.cases = {}
end

script.on_init(function()
  storage.tier = 0
  storage.phase = "running"
  logf("on_init")
  build()
end)

script.on_event(defines.events.on_tick, function(event)
  if not storage.cases or storage.phase ~= "running" then
    return
  end
  local tick = event.tick
  sample(tick)

  local due = storage.report_at
  if not due then
    storage.report_at = tick + HOT_SAMPLE_TICK
    return
  end
  if tick < due then
    return
  end

  report()
  teardown()
  storage.report_at = nil

  if (storage.tier or 0) >= #TIERS then
    storage.phase = "done"
    logf("BALANCE PROBE DONE")
    return
  end

  storage.tier = storage.tier + 1
  research(storage.tier)
  build()
end)
