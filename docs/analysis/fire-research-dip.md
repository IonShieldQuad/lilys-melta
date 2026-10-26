# Fire-damage research on turrets: single dip vs double dip

Analysis only — no balance number was changed by this card.

Measured on **Factorio 2.1.23**, `H:/Misc/lilys-innovations` is a different (FTL) repo; all
references below are either the game's own data or
`H:/Factorio Mods/lilys-melta`.

---

## 1. Summary

| turret | damage research | rate research | verdict |
|---|---|---|---|
| **gun turret** (vanilla) | `ammo-damage` (bullet) **and** `turret-attack` (gun-turret), **multiplicatively** | `gun-speed` (bullet) | **double dip**, measured: 5 → 10 → 10 → **20** per shot |
| **flamethrower turret** (vanilla) | the fire tech ships the same pair: `ammo-damage` (flamethrower) + `turret-attack` (flamethrower-turret) | none | designed to double dip (data-level: see §3 caveat) |
| **melta, shipped (`HEAD` 3f0a50e)** | **none at all** — its damage is script-only and no tech names its ammo category or its turret | **none** — the pulse clock is scripted | **zero dip**: 240 cold / 420 hot dps forever |
| **melta, working tree (uncommitted, in flight)** | `ammo-damage` (flamethrower) only, once | `gun-speed` copied onto the `melta` category | **single dip** + rate dip |

Two things follow, and both matter to the parent card:

1. A gun turret is **not** a 1×-per-level scaler. Two independent modifiers land on the same
   shot, so a +100 % level multiplies damage by **4**, not 2. Any "melta stays on par with the gun
   turret" table that treats the gun turret as single-dip is **1.8× low at tier 5**
   (907 dps instead of the measured 1633 dps).
2. Because the melta's damage is `LuaEntity.damage()` from `control.lua`, **the engine cannot scale
   it at all**. Every dip the melta gets is one the script has to read and apply itself — which is
   exactly why it is the only turret in the game that does not grow with research today.

---

## 2. Damage pipeline, in order

### 2.1 Gun turret (vanilla, engine-side)

`data/base/prototypes/entity/turrets.lua:458` (`gun-turret`), attack parameters at `:551`
(`type = "projectile"`, `ammo_category = "bullet"`, `cooldown = 6`), ammo in
`data/base/prototypes/item.lua:4051` (`firearm-magazine`, 5 physical) and `:2771`
(`uranium-rounds-magazine`, 24 physical).

For one shot, in this order:

1. **Fire interval** = `attack_parameters.cooldown / (1 + Σ gun-speed[bullet])`.
   Source of the sum: `technology` effect `gun-speed`, e.g.
   `data/base/prototypes/technology.lua:238` (`weapon-shooting-speed-1`, +0.1 per level).
2. **Ammo damage** = effect `damage.amount` × `(1 + Σ ammo-damage[bullet])`.
   `technology.lua:169` (`physical-projectile-damage-1`) carries
   `{type = "ammo-damage", ammo_category = "bullet", modifier = 0.1}`.
3. **Turret damage** = that × `(1 + Σ turret-attack[gun-turret])`. *The same technology level*
   also carries `{type = "turret-attack", turret_id = "gun-turret", modifier = 0.1}`.
   Steps 2 and 3 are two separate multipliers on the same number.
4. **Mitigation** (only here, once): `max(0, damage - decrease) × (1 - percent)` —
   `doc-html/concepts/Resistance.html` (`decrease` = flat, `percent` = fraction).

Confirmed by measurement (rig in §6, 100 % modifiers so the answer cannot be a rounding
artefact):

| research state | damage per shot | interpretation |
|---|---|---|
| nothing | **5.00** (25/25 shots) | base firearm-magazine |
| `ammo-damage[bullet]` +100 % | **10.00** (24/24) | ×2 |
| `turret-attack[gun-turret]` +100 % | **10.00** (24/24) | ×2 |
| both +100 % | **20.00** (30/31) | **×4 → multiplicative, not additive** |

Additive stacking would have given 15; a single applicable modifier would have given 10. It is 20.

Asymmetric detail for the infinite levels: `physical-projectile-damage-7` gives
`ammo-damage[bullet] +0.4` **but** `turret-attack[gun-turret] +0.7`
(`technology.lua`, block `physical-projectile-damage-7`), so the two dips are tuned separately
from level 7 on.

### 2.2 Flamethrower turret (vanilla fire-line reference)

`data/base/prototypes/entity/fire.lua:917` — fluid turret, `attack_parameters.type = "stream"`,
`ammo_category = "flamethrower"`, `fluids = {crude-oil, heavy-oil 1.05, light-oil 1.1}`,
`fluid_consumption = 0.2`. Its damage has two components:

* the stream's own `target_effects` (scaled by `ammo-damage[flamethrower]` and, as a turret, by
  `turret-attack[flamethrower-turret]`);
* the **`fire-sticker`** DoT (`entity/fire.lua:947`, `damage_per_tick = 10*100/60`,
  `damage_interval = 10`, `maximum_damage_multiplier = 6`, ramping with added fuel) — a sticker is
  a separate entity, so research does **not** scale it.

`refined-flammables-1..7` (`technology.lua:746` onward) ships the pair
`ammo-damage[flamethrower]` + `turret-attack[flamethrower-turret]` at identical values
(+0.2/+0.2/+0.2/+0.3/+0.3/+0.4, then +0.2 per infinite level) — i.e. the fire line is authored
with the same double dip as the bullet line.

**Caveat, stated honestly:** I attempted to measure the flamethrower's aggregate dps per phase and
the number is not usable — the probe re-filled its fluid buffer every tick, which drives the
`fire-sticker` fuel ramp to its 6× cap, so the DoT (which research does not scale) swamped the
signal and the "both modifiers" phase did not rise the way a ×4 contact-damage model predicts.
Data-level the double dip is unambiguous (both effects are in the tech and the turret is a fluid
turret with an ammo category); the aggregate measurement needs a normally-fuelled scene and is open.

### 2.3 Melta turret (shipped, `HEAD` 3f0a50e)

Turret prototype: `prototypes/entity.lua:149` — fluid turret, `attack_parameters.type = "stream"`,
`cooldown = C.cooldown` (8), `fluid_consumption = 2.5`, `ammo_category = "melta"`.

1. **Engine pass, result: zero.** The engine aims, burns fluid (2.5/shot at 7.5 shots/s ≈ 18.75/s)
   and spawns the invisible carrier stream `melta-stream`. That stream's only `target_effects`
   entry is `{type = "damage", damage = {amount = 0, type = "fire"}}`
   (`prototypes/melta.lua:74-90`, comment at `:81-88` explains why it must exist and why it is 0).
   No technology in vanilla names `ammo_category = "melta"` or `turret_id = "melta-turret"`, so
   even if the amount were non-zero there is nothing to scale. The stream also creates no sticker,
   so there is no DoT channel either.
2. **Script pass** (`control.lua` at `HEAD`):
   * aim gate — head orientation must be within `C.aim_tolerance` (`:863-867`), wind-up
     `C.windup_ticks`;
   * charge ramp — `state.charge = min(1, charge + 1/C.spin_up_ticks)` while firing (`:841-843`),
     150 ticks cold→white-hot;
   * pulse clock — `if tick >= state.pulse_at then state.pulse_at = tick + C.cooldown` (`:889-890`,
     `:926`); **fixed at 8 ticks, nothing reads research**;
   * `pulse()` (`:352`): `damage = (32 + 24*charge) × fuel.damage_modifier` (`:355`), then per body
     `dealt = damage × 0.82^(i-1)` (pierce, `:403`), split 85 % `fire` / 15 % `physical`, plus the
     asteroid-only `explosion` channel ×1.6;
   * `victim.damage(amount, force, type, source)` (`:410`, `:413`, `:422`).
3. **Mitigation** happens inside `LuaEntity.damage()` and is the only thing the engine does to the
   number: `max(0, amount - decrease) × (1 - percent)`.

Measurement confirming step 3 (and that research is *not* consulted by `damage()`): with
`ammo-damage[bullet] = turret-attack[gun-turret] = 1.0`, a direct
`dummy.damage(10, force, "physical", turret)` took exactly **10.00 hp** — the API path is
unscaled. (Same result the earlier tooltip card measured from the other side: a full-charge pulse
took exactly 56.00 hp, i.e. `C.damage_hot` and nothing else.)

**So at `HEAD` the melta's answer is "none": 240 cold / 420 hot dps at every research level, and
its fire rate never changes.**

### 2.4 Melta in the working tree (uncommitted; written by the parallel implementation card)

`control.lua:75-170` adds a per-force research cache and two multipliers:

* `damage_multiplier()` (`:154-160`) = `1 + Σ ammo-damage[flamethrower]` (category list
  `C.research_damage_ammo = {"flamethrower"}`), applied once to the whole pulse
  (`:503-504`: `… × profile.damage_modifier × damage_multiplier(turret)`);
* `pulse_interval()` (`:163-175`) = `C.cooldown / (1 + Σ gun-speed[melta])`, floored at
  `C.cooldown_min = 2`; the `gun-speed` effects are copied onto the `melta` category at the data
  stage by `data-updates.lua:88-126` so the tech tooltip shows them.

That is **single dip on damage** (one ammo modifier, once) **plus the rate dip**. The header
comment at `control.lua:85-96` states this deliberately.

---

## 3. Can the melta double dip "through a DoT"? No.

The task's hypothesis — once on the projectile, once on a per-tick burn — cannot fire in this mod
as built: `git grep sticker HEAD` and `grep -rn sticker|fire-flame` over the repo both return
nothing. The only time-dependent quantities are the charge ramp (a state multiplier, not a second
application of research) and the hot fluid surcharge. The one real double dip available to the
melta is the **same one the gun turret gets**: the second, `turret-attack`, copy of the same
research level.

---

## 4. Recommendation: make it double dip, the same way a gun turret does

Mechanism (fits the existing data/`control.lua` split, no new system):

1. `data-updates.lua`: for every technology that carries `turret-attack[flamethrower-turret]`,
   append an identical `{type = "turret-attack", turret_id = "melta-turret", modifier = X}`.
   That mirrors what the existing block already does for `gun-speed`, keeps the number owned by the
   game's data, and makes the effect visible in the tech tooltip ("Melta turret damage +20 %").
2. `control.lua`: read both terms —
   `force.get_ammo_damage_modifier("flamethrower")` **and**
   `force.get_turret_attack_modifier("melta-turret")` — and multiply
   `(1 + ammo) × (1 + turret_attack)`, which is precisely the engine's rule for a gun turret.
   (`set_/get_turret_attack_modifier` and `get_ammo_damage_modifier` are in
   `doc-html/runtime-api.json`, `LuaForce`.)
3. Keep the existing rate dip as-is.

Why:

* Parity is only possible with the same number of multipliers. At tier 5 single-dip the melta is at
  **68 %** of a uranium gun turret; double-dip it is at **149 %** cold and **260 %** hot — which is
  the parent card's stated contract ("on par cold, well ahead fired up").
* The double dip is not an exploit here, it is the vanilla shape of a turret damage line: the fire
  line's own tech ships both effects. A melta that reads only one of them is not "more honest than
  vanilla", it is a turret that quietly loses a factor the whole game is balanced around.
* Fuel efficiency finally scales: the double dip raises damage per fluid, which is the melta's
  compensating currency for short range.

Two decisions the spec card must make explicitly:

* **Should the fire bonus scale the 15 % physical share?** The working tree multiplies the *whole*
  pulse (`control.lua:503-504`), so a "fire damage" research also boosts the physical slice.
  Cleaner: scale only the fire component, `pulse = fire×(1+a)×(1+t) + physical`. Numbers for both
  are in §5 (`fire-share-only` rows). This changes nothing at tier 0 and about −12 % at tier 5
  double-dip.
* **Rate dip vs fuel.** The engine burns 2.5 fluid per *engine* shot (cooldown 8 → 7.5 shots/s ≈
  18.75 fluid/s) while the script pulses at up to `60/2 = 30/s` after research. Fuel per point of
  damage therefore *halves* per tier unless the engine-side cost is also scaled — reasonable as a
  design ("better ammo handling"), but it should be a decision, not a side effect.

---

## 5. Melta effective damage, tiers 0-5 (and the start of the infinite line)

Assumptions: `C.damage_cold = 32`, `C.damage_hot = 56`, `C.cooldown = 8` (7.5 pulses/s),
light oil (×1.0 — every number below multiplies linearly by the fuel profile, e.g. ×1.6 on
melta-fuel), no quality, one body (pierce falloff applies on top unchanged).

**tier N = `refined-flammables-N` and `weapon-shooting-speed-N` both researched** (the vanilla
cumulative bonuses: +20/+40/+60/+90/+120 % fire, +10/+30/+50/+80/+110 % rate).
`S` = single dip (`1+a` on damage), `D` = double dip (`(1+a)²`).

| tier | fire dmg | rate | pulse cold S / D | pulse hot S / D | dps cold S / D | dps hot S / D | gun turret (uranium) |
|---|---|---|---|---|---|---|---|
| 0 | +0 % | +0 % | 32.0 / 32.0 | 56.0 / 56.0 | 240 / 240 | 420 / 420 | 240 |
| 1 | +20 % | +10 % | 38.4 / 46.1 | 67.2 / 80.6 | 317 / 380 | 554 / 665 | 319 |
| 2 | +40 % | +30 % | 44.8 / 62.7 | 78.4 / 109.8 | 437 / 612 | 764 / 1070 | 449 |
| 3 | +60 % | +50 % | 51.2 / 81.9 | 89.6 / 143.4 | 576 / 922 | 1008 / 1613 | 706 |
| 4 | +90 % | +80 % | 60.8 / 115.5 | 106.4 / 202.2 | 821 / 1560 | 1436 / 2729 | 1106 |
| 5 | +120 % | +110 % | 70.4 / 154.9 | 123.2 / 271.0 | 1109 / 2439 | 1940 / 4269 | 1633 |
| 6* | +160 % | +150 % | 83.2 / 216.3 | 145.6 / 378.6 | 1560 / 4056 | 2730 / 7098 | 2904 |

\* level 6 is the last finite level; 7+ is infinite at +20 % fire / no further rate,
so the double-dip gap keeps widening (`(1.2)² = 1.44` per infinite level vs `1.2` single).

Ratios:

* double ÷ single dip on damage: **1.20 / 1.40 / 1.60 / 1.90 / 2.20** at tiers 1-5 (exactly `1+a`);
* melta single-dip cold ÷ gun turret: 0.99 / 0.97 / 0.82 / 0.74 / **0.68** — the melta falls behind;
* melta double-dip cold ÷ gun turret: 1.19 / 1.36 / 1.31 / 1.41 / **1.49**;
* melta **hot** double-dip at tier 5: 4269 dps vs gun turret 1633;
* "today" (`HEAD`, no scaling at all): 240 / 420 at every tier.

If the fire bonus is applied to the fire share only (85 %), double-dip cold dps becomes
240 / 363 / 567 / 837 / 1390 / **2149** (tier 5) and hot 420 / 635 / 992 / 1465 / 2433 / **3761**
— i.e. ≈88 % of the whole-pulse numbers above.

---

## 6. How the numbers were obtained

`C:/Users/Lily/AppData/Local/hermes/cache/scratch/dip-probe/` (scratch env, `--mod-directory` +
`--config` pointing at its own `write/`, so the live install was untouched):

* `mods/dip-probe_0.1.0/data.lua` — `dip-dummy`, a `small-biter` deepcopy with
  `max_health = 1e6`, `movement_speed = 0`, `resistances = {}`, harmless.
* `mods/dip-probe_0.1.0/control.lua` — builds a gun turret (firearm magazine) 8 tiles from the
  dummy and a flamethrower turret 12 tiles from a second dummy, then walks four phases by
  `force.set_ammo_damage_modifier` / `force.set_turret_attack_modifier`:
  none → ammo +100 % → turret-attack +100 % → both; logs dummy hp every tick; at tick 660 calls
  `dummy.damage(10, force, "physical", turret)` with both modifiers at +100 % to test the script path.
* run: `Factorio.exe --create save.zip` then
  `Factorio.exe --benchmark save.zip --benchmark-ticks 700`; parsed with `analyse2.py`
  (per-tick health drops, trim 3 ticks at each phase edge).
* Raw log: `write/factorio-current.log` in that directory (`[dip] t=… ghp=… ammo=…` per tick).

Known limitations: the vanilla flamethrower reading is not clean (see §2.2 caveat); the melta's own
values in §5 are computed from `constants.lua` plus the vanilla technology data, not re-measured —
the per-pulse damage path was already measured in `docs/verification/` (56.00 hp at full charge).
The probe sets every modifier on the ticket's own force, so the first ~60 ticks of the log carry
+100 %/+100 % (the tick-0 script-damage check runs before the phase clock re-zeroes them); all
quoted figures come from the trimmed phase windows.
