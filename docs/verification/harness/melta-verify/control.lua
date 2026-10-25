-- Verification harness control stage (never shipped). See data.lua for the dummy.
--
-- Everything is built on tick 2, not in on_init: on_init runs before the map around
-- the target position exists, so a "clear the area" there finds nothing and the
-- freeplay crash site / trees stay in frame. Tick 2 has a real map.
--
-- Scene: the melta on a concrete pad with a pipe on all four sides, the three vanilla
-- turrets in a row beside it for scale, and a row of item-on-ground icons (the item
-- icon as the game actually draws it). Then the turret is walked through the four
-- compass directions with a static dummy target, with a screenshot during the swing
-- (charge glow, no beam) and once the beam is up.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"
local DUMMY = "melta-dummy"

-- far from the freeplay crash site, which sits on the spawn point
local MELTA = {x = 0, y = 200}
local ROW = {
  {"gun-turret", {6, 0}},
  {"flamethrower-turret", {10, 0}},
  {"laser-turret", {14, 0}}
}
local ICONS = {
  {"melta-turret", 0},
  {"gun-turret", 1},
  {"laser-turret", 2},
  {"flamethrower-turret", 3}
}

local function S()
  storage.verify = storage.verify or {}
  return storage.verify
end

local function logf(fmt, ...)
  log("[verify] " .. string.format(fmt, ...))
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

local function shot(path, position, zoom, extra)
  local opts = {
    position = position,
    resolution = {1920, 1080},
    zoom = zoom,
    path = "melta/" .. path .. ".png",
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
    opts.surface = game.surfaces[1]
  end
  for k, v in pairs(extra or {}) do
    opts[k] = v
  end
  local ok, err = pcall(function()
    game.take_screenshot(opts)
  end)
  logf("shot %-20s -> %s%s", path, tostring(ok), ok and "" or (" err=" .. tostring(err)))
end

local function orientation_text(t)
  local ok, o = pcall(function()
    return t.orientation
  end)
  return ok and string.format("%.4f", o or -1) or "n/a"
end

local function state(label)
  local t = S().turret
  if not t or not t.valid then
    logf("%s: turret invalid", label)
    return
  end
  local dummies = game.surfaces[1].find_entities_filtered{name = DUMMY}
  local hp = dummies[1] and dummies[1].health or -1
  logf("%s: orient=%s dir=%s fluid=%.1f hp=%.1f dummies=%d dummy_hp=%.0f tick=%d",
    label, orientation_text(t), tostring(t.direction), t.get_fluid_count(), t.health,
    #dummies, hp, game.tick)
end

local function dummy_at(surface, dx, dy, distance)
  for _, e in ipairs(surface.find_entities_filtered{name = DUMMY}) do
    if e.valid then
      e.destroy()
    end
  end
  local d = surface.create_entity{
    name = DUMMY,
    position = {MELTA.x + dx * distance, MELTA.y + dy * distance},
    force = game.forces.enemy
  }
  if d then
    S().dummy = d
    logf("dummy spawned %d,%d at %.1f,%.1f", dx, dy, d.position.x, d.position.y)
  else
    logf("dummy spawn FAILED at %d,%d", dx, dy)
  end
end

local function spawn_biters(surface, dx, dy)
  local made = 0
  for _, distance in ipairs({4, 5, 6}) do
    local biter = surface.create_entity{
      name = "small-biter",
      position = {MELTA.x + dx * distance, MELTA.y + dy * distance},
      force = game.forces.enemy
    }
    if biter then
      made = made + 1
    end
  end
  logf("spawned %d small biters in the beam line", made)
end

local function count_biters(surface)
  return #surface.find_entities_filtered{area = {{MELTA.x - 20, MELTA.y - 20}, {MELTA.x + 20, MELTA.y + 20}},
                                         force = "enemy", type = "unit"}
end

local function icon_row(surface)
  for _, entry in ipairs(ICONS) do
    local ok, e = pcall(function()
      return surface.create_entity{
        name = "item-on-ground",
        stack = {name = entry[1], count = 1},
        position = {MELTA.x + 8 + entry[2], MELTA.y + 6.5}
      }
    end)
    logf("icon item %-22s -> %s", entry[1], ok and (e and "ok" or "failed") or tostring(e))
  end
end

----------------------------------------------------------------- setup -------
local function build()
  local surface = game.surfaces[1]
  surface.always_day = true

  local ok_chunks, err_chunks = pcall(function()
    surface.request_to_generate_chunks({MELTA.x, MELTA.y}, 3)
    surface.force_generate_chunk_requests()
  end)
  logf("chunk generation -> %s%s", tostring(ok_chunks),
    ok_chunks and "" or (" err=" .. tostring(err_chunks)))

  local turret
  do
    local removed = clear_area(surface, {{MELTA.x - 30, MELTA.y - 24}, {MELTA.x + 30, MELTA.y + 20}})
    flatten(surface, MELTA.x - 26, MELTA.y - 18, MELTA.x + 26, MELTA.y + 16)
    logf("cleared %d entities, laid concrete", removed)
    turret = surface.create_entity{name = TURRET, position = {MELTA.x, MELTA.y},
                                   force = game.forces.player, raise_built = true}
  end
  if not turret then
    logf("FATAL: could not create %s", TURRET)
    return
  end
  MELTA.x, MELTA.y = turret.position.x, turret.position.y
  S().turret = turret
  S().pipes = {}

  for _, p in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
    local pipe = surface.create_entity{
      name = "pipe",
      position = {MELTA.x + p[1], MELTA.y + p[2]},
      force = game.forces.player
    }
    if pipe then
      S().pipes[#S().pipes + 1] = pipe
    else
      logf("pipe at %d,%d FAILED", p[1], p[2])
    end
  end
  logf("melta at %.1f,%.1f with %d/4 pipes", MELTA.x, MELTA.y, #S().pipes)

  local conns = turret.get_fluid_box_pipe_connections(1) or {}
  logf("pipe connections: %d", #conns)

  for _, entry in ipairs(ROW) do
    local ok, e = pcall(function()
      return surface.create_entity{name = entry[1], position = {MELTA.x + entry[2][1], MELTA.y + entry[2][2]},
                                   force = game.forces.player}
    end)
    logf("row %-22s at x+%d: %s", entry[1], entry[2][1],
      ok and (e and "ok" or "create failed") or ("error " .. tostring(e)))
  end

  local inv = turret.get_inventory(defines.inventory.turret_ammo)
  logf("turret_ammo inventory: %s", inv and tostring(#inv) or "none")
  logf("status with no fuel: %s", tostring(turret.status))

  local player = game.players and game.players[1]
  if player and player.character then
    player.teleport({MELTA.x + 24.5, MELTA.y + 12.5}, surface)
    logf("character moved out of frame")
  end
  if player then
    -- the quickbar signature is not obvious from the error text, so try the likely
    -- shapes and log which one the engine accepts
    local variants = {
      {"(slot, item)", function() player.set_quick_bar_slot(1, "melta-turret") end},
      {"(page, slot, item)", function() player.set_quick_bar_slot(1, 1, "melta-turret") end},
      {"(item, slot)", function() player.set_quick_bar_slot("melta-turret", 1) end}
    }
    for _, variant in ipairs(variants) do
      local ok, err = pcall(variant[2])
      logf("quickbar %-20s -> %s%s", variant[1], tostring(ok), ok and "" or (" err=" .. tostring(err)))
      if ok then
        break
      end
    end
  end
end

----------------------------------------------------------------- ticks -------
local function on_tick(event)
  local tick = event.tick
  local surface = game.surfaces[1]

  if tick == 2 then
    build()
  elseif tick == 6 then
    icon_row(surface)
  elseif tick % 100 == 0 then
    state("heartbeat")
  end

  if tick == 20 then
    state("t20")
    shot("01-scale-row", {MELTA.x + 6, MELTA.y - 1}, 0.62)
    shot("02-melta-closeup", MELTA, 2.0)
    shot("03-pipes-overview", MELTA, 1.3)
  elseif tick == 26 then
    shot("04-icon-row", {MELTA.x + 9.5, MELTA.y + 6.5}, 1.6)

  elseif tick == 30 then
    for _, pipe in ipairs(S().pipes) do
      pipe.set_fluid(1, {name = FLUID, amount = 100})
    end
    state("t30 after filling the four pipes")

  elseif tick == 45 then
    dummy_at(surface, 0, -1, 9)
    spawn_biters(surface, 0, -1)
  elseif tick == 60 then
    state("t60 (biters should be dying)")
    logf("live biters: %d", count_biters(surface))
  elseif tick == 79 then
    logf("live biters at t79: %d", count_biters(surface))
  elseif tick == 80 then
    state("t80 north (aligned from the start)")
    shot("05-beam-north", {MELTA.x, MELTA.y - 4}, 1.25)
  elseif tick == 84 then
    shot("06-beam-north-b", {MELTA.x, MELTA.y - 4}, 1.25)

  elseif tick == 90 then
    dummy_at(surface, 1, 0, 9)
  elseif tick == 98 then
    state("t98 mid-swing east")
    shot("07-windup-east", {MELTA.x + 4, MELTA.y}, 1.25)
  elseif tick == 145 then
    state("t145 east (should be on target)")
    shot("08-beam-east", {MELTA.x + 4, MELTA.y}, 1.25)

  elseif tick == 150 then
    dummy_at(surface, 0, 1, 9)
  elseif tick == 158 then
    state("t158 mid-swing south")
    shot("09-windup-south", {MELTA.x, MELTA.y + 4}, 1.25)
  elseif tick == 205 then
    state("t205 south")
    shot("10-beam-south", {MELTA.x, MELTA.y + 4}, 1.25)

  elseif tick == 210 then
    dummy_at(surface, -1, 0, 9)
  elseif tick == 218 then
    state("t218 mid-swing west")
    shot("11-windup-west", {MELTA.x - 4, MELTA.y}, 1.25)
  elseif tick == 265 then
    state("t265 west")
    shot("12-beam-west", {MELTA.x - 4, MELTA.y}, 1.25)

  elseif tick == 272 then
    state("t272 final")
    shot("13-gui", MELTA, 1.6, {show_gui = true})
  elseif tick == 285 then
    local ok, err = pcall(function()
      game.server_save("verify-after")
    end)
    logf("server_save -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
    logf("VERIFY DONE")
  end
end

script.on_init(function()
  logf("on_init (scene is built on tick 2)")
end)

script.on_event(defines.events.on_tick, on_tick)
