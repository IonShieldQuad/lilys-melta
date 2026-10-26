-- Pipe-connection probe (never shipped).
--
-- Answers one question with the engine's own data instead of a picture: with the
-- turret's fluid_box.pipe_connections at C.pipe_reach, which pipes does the engine
-- actually link it to, and does fluid move?
--
--   * turret.get_fluid_box_neighbours(1) is the engine's connection graph -- the
--     authoritative answer to "is the pipe connected", no fluid simulation needed;
--   * a pipe two tiles out is filled, then ticks run (--benchmark) and the turret's
--     own buffer is read: that is "fluid transferring".
--
-- The scene is built in on_init (a --create run executes no ticks, so a tick-2
-- scene would not exist in the save), after the chunks are force-generated.
--
-- Log lines are prefixed "[conn]" and parsed by run_connprobe.sh.

local TURRET = "melta-turret"
local X, Y = 0, 200
local FLUID = "melta-fuel"
local SIDE = {[1] = "north", [2] = "east", [3] = "south", [4] = "west"}

local function logf(fmt, ...)
  log("[conn] " .. string.format(fmt, ...))
end

-- shallow dump: prototype connection entries are LuaStructs, so tostring() prints
-- an address, and a wrong field name reads as nil with no error
local function dump(t)
  if type(t) ~= "table" then
    return tostring(t)
  end
  local parts = {}
  for k, v in pairs(t) do
    if type(v) == "table" then
      parts[#parts + 1] = tostring(k) .. "={table}"
    elseif type(v) ~= "function" then
      parts[#parts + 1] = tostring(k) .. "=" .. tostring(v)
    end
  end
  table.sort(parts)
  return "{" .. table.concat(parts, " ") .. "}"
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

local function build()
  local surface = game.surfaces[1]
  surface.always_day = true
  surface.request_to_generate_chunks({X, Y}, 4)
  surface.force_generate_chunk_requests()
  flatten(surface, X - 12, Y - 6, X + 12, Y + 6)

  local turret = surface.create_entity{name = TURRET, position = {X, Y},
                                       force = game.forces.player,
                                       raise_built = true}
  if not turret then
    logf("FATAL: could not create %s", TURRET)
    return
  end
  storage.turret = turret
  logf("turret at %.3f,%.3f", turret.position.x, turret.position.y)

  -- the prototype, as the engine resolved it (not as the source file spells it)
  local ok, err = pcall(function()
    local proto = prototypes.entity[TURRET]
    logf("prototype collision_box=%s", dump(proto.collision_box))
    local boxes = proto.fluidbox_prototypes or {}
    logf("fluidbox_prototypes: %d", #boxes)
    for i, box in ipairs(boxes) do
      local conns = box.pipe_connections or {}
      logf("box %d: %d connection(s) production_type=%s", i, #conns,
           tostring(box.production_type))
      for j, c in ipairs(conns) do
        logf("  connection %d raw=%s", j, dump(c))
        local poss = c.positions or {}
        logf("  connection %d direction=%s flow=%s positions=%d", j,
             tostring(c.direction), tostring(c.flow_direction), #poss)
        for k, p in ipairs(poss) do
          local x = p.x or (p[1]) or "?"
          local y = p.y or (p[2]) or "?"
          logf("    position %d = {%.4f, %.4f}", k, x, y)
        end
      end
    end
    logf("turret.fluids_count=%s", tostring(turret.fluids_count))
  end)
  if not ok then
    logf("prototype read failed: %s", tostring(err))
  end

  -- one pipe per side, two tiles out (the nearest a 1-tile pipe can sit), then two
  -- more along the east run so a multi-pipe network is in play
  storage.pipes = {}
  local dirs = {{0, -1}, {1, 0}, {0, 1}, {-1, 0}}
  for i, d in ipairs(dirs) do
    local p = surface.create_entity{name = "pipe",
                                    position = {turret.position.x + d[1] * 2,
                                                turret.position.y + d[2] * 2},
                                    force = game.forces.player}
    if p then
      storage.pipes[#storage.pipes + 1] = p
      logf("pipe %s: at %.3f,%.3f  offset {%.3f,%.3f}", SIDE[i],
           p.position.x, p.position.y,
           p.position.x - turret.position.x, p.position.y - turret.position.y)
      if SIDE[i] == "north" then
        storage.north = p
      end
    else
      logf("pipe %s FAILED to place", SIDE[i])
    end
  end
  for step = 3, 4 do
    local p = surface.create_entity{name = "pipe",
                                    position = {turret.position.x + step,
                                                turret.position.y},
                                    force = game.forces.player}
    logf("east run pipe at offset %.1f: %s", step, p and "placed" or "FAILED")
  end

  -- fill the north pipe so flow can be observed (a neighbour needs fluid in it)
  local north = storage.north
  if north and north.valid then
    north.insert_fluid{name = FLUID, amount = 100}
    logf("filled north pipe with %s, pipe holds %.1f", FLUID,
         north.get_fluid_count(FLUID))
  end

  -- the engine's connection graph, read straight out of the fluid box
  for i = 1, turret.fluids_count do
    local n = turret.get_fluid_box_neighbours(i) or {}
    local names = {}
    for _, e in pairs(n) do
      if type(e) == "table" then
        names[#names + 1] = dump(e)
      else
        names[#names + 1] = tostring(e)
      end
    end
    logf("fluid box %d: %d neighbour(s): %s", i, #names,
         table.concat(names, "  "))
  end
end

script.on_init(function()
  local ok, err = pcall(build)
  if not ok then
    logf("FATAL: %s", tostring(err))
  end
end)

-- ---------------------------------------------------------------- gui pass ---
-- The F4 debug overlays (tile grid, collision box) are not scriptable, so the same
-- information is drawn explicitly with rendering.* and photographed with
-- game.take_screenshot. Only a GUI run has a player; a headless run skips this.
local SHOTS = {
  {tick = 90,  zoom = 1.4, path = "conn/01-four-way.png", note = "overview"},
  {tick = 110, zoom = 3.0, path = "conn/02-north-join.png", at = {0, -2}},
  {tick = 130, zoom = 3.0, path = "conn/03-south-join.png", at = {0, 2}},
  {tick = 150, zoom = 3.0, path = "conn/04-east-join.png", at = {2, 0}},
  {tick = 170, zoom = 3.0, path = "conn/05-west-join.png", at = {-2, 0}}
}

local function draw_overlay(surface, turret)
  local t = turret.position
  storage.gfx = {}
  local span = 6
  for i = -span, span do
    local c = (i == 0) and {1, 1, 1, 0.75} or {1, 1, 1, 0.16}
    storage.gfx[#storage.gfx + 1] = rendering.draw_line{
      surface = surface, color = c, width = 1,
      from = {t.x + i, t.y - span}, to = {t.x + i, t.y + span},
      render_layer = "selection-box", draw_on_ground = true}
    storage.gfx[#storage.gfx + 1] = rendering.draw_line{
      surface = surface, color = c, width = 1,
      from = {t.x - span, t.y + i}, to = {t.x + span, t.y + i},
      render_layer = "selection-box", draw_on_ground = true}
  end
  -- the collision box (what keeps the pipe at 2.0 tiles) and the pipe reach
  storage.gfx[#storage.gfx + 1] = rendering.draw_rectangle{
    surface = surface, color = {0.25, 1, 0.45, 0.85}, width = 2, filled = false,
    left_top = {t.x - 1.2, t.y - 1.2}, right_bottom = {t.x + 1.2, t.y + 1.2},
    render_layer = "selection-box", draw_on_ground = true}
  storage.gfx[#storage.gfx + 1] = rendering.draw_circle{
    surface = surface, color = {1, 0.55, 0.15, 0.85}, width = 2, filled = false,
    radius = 2.0, target = t,
    render_layer = "selection-box", draw_on_ground = true}
  logf("overlay drawn: tile grid, collision box (1.2), pipe distance (2.0)")
end

local function gui_tick()
  local turret = storage.turret
  local player = game.players[1]
  if not turret or not turret.valid or not player then
    return
  end
  if game.tick == 60 then
    local ok, err = pcall(draw_overlay, turret.surface, turret)
    if not ok then
      logf("overlay failed: %s", tostring(err))
    end
  end
  for _, s in ipairs(SHOTS) do
    if game.tick == s.tick then
      local at = s.at and {turret.position.x + s.at[1], turret.position.y + s.at[2]}
        or {turret.position.x, turret.position.y}
      game.take_screenshot{player = player, position = at,
                           resolution = {1920, 1080}, zoom = s.zoom,
                           path = s.path, show_gui = false, hide_fog = true,
                           hide_health_bars = true}
      logf("shot %s at tick %d zoom %.1f (%s)", s.path, game.tick, s.zoom, s.note)
    end
  end
  if game.tick == 260 then
    -- take_screenshot is async: keep the game alive a moment, then report
    logf("MELTA CONNGUI DONE")
  end
end

script.on_event(defines.events.on_tick, function()
  local ok, err = pcall(gui_tick)
  if not ok then
    logf("gui tick failed: %s", tostring(err))
  end
end)

script.on_nth_tick(60, function()
  local turret = storage.turret
  if not turret or not turret.valid then
    return
  end
  local n = {}
  for i = 1, turret.fluids_count do
    n[i] = #(turret.get_fluid_box_neighbours(i) or {})
  end
  logf("tick %d: turret buffer %s = %.1f   box neighbours %s", game.tick, FLUID,
       turret.get_fluid_count(FLUID),
       table.concat({tostring(n[1]), tostring(n[2])}, "/"))
end)
