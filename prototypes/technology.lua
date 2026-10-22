local C = require("constants")

local turret_icon = data.raw["item"][C.turret].icon

data:extend(
{
  {
    type = "technology",
    name = C.tech,
    icon = turret_icon,
    icon_size = 64,
    effects =
    {
      {type = "unlock-recipe", recipe = C.turret},
      {type = "unlock-recipe", recipe = C.ammo}
    },
    -- a beam weapon with a fuel feed: you need a reliable beam (laser turret) and
    -- the oil chain that makes the fuel worth burning
    prerequisites = {"laser-turret", "advanced-oil-processing"},
    unit =
    {
      count = 150,
      ingredients =
      {
        {"automation-science-pack", 1},
        {"logistic-science-pack", 1},
        {"military-science-pack", 1},
        {"chemical-science-pack", 1}
      },
      time = 30
    },
    order = "e[melta-turret]"
  }
})
