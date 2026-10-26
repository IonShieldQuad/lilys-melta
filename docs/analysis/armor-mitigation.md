# Armor mitigation — flat `decrease` vs percentage `percent`

Analysis for the spec card *melta turret — damage* (t_fddb93b1). **Nothing is implemented
by this document**: it describes what the engine and the mod do today, quantifies what flat
armour costs the turret, and ranks the mechanisms for "ignore flat armour, respect
percentage". Every number below is either read out of `constants.lua`/`data-raw` or measured;
the commands are in §7.

Engine: Factorio **2.1.23** (Steam), headless `--create` / `--dump-data`, base + space-age +
quality.

## 1. Where a melta pulse is actually dealt

The turret's damage is **entirely script-side**. The engine's own stream is a carrier for
aiming, sound and the fluid box, and its damage is explicitly zeroed:

| step | file:line | what happens |
|---|---|---|
| 1 | `prototypes/melta.lua:88` | the stream's damage effect is `amount = 0`, so the engine's damage pass contributes nothing |
| 2 | `control.lua:503` | pulse damage = `lerp(damage_cold, damage_hot, charge) * fuel.damage_modifier * damage_multiplier(turret)` |
| 3 | `control.lua:552` | `dealt = damage * pierce_falloff ^ (index - 1)` per body along the beam |
| 4 | `control.lua:565-566` | `dealt` is split: `fire_damage = dealt * (1 - physical_share)`, `physical_damage = dealt * physical_share` |
| 5 | `control.lua:567-570` | **uncommitted WIP** (`C.pierce_flat_armor`, `constants.lua:131`): each half is raised by that damage type's `decrease` before it is handed to the engine |
| 6 | `control.lua:571`, `:574` | two `victim.damage(amount, force, type, source)` calls — one damage type per call, and the second is skipped if the first killed the target |
| 7 | `control.lua:583` | asteroids only: an extra `explosion` hit of `dealt * C.asteroid_damage_multiplier` (1.6) |
| 8 | engine | applies the target's `resistances` to each of those calls — this is the step the mod cannot configure |

`C.physical_share = 0.15` (`constants.lua:23`), so a pulse is 85 % `fire` + 15 % `physical`;
`C.cooldown = 8` ticks (`constants.lua:45`) = 7.5 pulses/s.

Two consequences worth stating before any mechanism is chosen:

* The turret takes resistances **twice per pulse**, once per damage type, with different flat
  and percentage values. Any "ignore flat armour" rule has to be per damage type, not per shot.
* Because the split is taken *out of* `dealt`, the fire half is what the biters resist least —
  see §4. Fire resistance is absent from every biter, spitter and pentapod prototype in the
  dump; it appears only on spawners (3 flat / 60 %), worm turrets (2-3 flat / 50-70 %) and
  asteroids (100 %).

## 2. The engine's mitigation, measured

`LuaEntity::damage()` reduces the incoming amount by the target prototype's resistances for
that damage type. The `Resistance` concept documents the two fields as "Absolute damage
decrease" and "Percentual damage decrease"; the **order** is not written down anywhere in the
shipped docs, so it was measured:

| dummy prototype resistance | hit of 100 lands | hit of `100 + decrease` lands |
|---|---|---|
| none | 100.0 | 100.0 |
| `decrease = 12` | 88.0 | 100.0 |
| `percent = 10` | 90.0 | 90.0 |
| `decrease = 12, percent = 10` | **79.203** | **90.0** |
| `decrease = 12, percent = 100` | **0.0** | **0.0** |
| `decrease = -5, percent = 10` | 94.5 | 90.0 |

Probe: `docs/verification/harness/armor-mit-probe/` (six dummy units, one hit each, base only,
~12 s). What it establishes:

```
landed = max(0, amount - decrease) * (1 - percent / 100)
```

1. **Flat first, then percentage.** 79.203 = (100 − 12) × 0.9. Percentage-first would give
   78.0, and that is 1.2 damage away from what the engine actually did — the order is settled
   by measurement, not by assumption.
2. **The result is clamped at zero**, never negative: `decrease = 12, percent = 100` lands 0.
3. **A negative `decrease` adds damage** (94.5 = (100 + 5) × 0.9). Her pack's bosses use both
   negative `decrease` and negative `percent` (§3), so both branches are live in her game.
4. **`percent = 100` is absolute**: adding the flat amount back does not open a hole
   (still 0.0). "Respects percentage" therefore comes for free from any compensation scheme.
5. **The compensation identity holds exactly**: handing the engine `amount + decrease` makes
   the flat term cancel and the percentage apply to the nominal amount — 90.0 for a
   100-damage hit under 10 % resistance, 0.0 under 100 %. This is the whole trick behind
   option A in §5.
6. **`damage()` returns the amount actually taken** (79.199997 ≈ 79.2, float32). A caller can
   therefore read back the real post-mitigation number instead of assuming the formula — worth
   knowing for both the mechanism and its acceptance test.

## 3. Which armour actually stands in front of the turret

Read back from `data.raw` of a 2.1.23 dump (base + space-age + quality). `P` = physical,
`F` = fire, `E` = explosion; "flat / %".

| tier | prototype | hp | resistances |
|---|---|---|---|
| 0 | small-biter | 15 | none |
| 1 | medium-biter | 75 | P 4 / 10 %, E 0 / 10 % |
| 2 | big-biter | 375 | P 8 / 10 %, E 0 / 10 % |
| 3 | behemoth-biter | 3000 | P 12 / 10 %, E 12 / 10 % |
| 0-3 | spitters (all four) | 10-1500 | E only (0 / 10-30 %) — **no fire or physical resistance at all** |
| — | biter / spitter / gleba spawner | 350-500 | P 2 / 15 %, E 5 flat, **F 3 / 60 %** |
| — | small / medium / big / behemoth worm turret | 200-3000 | P 0-10 flat, **F 2-3 / 50-70 %**, E 5-10, laser 0 / 20-80 % |
| — | wriggler + stomper/strafer pentapods | 100-15000 | P 2 flat (stomper 50 %), laser/impact % only |
| — | small / medium / big / huge asteroid | 100-5000 | P 0 / 0 / **2000** / **3000** flat at 10 %, F **100 %**, E 50 / 30 / 10 / 99 %, electric 100 % |

So the flat armour the melta meets is: `physical` 2-12 on the biter line, `fire` 2-3 on
spawners and worms, and `physical` 2000-3000 on big and huge asteroids. **Nothing else in
base + space-age carries flat armour against `fire`.**

### Her actual pack

* `mod-list.json`: 238 mods enabled. A scan of every enabled ZIP's Lua (228 matched) found 60
  mods mentioning `resistances`, but only two touch **enemy** prototypes: `apia` (its own test
  units, `decrease = 4`) and `mferrari_lib` (bosses). Everything else is buildings, pipes,
  belts, vehicles and robots.
* `mferrari_lib/prototypes/resistances.lua` ships boss profiles worth naming, because they are
  the enemies where "ignore flat armour" stops being cosmetic:
  * `boss_fire_only`: `fire decrease -5, percent -80` (**takes 180 % fire damage**), physical
    `20 / 60`, explosion `20 / 60`, laser `10 / 50`, electric `10 / 50`.
  * `boss_fireworm`: `fire percent 100` (immune), `physical 10 / 10`, `explosion 15 / 40`.
* `ArmouredBiters` (2.0.2) and `castra` are installed but **disabled**, so neither is part of
  her current game.
* `they-be-biters` (enabled) rewrites biter *movement speeds* and adds a map preset; its data
  stage contains no `resistances`, `decrease` or `percent`.

## 4. What flat armour costs the turret — and the gun/tesla

Landed damage per **pulse** (melta) and per **shot** (gun, tesla). "Flat ignored" is the same
table with the §5-A mechanism applied; percentages still apply in both columns.

| target | melta cold today | cold, flat ignored | melta hot today | hot, flat ignored |
|---|---|---|---|---|
| small biter | 32.00 | 32.00 | 56.00 | 56.00 |
| medium biter | 27.92 | 31.52 | 51.56 | 55.16 |
| big biter | 27.20 | 31.52 | 47.96 | 55.16 |
| behemoth biter | 27.20 | 31.52 | 47.60 | 55.16 |
| behemoth spitter | 32.00 | 32.00 | 56.00 | 56.00 |
| biter spawner | 12.06 | 14.96 | 23.28 | 26.18 |
| behemoth worm | 7.26 | 12.96 | 13.38 | **22.68** |
| big stomper pentapod | 28.60 | 29.60 | 50.80 | 51.80 |
| small asteroid | 30.40 | 30.40 | 53.20 | 53.20 |
| medium asteroid | 40.16 | 40.16 | 70.28 | 70.28 |
| big asteroid | 46.08 | 50.40 | 80.64 | 88.20 |
| huge asteroid | 0.51 | 4.83 | 0.90 | 8.46 |

(Asteroid rows include the committed `explosion` channel, so they are *not* the fire/physical
split alone.)

Single-target dps at 7.5 pulses/s, first body only:

| target | cold today → ignored | hot today → ignored |
|---|---|---|
| small biter | 240.0 → 240.0 | 420.0 → 420.0 |
| medium biter | 209.4 → 236.4 | 386.7 → 413.7 |
| big biter | 204.0 → 236.4 | 359.7 → 413.7 |
| behemoth biter | 204.0 → 236.4 | 357.0 → 413.7 |
| biter spawner | 90.4 → 112.2 | 174.6 → 196.4 |
| behemoth worm | 54.5 → 97.2 | 100.4 → **170.1** |
| big stomper pentapod | 214.5 → 222.0 | 381.0 → 388.5 |
| big asteroid | 345.6 → 378.0 | 604.8 → 661.5 |
| huge asteroid | 3.8 → 36.2 | 6.7 → 63.4 |

Cross-turret comparison, damage **per hit** against the same armour (gun turret: 10 shots/s,
`gun-turret` cooldown 6; tesla: `tesla-turret` cooldown 120 → 0.5 shots/s, 30 `electric` per
body per jump, up to 12 jumps + fork 0.3):

| target | firearm (5) | piercing (8) | uranium (24) | tesla (30 electric) | loss caused by flat armour: melta hot / uranium bullet |
|---|---|---|---|---|---|
| small biter | 5.00 | 8.00 | 24.00 | 30.00 | 0 % / 0 % |
| medium biter | 0.90 | 3.60 | 18.00 | 30.00 | 6.5 % / 25.0 % |
| big biter | **0.00** | **0.00** | 14.40 | 30.00 | 13.1 % / 40.0 % |
| behemoth biter | **0.00** | **0.00** | 10.80 | 30.00 | 13.7 % / 55.0 % |
| behemoth spitter | 5.00 | 8.00 | 24.00 | 30.00 | 0 % / 0 % |
| biter spawner | 2.55 | 5.10 | 18.70 | 30.00 | 11.1 % / 22.1 % |
| behemoth worm | **0.00** | **0.00** | 14.00 | 30.00 | 41.0 % / 41.7 % |
| big stomper pentapod | 1.50 | 3.00 | 11.00 | 30.00 | 1.9 % / 54.2 % |
| small asteroid | 5.00 | 8.00 | 24.00 | **0.00** | 0 % / 0 % |
| medium asteroid | 4.50 | 7.20 | 21.60 | **0.00** | 0 % / 10.0 % |
| big asteroid | **0.00** | **0.00** | **0.00** | **0.00** | 8.6 % / 100 % |
| huge asteroid | **0.00** | **0.00** | **0.00** | **0.00** | 89.4 % / 100 % |

Pack bosses (`mferrari_lib`, transcribed in the harness):

| boss | melta hot today | hot, flat ignored | hot dps today → ignored |
|---|---|---|---|
| `boss_fire_only` | 94.68 | 98.04 | 710.1 → 735.3 |
| `boss_fireworm` | **0.00** | **7.56** | **0.0 → 56.7** |

How to read all of that:

* **Against the biter line the melta already beats flat armour, and it does so by
  construction.** 85 % of every pulse is `fire`, and no biter/spitter/pentapod in the dump
  resists fire, so the flat tax can only touch the 15 % physical slice — at most −15 % dps
  (behemoth: 420 → 357). Meanwhile the same armour takes a firearm bullet from 5.00 to 0.00
  and a uranium round from 24.00 to 10.80; the tesla pays nothing against base/space-age
  enemies at all, because **no enemy prototype in the dump resists `electric`** (asteroids
  excepted, at 100 %). Her pack's bosses do resist it (10 flat / 50 %), so the tesla is not
  armour-proof in her game — only against the vanilla ladder.
* **That is the answer to "is a low-per-shot, high-rate weapon punished by flat armour?"**
  Yes in principle — flat `decrease` is a per-hit tax, so it scales with pulses/second — but
  the melta's per-hit slice is *below* every biter tier's flat value (4.8 cold / 8.4 hot vs 4,
  8, 12), so the tax is total on that slice rather than partial, and the slice is only 15 % of
  the pulse. The turret loses −13.1 % against big and −13.7 % against behemoth biters, versus
  −40 % / −55 % for the gun turret's best ammo.
* **Where flat armour genuinely hurts is the classes with `fire` flat armour**: spawners
  (−11 % hot) and worm turrets (−41 % hot, because 8.4 physical is eaten whole by flat 10 and
  the 3 flat fire comes out of an already 70 %-resisted half).
* **Where it is fatal is where the fire channel is dead**: any 100 %-fire target. The
  `boss_fireworm` in her own pack is immune to fire and carries physical 10 flat — the melta
  currently does **0.00** damage per pulse to it. The physical slice alone is then the whole
  weapon, and flat armour takes all of it.
* **Asteroids** are the same story and already handled by the committed `explosion` channel:
  flat 2000/3000 still suppresses the physical slice to 0, which is why that channel exists.
  Ignoring flat armour adds +9.4 % on big asteroids and takes huge ones from 0.90 to 8.46 per
  pulse (still ~600 pulses for 5 000 hp).
* **Percentage resistance must keep working**, and it already dominates every hard target:
  the worm's 70 %, the boss's `percent = 100` fire immunity, the boss's `percent = -80` fire
  *vulnerability* (which is why `boss_fire_only` takes 94.68 from a 56 pulse). Any mechanism
  that sidesteps `percent` would break all of these at once.

## 5. Mechanisms, ranked

### A. Compensate the flat term at the damage call (script-side) — **recommended**

Hook: `control.lua` `pulse()` (`:565-576`), with the per-prototype lookup in `flat_armor()`
(`:191-220`) and the switch `C.pierce_flat_armor` (`constants.lua:131`). *Already present in
the working tree as uncommitted WIP; this section describes it as a design and lists what it
still needs.*

```
fire_amount     = dealt * (1 - physical_share) + fire_decrease
physical_amount = dealt * physical_share     + physical_decrease
```

The engine then computes `max(0, (x + d) - d) * (1 - p/100)` = `x * (1 - p/100)`, i.e. the
nominal amount under percentage resistance only — measured exactly in §2 row 4/5.

Pros
* No data surface: no new damage type, no prototype sweep, no prototype owned by base or
  another mod is touched.
* Reads the *real* resistance table of whatever is being hit, so modded enemies (her bosses,
  `apia`'s units, anything a future mod adds) are handled without a per-enemy table. Cached by
  prototype name, O(1) per pulse after the first hit.
* Per hit type, which is required here: a spawner's `fire` decrease is 3 while its `physical`
  decrease is 2, and the two halves are separate `damage()` calls anyway.
* Percentage resistance is untouched by construction, including the `percent = 100` floor and
  the `percent = -80` vulnerability: the compensation feeds the percentage, it does not skip it.
* Survives a target that dies mid-pulse: the second call is already guarded (`:573`).

Cons / things the implementation still owes
* The number handed to the engine is no longer the number the design says. Anything reading
  `on_entity_damaged.original_damage_amount` (DPS meters, damage-number overlays, another
  mod's logging) sees the inflated figure; `damage()`'s own return value and the health drop
  are correct. Cosmetic, but it should be a named trade-off in the spec.
* **Sign policy must be deliberate.** The current code compensates only `decrease > 0`. That is
  right for her bosses (`boss_fire_only` has `fire decrease -5`, a *bonus*; compensating it
  would remove 5 damage from every fire hit — the reason the guard exists) but the comment
  attached to it is wrong about *why*: it claims asteroids carry negative flat resistances.
  They do not — `data/space-age/prototypes/entity/asteroid.lua:51` is
  `decrease = {0, 0, 0, 2000, 3000}`, positive, and the same numbers appear in the dump.
  The real negative-`decrease` enemies are `mferrari_lib`'s bosses.
* **Asteroid decision needed.** Because the sign claim is inverted, the current guard does not
  do what its comment says: asteroids *are* compensated, which is why §4 shows big asteroids
  gaining +9.4 % and huge ones 0.90 → 8.46 per pulse. Either keep that (consistent with
  "ignore flat armour", small in absolute terms) or skip `victim.type == "asteroid"` so the
  authored rock ladder and the `explosion` channel stay the only rock path. Both are one line;
  the numbers above are the choice.
* Reads `prototype.resistances` per hit type; the existing code accepts both the dictionary and
  array shapes (2.1 hands back a dictionary — a dictionary for real, per the dump and per the
  probe). Keep that, it is free insurance for a future engine shape.
* Only `decrease` is cancelled. A target with `percent = 100` still takes zero — correct, and
  worth stating in the description so it is not reported as a bug.

### B. A custom damage type with percentage-only resistances (data-side)

Hook: `data.lua`/`data-updates.lua`. Declare `{type = "damage-type", name = "melta"}` (damage
types are prototypes — `data/base/prototypes/damage-type.lua`), point `C.damage_type` at it,
and in `data-updates` walk every enemy prototype (`unit`, `unit-spawner`, `turret` worms,
`asteroid`, `spider-unit`, …) and append
`{type = "melta", percent = <that prototype's fire or physical percent>}` — **with no
`decrease` field**. The engine then applies the percentage and there is no flat term to ignore.

Pros
* The engine does all of the arithmetic; the amount the script deals *is* the number the
  player sees, and `on_entity_damaged` stays honest.
* The percentage mapping is explicit and reviewable in one table, rather than being implied by
  the prototype at run time.
* No per-pulse prototype reads at all.

Cons
* Mutates ~40 prototypes owned by base/space-age, and every enemy from every other mod needs a
  matching entry. **The failure mode is silent and generous**: an enemy the sweep misses has no
  resistance entry for `melta`, so it takes full damage with no percentage either — the exact
  bug `boss_fire_only`'s `percent = 100` fire immunity exists to prevent.
* Load order matters twice: the sweep must run *after* the mods that create enemies
  (`data-updates` is not necessarily late enough — `mferrari_lib` and `apia` write their
  units in their own data stages), and space-age's asteroid builder inserts `percent = 100`
  for every damage type an asteroid does not list, which would silently make rocks immune to
  the new type unless the entry is inserted at the right stage.
* Needs locale + a `utility` damage-type icon, or the enemy information panel and the console
  show a raw `melta` identifier.
* A new damage type is visible in the Factoriopedia and in every enemy tooltip — more surface
  than the feature deserves for one turret.

### C. Compute the mitigation in script and write `health` directly — rejected

`victim.health = victim.health - landed` bypasses `on_entity_damaged`, `dying_explosion`, the
corpse/`last_damage_type` bookkeeping, force relations and damage triggers, and makes kill
attribution depend on `on_entity_died` still firing. It buys nothing that A does not already
give (A's landed value is exact, per §2), at the cost of stepping outside the damage system.

### D. Zero `decrease` on every prototype in `data-updates` — rejected

One line, and it changes the gun turret, the tesla, the flamethrower and every other weapon in
the game at once. Not a melta feature.

### E. No mechanism: buy the loss back with damage — fallback

The fire channel already ignores the biter line's flat armour, so the only thing "lost" on
pawns is the physical slice: ≤15 % dps. `C.damage_hot` 56 → 62 (+11 %) covers the behemoth
case but over-buffs unarmoured and 100 %-fire-resistant targets differently, and it does not
help the `boss_fireworm` case at all (fire 100 % immune, physical eaten). Worth naming so the
spec records why a code mechanism was preferred; not a substitute for A.

## 6. What the spec should say

1. **Mechanism: A**, implemented as it already is (per damage type, cached by prototype), with
   the WIP switch `C.pierce_flat_armor` as the dial.
2. **Guards the implementation must carry:**
   * compensate only a *suppressing* `decrease` (`> 0`); a negative one is a damage bonus and
     must survive (`boss_fire_only` fire `-5` / `-80 %`);
   * per damage type, not per shot (fire and physical tables differ on spawners and worms);
   * *the asteroid decision* — the current comment's justification is factually wrong (their
     `decrease` is positive 2000/3000), so choose explicitly: compensate (= +9.4 % on big
     rocks, huge 0.90 → 8.46/pulse) or exclude `entity.type == "asteroid"`;
   * no change to any other turret, damage type or prototype — an assertion that can be
     checked by diffing a `--dump-data` before/after.
3. **Acceptance test** (already in the tree as `melta-balance-probe`, built for this card's
   sibling — plus the engine probe added here): one melta, four dummies — plain, `fire`+
   `physical` `12 / 10 %`, `percent 50` only, `fire percent 100` — expecting nominal,
   nominal-minus-percentage, half, and the physical slice only. Extend with the two
   `mferrari_lib` boss profiles (§4), because the `fireworm` is the case the feature exists for.
4. **Player-facing wording**: the inspect panel already prints damage per pulse from
   `constants.lua`; the flat-armour bypass must not change that number, and the description
   should say the beam ignores *flat* armour but still suffers percentage resistance (so a
   100 %-fire target staying at zero reads as intended).

## 7. Two documentation errors found on the way

* `constants.lua:118-125` and `DESIGN.md` ("Asteroids", and the table row "big / -2000 flat")
  describe the asteroid flat armour as **negative**. It is positive
  (`decrease = {0, 0, 0, 2000, 3000}` in space-age's `asteroid.lua:51`, confirmed by the dump
  and by the measured "0.0 per pulse on a big rock"). The behaviour the docs describe is
  correct; the sign — and the conclusion drawn from it in the `pierce_flat_armor` comment — is
  not.
* `DESIGN.md` still lists "damage / pulse | 14 cold → 56 hot | 105 → 420 dps" while
  `constants.lua` ships 32 cold (240 dps). The same row's "damage type" line is fine.

## 8. Reproducing the numbers

```bash
# engine mitigation (§2) — base only, ~12 s, no GUI
#   copy docs/verification/harness/armor-mit-probe/ into a scratch --mod-directory with a
#   mod-list.json naming it, then:
Factorio.exe --config <scratch>/config.ini --mod-directory <scratch>/mods --create <scratch>/p.zip
grep mitprobe <scratch>/write/factorio-current.log

# enemy armour (§3) — full prototype dump, base + space-age + quality
Factorio.exe --config <scratch>/config.ini --mod-directory <scratch>/mods --dump-data

# tables in §4 — melta numbers come from constants.lua, armour from the dump
python docs/analysis/quantify_armor.py <scratch>/write/script-output/data-raw-dump.json
```

`quantify_armor.py` fails loudly if `constants.lua` stops defining a constant it reads, so a
retune cannot silently produce a table computed from the wrong numbers.
