-- Lily's Thermal Beam turret -- every number the turret uses lives here.
-- Both stages read this file (data.lua for the prototype, control.lua for the
-- beam maths), so a value can never disagree between the prototype and the script.
-- Retune freely: nothing below is structural.

local C = {}

-- names ----------------------------------------------------------------------
C.turret        = "melta-turret"
C.fluid         = "melta-fuel"
C.stream        = "melta-stream"
C.tech          = "melta-turret"
C.damage_type   = "thermal"
C.ammo_category = "melta"

-- the beam -------------------------------------------------------------------
C.range           = 12    -- tiles. laser turret reaches 24, rocket turret 36: the melta has to be close
C.cooldown        = 8     -- ticks between pulses (7.5/s, reads as one continuous beam)
C.damage_cold     = 14    -- thermal damage per pulse, cold barrel
C.damage_hot      = 56    -- thermal damage per pulse, fully spun up
C.spin_up_ticks   = 150   -- 2.5 s of unbroken fire from cold to white-hot
C.spin_down_ticks = 60    -- 1 s to fall back to cold once the target is gone
C.pierce_falloff  = 0.82  -- each further body in the line takes this fraction of the last hit
C.pierce_max      = 12    -- hard cap on bodies a single pulse can cut through
C.hit_half_width  = 0.45  -- tiles: half-width of the line hit test around the beam axis
C.muzzle_offset   = 1.9   -- tiles in front of the turret centre the beam starts

-- beam look ------------------------------------------------------------------
-- three stacked lines: a soft heat column, an orange glow, a white-hot core
C.beam_layers =
{
  {width_cold = 0.55, width_hot = 1.90, color_cold = {r = 1.00, g = 0.30, b = 0.06, a = 0.16}, color_hot = {r = 1.00, g = 0.55, b = 0.18, a = 0.30}},
  {width_cold = 0.30, width_hot = 1.05, color_cold = {r = 1.00, g = 0.45, b = 0.12, a = 0.45}, color_hot = {r = 1.00, g = 0.78, b = 0.40, a = 0.70}},
  {width_cold = 0.12, width_hot = 0.42, color_cold = {r = 1.00, g = 0.85, b = 0.55, a = 0.80}, color_hot = {r = 1.00, g = 1.00, b = 0.95, a = 1.00}},
  -- the cutting core: stays thin and goes white-hot, that is what reads as a melta
  {width_cold = 0.05, width_hot = 0.16, color_cold = {r = 1.00, g = 0.95, b = 0.80, a = 0.95}, color_hot = {r = 1.00, g = 1.00, b = 1.00, a = 1.00}}
}
C.beam_flicker = 0.12       -- +/- fraction of the width that wobbles as the beam burns
-- the boiling plasma sheath around the core: short segments that re-roll often
C.sheath_segments    = 9
C.sheath_retune_ticks = 3

-- fuel -----------------------------------------------------------------------
-- A fluid turret burns fluid per shot all by itself; the script adds a surcharge
-- while the beam is hot, so holding full intensity costs about twice the fuel.
C.fluid_consumption         = 0.15   -- engine-side, fluid units per shot
C.extra_fluid_per_pulse_hot = 0.16   -- script-side, fluid units per pulse at full charge
C.fluid_buffer              = 100

-- Anything in this list can be piped into the turret. Entries whose fluid does not
-- exist are skipped by BOTH stages, so listing another mod's fuel is safe with or
-- without that mod installed. `damage_modifier` multiplies the beam damage, like the
-- flamethrower's fluid bonuses.
C.fuels =
{
  {name = "melta-fuel", damage_modifier = 1.0},
  -- Lily's Incendiaries: napalm burns hotter than pyrum
  {name = "lilys-napalm-mix", damage_modifier = 1.35}
}

-- Late-game ingredient hooks: if the named item (and optionally the named technology)
-- exists because another mod added it, the melta's recipe and tech pick it up on their
-- own. Wanderer is where the iridium tier is meant to live (plans.txt: "Iridium turrets
-- (Melta, IRBM, Excalibur and Durandal)"), so the names are already wired.
C.recipe_hooks =
{
  -- item, amount into the turret recipe, and a technology to hang the turret's tech off
  {item = "iridium-plate", amount = 10, technology = "iridium-processing"}
}

-- set true to log every pulse and every fire/stop transition into factorio-current.log
C.debug = false

return C
