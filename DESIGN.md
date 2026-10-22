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
| hull | rocket turret (2x2), base art untouched | her call: reuse the rocket turret |
| head | purpose-drawn 64-direction emitter sheet | see **Graphics** below |
| health | 1200 | an emitter, not an armoured box (rocket turret: 1500) |
| range | 12 tiles | laser 24, rocket 36: the melta has to be near the wall |
| pulse rate | 8 ticks (7.5/s) | fast enough that discrete pulses read as one beam |
| damage / pulse | 14 cold → 56 hot | 105 → 420 dps single target, before pierce |
| spin-up | 150 ticks (2.5 s) | one biter wave is not enough time to peak |
| spin-down | 60 ticks (1 s) | it cools fast, so holding a line is the skill |
| pierce | 12 bodies, 0.82 falloff each | front rank eats it, back ranks eat 82 % of the one in front |
| damage type | `thermal` (new) | nothing in vanilla resists it — that is the fantasy |
| fuel | light-oil 1.0x, petroleum-gas 0.85x, enriched melta-fuel 1.6x, incendiaries napalm 1.35x | each fuel sets damage *and* beam colour; see the fuel table below |
| burn rate | 2.5 units/shot engine-side + 3.8 per pulse at full charge | ~19/s cold, ~47/s white-hot |

Derived: a behemoth biter (3000 hp) dies in ~5 s of full-intensity fire.

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
- `thermal` damage type, `melta` ammo category, turret recipe, technology.

**Runtime (`control.lua`)**
- `charge` per turret: +1/150 per tick while a target is held *and* the turret has fluid,
  −1/60 per tick otherwise.
- one **pulse** every 8 ticks: corridor hit test along the beam axis (12 bodies, 0.82
  falloff), `entity.damage()` with the `thermal` type. Enemies only.
- fuel surcharge: `extra_fluid_per_pulse_hot * charge` per pulse, removed with
  `remove_fluid(amount, 1)` — positional API, like `damage()`.
- visuals: 4 stacked `rendering.draw_line` layers (haze / glow / hot / white core), a
  9-segment **boiling sheath** re-rolled every 3 ticks, a muzzle orb, a 3-tick muzzle
  flash and a burn pop on every body the beam cuts.

## Graphics

Not a recolour of the rocket pod. `graphics/_generator/melta_head.py` draws a new head
procedurally at 4x supersampling and writes a sheet that drops straight into the vanilla
rig (frame 160x164, 64 directions, 3 files of 22/22/20 rows, shift `by_pixel(0, -8.5)`,
scale 0.5), so the base/hull stays the rocket turret's own art:

- everything on the head is drawn in a **barrel-aligned frame**, so the barrel, collar,
  cooling rings, heat-sink vanes and sight glass all rotate together;
- the housing is rotation-symmetric and drawn in **screen space**, so a rigid turn does not
  squash it;
- painter's order flips at the camera: pointing away → dome over barrel, pointing toward →
  barrel over dome, which fixes the south-facing junction;
- mounting plate + contact shadow so it sits on the hull instead of floating;
- no fold/unfold strip: the emitter is always deployed, which keeps the head one sheet.

`preview.png` (review only, never loaded) shows the turret at rest and at three beam
intensities.

## Engine facts this leans on (and the ones that bit)

- `LuaEntity::shooting_state` **throws** on turrets ("Entity is not character") — use
  `shooting_target`. A turret keeps *aiming* with no fuel at all, so the fuel gate has to
  be script-side.
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
- `thumbnail.png` is still the radar-artillery leftover from the stub.

## Where to retune

`constants.lua` only — read by both stages. The knobs that decide the feel:
`damage_cold`, `damage_hot`, `spin_up_ticks`, `pierce_falloff`, `sheath_segments`
(lower = tidier beam, higher = wilder plasma), `fluid_consumption`.
