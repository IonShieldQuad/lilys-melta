-- Visual probe control stage (never shipped).
--
-- Three things the numbers cannot settle, photographed:
--   A. does the turret stand on its own tile? (drawn against a tiled floor, against a
--      vanilla gun turret, with pipes arriving north and south of it)
--   B. what does the lance look like where it runs out of reach? (close on the far end)
--   C. is the lance behind the gun when the gun points away from the camera, and is the
--      spin-up readable? (same turret at three charges, plus a south-facing one)
--
-- Everything happens in on_tick so one save works for both a --create run and a
-- --load-game run. The whole schedule is under 400 ticks: other cards on this machine
-- close whatever Factorio window is in front of them.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"
local DUMMY = "melta-dummy"

local Y = 200          -- the beam row (turrets face north, dummy 9 tiles north)
local ROW_Y = 220      -- the alignment row
local SOUTH_Y = 240    -- the "gun points at the camera" turret

local function logf(fmt, ...)
  log("[vis] " .. string.format(fmt, ...))
end

local function S()
  storage.probe = storage.probe or {}
  return storage.probe
end

local function surface()
  return game.surfaces[1]
end

local function shot(name, position, zoom)
  local opts =
  {
    position = position,
    resolution = {1920, 1080},
    zoom = zoom,
    path = "visual/" .. name .. ".png",
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
  logf("shot %-28s -> %s%s", name, tostring(ok), ok and "" or (" err=" .. tostring(err)))
end

local function flatten(x1, y1, x2, y2, tile)
  local tiles = {}
  for y = y1, y2 do
    for x = x1, x2 do
      tiles[#tiles + 1] = {name = tile, position = {x, y}}
    end
  end
  surface().set_tiles(tiles)
end

local function build()
  local s = surface()
  s.always_day = true
  game.speed = 4
  pcall(function()
    s.request_to_generate_chunks({0, ROW_Y + 10}, 4)
    s.request_to_generate_chunks({0, Y}, 3)
    s.force_generate_chunk_requests()
  end)
  for _, e in ipairs(s.find_entities_filtered{area = {{-16, Y - 20}, {30, SOUTH_Y + 6}}}) do
    if e.valid and e.type ~= "character" then
      e.destroy()
    end
  end
  -- a tiled floor with visible seams: stone path beside concrete, so the tile boundaries
  -- are where a half-tile error shows up
  flatten(-16, Y - 20, 30, SOUTH_Y + 6, "refined-concrete")
  flatten(-16, Y - 20, 30, Y - 16, "stone-path")
  flatten(-16, ROW_Y - 2, 30, ROW_Y, "stone-path")

  -- A. alignment: two meltas side by side (bases must NOT overlap or gap), each with an
  -- iron pipe arriving north, a vanilla gun turret as the "how vanilla sits on the grid"
  -- reference, and a third melta with a pipe south of it
  S().align = {
    a = s.create_entity{name = TURRET, position = {2.5, ROW_Y + 0.5}, force = game.forces.player, raise_built = true},
    b = s.create_entity{name = TURRET, position = {4.5, ROW_Y + 0.5}, force = game.forces.player, raise_built = true},
    c = s.create_entity{name = TURRET, position = {8.5, ROW_Y + 0.5}, force = game.forces.player, raise_built = true},
    vanilla = s.create_entity{name = "gun-turret", position = {6.5, ROW_Y + 0.5}, force = game.forces.player}
  }
  s.create_entity{name = "pipe", position = {2.5, ROW_Y - 1.5}}
  s.create_entity{name = "pipe", position = {2.5, ROW_Y - 2.5}}
  s.create_entity{name = "pipe", position = {8.5, ROW_Y + 2.5}}
  s.create_entity{name = "pipe", position = {8.5, ROW_Y + 3.5}}

  -- B/C. the beam row: two turrets facing north at their own dummies, one facing south
  S().north = s.create_entity{name = TURRET, position = {2.5, Y + 0.5}, force = game.forces.player, raise_built = true}
  S().dummy = s.create_entity{name = DUMMY, position = {2.5, Y - 8.5}, force = game.forces.enemy}
  S().south = s.create_entity{name = TURRET, position = {8.5, Y + 0.5}, force = game.forces.player, raise_built = true}
  S().south_dummy = s.create_entity{name = DUMMY, position = {8.5, Y + 9.5}, force = game.forces.enemy}
  S().side = s.create_entity{name = TURRET, position = {14.5, Y + 0.5}, force = game.forces.player, raise_built = true}
  S().side_dummy = s.create_entity{name = DUMMY, position = {23.5, Y + 0.5}, force = game.forces.enemy}

  S().firing = {S().north, S().south, S().side}
  local player = game.players and game.players[1]
  if player and player.character then
    player.teleport({0, SOUTH_Y + 8}, s)
  end
  logf("built: north=%s south=%s side=%s", tostring(S().north ~= nil),
    tostring(S().south ~= nil), tostring(S().side ~= nil))
end

local function fuel()
  -- explicit list: LuaEntity values are userdata, so "iterate the storage table and pick
  -- the fluid turrets" silently fuels nothing (that is exactly what the first run did)
  for _, turret in ipairs(S().firing or {}) do
    if turret and turret.valid then
      local ok, amount = pcall(function() return turret.insert_fluid{name = FLUID, amount = 900} end)
      logf("fuel %s -> ok=%s amount=%s count=%.1f", turret.unit_number and tostring(turret.unit_number),
        tostring(ok), tostring(amount), turret.get_fluid_count(FLUID))
    end
  end
end

local function state_dump(label)
  local count = -1
  pcall(function() count = #rendering.get_all_objects("lilys-melta") end)
  for _, turret in ipairs(S().firing or {}) do
    if turret and turret.valid then
      logf("%s unit=%s target=%s fuel=%.1f objects=%d", label, tostring(turret.unit_number),
        tostring(turret.shooting_target ~= nil), turret.get_fluid_count(FLUID), count)
    end
  end
  logf("%s objects total=%d", label, count)
end

script.on_init(function()
  logf("on_init")
end)

script.on_event(defines.events.on_tick, function(event)
  local tick = event.tick
  if tick == 2 then
    build()
  elseif tick == 4 then
    fuel()
  elseif tick == 8 then
    state_dump("t8")
  elseif tick == 12 then
    -- A. alignment, close. 32 px/tile at zoom 1; zoom 3 is ~10 screen px per art px
    shot("a1-align-row", {6.5, ROW_Y - 1.0}, 2.0)
    shot("a2-align-close", {3.5, ROW_Y - 0.5}, 4.0)
    shot("a3-pipe-south", {8.5, ROW_Y + 1.5}, 4.0)
  elseif tick == 30 then
    -- C. spin-up: first second of the engagement, charge is still low
    shot("c1-spinup-low", {2.5, Y - 2.0}, 3.0)
  elseif tick == 90 then
    shot("c2-spinup-mid", {2.5, Y - 2.0}, 3.0)
  elseif tick == 200 then
    state_dump("t200")
    -- B. full charge: the far end, the muzzle, the whole lance
    shot("c3-spinup-full", {2.5, Y - 2.0}, 3.0)
    shot("b1-far-end", {2.5, Y - 8.0}, 3.0)
    shot("b2-whole-lance", {2.5, Y - 4.0}, 1.4)
    shot("b3-muzzle", {2.5, Y - 1.0}, 4.0)
    shot("d1-south-facing", {8.5, Y + 4.0}, 2.4)
    shot("d2-side-facing", {18.5, Y + 0.5}, 2.4)
  elseif tick == 240 then
    local dummy = S().dummy
    if dummy and dummy.valid then
      dummy.destroy()
    end
    logf("north dummy destroyed")
  elseif tick == 244 then
    shot("e1-fading", {2.5, Y - 4.0}, 2.0)
  elseif tick == 258 then
    shot("e2-gone", {2.5, Y - 4.0}, 2.0)
  elseif tick == 262 then
    -- C. cooling down: the gauge has to empty, not switch off
    shot("c4-cooling", {2.5, Y - 2.0}, 3.0)
  elseif tick == 330 then
    local count = -1
    pcall(function() count = #rendering.get_all_objects("lilys-melta") end)
    -- the mouth glows of three idle turrets are all that may be left
    logf("render objects at rest: %d", count)
    logf("VIS PROBE DONE")
  end
end)
