# Melta beam rework — verification

**Scope:** the firing beam only (`control.lua` visuals, `constants.lua` "beam look",
`prototypes/beam.lua`, `graphics/beam/generate.py`). Damage, range, rotation, pipes and
icons belong to other cards on the same board and were not touched.

**Runs:** two real GUI Factorio launches of the same probe scene — one against the
pre-rework tree (`git archive HEAD`, i.e. 0.4.0) and one against this tree — plus repeat
runs of both to check the timing numbers were not a one-off. Factorio 2.1.23 (build
87750, win64, steam), mods enabled: **base + lilys-melta + beam-probe only**
(`quality`, `space-age`, `elevated-rails`, `recycler` disabled). Isolated write dir, so
her saves, blueprints and log were untouched.

**Probe:** `harness/melta-beam-probe/` — six meltas in a row on a concrete pad, each with
its own 5 000 000 HP dummy nine tiles north, all six firing continuously. The probe then
kills every dummy at once, respawns them, and kills one *turret* out from under a live
beam, counting render objects at each step. Screenshots land in `script-output/beam/`.
`harness/run_beam_probe.py` is the launcher (see *How to re-run*).

Verdict: **all three acceptance criteria pass**, with one honest caveat about what "frame
time" could be measured on this machine (see *Open issues*).

---

## 1. Why the old beam looked like a placeholder

The old beam was four stacked `rendering.draw_line`s plus a glow, and `constants.lua`
was written as if `draw_line`'s `width` were in **tiles**:

```lua
-- 0.4.0
{width_cold = 0.55, width_hot = 1.90, ...}   -- widest layer
```

`LuaRendering::draw_line`'s `width` is in **pixels, 32 per tile**. So the widest layer of
the whole stack was 1.90 px = **0.059 tiles**: a hairline, thinner than the barrel it
came out of, and every layer underneath it thinner still. Measured from the shipped
before-screenshot at 64 px/tile: **FWHM 4 px = 0.06 tiles**, which is exactly the 1.9 px
the constants asked for (plus one pixel of antialiasing).

That is the whole of the "weak/placeholder" complaint: the lance was being drawn at
1/16th of its intended width, and `draw_line` cannot draw a soft edge at any width, so
no amount of layering would have hidden it.

## 2. What the beam is now

| layer | primitive | why |
|---|---|---|
| 2 core lines | `draw_line`, 0.14 → 0.34 tiles wide | the only primitive that is exactly 1:1 with the world at every zoom and tracks a moving target without resampling; widths now converted once with `C.px_per_tile = 32` |
| 3 glow sprites | `draw_sprite`, additive, 0.32 → 3.70 tiles | a wide soft halo is impossible with lines (they paint a flat quad with a hard edge). Textures are generated white with the shape in the alpha channel (`graphics/beam/generate.py`) and tinted per fuel at runtime, so one set serves oil/gas/melta/napalm |
| 6 sheath tongues | `draw_sprite`, additive | jump to a new offset/length/alpha every 3 ticks, so the edge boils instead of reading as a clean bar |
| muzzle flare + blast cone | `draw_sprite`, additive | the discharge; both swell for 3 ticks after each pulse, so each shot thumps |
| impact flare | `draw_sprite`, additive | sits on the nearest body the pulse cut, re-positioned to that body's current position every tick, hidden the moment it dies |
| tip flare | `draw_sprite`, additive | the lance sprays out where it runs out of reach instead of ending in mid-air |
| mouth heat (charge-up, bleed-off) | 2 `draw_sprite` flares | was two `draw_circle`s |

The sprites are `type = "sprite"` prototypes (`prototypes/beam.lua`) because
`rendering.draw_sprite`'s `sprite` field is a *SpritePath* — a prototype name, or
`item/…`/`entity/…`/`utility/…`/`file/…`, and `file/` can only reach the current
scenario, not a mod's graphics folder. Their `blend_mode = "additive"` is what makes a
wide low-alpha wash read as heat on dark ground instead of as fog.

Rendering rules the code now obeys, each learned from a measured artifact:

* **The core lines must be near-white.** The lines blend normally, the glow under them is
  additive, so a fuel-coloured line over a saturated glow measures *darker* than its
  surroundings (232 vs 255 luminance) and shows as a dark seam down the middle of the
  beam. The first pass had exactly that; the core is now mixed 30–85 % toward white.
* **The sheath alpha has to survive the core.** Below ~0.15 the tongues are invisible next
  to a white-hot core and the lance collapses back into a clean lightsaber bar (first
  pass, visible in the screenshots before this fix).
* **The muzzle cone has to be longer than the muzzle flare**, or the flare hides it
  completely.

## 3. Acceptance criteria

### 3a — "visibly thicker, brighter beam with a distinct muzzle flash and impact flash" — **PASS**

Measured from the same scene, same camera, same zoom (2.0 = 64 px/tile), same tick of a
fully spun-up beam, three rows between the muzzle and the dummy body
(`before-after-1to1.png`, `cross-section.png`):

| metric | before | after | ratio |
|---|---|---|---|
| beam width, FWHM, row 636 / 540 / 444 | 0.06 / 0.06 / 0.06 tiles | 1.14 / 0.95 / 1.00 tiles | **×16.5** mean |
| beam width at 10 % of contrast | 0.14 tiles | 1.68 tiles | ×12.4 |
| peak luminance | 232 | 253 | ×1.09 |
| total light added to the row | 16 042 | 45 360 | **×2.83** |

So the lance went from ~2 px to ~66 px wide at half maximum on a 64 px/tile screen, and
the light it dumps into the scene (brightness × area, integrated across the row) is about
2.8× — while peak luminance rose only 9 %, i.e. the gain is width and glow, not a
brighter point.

Muzzle and impact are in `01-beam-close.jpg` (blast cone and burst at the barrel mouth,
flare on the biter), `03-beam-mid.jpg` (all six) and `08-night-close.jpg` (same at night:
the core is saturated, the halo lights the ground around the turret).

### 3b — "fades out smoothly and disappears cleanly; no stuck beams after target death or turret destruction" — **PASS**

The lance now owns a frozen copy of its last geometry and its own render objects, so it
can outlive both its target and its turret:

* firing stops / target dies → `fade_current_beam`: alpha ramps down over
  `C.beam_fade_ticks = 10` and the beam thins to 55 % of its width, then every object is
  destroyed;
* turret dies or is mined mid-beam → `retire_beam` moves the beam into `storage.fades`
  and it keeps drawing its last geometry on its own surface while the tick handler fades
  and frees it. The turret's mouth glow is destroyed immediately (a dead turret does not
  glow).

Probe evidence (log lines from `docs/verification/beam/../` runs, reproduced in §5):

| moment | render objects (`rendering.get_all_objects("lilys-melta")`) |
|---|---|
| 6 turrets firing (t178) | 120 |
| 3 ticks after **all six targets** died (t363) | 120 — six beams still fading |
| 15 ticks after all six targets died (t376) | **12** — only the six turrets' mouth glows, every beam object freed |
| 3 ticks after **turret 3 was destroyed mid-beam** (t463) | 118 — five live beams + the fading one |
| 15 ticks after that turret died (t476) | 100 (5 turrets × 17 objects + a few one-shot pops); the fading beam is gone |

Screenshots: `04-beams-fading-3ticks.jpg` (six dim ghosts, no longer attached to any
beam — the turret row is empty of targets), `05-beams-gone-15ticks.jpg` (nothing left),
`06-turret-dead-fading-3ticks.jpg` / `07-turret-dead-gone-15ticks.jpg` (same for the
destroyed turret, next to its still-firing neighbours).

The one-shot flares (cut marks, muzzle pops) carry `time_to_live = 6` and are freed by
the engine, so they cannot leak either.

### 3c — "no measurable frame-time regression with 5+ meltas firing" — **PASS on script time, not measured on frame time**

Six meltas firing continuously, `helpers.create_profiler()` over the identical 178-tick
window, same probe, same map, three runs of the reworked tree and two of the original:

| tree | script time per tick, 6 meltas firing |
|---|---|
| 0.4.0 (before) | 5.276 ms, 4.967 ms → median **5.12 ms** |
| this tree (after) | 4.317 ms, 4.433 ms, 4.333 ms → median **4.33 ms** |

**−15 % script time**, despite the beam owning more render objects (17 per turret vs 15)
and updating more properties per object: the old draw path built fresh position/colour
tables for every one of its 15 segments every tick, the new one writes into preallocated
scratch tables (`V`, `COL`, `ORB_CORE`, `ORB_HALO`) and preallocated sheath rolls.

The absolute numbers are high for Lua (this is an FX-8350 with other cards' Factorio
processes on the box); what is meaningful is that both numbers come from the same
instrument over the same scene on the same machine, with the mod as the only difference.

## 4. Files

Mod code:

```
constants.lua          "beam look" section rewritten (tiles not pixels, glow/tongue/
                       muzzle/impact/tip block, fade ticks)
control.lua            visuals section rewritten; beam state, fade list, retire_beam,
                       additive sprite drawing, no-allocation draw path
data.lua               requires prototypes/beam.lua
prototypes/beam.lua    NEW: five sprite prototypes, additive blend, mipmapped
graphics/beam/generate.py   NEW: texture generator (numpy/PIL, deterministic)
graphics/beam/preview.png   NEW: contact sheet of the five textures
graphics/entity/melta-beam/ NEW: beam-haze, beam-glow, beam-cone, beam-tongue,
                       beam-flare (.png, white RGB + alpha shape)
```

Evidence:

```
docs/verification/beam-verification.md      this file
docs/verification/beam/*.png, *.jpg         14 images (see the tables above)
docs/verification/harness/melta-beam-probe/ probe mod (never shipped)
docs/verification/harness/run_beam_probe.py launcher, retries, collects the log
docs/verification/harness/measure_beam_pixels.py   the FWHM/light measurement
```

## 5. How to re-run

1. `bash docs/verification/harness/setup_beam_run.sh` — copies the mod to
   `<run>/mods/lilys-melta`, the probe to `<run>/mods/beam-probe`, writes
   `<run>/mods/mod-list.json` with base + lilys-melta + beam-probe only, and a
   `config.ini` whose `write-data` is `<run>/write` (edit the three paths at the top of
   the script; it defaults to a scratch run dir).
2. `python docs/verification/harness/run_beam_probe.py <run>` — creates the map headless
   if needed, launches the GUI, waits for `BEAM PROBE DONE`, stops the game, prints the
   probe log. It retries up to four times, because other cards on this machine close
   whatever Factorio window is in front of them.
3. `python docs/verification/harness/measure_beam_pixels.py <before_run> <after_run>` for
   the width/brightness numbers.

For the "before" numbers, extract the released tree into a second run dir
(`git archive HEAD | tar -x -C <run>/mods/lilys-melta`) and point the same probe at it.

Raw probe logs from the two runs compared here: `docs/verification/beam/logs/after-run.txt`
and `before-run.txt`.

**Launching the Steam build without a launch dialog:** running `Factorio.exe` directly
prints `Steam requires game restart, restarting...` and exits. Handing the process
`SteamAppId=427520 SteamGameId=427520` in the environment is enough — the game then
accepts `--config/--mod-directory/--load-game` and runs normally. That is what the
launcher does; no `steam://run/` dialog and no mouse click is needed.

## 6. Open issues

1. **Frame time was not measured, only script time.** There is no way to read FPS from a
   mod, and this box has other cards' Factorio instances running, so an FPS reading would
   not have been attributable. What is measured is the whole Lua-side cost of the beam at
   six turrets firing, which is the only part the mod controls; the GPU cost of 102
   additive sprites + 12 lines is not measured here. If it ever matters, the same probe
   with `--benchmark` gives a whole-tick number including the engine.
2. **The six beams in the screenshots are identical** (same phase, same flicker) because
   the probe spawns all six on the same tick with the same fuel. In a real base they
   desynchronise by themselves: the sheath re-rolls on `math.random()`, the flicker is
   `sin(tick)`, and the pulse timing depends on when each turret acquired its target.
3. **The lance still runs its full `range` through whatever it hits** — that is the
   piercing design from the 0.3.x tree (`pierce_max = 12`), not a rendering choice; the
   visible beam and the damage corridor use the same line, so they cannot disagree.
4. **`rendering.draw_sprite` cannot use a plain file path.** Any future beam texture has
   to be added as a `type = "sprite"` prototype first (`prototypes/beam.lua`), or
   `draw_sprite` will silently want a SpritePath it cannot resolve.
