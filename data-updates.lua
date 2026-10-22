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
