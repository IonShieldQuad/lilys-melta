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
C.ammo_category = "melta"

-- The beam is FIRE, and a slice of every pulse is physical: the lance carries mass
-- as well as heat. Two damage types, one number split -- `physical_share` is taken
-- out of the same total, so the turret's damage per pulse does not change.
-- Why not one type: fire damage is what fire-vulnerable biters are supposed to eat
-- (and what the flame/burn side of the game understands), while the physical slice
-- keeps the turret useful against a 100 % fire-resistant target instead of useless.
C.damage_type      = "fire"       -- primary: what the beam is made of
C.damage_type_hit  = "physical"   -- secondary: the impact of the stream itself
C.physical_share   = 0.15         -- 0.15 = 15 % of every pulse is physical, 85 % fire

-- the beam -------------------------------------------------------------------
C.range           = 12    -- tiles. laser turret reaches 24, rocket turret 36: the melta has to be close
C.cooldown        = 8     -- ticks between pulses (7.5/s, reads as one continuous beam)
C.damage_cold     = 14    -- damage per pulse, cold barrel (85 % fire + 15 % physical)
C.damage_hot      = 56    -- damage per pulse, fully spun up (same split)
C.spin_up_ticks   = 150   -- 2.5 s of unbroken fire from cold to white-hot
C.spin_down_ticks = 60    -- 1 s to fall back to cold once the target is gone
C.pierce_falloff  = 0.82  -- each further body in the line takes this fraction of the last hit
C.pierce_max      = 12    -- hard cap on bodies a single pulse can cut through
C.hit_half_width  = 0.45  -- tiles: half-width of the line hit test around the beam axis
C.muzzle_offset   = 1.51  -- tiles in front of the turret centre the beam starts
                          -- (measured off the rendered model: the heat projector's
                          -- front face is 1.51 tiles from the pivot, see
                          -- graphics/_blender/melta_render.py meta.json)

-- beam look ------------------------------------------------------------------
-- Four stacked lines. Colours come from whichever fuel is burning (see C.fuels) and
-- the alphas ramp with charge: the sheath is the wide heat column, the core is the
-- thin cutting line that goes white-hot.
C.beam_layers =
{
  {tier = "sheath", width_cold = 0.55, width_hot = 1.90, alpha_cold = 0.16, alpha_hot = 0.30},
  {tier = "sheath", width_cold = 0.30, width_hot = 1.05, alpha_cold = 0.45, alpha_hot = 0.70},
  {tier = "core",   width_cold = 0.12, width_hot = 0.42, alpha_cold = 0.80, alpha_hot = 1.00},
  {tier = "core",   width_cold = 0.05, width_hot = 0.16, alpha_cold = 0.95, alpha_hot = 1.00}
}
C.beam_flicker = 0.12       -- +/- fraction of the width that wobbles as the beam burns
-- the boiling plasma sheath around the core: short segments that re-roll often
C.sheath_segments    = 9
C.sheath_retune_ticks = 3

-- fuel -----------------------------------------------------------------------
-- A fluid turret burns fluid per shot all by itself; the script adds a surcharge
-- while the beam is hot, so holding full intensity costs about twice the fuel.
-- 7.5 shots/s: 2.5 per shot = ~19/s cold, +3.8 per pulse at full charge = ~47/s hot
C.fluid_consumption         = 2.5    -- engine-side, fluid units per shot
C.extra_fluid_per_pulse_hot = 3.8    -- script-side, fluid units per pulse at full charge
C.fluid_buffer              = 200    -- ~4-10 s of beam in the buffer, so a short gap in the pipe is survivable

-- Anything in this list can be piped into the turret. Entries whose fluid does not
-- exist are skipped by BOTH stages, so listing another mod's fuel is safe with or
-- without that mod installed. `damage_modifier` multiplies the beam damage, like the
-- flamethrower's fluid bonuses.
-- `core` is the cutting line's colour, `sheath` the heat column around it, so the
-- fuel you burn is readable at a glance. Highest modifier present wins.
C.fuels =
{
  -- vanilla oil straight out of the refinery: cheap, orange
  {name = "light-oil", damage_modifier = 1.00,
   core = {r = 1.00, g = 0.88, b = 0.60}, sheath = {r = 1.00, g = 0.42, b = 0.10}},
  -- gas burns leaner: pale blue, less bite
  {name = "petroleum-gas", damage_modifier = 0.85,
   core = {r = 0.85, g = 0.95, b = 1.00}, sheath = {r = 0.35, g = 0.55, b = 1.00}},
  -- the good stuff: pyrum laced with uranium, green-white and vicious
  {name = "melta-fuel", damage_modifier = 1.60,
   core = {r = 0.80, g = 1.00, b = 0.75}, sheath = {r = 0.25, g = 0.95, b = 0.40}},
  -- Lily's Incendiaries: napalm, deep red and hot
  {name = "lilys-napalm-mix", damage_modifier = 1.35,
   core = {r = 1.00, g = 0.82, b = 0.55}, sheath = {r = 1.00, g = 0.28, b = 0.06}}
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
