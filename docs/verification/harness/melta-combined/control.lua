-- Combined in-game verification probe for the melta improvements (never shipped).
--
-- One scene, five regions, so a single GUI run and a single long headless run cover all
-- five workstreams AND their interactions:
--
--   y=100  quality row       normal/uncommon/rare/epic/legendary meltas; the camera
--                            cycles over them so an external watcher can photograph the
--                            inspect panel (Range line) for each quality
--   y=200  pipe joints       four-way plumbing into tanks, one-sided plumbing, and the
--                            straight / L / T / cross / dead-end runs
--   y=260  beam + damage     six meltas cutting dummies (3 on light oil, 3 on melta
--                            fuel); pulse drops, profiler window, fade-out object counts
--   y=320  asteroids         small/medium/big/huge metallic rocks; pulses to kill
--   y=380  reach + rotation  normal melta with a target at 15 and 19 tiles, legendary
--                            with 23 and 27, plus a 180 deg swing and a fast crossing
--
-- Everything is built in on_init because this save comes from `--create`, which runs no
-- ticks: the scene has to exist before the map is written.

local TURRET = "melta-turret"
local FUEL = "melta-fuel"
local OIL = "light-oil"
local DUMMY = "comb-probe-dummy"

local QY, PY, BY, AY, RY = 100, 200, 260, 320, 380
local QX = {0, 12, 24, 36, 48}
local QUALITIES = {"normal", "uncommon", "rare", "epic", "legendary"}

local T_LEG0, T_LEG_STEP = 120, 600
local T_SWING = 400        -- target jumps from 4 north to 4 south
local T_CROSS = 520        -- target crosses at 0.3 tiles/tick, 4 tiles north
local T_KILL = 4800        -- all six beam dummies destroyed -> fade-out check
local T_RESPAWN = 4900
local T_DONE = 4980
local T_PROF0, T_PROF1 = 4400, 4700      -- window A: 6 beams firing
local T_IDLE = 5000                      -- window B: same scene, no beam target
local T_PROF2, T_PROF3 = 5010, 5310
local T_ROCK_SHOTS = {4243, 4288, 4333}  -- fresh rocks so the shots show a rock being cut

local ROCKS =
{
  {x = 0,   name = "small-metallic-asteroid",  dist = 8},
  {x = 40,  name = "medium-metallic-asteroid", dist = 8},
  {x = 80,  name = "big-metallic-asteroid",    dist = 9},
  {x = 120, name = "huge-metallic-asteroid",   dist = 11},
}

local SHOTS =
{
  {3300, "pipes/01-overview",        {8, PY + 7},    0.9},
  {3345, "pipes/02-four-way",        {0, PY + 0.5},  2.6},
  {3390, "pipes/03-join-north",      {0, PY - 1.4},  4.0},
  {3435, "pipes/04-join-east",       {1.4, PY},      4.0},
  {3480, "pipes/05-capped-ports",    {16, PY},       2.6},
  {3525, "pipes/06-shapes",          {0, PY + 14},   1.6},
  {3570, "pipes/07-straight",        {-12, PY + 14}, 3.2},
  {3615, "pipes/08-corner",          {-5.5, PY + 15}, 3.2},
  {3660, "pipes/09-t-junction",      {0, PY + 15},   3.2},
  {3705, "pipes/10-cross",           {5, PY + 14},   3.2},
  {3750, "pipes/11-dead-end",        {10.5, PY + 14}, 3.2},
  {3795, "pipes/12-join-south",      {0, PY + 1.8},  4.0},
  {3840, "pipes/13-join-west",       {-1.5, PY},     4.0},
  {3885, "pipes/14-normal-zoom",     {8, PY + 7},    0.8},
  {3930, "pipes/15-capped-port-north", {16, PY - 1.4}, 4.0},
  {3975, "beam/01-six-firing",       {50, BY + 2},   1.2},
  {4020, "beam/02-close-lightoil",   {0, BY - 5},    3.0},
  {4065, "beam/03-close-meltafuel",  {60, BY - 5},   3.0},
  {4110, "beam/04-six-zoomed",       {50, BY + 2},   1.6},
  {4128, "beam/05-six-wide",         {50, BY + 8},   0.5},
  {4155, "reach/01-normal-15",       {0, RY - 6},    1.2},
  {4200, "reach/02-legendary-23",    {80, RY - 14},  0.9},
  {4245, "asteroids/01-overview",    {60, AY - 4},   0.8},
  {4290, "asteroids/02-small-cut",   {0, AY - 5},    3.0},
  {4335, "asteroids/03-big-cut",     {80, AY - 6},   3.0},
  {4803, "beam/05-fade-3ticks",      {20, BY + 2},   2.0},
  {4815, "beam/06-fade-gone",        {20, BY + 2},   2.0},
}

local atan2 = math.atan2 or function(y, x) return math.atan(y, x) end

local function logf(fmt, ...)
  log("[comb] " .. string.format(fmt, ...))
end

local function tlog(fmt, ...)
  log("[tooltip] " .. string.format(fmt, ...))
end

local function C()
  storage.c = storage.c or {}
  return storage.c
end

local function wrap(d)
  d = d % 1
  if d > 0.5 then d = d - 1 end
  return d
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

local function clear(surface, area)
  local n = 0
  for _, e in ipairs(surface.find_entities_filtered{area = area}) do
    if e.valid and e.type ~= "character" then
      e.destroy()
      n = n + 1
    end
  end
  return n
end

local function turret(surface, x, y, quality, fluid)
  local ok, t = pcall(surface.create_entity, {name = TURRET, position = {x, y},
    force = game.forces.player, quality = quality or "normal", raise_built = true})
  if not ok or not t then
    logf("FAILED melta at %.1f,%.1f quality=%s err=%s", x, y, tostring(quality), tostring(t))
    return nil
  end
  C().turrets = C().turrets or {}
  C().turrets[#C().turrets + 1] = t
  C().fuel = C().fuel or {}
  if fluid then
    C().fuel[t.unit_number] = fluid
    for box = 1, 2 do
      pcall(function() t.set_fluid(box, {name = fluid, amount = 250}) end)
    end
  end
  return t
end

local function pipe_at(surface, x, y, fluid)
  local p = surface.create_entity{name = "pipe", position = {x, y}, force = game.forces.player}
  if p and fluid then
    pcall(function() p.set_fluid(1, {name = fluid, amount = 100}) end)
  end
  return p
end

local function plumbing(surface, x, y, fluid)
  for _, o in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
    pipe_at(surface, x + o[1], y + o[2], fluid)
  end
end

local function dummy(surface, x, y)
  local ok, e = pcall(surface.create_entity, {name = DUMMY, position = {x, y},
    force = game.forces.enemy})
  if not ok or not e then
    logf("FAILED dummy at %.1f,%.1f", x, y)
    return nil
  end
  return e
end

------------------------------------------------------------------ build ------
local function build()
  local surface = game.surfaces[1]
  surface.always_day = true
  pcall(function() surface.peaceful_mode = true end)

  for _, r in ipairs({{0, QY, 4}, {0, PY, 4}, {50, BY, 4}, {60, AY, 5}, {100, RY, 6}}) do
    surface.request_to_generate_chunks({r[1], r[2]}, r[3])
  end
  surface.force_generate_chunk_requests()

  local ok, err = pcall(function() game.forces.enemy.kill_all_units() end)
  logf("kill_all_units -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))

  flatten(surface, -30, QY - 12, 70, QY + 8)
  flatten(surface, -30, PY - 24, 60, PY + 24)
  flatten(surface, -20, BY - 14, 120, BY + 8)
  flatten(surface, -20, AY - 18, 140, AY + 8)
  flatten(surface, -20, RY - 32, 240, RY + 8)

  logf("cleared q=%d p=%d b=%d a=%d r=%d",
    clear(surface, {{-32, QY - 14}, {72, QY + 10}}),
    clear(surface, {{-32, PY - 26}, {62, PY + 26}}),
    clear(surface, {{-22, BY - 16}, {122, BY + 10}}),
    clear(surface, {{-22, AY - 20}, {142, AY + 10}}),
    clear(surface, {{-22, RY - 34}, {242, RY + 10}}))

  ---------------------------------------------------------------- quality -----
  C().quality_row = {}
  for i, q in ipairs(QUALITIES) do
    plumbing(surface, QX[i], QY, FUEL)
    local t = turret(surface, QX[i], QY, q, FUEL)
    if t then
      C().quality_row[i] = {turret = t, quality = q, x = QX[i], y = QY}
      logf("quality row %d: requested=%s actual=%s range=%s", i, q,
        tostring(t.quality and t.quality.name), tostring(t.prototype.attack_parameters.range))
    end
  end

  ---------------------------------------------------------------- pipes -------
  local pa = turret(surface, 0, PY, "normal", FUEL)
  if pa then
    for _, d in ipairs({{0, -1}, {1, 0}, {0, 1}, {-1, 0}}) do
      for step = 2, 5 do
        pipe_at(surface, d[1] * step, PY + d[2] * step, FUEL)
      end
      surface.create_entity{name = "storage-tank",
        position = {d[1] * 6 + d[2], PY + d[2] * 6 - d[1]}, force = game.forces.player}
    end
    local conns = pa.get_fluid_box_pipe_connections(1)
    logf("pipes A: connections=%d fluid=%s", #conns, tostring(pa.get_fluid_count(FUEL)))
  end

  local pb = turret(surface, 16, PY, "normal", FUEL)
  if pb then
    for step = 2, 4 do
      pipe_at(surface, 16 + step, PY, FUEL)
    end
    surface.create_entity{name = "storage-tank", position = {21.5, PY + 1.5},
      force = game.forces.player}
    logf("pipes B: connections=%d fluid=%s", #pb.get_fluid_box_pipe_connections(1),
      tostring(pb.get_fluid_count(FUEL)))
  end

  local sy = PY + 14
  for x = -14, -10 do pipe_at(surface, x, sy, FUEL) end                      -- straight
  pipe_at(surface, -6, sy, FUEL)                                             -- L corner
  pipe_at(surface, -5, sy, FUEL)
  pipe_at(surface, -5, sy + 1, FUEL)
  pipe_at(surface, -5, sy + 2, FUEL)
  for x = -1, 1 do pipe_at(surface, x, sy, FUEL) end                          -- T junction
  pipe_at(surface, 0, sy + 1, FUEL)
  pipe_at(surface, 0, sy + 2, FUEL)
  for x = 4, 6 do pipe_at(surface, x, sy, FUEL) end                           -- cross
  pipe_at(surface, 5, sy - 1, FUEL)
  pipe_at(surface, 5, sy - 2, FUEL)
  pipe_at(surface, 5, sy + 1, FUEL)
  pipe_at(surface, 5, sy + 2, FUEL)
  for x = 9, 11 do pipe_at(surface, x, sy, FUEL) end                          -- dead end

  ---------------------------------------------------------------- beam --------
  C().beam = {}
  local fuels = {OIL, OIL, OIL, FUEL, FUEL, FUEL}
  for i = 1, 6 do
    local x = (i - 1) * 20
    plumbing(surface, x, BY, fuels[i])
    local t = turret(surface, x, BY, "normal", fuels[i])
    local target = dummy(surface, x, BY - 8)
    C().beam[i] = {turret = t, target = target, fuel = fuels[i], x = x,
                   drops = {}, samples = 0, last = target and target.health, first = {}}
    logf("beam %d: fuel=%s turret=%s target=%s hp=%s", i, fuels[i],
      tostring(t ~= nil), tostring(target ~= nil), target and string.format("%.1f", target.health) or "-")
  end

  ---------------------------------------------------------------- rocks ------
  C().ast = {}
  for i, rock in ipairs(ROCKS) do
    plumbing(surface, rock.x, AY, FUEL)
    local t = turret(surface, rock.x, AY, "normal", FUEL)
    local target
    if prototypes.entity[rock.name] then
      local okc, made = pcall(surface.create_entity, {name = rock.name,
        position = {rock.x, AY - rock.dist}, force = game.forces.enemy})
      target = okc and made or nil
    end
    C().ast[i] = {name = rock.name, x = rock.x, dist = rock.dist, turret = t, target = target,
                  pulses = 0, last = target and target.health, start = target and target.health,
                  died = nil}
    logf("rock %d: %s hp=%s turret=%s", i, rock.name,
      target and string.format("%.1f", target.health) or "-", tostring(t ~= nil))
  end

  ---------------------------------------------------------------- reach -------
  C().reach = {}
  local function reach_case(key, x, quality, dist, expect)
    plumbing(surface, x, RY, FUEL)
    local t = turret(surface, x, RY, quality, FUEL)
    local target = dummy(surface, x, RY - dist)
    C().reach[#C().reach + 1] = {key = key, turret = t, target = target, dist = dist,
                                 expect = expect, hit = false, max_target = nil,
                                 start = target and target.health,
                                 last = target and target.health}
    logf("reach %s: quality=%s dist=%d expect=%s turret=%s", key, quality, dist,
      tostring(expect), tostring(t ~= nil))
  end
  reach_case("normal_15", 0, "normal", 15, true)
  reach_case("normal_19", 19, "normal", 19, false)     -- due east, out of range
  reach_case("legendary_23", 80, "legendary", 23, true)
  reach_case("legendary_27", 80 + 27, "legendary", 27, false)

  ---------------------------------------------------------------- rotation ----
  plumbing(surface, 200, RY, FUEL)
  local rt = turret(surface, 200, RY, "normal", FUEL)
  local rd = dummy(surface, 200, RY - 4)
  C().rot = {turret = rt, dummy = rd, swing_done = false, cross_done = false,
             swing_ticks = nil, max_err = 0}
  logf("rotation: turret=%s dummy=%s rotation_speed=%s", tostring(rt ~= nil),
    tostring(rd ~= nil), rt and tostring(rt.prototype.rotation_speed) or "-")

  local p = prototypes.entity[TURRET]
  logf("prototype: range=%s cooldown=%s rotation_speed=%s turn_range=%s",
    tostring(p.attack_parameters.range), tostring(p.attack_parameters.cooldown),
    tostring(p.rotation_speed), tostring(p.attack_parameters.turn_range))
  for _, q in ipairs(QUALITIES) do
    local qp = prototypes.quality and prototypes.quality[q]
    logf("quality %s: range_multiplier=%s", q,
      tostring(qp and qp.range_multiplier))
  end
  logf("scene ready")
end

------------------------------------------------------------------ shots ------
local function shot(path, position, zoom)
  local player = game.players and game.players[1]
  if not player then
    return false
  end
  game.take_screenshot{
    player = player, position = position, resolution = {1920, 1080}, zoom = zoom,
    path = "combined/" .. path .. ".png", show_gui = false, show_entity_info = false,
    hide_fog = true, hide_clouds = true, hide_health_bars = true
  }
  return true
end

------------------------------------------------------------------ hover ------
local function ensure_character(player)
  if player.character then
    return player.character
  end
  pcall(function()
    player.set_controller{type = defines.controllers.god, position = {0, QY},
                          surface = game.surfaces[1]}
  end)
  pcall(function() player.create_character() end)
  if player.character then
    pcall(function()
      player.set_controller{type = defines.controllers.character, character = player.character}
    end)
  end
  return player.character
end

local function hover_leg(index)
  local player = game.players and game.players[1]
  if not player then
    return
  end
  local q = QUALITIES[index]
  local x, y = QX[index], QY
  local camera = {x = x, y = y + 2}
  pcall(function()
    if player.character then
      player.teleport(camera, game.surfaces[1])
      player.zoom = 1.0
    else
      player.set_controller{type = defines.controllers.remote, position = camera,
                            surface = game.surfaces[1], start_zoom = 1.0}
    end
    rendering.draw_circle{surface = game.surfaces[1], color = {r = 1, g = 0.1, b = 0.1},
                          radius = 1.0, width = 2, position = {x, y}, time_to_live = T_LEG_STEP}
    rendering.draw_circle{surface = game.surfaces[1], color = {r = 0.1, g = 1, b = 0.1},
                          radius = 0.2, width = 2, position = camera, time_to_live = T_LEG_STEP}
  end)
  tlog("HOVER_Q_%s leg=%d subject=%.1f,%.1f camera=%.1f,%.1f character=%s",
    q:upper(), index, x, y, camera.x, camera.y, tostring(player.character ~= nil))
end

------------------------------------------------------------------ ticks ------
local function median(t)
  if #t == 0 then
    return -1
  end
  local c = {}
  for i = 1, #t do c[i] = t[i] end
  table.sort(c)
  return c[math.ceil(#c / 2)]
end

local function object_counts()
  local total = #rendering.get_all_objects()
  local ok, list = pcall(rendering.get_all_objects, "lilys-melta")
  local mine = -1
  if ok and type(list) == "table" then
    mine = #list
  end
  return total, mine
end

local function respawn_beam(c)
  for i, b in ipairs(c.beam or {}) do
    if (not b.target) or (not b.target.valid) then
      b.target = dummy(game.surfaces[1], b.x, BY - 8)
      b.last = b.target and b.target.health
      b.drops = {}
      b.first = {}
    end
  end
end

local function spawn_display_rocks(tick)
  local surface = game.surfaces[1]
  local made = 0
  for _, rock in ipairs(ROCKS) do
    local present = #surface.find_entities_filtered{name = rock.name,
      area = {{rock.x - 1, AY - rock.dist - 1}, {rock.x + 1, AY - rock.dist + 1}}} > 0
    if not present then
      local ok, e = pcall(surface.create_entity, {name = rock.name,
        position = {rock.x, AY - rock.dist}, force = game.forces.enemy})
      if ok and e then
        made = made + 1
      end
    end
  end
  logf("t=%-6d display rocks for the screenshots: %d spawned", tick, made)
end

local function summary(tick)
  local c = C()
  local total, mine = object_counts()
  logf("t=%-6d objects total=%d melta=%d", tick, total, mine)
  for i, b in ipairs(c.beam or {}) do
    if b.turret and b.turret.valid then
      local recent = {}
      for k = math.max(1, #b.drops - 49), #b.drops do
        recent[#recent + 1] = b.drops[k]
      end
      logf("t=%-6d beam %d fuel=%-10s status=%s target=%s fluid=%.0f drops=%d median_recent=%.2f",
        tick, i, b.fuel, tostring(b.turret.status),
        tostring(b.turret.shooting_target and b.turret.shooting_target.name or "-"),
        b.turret.get_fluid_count(), #b.drops, median(recent))
    end
  end
  for i, r in ipairs(c.reach or {}) do
    if r.turret and r.turret.valid then
      logf("t=%-6d reach %-14s dist=%d status=%s target=%s hits=%s",
        tick, r.key, r.dist, tostring(r.turret.status),
        tostring(r.turret.shooting_target and r.turret.shooting_target.name or "-"),
        tostring(r.hit))
    end
  end
end

local function refuel(tick)
  local fuels = C().fuel or {}
  for _, t in ipairs(C().turrets or {}) do
    if t.valid then
      local fluid = fuels[t.unit_number]
      if fluid then
        for box = 1, 2 do
          pcall(function() t.set_fluid(box, {name = fluid, amount = 250}) end)
        end
      end
    end
  end
end

script.on_init(function()
  local ok, err = pcall(build)
  logf("build -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
  for _, kind in ipairs({"entity", "item"}) do
    local proto = prototypes[kind] and prototypes[kind][TURRET]
    local description = proto and proto.localised_description
    if description then
      localised_print("##### " .. kind .. " description:")
      localised_print(description)
      localised_print("##### end")
    end
  end
end)

script.on_configuration_changed(function()
  local player = game.players and game.players[1]
  if player then
    ensure_character(player)
  end
end)

script.on_event(defines.events.on_tick, function(event)
  local tick = event.tick
  local c = C()
  storage.ready = storage.ready or (c.beam ~= nil)
  if not storage.ready then
    return
  end

  -- player setup (GUI runs only)
  local player = game.players and game.players[1]
  if player and not storage.setup_done then
    storage.setup_done = true
    ensure_character(player)
  end

  ---------------------------------------------------------- asteroids -------
  for _, r in ipairs(c.ast or {}) do
    if r.target and r.target.valid then
      r.target.teleport({r.x, AY - r.dist})   -- rocks drift toward the platform
      local h = r.target.health
      if r.last and h < r.last - 1e-4 then
        r.pulses = r.pulses + 1
      end
      r.last = h
    end
  end

  ---------------------------------------------------------- beam damage -----
  for i, b in ipairs(c.beam or {}) do
    local tgt = b.target
    if tgt and tgt.valid then
      local h = tgt.health
      if b.last and h < b.last - 1e-4 then
        local d = b.last - h
        if #b.drops < 400 then
          b.drops[#b.drops + 1] = d
        end
        if #b.first < 12 then
          b.first[#b.first + 1] = {tick = tick, drop = d}
          logf("t=%-6d beam %d pulse #%d drop=%.2f", tick, i, #b.first, d)
        end
      end
      b.last = h
    end
  end

  ---------------------------------------------------------- reach ----------
  for _, r in ipairs(c.reach or {}) do
    if r.turret and r.turret.valid then
      local tgt = r.turret.shooting_target
      r.max_target = tgt and tgt.valid and tgt.position.x or r.max_target
      if tgt and r.target and tgt.valid and tgt.unit_number == r.target.unit_number then
        r.engaged = true
      end
    end
    if r.target and r.target.valid then
      local h = r.target.health
      if r.last and h < r.last - 1e-4 then
        if not r.hit then
          logf("t=%-6d reach %s: FIRST DAMAGE at tick %d", tick, r.key, tick)
        end
        r.hit = true
      end
      r.last = h
    end
  end

  ---------------------------------------------------------- rotation -------
  local R = c.rot
  if R and R.turret and R.turret.valid and R.dummy and R.dummy.valid then
    local ok, err = pcall(function()
      if tick == T_SWING then
        -- the head is already locked on a target 4 north; move it 4 south: a 180 deg swing
        R.dummy.teleport({200, RY + 4})
        logf("t=%-6d swing START from orient=%.4f (target now 4 south)", tick,
          R.turret.orientation)
      end
      local dx = R.dummy.position.x - R.turret.position.x
      local dy = R.dummy.position.y - R.turret.position.y
      local want = atan2(dx, -dy) / (2 * math.pi)
      local e = wrap(want - R.turret.orientation)
      if tick >= T_SWING and tick <= T_SWING + 60 then
        logf("t=%-6d swing orient=%.4f want=%.4f err=%.4f", tick,
          R.turret.orientation, want % 1, e)
        if not R.swing_done and tick > T_SWING and math.abs(e) <= 0.006 then
          R.swing_done = true
          R.swing_ticks = tick - T_SWING
          logf("t=%-6d swing ARRIVED after %d ticks (%.2f s)", tick, R.swing_ticks,
            R.swing_ticks / 60)
        end
      end
      if tick == T_CROSS - 30 then
        R.dummy.teleport({188, RY - 4})
        logf("t=%-6d crossing staged at 188,%.0f", tick, RY - 4)
      end
      if tick >= T_CROSS and tick <= T_CROSS + 80 then
        local step = 0.3
        R.dummy.teleport({R.dummy.position.x + step, RY - 4})
        if tick >= T_CROSS + 30 then
          R.max_err = math.max(R.max_err, math.abs(e))
        end
        if tick == T_CROSS + 80 then
          R.cross_done = true
          logf("t=%-6d crossing DONE max aim deviation after catch-up = %.4f turns (%.2f deg)",
            tick, R.max_err, R.max_err * 360)
        end
      end
    end)
    if not ok then
      logf("rotation probe FAILED: %s", tostring(err))
    end
  end

  ---------------------------------------------------------- schedule -------
  for _, s in ipairs(SHOTS) do
    if tick == s[1] then
      if shot(s[2], s[3], s[4]) then
        logf("t=%-6d shot %s", tick, s[2])
      end
    end
  end

  if tick % T_LEG_STEP == T_LEG0 then
    local index = (tick - T_LEG0) / T_LEG_STEP + 1
    if index >= 1 and index <= #QUALITIES then
      hover_leg(index)
    end
  end

  if tick % 200 == 0 then
    refuel(tick)
  end

  if tick == 200 then logf("t=200 asteroids pinned, beam firing"); end

  if tick % 600 == 0 then
    summary(tick)
  end

  if tick == T_PROF0 then
    storage.profiler = helpers.create_profiler()
    logf("t=%-6d profiler START (window %d ticks)", tick, T_PROF1 - T_PROF0)
  elseif tick == T_PROF1 and storage.profiler then
    local profiler = storage.profiler
    storage.profiler = nil
    profiler.stop()
    profiler.divide(T_PROF1 - T_PROF0)
    log({"", "##### PROFILER ms/tick over " .. tostring(T_PROF1 - T_PROF0) .. " ticks: ", profiler})
    logf("t=%-6d profiler STOP", tick)
    summary(tick)
  end

  if tick == T_KILL then
    local before_total, before_melta = object_counts()
    logf("t=%-6d KILL all six beam dummies (objects total=%d melta=%d)", tick, before_total, before_melta)
    for _, b in ipairs(c.beam or {}) do
      if b.target and b.target.valid then
        b.target.destroy()
      end
    end
  end
  if tick == T_KILL + 3 or tick == T_KILL + 15 or tick == T_KILL + 30 then
    local total, mine = object_counts()
    logf("t=%-6d objects after kill total=%d melta=%d", tick, total, mine)
  end

  if tick == T_RESPAWN then
    respawn_beam(c)
    local total, mine = object_counts()
    logf("t=%-6d beam dummies respawned, objects total=%d melta=%d", tick, total, mine)
  end

  for _, rock_tick in ipairs(T_ROCK_SHOTS) do
    if tick == rock_tick then
      spawn_display_rocks(tick)
    end
  end

  -- window B: the same scene with the six beam targets removed, so the profiler can
  -- subtract everything that is not the six firing beams
  if tick == T_IDLE then
    for _, b in ipairs(c.beam or {}) do
      if b.target and b.target.valid then
        b.target.destroy()
      end
    end
    local total, mine = object_counts()
    logf("t=%-6d IDLE window: beam targets removed, objects total=%d melta=%d", tick, total, mine)
  elseif tick == T_PROF2 then
    storage.profiler_b = helpers.create_profiler()
    logf("t=%-6d profiler B START (idle window, %d ticks)", tick, T_PROF3 - T_PROF2)
  elseif tick == T_PROF3 and storage.profiler_b then
    local profiler = storage.profiler_b
    storage.profiler_b = nil
    profiler.stop()
    profiler.divide(T_PROF3 - T_PROF2)
    log({"", "##### PROFILER B idle ms/tick over " .. tostring(T_PROF3 - T_PROF2) .. " ticks: ", profiler})
    logf("t=%-6d profiler B STOP", tick)
    summary(tick)
  elseif tick == T_PROF3 + 20 then
    respawn_beam(c)
    local total, mine = object_counts()
    logf("t=%-6d beam dummies back, firing resumes, objects total=%d melta=%d", tick, total, mine)
  end

  if tick == T_DONE then
    summary(tick)
    local total, mine = object_counts()
    logf("t=%-6d COMBINED PROBE DONE objects total=%d melta=%d", tick, total, mine)
  end
end)

script.on_event(defines.events.on_entity_died, function(event)
  local e = event.entity
  if not e then
    return
  end
  for i, r in ipairs(C().ast or {}) do
    if r.target and r.target.valid and r.target.unit_number == e.unit_number then
      r.died = event.tick
      logf("t=%-6d KILL rock %d (%s) at tick %d pulses=%d start_hp=%.1f",
        event.tick, i, r.name, event.tick, r.pulses, r.start or -1)
    end
  end
end)
