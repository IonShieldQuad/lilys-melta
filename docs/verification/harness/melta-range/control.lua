-- Range / quality / rotation probe for Lily's melta turret (never shipped).
--
-- Four independent scenes, 70 tiles apart. The spacing is deliberate: a turret's
-- `call_for_help_radius` (40 on the melta) lets a shooting neighbour hand its target
-- to everything inside that radius, which makes an "out of range" scene lie about
-- what the engine can see. 70 > 40, so every scene is on its own.
--
--   A  normal melta at (0, 200)      dummies at 15 and 19 tiles north
--      reach 16 -> the 15 one is engaged, the 19 one is not (19 minus a 2-tile body
--      radius is still 17, past 16)
--   B  legendary melta at (70, 200)  dummies at 19 and 27 tiles north
--      reach 24 (16 x the engine's legendary range_multiplier 1.5) -> 19 is engaged
--      (the engine's own base search stops at 16, so this is quality's doing), 27 is not
--   C  normal melta at (140, 200)    one dummy 10 tiles north, teleported 10 tiles
--      south at a known tick: a 180 degree swing logged every tick
--   D  rare melta at (210, 200)      dummy 12 tiles north, and the turret is MINED at
--      a known tick while it is burning the dummy -- exercises the unregister path
--      (no stray state, no null reference on the ticks after)
--
-- Distances are centre-to-centre: the entities snap to the tile grid, so the target
-- is placed at {x, Y - distance} on a .5 line, which lands the pair exactly `distance`
-- apart. Everything logs with the "[range]" prefix:
--   [range] status ...             periodic health / fluid / orientation snapshot
--   [range] swing tick=N ori=...   one line per tick across the 180 degree swing
--   [range] mine ...               the mine-out test, and the state right after it

local TURRET = "melta-turret"
local FLUID = "melta-fuel"
local DUMMY = "melta-dummy"
local Y = 200.5

local SWING_AT = 130      -- tick the rotation dummy jumps to the far bearing
local SWING_UNTIL = 260   -- long enough for the OLD 0.006 turns/tick head to finish
                          -- (about 84 ticks for a half turn), so before/after runs
                          -- are directly comparable
local MINE_AT = 200       -- tick the scene-D turret is mined out from under itself

local function logf(fmt, ...)
  log("[range] " .. string.format(fmt, ...))
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
  for _, entity in ipairs(surface.find_entities_filtered{area = area}) do
    if entity.valid and entity.type ~= "character" then
      entity.destroy()
    end
  end
end

local function dummy_at(surface, x, distance)
  return surface.create_entity
  {
    name = DUMMY,
    position = {x, Y - distance},
    force = "enemy",
    raise_built = true
  }
end

local function melta(surface, x, quality)
  -- a quality the install does not have (quality mod off, or the test quality when it
  -- was not defined) falls back to normal instead of failing the whole scene
  if not (prototypes.quality and prototypes.quality[quality]) then
    quality = "normal"
  end
  local turret = surface.create_entity
  {
    name = TURRET,
    position = {x, Y},
    force = "player",
    quality = quality,
    raise_built = true
  }
  if turret then
    turret.insert_fluid{name = FLUID, amount = 200}
  end
  return turret
end

local function P()
  storage.probe = storage.probe or {}
  return storage.probe
end

local SCENES = {"a", "b", "rot", "mine", "clamp"}

local function status(tag)
  local p = P()
  for _, key in ipairs(SCENES) do
    local scene = p[key]
    if scene and scene.turret and scene.turret.valid then
      local turret = scene.turret
      local target = turret.shooting_target
      logf("status %s t=%s quality=%s range_multiplier=%s fluid=%d ori=%.4f target=%s",
        tag, tostring(turret.unit_number),
        tostring(turret.quality and turret.quality.name or "nil"),
        tostring(turret.quality and turret.quality.range_multiplier),
        turret.get_fluid_count(FLUID), turret.orientation or -1,
        target and target.valid and target.name or "-")
      for _, d in ipairs(scene.dummies or {}) do
        if d and d.valid then
          logf("status %s dummy_at=(%.1f,%.1f) health=%.2f distance=%.2f",
            tag, d.position.x, d.position.y, d.health,
            math.sqrt((d.position.x - turret.position.x) ^ 2 + (d.position.y - turret.position.y) ^ 2))
        end
      end
    elseif scene and scene.turret then
      logf("status %s turret gone (valid=%s)", tag, tostring(scene.turret.valid))
    end
  end
end

local function build()
  local surface = game.surfaces[1]
  clear_area(surface, {{-30, Y - 40}, {330, Y + 40}})
  flatten(surface, -30, Y - 40, 330, Y + 40)

  local p = P()
  p.a    = {turret = melta(surface, 0, "normal"),     dummies = {dummy_at(surface, 0, 15), dummy_at(surface, 0, 19)}}
  p.b    = {turret = melta(surface, 70, "legendary"), dummies = {dummy_at(surface, 70, 19), dummy_at(surface, 70, 23), dummy_at(surface, 70, 27)}}
  p.rot  = {turret = melta(surface, 140, "normal"),   dummies = {dummy_at(surface, 140, 10)}}
  p.mine = {turret = melta(surface, 210, "rare"),     dummies = {dummy_at(surface, 210, 12)}}
  -- clamp: a quality whose multiplier would give 48 tiles; the mod must stop at 24,
  -- so a body at 30 stays untouched even though the engine would happily target it
  p.clamp = {turret = melta(surface, 280, "melta-overclocked"), dummies = {dummy_at(surface, 280, 30)}}

  logf("built a=%s b=%s rot=%s mine=%s clamp=%s",
    tostring(p.a.turret and p.a.turret.unit_number),
    tostring(p.b.turret and p.b.turret.unit_number),
    tostring(p.rot.turret and p.rot.turret.unit_number),
    tostring(p.mine.turret and p.mine.turret.unit_number),
    tostring(p.clamp.turret and p.clamp.turret.unit_number))
  status("built")
end

script.on_init(function()
  storage.probe = {}
end)

script.on_configuration_changed(function()
  storage.probe = storage.probe or {}
end)

script.on_nth_tick(2, function(event)
  if event.tick == 2 then
    build()
  end
end)

-- keep the buffers topped up: the engine drinks 2.5 units a shot and the script
-- adds its own surcharge once the beam is hot
script.on_nth_tick(30, function()
  local p = P()
  for _, key in ipairs(SCENES) do
    local scene = p[key]
    if scene and scene.turret and scene.turret.valid then
      scene.turret.insert_fluid{name = FLUID, amount = 200}
    end
  end
end)

script.on_nth_tick(60, function(event)
  status("t" .. tostring(event.tick))
end)

script.on_nth_tick(1, function(event)
  local p = P()
  if not p.rot then
    return
  end

  -- the 180 degree swing: north -> south, logged every tick
  if event.tick == SWING_AT then
    local d = p.rot.dummies[1]
    if d and d.valid then
      d.teleport({p.rot.turret.position.x, Y + 10})
      logf("swing start tick=%d ori=%.4f", event.tick, p.rot.turret.orientation or -1)
    end
  end
  if event.tick >= SWING_AT and event.tick <= SWING_UNTIL then
    local turret = p.rot.turret
    if turret and turret.valid then
      local target = turret.shooting_target
      logf("swing tick=%d ori=%.5f target=%s",
        event.tick, turret.orientation or -1,
        target and target.valid and "yes" or "-")
    end
  end

  -- mine a firing turret out from under the script
  if event.tick == MINE_AT then
    local turret = p.mine.turret
    if turret and turret.valid then
      logf("mine tick=%d unit=%s fluid=%d", event.tick, tostring(turret.unit_number),
        turret.get_fluid_count(FLUID))
      -- `force` here is the mine-anyway boolean, not a force: items go to the ground
      -- because no inventory is given, and script_raised_destroy is what the mod's
      -- unregister path listens to
      turret.mine{force = true, raise_destroyed = true}
      logf("mine tick=%d mined; valid_now=%s", event.tick, tostring(turret.valid))
    end
  end
  if event.tick >= MINE_AT and event.tick <= MINE_AT + 3 then
    local turret = p.mine.turret
    logf("mine tick=%d after: valid=%s", event.tick, tostring(turret and turret.valid))
  end
end)
