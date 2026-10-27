-- Portal gallery probe (never shipped). Builds a small melta emplacement on generated nauvis
-- terrain, keeps a trickle of biters coming so the turret is white hot, and photographs it.
--
-- Shots land in <write>/script-output/gallery/. Run with setup_gallery.sh + run_gallery.py.

local TURRET, FLUID = "melta-turret", "melta-fuel"
local BITER = "medium-biter"

local SPOTS = {{x = -10.5, y = 0.5}, {x = 0.5, y = 0.5}, {x = 10.5, y = 0.5}}
local CENTRE = SPOTS[2]

local function logf(fmt, ...) log("[gallery] " .. string.format(fmt, ...)) end
local function S() storage.probe = storage.probe or {} return storage.probe end

local function shot(name, position, zoom)
  game.take_screenshot
  {
    position = position,
    resolution = {1920, 1080},
    zoom = zoom,
    path = "gallery/" .. name .. ".png",
    show_gui = false,
    show_entity_info = false,
    hide_fog = true,
    hide_clouds = true,
    hide_health_bars = true
  }
  logf("shot %s", name)
end

-- a deliberate wave: an arc of biters in front of one turret, close enough to be in the beam
local function wave(target, count, radius, spread_deg, health)
  local s = game.surfaces[1]
  local made = 0
  for index = 1, count do
    local fraction = (index - 1) / math.max(1, count - 1)       -- 0..1 across the arc
    local angle = math.rad(-spread_deg * 0.5 + spread_deg * fraction)
    local r = radius + ((index % 3) - 1) * 1.2
    local position = {x = target.x + math.sin(angle) * r, y = target.y - math.cos(angle) * r}
    local biter = s.create_entity{name = BITER, position = position, force = game.forces.enemy}
    if biter then
      made = made + 1
      if health then
        biter.health = health
      end
    end
  end
  logf("wave of %d near %.1f,%.1f", made, target.x, target.y)
end

script.on_init(function()
  local s = game.surfaces[1]
  s.always_day = true
  game.speed = 2
  pcall(function()
    s.request_to_generate_chunks({0, 0}, 4)
    s.force_generate_chunk_requests()
  end)
  for _, e in ipairs(s.find_entities_filtered{area = {{-28, -22}, {28, 22}}, type = "unit"}) do
    if e.valid then e.destroy() end
  end
  for _, e in ipairs(s.find_entities_filtered{area = {{-28, -22}, {28, 22}}, type = "tree"}) do
    if e.valid and math.abs(e.position.y) < 3 then e.destroy() end
  end

  S().turrets = {}
  for index, spot in ipairs(SPOTS) do
    local turret = s.create_entity{name = TURRET, position = spot, force = game.forces.player,
      raise_built = true}
    S().turrets[index] = turret
    if turret then
      turret.insert_fluid{name = FLUID, amount = 900}
    end
  end
  -- fuel arriving from a tank, so the emplacement reads as plumbed rather than magic
  local tank = s.create_entity{name = "storage-tank", position = {CENTRE.x - 3.5, CENTRE.y + 4.5},
    force = game.forces.player}
  if tank then
    tank.insert_fluid{name = FLUID, amount = 25000}
  end
  for offset = 1, 3 do
    s.create_entity{name = "pipe", position = {CENTRE.x - 3.5, CENTRE.y + 4.5 - offset}}
  end
  s.create_entity{name = "pipe-to-ground", position = {CENTRE.x - 3.5, CENTRE.y + 0.5}}
  logf("built %d turrets, tank=%s", #S().turrets, tostring(tank ~= nil))

  local player = game.players and game.players[1]
  if player and player.character then
    player.teleport({0, 26}, s)
  end
end)

script.on_event(defines.events.on_tick, function(event)
  local tick = event.tick
  if tick == 12 then
    wave(SPOTS[1], 3, 9, 24)          -- something to burn while the turret spins up
    wave(SPOTS[2], 3, 9, 24)
    wave(SPOTS[3], 3, 9, 24)
  elseif tick == 200 then
    wave(SPOTS[2], 7, 7.5, 46)
    wave(SPOTS[1], 5, 8, 36)
    wave(SPOTS[3], 5, 8, 36)
  elseif tick == 212 then
    shot("01-hero", {CENTRE.x, CENTRE.y - 3.2}, 2.2)
  elseif tick == 220 then
    shot("02-emplacement", {CENTRE.x, CENTRE.y - 0.8}, 5.0)
  elseif tick == 228 then
    shot("03-battle-line", {CENTRE.x, CENTRE.y - 4.0}, 1.55)
  elseif tick == 240 then
    game.surfaces[1].always_day = false
    game.surfaces[1].daytime = 0.25
    wave(SPOTS[2], 9, 7.0, 60)
  elseif tick == 258 then
    shot("04-night", {CENTRE.x, CENTRE.y - 3.0}, 2.6)
  elseif tick == 268 then
    game.surfaces[1].always_day = true
    -- clear what is in front of the middle turret so the head has to swing to the flanks:
    -- the moment the lance is crossing the gap is the sweep this weapon is about
    for _, e in ipairs(game.surfaces[1].find_entities_filtered{area = {{CENTRE.x - 3, CENTRE.y - 11},
                                                                     {CENTRE.x + 3, CENTRE.y - 2}},
                                                               force = game.forces.enemy}) do
      if e.valid then e.destroy() end
    end
    wave(SPOTS[2], 3, 7, 20)
  elseif tick == 272 then
    shot("05-sweep", {CENTRE.x, CENTRE.y - 3.0}, 2.6)
  elseif tick == 300 then
    shot("06-wide", {CENTRE.x, CENTRE.y - 6.0}, 1.15)
    logf("GALLERY DONE")
  end
end)
