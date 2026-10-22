-- Lily's Thermal Beam turret -- every number the turret uses lives here.
-- Both stages read this file (data.lua for the prototype, control.lua for the
-- beam maths), so a value can never disagree between the prototype and the script.
-- Retune freely: nothing below is structural.

local C = {}

-- names ----------------------------------------------------------------------
C.turret        = "melta-turret"
C.ammo          = "melta-fuel"
C.beam          = "melta-beam"
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
C.beam_width_cold = 0.35
C.beam_width_hot  = 1.70
C.color_cold      = {r = 1.00, g = 0.32, b = 0.08, a = 0.55}
C.color_hot       = {r = 1.00, g = 0.88, b = 0.60, a = 0.90}

-- fuel -----------------------------------------------------------------------
-- The engine eats one cell per C.magazine_size pulses by itself (that is the
-- ammo item's magazine). On top of that a hot beam burns a script-side surcharge,
-- so holding a full-intensity beam costs about twice what tapping does.
C.magazine_size            = 60
C.extra_cell_per_pulse_hot = 0.017

-- set true to log every pulse and every fire/stop transition into factorio-current.log
C.debug = false

return C
