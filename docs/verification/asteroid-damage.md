# Melta vs asteroids — the rock-damage channel

Status: **implemented and measured headlessly** (Factorio 2.1.23, space-age). Harness:
`docs/verification/harness/melta-ast-probe/` (never shipped). Raw logs below are from
`--create` + `--benchmark`, i.e. the real engine and the real mod code, no GUI.

## Why a melta could not break a rock

`data/space-age/prototypes/entity/asteroid.lua` gives every asteroid an explicit
resistance entry for each damage type its type does **not** list:

```lua
if damage_name ~= "impact" and damage_name ~= "poison" and damage_name ~= "acid" then
  table.insert(resistances, {type = damage_name, percent = 100})
end
```

`fire` is listed for no asteroid type, so **every asteroid is 100 % fire resistant** —
85 % of a melta pulse was doing literally nothing. The 15 % physical slice
(`C.physical_share`) was the only part that could land, and only where the rock has no
flat armour. Resistances read back from the live prototypes:

| asteroid | hp | physical | explosion | laser | fire | electric |
|---|---|---|---|---|---|---|
| small (metallic) | 100 | — | 50 % | 20 % | 100 % | 100 % |
| medium | 400 | 10 %, no flat armour | 30 % | 90 % | 100 % | 100 % |
| big | 2000 | 10 %, **-2000 flat** | 10 % | 95 % | 100 % | 100 % |
| huge | 5000 | 10 %, **-3000 flat** | 99 % | 99 % | 100 % | 100 % |

So at full heat a pulse put 8.4 physical on a small rock, 7.6 on a medium one, and
**0.0** on a big or huge one — the flat armour absorbs the whole slice.

## The fix

`C.asteroid_damage_multiplier` (`constants.lua`) adds one more damage call on the same
hit, `C.asteroid_damage_type = "explosion"`, sized as a multiple of the pulse:

```lua
if victim.valid and victim.health and victim.health > 0 and victim.type == "asteroid" then
  victim.damage(dealt * C.asteroid_damage_multiplier, force, C.asteroid_damage_type, turret)
end
```

* It is a **targeted multiplier**, not a blanket buff: the gate is the entity type, so
  pawns, spawners and buildings never see it.
* `explosion` is the type space-age already balances the asteroid ladder with (50 / 30 /
  10 / 99 %), so the melta kills small, medium and big rocks and leaves huge ones to the
  railgun. It is *not* `impact`/`acid` (unresisted by asteroids), which would have made
  the melta the best rock weapon in the game.
* It rides the existing pulse maths, so it ramps with charge, scales with the fuel's
  `damage_modifier`, and falls off along the pierce line like every other hit.

## Before / after (one melta, light oil 1.0x, pads 8–11 tiles, targets pinned)

Pulses are counted from the target's health dropping; a kill is captured by
`on_entity_died`, so the shot count is exact.

| target | before | after (1.6x) | after (1.9x) |
|---|---|---|---|
| small metallic asteroid, 100 hp | 11 pulses, 2.20 s | **2–3 pulses, 0.70–0.75 s** | 2 pulses, 0.60 s |
| medium metallic asteroid, 400 hp | 31 pulses, 5.77 s | **5–6 pulses, 1.33–1.38 s** | 6 pulses, 1.37 s |
| big metallic asteroid, 2000 hp | never — 236 pulses, 0.14 hp lost | **17 pulses, 3.3 s** | 15 pulses, 3.1 s |
| huge metallic asteroid, 5000 hp | never — 238 pulses, 0.15 hp lost | 413 hp in 40 s ⇒ ~8 min | 492 hp in 40 s ⇒ ~7 min |

Times are spawn-to-kill (they include the ~0.4 s the head needs to swing onto the target);
the two 1.6x columns are two independent runs of the same save recipe.

Effective dps on rock (single target, spawn-to-kill window): medium 69 → **290**, big 0 →
**600**. For scale, the same turret on a pawn does ~820 dps, so a rock still costs more beam
time than meat — the ladder is intact.

Huge asteroids stay effectively out of reach on purpose: 99 % explosion resistance plus
0.15 x 56 = 8.4 per pulse is ~3900 pulses. That is the vanilla intent (huge = railgun)
and the reason the new channel is `explosion` rather than an unresisted type.

## Pawn balance is untouched

Two stationary dummy units, `1e6` hp (float32 quantum 0.06), same pads, same fuel:

| target | before | after |
|---|---|---|
| unit, no resistances | 26 061.8 damage over 238 pulses (109.5/pulse, 821 dps) | 25 792.9 over 235 pulses (109.8/pulse, 823 dps) |
| unit, behemoth-biter armour (physical -12/10 %, explosion -15/10 %) | 22 448.1 over 237 pulses (94.7/pulse, 710 dps) | 22 525.6 over 238 pulses (94.7/pulse, 710 dps) |

Identical within charge-phase jitter. Time-to-kill a behemoth biter (3000 hp) is ~4.2 s
before and after.

## No errors on non-pawn, non-building targets

* asteroid (`type == "asteroid"`): 479 pulses across four rocks in one run, no Lua
  error, no "not a valid entity" complaint.
* biter-spawner (`type == "unit-spawner"`, enemy force): 13 pulses to kill, no error —
  the gate is skipped, the damage path is the old one.
* a neutral nauvis simple-entity (`rock-huge`) is **not** targetable by the turret at
  all, before or after: the pulse corridor only takes `is_military_target` entities whose
  force is an enemy of the turret's. If the melta should mine rocks too, that is a
  targeting change, not a damage change, and it is not in this patch.

## Reproducing

```bash
F=/e/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe
W=<scratch>   # config.ini with [path] write-data=<scratch>/write, mods/ = mod list + harness
cp -r docs/verification/harness/melta-ast-probe "<scratch>/mods/"
"$F" --config "$W/config.ini" --mod-directory "$W/mods" --create "$W/save.zip"
"$F" --config "$W/config.ini" --mod-directory "$W/mods" --benchmark "$W/save.zip" --benchmark-ticks 2400
grep astprobe "$W/write/factorio-current.log"
```

Two harness details that cost a debugging cycle each: asteroids **drift toward the
platform** (a rock placed 9 tiles away walks into the turret after ~8 s and the beam
loses the target), so the probe pins each target to its spawn tile every tick; and the
fluid buffer is only ~9 s of full beam, so it tops the boxes up every 200 ticks.

## Tuning

One dial: `C.asteroid_damage_multiplier`. 0 removes the channel entirely, 1.6 is the
shipped value, 1.9 makes a big rock 15 pulses instead of 17. Fuel modifiers stack on top
(melta-fuel 1.6x ⇒ medium rock in ~4 pulses).
