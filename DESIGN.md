# Melta turret — design

A short-ranged thermal emitter that drinks liquid fuel and cuts a line through a crowd.
Everything below is implemented and verified in-game (headless create + benchmark with a
scripted harness: spin-up, pierce falloff, fluid burn, dry-turret gate, friendly fire,
render-object leaks).

## The three things it has to feel like

1. **A lance, not a squirt gun.** One beam that starts at the muzzle and runs its whole
   12 tiles, cutting every body on the line instead of stopping at the first one.
2. **It has to warm up.** Tapping fire is a thin orange line; holding it on a target for
   ~2.5 s turns it into a boiling white-hot column and roughly quadruples the damage.
3. **It costs something.** Liquid fuel, not electricity — a turret you plumb in, and a hot
   beam burns about twice the fuel of a cold one.

## Numbers

| thing | value | why |
|---|---|---|
| hull | own rendered emplacement, 2x2 footprint (collision +-1.2) | modelled in Blender, not vanilla art | see **Graphics** below |
| head | rendered 64-direction cannon, 256x256, 8 sheets of 8 rows | see **Graphics** below |
| health | 1200 | an emitter, not an armoured box (rocket turret: 1500) |
| range | 16 tiles, scaling with quality through the engine's `range_multiplier` (17.6 / 19.2 / 20.8 / 24 at uncommon / rare / epic / legendary) | laser 24, rocket 36: the melta is still the close-in emitter, and quality is what buys the extra tiles. The engine does the scaling; the script mirrors it for the beam and clamps at 24 — see **Quality range** below |
| head rotation | 0.03 turns/tick (10.8 deg/tick) | was 0.006 (2.16 deg/tick, inherited from the rocket turret): a half turn took 83 ticks (1.4 s) and the head could not track a behemoth biter (0.3 tiles/tick) crossing at 4 tiles, which needs 0.012 turns/tick. 0.03 = half a turn in 17 ticks (0.28 s), twice the vanilla gun turret's 0.015 |
| pulse rate | 8 ticks (7.5/s) | fast enough that discrete pulses read as one beam |
| damage / pulse | 14 cold → 56 hot | 105 → 420 dps single target, before pierce |
| spin-up | 150 ticks (2.5 s) | one biter wave is not enough time to peak |
| spin-down | 60 ticks (1 s) | it cools fast, so holding a line is the skill |
| pierce | 12 bodies, 0.82 falloff each | front rank eats it, back ranks eat 82 % of the one in front |
| damage type | `fire`, with 15 % of each pulse dealt as `physical` | fire is what a melta is (and fire-vulnerable biters take it in full); the physical slice is the mass of the stream, so a fire-immune target still takes 15 % instead of nothing |
| fuel | light-oil 1.0x, petroleum-gas 0.85x, enriched melta-fuel 1.6x, incendiaries napalm 1.35x | each fuel sets damage *and* beam colour; see the fuel table below |
| burn rate | 2.5 units/shot engine-side + 3.8 per pulse at full charge | ~19/s cold, ~47/s white-hot |

Derived — per pulse at full intensity, base damage 56 (47.6 fire + 8.4 physical), and what
survives each biter's resistances (none of them resist fire; only physical is resisted):

| target | physical resistance | lands per pulse | vs the old single-type 56 |
|---|---|---|---|
| small biter | none | 56.0 (47.6 + 8.4) | unchanged |
| medium biter | decrease 4, 10 % | 51.6 (47.6 + 3.96) | −7.9 % |
| big biter | decrease 8, 10 % | 48.0 (47.6 + 0.36) | −14.2 % |
| behemoth biter | decrease 12, 10 % | 47.6 (fire only) | −15.0 % |
| any 100 % fire-resistant target | — | 8.4 (physical only) | was 0 — the reason for the split |

So the split is free against unarmoured bodies and costs up to 15 % against the armoured
end of the biter line, because flat armour eats a small physical slice whole. Turn
`C.physical_share` down if that trade is not worth it, or raise `damage_hot` by ~15 % if
behemoth dps matters more than parity with everything else.

Measured headlessly (harness mod, one target at a time, melta-fuel = 1.6x, full charge):
89.59 / 13.44 / 77.44 per pulse on the plain / fire-resistant / behemoth-armour targets —
i.e. exactly 56 x 1.6, 15 % of it, and 86.4 % of it.

Derived: a behemoth biter (3000 hp) dies in ~8 s of full-intensity fire (was ~7 s): its
flat 12 physical resistance swallows the physical slice whole (0.15 x 56 = 8.4).

## Asteroids (space age)

Rocks are the one target class the fire beam cannot touch: every asteroid prototype gets
`percent = 100` on every damage type it does not list, and `fire` is listed for none of
them — so 85 % of a pulse was zero, and the 15 % physical slice was eaten whole by the
-2000 / -3000 flat armour of big and huge asteroids. Measured before the fix: small rock
11 pulses, medium 31, big and huge never (236 pulses for 0.14 hp).

The melta now delivers one extra hit per pulse to `entity.type == "asteroid"` — an
`explosion` hit sized `C.asteroid_damage_multiplier` (1.6) x the pulse. Explosion is the
type the vanilla asteroid ladder is built on (small 50 %, medium 30 %, big 10 %, huge
99 %), so the turret becomes a small/medium/big rock killer and huge asteroids stay
railgun work. After the fix: 2–3 / 5–6 / 17 pulses and huge >8 minutes. Pawn dps is
byte-identical before and after, because the extra call is gated on the asteroid type.
Full numbers, method and the reproducible harness: `docs/verification/asteroid-damage.md`.

## How it is built

**Why a *fluid* turret.** The engine offers exactly two turret shapes: an ammo turret
(beam attacks, but its `fluid_box` is silently dropped — "does not have fluids") and a
fluid turret (fluid box, but "Fluid turret can have only stream attack parameters").
Liquid fuel therefore forces the fluid-turret type, and the beam has to be ours.

Two consequences, both handled:

- a fluid turret must be `turret_base_has_direction = true` (forced by the loader) and
  wants a 4-entry circuit connector — the collision box is symmetric and the rocket hull's
  base is a single non-directional sprite, so neither shows.
- its `turn_range` is set to `1.0` (vanilla flamers use 1/3): the turret tracks in a full
  circle like a normal turret instead of guarding one 120° arc.

**Prototype (`prototypes/`)**
- `melta-turret`: `fluid-turret` on the rocket hull, `fluid_box` filtered to
  `melta-fuel`, `fluid_buffer_size`, fuel out-of-ammo alert icon.
- `melta-stream`: a copy of the flamethrower stream with its particles zeroed and its
  damage set to 1 — **invisible on purpose**. It exists because the engine only lets a
  fluid turret consume fluid through a stream; the beam is not it.
- `melta-fuel`: fluid + chemistry recipe from light oil.
- `melta` ammo category, turret recipe, technology. (No damage type of its own any more:
  the beam is vanilla `fire` plus a `physical` slice.)

**Runtime (`control.lua`)**
- `charge` per turret: +1/150 per tick while a target is held *and* the turret has fluid,
  −1/60 per tick otherwise.
- **aiming gate** — the beam is not allowed to exist before the barrel points at the
  target. `LuaEntity::orientation` on a turret *is the weapon's* smooth orientation
  (0 = north, 0.25 = east), so each tick the script compares it with the bearing to the
  target and only fires when the head is within `C.aim_tolerance` (0.006 turns = 2.16 deg;
  deliberately tighter than one rotation step, so the shot leaves on the tick the engine
  clamps onto the exact bearing instead of up to 11 deg off-bore). While the
  head is still swinging it plays a **charge-up glow at the mouth** instead: no beam, no
  damage, and `pulse_at` is not advanced, so the first shot leaves the moment the barrel
  arrives rather than a cooldown later. A target the barrel is *already* on does not pay
  that wind-up (killing a biter and picking the next one on the same line stays at full
  rate).
- **muzzle** — the beam starts where the sprite *draws* the mouth, which is not
  `position + forward * length`: the head is a pitched-camera render (51 deg from
  vertical), so the forward reach is foreshortened by cos(51°) on the screen's vertical
  axis and the raised muzzle sits sin(51°) * 0.722 tiles further up the screen (north).
  `C.muzzle_forward` / `C.muzzle_height` / `C.camera_tilt_deg` carry the numbers; the
  result differs per direction — 1.51 tiles north, 1.61 east/west, 0.39 south — and was
  verified against Blender's own camera projection for all 64 directions
  (`graphics/_blender/muzzle_marker.py`, agreement < 0.001 tiles) and against the
  shipped sheets (`graphics/_blender/check_beam_anchor.py`: every start pixel is on the
  gun, 0.39-1.68 tiles from the pivot).
- one **pulse** every 8 ticks: corridor hit test from the mouth along the mouth→target
  line (12 bodies, 0.82 falloff, ending exactly that turret's `range` from the centre —
  16 tiles plus its quality bonus), two
  `entity.damage()` calls per body — `fire` for 85 % of the pulse, `physical` for the
  other 15 % (the second is skipped if the first killed the body). Enemies only.
- fuel surcharge: `extra_fluid_per_pulse_hot * charge` per pulse, removed with
  `remove_fluid(amount, 1)` — positional API, like `damage()`.
- visuals: 4 stacked `rendering.draw_line` layers (haze / glow / hot / white core), a
  9-segment **boiling sheath** re-rolled every 3 ticks, a muzzle orb, a 3-tick muzzle
  flash and a burn pop on every body the beam cuts.

## Quality range

Base reach is **16 tiles**, and quality extends it through the **engine's own
multiplier**: every quality prototype carries `range_multiplier` (2.1.23: normal 1.0,
uncommon 1.1, rare 1.2, epic 1.3, legendary 1.5) and the engine applies it to a
turret's `attack_parameters.range`. So a normal melta reaches 16 tiles, a legendary
**24** — and that is both the acquisition *and* the firing range, no help needed.

That was measured, not read off the docs: with the base still at 12, a legendary melta
acquired and burned fluid on a target 19 tiles out while a normal one stopped at 13
(`docs/verification/harness/melta-range`, scene ladder). `LuaQualityPrototype` exposes
the same number as `range_multiplier`, which is what the script reads.

The mod's part is the two things the engine does not do:

| what | how |
|---|---|
| beam length | the drawn lance must equal the turret's real reach, so `control.lua` computes `C.range * quality.range_multiplier` per turret (cached in its state, refreshed on build / reconcile) and draws to that |
| the clamp | a modded quality with a silly multiplier would otherwise give a 48-tile melta; the beam stops at `C.range_max` = 24 (16 × vanilla legendary). The engine still *targets* further, so a turret handed an unreachable target re-targets the nearest reachable one (`C.range_scan_ticks`) instead of burning fluid on something it cannot cut |

`turret.quality` is read defensively: documented to answer `normal` when an entity does
not support quality, and `range_multiplier` is type-checked, so a turret with the quality
mod absent, a script-created turret, or a minified one never throws inside the tick
handler. With the quality mod disabled the whole ladder collapses to 16 tiles, which the
harness run `melta-noquality` proves.

Side note that cost an hour: the melta's `call_for_help_radius` is 40, and a turret that
starts shooting hands its target to every turret inside that radius **regardless of
range**. A turret can therefore be aiming at a biter 19 tiles away with a 16-tile beam;
that is what the re-target path above cleans up.

## Graphics

The turret is a **modelled and rendered** asset now, not a drawn sprite: the whole
emplacement (hull + cannon) is built procedurally in Blender and rendered from a
top-down orthographic camera, which is the only way to get the chunky, welded,
dented read of Factorio's own turret art.

Pipeline: `graphics/_blender/melta_render.py` (model + render) → `assemble.py`
(downsample, tone curve, baked cast shadows, sheet packing) →
`prototypes/graphics.lua` (frame geometry). `graphics/_blender/README.md` records
the contract between the scripts and the prototype.

- **hull** — static 256x256 sprite (scale 0.5 -> 3.1 tiles on screen): octagonal
  cast pedestal, layered armour wedges with welded beads, radiator stack, coolant
  drum, crate, hydraulic rams, copper fuel stubs at +-1.2 tiles (they line up with
  `fluid_box.pipe_connections`), and a bearing well with spokes so pointing the gun
  away does not expose a blank disc.
- **cannon** — 64 directions, frame 256x256, 8 files of 8 rows (256x2048, power of
  two): chunky breech with a heat-exchanger fin stack, ribbed copper heat coils with
  a glow ring between them, vented shroud, wide-bore projector mouth with a
  white-hot throat, hydraulic ram, optic block and a bent armour flap — asymmetric
  on purpose.
- **size** — the cannon's muzzle reaches 1.51 tiles from the pivot (it was 0.66):
  ~2.3x longer and ~2x fatter, which is what "too small next to base turrets" was
  about. The model is scaled 0.84 so the frame can hold the barrel at every angle.
- **pivot** — the model rotates about the world origin and the camera aims at it, so
  the pivot lands on the frame centre: `shift = {0, 0}`, no wobble in any direction.
- **wear** — chipped paint over bare metal, edge wear on convex pointiness, rust
  streaks stretched down Z, oil streaks, and grime packed into concave pointiness.
  The palette (dark steel, muted warning yellow, rust, copper) is picked to sit next
  to the vanilla gun/laser turret sprites.
- no fold/unfold strip: the cannon is always deployed, which keeps the head one sheet.

Brightness is tuned against vanilla art rather than by eye: the tone curve in
`assemble.py` maps the render's range onto the spread measured from the vanilla
turret sprites (p10 ~4, p50 ~26, p90 ~120), so the turret does not read as a
brighter or flatter object pasted into the world.

## Plumbing (pipes and sockets)

The turret drinks from a pipe, so the pipe has to *look* like it goes somewhere. It
did not: the art was replaced by a much wider hull, the ports stayed at the old
positions, and a pipe simply ran on top of the emplacement.

What the geometry actually allows — all measured, not assumed:

- A pipe is a 1-tile entity and the turret's collision box is 1.2, so the nearest tile
  a pipe can occupy is **2.0 tiles** from the turret's centre (`can_place_entity` is
  false at 1.0 and true at 2.0). The pipe's art then stops at 1.5 tiles.
- A `pipe_connection.position` **must lie inside the entity's collision box** — the
  loader rejects anything else ("PipeConnectionDefinition: position must be inside of
  entity bounding box"), so the socket can never be drawn out at the pipe's mouth;
  1.199 is the hard ceiling.
- `pipe_covers` are drawn **at the connection point, inboard of it**: vanilla's cover
  art sits 0.28-0.5 tiles inside the anchor. That makes them sockets on the machine's
  wall, not sleeves out in the gap.
- Turret fluid boxes **rotate with the entity**: rotating the turret moved an
  asymmetric port set by 0.15 tiles and would slide the sockets off their pipes. Hence
  one symmetric number, `C.pipe_reach = 1.12`, for all four sides.
- Vanilla pipe covers (`pipecoverspictures()`) come from base with both diffuse and
  shadow layers, `priority = "extra-high"` — above the hull's `"high"`, so no
  z-fighting and no re-ordering needed.

So the ports are `+-1.12` tiles on the four axes and `flow_direction` is left at the
engine default (`"input-output"`, verified at runtime by reading
`get_fluid_box_pipe_connections`) like the vanilla flamethrower turret.

### Why the pipes still looked disconnected, and what actually fixes it

`pipe_covers` is **not** the connected-port picture. 2.1 splits the two cases:

| field | drawn when |
|---|---|
| `pipe_picture` | a pipe *is* connected on that side — this is the machine's own stub (vanilla's `assembling-machine-2-pipe-N/E/S/W`) |
| `pipe_covers` | nothing is connected on that side — a blanking cap |
| `always_draw_covers` | defaults to **true when `pipe_picture` is absent**, i.e. covers are then drawn on every side |

The 0.4.0 build set only `pipe_covers`, so the engine drew vanilla's *cap* — whose art
sits 0.28-0.5 tiles inboard of the anchor, i.e. at 0.88-1.04 tiles from the centre —
on all four sides whether a pipe was there or not: a collar lying on the deck, half a
tile short of the pipe, and no port art at all where the pipe arrived.

The fix is the native one and it is where the "render extra pipe models" instinct was
right: the mod now renders its own port (`graphics/_blender/pipe_port.py`, one model:
mount pad, neck with ribbed strain relief, bolted clamp collar, socket mouth with a
bolt ring) in four orientations, and supplies it as **`pipe_picture`** for connected
sides and as a blanked-off variant of the same port for **`pipe_covers`**.
`always_draw_covers = false` makes the distinction explicit.

- Frame centre = the connection point, `scale = 0.5` on a 128 px sprite (64 art px/tile,
  the same density as the rest of the mod's art), so `C.pipe_reach` decides where the
  socket sits and nothing guesses a `shift`.
- One model, four renders through the same 51° camera: the projection lands it at a
  different screen distance per side (the pipe's own art is asymmetric too — its near
  edge is 1.52 tiles north but 1.19 south). `C.pipe_shift` carries the per-side
  correction, screen tiles: south `+0.18` and west `-0.22`, because on those sides the
  clamp collar otherwise hid behind the hull's deeper rim (south 1.28) or the west
  vent block, and only the mouth showed — which read as a cap sitting on the pipe.

Measured with `python graphics/_blender/pipe_join.py --check`, which composites the
hull, the port and the real vanilla pipe sprite at 64 px/tile (Factorio zoom 2.0) and
fails if the port does not reach the pipe or if any bare ground shows in between:

| side | port reaches | pipe's near edge | overlap | bare ground between |
|---|---|---|---|---|
| north | 1.98 | 1.52 | +0.46 | 0 |
| east | 1.89 | 1.50 | +0.39 | 0 |
| south | 1.77 | 1.19 | +0.58 | 0 |
| west | 2.01 | 1.52 | +0.50 | 0 |

The capped sprite is checked the same way (`cap px`: pixels the blanking plate adds over
the open port, 72-160 per side) so "no pipe connected" cannot silently revert to looking
like an open socket.

In game (Steam build, 15 screenshots in `docs/verification/in-game-pipes/`): all four
pipes meet the turret with no bare floor and a visible socket, the three unconnected
sides of a one-sided turret show blanked plates, and the straight / L / T / cross
junctions plus a dead end all render clean — the dead end capped, not hollow.


Measured join — distance from the turret centre to the hull's own silhouette vs to the
pipe's near edge, at 64 px/tile, measured in a +-0.5 tile band around each pipe axis
(that band is the only part of the hull a pipe can meet):

| side | hull silhouette | pipe's near edge | ground gap |
|---|---|---|---|
| north | 1.38 | 1.50 | **+0.12** |
| east | 1.64 | 1.50 | −0.14 (pipe overlaps the hull) |
| south | 1.28 | 1.19 | −0.09 (overlap: the pipe's raised rim projects over the skirt) |
| west | 1.53 | 1.50 | −0.03 |

The south and east pipe ends are drawn *closer* than 1.5 tiles because the vertical
pipe sprite's raised rim, and the baked cast shadow, project inboard on screen — that is
the art, not a port placement.

North used to be +0.42 and was the one side that read as unattached. It was not a
plumbing problem: a `pipe_connection` cannot sit outside the 1.199 collision box and the
cover art draws inboard of the anchor, so no socket sprite can reach into that gap. The
cause was the **art**: `melta-turret-base.png` is rendered through a 51° pitched
orthographic camera, so the round hull's footprint is drawn squashed in Y — 3.05 tiles
wide but only ~2.1 tall where vanilla turret hulls run about 1.2 wide-to-tall. So
`assemble.py` now de-squashes the base layer vertically (`BASE_DESQUASH_Y = 1.26`,
applied about the frame centre, so `shift = {0, 0}` and the head stays concentric). Only
the base layer: the 64 head frames are not resampled, so the pivot is untouched.

For reference, vanilla `assembling-machine-2` (same ±1.2 collision box, so pipes also sit
2.0 tiles out) leaves **+0.24** on its north side — measured the same way, in
`docs/pipe-sockets/reference-vanilla.png`. Ours is now tighter than vanilla's.

`docs/pipe-sockets/` holds the comparison that picked 1.12 (sink / flush / float /
no-covers), the four side views, the north before/after panel, the vanilla reference and
`gaps.json` (the measured table), with a README that says exactly how they were made and
the one command that re-measures them:
`python graphics/_blender/pipe_sockets.py --check`.

## Engine facts this leans on (and the ones that bit)

- `LuaEntity::shooting_state` **throws** on turrets ("Entity is not character") — use
  `shooting_target`. A turret keeps *aiming* with no fuel at all, so the fuel gate has to
  be script-side.
- `LuaEntity::orientation` on a turret is the **weapon's** smooth orientation (0 = north,
  0.25 = east), not the building's facing — that is what makes a rotation gate possible
  without simulating the head's turn. The head turns in whole `rotation_speed` steps
  (0.006 = 2.16 deg/tick here) and snaps onto the target, and the engine fires the tick
  after it gets there.
- `remove_fluid` / `damage` are **positional** APIs; calling them with a table errors.
- `rendering.draw_light` needs a sprite and `__core__/...` is not resolvable at runtime
  ("Unknown type __core__") — circles instead.
- Beams cannot pierce; the stream cannot beam. Both halves of the engine are needed for
  this weapon, and neither is enough on its own.
- Script-created entities raise no event, so the turret registry self-repairs every 600 ticks.

## Fuels

| fluid | damage | beam | how you get it |
|---|---|---|---|
| light-oil | 1.00x | orange, warm white core | straight from the refinery |
| petroleum-gas | 0.85x | pale blue | gas cracking, leaner burn |
| melta-fuel | 1.60x | green-white | chemistry: 20 light oil + 2 uranium-238 + 1 sulfur -> 100 |
| lilys-napalm-mix | 1.35x | deep red | Lily's Incendiaries |

Burn rate: 7.5 shots/s x 2.5 units = ~19/s cold, plus the script surcharge (3.8/pulse at full
charge) = **~47/s held at full intensity**. The 200-unit buffer is 4-10 s of beam, so a short
feed hiccup does not kill the turret. Cost note: 47/s of light oil is most of a refinery's
light-oil output -- that is deliberate (it is a burst weapon, and the enriched fuel is 5x more
units per oil at 1.6x damage), but `C.fluid_consumption` / `C.extra_fluid_per_pulse_hot` are the
two numbers to turn down if it feels like a pipe into the void.

## Sound

`sound/_generator/melta_sounds.py` synthesises the whole set from noise spectra (random phase ->
circular filters -> inverse FFT, so the loop is seamless):

- `melta-burn.ogg` -- 2 s loop: low rumble, a band-passed roaring body with a 7 Hz flutter, and a
  thin sizzle with crackle ticks on top. Measured 63 % of its energy sits in 0.5-3 kHz, ~2.4 kHz
  centroid: air being pushed, not white hiss.
- `melta-start.ogg` -- 0.45 s pressure build-up (rising jet + falling thump).
- `melta-stop.ogg` -- 0.6 s decay, sizzle lingering.

They are wired as the turret's `cyclic_sound` (begin / middle loop / end), so the jet runs for as
long as the trigger is held and stops with the beam. The engine cannot pitch a sound per entity,
so the spin-up is carried by the visuals, not the audio.

**Loudness (measured, not guessed).** The generator normalises by *peak*, and this noise bed has a
25 dB crest factor, so the loop shipped 12.7 dB quieter than a vanilla flamer loop even though its
`volume` was close to vanilla's:

| | file RMS | volume | in the mix | file peak |
|---|---|---|---|---|
| before | −26.4 dBFS | 0.45 | −33.3 dBFS | −1.4 dBFS |
| now | −15.2 dBFS | 0.70 | −18.3 dBFS | −1.6 dBFS |
| reference: flamethrower-turret-mid | −13.2 dBFS | 0.5 | −19.2 dBFS | −2.3 dBFS |
| reference: gun-turret gunshot | −17.6 dBFS | 0.4 | — | −0.5 dBFS |

That is +15 dB in the mix: level with a vanilla flamer loop, still below gun-turret spam, and with
−4.7 dBFS of headroom per voice so two loops cannot sum past full scale. `aggregation.max_count =
2` on all three sounds is the anti-clipping clamp, and `audible_distance_modifier` 1.3–1.4 widens
the falloff so it carries further than it did.

The shipped `melta-burn.ogg` is the generator's output run through a limiter that raises the RMS
without touching the loop point (causal, no tail), same 22050 Hz mono Vorbis:

```bash
ffmpeg -i melta-burn.ogg -af "volume=20dB,alimiter=limit=0.80:attack=3:release=60:level=disabled" \
       -ac 1 -ar 22050 -c:a libvorbis -q:a 6 out.ogg
```

Re-running `melta_sounds.py` restores the quiet version — re-apply that command, or add the gain to
the generator, before shipping a rebuild.

## Research and recipes

| thing | detail |
|---|---|
| technology | `melta-turret`, prereqs `laser-turret` + `advanced-oil-processing`, 150 x (automation, logistic, military, chemical) at 30 s |
| unlocks | the turret recipe and the fuel recipe |
| turret recipe | 25 steel-plate + 20 iron-gear-wheel + 15 advanced-circuit + 5 processing-unit, 6 s |
| fuel recipe | chemistry: 20 light-oil + 2 uranium-238 + 1 sulfur -> 100 enriched melta-fuel, 4 s, productivity allowed |
| fuel value | engine burns 0.15 per shot; a shot is every 8 ticks, so ~1.1/s cold and ~2.3/s white-hot with the surcharge |

## Living with her other mods

Two tables in `constants.lua` are the whole integration surface, and both stages read them:

- `C.fuels` — any fluid listed here that exists in the install can be piped into the turret
  and sets a damage multiplier (applied by the script, because the engine's own
  `fluids[].damage_modifier` only scales its invisible 1-damage stream). The fluid box is
  **unfiltered** for this reason, exactly like the flamethrower's.
- `C.recipe_hooks` — an item + amount + technology. If that item exists, it is added to the
  turret recipe; if the technology exists too, it becomes a prerequisite. Absent item or
  technology = the hook silently does nothing.

What that gives today:

| installed | effect |
|---|---|
| vanilla | melta-fuel only; recipe and tech as above |
| `? lilys-incendiaries` | `lilys-napalm-mix` pipes straight in and hits 1.35x with a deep red beam (verified: 56 -> 75.6 damage per pulse) |
| `? wanderer` | nothing yet (the mod has no items); the moment it defines `iridium-plate` + `iridium-processing` the recipe gains 10 iridium and the tech requires that research (verified with a stub mod) |

`data-updates.lua` prints one line per applied integration into `factorio-current.log`, so a
load log answers "why is napalm not burning" without guesswork.

This mod does not gate itself against your other mods: the turret item, recipe and technology are
ordinary prototypes under stable names, so Incendiaries or Wanderer can rewrite the recipe, add
prerequisites or move the unlock from **their** data-updates and it simply wins (they load after
this mod alphabetically, so their edit is the last word). The hooks here are only the version that
works without anyone touching us.

## Known simplifications

- The beam is flat: it passes over walls, cliffs and your own base (it damages enemies
  only, so there is **no friendly fire** — verified with a friendly wall in the corridor:
  wall hp unchanged, biter behind it cooked).
- Quality affects the turret like any other; no per-quality beam scaling.
- The icon, the placing item, the technology and `thumbnail.png` are all rendered from the
  turret model (`graphics/_blender/render_icons.py`, `assemble_icons.py`). Honest limit: the
  2x2 emplacement is wider than it is tall and its muzzle stops a hair short of the hull rim
  (1.51 vs 1.56 tiles), so the icon reads as a compact industrial emplacement rather than as
  vanilla's long-barrel silhouette; at 32 px the plate seams are denser than vanilla's icons.
  The fix for that is a model change (fewer, larger plates), not an icon pass.

## Where to retune

`constants.lua` only — read by both stages. The knobs that decide the feel:
`damage_cold`, `damage_hot`, `spin_up_ticks`, `pierce_falloff`, `sheath_segments`
(lower = tidier beam, higher = wilder plasma), `fluid_consumption`.
