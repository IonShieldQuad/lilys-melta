-- Harness only: nothing here ships with lilys-melta.
--
-- Two jobs, both of which a `--create` save cannot do by itself:
--   1. build the scene in `on_init` (a save written by --create runs no ticks, so a
--      tick-built scene would never exist in it), on flat refilled ground, with the
--      turret the card is about;
--   2. once the GUI run starts simulating, hand the player a real character (a --create
--      save sits on the remote controller and has no character at all), aim the camera
--      so the turret hangs a few tiles above the screen centre, and paint every melta
--      locale key into the screen GUI -- the entity tooltip is photographed from the
--      real mouse hover, the strings that need no hover are read straight off the
--      labels.
--
-- Log lines the capture driver waits for:
--   [localeprobe] SCENE <details>      scene built during --create
--   [localeprobe] READY zoom=<z> dy=<screen px between camera centre and turret>

local READY = false

local function report(message)
  log("[localeprobe] " .. message)
end

local function setup_scene()
  local surface = game.surfaces[1]
  surface.request_to_generate_chunks({0, 0}, 2)
  surface.force_generate_chunk_requests()

  local tiles = {}
  for x = -8, 8 do
    for y = -8, 8 do
      tiles[#tiles + 1] = {name = "refined-concrete", position = {x, y}}
    end
  end
  surface.set_tiles(tiles, true)

  for _, entity in pairs(surface.find_entities_filtered{area = {{-8, -8}, {8, 8}}}) do
    if entity.valid and entity.type ~= "character" then
      entity.destroy()
    end
  end

  local turret = surface.create_entity{
    name = "melta-turret",
    position = {0, 0},
    force = game.forces.player,
    raise_built = true
  }
  if turret then
    -- a full buffer, so the panel is not the "no fuel" variant.
    -- insert_fluid takes a Fluid table: {name=..., amount=...}
    pcall(function() turret.insert_fluid{name = "light-oil", amount = 200} end)
  end

  local contents = {}
  if turret then
    for name, amount in pairs(turret.get_fluid_contents()) do
      contents[#contents + 1] = string.format("%s=%s", name, tostring(amount))
    end
  end

  report(string.format("SCENE turret=%s fluids=%s", tostring(turret ~= nil),
    #contents > 0 and table.concat(contents, ",") or "empty"))
end

local function label(parent, caption)
  local element = parent.add{type = "label", caption = caption}
  element.style.single_line = false
  element.style.maximal_width = 760
  element.style.font = "default"
  return element
end

local function show_strings(player)
  if player.gui.screen["localeprobe-strings"] then
    player.gui.screen["localeprobe-strings"].destroy()
  end
  local frame = player.gui.screen.add{type = "frame", name = "localeprobe-strings",
    caption = "melta locale probe", direction = "vertical"}
  frame.location = {12, 90}

  -- the two surfaces the card is judged on, at full length: the game's own
  -- localised_description of the prototype, so this is exactly what the tooltip
  -- joins (flavour line, blank line, the parameterised damage block, then the
  -- armour/research lines) -- rich-text tags included, icons and all.
  local item = prototypes.item["melta-turret"]
  local entity = prototypes.entity["melta-turret"]
  label(frame, "-- item tooltip (inventory) --")
  label(frame, item and item.localised_description or "MISSING")
  label(frame, " ")
  label(frame, "-- entity tooltip (inspect panel) --")
  label(frame, entity and entity.localised_description or "MISSING")
  label(frame, " ")

  -- every key on its own, so a missing translation or a stray key shows up
  label(frame, {"item-name.melta-turret"})
  label(frame, {"item-description.melta-turret"})
  label(frame, {"entity-name.melta-turret"})
  label(frame, {"fluid-name.melta-fuel"})
  label(frame, {"fluid-description.melta-fuel"})
  label(frame, {"technology-name.melta-turret"})
  label(frame, {"technology-description.melta-turret"})
  label(frame, {"recipe-name.melta-fuel"})
  label(frame, {"recipe-name.melta-turret"})
  label(frame, {"melta-tooltip.armor"})
  label(frame, {"melta-tooltip.research"})
end

-- Runtime locale dump.
--
-- `localised_print` resolves keys only once the locale files are loaded, and that
-- happens AFTER the data stage -- called from a data.lua it answers "Unknown key"
-- for every string, vanilla ones included. on_init runs in the runtime, and
-- `--create` runs on_init (but no ticks), so this is the offline proof:
-- every locale key resolved, the item and entity tooltips joined exactly as the
-- game will join them, and the fluid names in the fuel list looked up for real.
local function dump_locale()
  local keys = {
    {"item-name", "melta-turret"},
    {"item-description", "melta-turret"},
    {"fluid-name", "melta-fuel"},
    {"fluid-description", "melta-fuel"},
    {"entity-name", "melta-turret"},
    {"entity-description", "melta-turret"},
    {"recipe-name", "melta-turret"},
    {"recipe-name", "melta-fuel"},
    {"technology-name", "melta-turret"},
    {"technology-description", "melta-turret"},
    {"ammo-category-name", "melta"},
    {"mod-name", "lilys-melta"},
    {"mod-description", "lilys-melta"},
    {"melta-tooltip", "armor"},
    {"melta-tooltip", "research"},
  }
  for _, entry in ipairs(keys) do
    local key = entry[1] .. "." .. entry[2]
    localised_print({"", "[locale-probe] KEY ", key, " = ", {key}})
  end

  local entity = prototypes.entity["melta-turret"]
  if entity then
    -- the raw table first: a resolved string that stops short of the damage block
    -- means the prototype lost part of its localised_description, not the locale
    local ok, raw = pcall(function() return helpers.table_to_json(entity.localised_description) end)
    report("ENTITY RAW = " .. (ok and raw or ("unavailable: " .. tostring(raw))))
    localised_print({"", "[locale-probe] ENTITY FLAVOUR = ", entity.localised_description[2]})
    -- the damage block and the two mechanics lines, resolved on their own
    -- (`localised_print` prints only the first line of a multi-line string)
    local body = {""}
    for index = 3, #entity.localised_description do
      body[#body + 1] = entity.localised_description[index]
    end
    localised_print({"", "[locale-probe] ENTITY BODY = ", table.unpack(body)})
  else
    report("ENTITY TOOLTIP missing")
  end

  local item = prototypes.item["melta-turret"]
  if item then
    localised_print({"", "[locale-probe] ITEM FLAVOUR = ", item.localised_description[2]})
    local body = {""}
    for index = 3, #item.localised_description do
      body[#body + 1] = item.localised_description[index]
    end
    localised_print({"", "[locale-probe] ITEM BODY = ", table.unpack(body)})
  else
    report("ITEM TOOLTIP missing")
  end

  -- what the damage block's fuel list will print: a fluid with no name would show
  -- as its raw prototype id, which is the failure this line exists to catch
  local turret = entity
  if turret and turret.attack_parameters and turret.attack_parameters.fluids then
    for _, fuel in ipairs(turret.attack_parameters.fluids) do
      localised_print({"", "[locale-probe] FUEL ", fuel.type, " = ", {"fluid-name." .. fuel.type}})
    end
  end
end

local function prepare()
  local player = game.players[1]
  if not player then
    return false
  end

  player.set_controller{type = defines.controllers.god}
  local position = player.surface.find_non_colliding_position("character", {0, 3}, 64, 0.5) or {0, 3}
  if not player.character then
    -- 2.1: create_character takes at most a character entity, no surface/position --
    -- it spawns at the player's current controller position, so teleport afterwards
    player.create_character()
  end
  player.set_controller{type = defines.controllers.character, character = player.character}
  -- the camera follows the character, so this number is the camera centre
  player.character.teleport({0, 3})
  player.zoom = 1

  player.insert{name = "melta-turret", count = 5}
  -- slot 1 of the quickbar, so the capture driver has one *deterministic* place to
  -- hover for the item tooltip: the bar is bottom-centre and the icon is in its
  -- first slot, instead of hunting for an inventory slot inside a GUI panel
  player.set_quick_bar_slot(1, 1, "melta-turret")
  show_strings(player)

  -- screen pixels per tile = 32 * zoom; the turret sits 3 tiles north of the camera
  report(string.format("READY zoom=%s dy=%d item=%s", tostring(player.zoom),
    math.floor(3 * 32 * player.zoom), tostring(prototypes.item["melta-turret"] ~= nil)))
  return true
end

script.on_init(function()
  setup_scene()
  dump_locale()
end)

script.on_event(defines.events.on_tick, function(event)
  if READY then
    return
  end
  if event.tick >= 10 then
    READY = prepare()
  end
end)
