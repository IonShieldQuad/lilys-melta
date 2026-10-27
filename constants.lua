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
C.cooldown_min    = 2     -- floor for the researched pulse interval: a modded
                          -- +400 % firing-speed bonus must not turn the beam into
                          -- a per-tick damage hose

-- DAMAGE ---------------------------------------------------------------
-- The melta is compared with two turrets, and both of them are ahead on
-- something else: the gun turret outranges it (18 tiles, the tesla 30, the
-- melta 16) and the tesla turret hits a whole chain of bodies (up to 10 jumps
-- at 120 electric each, i.e. 60 dps single-target but up to ~600 across a
-- chain). What the melta has is *dps on the one body in front of it*, so that
-- is what this number has to buy:
--
--   turret (no research, unarmoured)   single-target dps
--   gun turret, firearm magazine        50   (10 shots/s x 5)
--   gun turret, piercing rounds         80   (10 shots/s x 8)
--   gun turret, uranium rounds         240   (10 shots/s x 24)
--   tesla turret                        60   (0.5 shots/s x 120, plus chain)
--   melta, cold barrel                 240   <- 32 x 7.5
--   melta, fully spun up               420   <- 56 x 7.5 = 1.75x cold
--
-- 32 cold puts the cold barrel level with the strongest gun turret (uranium
-- rounds) even though it only reaches 16 tiles and drinks fluid instead of
-- ammo; the spin-up then leaves every other turret well behind, which is what
-- pays for the short reach and the fuel bill. Before this the cold barrel was
-- 14 (105 dps) -- below a *piercing* gun turret -- and the turret only became
-- worth its plumbing once it was white hot.
C.damage_cold     = 32    -- damage per pulse, cold barrel (85 % fire + 15 % physical)
C.damage_hot      = 56    -- damage per pulse, fully spun up (same split) = 1.75x cold
C.spin_up_ticks   = 150   -- 2.5 s of unbroken fire from cold to white-hot
C.spin_down_ticks = 60    -- 1 s to fall back to cold once the target is gone
C.pierce_falloff  = 0.82  -- each further body in the line takes this fraction of the last hit
C.pierce_max      = 12    -- hard cap on bodies a single pulse can cut through
C.hit_half_width  = 0.45  -- tiles: half-width of the line hit test around the beam axis

-- research scaling ------------------------------------------------------------
-- The beam damage is the script's, so the engine's own ammo upgrades never see
-- it: before this, EVERY turret in the game scaled with research and the melta
-- stayed at 240/420 forever, i.e. it lost the arms race it was balanced for.
-- The melta now takes the same two dips a gun turret takes:
--
--   1. damage -- the fire line (`refined-flammables`): its `ammo-damage`
--      effects for the ammo categories below, applied once per pulse. The
--      engine's carrier stream is zeroed, so this is the only place the number
--      can come from; nothing else scales it.
--   2. rate   -- the turret firing-speed line (`weapon-shooting-speed`).
--      data-updates.lua copies each level's `gun-speed` modifier onto the
--      melta's own ammo category, and control.lua shortens the pulse interval
--      by the same amount (the pulse clock is scripted, so the script has to
--      read it).
--
-- Why "double dip" needed a coefficient rather than a second modifier: every
-- turret technology ships its bonus TWICE -- `ammo-damage` for an ammo category
-- and `turret-attack` for a turret id -- and the engine multiplies the two
-- together. That is why a gun turret's damage is the square of its accumulated
-- bonus (measured: uranium rounds, 24 -> 29.06 at +10 % = 24 x 1.1^2, ->
-- 61.44 at +60 % = 24 x 1.6^2) while its firing speed is a single application.
-- The melta is not the `turret_id` any technology names (the fire line points
-- at `flamethrower-turret`), so only the `ammo-damage` half is readable -- the
-- turret-attack half simply does not exist for this turret id. A single flat
-- application of the (steeper) fire ladder leaves it 32 % behind a gun turret
-- at the end of the finite lines, so the readable half is compounded by
-- `research_damage_exponent = 1.5`, the one number that puts the cold barrel
-- level with a uranium gun turret at EVERY tier while keeping the hot end where
-- it belongs:
--
--   tier  fire dmg  rate   melta cold  melta hot   gun turret (uranium)
--    0      +0 %     +0 %     245        429       240
--    1     +20 %    +10 %     353        618       319
--    2     +40 %    +30 %     519        909       449
--    3     +60 %    +50 %     729       1275       706
--    4     +90 %    +80 %    1131       1980      1106
--    5    +120 %   +110 %    1637       2866      1632
--
-- (melta cold = 32 x (1+fire)^1.5 x the pulse rate; the gun turret column is
-- 24 x (1+bullet-dmg)^2 x its shot rate. Both columns are measured in game:
-- docs/verification/balance-verification.md. The pulse rate has to *deliver*
-- the researched bonus -- control.lua carries the fraction of a tick forward,
-- because rounding each interval up to a whole tick cost 11 % at tier 4 and put
-- the turret at 0.85x the gun there. A 1.0 exponent is the plain single dip, 2.0
-- is a literal double dip -- re-tune here, not in control.lua.)
C.research_damage_ammo    = {"flamethrower"}  -- ammo categories whose ammo-damage research scales the beam
C.research_damage_scale   = 1.0   -- 0 turns the damage dip off; 1 = the researched bonus, as-is
C.research_damage_exponent = 1.5  -- how hard the fire ladder compounds (see the table above)
C.research_rate           = true  -- false pins the pulse rate at C.cooldown (no firing-speed dip)
C.research_rate_ammo      = {"melta"}  -- ammo categories whose gun-speed research speeds the pulse clock

-- flat armour bypass ----------------------------------------------------------
-- The brief: the melta should ignore the *flat* part of an enemy's armour
-- (resistances[type].decrease) and still be subject to the *percentage* part.
-- The engine always does `max(0, damage - decrease) * (1 - percent/100)`, so
-- the only honest way to ignore the flat half is to hand the engine
-- `damage + decrease` for that damage type: the subtraction cancels and the
-- percentage is applied to the full figure. Two details matter:
--   * only a POSITIVE decrease is compensated. A NEGATIVE decrease (some modded
--     entities have one) means "takes extra damage", so adding it would subtract
--     damage and quietly turn a bonus into a penalty; those are left alone.
--   * note the vanilla big/huge asteroids carry POSITIVE physical flat armour
--     (`decrease = {0,0,0,2000,3000}`, percent {0,0,10,10,10}) -- so this bypass
--     cancels it and rocks DO take the physical slice, which they did not before.
--   * a 100 % resistance still comes out at zero damage, which is correct:
--     percentage resistance is respected, by design.
-- This touches nothing outside the melta's own pulse: no engine behaviour, no
-- other turret, no fraction of it.
C.pierce_flat_armor = true   -- ignore resistances[type].decrease on both damage components

-- asteroids / rocks ------------------------------------------------------------
-- A melta pulse is 85 % fire, and EVERY space-age asteroid is 100 % fire resistant:
-- data/space-age/prototypes/entity/asteroid.lua gives every asteroid an explicit
-- `percent = 100` entry for each damage type its type does not list, and fire is
-- listed for none of them. So 85 % of the beam is literally nothing on a rock, and
-- the 15 % physical slice is all that lands (before the flat-armour bypass, the rock's
-- own flat armour swallowed it too):
--
--   asteroid   hp    physical resistance        physical that lands per pulse (hot)
--   small      100   none                       8.4
--   medium     400   10 %, no flat armour       7.6
--   big       2000   10 % and +2000 flat        7.6   (flat ignored; was 0.0)
--   huge      5000   10 % and +3000 flat        7.6   (same)
--
-- Even with the flat armour gone that slice is 0.4 % of a big rock's health and
-- 0.15 % of a huge one -- a rounding error next to the rock's own damage output,
-- which is why rocks still need a channel of their own: an extra hit sized as a
-- multiple of the pulse, in a damage type the vanilla asteroid ladder already balances.
-- `explosion`
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

-- art placement --------------------------------------------------------------
-- The model is rendered with its pivot on the frame centre, which is right for the
-- rotation (no wobble) but wrong for the GROUND: a pitched-camera view draws a 2x2
-- emplacement so that its cast shadow and base plate sit on the tile's NORTH edge, so
-- the turret reads as floating half a tile off the tile it is actually standing on.
-- Both sprites (hull and cannon) are shifted DOWN the screen by this much. `shift` on a
-- sprite is in TILES and +y is south, so this is "half a tile toward the camera".
--
-- The pipe stubs are drawn by the ENGINE at each `pipe_connections` point, in the
-- entity's own space -- they do not take the shift, and must not: the pipes they meet
-- are on the tile grid, and moving the stubs with the art would slide them off their
-- pipes. Only the art moves.
C.sprite_shift = {0, 0.5}

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

--- Where each side's port sprite is drawn, in SCREEN tiles relative to the
--- connection point (so +y is south on screen, whatever the world axis). The port is
--- rendered once and turned by the render rig, so the same model lands at different
--- screen distances per side; the south one also had to clear the hull's deeper south
--- rim (silhouette 1.28 tiles) or its clamp collar hid behind the hull and only the
--- mouth showed. graphics/_blender/pipe_join.py reads these numbers, so the sprite
--- plane and the measurement cannot drift apart.
C.pipe_shift =
{
  north = {0, 0},
  east = {0, 0},
  south = {0, 0.18},
  west = {-0.22, 0}
}


-- beam look ------------------------------------------------------------------
-- WIDTHS ARE IN TILES. Everything the lance is made of is now a SPRITE -- including the
-- core, which used to be two `rendering.draw_line` quads. Why the lines are gone:
--   * `draw_line` has NO `render_layer` field (it is not in its parameter list at all),
--     so the core lived on a fixed layer while every other layer obeyed ours. With a
--     smog/weather mod installed that reads as the core drawing in front of the smoke
--     and the rest of the lance behind it -- two different pictures of one object.
--   * a line is a hard-edged quad: it reads as a graph line rather than plasma at every
--     zoom, and it ended dead flat where the turret's reach ran out.
-- A sprite core can be soft-edged, tapered at the far end, tinted like the rest and
-- switched to the same layer as the rest -- all three complaints, one change.

-- The sprite layers the lance is made of (prototypes/beam.lua), with the footprint each
-- one is authored at: `tiles = {width, height}` at scale 1. control.lua divides the
-- wanted size by these to get x_scale/y_scale.
C.beam_texture =
{
  core   = {sprite = "melta-beam-core",   tiles = {1, 8}},   -- soft cutting column
  haze   = {sprite = "melta-beam-haze",   tiles = {2, 8}},
  glow   = {sprite = "melta-beam-glow",   tiles = {2, 8}},
  tongue = {sprite = "melta-beam-tongue", tiles = {1, 2}},
  flare  = {sprite = "melta-beam-flare",  tiles = {4, 4}},
  cone   = {sprite = "melta-beam-cone",   tiles = {2, 4}},  -- apex at the mouth
  spray  = {sprite = "melta-beam-spray",  tiles = {2, 4}}   -- the dissolving far end
}

-- Render layer: ONE, for every object of the lance (2.1.23, 157 = "projectile").
-- This is deliberate and it is load-bearing twice over. The old beam split its layers --
-- the core was two `draw_line` quads, which have NO render_layer field at all, while the
-- glow sprites obeyed this one -- so with a smog/weather mod the core drew in front of the
-- smoke and the rest of the lance behind it. One layer, all sprites, no exceptions.
--
-- A barrel pointing AWAY from the camera does not get a lower layer (drawing the lance at
-- 122 "object-under" put it behind every biter nest, wall and tree along its length, which
-- is far worse than the problem it solved): instead the drawn lance simply STARTS further
-- down the barrel, past the point where the gun sprite can be in the way. See
-- C.beam_away_offset.
C.beam_layer = "projectile"
-- tiles to push the START of the drawn lance forward while the barrel points away from the
-- camera (~20 deg off north, `beam_behind_dot`) -- enough to lift the muzzle flare and the
-- near end of the haze off the barrel's silhouette, small enough not to read as a gap
C.beam_behind_dot = 0.35
C.beam_away_offset = 0.55

-- The cutting core: two stacked soft sprites, tiles wide (cold .. hot). `whiten` mixes
-- the tint toward white -- the inner layer is the white-hot edge, the outer one keeps the
-- fuel's colour so the lance still says which fluid is burning.
C.beam_core =
{
  {texture = "core", tint = "sheath", whiten = 0.15,
   width_cold = 0.18, width_hot = 0.42, alpha_cold = 0.55, alpha_hot = 0.75},
  {texture = "core", tint = "core",   whiten = 0.70,
   width_cold = 0.07, width_hot = 0.17, alpha_cold = 0.55, alpha_hot = 0.85}
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
-- second (they replaced short hard-edged line segments, which read as shards). The last
-- `spill` of them start at the very end of the lance and run PAST it, so the tip boils
-- and frays instead of ending on a ruled line.
C.beam_tongues      = 6      -- segments in the sheath
C.beam_tongue_ticks = 3      -- re-roll interval, ticks
C.beam_tongue_len   = {0.60, 1.80}   -- tiles, cold .. hot
C.beam_tongue_width = {0.30, 0.95}   -- tiles, cold .. hot
-- alpha has to hold up *against the core*: below ~0.15 the tongues are invisible next to
-- it and the lance collapses back into a clean bar, which is what the first pass did
C.beam_tongue_alpha = {0.18, 0.45}
C.beam_tongue_spill = 2      -- how many tongues are rolled past the far end

-- Spin-up indicator ---------------------------------------------------------
-- Damage ramps 32 -> 56 over 2.5 s of unbroken fire (`spin_up_ticks`), and until now
-- nothing on screen said so: the lance got wider and the mouth glow bigger, which reads
-- as "further away target", not as "the turret is getting hotter". So the hull carries a
-- ring of gauge lights that light up one after another as the charge climbs and go out
-- one after another as it cools. They are additive sprites (the flare texture, shrunk),
-- tinted with the fuel's sheath colour, so they look like the emitter's own light.
--
-- A RING, not a bar, and drawn in world space: the hull rotates with the entity (R
-- press), so a feature that must stay on the deck has to be symmetric about the pivot.
-- The ring is an ellipse on screen because the camera is pitched: y is squashed by
-- cos(tilt) and the whole ring is lifted up-screen by the deck height.
-- Five, not six, and big: a 6-dot ring at 0.26 tiles read as sparkle in the first
-- screenshot pass (docs/verification/visual-rework.md), because five or six small glints
-- around an octagonal hull are indistinguishable from the gauge lights the model already
-- has. Fewer, larger, whiter lights on a tight ring read as FIXTURES, and the count is
-- what carries the state.
C.spin_leds        = 5      -- gauge lights around the base
C.spin_led_radius  = 1.00   -- tiles, half-extent on X (inside the hull's 1.53)
C.spin_led_lift    = 0.34   -- tiles up-screen: they sit on the deck, not the ground
C.spin_led_size    = 0.34   -- tiles across, per light
C.spin_led_alpha   = 0.92   -- peak alpha of a lit light
C.spin_led_dim     = 0.14   -- alpha of an unlit light (a dark lens, not a hole)
C.spin_led_white   = 0.55   -- how far a lit light is mixed toward white: they have to
                            -- read against the fuel-tinted glow of their own beam
C.spin_led_layer   = "higher-object-above"   -- over the hull sprite (object = 123)

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
-- The lance used to stop exactly at `range`: a hard end, a small flare, nothing else, so
-- at maximum reach it looked scissored off. The last two tiles are now a dissolving
-- plume -- a soft spray sprite carried past the end of the beam, wide and faint, tinted
-- with the sheath -- so the heat thins into the air instead of being cut. It sits inside
-- the glow, so it reads as the beam running out of pressure rather than as a separate
-- puff. `carry` is in tiles past the tip, cold .. hot.
C.beam_dissipate =
{
  carry_cold = 1.20, carry_hot = 2.60,
  width_cold = 0.55, width_hot = 1.60,
  alpha_cold = 0.16, alpha_hot = 0.30
}
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
