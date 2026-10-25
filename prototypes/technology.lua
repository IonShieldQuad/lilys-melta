local C = require("constants")

-- Technology icons are authored at 256 px in 2.1 (vanilla: 480x256 = the 256 px
-- icon plus its 128/64/32 px mip levels packed to the right). Our own render at
-- that size keeps the tech page crisp instead of upscaling the 64 px item icon.
local TECH_ICON = "__lilys-melta__/graphics/icons/melta-turret-technology.png"
local TECH_ICON_SIZE = 256

data:extend(
{
  {
    type = "technology",
    name = C.tech,
    icon = TECH_ICON,
    icon_size = TECH_ICON_SIZE,
    effects =
    {
      {type = "unlock-recipe", recipe = C.turret},
      {type = "unlock-recipe", recipe = C.fluid}
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
