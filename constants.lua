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
C.range           = 16    -- tiles, at normal quality. laser turret reaches 24, rocket
                          -- turret 36: the melta is still the close-in weapon, but 16 is
                          -- what makes its 2x2 hull and its slow fuel burn worth the space.
-- Range grows with quality through the ENGINE's own multiplier: every quality
-- prototype carries a `range_multiplier` (2.1.23: normal 1.0, uncommon 1.1, rare 1.2,
-- epic 1.3, legendary 1.5) and the engine applies it to a turret's
-- `attack_parameters.range` -- measured, not assumed: with the base at 12 a legendary
-- melta acquired and burned fluid at 19 tiles while a normal one stopped at 13
-- (docs/verification/harness/melta-range). So a legendary melta reaches
-- 16 * 1.5 = 24 tiles with no help from this mod.
-- What the script needs the multiplier for is the *drawn beam*: the lance must be
-- exactly as long as the engine's real reach. The clamp is the part the engine cannot
-- do -- a modded quality with a silly multiplier must not turn the melta into an
-- artillery piece.
C.range_max          = 24   -- tiles, hard ceiling on the beam (16 * vanilla legendary)
C.range_scan_ticks   = 6    -- a turret handed a target it cannot reach (a neighbour's
                            -- call_for_help, which ignores range) looks for a reachable
                            -- one this often (ticks)

C.cooldown        = 8     -- ticks between pulses (7.5/s, reads as one continuous beam)
C.damage_cold     = 14    -- damage per pulse, cold barrel (85 % fire + 15 % physical)
C.damage_hot      = 56    -- damage per pulse, fully spun up (same split)
C.spin_up_ticks   = 150   -- 2.5 s of unbroken fire from cold to white-hot
C.spin_down_ticks = 60    -- 1 s to fall back to cold once the target is gone
C.pierce_falloff  = 0.82  -- each further body in the line takes this fraction of the last hit
C.pierce_max      = 12    -- hard cap on bodies a single pulse can cut through
C.hit_half_width  = 0.45  -- tiles: half-width of the line hit test around the beam axis

-- asteroids / rocks ------------------------------------------------------------
-- A melta pulse is 85 % fire, and EVERY space-age asteroid is 100 % fire resistant:
-- data/space-age/prototypes/entity/asteroid.lua gives every asteroid an explicit
-- `percent = 100` entry for each damage type its type does not list, and fire is
-- listed for none of them. So 85 % of the beam is literally nothing on a rock, and
-- the 15 % physical slice is all that lands -- until the rock's flat armour eats it:
--
--   asteroid   hp    physical resistance        physical that lands per pulse (hot)
--   small      100   none                       8.4
--   medium     400   10 %, no flat armour       7.6
--   big       2000   10 % and -2000 flat        0.0   <- the whole slice is absorbed
--   huge      5000   10 % and -3000 flat        0.0   <- same
--
-- Rocks therefore get their own channel: an extra hit sized as a multiple of the
-- pulse, in a damage type the vanilla asteroid ladder already balances. `explosion`
-- is that ladder (small 50 %, medium 30 %, big 10 %, huge 99 % resistance), so the
-- melta becomes a small/medium/big rock killer and leaves huge asteroids to the
-- railgun -- the progression space-age already ships.
--
-- `asteroid_damage_multiplier` is the single dial (0 removes the channel). Measured
-- on metallic asteroids with one turret on light oil (docs/verification/
-- asteroid-damage.md): 1.6 gives 2-3 pulses for a small rock, 5-6 for a medium and 17
-- for a big one, while a huge one takes >10 minutes and stays untouched in practice.
-- 1.9 was measured too: big drops 17 -> 15 pulses, medium and small are unchanged.
-- Pawns never see this number -- it is gated on `entity.type == "asteroid"` in
-- control.lua, and biter dps was measured identical before and after.
C.asteroid_damage_type       = "explosion"
C.asteroid_damage_multiplier = 1.6   -- x pulse damage per pulse, asteroids only


-- aiming ----------------------------------------------------------------------
-- The engine turns the head at `rotation_speed` (in turns per tick: 1 = a full
-- circle). 0.03 = 10.8 deg/tick, i.e. a half turn in 17 ticks (0.28 s) -- twice
-- the vanilla gun turret's 0.015, because a short-ranged turret has to swing
-- faster than a long-ranged one to keep up: the angular speed needed to stay on a
-- target is v/(2*pi*r), so a behemoth biter (0.3 tiles/tick) crossing at 4 tiles
-- needs 0.012 turns/tick. The old 0.006 could not do that (it trailed by half a
-- turn at close range) and needed 83 ticks -- 1.4 s -- for a half turn.
-- Measured on 2.1.23 with the harness in docs/verification/harness.
C.rotation_speed  = 0.03  -- turns per tick
C.aim_tolerance   = 0.006 -- turns (1 = full circle). ~2 deg: the beam fires only when
                          -- the barrel is this close to the bearing. Deliberately not
                          -- a whole rotation step: the engine clamps onto the exact
                          -- bearing, so a small threshold fires on the tick it arrives
                          -- instead of letting a shot leave off-bore.
C.windup_ticks    = 3     -- 0.05 s of charge glow before the first shot at a newly
                          -- acquired target. Short on purpose: with the fast head the
                          -- 45 deg swing takes 5 ticks, so a long wind-up would just
                          -- delay the first pulse on every target switch.

-- muzzle geometry ------------------------------------------------------------
-- Where the beam starts is not "1.51 tiles in front of the pivot": the head sprite
-- is a pitched-camera render, so a ground point has to be chosen that *looks* like
-- the mouth of the heat projector. Two numbers do it, both read off the model
-- (graphics/_blender/melta_render.py: muzzle at model y 1.80, barrel axis at z 0.86,
-- gun root scaled 0.84) and verified against Blender's own camera projection for all
-- 64 directions (graphics/_blender/muzzle_marker.py, agreement < 0.001 tiles).
C.muzzle_forward  = 1.512 -- tiles along the barrel, pivot -> front face of the mouth
C.muzzle_height   = 0.722 -- tiles above ground: the barrel axis height
C.camera_tilt_deg = 51    -- the render camera's pitch from vertical. control.lua uses
                          -- cos(tilt) to foreshorten the forward reach on screen and
                          -- sin(tilt)*height to lift a raised muzzle up the screen.

-- plumbing -------------------------------------------------------------------
-- Where a pipe stops against the emplacement. Two hard constraints set this number:
--   1. a 1-tile pipe can only be built 2.0 tiles from the turret's centre (its 1.0
--      tile is inside the turret's 1.2 collision box), so the pipe's mouth lands at
--      1.5 tiles -- and the engine refuses a pipe_connection outside the entity's
--      collision box ("position must be inside of entity bounding box"), so the
--      socket can never be drawn at the mouth itself, only as close in as 1.199;
--   2. the turret rotates, and pipe connections rotate with the entity, so an
--      asymmetric reach would move every port by up to 0.15 tiles on an R press and
--      slide the sockets off their pipes. One symmetric number keeps the four ports
--      on top of themselves for all four rotations (proved with a headless probe).
-- 1.12 is the measured compromise: the rendered hull's silhouette is 1.56 tiles wide
-- on X but only 1.02-1.09 on Y (the camera is pitched 51 deg), so 1.12 sits within a
-- tenth of a tile of the rim on all four sides and the vanilla pipe-cover sprite
-- reads as a socket on the housing instead of a plate floating in the gap.
C.pipe_reach = 1.12   -- tiles, all four sides


-- beam look ------------------------------------------------------------------
-- WIDTHS ARE IN TILES, except where a line is handed to the engine (it takes PIXELS,
-- 32 per tile -- control.lua converts once with C.px_per_tile).
--
-- This is the bug that made the old beam read as a placeholder: the previous table
-- was written as if `rendering.draw_line`'s width were tiles, but it is pixels, so the
-- whole four-line stack was at most 1.90 px = 0.06 tile wide -- a hairline, thinner
-- than the barrel it came out of. Widths below are what the beam should actually
-- cover on the ground.
C.px_per_tile = 32

-- The sprite layers the glow is made of (prototypes/beam.lua), with the footprint each
-- one is authored at: `tiles = {width, height}` at scale 1. control.lua divides the
-- wanted size by these to get x_scale/y_scale.
C.beam_texture =
{
  haze   = {sprite = "melta-beam-haze",   tiles = {2, 8}},
  glow   = {sprite = "melta-beam-glow",   tiles = {2, 8}},
  tongue = {sprite = "melta-beam-tongue", tiles = {1, 2}},
  flare  = {sprite = "melta-beam-flare",  tiles = {4, 4}},
  cone   = {sprite = "melta-beam-cone",   tiles = {2, 4}}   -- apex at the mouth
}

-- The cutting core: two stacked lines, tiles wide. The inner one is the white-hot
-- edge; both are drawn as lines rather than sprites because the core has to stay
-- sharp at every zoom and follow the target exactly.
C.beam_core =
{
  {width_cold = 0.14, width_hot = 0.34, alpha_cold = 0.85, alpha_hot = 1.00},
  {width_cold = 0.05, width_hot = 0.12, alpha_cold = 0.95, alpha_hot = 1.00}
}

-- The glow around the core: three additive sprites, tiles wide (cold .. hot), tinted
-- with the fuel's sheath colour (the innermost mixes toward the core colour). Wide and
-- faint outside, tight and bright inside -- that gradient is the "glow", and because
-- the blend is additive it reads as light on dark terrain instead of as a grey wash.
C.beam_glow =
{
  {texture = "haze", tint = "sheath", width_cold = 1.70, width_hot = 3.70,
   alpha_cold = 0.20, alpha_hot = 0.36},
  {texture = "glow", tint = "sheath", width_cold = 0.75, width_hot = 1.80,
   alpha_cold = 0.30, alpha_hot = 0.52},
  {texture = "glow", tint = "core",   width_cold = 0.32, width_hot = 0.85,
   alpha_cold = 0.30, alpha_hot = 0.50}
}
C.beam_flicker     = 0.12   -- +/- fraction of the width that wobbles as the beam burns
-- the boiling plasma sheath around the core: soft blobs that re-roll a few times a
-- second (they replaced short hard-edged line segments, which read as shards)
C.beam_tongues      = 6      -- segments in the sheath
C.beam_tongue_ticks = 3      -- re-roll interval, ticks
C.beam_tongue_len   = {0.60, 1.80}   -- tiles, cold .. hot
C.beam_tongue_width = {0.30, 0.95}   -- tiles, cold .. hot
-- alpha has to hold up *against the core*: below ~0.15 the tongues are invisible next to
-- it and the lance collapses back into a clean bar, which is what the first pass did
C.beam_tongue_alpha = {0.18, 0.45}

-- Muzzle: a burst flare at the mouth plus a cone of blast pointing down the beam. Both
-- pop for C.beam_pulse_ticks after each pulse, so the shot has a thump instead of
-- being a constant hum. Sizes in tiles.
C.beam_muzzle =
{
  offset    = 0.22,                      -- forward of the mouth, so the flare is not
                                         -- buried inside the barrel sprite
  flare_cold = 1.30, flare_hot = 2.90,
  flare_alpha = 0.55,
  -- long enough to read past the flare: a cone that only covers the first tile is
  -- completely hidden behind the burst
  cone_len_cold = 1.60, cone_len_hot = 3.80,
  cone_width_cold = 0.90, cone_width_hot = 2.30,
  cone_alpha = 0.65
}
-- Impact: a flare wherever the nearest cut body is (so the beam visibly bites), and a
-- smaller one where the lance reaches its full length, so it terminates in something
-- instead of stopping in mid-air.
C.beam_impact = {flare_cold = 0.85, flare_hot = 2.00, alpha = 0.55}
C.beam_tip    = {flare_cold = 0.55, flare_hot = 1.10, alpha = 0.28}
C.beam_pulse_pop    = 1.45   -- size multiplier while a pulse is fresh
C.beam_pulse_ticks  = 3      -- how long "fresh" lasts, ticks
C.beam_pop_ticks    = 6      -- how long the one-shot flares live before the engine
                             -- frees them (cut marks at every body on the line)
-- Fade: the lance thins and dims over this many ticks when firing stops (or when the
-- turret/target dies mid-beam) instead of snapping off the screen.
C.beam_fade_ticks   = 10

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
