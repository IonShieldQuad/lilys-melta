-- Balance probe (harness, never shipped) -- data stage.
--
-- Four stationary dummies with the same 1e6 hp (float32: at 1e9 the quantum is 64
-- damage and the whole spin-up ramp disappears) that differ only in resistance, so
-- one scene can answer all four questions the balance spec asks:
--
--   plain       no resistances at all            -> how much the pulse really deals
--   flat        fire+physical decrease 12, 10 %   -> is the flat half ignored?
--   percent     fire+physical percent 50 %        -> is the percentage still applied?
--   fireimmune  fire percent 100 %                -> does the physical slice land alone?
--
-- The flat-armour figure is a behemoth biter's (decrease 12, percent 10), and 12
-- is deliberately larger than the melta's cold physical slice used to be, which is
-- the case that used to come out as literally zero damage.

local RESISTANT =
{
  {type = "fire", decrease = 12, percent = 10},
  {type = "physical", decrease = 12, percent = 10}
}

local PERCENT =
{
  {type = "fire", percent = 50},
  {type = "physical", percent = 50}
}

local IMMUNE =
{
  {type = "fire", percent = 100}
}

local function dummy(name, resistances)
  local unit = table.deepcopy(data.raw["unit"]["small-biter"])
  unit.name = name
  unit.max_health = 1000000
  unit.healing_per_tick = 0
  unit.movement_speed = 0
  unit.vision_distance = 0
  unit.max_pursue_distance = 0
  unit.resistances = resistances
  unit.dying_sound = nil
  unit.corpse = nil
  unit.dying_animation = nil
  unit.collision_box = {{-0.4, -0.4}, {0.4, 0.4}}
  unit.selection_box = {{-0.5, -0.5}, {0.5, 0.5}}
  if unit.attack_parameters then
    unit.attack_parameters.cooldown = 100000
    unit.attack_parameters.range = 0
  end
  return unit
end

data:extend(
{
  dummy("melta-dummy", {}),
  dummy("melta-dummy-flat", RESISTANT),
  dummy("melta-dummy-percent", PERCENT),
  dummy("melta-dummy-fireimmune", IMMUNE)
})
