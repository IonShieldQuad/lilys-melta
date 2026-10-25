-- Measurement harness (never shipped) -- control stage.
--
-- "How much damage does one melta pulse really do?" Two meltas on a concrete pad,
-- six tiles from their own dummy, each fuelled with a different fluid (light oil =
-- 1.00x, enriched melta fuel = 1.60x). Health is sampled every tick, so every pulse
-- is one measurable drop. The drop is the whole truth: the script's beam damage plus
-- anything the engine's own invisible stream adds on contact -- which is exactly the
-- number the tooltip has to report.
--
-- Runs headless (`--benchmark`), where there are no players; turrets act on their own.

local DUMMY = "melta-dummy"
local CASES = {
  {key = "A", fluid = "light-oil",  position = {x = 0,  y = 100}},
  {key = "B", fluid = "melta-fuel", position = {x = 40, y = 100}}
}

local function logf(fmt, ...)
  log("[measure] " .. string.format(fmt, ...))
end

local function build()
  local surface = game.surfaces[1]
  local ok, err = pcall(function()
    surface.request_to_generate_chunks(CASES[1].position, 6)
    surface.force_generate_chunk_requests()
  end)
  logf("chunks -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))

  local tiles = {}
  for y = 92, 106 do
    for x = -8, 48 do
      tiles[#tiles + 1] = {name = "refined-concrete", position = {x, y}}
    end
  end
  surface.set_tiles(tiles)

  storage.cases = {}
  for _, case in ipairs(CASES) do
    local turret = surface.create_entity{name = "melta-turret", position = case.position,
                                         force = game.forces.player, raise_built = true}
    if not turret then
      logf("%s melta FAILED", case.key)
    else
      turret.set_fluid(1, {name = case.fluid, amount = 500})
      local dummy = surface.create_entity{name = DUMMY,
        position = {case.position.x, case.position.y - 6}, force = game.forces.enemy}
      logf("%s melta at %.0f,%.0f fluid=%s count=%.0f dummy=%s hp=%.0f", case.key,
        case.position.x, case.position.y, case.fluid, turret.get_fluid_count(),
        tostring(dummy ~= nil), dummy and dummy.health or -1)
      storage.cases[#storage.cases + 1] = {
        key = case.key, fluid = case.fluid, turret = turret, dummy = dummy,
        last = dummy and dummy.health or 0, pulses = 0, total = 0, first = nil, last_drop = nil
      }
    end
  end
end

local function sample()
  for _, case in ipairs(storage.cases or {}) do
    local dummy = case.dummy
    if dummy and dummy.valid then
      local health = dummy.health
      if health < case.last - 0.005 then
        local drop = case.last - health
        case.pulses = case.pulses + 1
        case.total = case.total + drop
        case.first = case.first or drop
        case.last_drop = drop
        if case.pulses <= 3 or case.pulses % 10 == 0 then
          logf("%s pulse %d drop=%.2f (tick %d)", case.key, case.pulses, drop, game.tick)
        end
      end
      case.last = health
    end
  end
end

local function report()
  for _, case in ipairs(storage.cases or {}) do
    local count = case.turret and case.turret.valid and case.turret.get_fluid_count() or -1
    logf("%s SUMMARY %s: pulses=%d first=%.2f last=%.2f mean=%.2f total=%.1f fuel_left=%.0f",
      case.key, case.fluid, case.pulses, case.first or -1, case.last_drop or -1,
      case.pulses > 0 and (case.total / case.pulses) or -1, case.total, count)
  end
end

script.on_init(function()
  logf("on_init")
  build()
end)

script.on_event(defines.events.on_tick, function(event)
  if not storage.cases then
    return
  end
  sample()
  if event.tick == 1200 then
    report()
  end
end)
