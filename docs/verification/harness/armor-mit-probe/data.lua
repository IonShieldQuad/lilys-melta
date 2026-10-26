-- Engine mitigation probe (never shipped): the six armour profiles under test.
local PROFILES =
{
  {"no_res",        {}},
  {"flat12",        {{type = "physical", decrease = 12}}},
  {"pct10",         {{type = "physical", percent = 10}}},
  {"flat12_pct10",  {{type = "physical", decrease = 12, percent = 10}}},
  {"flat12_pct100", {{type = "physical", decrease = 12, percent = 100}}},
  {"neg5_pct10",    {{type = "physical", decrease = -5, percent = 10}}}
}

local protos = {}
for _, profile in ipairs(PROFILES) do
  for _, variant in ipairs({"plain", "comp"}) do
    local unit = table.deepcopy(data.raw["unit"]["small-biter"])
    unit.name = "mit-probe-" .. variant .. "-" .. profile[1]
    unit.max_health = 100000
    unit.healing_per_tick = 0
    unit.movement_speed = 0
    unit.vision_distance = 0
    unit.max_pursue_distance = 0
    unit.resistances = profile[2]
    unit.dying_sound = nil
    unit.corpse = nil
    unit.dying_animation = nil
    unit.collision_box = {{-0.4, -0.4}, {0.4, 0.4}}
    unit.selection_box = {{-0.5, -0.5}, {0.5, 0.5}}
    if unit.attack_parameters then
      unit.attack_parameters.cooldown = 100000
      unit.attack_parameters.range = 0
    end
    protos[#protos + 1] = unit
  end
end

data:extend(protos)
