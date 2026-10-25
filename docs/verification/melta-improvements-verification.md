# Five melta workstreams — combined in-game verification pass

**Tree under test:** `f5aa887` (`docs: quote the port-overlap numbers the gate actually printed`),
clean worktree, **lilys-melta 0.5.0**.
**Mods enabled together:** base 2.1.23, **space-age**, **quality**, **recycler**,
**elevated-rails**, lilys-melta — i.e. the asteroid channel and quality scaling were loaded
in the same run, which none of the five work cards did on its own.
**Runs (one isolated scratch env, her install/saves/log never touched):**

| run | what it did |
|---|---|
| GUI (Factorio 2.1.23, real window) | 5 inspect-panel legs (normal → legendary), 27 scheduled screenshots, 5000 ticks of play |
| headless `--create` | built the scene (saves only ever come from here) |
| headless `--benchmark 18000` ticks | **5 minutes of continuous firing**, profiler window A (beams firing) and B (same scene, beams idle), full log sweep |

**Verdict: all five workstreams PASS individually and together, 0 error lines in all three
runs.** Two observations are recorded at the end; neither is a defect and neither blocks
shipping. No mod code was changed by this card.

The scene (`harness/melta-combined`) is one map with five regions so that the workstreams
cannot pass on their own: a quality row (5 qualities), the pipe rig (four-way, one-sided,
straight/L/T/cross/dead-end), six meltas cutting 1e6-hp dummies (3 light oil, 3 melta fuel),
four asteroids, and a reach/rotation rig.

---

## 1. Pass/fail checklist

### 1a. Pipe visuals (`t_3d5ee7b2`) — **PASS**

| check | result | evidence |
|---|---|---|
| offline gate on this tree | **PASS** `pipe_join.py --check` exit 0 | port reach 1.95 / 1.85 / 1.74 / 1.97 tiles (N/E/S/W) vs the pipe sprite's own near edge 1.52 / 1.50 / 1.19 / 1.52 → overlap **+0.43 / +0.35 / +0.55 / +0.45**, `seam 0`; cap adds 160 / 73 / 134 / 72 px of plate |
| plumbing is real, not just art | **PASS** | four-way turret `connections=4`, buffer 205.7; one-sided turret `connections=4` (4 physical ports), buffer 202.0 as built |
| four joins read pipe → socket | **PASS** | `pipes/02-four-way.jpg`, `03-join-north`, `04-join-east`, `12-join-south`, `13-join-west` — no bare floor on any side |
| south join under the hull shadow | **PASS** | `12-join-south.jpg` (zoom 4.0): collar seated, no floor between pipe end and socket |
| west socket vs the vent block | **PASS** | `13-join-west.jpg` (zoom 4.0): pipe enters a flange on the vent block, no bare floor |
| bare ports are blanked, not hollow | **PASS with a legibility note** | `05-capped-ports.jpg`, `15-capped-port-north.jpg`; the shipped composite `docs/pipe-join/north-cap-2x.png` shows a bolted plate touching the hull. At 4× a vision read calls the dark plate an open bore — see observation **N1** |
| straight / L / T / cross / dead-end | **PASS** | `06-shapes.jpg`: all five meet with correct junction pieces, dead end capped (`07`–`11`) |
| normal play zoom | **PASS** | `14-normal-zoom.jpg` (zoom 0.8): both meltas read as plumbed, no gap at any join |

### 1b. Range, quality scaling, rotation (`t_70ef9102`) — **PASS**, and the panel question is answered

| check | result | evidence |
|---|---|---|
| inspect pane, normal quality | **PASS — `Range: 16.0`** (was 12) | `panels/panel_normal.png` |
| inspect pane, quality | **PASS — 17.6 / 19.2 / 20.8 / 24.0** for uncommon / rare / epic / legendary | `panels/panel_uncommon.png` … `panel_legendary.png` |
| …so the panel *does* show the engine-scaled value | **PASS** | the prototype stays `range=16` for every quality (`create.log`); the engine applies `range_multiplier` 1.1/1.2/1.3/1.5 and the panel prints 17.6/19.2/20.8/24.0. The open question from `t_70ef9102` ("might an engine display quirk show an unscaled 16") is answered: it shows the scaled number |
| normal melta reaches 15 but not 19 | **PASS** | dummy at 15 tiles: first damage tick 38; dummy at 19 tiles (perpendicular, out of the beam corridor): `hits=false` for the whole run |
| legendary reaches 23 but not 27 | **PASS** | dummy at 23 tiles: first damage tick 18; dummy at 27 tiles: `hits=false` |
| …still true after 5 minutes | **PASS** | same four lines at `t=17400` |
| 180° swing | **PASS — 16 ticks (0.27 s)** | target teleported from 4 north to 4 south: `swing ARRIVED after 16 ticks`, vs 84 ticks (1.4 s) before the card |
| tracks a fast crossing target | **PASS** | target crossing at **0.3 tiles/tick** 4 tiles from the turret: max aim deviation **0.0297 turns = 10.7°**, i.e. one rotation step — it never trails more than a step |

### 1c. Damage tooltip / inspect description (`t_ab5fadef`) — **PASS**

| check | result | evidence |
|---|---|---|
| bogus engine Effect line gone | **PASS** | the panel has no `Damage: 0.09/s Fire + 0.02/s Physical` block any more (`panels/panel_normal.png`) |
| description present on entity and item | **PASS** | panel prints "…Range 16 tiles at normal quality, further as quality goes up (24 at legendary)… Damage: 14 per pulse on a cold barrel, 56 at full intensity (85 % fire, 15 % physical) … 105 to 420 per second … 82 % … up to 12 bodies … x1.00 / x0.85 / x1.60 … Rocks and asteroids also take an explosion hit at 160 % of the pulse." |
| stated damage = dealt damage | **PASS** | measured on an unarmoured 1e6-hp dummy, per pulse: **17.63 → 19.88 → 22.13 → 24.31 …** (the stated `14 + 42·charge` ramp), steady median **56.00** on light oil and **89.63** on enriched melta fuel (= 56 × 1.60, exactly the stated multiplier) |
| numbers do not drift from `constants.lua` | **PASS** | both the text and the damage come from the same constants; the pipe/range/beam cards changed neither |

### 1d. Beam VFX and fade-out (`t_f066608b`) — **PASS**

| check | result | evidence |
|---|---|---|
| visible beam, core + glow | **PASS** | `beam/02-close-lightoil.jpg`, `03-close-meltafuel.jpg`: white-hot core inside a wide tinted glow, ~1 tile at half maximum, clearly wider than the barrel |
| muzzle and impact flash | **PASS** | `beam/02-close-lightoil.jpg` (muzzle burst + blast cone), `asteroids/03-big-cut.jpg` (impact flare on the rock) |
| fuel tint | **PASS** | `beam/05-six-wide.jpg`: three orange (light oil) + three green (enriched melta fuel) beams, same shape, different colour |
| several at once | **PASS** | `beam/05-six-wide.jpg`: six turrets, six beams, no phase lock visible |
| beam length follows range and quality | **PASS** | `reach/02-legendary-23.jpg`: a legendary melta's beam runs the full ~23 tiles to its target (old reach was 12) |
| clean fade, nothing stranded | **PASS** | destroy all six targets: **188 → 86 render objects after 15 ticks → 77 (the idle baseline) at tick 4900**; `beam/06-fade-gone.jpg` shows no leftover streak |
| no leak over 5 minutes | **PASS** | object count is **188 at t=2400 and still 188 at t=17400** with all six beams firing the whole time |

### 1e. Asteroid / physical damage channel (`t_3bfcae3b`) — **PASS**

| target | before (parent card) | this pass | verdict |
|---|---|---|---|
| small metallic, 100 hp | 11 pulses (2.20 s) | **3 pulses, 45 ticks (0.75 s)** | PASS |
| medium metallic, 400 hp | 31 pulses (5.77 s) | **7 pulses, 83 ticks (1.38 s)** | PASS |
| big metallic, 2000 hp | **never** (236 pulses, 0.14 hp) | **21 pulses, 201 ticks (3.35 s)** | PASS |
| huge metallic, 5000 hp | never | **still alive after 5 minutes** — unchanged by design ("railgun work") | PASS (expected) |

`asteroids/03-big-cut.jpg` shows the beam visibly biting the big rock with an impact flare.
Pulse counts here are *higher* than the parent card's because this probe samples health
**every tick** (the earlier probe sampled every 10 ticks and undercounted); the kill ticks
agree exactly (small 45/42, medium 83/80, big 201/198 ticks on the two probes).

---

## 2. Did they regress each other? — **no**

| cross-check | result |
|---|---|
| all five load together (space-age **and** quality **and** the pipe art) | PASS — 0 error lines in `logs/create.log` |
| pipes still feed the turret while it is firing | PASS — fluid draw 18.75/s, buffers held through 18 000 ticks of firing |
| new range does not break the beam drawing | PASS — the drawn lance reaches 23 tiles for a legendary turret |
| tooltip survived the beam/pipe/range changes | PASS — 56.00 / 89.63 measured against the same text |
| quality row (5 comps) coexists with the asteroid channel | PASS — all five qualities spawn and fire normally |
| 5-minute log sweep, active firing + plumbing | **PASS — 0 `Error`/`lua` exception lines** (650 probe log lines, 300 s of game time) |
| GUI run log | **PASS — 0 error lines**, atlas accepted every sprite |

## 3. Performance with several meltas firing

Measured with `helpers.create_profiler()` on the same scene, 300-tick windows, headless
benchmark (unlocked tick loop, so the number is real script time):

| window | turrets firing | ms/tick |
|---|---|---|
| A — beams firing | 10 (6 beam + huge rock + normal-15 + legendary-23 + rotation) | **4.41** |
| B — the six beam targets removed | 4 | **2.01** |
| difference | 6 beams | **2.41 → 0.40 ms/tick per firing beam** |

That is ~26 % of a 60 fps frame budget for ten simultaneously firing meltas — the same
order as the beam card's 4.33 ms figure for six of them. In the GUI run at 1× speed the
game simulated 5000 ticks in ~110 s wall clock (**≈60 ticks/s, real time**) with ten
turrets firing and 194 render objects, i.e. no visible slowdown.

**Not measurable:** frame rate itself. Factorio exposes no FPS API and no benchmark metric
reads it; the ticks/s figure above is the closest honest proxy.

## 4. Observations (not defects, nothing to fix before shipping)

* **N1 — capped port legibility.** The blanking plate is present and correctly seated
  (offline composite `docs/pipe-join/north-cap-2x.png`: plate touching the hull, +73…160 px
  of plate over the open variant), but its face is nearly as dark as the bore, so at 4× a
  fresh eye can read "open hole + floating disc". If she wants it unambiguous, brighten the
  plate face ~10 % or put one bolt highlight on it — `graphics/_blender/pipe_port.py`, cap
  variant only. Art unchanged since `efd1e7c`; this pass did not make it worse.
* **N2 — the panel's Range is the *effective* range, the prototype field is not.** In the
  inspect pane a legendary melta reads `Range: 24.0` while
  `prototypes.entity["melta-turret"].attack_parameters.range` stays 16 for every quality
  (the engine multiplies at runtime). Anything else that wants the effective range must
  read `entity.quality.range_multiplier`, not the prototype field.
* **Harness artifact, stated so nobody re-shoots it:** `asteroids/01-overview.jpg` and
  `02-small-cut.jpg` were taken 2 and 45 ticks after the display rocks were respawned, so
  they caught the turrets before re-acquisition / after the small rock was already dead.
  `03-big-cut.jpg` is the frame that shows the cut. Not a mod behaviour issue.

## 5. What this pass did not close

* **Frame rate** (see §3) and **sound** — no measurement path on this machine.
* **Huge asteroid kill** — not run to death (≈8 min of continuous beam); it survived the
  whole 5-minute run, which is the designed outcome.
* **Rocket/promethium asteroids** — the space-age ladder was sampled at the four metallic
  sizes only, as in the parent card.

## 6. Files

Mod code: **none changed.** Evidence added:

```
docs/verification/melta-improvements-verification.md   (this report)
docs/verification/in-game-combined/   panels/ (5), pipes/ (15), beam/ (7), reach/ (2),
                                      asteroids/ (3), logs/{create,gui2,long-run}.log,
                                      logs/measurements.txt (the numbers quoted above)
docs/verification/harness/melta-combined/{info.json,data.lua,control.lua}
docs/verification/harness/setup_combined_run.sh
docs/verification/harness/run_combined.py        create / benchmark driver
docs/verification/harness/hover_combined.py      GUI run + inspect-panel capture
docs/verification/harness/crop_panels.py         panel/world crops out of a desktop grab
docs/verification/harness/zoom_crop.py, floor_map.py   pixel inspection helpers
docs/verification/harness/collect_evidence.py    assembles the folder above
```

Reproduce:

```bash
bash docs/verification/harness/setup_combined_run.sh                 # isolated env
python docs/verification/harness/run_combined.py <run> --create-only # build the scene
python docs/verification/harness/hover_combined.py <run> <out> 5     # GUI: panels + shots
python docs/verification/harness/run_combined.py <run> --benchmark-only --ticks 18000
```

The Steam build needs `SteamAppId=427520 SteamGameId=427520` in the environment for a direct
launch (the scripts set it); screenshots land in `<run>/write/script-output/combined/`.
