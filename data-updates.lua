-- Late-stage integration: this mod is meant to live next to her other mods, which
-- add fuels, items and technologies. Everything here is existence-checked, so each
-- hook simply does nothing when its source mod (or that mod's current version) is
-- not installed -- the melta must never crash over a missing optional dependency.

local C = require("constants")

local function report(message)
  log("[lilys-melta] " .. message)
end

--------------------------------------------------------------- fuels ---------
-- constants.lua lists every fluid the turret accepts. prototypes/entity.lua builds the
-- engine's list at DATA.LUA time and can only keep the fluids that already exist -- and
-- another mod's fluid may not exist yet. Measured on her install: lilys-melta's data.lua
-- loads at 37.9 s, lilys-cubeine's (which defines cubonium-gas) at 41.2 s, because
-- cubeine's own dependency chain pushes it later in the load order. So cubonium-gas was
-- silently dropped from the prototype even though constants.lua listed it.
--
-- This stage runs after EVERY mod's data.lua, so the missing fuels are added here. Same
-- turret, same field, one append per fluid that exists now and was not there before.
local turret = data.raw["fluid-turret"] and data.raw["fluid-turret"][C.turret]
if turret and turret.attack_parameters and turret.attack_parameters.fluids then
  local listed = {}
  for _, fuel in ipairs(turret.attack_parameters.fluids) do
    listed[fuel.type] = true
  end
  local added = {}
  for _, fuel in ipairs(C.fuels) do
    if data.raw["fluid"][fuel.name] and not listed[fuel.name] then
      turret.attack_parameters.fluids[#turret.attack_parameters.fluids + 1] =
      {
        type = fuel.name,
        damage_modifier = fuel.damage_modifier
      }
      listed[fuel.name] = true
      added[#added + 1] = fuel.name
    end
  end
  if #added > 0 then
    report("late fuels added at data-updates: " .. table.concat(added, ", "))
  end
  local names = {}
  for _, fuel in ipairs(turret.attack_parameters.fluids) do
    names[#names + 1] = fuel.type
  end
  report("fuels accepted: " .. table.concat(names, ", "))
end

-- The tooltip's fuel list is built from the same `data.raw["fluid"]` check, so it has to
-- be rebuilt here too -- it used to run in data.lua and would have kept printing the fuel
-- roster from before the top-up above.
local tooltip = require("prototypes.tooltip")
if type(tooltip) == "function" then
  tooltip()
end

------------------------------------------------------------- recipe hooks ----
-- C.recipe_hooks turns "an item that another mod adds" into an ingredient of the
-- turret and, if the technology exists too, a prerequisite of the turret's tech.
-- Wanderer is where the iridium tier belongs, so its names are already listed.
local recipe = data.raw["recipe"][C.turret]
local technology = data.raw["technology"][C.tech]

for _, hook in ipairs(C.recipe_hooks) do
  if hook.item and data.raw["item"][hook.item] then
    local applied = {}

    if recipe and hook.amount and hook.amount > 0 then
      local already = false
      for _, ingredient in ipairs(recipe.ingredients or {}) do
        if ingredient.name == hook.item then
          already = true
          ingredient.amount = ingredient.amount + hook.amount
        end
      end
      if not already then
        recipe.ingredients[#recipe.ingredients + 1] = {type = "item", name = hook.item, amount = hook.amount}
      end
      applied[#applied + 1] = string.format("recipe +%d %s", hook.amount, hook.item)
    end

    if technology and hook.technology and data.raw["technology"][hook.technology] then
      local already = false
      for _, prerequisite in ipairs(technology.prerequisites or {}) do
        if prerequisite == hook.technology then
          already = true
        end
      end
      if not already then
        technology.prerequisites[#technology.prerequisites + 1] = hook.technology
        applied[#applied + 1] = "tech requires " .. hook.technology
      end
    end

    if #applied > 0 then
      report(table.concat(applied, "; "))
    end
  end
end

------------------------------------------ research: melta firing speed ----------
-- The melta's pulse clock is scripted (control.lua `state.pulse_at`), so the
-- engine cannot speed it up on its own -- and a fluid turret's ammo category is
-- never named by any speed technology, which is why a vanilla flamethrower does
-- not get faster either. Gun turrets do: their dps is damage research x firing
-- speed research (2.2 x 2.5 = 5.5x at the end of the finite lines), and a melta
-- that only took the damage half would fall behind exactly the turret it is
-- supposed to match.
--
-- So every technology that carries a `gun-speed` modifier for bullets also gets
-- the same modifier for the melta's own ammo category. Two things follow:
--   * the effect is visible in the tech tooltip ("Melta turret firing speed"),
--     so the player can see why the beam got faster;
--   * control.lua reads the same modifiers (C.research_rate_ammo) and divides
--     the pulse interval by the bonus -- no data-stage number is duplicated in
--     the script, it is the same table the engine was handed.
-- Existence-checked like everything else here: mods that add their own bullet
-- speed levels are picked up automatically, and a game without the vanilla line
-- simply gets nothing.
local research_categories = C.research_rate_ammo or {}
local copies, sources = 0, 0
for _, technology in pairs(data.raw["technology"] or {}) do
  local effects = technology.effects
  if effects then
    local wanted = {}
    for _, effect in ipairs(effects) do
      if effect.type == "gun-speed" and effect.ammo_category == "bullet" and (effect.modifier or 0) > 0 then
        wanted[#wanted + 1] = effect.modifier
      end
    end
    if #wanted > 0 then
      sources = sources + 1
      for _, category in ipairs(research_categories) do
        if category ~= "bullet" then
          local present = false
          for _, effect in ipairs(effects) do
            if effect.type == "gun-speed" and effect.ammo_category == category then
              present = true
            end
          end
          if not present then
            for _, modifier in ipairs(wanted) do
              effects[#effects + 1] =
              {
                type = "gun-speed",
                ammo_category = category,
                modifier = modifier
              }
              copies = copies + 1
            end
          end
        end
      end
    end
  end
end
if sources > 0 then
  report(string.format("melta firing speed: %d gun-speed effects copied from %d technologies", copies, sources))
end

--------------------------------- research: melta damage shows in the techs ----
-- The flamethrower turret appears in the fire line's effects because every
-- `refined-flammables` level carries TWO effects: `ammo-damage` for the flamethrower
-- ammo category and `turret-attack` for the `flamethrower-turret` prototype. The melta
-- was invisible in that list -- it is not a turret any vanilla technology names -- so a
-- player could not see that fire research touches it at all.
--
-- Mirroring the `turret-attack` half onto `melta-turret` fixes that: the tech tooltip
-- then lists the melta next to the flamethrower, which is also what makes the engine
-- report the ladder to the script (`force.get_turret_attack_modifier`, read in
-- control.lua). It cannot double-dip the damage: the melta's engine-side stream is
-- zeroed on purpose (`prototypes/melta.lua`), so the only damage the modifier could act
-- on is the script's, and the script reads the modifier instead of being multiplied by
-- the engine.
--
-- Donor list = the turret the vanilla fire line names. A modded damage technology that
-- only adds `ammo-damage` for our categories is caught by the second pass, so the melta
-- still appears wherever fire damage is researched.
local DONOR_TURRETS = {"flamethrower-turret"}
local mirrored, fallbacks = 0, 0
for _, technology in pairs(data.raw["technology"] or {}) do
  local effects = technology.effects
  if effects then
    local attack = {}          -- donor turret-attack modifiers to mirror
    local ammo = {}            -- ammo-damage modifiers for our categories
    local named_melta = false
    for _, effect in ipairs(effects) do
      if effect.type == "turret-attack" then
        if effect.turret_id == C.turret then
          named_melta = true
        end
        for _, donor in ipairs(DONOR_TURRETS) do
          if effect.turret_id == donor and (effect.modifier or 0) > 0 then
            attack[#attack + 1] = effect.modifier
          end
        end
      elseif effect.type == "ammo-damage" then
        for _, category in ipairs(C.research_damage_ammo or {}) do
          if effect.ammo_category == category and (effect.modifier or 0) > 0 then
            ammo[#ammo + 1] = effect.modifier
          end
        end
      end
    end
    if not named_melta then
      local wanted = #attack > 0 and attack or ammo
      for _, modifier in ipairs(wanted) do
        effects[#effects + 1] =
        {
          type = "turret-attack",
          turret_id = C.turret,
          modifier = modifier
        }
        if #attack > 0 then
          mirrored = mirrored + 1
        else
          fallbacks = fallbacks + 1
        end
      end
    end
  end
end
if mirrored + fallbacks > 0 then
  report(string.format("melta damage research: %d turret-attack effects mirrored (%d from ammo-damage only)",
    mirrored, fallbacks))
end
