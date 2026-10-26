-- Harness only: nothing here changes lilys-melta. A `--create` save has no character and
-- sits on the remote controller, so the crafting menu cannot be opened in it. This turns
-- the player into a normal character and unlocks the melta recipe, so the crafting menu
-- shows the turret in its real group/subgroup instead of hiding it behind a technology.
--
-- Waits for tick 10 because `--create` runs no ticks: the save is written with this handler
-- registered and runs it as soon as the GUI run starts simulating.

local prepared = false

local function prepare()
  local player = game.players[1]
  if not player then
    return false
  end

  player.set_controller{type = defines.controllers.god}
  if not player.character then
    -- 2.1: create_character's only argument is the character entity to attach
    -- ("EntityWithQualityID", optional) -- not a position or a surface. Passing a point
    -- fails with "value for required field 'name' is missing". No argument spawns the
    -- default character, which is all this probe needs (it only has to open the menu).
    player.create_character()
  end
  player.set_controller{type = defines.controllers.character, character = player.character}

  local recipe = player.force.recipes["melta-turret"]
  if recipe then
    recipe.enabled = true
  end
  local technology = player.force.technologies["melta-turret"]
  if technology then
    technology.researched = true
  end

  -- A fresh --create force has almost nothing researched, so the combat group would show
  -- only ammo and the picture would prove nothing. Unlock everything: the crafting menu then
  -- lists every turret next to the melta, which is what the card is about.
  local unlocked = 0
  for _, proto in pairs(player.force.recipes) do
    if not proto.enabled then
      proto.enabled = true
      unlocked = unlocked + 1
    end
  end
  for _, proto in pairs(player.force.technologies) do
    if not proto.researched then
      proto.researched = true
    end
  end
  log(string.format("[itemorder] unlocked %d more recipes", unlocked))

  log(string.format("[itemorder] PROBE READY character=%s recipe_enabled=%s subgroup=%s order=%s",
    tostring(player.character ~= nil),
    tostring(recipe and recipe.enabled),
    tostring(prototypes.item["melta-turret"].subgroup),
    tostring(prototypes.item["melta-turret"].order)))

  -- The runtime prototype table, one line per item, so the ordering can be checked from the
  -- log alone (the crafting list is sorted by subgroup order then item order).
  for name, proto in pairs(prototypes.item) do
    if proto.subgroup and proto.subgroup.name == prototypes.item["melta-turret"].subgroup.name then
      log(string.format("[itemorder] sib %s order=%s", name, tostring(proto.order)))
    end
  end
  return true
end

-- Clean frames of the live GUI. `game.take_screenshot` with show_gui=true photographs the game
-- window as the player sees it, so the crafting menu can be read off a 1920x1080 image with no
-- browser or second monitor in it. A plan step that opens the menu lands somewhere inside this
-- window; the tick numbers are in the file names, so the right frame is easy to pick.
local SHOT_FIRST, SHOT_EVERY, SHOT_LAST = 60, 30, 900
local next_shot = SHOT_FIRST

script.on_event(defines.events.on_tick, function(event)
  if not prepared then
    if event.tick >= 10 then
      prepared = prepare()
    end
    return
  end
  local player = game.players[1]
  if not player or event.tick < next_shot or event.tick > SHOT_LAST then
    return
  end
  next_shot = next_shot + SHOT_EVERY
  game.take_screenshot{
    player = player,
    path = string.format("itemorder/gui-%04d.png", event.tick),
    show_gui = true,
    hide_fog = true,
    hide_health_bars = true
  }
end)
