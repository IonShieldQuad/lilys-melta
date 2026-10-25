-- Tooltip probe (never shipped). One melta, one vanilla flamethrower turret and one
-- vanilla gun turret on a concrete pad. The camera is moved from subject to subject
-- on a cycle and a marker is logged for each leg; an external watcher (hover_shot.py)
-- sees the marker, parks the OS cursor on the subject and grabs the screen -- the
-- only way to photograph a tooltip, since the game has no API that renders one into
-- a screenshot.
--
-- Build happens in on_init because this save comes from `--create` (no ticks run
-- there). Chunk generation is forced by hand and fluid is set directly, since no
-- ticks run for pipes to flow.

local TURRET = "melta-turret"
local FLUID = "melta-fuel"
local PAD = {x = 0, y = 100}

-- key and subject position; the camera parks two tiles south of the subject, so
-- the subject sits above the screen centre and the player's own character is not
-- under the cursor
local SUBJECTS = {
  {"MELTA", {x = PAD.x, y = PAD.y}},
  {"FLAMER", {x = PAD.x + 6, y = PAD.y}},
  {"GUN", {x = PAD.x + 10, y = PAD.y}}
}

local function logf(fmt, ...)
  log("[tooltip] " .. string.format(fmt, ...))
end

local function build()
  local surface = game.surfaces[1]
  local ok, err = pcall(function()
    surface.request_to_generate_chunks(PAD, 4)
    surface.force_generate_chunk_requests()
  end)
  logf("chunk generation -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))

  local tiles = {}
  for y = PAD.y - 8, PAD.y + 8 do
    for x = PAD.x - 6, PAD.x + 18 do
      tiles[#tiles + 1] = {name = "refined-concrete", position = {x, y}}
    end
  end
  ok, err = pcall(function() surface.set_tiles(tiles) end)
  logf("concrete -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))

  local melta = surface.create_entity{name = TURRET, position = PAD, force = game.forces.player,
                                      raise_built = true}
  logf("melta -> %s", melta and "ok" or "FAILED")
  if melta then
    for _, p in ipairs({{0, -2}, {2, 0}, {0, 2}, {-2, 0}}) do
      local pipe = surface.create_entity{name = "pipe",
        position = {PAD.x + p[1], PAD.y + p[2]}, force = game.forces.player}
      if pipe then
        pipe.set_fluid(1, {name = FLUID, amount = 100})
      end
    end
    logf("melta fluid: %d", melta.get_fluid_count())
  end

  local flamer = surface.create_entity{name = "flamethrower-turret",
    position = {PAD.x + 6, PAD.y}, force = game.forces.player}
  if flamer then
    flamer.set_fluid(1, {name = "light-oil", amount = 100})
    logf("flamer -> ok, fluid %d", flamer.get_fluid_count())
  else
    logf("flamer -> FAILED")
  end

  local gun = surface.create_entity{name = "gun-turret", position = {PAD.x + 10, PAD.y},
                                    force = game.forces.player}
  if gun then
    local inv = gun.get_inventory(defines.inventory.turret_ammo)
    if inv then
      inv.insert{name = "firearm-magazine", count = 10}
    end
    logf("gun turret -> ok, ammo %d", inv and #inv or -1)
  else
    logf("gun turret -> FAILED")
  end

  storage.melta = melta
end

script.on_init(function()
  logf("on_init")
  build()
  -- resolve the generated tooltip text the way the game would render it: this is the
  -- only offline way to see the final string (params substituted, fluid names looked
  -- up) without hovering the entity by hand
  for _, kind in ipairs({"entity", "item"}) do
    local prototype = prototypes[kind] and prototypes[kind]["melta-turret"]
    local description = prototype and prototype.localised_description
    if description then
      localised_print("##### " .. kind .. " description:")
      localised_print(description)
      localised_print("##### end")
    else
      logf("%s has no localised_description", kind)
    end
  end
end)

-- A save produced by `--create` has a player but no character, and that player sits
-- on the *remote* controller, which refuses `create_character` ("Can't set character
-- for non player with non god controller"). Switch to the god controller first, then
-- attach a character so the camera follows the body like a normal player's.
local function ensure_character(player, position)
  if player.character then
    return player.character
  end
  local ok, err = pcall(function()
    player.set_controller{type = defines.controllers.god, position = position, surface = game.surfaces[1]}
  end)
  logf("set_controller(god) -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
  ok, err = pcall(function() player.create_character() end)
  logf("create_character -> %s%s (character=%s)", tostring(ok), ok and "" or (" err=" .. tostring(err)),
    tostring(player.character ~= nil))
  if player.character then
    -- the god controller keeps its own camera at the god position and ignores the
    -- body; only the character controller follows a teleported character
    ok, err = pcall(function()
      player.set_controller{type = defines.controllers.character, character = player.character}
    end)
    logf("set_controller(character) -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
  end
  if not player.character then
    -- last resort: the remote controller can still be pointed at a position, which
    -- is all the tooltip probe needs (a camera, not a body)
    ok, err = pcall(function()
      player.set_controller{type = defines.controllers.remote, position = position,
                            surface = game.surfaces[1], start_zoom = 1.0}
    end)
    logf("set_controller(remote) -> %s%s", tostring(ok), ok and "" or (" err=" .. tostring(err)))
  end
  return player.character
end


script.on_configuration_changed(function()
  local player = game.players and game.players[1]
  if player then
    ensure_character(player)
  end
end)

-- A leg runs every LEG_TICKS; the first starts at tick 60 so the map has settled.
-- The cycle repeats, so the watcher can miss a marker and still catch the subject
-- on the next lap.
local LEG_TICKS = 600
local first_leg = 60
local legs = 0

script.on_event(defines.events.on_tick, function(event)
  if (event.tick % 100) == 0 then
    logf("tick=%d players=%d player1=%s character=%s", event.tick,
      game.players and #game.players or -1,
      tostring(game.players and game.players[1] ~= nil),
      tostring(game.players and game.players[1] and game.players[1].character ~= nil))
  end
  local player = game.players and game.players[1]
  if not player then
    return
  end
  if not storage.setup_done then
    storage.setup_done = true
    ensure_character(player, PAD)
  end
  if event.tick < first_leg or (event.tick - first_leg) % LEG_TICKS ~= 0 then
    return
  end
  legs = legs + 1
  local index = ((legs - 1) % #SUBJECTS) + 1
  local key, position = SUBJECTS[index][1], SUBJECTS[index][2]
  local camera = {x = position.x, y = position.y + 2}
  local ok, err = pcall(function()
    if player.character then
      player.teleport(camera, game.surfaces[1])
      player.zoom = 1.0
    else
      player.set_controller{type = defines.controllers.remote, position = camera,
                            surface = game.surfaces[1], start_zoom = 1.0}
    end
    -- visual anchors for the screenshot: a red ring around the subject and a green
    -- dot at the camera centre, so the grab can be checked by eye
    rendering.draw_circle{surface = game.surfaces[1], color = {r = 1, g = 0.1, b = 0.1},
                          radius = 1.0, width = 2, position = position,
                          time_to_live = LEG_TICKS}
    rendering.draw_circle{surface = game.surfaces[1], color = {r = 0.1, g = 1, b = 0.1},
                          radius = 0.2, width = 2, position = camera,
                          time_to_live = LEG_TICKS}
  end)
  if not ok then
    logf("camera move FAILED: %s", tostring(err))
  end
  logf("HOVER_%s leg=%d subject=%.1f,%.1f camera=%.1f,%.1f body=%.1f,%.1f character=%s", key, legs,
    position.x, position.y, camera.x, camera.y,
    player.position and player.position.x or -1, player.position and player.position.y or -1,
    tostring(player.character ~= nil))
end)
