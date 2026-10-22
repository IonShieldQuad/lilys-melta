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
| fuel | 40 melta-fuel per 10 light oil; engine burns 0.15/shot plus a script surcharge | ~1 light oil per 2.7 s of full-intensity beam |

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
