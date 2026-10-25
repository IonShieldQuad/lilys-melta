-- Beam probe control stage (never shipped).
--
-- Scene: six melta turrets in a row on a concrete pad, each with its own fat dummy nine
-- tiles north, so all six lance at the same time. Then:
--   * every dummy is destroyed at once   -> all six lances must fade, none may stick
--   * one turret is destroyed mid-beam   -> its lance must fade, none may stick
--   * render objects are counted before, during and after -> nothing may leak
--   * a Lua profiler measures script time over a window of six turrets firing
--
-- The same probe runs against the pre-rework tree, so the two runs differ only in the
-- mod: same map, same turrets, same ticks, same shots. The whole schedule is kept under
-- 600 ticks because other cards on this machine kill factorio.exe by image name, and a
-- long run gets shot in the back.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"
local DUMMY = "melta-dummy"

local Y = 200
local SPOTS = {0, 6, 12, 18, 24, 30}
local PROFILE_TICKS = 178

local function S()
  storage.probe = storage.probe or {}
  return storage.probe
end

local function logf(fmt, ...)
  log("[beam] " .. string.format(fmt, ...))
end

local function surface()
  return game.surfaces[1]
end

local function objects()
  local ok, n = pcall(function()
    return #rendering.get_all_objects("lilys-melta")
  end)
  return ok and n or -1
end

local function count(label)
  logf("%s: render objects ours=%d turrets=%d", label or "count", objects(),
    #(S().turrets or {}))
end

local function shot(name, position, zoom)
  local opts =
  {
    position = position,
    resolution = {1920, 1080},
    zoom = zoom,
    path = "beam/" .. name .. ".png",
    show_gui = false,
    show_entity_info = false,
    hide_fog = true,
    hide_clouds = true,
    hide_health_bars = true
  }
  local player = game.players and game.players[1]
  if player then
    opts.player = player
  else
    opts.surface = surface()
  end
  local ok, err = pcall(function() game.take_screenshot(opts) end)
  logf("shot %-24s -> %s%s", name, tostring(ok), ok and "" or (" err=" .. tostring(err)))
end

local function flatten(x1, y1, x2, y2)
  local tiles = {}
  for y = y1, y2 do
    for x = x1, x2 do
      tiles[#tiles + 1] = {name = "refined-concrete", position = {x, y}}
    end
  end
  surface().set_tiles(tiles)
end

local function build()
  local s = surface()
  s.always_day = true
  -- the whole schedule has to fit in a couple of seconds of wall time: other cards on
  -- this machine close whatever Factorio window is in front of them, which includes
  -- this one. Script time per tick is unaffected by game speed, so the profiler number
  -- stays comparable.
  game.speed = 4
  pcall(function()
    s.request_to_generate_chunks({15, Y}, 4)
    s.force_generate_chunk_requests()
  end)
  for _, e in ipairs(s.find_entities_filtered{area = {{-12, Y - 22}, {44, Y + 14}}}) do
    if e.valid and e.type ~= "character" then
      e.destroy()
    end
  end
  flatten(-12, Y - 20, 44, Y + 12)

  S().turrets = {}
  S().dummies = {}
  for index, x in ipairs(SPOTS) do
    local turret = s.create_entity{name = TURRET, position = {x, Y}, force = game.forces.player,
                                   raise_built = true}
    if not turret then
      logf("FATAL: turret %d failed", index)
      return
    end
    S().turrets[index] = turret
    local dummy = s.create_entity{name = DUMMY, position = {x, Y - 9}, force = game.forces.enemy}
    S().dummies[index] = dummy
    logf("turret %d at %.1f,%.1f dummy=%s", index, turret.position.x, turret.position.y,
      tostring(dummy ~= nil))
  end

  local player = game.players and game.players[1]
  if player and player.character then
    player.teleport({20, Y + 24}, s)
    logf("character parked out of frame")
  end
end

local function fuel()
  for index, turret in ipairs(S().turrets or {}) do
    if turret and turret.valid then
      local ok, inserted = pcall(function()
        return turret.insert_fluid{name = FLUID, amount = 400}
      end)
      logf("turret %d fluid %.1f (insert=%s)", index, turret.get_fluid_count(FLUID),
        ok and tostring(inserted) or "error")
    end
  end
end

local function respawn_dummies()
  local s = surface()
  for index, x in ipairs(SPOTS) do
    local turret = S().turrets and S().turrets[index]
    if turret and turret.valid then
      S().dummies[index] = s.create_entity{name = DUMMY, position = {x, Y - 9},
                                           force = game.forces.enemy}
    end
  end
  logf("dummies respawned")
end

local function kill_dummies()
  local killed = 0
  for _, dummy in pairs(S().dummies or {}) do
    if dummy and dummy.valid then
      dummy.destroy()
      killed = killed + 1
    end
  end
  logf("killed %d dummies (every turret loses its target at once)", killed)
end

local function firing_state(label)
  local fired, idle, gone = 0, 0, 0
  for _, turret in ipairs(S().turrets or {}) do
    if turret and turret.valid then
      if turret.shooting_target then
        fired = fired + 1
      else
        idle = idle + 1
      end
    else
      gone = gone + 1
    end
  end
  logf("%s: firing=%d idle=%d gone=%d objects=%d", label, fired, idle, gone, objects())
end

local function on_tick(event)
  local tick = event.tick
  local s = surface()

  if tick == 2 then
    build()
  elseif tick == 6 then
    fuel()
    count("t6")
  elseif tick == 170 then
    shot("01-single-close", {0, Y - 4}, 2.0)
    shot("02-six-firing", {15, Y - 5}, 0.55)
  elseif tick == 174 then
    shot("03-beam-mid", {12, Y - 4}, 1.25)
  elseif tick == 178 then
    firing_state("t178 all firing")
    count("t178")
    S().profiler = helpers.create_profiler()
    logf("script profiler started")
  elseif tick == 178 + PROFILE_TICKS then
    local profiler = S().profiler
    if profiler then
      profiler.stop()
      profiler.divide(PROFILE_TICKS)
      S().profiler = nil
      -- a LuaProfiler can only be *printed*; the raw time is deliberately not readable
      -- from Lua, so it goes into the log as a localised string
      log({"", "[beam] script time per tick, six meltas firing: ", profiler})
    end
  elseif tick == 360 then
    kill_dummies()
  elseif tick == 363 then
    shot("04-beams-fading", {15, Y - 5}, 0.55)
    count("t363 (3 ticks after every target died)")
  elseif tick == 376 then
    shot("05-beams-gone", {15, Y - 5}, 0.55)
    count("t376 (15 ticks after every target died)")
  elseif tick == 380 then
    firing_state("t380 after every target died")
  elseif tick == 385 then
    respawn_dummies()
  elseif tick == 460 then
    local turret = S().turrets and S().turrets[3]
    if turret and turret.valid then
      logf("destroying turret 3 mid-beam (shooting_target=%s)",
        tostring(turret.shooting_target ~= nil))
      turret.destroy{raise_destroy = true}
    end
  elseif tick == 463 then
    shot("06-turret-dead-fading", {12, Y - 4}, 1.25)
    count("t463 (3 ticks after a turret died mid-beam)")
  elseif tick == 476 then
    shot("07-turret-dead-gone", {12, Y - 4}, 1.25)
    count("t476 (15 ticks after a turret died mid-beam)")
  elseif tick == 480 then
    firing_state("t480 after turret death")
  elseif tick == 490 then
    -- how the lance reads when the ground is dark: same shots, lights out
    local ok, err = pcall(function()
      s.always_day = false
      s.daytime = 0.25
    end)
    logf("night switch -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
  elseif tick == 520 then
    shot("08-night", {0, Y - 4}, 1.25)
    shot("09-night-six", {15, Y - 5}, 0.55)
  elseif tick == 530 then
    shot("10-night-wide", {15, Y - 5}, 1.0)
  elseif tick == 540 then
    count("t540 final")
    logf("BEAM PROBE DONE")
  end
end

script.on_init(function()
  logf("on_init (scene is built on tick 2)")
end)

script.on_event(defines.events.on_tick, on_tick)
