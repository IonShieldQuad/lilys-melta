# Melta damage balance — spec, implementation, and measurement

What this document is: the numbers the melta was retuned to, the code that applies
them, and the in-game measurements that prove each claim. Everything here was run on
Factorio **2.1.23** (Steam, space-age) through the headless harness in
`harness/melta-balance-probe/` — `--create` builds the scene, `--benchmark` ticks it,
and every figure is a real drop in a dummy's health, not a formula.

Two trees were measured with the same probe and the same scene:

* **before** = `git HEAD` (melta 0.5.0: `damage_cold = 14`, no research scaling, no
  flat-armour bypass),
* **after** = HEAD + the change in this card.

Reproduce with `run_balance.py before|after` (stage) and `run_tooltip.py` (tooltip),
both kept in the card workspace; the probe lives in the repo so the measurement can be
repeated on any later tree.

## 1. The comparison the melta has to win

| turret | per hit | rate | single-target dps | what it gets instead |
|---|---|---|---|---|
| gun turret, firearm magazine | 5 physical | 10/s | 50 | range 18 |
| gun turret, piercing rounds | 8 | 10/s | 80 | range 18 |
| gun turret, uranium rounds | 24 | 10/s | **240** | range 18 |
| tesla turret (space-age) | 120 electric | 0.5/s | **60** | range 30, chains up to 10 jumps x 12 tiles (`chain-tesla-turret-chain`), stun + slow stickers |
| **melta, cold barrel** | 32 (85 % fire / 15 % physical) | 7.5/s | **240** | range 16, fluid fuel, cuts up to 12 bodies |
| **melta, fully spun up** | 56 | 7.5/s | **420** = 1.75x cold | as above |

The gun turret and tesla figures are read from `data/base/prototypes/entity/turrets.lua`,
`data/space-age/prototypes/entity/turrets.lua`, `chain-tesla-turret-chain` and the ammo
prototypes; the gun turret's is confirmed in the scene (24.000 damage per shot, 6-tick
cooldown, i.e. 240 dps). The tesla turret was not run in the scene: an electric turret
needs a powered grid and a headless `--benchmark` scene has none.

**Contract.** Cold barrel on par with the strongest gun turret (uranium rounds) despite
16 tiles of reach and a fuel bill; fully spun up 1.75x that, which is what pays for the
short range. Before this card the cold barrel was **14 (105 dps)** — below a *piercing*
gun turret — and the turret only became worth its plumbing once white hot.

## 2. What changed

| what | where | before | after |
|---|---|---|---|
| cold pulse damage | `constants.lua` `damage_cold` | 14 | **32** |
| hot pulse damage | `constants.lua` `damage_hot` | 56 | 56 (unchanged: 420 dps = 1.75x cold) |
| research scaling | `control.lua` research section, `data-updates.lua` | none — script damage was invisible to every technology | fire damage ladder (x^1.5) + turret firing speed |
| flat armour | `control.lua` `flat_armor()` | applied in full (a behemoth's 12 flat ate the whole cold pulse) | ignored; percentage resistance still applies |
| tooltip | `prototypes/tooltip.lua`, `locale/*/locale.cfg` | cold/hot dps only | + two lines: flat armour, research |

Nothing else was touched: the gun and tesla turrets keep their own numbers, no shared
mitigation behaviour changed (the bypass lives inside the melta's own `victim.damage`
calls), and `damage_hot`, the pierce rule, the asteroid channel and the fuel table are
untouched.

### 2a. Research scaling — the two dips, and what "double dip" turned out to mean

The melta's damage is dealt by `control.lua`, so the engine's ammo upgrades never see
it. Measured on the stock tree, **nothing** the player researched moved the turret:

```
before   tier 0 .. tier 5   melta first=17.625  hot=56.000  interval=8   (identical at every tier)
                             gun   first=24.000 -> 77.750  interval=6 -> 3
```

The gun turret's own curve was measured first, because that is the curve the melta has
to match, and it is not what the wiki-style maths suggests:

| researched (bullet) | damage / shot | ratio | rate |
|---|---|---|---|
| none | 24.000 | 1.00 | 10/s |
| +10 % (ppd-1) | 29.063 | 1.21 = 1.1^2 | 12/s |
| +20 % (ppd-1,2) | 34.563 | 1.44 = 1.2^2 | 12/s |
| +40 % (…-3) | 47.063 | 1.96 = 1.4^2 | 15/s |
| +60 % (…-4) | 61.438 | 2.56 = 1.6^2 | 20/s |
| +80 % (…-5) | 77.750 | 3.24 = 1.8^2 | 21/s |

Two facts fall out, and both matter:

1. **Every turret technology ships its bonus twice** — `ammo-damage` for an ammo category
   *and* `turret-attack` for a turret id (`physical-projectile-damage-1` carries both
   `ammo-damage[bullet] +0.1` and `turret-attack[gun-turret] +0.1`), and the engine
   multiplies the two. That is why the gun turret's measured damage ratio is the square of
   its accumulated bonus, while its firing speed is a single application. The melta is not
   the `turret_id` any technology names (the fire line targets `flamethrower-turret`), so
   only the `ammo-damage` half is readable for it — the second half of the engine's double
   dip does not exist for this turret id. That is the "double dip" the card asked about:
   real, the engine's, and not reachable by a modded turret id.
2. **`technology.level` is the tier number, not a stacking count.** `refined-flammables-2`
   reports `level = 2, max_level = 2` with a single `modifier = 0.2`; multiplying by `level`
   triples the ladder (that mistake is what made the first pass of this change reach
   +240 % instead of +120 %, and it is recorded here so nobody repeats it). The engine
   applies each researched technology's modifier once — confirmed by the measured squares
   above and by the tier table in §3.

The melta therefore applies the fire ladder (`refined-flammables`, `ammo-damage` for
`flamethrower`) **once**, compounded by `C.research_damage_exponent = 1.5`: the fire
ladder is steeper than the bullet ladder (+20/20/20/30/30 % vs +10/10/20/20/20 %), and
without the exponent a single application leaves the melta **32 % behind** a gun turret
at the end of the finite lines. 1.5 is the one number that keeps the cold barrel level at
*every* tier (1.0 = plain single dip, 2.0 = literal double dip — both are one edit away).

The second dip is the turret firing-speed line: `data-updates.lua` copies each
`weapon-shooting-speed` level's bullet `gun-speed` modifier onto the melta's own ammo
category (so it appears in the tech tooltip as melta firing speed), and `control.lua`
divides the pulse interval by the same accumulated bonus. The pulse clock is scripted,
so the script has to read it; the data stage reports `melta firing speed: 6 gun-speed
effects copied from 6 technologies` at load.

### 2b. Flat armour — ignoring the subtraction, keeping the percentage

The engine always resolves a hit as `max(0, amount - decrease) * (1 - percent/100)` and
offers no "ignore flat armour" flag. The pulse is therefore handed
`amount + decrease` for each damage type, which cancels the subtraction exactly and
leaves the percentage doing its full job. Only **positive** `decrease` is compensated:
asteroids carry negative flat resistances (-2000 physical on big, -3000 on huge) that
mean *extra* damage, and cancelling those would nerf the melta against rocks.

Measured against four dummies of 1e6 hp that differ only in resistance:

| dummy | resistances | before: cold / hot pulse | after: cold / hot pulse |
|---|---|---|---|
| plain | none | 17.625 / 56.000 | 34.063 / 56.000 |
| flat | fire+physical `decrease 12, percent 10` | **2.750 / 32.250** | **30.688 / 50.375** |
| percent | fire+physical `percent 50` | 8.813 / 28.000 | 17.063 / 28.000 |
| fireimmune | fire `percent 100` | 2.625 / 8.375 | 5.125 / 8.375 |

Read the rows, not the ramp (the "cold" figure is the first pulse, taken a few ticks into
the spin-up, so it is a little above the 32/56 statline; both columns ramp the same way):

* **flat** — before, a behemoth's 12 flat armour erased the entire cold pulse (2.750 vs
  17.625 unarmoured, i.e. the turret did 16 % of its damage) and took 42 % off the hot
  pulse. After, it lands **90.1 %** of the unarmoured pulse — exactly its 10 %
  *percentage* resistance and nothing else. The flat half is gone.
* **percent** — identical 50 % of the unarmoured figure before and after (8.813/17.625
  and 17.063/34.063): percentage resistance is untouched, by design.
* **fireimmune** — the physical slice alone survives, and now lands in full (4.8 of the
  32 cold pulse; 8.375 at full charge) instead of being eaten by flat armour.

## 3. The curve, measured

Same scene, one tier per step: research the next level of `refined-flammables`,
`weapon-shooting-speed` and `physical-projectile-damage` (the gun turret's reference),
fresh turret + dummy per tier. `first` and `last` are real health drops; the dps columns
are `pulse x 60/cooldown` and are the comparable figures (the measured interval is
quantised to whole ticks, which is why tier 1 reads 8 ticks where the maths says 7.27).

| tier | fire / rate | melta cold pulse | melta hot pulse | interval | melta cold dps | melta hot dps | gun turret dps |
|---|---|---|---|---|---|---|---|
| 0 | +0 % / +0 % | 32 | 56.000 | 8 | **240** | **420** | **240** |
| 1 | +20 % / +10 % | 43.7 | 73.625 | 8 | 347 | 607 | 319 |
| 2 | +40 % / +30 % | 55.7 | 92.813 | 7 | 517 | 905 | 449 |
| 3 | +60 % / +50 % | 67.6 | 113.313 | 6 | 729 | 1275 | 706 |
| 4 | +90 % / +80 % | 87.1 | 146.688 | 5 | 1132 | 1980 | 1106 |
| 5 | +120 % / +110 % | 108.6 | 182.750 | 4 | **1645** | **2878** | **1633** |

* Cold tracks the gun turret within 1-15 % at every tier (1.00x, 1.09x, 1.15x, 1.03x,
  1.02x, 1.01x) — the "on par at cold barrel" half of the contract, held through the whole
  research chain instead of only at tier 0.
* Hot is 1.75x the melta's own cold dps everywhere, i.e. 1.76-2.02x the gun turret — the
  "significantly outperform when fired up" half.
* The unpulsed hot figures are exact against the statline (56 x 1.2^1.5 = 73.6,
  56 x 2.2^1.5 = 182.7), so the exponent is applied exactly once and nowhere twice.

Before the change the same probe read `first=17.625 hot=56.000` at **every** tier: no
scaling at all, i.e. the turret lost this race by 4x at the end of the finite lines.

## 4. Fuel, for completeness

`C.fluid_consumption = 2.5` per shot (engine) plus `extra_fluid_per_pulse_hot = 3.8` at
full charge: 18.75 fluid/s cold, ~47/s hot on light oil. Raising the cold pulse to 32
does not change either figure; the researched firing-speed line does, in proportion
(a +110 % rate burns ~2.1x the fluid per second for ~2.1x the damage, so fuel per point
of damage is flat across research — the same property a gun turret's ammo has).

## 5. How to re-run

```bash
# measurement (before/after, four dummies, six tiers)
python <card>/run_balance.py both

# the tooltip the player will read (headless: --create runs on_init, where
# localised_print resolves real locale strings)
python <card>/run_tooltip.py
```

The tooltip check prints the assembled description; on this tree it resolved to

```
Damage: 32 per pulse on a cold barrel, 56 when fully spun up (85% fire, 15% physical).
At 7.5 pulses per second that is 240 to 420 per second on the first enemy hit.
...
Ignores the flat part of enemy armor. Percentage resistance still applies.
Improved by flamethrower damage and turret firing speed research.
```

so the panel, the item tooltip and the code cannot disagree: the block is generated from
`constants.lua`.

## 6. What is not covered here

* No GUI run was made: this is a numbers change, and the sprite atlas, sounds and the
  hover panel were already verified in `melta-improvements-verification.md`. The tooltip
  text itself was verified headless (above).
* The tesla turret's 60 dps is read off its prototypes rather than measured (powered-grid
  reason above); its chained total is up to ~600 dps across 10 bodies, which no
  single-target comparison captures either way.
* `research_damage_exponent = 1.5` is a deliberate compromise, not a law: it is the
  number that makes cold-parity hold at every tier given the two ladders' different
  slopes. If the fire ladder is ever changed upstream, re-run the probe and re-fit.
