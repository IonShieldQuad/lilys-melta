-- Late-stage integration: this mod is meant to live next to her other mods, which
-- add fuels, items and technologies. Everything here is existence-checked, so each
-- hook simply does nothing when its source mod (or that mod's current version) is
-- not installed -- the melta must never crash over a missing optional dependency.

local C = require("constants")

local function report(message)
  log("[lilys-melta] " .. message)
end

--------------------------------------------------------------- fuels ---------
-- constants.lua lists every fluid the turret accepts; prototypes/entity.lua already
-- dropped the ones this install does not have. Report what survived so a load log
-- answers "why is napalm not burning" in one glance.
local turret = data.raw["fluid-turret"] and data.raw["fluid-turret"][C.turret]
if turret and turret.attack_parameters and turret.attack_parameters.fluids then
  local names = {}
  for _, fuel in ipairs(turret.attack_parameters.fluids) do
    names[#names + 1] = fuel.type
  end
  report("fuels accepted: " .. table.concat(names, ", "))
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
