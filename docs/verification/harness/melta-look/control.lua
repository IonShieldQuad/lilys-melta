-- Look-probe for the melta turret's art: one clean floor, four melta turrets with
-- their heads aimed at four different bearings, and the three vanilla defensive
-- turrets beside them for a palette/legibility comparison at normal zoom.
--
-- Everything is built in on_init because this save comes from `--create`, which runs
-- no ticks; the screenshots are then requested from a GUI `--load-game` run, which is
-- the only place Factorio builds the sprite atlas.

local TURRET = "melta-turret"
local Y = 0
local X0 = -12

-- Layout: four melta turrets 4 tiles apart (a 1.2-tile collision box, so they never
-- overlap and each silhouette stays readable), then the three vanilla turrets further
-- along the same row. The 2-tile spacing this probe started with made the four meltas
-- overlap into one "quad-module" mass in the screenshots, which is a composition
-- artefact, not the art.
local MELTA_X0 = X0 + 5
local MELTA_STEP = 4
local VANILLA_X0 = MELTA_X0 + 3 * MELTA_STEP + 4     -- X0 + 21

local SHOTS = {
  -- name,                position,                     zoom
  {"look-wide",           {X0 + 15.5, Y + 1.5},         0.65},
  {"look-pairs",          {VANILLA_X0 - 2, Y + 0.5},    1.0},
  {"look-melta",          {MELTA_X0 + MELTA_STEP, Y + 0.5}, 1.6},
  {"look-vanilla",        {VANILLA_X0 + 2.5, Y + 0.5},  1.6},
  {"look-melta-close",    {MELTA_X0 + MELTA_STEP, Y + 0.5}, 2.6},
}

local M = {}

local function logf(fmt, ...)
  log("[look] " .. string.format(fmt, ...))
end

local function floor(surface, x0, y0, x1, y1)
  local tiles = {}
  for x = x0, x1 do
    for y = y0, y1 do
      tiles[#tiles + 1] = {name = "stone-path", position = {x, y}}
    end
  end
  surface.set_tiles(tiles, true)
end

local function dummy(surface, x, y)
  return surface.create_entity{name = "look-dummy", position = {x, y},
                               force = game.forces.enemy, raise_built = true}
end

-- aim: the dummy sits 5 tiles away on this bearing; the turret turns to face it and
-- (with an empty fluid box) never fires, so no beam art covers the sprite
local BEARINGS = {
  {0, -5},   -- north
  {5, 0},    -- east
  {0, 5},    -- south
  {-5, 0},   -- west
}

local function build()
  local surface = game.surfaces[1]
  surface.request_to_generate_chunks({X0 + 9, Y}, 4)
  surface.force_generate_chunk_requests()
  floor(surface, X0 - 4, Y - 4, X0 + 32, Y + 8)

  local meltas = {}
  for i, bearing in ipairs(BEARINGS) do
    local x = MELTA_X0 + (i - 1) * MELTA_STEP
    local turret = surface.create_entity{name = TURRET, position = {x, Y},
                                         force = game.forces.player,
                                         raise_built = true}
    if not turret then
      logf("FAILED to create turret %d", i)
    else
      meltas[#meltas + 1] = turret
      -- No fuel on purpose. A turret with fluid and a target 5 tiles away fires the
      -- melta beam, and the beam is a solid green-white sheet that covers the very
      -- art this probe exists to photograph. Without fluid it still rotates to face
      -- the enemy (turret aiming does not need ammo/fluid), so the four bearings are
      -- set and nothing is drawn over the sprite.
      dummy(surface, x + bearing[1], Y + bearing[2])
    end
  end

  local vanilla = {
    {"gun-turret", VANILLA_X0},
    {"laser-turret", VANILLA_X0 + 2.5},
    {"flamethrower-turret", VANILLA_X0 + 5},
  }
  for _, v in ipairs(vanilla) do
    local e = surface.create_entity{name = v[1], position = {v[2], Y},
                                    force = game.forces.player, raise_built = true}
    logf("vanilla %s: %s", v[1], tostring(e ~= nil))
  end
  for _, v in ipairs(vanilla) do
    dummy(surface, v[2], Y - 6)
  end

  M.surface = surface
  logf("scene ready: %d meltas, 3 vanilla turrets", #meltas)
end

local function shot(spec)
  local player = game.players and game.players[1]
  if not player then
    logf("no player: cannot screenshot")
    return false
  end
  game.take_screenshot{
    player = player, position = spec[2], resolution = {1600, 900}, zoom = spec[3],
    path = "look/" .. spec[1] .. ".png", show_gui = false, show_entity_info = false,
    hide_fog = true, hide_clouds = true, hide_health_bars = true
  }
  logf("shot %s zoom %.2f", spec[1], spec[3])
  return true
end

script.on_init(function()
  build()
end)

script.on_configuration_changed(function()
  if not M.surface then
    build()
  end
end)

script.on_nth_tick(20, function(event)
  local tick = event.tick
  -- One screenshot every 60 ticks (1 s): on_nth_tick(20) only fires on multiples of
  -- 20, so the old (tick - 40) % 30 == 0 condition matched ticks 40, 100, 160 only
  -- and silently skipped shots 2 and 4 (look-pairs, look-vanilla). Index from the
  -- same arithmetic, but on a stride the event can actually land on.
  if tick < 40 or (tick - 40) % 60 ~= 0 then
    return
  end
  local index = (tick - 40) / 60 + 1
  if index >= 1 and index <= #SHOTS then
    shot(SHOTS[index])
  elseif index == #SHOTS + 1 then
    log("MELTA LOOK DONE")
  end
end)
