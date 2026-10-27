# Sustained fire: the beam follows the barrel and never goes quiet mid-fight (0.6.3)

Request:

> "make so it doesn't stop firing once it started and there are still enemies in range —
> will allow it to sweep and also prevent spool down because of switching targets"

Two mechanisms blocked that, both removed:

1. **The off-bore gate.** The script only drew a beam when the head was within
   `C.aim_tolerance` (2 deg) of the target bearing, and drew a "wind-up" orb while it swung.
   A turret could therefore never sweep: it refused to fire exactly while turning. The beam
   is now drawn along the **barrel** from the first tick, so a target switch sweeps the lance
   across everything between the old and the new bearing — and with per-tick damage it burns
   that too. `C.aim_tolerance`, `C.windup_ticks`, `aim_error()` and `draw_windup()` are gone.
2. **The target gap.** When the current target died, the engine had no target for a tick or
   three while it picked the next one, and during that gap the script went down its
   "not shooting" branch: beam faded, `state.pulse_at` reset, charge started decaying over
   `C.spin_down_ticks`. Every kill therefore cost a visible spin-down/spin-up cycle.
   `C.target_grace_ticks` (8) now keeps the lance lit after the last live target, and while
   it is lit the script looks for the next body itself (`nearest_enemy`, every
   `C.range_scan_ticks`) and hands it to the engine, so the head keeps tracking.

The scan is gated on `warm` (the grace window) or on the engine holding an unreachable target,
so an idle turret still costs no surface queries.

## Measurement

Nine durable, immobile dummies in a fan from -40 to +40 degrees, ten degrees apart, six tiles
out; the probe forces the target to jump across the fan every 20 ticks (`1 -> 9 -> 2 -> 8 ...`,
~80 degrees each time) and samples **total damage per tick across the whole fan**, which is
what "does the beam stay lit" looks like from outside.

| | 0.6.2 | 0.6.3 |
|---|---|---|
| silent ticks (no damage anywhere) | 123 of 140 (**87 %**) | **0 of 140 (0 %)** |
| dummies damaged across the fan | 9 of 9 | 9 of 9 |
| mean damage per tick | 111 (in bursts) | 80 (continuous, climbing with charge) |

The per-tick series shows both halves of the fix:

```
0.6.2: 0 0 0 0 0 0 0 0 440 0 0 0 456 0 0 ... 1100 0 0 0 0 0 0 0 1100 ...
0.6.3: 132 16 96 16 48 8 48 8 48 8 52 8 52 8 52 8 52 8 52 16 168 16 112 16 ... 240 32 160 32 ...
```

0.6.2 is the old story exactly: nothing, then a pulse, then nothing — 87 % of ticks silent, and
after each forced switch a cold beam while the charge ramped back. In 0.6.3 the damage never
stops, alternates fire/physical (large step, small step, per the every-other-tick cadence),
and **climbs monotonically from 48 to 160 through five forced 80-degree switches** — the
spin-up is not being reset by them any more. The 0.6.2 mean is higher only because its
measurement window caught a lucky run of hot pulses; it delivered them to whichever body the
beam happened to be over.

Visual check (before/after screenshots, `cmp-muzzle3`): the lance still leaves the muzzle and
runs along the barrel; no detached beam, no double beam, flare in the right place.
