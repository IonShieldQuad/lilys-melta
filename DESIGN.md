# Melta turret — design

A short-ranged thermal emitter that burns fuel and cuts a line through a crowd.
Everything below is implemented and verified in-game (headless create + benchmark
with a scripted harness: charge ramp, pierce falloff, fuel burn, fuel gate, no
render-object leaks).

## The three things it has to feel like

1. **A lance, not a squirt gun.** One continuous beam, thin at the muzzle and
   wider with heat, that goes *through* the front rank instead of stopping at it.
2. **It has to warm up.** Tapping fire is a weak orange line; holding it on a
   target for ~2.5 s turns it white-hot and roughly quadruples the damage.
3. **It costs something.** Fuel, not electricity — a turret you feed, and a hot
   beam burns about twice the fuel of a cold one.

## Numbers

| thing | value | why |
|---|---|---|
| hull | rocket turret (2x2), heat-tinted pod | her call: reuse the rocket turret, different gun reading |
| health | 1200 | an emitter, not an armoured box (rocket turret: 1500) |
| range | 12 tiles | laser 24, rocket 36. It has to be near the wall |
| pulse rate | 8 ticks (7.5/s) | fast enough that discrete pulses read as one beam |
| damage / pulse | 14 cold → 56 hot | 105 → 420 dps single target, before pierce |
| spin-up | 150 ticks (2.5 s) | one biter wave arriving is not enough time to peak |
| spin-down | 60 ticks (1 s) | it cools fast, so holding a line is the skill |
| pierce | 12 bodies, 0.82 falloff each | front rank eats it, back ranks eat 82 % of the one in front |
| damage type | `thermal` (new) | nothing in vanilla resists it — that is the fantasy |
| fuel | 1 cell per 60 pulses + a surcharge while hot | ~8 s of full beam per cell; ~2x that when white-hot |

Derived: a behemoth biter (3000 hp) dies in ~5 s of full-intensity fire; five
small biters in a line die to one cold pulse.

## How it is built

Two layers, split so the engine keeps the boring bits:

**Prototype (`prototypes/`)**
- `melta-turret`: an ordinary `ammo-turret` with `attack_parameters.type = "beam"`,
  ammo category `melta`. The engine does targeting, rotation, the 64-direction
  head, the cyclic roar sound and the ammo magazine.
- `melta-beam`: the vanilla laser beam tinted orange, widened to 0.9, carrying the
  **cold** contact damage (14 thermal).
- `melta-fuel`: an ammo item with `magazine_size = 60` — the engine's own fuel burn.
- `thermal` damage type, `melta` ammo category, turret + fuel recipes, technology.

**Runtime (`control.lua`)**
- `charge` per turret: +1/150 per tick while a target is held *and* fuel is in the
  turret, −1/60 per tick otherwise.
- one **pulse** every 8 ticks: a corridor hit test along the beam axis, every body
  within `hit_half_width + body radius` of the line, sorted by distance, damage
  scaled by charge and by `pierce_falloff ^ (index - 1)`. The engine's own target
  gets the difference (`total − damage_cold`) because the beam prototype already
  landed the cold hit on it.
- fuel surcharge: `extra_cell_per_pulse_hot * charge` accumulated per pulse, cells
  removed from the turret when a whole cell is owed.
- visuals: one `rendering.draw_line` whose width/colour follow charge, plus a
  two-circle muzzle orb (hot core inside a soft halo) that shrinks as it cools.

## Engine facts this leans on (and the two that bit)

- `LuaEntity::shooting_state` **throws** on a turret ("Entity is not character") —
  engagement is read off `shooting_target` instead.
- A turret keeps *aiming* at a target with an empty magazine, so "has a target" is
  not "can fire"; the fuel check in the script is what gates the damage.
- `rendering.draw_light` needs a sprite path and `__core__/...` is not resolvable at
  runtime ("Unknown type __core__") — hence circles instead of a light.
- Beams cannot pierce (`BeamPrototype` has no piercing field; only projectile
  prototypes do), which is why the pierce lives in the script.
- Script-created entities raise no event at all, so the turret registry is repaired
  by a sweep every 600 ticks instead of trusting build/mine events alone.

## Known simplifications

- The beam ignores walls/rocks: it only tests military targets, so a melta will
  happily cut biters standing behind a wall. Cheap to add if it matters.
- The gun is the rocket pod sheet, heat-tinted. A real melta nozzle sprite (or a
  swap to the tesla emitter head, which is the same 64-direction rig) is an art
  pass, not a code one.
- Quality affects the turret like any other (health/crafting speed); no per-quality
  beam scaling.
- `thumbnail.png` is still the radar-artillery leftover from the stub.

## Where to retune

`constants.lua` only — it is read by both stages, so prototype and script can
never disagree. The four knobs that decide how it feels: `damage_cold`,
`damage_hot`, `spin_up_ticks`, `pierce_falloff`.
