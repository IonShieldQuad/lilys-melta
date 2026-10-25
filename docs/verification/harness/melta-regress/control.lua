-- Regression probe for the melta (never shipped).
--
-- Phase based, so it works in any run: the schedule starts on the first tick after
-- the mod sees the game, whether that is a fresh map or a reload. If storage already
-- holds a turret (i.e. this is a reload) it records the surviving state and stops
-- instead of rebuilding.
--
-- Everything is logged with "[regress]"; every step is pcall'd so one failure does
-- not stop the rest.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"

local MELTA = {x = 0, y = 200}

local function R()
  storage.regress = storage.regress or {}
  return storage.regress
end

local function logf(fmt, ...)
  log("[regress] " .. string.format(fmt, ...))
end

local function ok_log(label, fn)
  local ok, a = pcall(fn)
  if ok then
    logf("%-36s OK   %s", label, tostring(a or ""))
  else
    logf("%-36s FAIL %s", label, tostring(a))
  end
  return ok, a
end

local function turret()
  local t = R().turret
  if t and t.valid then
    return t
  end
  return nil
end

local function state(label)
  local t = turret()
  if not t then
    logf("%s: turret gone", label)
    return
  end
  logf("%s: valid dir=%s orient=%.4f fluid=%.1f hp=%.1f status=%s",
    label, tostring(t.direction), t.orientation or -1, t.get_fluid_count(), t.health, tostring(t.status))
end

local function conn_set(t)
  local out = {}
  for _, c in ipairs(t.get_fluid_box_pipe_connections(1) or {}) do
    out[#out + 1] = string.format("%.2f,%.2f", c.position.x, c.position.y)
  end
  table.sort(out)
  return table.concat(out, " ")
end

local function count_units(origin_x, origin_y)
  return #game.surfaces[1].find_entities_filtered{
    area = {{origin_x - 20, origin_y - 20}, {origin_x + 20, origin_y + 20}},
    force = "enemy", type = "unit"}
end

local function shot(path, position, zoom, extra)
  local opts = {
    position = position,
    resolution = {1920, 1080},
    zoom = zoom,
    path = "melta-regress/" .. path .. ".png",
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
  logf("shot %-22s -> %s%s", path, tostring(ok), ok and "" or (" err=" .. tostring(err)))
end

local function feed(t, offset_x)
  local surface = game.surfaces[1]
  local made = 0
  for _, p in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
    local pipe = surface.create_entity{name = "pipe",
                                       position = {t.position.x + p[1], t.position.y + p[2]},
                                       force = game.forces.player}
    if pipe then
      pipe.set_fluid(1, {name = FLUID, amount = 100})
      made = made + 1
    end
  end
  return made
end

local function build()
  local surface = game.surfaces[1]
  surface.always_day = true
  ok_log("generate chunks", function()
    surface.request_to_generate_chunks({MELTA.x, MELTA.y}, 3)
    surface.force_generate_chunk_requests()
    return "ok"
  end)

  for _, e in ipairs(surface.find_entities_filtered{area = {{MELTA.x - 30, MELTA.y - 24}, {MELTA.x + 30, MELTA.y + 24}}}) do
    if e.valid and e.type ~= "character" then
      e.destroy()
    end
  end

  local _, t = ok_log("create turret (raise_built)", function()
    return surface.create_entity{name = TURRET, position = {MELTA.x, MELTA.y},
                                 force = game.forces.player, raise_built = true}
  end)
  if not t or not t.valid then
    logf("FATAL: no turret")
    return
  end
  MELTA.x, MELTA.y = t.position.x, t.position.y
  R().turret = t
  R().pipes = {}

  for _, p in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
    local pipe = surface.create_entity{name = "pipe", position = {MELTA.x + p[1], MELTA.y + p[2]},
                                       force = game.forces.player}
    if pipe then
      R().pipes[#R().pipes + 1] = pipe
    end
  end
  logf("pipes placed: %d/4, connection positions: %s", #R().pipes, conn_set(t))

  ok_log("prototype flags", function()
    local proto = prototypes.entity[TURRET]
    if not proto then
      return "prototype not readable"
    end
    local flags = {}
    for _, flag in pairs(proto.flags or {}) do
      flags[#flags + 1] = tostring(flag)
    end
    return table.concat(flags, ",")
  end)

  local player = game.players and game.players[1]
  if player and player.character then
    player.teleport({MELTA.x + 14.5, MELTA.y + 8.5}, surface)
  end
end

local function on_tick(event)
  local tick = event.tick
  local surface = game.surfaces[1]

  if not R().start then
    R().start = tick
    logf("start tick %d, players: %d", tick, game.players and #game.players or -1)
    if R().turret then
      logf("RELOAD: storage already holds a turret, checking it instead of rebuilding")
      state("reload")
      logf("RELOAD pipes in storage: %d", #(R().pipes or {}))
      logf("RELOAD connection set: %s", conn_set(R().turret))
      R().phase = "reload-done"
    end
    return
  end

  if R().phase == "reload-done" then
    return
  end

  local step = tick - R().start

  if step == 2 then
    build()

  elseif step == 10 then
    state("t10 empty (no fuel)")
    for _, pipe in ipairs(R().pipes or {}) do
      pipe.set_fluid(1, {name = FLUID, amount = 100})
    end
    state("t10 after filling pipes")
    for _, distance in ipairs({4, 5, 6}) do
      surface.create_entity{name = "small-biter", position = {MELTA.x, MELTA.y - distance}, force = game.forces.enemy}
    end
    logf("units spawned in the beam line: %d", count_units(MELTA.x, MELTA.y))

  elseif step == 35 then
    logf("units alive at t35: %d", count_units(MELTA.x, MELTA.y))
    state("t35 after firing")

  elseif step == 45 then
    local t = turret()
    if t then
      local before = conn_set(t)
      local dir_before = t.direction
      ok_log("rotate() (what R does)", function()
        t.rotate()
        return string.format("dir %s -> %s", tostring(dir_before), tostring(t.direction))
      end)
      logf("connection set after rotate identical: %s", tostring(before == conn_set(t)))
    end

  elseif step == 60 then
    -- A real clipboard round trip is not scriptable in 2.1 (LuaPlayer.create_blueprint
    -- is gone and surface.create_entities_from_blueprint_string is simulation-only),
    -- so the paste is reproduced with the engine call a paste ends in: a cloned
    -- entity created through the same raise_built path.
    local t = turret()
    if not t then
      return
    end
    local _, copy = ok_log("clone turret 20 tiles east (paste)", function()
      return t.clone{position = {MELTA.x + 20, MELTA.y}, force = game.forces.player,
                     create_build_effect_smoke = true}
    end)
    if not copy then
      return
    end
    R().copy = copy
    logf("pasted turret: dir=%s fluid=%.1f hp=%.0f status=%s conns=%s",
      tostring(copy.direction), copy.get_fluid_count(), copy.health, tostring(copy.status), conn_set(copy))
    logf("pipes fed to the pasted turret: %d/4", feed(copy, 20))
    for _, distance in ipairs({4, 5, 6}) do
      surface.create_entity{name = "small-biter", position = {MELTA.x + 20, MELTA.y - distance},
                            force = game.forces.enemy}
    end
    logf("units spawned in front of the pasted turret: %d", count_units(MELTA.x + 20, MELTA.y))

  elseif step == 75 then
    local copy = R().copy
    if copy and copy.valid then
      logf("pasted turret after being fed: fluid=%.1f status=%s", copy.get_fluid_count(), tostring(copy.status))
      logf("units alive in front of the pasted turret: %d", count_units(MELTA.x + 20, MELTA.y))
      shot("20-blueprint-paste", {MELTA.x + 16, MELTA.y - 2}, 0.9)
    end

  elseif step == 90 then
    local t = turret()
    if t then
      ok_log("order_deconstruction", function()
        t.order_deconstruction(game.forces.player)
        return "requested"
      end)
      logf("to_be_deconstructed: %s", tostring(t.to_be_deconstructed(game.forces.player)))
      shot("21-deconstruction-marked", MELTA, 1.2)
      ok_log("cancel_deconstruction", function()
        t.cancel_deconstruction(game.forces.player)
        return "cancelled"
      end)
      logf("to_be_deconstructed after cancel: %s", tostring(t.to_be_deconstructed(game.forces.player)))
    end

  elseif step == 100 then
    state("t100 before save")
    ok_log("auto_save", function()
      game.auto_save("regress-after")
      return "requested"
    end)
    logf("REGRESS DONE")
  end
end

script.on_init(function()
  logf("on_init")
end)

script.on_event(defines.events.on_tick, on_tick)
