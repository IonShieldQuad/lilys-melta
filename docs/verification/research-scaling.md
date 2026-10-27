# Research scaling, and fuels that arrive after this mod's data.lua

Two reports from a playtest on 0.6.0, both measured on 2.1.23.

> "cubonium gas doesn't seem to show as available fuel (mod load order maybe?)"
> "with 10+ upgrade levels they shouldn't struggle vs medium and big biters"

## 1. A fuel that another mod defines LATER

Her own `factorio-current.log` had the answer before any probe:

```
37.932  Loading mod lilys-melta 0.6.0 (data.lua)
41.253  Loading mod lilys-cubeine 2.4.5 (data.lua)     <-- defines cubonium-gas
48.949  Loading mod lilys-melta 0.6.0 (data-updates.lua)
...
[lilys-melta] fuels accepted: light-oil, petroleum-gas, melta-fuel, lilys-napalm-mix
```

`prototypes/entity.lua` builds the engine's `attack_parameters.fluids` at **data.lua**
time and keeps only the fluids that exist then. Cubeine's own dependency chain (space-age,
its asset packs, the spoilage engine) pushes it *after* the melta in the load order even
though "cubeine" sorts before "melta" — so `cubonium-gas` did not exist yet and was
dropped, exactly as she guessed.

Fix, two parts:

* `data-updates.lua` now tops the list up (it runs after every mod's data.lua): every
  `C.fuels` entry whose fluid exists by then and is not already listed is appended. The
  load log says which:
  `[lilys-melta] late fuels added at data-updates: cubonium-gas`.
* `prototypes/tooltip.lua` is now a function called from that same stage, so the fuel list
  inside the tooltip is generated from the same, final `data.raw.fluid` table. It used to
  run in data.lua and would have kept printing the pre-top-up roster.
* `info.json` gained `? lilys-cubeine`, so when that mod is installed the ordering is
  guaranteed instead of accidental.

Verified with a stub mod that defines `cubonium-gas` in its data.lua *and depends on
lilys-melta* (so it loads after it, like cubeine does here):

```
4.468 Loading mod lilys-melta 0.6.0 (data.lua)
4.605 Loading mod zz-latefuel-probe 0.0.1 (data.lua)
4.786 [lilys-melta] late fuels added at data-updates: cubonium-gas
4.786 [lilys-melta] fuels accepted: light-oil, petroleum-gas, melta-fuel, cubonium-gas
```

and the turret really burns it — `cubonium-gas` in the buffer over 200 firing ticks:
196.4 -> 131.2 units (≈19.6/s, the same rate as melta-fuel). `--dump-data` confirms both
the prototype list and the tooltip description mention it.

## 2. The infinite tier was not being counted

0.6.0 read research by walking `force.technologies` and adding each technology's
`ammo-damage` modifier **once**. That is wrong for the infinite tier: `refined-flammables-7`
is `max_level = "infinite"` and pays **+0.2 per level**, so ten extra levels added 0.2
instead of 2.0. A turret could be ten levels into fire damage and fight like it had none —
which is exactly what was reported.

The engine already computes this correctly, so the script now asks it instead of summing by
hand:

| read | API | what it returns |
|---|---|---|
| damage | `force.get_ammo_damage_modifier("flamethrower")` | +1.8 at all finite tiers + infinite level 1 (measured), +2.4 after the infinite level moved |
| damage | `force.get_turret_attack_modifier("melta-turret")` | the same ladder, once the effects are mirrored (§3) |
| rate | `force.get_gun_speed_modifier("melta")` | firing-speed ladder, including the copied levels |

**The call has to be one argument.** `force.get_ammo_damage_modifier("flamethrower")` works;
`force.get_ammo_damage_modifier(force, "flamethrower")` raises *"Arguments count error:
Expected 1 argument but 2 were given"*. The first version of this fix wrapped the call in
`pcall` *with* `self`, so the error was swallowed and every read returned 0 — research
silently off, which is worse than the bug it replaced. Both forms are measured in the api
probe; the working form is the one in `control.lua`.

The bonus is cached for a second per force (not forever): another mod's script can change a
force modifier and no event this mod may listen to is raised for it
(`on_technology_effects_reset` cannot be raised from script at all — measured), so the cache
expires on its own.

### What it is worth, measured as real health taken off a dummy

`set_ammo_damage_modifier` / `set_turret_attack_modifier` / `set_gun_speed_modifier` applied
before the first pulse (so no cache can hide it), dps = health lost over exactly 60 ticks:

| force bonus | dps | ratio | expected |
|---|---|---|---|
| none | 1398 | 1.00 | — |
| +200 % ammo-damage (fire) | 7426 | 5.31x | (1+2)^1.5 = 5.20x, `research_damage_exponent` |
| +200 % turret-attack (melta) | 7426 | 5.31x | same — both read paths agree |
| +100 % gun speed (melta) | 2654 | 1.90x | interval 8 -> 4 ticks |

So the damage ladder reaches the beam through *either* modifier, the firing-speed ladder
reaches the pulse clock, and `C.research_damage_exponent` is the only thing deciding how
hard the damage ladder bites.

## 3. Making it visible: the melta now appears in the techs

The flamethrower turret shows up in the fire line because every `refined-flammables` level
carries **two** effects: `ammo-damage` for its ammo category and `turret-attack` for
`flamethrower-turret`. The melta was in neither list — no vanilla technology names its
turret id — so nothing on any technology screen pointed at it.

`data-updates.lua` now mirrors the `turret-attack` half onto `melta-turret` for every
technology that has one for a donor turret (`flamethrower-turret`), with a fallback pass for
modded technologies that only carry `ammo-damage` for our categories. Real data after the
change:

```
refined-flammables-7.effects = [
  {type = "turret-attack", turret_id = "flamethrower-turret", modifier = 0.2},
  {type = "turret-attack", turret_id = "melta-turret",        modifier = 0.2}   <-- added
]
[lilys-melta] melta damage research: 7 turret-attack effects mirrored
```

It cannot double-dip the damage: the melta's engine-side stream is zeroed on purpose, so the
only damage the engine could multiply is already zero, and the script reads the modifier
rather than being multiplied by it. Taking the **larger** of the two modifiers when both are
present is what keeps every researched level counted exactly once instead of squared.

Still not shown: a Damage line in the inspect panel. The panel's number comes from the
ammo/stream action, which is deliberately 0 for this turret, and the description block is
static data — it cannot print a live researched figure. The technology tooltips are where
the ladder is now visible, and the turret's description says the ladder applies once per
researched level including the infinite one.
