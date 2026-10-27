-- Portal gallery probe v2 (never shipped).
--
-- A believable defensive line on generated Nauvis terrain: concrete pad, four emplacments each
-- fed from its own tank through a pipe, three different fuels so three beam colours, biters
-- coming out of the north. Everything that is not a tree is removed first, so no wrecks,
-- rocks or odd generated structures end up in frame.
--
-- Shots land in <write>/script-output/gallery/. The technology-screen shot is taken by the
-- Python runner (it needs a real keypress), after this script logs TECH READY.

local TURRET, FLUID = "melta-turret", "melta-fuel"
local BITER = "medium-biter"

-- x offsets of the four emplacements, and what each one burns
local LINE = {
  {x = -13.5, fuel = "light-oil",     sheath = "orange"},
  {x = -4.5,  fuel = "petroleum-gas", sheath = "blue"},
  {x = 4.5,   fuel = "melta-fuel",    sheath = "green"},
  {x = 13.5,  fuel = "melta-fuel",    sheath = "green"}
}
local PAD_Y = 0.5

local function logf(fmt, ...) log("[gallery] " .. string.format(fmt, ...)) end
local function S() storage.probe = storage.probe or {} return storage.probe end

-- Corpses and remnants from the fight appear in frame as yellow wreckage; a gallery shot wants
-- the emplacements, the beams and the living swarm, not the debris of the previous one.
local function purge()
  local keep = {}
  for _, turret in ipairs(S().turrets or {}) do
    if turret and turret.valid then keep[turret.unit_number] = true end
  end
  for _, e in ipairs(game.surfaces[1].find_entities_filtered{area = {{-34, -26}, {34, 20}}}) do
    if e.valid and e.unit_number and not keep[e.unit_number]
       and e.type ~= "tree" and e.type ~= "unit" and e.type ~= "character"
       and e.type ~= "pipe" and e.type ~= "storage-tank" then
      logf("purged %s", e.name)
      e.destroy()
    end
  end
end

local function shot(name, position, zoom)
  purge()
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

local function clear_area(s, x1, y1, x2, y2)
  for _, e in ipairs(s.find_entities_filtered{area = {{x1, y1}, {x2, y2}}}) do
    if e.valid and e.type ~= "tree" and e.type ~= "character" then
      e.destroy()
    end
  end
end

local function pad(s, x1, y1, x2, y2, tile)
  local tiles = {}
  for y = y1, y2 do
    for x = x1, x2 do
      tiles[#tiles + 1] = {name = tile, position = {x, y}}
    end
  end
  s.set_tiles(tiles)
end

local function wave(target, count, radius, spread_deg)
  local s = game.surfaces[1]
  local made = 0
  for index = 1, count do
    local fraction = (index - 1) / math.max(1, count - 1)
    local angle = math.rad(-spread_deg * 0.5 + spread_deg * fraction)
    local r = radius + ((index % 3) - 1) * 1.1
    local biter = s.create_entity{name = BITER,
      position = {x = target.x + math.sin(angle) * r, y = target.y - math.cos(angle) * r},
      force = game.forces.enemy}
    if biter then made = made + 1 end
  end
  return made
end

script.on_init(function()
  local s = game.surfaces[1]
  s.always_day = true
  game.speed = 2
  pcall(function()
    s.request_to_generate_chunks({0, 0}, 3)
    s.request_to_generate_chunks({0, -12}, 2)
    s.force_generate_chunk_requests()
  end)

  -- nothing but trees survives in the shooting area: no wrecks, no rocks, no nests
  clear_area(s, -30, -22, 30, 16)
  pad(s, -19, -1, 19, 2, "refined-concrete")

  S().turrets = {}
  S().fed = 0
  for index, entry in ipairs(LINE) do
    local turret = s.create_entity{name = TURRET, position = {entry.x, PAD_Y},
      force = game.forces.player, raise_built = true}
    S().turrets[index] = turret
    if turret then
      turret.insert_fluid{name = entry.fuel, amount = 200}
    end
    -- plumbing that reads as plumbing: a pipe into the housing, a tank behind it
    s.create_entity{name = "pipe", position = {entry.x, PAD_Y + 2.0}}
    local tank = s.create_entity{name = "storage-tank", position = {entry.x, PAD_Y + 6.0},
      force = game.forces.player}
    if tank then
      tank.insert_fluid{name = entry.fuel, amount = 24000}
    end
  end
  logf("built %d emplacements on a pad; fuels: light-oil, petroleum-gas, melta-fuel", #LINE)

  local player = game.players and game.players[1]
  if player and player.character then
    player.teleport({60, 60}, s)
  end
end)

script.on_event(defines.events.on_tick, function(event)
  local tick = event.tick
  if tick == 30 then
    -- does the pipe actually feed the turret? (read the buffer back 60 ticks later)
    S().fuel_before = {}
    for index, turret in ipairs(S().turrets) do
      S().fuel_before[index] = turret and turret.valid and turret.get_fluid_count(LINE[index].fuel) or -1
    end
  elseif tick == 90 then
    for index, turret in ipairs(S().turrets) do
      if turret and turret.valid then
        local now = turret.get_fluid_count(LINE[index].fuel)
        logf("turret %d (%s): %.1f -> %.1f", index, LINE[index].fuel,
          S().fuel_before[index] or -1, now)
      end
    end
  elseif tick == 100 then
    for _, entry in ipairs(LINE) do wave({x = entry.x, y = PAD_Y}, 4, 9, 26) end
  elseif tick == 260 then
    for _, entry in ipairs(LINE) do wave({x = entry.x, y = PAD_Y}, 6, 7.5, 40) end
  elseif tick == 272 then
    shot("01-line", {0.0, PAD_Y - 3.0}, 1.6)
  elseif tick == 280 then
    shot("02-fuels", {-9.0, PAD_Y - 2.0}, 2.6)
  elseif tick == 288 then
    shot("03-emplacement", {4.5, PAD_Y - 0.4}, 4.6)
  elseif tick == 300 then
    game.surfaces[1].always_day = false
    game.surfaces[1].daytime = 0.25
    for _, entry in ipairs(LINE) do wave({x = entry.x, y = PAD_Y}, 7, 6.5, 50) end
  elseif tick == 320 then
    shot("04-night", {0.0, PAD_Y - 2.0}, 2.2)
  elseif tick == 330 then
    game.surfaces[1].always_day = true
    for _, e in ipairs(game.surfaces[1].find_entities_filtered{
        area = {{-7, PAD_Y - 12}, {-2, PAD_Y - 2}}, force = game.forces.enemy}) do
      if e.valid then e.destroy() end
    end
    wave({x = -4.5, y = PAD_Y}, 3, 7, 18)
  elseif tick == 334 then
    shot("05-sweep", {-4.5, PAD_Y - 3.0}, 2.7)
  elseif tick == 344 then
    shot("06-line-from-above", {0.0, PAD_Y - 3.5}, 1.25)
  elseif tick == 356 then
    -- the tech screen: prepare it so the runner can photograph it centred on this turret's tech
    local force = game.forces.player
    for _, name in ipairs({"laser-turret", "advanced-oil-processing"}) do
      local tech = force.technologies[name]
      if tech then tech.researched = true end
    end
    local tech = force.technologies["melta-turret"]
    if tech then
      tech.researched = false
      local ok, err = pcall(function() force.add_research("melta-turret") end)
      logf("add_research(melta-turret): ok=%s err=%s current=%s", tostring(ok), tostring(err),
        tostring(force.current_research and force.current_research.name))
    end
    logf("TECH READY")
  elseif tick == 400 then
    logf("GALLERY DONE")
  end
end)
