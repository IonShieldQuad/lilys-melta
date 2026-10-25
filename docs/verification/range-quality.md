# Melta range, quality scaling and head rotation — measured

Headless runs on **Factorio 2.1.23**, isolated `--config` / `--mod-directory` under
`hermes/cache/scratch`, so her install, saves and `factorio-current.log` were untouched.
Probe mod: `docs/verification/harness/melta-range` (never shipped). Every number below
comes out of the run logs, not out of the code.

The probe is run three ways:

| env | tree | what it answers |
|---|---|---|
| `melta-head` | `git show HEAD:<file>` of every file this card touched | the "before" side (range 12, `rotation_speed` 0.006) |
| `melta-new` | the working tree | the "after" side |
| `melta-noquality` | the working tree, **quality mod disabled** | no crash and a flat 16-tile ladder when quality is absent |

Each run is `--create save.zip` followed by `--benchmark save.zip --benchmark-ticks 320`,
and all five scenes are 70 tiles apart — a turret's `call_for_help_radius` is 40, and a
shooting turret hands its target to every turret inside that radius *regardless of range*,
so closer scenes would report targets the engine could not actually see.

## Scenes

| scene | turret | body | what it proves |
|---|---|---|---|
| A | normal | 15 tiles / 19 tiles north | 16-tile reach engages 15, not 19 |
| B | legendary | 19 / 23 / 27 tiles north | quality's reach engages 19 **and** 23 (pierced, 82 % falloff), not 27 |
| C | normal | one body, teleported north → south | 180° swing time, logged per tick |
| D | rare | 12 tiles north, turret mined at tick 200 | unregister path, no null reference after |
| E | `melta-overclocked` (test quality, `range_multiplier` 3) | 30 tiles north | the clamp: engine would reach 48, the beam stops at 24 and refuses a body it cannot cut |

## Results

**Range.** Engaged = the body's health actually fell (the beam's `entity.damage()`);
untouched bodies drift *up* ~0.8 per 60 ticks from the spawner's absorption, which is why
the untouched column rises above 100 000 instead of sitting still.

| scene | body at | before (HEAD, range 12) | after (range 16) |
|---|---|---|---|
| A | 15.0 | 100 004.6 — never engaged | 98 829.3 — engaged |
| A | 19.0 | 100 004.6 — never engaged | 100 004.6 — untouched |
| B legendary | 19.0 | 100 004.6 — never engaged | 98 829.3 — engaged |
| B legendary | 23.0 | 100 004.6 — never engaged | 99 060.8 — engaged (pierce falloff) |
| B legendary | 27.0 | 100 004.6 — never engaged | 100 004.6 — untouched |
| E overclocked ×3 | 30.0 | — | 100 004.6 — untouched (clamped beam) |

**Quality scaling is the engine's, not the mod's.** `LuaQualityPrototype` exposes
`range_multiplier` (measured: normal 1.0, legendary 1.5) and the engine applies it to a
turret's `attack_parameters.range` for acquisition *and* firing. Proof on the *pre-change*
tree, where the mod itself does nothing about range: a quality × distance ladder (turrets
100 tiles apart) showed

| quality | level | furthest body the engine alone acquired |
|---|---|---|
| normal | 0 | 13 |
| uncommon | 1 | 15 |
| rare | 2 | 15 |
| epic | 3 | 17 |
| legendary | 5 | 19 |

with the base prototype range still at 12 — a 1.1 / 1.2 / 1.3 / 1.5 multiplier ladder,
measured, not assumed. That is why this card does not hand the engine targets: the engine
already reaches; the script only has to draw the beam to the same distance and clamp it.

**Rotation.** Tick-by-tick orientation across the 180° swing:

| tree | `rotation_speed` | ticks for 180° | wall clock |
|---|---|---|---|
| HEAD | 0.006 turns/tick (2.16°/tick) | **84** | 1.40 s |
| this card | 0.03 turns/tick (10.8°/tick) | **17** | 0.28 s |

The measured per-tick step is 0.03 (`ori` drops 0.97 → 0.94 → … → 0.50 and then stays),
so the value in `constants.lua` is the value the engine uses.

Why 0.03: staying on a target needs `v / (2πr)` turns per tick. A behemoth biter moves
0.3 tiles/tick, so at 4 tiles it needs 0.012 turns/tick — the old 0.006 could not do it
(that is the "trailing at short range" complaint), while 0.03 keeps a 2.5× margin there
and a 10× margin at 16 tiles. A half turn in 0.28 s is also twice as fast as a vanilla gun
turret (0.015), which is what "snaps to new targets" feels like.

**Robustness.**

* `melta-noquality` (quality mod off): the whole run is clean, every turret reads
  `quality=normal`, `range_multiplier=1`, and the 15/19/12-tile bodies behave exactly as
  the normal-quality scene above. No null references.
* Scene D mines an actively-firing turret at tick 200 (`LuaEntity::mine`, which raises
  `script_raised_destroy`); the mod's unregister path cleared its state and the remaining
  120 ticks logged no error. Log: `mine tick=200 unit=19 fluid=386 / mined; valid_now=false`.
* Scene E's `melta-overclocked` quality (multiplier 3 → 48 tiles) is clamped: the beam
  stops at 24 and the turret does not draw a beam at a body it cannot reach.
* Whole run: `grep -icE 'error|traceback'` = **0** in all three envs.

## What is not covered here

The inspect pane / tooltip line ("a newly built melta shows range 16") needs the GUI: a
headless run never initialises the renderer and tooltips need a real mouse hover. The
quality-scaled number in that tooltip is the engine's own (same `range_multiplier` the
table above measures), so the remaining risk is presentational, not behavioural — it
belongs to the in-game verification pass (`t_e17c7b8c`). Checklist for it:

1. build a normal melta, hover it: **Range 16**;
2. build an uncommon / rare / epic / legendary melta, hover each: Range 16 → ~17.6 → ~19.2
   → ~20.8 → **24** (the game rounds the displayed number itself);
3. put a biter exactly 16 tiles from a normal melta and one 20+ from a legendary: both must
   be engaged at that distance;
4. watch a target jump bearings: the head should cross 180° in about a quarter second.

## Reproducing

```bash
# from the repo
bash ~/stage.sh new        # or head / noquality  (see this card's workspace)
W=C:/Users/Lily/AppData/Local/hermes/cache/scratch/melta-new
"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe" \
  --config "$W/config.ini" --mod-directory "$W/mods" --create "$W/save.zip"
"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe" \
  --config "$W/config.ini" --mod-directory "$W/mods" \
  --benchmark "$W/save.zip" --benchmark-ticks 320
grep "\[range\]" "$W/write/factorio-current.log"
```
