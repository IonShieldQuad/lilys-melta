-- Pipe-join verification harness (never shipped). Scene built on tick 2, not in
-- on_init: on_init runs before the map around the target position exists.
--
-- What it puts on the ground, all on one concrete pad far from the crash site:
--   A. the melta with a pipe on all four sides, each running on to a storage tank
--      (a real network, not four loose pipes)
--   B. a second melta plumbed on ONE side only, so the other three ports are bare
--      -- that is the "dead end shows a cap, not an open hole" case
--   C. the four junction shapes on their own, so a straight run, an L corner, a T
--      junction, a 4-way cross and a dead-ended pipe can each be looked at
--
-- It then takes screenshots on a schedule. Nothing is shot in a headless run
-- (game.players[1] is nil there), so the same save can be made with --create and
-- then loaded in a GUI launch for the visual pass.

local TURRET = "melta-turret"

local A = {x = 0, y = 200}          -- melta, four pipes
local B = {x = 16, y = 200}         -- melta, east pipe only
local SHAPES = {x = 0, y = 214}     -- the junction shapes

local function S()
  storage.pipes = storage.pipes or {}
  return storage.pipes
end

local function logf(fmt, ...)
  log("[pipes] " .. string.format(fmt, ...))
end

local function flatten(surface, x1, y1, x2, y2)
  local tiles = {}
  for y = y1, y2 do
    for x = x1, x2 do
      tiles[#tiles + 1] = {name = "refined-concrete", position = {x, y}}
    end
  end
  surface.set_tiles(tiles)
end

local function clear_area(surface, area)
  local n = 0
  for _, e in ipairs(surface.find_entities_filtered{area = area}) do
    if e.valid and e.type ~= "character" then
      e.destroy()
      n = n + 1
    end
  end
  return n
end

local function pipe(surface, x, y)
  local p = surface.create_entity{name = "pipe", position = {x, y},
                                  force = game.forces.player}
  if p then
    S()[#S() + 1] = p
  else
    logf("pipe at %.1f,%.1f FAILED", x, y)
  end
  return p
end

local function tank(surface, x, y)
  return surface.create_entity{name = "storage-tank", position = {x, y},
                               force = game.forces.player}
end

----------------------------------------------------------------- setup -------
local function build()
  local surface = game.surfaces[1]
  surface.always_day = true

  surface.request_to_generate_chunks({SHAPES.x, SHAPES.y}, 4)
  surface.force_generate_chunk_requests()

  local removed = clear_area(surface, {{-30, 180}, {34, 232}})
  flatten(surface, -16, 190, 26, 226)
  logf("cleared %d entities, laid concrete", removed)

  -- A: melta, one pipe per side, each running out to a tank
  local melta = surface.create_entity{name = TURRET, position = {A.x, A.y},
                                      force = game.forces.player, raise_built = true}
  if not melta then
    logf("FATAL: could not create %s", TURRET)
    return
  end
  A.x, A.y = melta.position.x, melta.position.y
  storage.melta_a = melta
  for _, d in ipairs({{0, -1}, {1, 0}, {0, 1}, {-1, 0}}) do
    -- pipe at 2.0, then three more so the run is a straight line into the tank
    for step = 2, 5 do
      pipe(surface, A.x + d[1] * step, A.y + d[2] * step)
    end
    tank(surface, A.x + d[1] * 6 + d[2] * 1, A.y + d[2] * 6 - d[1] * 1)
  end

  -- B: one-sided plumbing, three bare ports
  local melta_b = surface.create_entity{name = TURRET, position = {B.x, B.y},
                                        force = game.forces.player, raise_built = true}
  if melta_b then
    B.x, B.y = melta_b.position.x, melta_b.position.y
    for step = 2, 4 do
      pipe(surface, B.x + step, B.y)
    end
    tank(surface, B.x + 5.5, B.y + 1.5)
  else
    logf("FATAL: could not create the second melta")
  end

  -- C: the junction shapes
  local y = SHAPES.y
  -- straight run
  for x = -14, -10 do
    pipe(surface, x, y)
  end
  -- L corner
  pipe(surface, -6, y)
  pipe(surface, -5, y)
  pipe(surface, -5, y + 1)
  pipe(surface, -5, y + 2)
  -- T junction
  for x = -1, 1 do
    pipe(surface, x, y)
  end
  pipe(surface, 0, y + 1)
  pipe(surface, 0, y + 2)
  -- 4-way cross
  for x = 4, 6 do
    pipe(surface, x, y)
  end
  pipe(surface, 5, y - 1)
  pipe(surface, 5, y - 2)
  pipe(surface, 5, y + 1)
  pipe(surface, 5, y + 2)
  -- dead-ended run (two tiles that stop in open ground)
  for x = 9, 11 do
    pipe(surface, x, y)
  end
  logf("built %d pipes total", #S())

  -- fluid, so the networks are live and not just artwork
  for _, p in ipairs(S()) do
    local ok = pcall(function()
      p.fluidbox[1] = {name = "water", amount = 50, temperature = 15}
    end)
    if not ok then
      break
    end
  end
  logf("scene ready at tick %d; melta A %.1f,%.1f B %.1f,%.1f", game.tick,
       A.x, A.y, B.x, B.y)
end

---------------------------------------------------------------- shots -------
-- tick, path, position, zoom
local SHOTS = {
  {120, "01-overview",        {8, 207},   0.9},
  {165, "02-melta-four-way",  {0, 200.5}, 2.6},
  {210, "03-join-north",      {0, 198.6}, 4.0},
  {255, "04-join-east",       {1.4, 200}, 4.0},
  {300, "05-capped-ports",    {16, 200},  2.6},
  {345, "06-shapes",          {0, 214},   1.6},
  {390, "07-straight",        {-12, 214}, 3.2},
  {435, "08-corner",          {-5.5, 215}, 3.2},
  {480, "09-t-junction",      {0, 215},   3.2},
  {525, "10-cross",           {5, 214},   3.2},
  {570, "11-dead-end",        {10.5, 214}, 3.2},
  {615, "12-join-south",      {0, 201.8}, 4.0},
  {660, "13-join-west",       {-1.5, 200}, 4.0},
  {705, "14-capped-port-north", {16, 198.6}, 4.0},
  {750, "15-overview-close",  {0, 200.5}, 1.8},
}

local function shot(path, position, zoom)
  local player = game.players and game.players[1]
  if not player then
    return false
  end
  game.take_screenshot{
    player = player,
    position = position,
    resolution = {1920, 1080},
    zoom = zoom,
    path = "pipes/" .. path .. ".png",
    show_gui = false,
    show_entity_info = false,
    hide_fog = true,
    hide_clouds = true,
    hide_health_bars = true
  }
  return true
end

script.on_init(function()
  -- --create saves the map without ever running a tick, so the scene has to exist
  -- before the save is written: build it here, after forcing the chunks in. (The
  -- skill's "build on tick 2" rule is about maps that are *generated* while the
  -- screenshot runs; build() forces generation itself, so this is safe.)
  storage.built = true
  local ok, err = pcall(build)
  logf("init build -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
end)

script.on_nth_tick(2, function()
  if storage.built then
    return
  end
  storage.built = true
  local ok, err = pcall(build)
  logf("build -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
end)

script.on_nth_tick(15, function(event)
  if not storage.built then
    return
  end
  for _, s in ipairs(SHOTS) do
    if event.tick == s[1] then
      if shot(s[2], s[3], s[4]) then
        logf("shot %s at tick %d", s[2], event.tick)
      else
        logf("no player (headless): skipped %s", s[2])
      end
    end
  end
end)
