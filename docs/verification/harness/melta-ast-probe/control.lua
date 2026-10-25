-- Control stage for the melta asteroid-damage probe (never shipped).
--
-- Six identical melta turrets, 40 tiles apart, each with one target 8-11 tiles to
-- its north and a pipe full of melta-fuel:
--   1  small-metallic-asteroid   (100 hp)
--   2  medium-metallic-asteroid  (400 hp)   <- the "standard" platform asteroid
--   3  big-metallic-asteroid     (2000 hp, physical decrease 2000 / 10 %)
--   4  huge-metallic-asteroid    (5000 hp, physical decrease 3000 / 10 %)
--   5  ast-probe-plain           (1e6 hp unit, no resistances)     -> beam dps
--   6  ast-probe-behemoth        (1e6 hp unit, behemoth-biter armour) -> dps through armour
--
-- The scene is built in on_init (a --create run) so it is saved into the map, then
-- a --benchmark run simulates the ticks and the log carries the numbers. Pulses are
-- counted by watching each target's health go *down* on a tick; a kill is captured by
-- on_entity_died, so "shots to destroy" is exact rather than inferred.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"

local Y = 200
local PADS =
{
  {x = 0,   name = "small-metallic-asteroid",  dist = 8},
  {x = 40,  name = "medium-metallic-asteroid", dist = 8},
  {x = 80,  name = "big-metallic-asteroid",    dist = 9},
  {x = 120, name = "huge-metallic-asteroid",   dist = 11},
  {x = 160, name = "ast-probe-plain",          dist = 8},
  {x = 200, name = "ast-probe-behemoth",       dist = 8},
  {x = 240, name = "biter-spawner",            dist = 8},
  {x = 280, name = "rock-huge",                dist = 8}
}

local function P()
  storage.probe = storage.probe or {}
  return storage.probe
end

local function logf(fmt, ...)
  log("[astprobe] " .. string.format(fmt, ...))
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
  surface.request_to_generate_chunks({110, Y}, 10)
  surface.force_generate_chunk_requests()

  flatten(surface, -12, Y - 16, 294, Y + 6)

  -- nothing else may stand in a beam corridor or be a competing target
  for _, e in ipairs(surface.find_entities_filtered{area = {{-20, Y - 24}, {300, Y + 12}}}) do
    if e.valid and e.type ~= "character" then
      e.destroy()
    end
  end

  P().pads = {}
  for index, pad in ipairs(PADS) do
    local record =
    {
      name = pad.name,
      x = pad.x,
      dist = pad.dist,
      pulses = 0,
      first_hit = nil,
      died_at = nil
    }
    P().pads[index] = record

    local turret = surface.create_entity{name = TURRET, position = {pad.x, Y},
                                         force = game.forces.player, raise_built = true}
    if not turret then
      logf("pad %d (%s): TURRET NOT CREATED", index, pad.name)
    else
      record.turret = turret
      for box = 1, 2 do
        pcall(function() turret.set_fluid(box, {name = FLUID, amount = 250}) end)
      end
      logf("pad %d (%s): turret unit=%s fluid=%d", index, pad.name,
        tostring(turret.unit_number), turret.get_fluid_count(FLUID))
    end

    for _, offset in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
      local pipe = surface.create_entity{name = "pipe",
                                         position = {pad.x + offset[1], Y + offset[2]},
                                         force = game.forces.player}
      if pipe then
        pipe.set_fluid(1, {name = FLUID, amount = 100})
      end
    end

    local target
    if prototypes.entity[pad.name] then
      local ok, created = pcall(surface.create_entity, {name = pad.name,
                                                        position = {pad.x, Y - pad.dist},
                                                        force = game.forces.enemy})
      target = ok and created or nil
    end
    if target then
      record.target = target
      record.start_health = target.health
      record.last_health = target.health
      record.start_tick = nil
      logf("pad %d: target %s hp=%.1f resistances=%s", index, target.name, target.health,
        serpent and serpent.line(target.prototype.resistances or {}, {compact = true}) or "?")
    else
      logf("pad %d: TARGET %s NOT CREATED", index, pad.name)
    end
  end

  local turret = P().pads[2].turret
  if turret then
    logf("prototype: range=%s cooldown=%s rotation_speed=%s", tostring(turret.prototype.attack_parameters.range),
      tostring(turret.prototype.attack_parameters.cooldown), tostring(turret.prototype.rotation_speed))
  end
end

script.on_init(function()
  storage.probe = {}
  logf("on_init")
  build()
end)

script.on_configuration_changed(function()
  storage.probe = storage.probe or {}
end)

script.on_event(defines.events.on_entity_died, function(event)
  local entity = event.entity
  if not entity then
    return
  end
  for index, record in ipairs(P().pads or {}) do
    if record.target and record.target.valid and record.target.unit_number == entity.unit_number then
      record.died_at = event.tick
      record.pulses_at_death = record.pulses
      logf("KILL pad %d (%s) tick=%d pulses=%d first_hit=%s", index, record.name, event.tick,
        record.pulses, tostring(record.first_hit))
    end
  end
end)

script.on_nth_tick(1, function(event)
  -- Asteroids drift toward the platform, so a rock placed 9 tiles away walks into the
  -- turret after ~8 s and the beam loses the target. Pin every probe target to its
  -- spawn position each tick so the geometry of the measurement is constant.
  for _, record in ipairs(P().pads or {}) do
    local target = record.target
    if target and target.valid then
      target.teleport({record.x, Y - (record.dist or 8)})
    end
  end
end)

script.on_nth_tick(200, function(event)
  -- keep the fuel topped up: 250 per box + 100 per pipe is only ~9 s of full beam
  for _, record in ipairs(P().pads or {}) do
    local turret = record.turret
    if turret and turret.valid then
      for box = 1, 2 do
        pcall(function() turret.set_fluid(box, {name = FLUID, amount = 250}) end)
      end
      local surface = game.surfaces[1]
      for _, pipe in ipairs(surface.find_entities_filtered{name = "pipe",
            area = {{record.x - 3, Y - 3}, {record.x + 3, Y + 3}}}) do
        pcall(function() pipe.set_fluid(1, {name = FLUID, amount = 100}) end)
      end
    end
  end
end)

script.on_nth_tick(10, function(event)
  local tick = event.tick
  for index, record in ipairs(P().pads or {}) do
    local target = record.target
    local turret = record.turret
    if target and target.valid then
      local health = target.health
      if record.start_tick == nil and health < record.start_health then
        record.start_tick = tick
        record.first_hit = tick
      end
      if health < record.last_health - 0.0001 then
        record.pulses = record.pulses + 1
      end
      record.last_health = health
      logf("t=%-5d pad %d %-24s hp=%-9.2f pulses=%-3d target=%s status=%s fluid=%.0f at=%.1f,%.1f", tick, index, record.name, health,
        record.pulses, turret and turret.valid and tostring(turret.shooting_target and turret.shooting_target.name) or "-",
        turret and turret.valid and tostring(turret.status) or "-",
        turret and turret.valid and turret.get_fluid_count() or -1,
        target.position.x, target.position.y)
    else
      logf("t=%-5d pad %d %-24s GONE died_at=%s pulses=%d target=%s", tick, index, record.name,
        tostring(record.died_at), record.pulses,
        turret and turret.valid and tostring(turret.shooting_target and turret.shooting_target.name) or "-")
    end
  end
  logf("t=%-5d render_objects=%d", tick, #rendering.get_all_objects())
end)
