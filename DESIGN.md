# Melta turret — design

A short-ranged thermal emitter that drinks liquid fuel and cuts a line through a crowd.
Everything below is implemented and verified in-game (headless create + benchmark with a
scripted harness: spin-up, pierce falloff, fluid burn, dry-turret gate, friendly fire,
render-object leaks).

## The three things it has to feel like

1. **A lance, not a squirt gun.** One beam that starts at the muzzle and runs its whole
   16 tiles, cutting every body on the line instead of stopping at the first one.
2. **It has to warm up.** Tapping fire is a thin orange line; holding it on a target for
   ~2.5 s turns it into a boiling white-hot column at 1.75x the damage.
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
| damage / pulse | 32 cold → 56 hot (1.75x) | 240 → 420 dps single target, before pierce; cold is level with a gun turret on uranium rounds (240), hot is 1.76-2.02x it across the research tiers. Scales with the fire damage and turret firing-speed research — see the balance note below |
| spin-up | 150 ticks (2.5 s) | one biter wave is not enough time to peak |
| spin-down | 60 ticks (1 s) | it cools fast, so holding a line is the skill |
| pierce | 12 bodies, 0.82 falloff each | front rank eats it, back ranks eat 82 % of the one in front |
| damage type | `fire`, with 15 % of each pulse dealt as `physical` | fire is what a melta is (and fire-vulnerable biters take it in full); the physical slice is the mass of the stream, so a fire-immune target still takes 15 % instead of nothing |
| fuel | light-oil 1.0x, petroleum-gas 0.85x, enriched melta-fuel 1.6x, incendiaries napalm 1.35x | each fuel sets damage *and* beam colour; see the fuel table below |
| burn rate | 2.5 units/shot engine-side + 3.8 per pulse at full charge | ~19/s cold, ~47/s white-hot |

Derived — per pulse at full intensity, base damage 56 (47.6 fire + 8.4 physical), and what
survives each biter's resistances (none of them resist fire; only physical is resisted):

| target | physical resistance | lands per pulse | note |
|---|---|---|---|
| small biter | none | 56.0 (47.6 + 8.4) | unchanged |
| medium biter | decrease 4, 10 % | 55.2 (47.6 + 7.56) | flat ignored — only the 10 % percentage is left |
| big biter | decrease 8, 10 % | 55.2 | same |
| behemoth biter | decrease 12, 10 % | 55.2 | was 47.6 before the flat-armour bypass |
| any 100 % fire-resistant target | — | 8.4 (physical only) | was 0 before the split |

So the split now costs almost nothing: the only thing the physical slice loses is the
target's *percentage* resistance, i.e. 1.4 % of the pulse against the whole biter line,
where flat armour used to eat up to 15 % of it. Flat armour is bypassed by handing the
engine `damage + decrease` (it always resolves `max(0, amount - decrease) * (1 -
percent/100)`); percentage resistance is deliberately respected. Turn
`C.pierce_flat_armor` off to get the old behaviour back, and `C.physical_share` down if the
physical slice ever stops earning its two `damage()` calls per body.

Measured headlessly at 7.5 pulses/s, light oil, four dummies that differ only in
resistance (full charge): 56.00 unarmoured, 50.38 on a `decrease 12, percent 10` target
(90.0 %, exactly its percentage), 28.00 on a 50 % target (50 % exactly), 8.38 on a
fire-immune one (the physical slice alone) — `docs/verification/balance-verification.md`.

Derived: a behemoth biter (3000 hp) dies in ~8 s of full-intensity light-oil fire (377.8
dps after its 10 % resistance), and in ~5 s on melta-fuel (1.6x).

## Research scaling and the comparison turrets

The beam's damage is dealt by `control.lua`, so no technology reached it: before this
change the turret sat at 240/420 dps while a gun turret went 240 → 1632 and both other
turrets pulled ahead for free. It now reads the same research a gun turret does, **from the
engine's own accumulators** — `force.get_ammo_damage_modifier("flamethrower")` or
`force.get_turret_attack_modifier("melta-turret")` for damage (whichever is larger, so each
researched level counts exactly once), and `force.get_gun_speed_modifier("melta")` for the
pulse clock, whose levels `data-updates.lua` copies from the bullet line. Damage is then
compounded by `C.research_damage_exponent = 1.5`.

The engine, not a hand sum, is what makes the *infinite* tier work: `refined-flammables-7`
is `max_level = "infinite"` and pays +0.2 per level, and a hand sum of `effect.modifier`
pays that once no matter how deep the research goes (that was 0.6.0's bug — ten extra levels
bought 0.2, not 2.0). `data-updates.lua` also mirrors the fire line's `turret-attack` half
onto `melta-turret`, so the turret appears in those technologies at all; the melta's own
engine-side stream is zeroed, so the engine cannot multiply anything the script did not
already account for. Measurements: `docs/verification/research-scaling.md`.

| tier | fire / rate | melta cold dps | melta hot dps | gun turret (uranium) |
|---|---|---|---|---|
| 0 | +0 % / +0 % | 245 | 429 | 240 |
| 1 | +20 % / +10 % | 353 | 618 | 319 |
| 2 | +40 % / +30 % | 519 | 909 | 449 |
| 3 | +60 % / +50 % | 729 | 1275 | 706 |
| 4 | +90 % / +80 % | 1131 | 1980 | 1106 |
| 5 | +120 % / +110 % | 1637 | 2866 | 1632 |

Cold holds parity with the gun turret at every tier (1.00x-1.16x) despite 16 tiles of reach
and a fluid bill; hot is 1.76x-2.02x the gun turret, which is what pays for the short range.
The tesla turret is the other comparison: 60 dps on one body, up to ~600 across its chain,
against the melta's 12-body piercing line (32 + 0.82 falloff ≈ 1290 dps cold across a full
line). Method, probe and the before/after measurement:
`docs/verification/balance-verification.md`.

## Asteroids (space age)

Rocks are the one target class the fire beam cannot touch: every asteroid prototype gets
`percent = 100` on every damage type it does not list, and `fire` is listed for none of
them — so 85 % of a pulse is zero, and only the 15 % physical slice is in play. Big and
huge asteroids also carry a POSITIVE 2000 / 3000 physical `decrease`
(`data/space-age/prototypes/entity/asteroid.lua`), which swallowed that slice whole:
measured before either fix, a small rock took 11 pulses, a medium 31, and big and huge
never killed (236 pulses for 0.14 hp). The flat-armour bypass now cancels that
`decrease`, so the slice does land (7.56 per hot pulse on every rock tier, 0.4 % of a big
rock's health) — still nothing next to the rock's own damage output, which is why rocks
still need a channel of their own.

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
- visuals: a **soft sprite core** (two additive layers, whitened inward) inside 3 additive
  glow layers, a 6-segment **boiling sheath** re-rolled every 3 ticks (its last 2 rolls run
  past the tip so the end frays), a dissolving **spray plume** carried past maximum reach, a
  muzzle orb, a muzzle flare + blast cone, an impact flare on the nearest cut body and a
  burn pop on every body the beam cuts. Every object is a sprite on ONE render layer
  (`C.beam_layer`) — `rendering.draw_line` has no `render_layer` field at all, so a core
  drawn with it lands on a fixed engine layer and disagrees with the rest of the lance
  under any mod that adds smoke or weather.
- spin-up gauge: 5 additive lights around the hull deck that fill in sequence with
  `charge` (2.5 s cold → white hot) and empty again as it cools, so the ramp is readable
  as state instead of only as a thicker beam. They are placed on an ellipse
  (`cos(tilt)` squash, `C.spin_led_lift` up-screen) because the camera is pitched.
- art placement: both sprites carry `C.sprite_shift` (half a tile DOWN the screen) so the
  hull stands on its own tile instead of the tile boundary behind it; the engine-drawn
  pipe stubs do NOT move (they belong to the tile grid, not to the art). `muzzle_point`
  adds the same shift, so the lance leaves the mouth the player can see.

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
  two): chunky breech, three fat ribbed heat rings with a dim glow collar between
  them, vented shroud, and a WH40K-style melta projector at the front — a fat
  cylinder with a ring of six radial vents over a hollow, warm bore, closed by a
  hot-metal lip. No flat face anywhere on the barrel: that plate was the "unfinished"
  read. The fluid hardware hangs off the receiver — a brass compressor drum with a
  finned body and intake on the right, a cast turbine housing with an exhaust stack on
  the roof, a banded brass pressure tank on the left, and copper hard lines carrying
  fuel from the tank and the compressor into the breech. Every one of them is sized
  for the sprite (>= 0.4 tiles across) rather than for the render, because 1 tile is
  32 art px and anything thinner downsamples to noise. Hydraulic ram, optic block and a
  bent armour flap keep it asymmetric.
- **size** — the cannon's muzzle reaches 1.51 tiles from the pivot (it was 0.66):
  ~2.3x longer and ~2x fatter, which is what "too small next to base turrets" was
  about. The model is scaled 0.84 so the frame can hold the barrel at every angle.
- **pivot** — the model rotates about the world origin and the camera aims at it, so
  the pivot lands on the frame centre: `shift = {0, 0}`, no wobble in any direction.
- **wear** — chipped paint over bare metal, edge wear on convex pointiness, rust
  streaks stretched down Z, oil streaks, and grime packed into concave pointiness.
  The palette is picked off the vanilla sprites rather than by eye: a mid-value warm
  gunmetal body (mean 79, vanilla gun head 75), near-black recesses, brass and copper
  on everything that carries fluid, and a warm orange emissive used *only* on the
  vent bores, the muzzle lip and the gauge lights. The hull keeps its own, darker
  values (mean 61, vanilla flamethrower hull 56-60) because vanilla turret bases sit a
  step below their heads.
- **lighting** — three emissive softboxes (warm key upper-left so the baked cast
  shadow falls lower-right, cool fill right, cool rim behind). Lamp energy is ignored
  by Cycles in this Blender build, so the rig is emissive geometry and the plates are
  hidden from camera rays; `check_rig_in_frame()` fails loudly if one would be
  photographed.
- no fold/unfold strip: the cannon is always deployed, which keeps the head one sheet.

Brightness is tuned against vanilla art rather than by eye: the tone curve in
`assemble.py` is quantile-matched to `gun-turret-shooting-1.png` and refit with
`fit_final.py` whenever the model or the rig changes (it is not a constant — the
curve fitted to the old dark model sent the new render to p90 234, which is what read
as a white plate at the muzzle). The assembled head now measures p50 63, p75 116,
p90 177, mean 79 with 0.00% pure-white pixels, against vanilla gun head 60 / 105 / 160
/ 75. `palette_vs_vanilla.py` prints that table, and `check_sheets.py` audits the
sheet geometry: frame size, clipping, pivot radius, and that the 64 directions walk
one closed loop.

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

### The fix: the pipe hardware cubeine's combustion center already ships

`pipe_covers` is **not** the connected-port picture. 2.1 splits the two cases:

| field | drawn when |
|---|---|
| `pipe_picture` | a pipe *is* connected on that side — the machine's own stub |
| `pipe_covers` | nothing is connected on that side — a blanking cap |
| `always_draw_covers` | defaults to **true when `pipe_picture` is absent**, i.e. covers are then drawn on every side |

0.4.0 set only `pipe_covers`, so vanilla's *cap* — whose art sits 0.28-0.5 tiles inboard
of the anchor — was drawn on all four sides whether a pipe was there or not. 0.5.x
replaced that with the mod's own rendered port plus a blanked-off variant of it, and hit
the same wall one generation further on: a cap has to be drawn at the connection point
(1.12), while the hull's silhouette starts at 1.28 north / 1.53 west / 1.64 east, so
**every unused side showed a plate floating half a tile off the deck** — visible in
`docs/verification/in-game-pipes/05-capped-ports.jpg` from 0.5.1.

The configuration that works is not a render at all: it is what `lilys-cubeine`'s
combustion center already ships, copied almost verbatim.

```lua
pipe_picture             = <space-age electromagnetic-plant pipe pictures>
draw_only_when_connected = true
secondary_draw_orders    = {north = -1, west = -1, east = -1}
pipe_covers              = nil          -- whenever space-age is present
```

- `draw_only_when_connected` is literally "only if the connector is actually used": a
  side with no pipe draws nothing, so an unused port is bare hull with no cap to float.
- `secondary_draw_order = -1` draws the stub behind the hull, so its inboard half is
  hidden and what reads is the part that pokes past the rim — a pipe running into the
  housing rather than a collar lying on the deck.
- The art is space-age's `electromagnetic-plant-pipe-{N,E,S,W}`, **untinted**: the same
  grey metal as every pipe the player builds. (cubeine's own combustion center uses
  exactly these pictures, also untinted.)
- `pipe_connections` stay at `C.pipe_reach = 1.12` on all four sides. Positions are the
  one part of that config that does *not* carry over: cubeine's connections sit at ±2 on
  a 5x5 reactor, and a connection cannot move out to meet the pipe anyway (1.199 is the
  hard ceiling).

A base-only install gets vanilla `pipecoverspictures()` covers instead — the same thing
the vanilla flamethrower turret uses — because the electromagnetic-plant art does not
exist without the expansion. The mod detects `mods["space-age"]` at the data stage and
picks the branch itself.

### Evidence

Real frames from one GUI run (Steam build 87750, 2.1.23), `docs/verification/in-game-pipes/`,
taken by the `melta-pipes` harness:

| shot | what it shows |
|---|---|
| `00-vanilla-ref` | vanilla `assembling-machine-2` with a pipe on four sides — the yardstick for what a vanilla `pipe_picture` join looks like (it leaves a hairline seam too) |
| `02-melta-four-way`, `03/04/12/13-join-*` | all four joins on a fully plumbed turret: pipe, stub, hull, no bare floor |
| `05-capped-ports`, `14-capped-port-north` | a turret plumbed on one side: the other three sides are **bare hull**, no hardware at all |
| `01-overview`, `15-overview-close` | the whole pad, so the joins can be judged at normal zoom |

Before/after on the same scene: the 0.5.1 frames (in the same folder) draw a ringed cap
on every side, connected or not; these draw the stub only where a pipe arrives. The
in-game pass also re-confirms the plumbing still works headlessly — pipes on all four
sides are connection targets, and a filled pipe hands fluid over on the next tick (see
`docs/pipe-connections/`, unchanged by this: no prototype moved except the pipe art
fields).

The measured hull/pipe geometry above is unchanged and still the reason the stub cannot
simply be moved outward: `docs/pipe-sockets/` (superseded as art evidence — its
composites still draw vanilla covers — but `gaps.json` is the measurement) and
`python graphics/_blender/pipe_sockets.py --check` remain valid as numbers.

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
circular filters -> inverse FFT, so the loop is seamless). Every cue is built from three layers,
and each layer is placed in a different part of the spectrum so that "is it there?" is a
measurement:

| layer | synthesis | band |
|---|---|---|
| pressure release | 2600/6800 Hz burst on sample 0, 1.5 ms attack, 40 ms decay, plus a falling 150 -> 62 Hz thump for mass | first 5 ms, 2-6 kHz |
| sizzle / roar | 420/1150/2800 Hz noise body with 7 Hz flutter, a 5.2/9 kHz hiss, 7-12 molten spatter ticks | 120 Hz - 16 kHz |
| turbopump | harmonic stack (1, 2, 3, 4, 6 x) climbing 45 -> 92 Hz over 0.20 s, 11x/17x blade whine, 9 Hz wobble | 20-120 Hz |

- `melta-fire-1/2/3.ogg` -- 0.62 / 0.70 / 0.66 s shots, three variations (pump pitch, sizzle level
  and spatter count differ; cross-correlation between them is 0.17-0.27, and they are level-matched
  within 0.15 dB). Onset is 0.2-0.45 ms from sample 0, so there is no perceptible firing delay.
- `melta-burn.ogg` -- 2 s loop at the same three layers with the pump at running speed, so the
  ignition hands over to the sustain with no step. Seam continuous: |last - first| is 0.016 against
  a mean sample step of 0.046.
- `melta-stop.ogg` -- 0.6 s shut-down with the rotor winding down 88 -> 42 Hz.

They are wired as the turret's `cyclic_sound`: the three variations are `begin_sound.variations`,
`melta-burn.ogg` is `middle_sound`, `melta-stop.ogg` is `end_sound`. Not `attack_parameters.sound`:
that retriggers on every 8-tick pulse, i.e. 7.5/s, so a 0.65 s cue would stack five deep and smear.
`begin/middle/end` is the model vanilla uses for a held stream (the flamethrower turret), and
`allow_random_repeat` defaults to false, so consecutive ignitions pick different files. The engine
still cannot pitch a sound per entity, so the pump spin-up lives in the cue itself rather than in
the audio engine.

**Loudness (measured, not guessed).** The generator normalises by *RMS*, not peak: a noise bed like
this has a ~13 dB crest factor, and peak-normalising it was how an earlier build shipped 12.7 dB
quieter than a vanilla flamer loop with a `volume` that looked right. Numbers come from decoding the
shipped OGGs (`docs/verification/harness/sound_measure.py`):

| cue | file RMS | volume | in the mix | file peak |
|---|---|---|---|---|
| melta-fire-1/2/3 | −15.4 dBFS | 0.70 | −18.5 dBFS | −3.3 dBFS |
| melta-burn (loop) | −15.3 dBFS | 0.70 | −18.4 dBFS | −4.4 dBFS |
| melta-stop | −19.6 dBFS | 0.70 | −22.7 dBFS | −5.7 dBFS |
| reference: flamethrower-turret-start | −13.2 dBFS | 0.5 | −19.2 dBFS | −1.2 dBFS |
| reference: flamethrower-turret-mid | −13.7 dBFS | 0.5 | −19.7 dBFS | −2.4 dBFS |
| reference: gun-turret gunshot | −17.9 dBFS | 0.4 | −25.9 dBFS | −0.8 dBFS |
| reference: laser turret shot | −20.2 dBFS | 0.5 | −26.2 dBFS | −3.6 dBFS |

So the melta is ~0.8 dB above the flamethrower turret's igniter and ~7 dB above the gun and laser
turrets: the heaviest weapon in the comparison, which is what a pressure weapon should be.

**Clipping budget.** Peak is the number that decides clipping, and the encoder is where it moves:
libvorbis overshoots a sharp transient by 1.5-3 dB, so the generator now re-encodes until every cue
*decodes* at or under −3 dBFS (that loop caught files that were safe before encoding and decoded at
−1.4 dBFS). Two voices of any variations 0-40 ms apart peak at −1.4 dBFS, and `aggregation.max_count
= 2` on all three slots is what keeps it at two; `progress_threshold = 0.35` on the ignition hands
its slot back once the cue is a third through, so a second turret's ignition is never dropped by the
first one's tail.

There is no manual mastering step any more -- no ffmpeg limiter command to re-apply after a rebuild.
`melta_sounds.py` is the whole pipeline: synthesise, RMS-match, soft-limit, encode, then gate the
decoded file on peak, loudness, per-layer band balance, sample 0 near zero, tail to silence and loop
seam continuity, and fail loudly if any of it regresses.

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
