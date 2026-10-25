-- The damage readout in the melta's tooltip.
--
-- Why this file exists: the melta's damage is not the engine's. A fluid turret can
-- only fire `stream` attacks, and the stream this mod ships is deliberately
-- invisible and deals nothing measurable -- a measured pulse takes exactly 56.00 hp
-- off an unarmoured dummy at full charge, i.e. the script's number from
-- control.lua and not a point more (docs/verification/). So the engine has no damage
-- figure of its own to print and the inspect panel shows no damage line at all.
--
-- Everything that decides the damage -- the charge ramp, the fuel multiplier, the
-- pierce falloff, the rock channel -- lives in constants.lua, so the tooltip text is
-- generated from constants.lua here: the numbers cannot drift away from the code
-- that applies them, and a retune shows up in the tooltip by itself.
--
-- The strings themselves are translated in locale/; this file only supplies values.

local C = require("constants")

-- 14 -> "14", 7.5 -> "7.5", 82.0 -> "82"
local function num(value)
  local text = string.format("%.2f", value)
  text = text:gsub("0+$", ""):gsub("%.$", "")
  return text
end

local function percent(value)
  return num(value * 100) .. "%"
end

-- "7.5" pulses per second from an 8-tick cooldown
local per_second = 60 / C.cooldown

-- only the fuels this install actually has, exactly like the prototype does -- a fuel
-- belonging to an absent mod must not appear in the tooltip either
local fuels = {}
for _, fuel in ipairs(C.fuels) do
  if data.raw["fluid"] and data.raw["fluid"][fuel.name] then
    -- two decimals always: "x1.00" next to "x0.85" reads as one column, "x1" does not
    fuels[#fuels + 1] = string.format("[fluid=%s] x%.2f", fuel.name, fuel.damage_modifier or 1)
  end
end

-- __1__ cold per pulse, __2__ white-hot, __3__ fire share, __4__ physical share,
-- __5__ pulses per second, __6__ cold dps, __7__ hot dps, __8__ pierce falloff,
-- __9__ pierce cap, __10__ the fuel list, __11__ the rock multiplier
--
-- The rock sentence is its own key, not a number: `asteroid_damage_multiplier = 0`
-- is the documented way to remove that channel, and a tooltip that still promised an
-- explosion hit at 0 % would be exactly the sort of lie this file exists to stop.
local asteroid_percent = C.asteroid_damage_multiplier or 0
local block
if asteroid_percent > 0 then
  block =
  {
    "melta-tooltip.block",
    num(C.damage_cold),
    num(C.damage_hot),
    percent(1 - C.physical_share),
    percent(C.physical_share),
    num(per_second),
    num(C.damage_cold * per_second),
    num(C.damage_hot * per_second),
    percent(C.pierce_falloff),
    tostring(C.pierce_max),
    table.concat(fuels, ", "),
    percent(asteroid_percent)
  }
else
  block =
  {
    "melta-tooltip.block-no-rocks",
    num(C.damage_cold),
    num(C.damage_hot),
    percent(1 - C.physical_share),
    percent(C.physical_share),
    num(per_second),
    num(C.damage_cold * per_second),
    num(C.damage_hot * per_second),
    percent(C.pierce_falloff),
    tostring(C.pierce_max),
    table.concat(fuels, ", ")
  }
end

-- The description the player reads: the flavour text that already exists in locale/,
-- then the generated damage block. Same block on the item and on the entity, so the
-- inventory tooltip and the inspect panel cannot disagree.
local function with_damage(flavour_key)
  return {"", {flavour_key}, "\n\n", block}
end

local entity = data.raw["fluid-turret"] and data.raw["fluid-turret"][C.turret]
if entity then
  entity.localised_description = with_damage("entity-description." .. C.turret)
end

local item = data.raw["item"] and data.raw["item"][C.turret]
if item then
  item.localised_description = with_damage("item-description." .. C.turret)
end
