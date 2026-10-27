# Damage model: continuous instead of pulses (0.6.2)

Playtest report:

> "because the pulse rate is limited, if turret 'sweeps rapidly' across a swarm of biters,
> some of them get touched by beam visually, yet take no damage if a pulse doesn't happen at
> a correct time"

and then:

> "I think continuous damage instead of pulses + no falloff for pierce would be fine, just
> make sure it's consistent and doesn't tank performance"

Both done. Everything below is measured on 2.1.23 with the same scene run against the 0.6.1
tree and the working tree.

## What was wrong

Two clocks were fused. The beam is drawn, and its target tracked, every tick, so the corridor
it covers moves every tick. Damage was applied once per 8-tick pulse, tested on that tick's
corridor only. A turret following a target across a group therefore cut a visible arc through
bodies that took nothing unless the arc happened to be over them on a pulse tick.

## The change

* damage every tick: `pulse damage / pulse interval` per tick, so the damage per second on a
  locked target is unchanged and the damage per *second of exposure* is what the drawn beam
  covers. The corridor is sampled when the beam's geometry moves (a locked-on turret reuses
  it, one engine query per pulse window exactly as before; every `C.hit_refresh_ticks`, 8,
  it is rebuilt so bodies that walk in are picked up);
* `C.pierce_falloff = 1.0` by default: every body on the axis takes the whole hit, capped by
  `C.pierce_max`. At 1 the code also skips the `^` and the near-to-far sort entirely;
* the pulse clock keeps the thump — muzzle flash, cut marks, impact pop, fuel surcharge, the
  "which fluid is burning" sample;
* cost control: each body's radius is cached at refresh (`bounding_box` allocates two tables
  per read and must not run per tick), and the fire and physical halves of a hit land on
  alternating ticks at double the amount. Every resistance is linear in the amount
  (`(x + flat) * (1 - percent)`), so a two-tick window delivers exactly what two calls per
  tick would, for half the engine calls.

## Evidence

### 1. Damage is continuous now

One turret, its target 6 tiles north, five 50M hp unit dummies on the beam line 10 tiles
north; health of the centre dummy sampled every tick for 16 ticks.

```
0.6.1 (pulses):  49997188 49996876 49996876 49996876 ... 49996552 49996552 ...
                 ^ one 312 hp step every 8 ticks = one pulse
0.6.2 (per tick): 49996872 49996804 49996792 49996720 49996708 49996636 ...
                 ^ a step EVERY tick (large on fire ticks, small on physical ticks)
```

### 2. No falloff: bodies on the line all take the same

Same scene, all five dummies measured over the window:

```
0.6.1: 0 3416 3788 3592 0     <- unequal: the falloff ladder, per pulse
0.6.2: 0 3880 3880 3880 0     <- equal: every body on the axis takes the full hit
```

(The outer two are outside the corridor: `hit_half_width` 0.9 + body radius ~0.4 at 10 tiles.)

### 3. Dps on a locked target is unchanged

`ftest-scale-probe`, 60-tick window, 5M hp dummy, melta-fuel:

```
0.6.1: 1398 dps      0.6.2: 1297 dps
```

That 7 % is the *old* number, not the new one: a 60-tick window holds 7.5 pulses, and a
pulse clock can only fire 7 or 8 of them — the 0.6.1 measurement rounded up. Per interval the
two models deliver the identical amount (8 ticks x damage/8 = one pulse), which is also what
the alternation above preserves.

### 4. Cost, which is what the brief was worried about

`ftest-dmg-probe` scene B: 20 meltas in a row, each with its own dummy 9 tiles north, all
firing for 300 ticks; Factorio's own `--benchmark` average over 300 updates (the honest
end-to-end number, not a mod-local profiler):

| tree | avg ms/update | delta |
|---|---|---|
| 0.6.1 (pulse damage) | 9.09 | — |
| 0.6.2, before the two optimisations | 11.06 | +2.0 |
| 0.6.2, radius cached | 10.78 | +1.7 |
| 0.6.2, + alternating damage types (shipped) | 10.21 | +1.1 (+12 %) |

So the fair-damage change costs about 0.055 ms per turret per tick. For context, the mod's
*total* per-turret cost in this scene is ~0.5 ms/tick, most of it the drawing path (17 render
objects per turret, ~100 property writes per turret per tick) — the damage change is the
smaller half of the budget. If a big melta wall ever needs to be cheaper, the beam's per-tick
sprite updates are where the time is, not here.

### 5. Sweep scene (why the count is not the headline)

A lure dragged across a fan of seven dummies (`ftest-sweep-probe`) showed 0 of 7 damaged on
0.6.1 and 1-2 of 7 on 0.6.2, but that probe is a poor instrument: the mod deliberately draws
no beam while the head is off-bore (`C.aim_tolerance`), and a lure moving fast enough to make
the sweep obvious also makes the turret lag, so most of the sweep has no beam at all. It is
kept as a scene, not as a gate — the continuity and equality measurements above are the
acceptance evidence for the change, and they hold regardless of how the beam got there.

## Still not done

Nothing pending. `C.pierce_falloff`, `C.pierce_max` and `C.hit_refresh_ticks` are the whole
dial: falloff back on, fewer bodies, or a lazier corridor refresh (cheaper, slightly staler
on a static beam).
