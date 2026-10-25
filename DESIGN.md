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
| range | 12 tiles | laser 24, rocket 36: the melta has to be near the wall |
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
  target and only fires when the head is within `C.aim_tolerance` (0.006 turns = 2.16 deg
  = one `rotation_speed` step, which is the rule the engine itself fires on). While the
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
  line (12 bodies, 0.82 falloff, ending exactly `C.range` from the turret centre), two
  `entity.damage()` calls per body — `fire` for 85 % of the pulse, `physical` for the
  other 15 % (the second is skipped if the first killed the body). Enemies only.
- fuel surcharge: `extra_fluid_per_pulse_hot * charge` per pulse, removed with
  `remove_fluid(amount, 1)` — positional API, like `damage()`.
- visuals: 4 stacked `rendering.draw_line` layers (haze / glow / hot / white core), a
  9-segment **boiling sheath** re-rolled every 3 ticks, a muzzle orb, a 3-tick muzzle
  flash and a burn pop on every body the beam cuts.

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
