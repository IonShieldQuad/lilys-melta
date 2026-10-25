# Melta rework — end-to-end verification report

**Tree:** `97a327b` (melta: de-squash the hull so the north and south pipes meet it), clean
worktree, mods enabled: **base 2.1.23 + lilys-melta 0.4.0 only** (space-age, quality,
elevated-rails and recycler explicitly disabled in `mod-list.json`).
**Game:** Factorio 2.1.23 (build 87750, win64, steam), single player, generated map
(`--create`, default settings), scene built on a concrete pad far from the crash site.
**Runs:** one normal Steam GUI launch (screenshots), three headless runs (regression,
save/reload, determinism). Logs and screenshots in this folder; probe mods in `harness/`.

Verdict: **7 of 7 acceptance items pass**, with four honest caveats and two things that
could not be verified on this machine (see *Open issues*). No mod code was changed by
this card.

---

## 1. Launch, log hygiene, feed, kill

| check | result | evidence |
|---|---|---|
| loads with base + this mod only | **PASS** | `logs/gui-run.txt` — `Loading mod base 2.1.23 (data.lua)`, `Loading mod lilys-melta 0.4.0 (data.lua)`, `… (data-updates.lua)`, `[lilys-melta] fuels accepted: light-oil, petroleum-gas, melta-fuel`; nothing else loaded |
| no missing sprites / atlas complaints | **PASS** | 96 `Created an atlas bitmap` lines, **0** `Failed to load`, **0** `Can't load`, and no other error/warning line from the mod in the whole GUI log |
| icons accepted by the atlas | **PASS** | same run — this is the GUI-only proof the icon card could not produce headlessly |
| sounds load | **PASS** | `[Audio] Driver:wasapi, Device:Default device` then `Loading sounds...`, no sound errors |
| turret places and takes fluid from pipes | **PASS** | probe log: `pipe connections: 4`; turret fluid `0.0 → 103.5` after filling the four pipes with 100 each |
| needs ammunition? | **PASS (none)** | `turret_ammo inventory: none` — the fluid turret has no ammo slots; fluid is the only input, as designed |
| refuses to fire without fuel | **PASS** | `status with no fuel: 29` (no-fuel status) at tick 10; `status 1` (working) once filled |
| kills biters | **PASS** | 3 `small-biter`s spawned 4/5/6 tiles up the beam line at t45: `live biters: 0` at t60 and t79. (One biter survived a 25-tick window in the headless run — biters walk out of a 0.9-tile-wide line; not a defect.) |

## 2. Acceptance list

### 2a — turret is 2-3x bigger, matches base-turret scale in a side-by-side shot — **PASS**

`in-game/01-scale-row.jpg` (melta, gun turret, flamethrower turret, laser turret, same
zoom, all facing north). Measured from the shipped sprites at the declared `scale = 0.5`
and 32 px/tile, opaque silhouette:

| sprite | silhouette |
|---|---|
| melta base + head | **3.17 × 3.12 tiles** |
| vanilla gun turret | 1.78 × 1.73 tiles |
| vanilla laser turret | 1.50 × 1.44 tiles |

That is **1.8x linear and 3.2x silhouette area** against the gun turret (2.1x / 4.6x
against the laser turret). So "2-3x" holds for visual mass and area; linearly it is 1.8x.
It dominates the row in the screenshot, which is what the item asks for.

### 2b — reads rusty/industrial, not clean sci-fi — **PASS**

`in-game/02-melta-closeup.jpg` and `detail/pipe-join-1to1.png`: dark weathered gunmetal
plating with soot in the crevices, rust-brown streaks, tarnished brass collars on the
barrel, exposed rivets and ribs, a dull bare-metal edge highlight. No gloss, no neon
casing, no streamlined sci-fi surfaces. Nothing in the sprite reads as broken art: no
transparent holes, no rectangular sprite edge, the cast shadow is baked into the base and
sits under the machine.

### 2c — pipes connect visually from all four sides — **PASS**

Four pipes at ±2.0 tiles are present in every shot and every one of them is a working
fluid neighbour of the turret (`get_fluid_box_pipe_connections` reports 4, fuel arrives
from all four). The collar meets the hull on every side in the 1:1 crop
`detail/pipe-join-1to1.png`, and `in-game/03-pipes-overview.jpg` shows no bare strip of
ground on any of the four sides.

Measured with `python graphics/_blender/pipe_sockets.py --check`, which compares the
hull's opaque extent with the pipe sprite's *near edge* inside the ±0.5 tile band around
each pipe axis. (An earlier pass here assumed a 1.5-tile mouth on all four sides and read
a 0.23-tile south gap out of that; that is wrong for the vertical pipes, whose raised rim
and baked shadow project inboard on the screen's vertical axis.)

| side | hull | pipe near edge | gap (alpha ≥ 8) | gap (alpha ≥ 200) |
|---|---|---|---|---|
| north | 1.38 | 1.50 | 0.12 | 0.14 |
| east | 1.64 | 1.50 | −0.14 | −0.02 |
| south | 1.28 | 1.19 | −0.09 | 0.02 |
| west | 1.53 | 1.50 | −0.03 | −0.02 |

Positive = bare ground. The largest residual is north's 0.12-0.14 tiles; vanilla
`assembling-machine-2`, with the same ±1.2 collision box, leaves 0.22 on its own north
side. Not a defect.

### 2d — turret, item and mod-list icons are correct and sharp — **PASS, with a legibility caveat**

*The technical contract holds:* both icons are loaded into the atlas by the game with no
complaint (see 1), the item icon is drawn in-world at its real size in
`in-game/04-icon-row.jpg` / `detail/item-icons-1to1.png` (rusted circular emplacement,
transparent background, no black box, no clipping, no magenta), and `thumbnail.png`
(512²) + `thumbnail-144.png` (144²) are the files the mod list shows.

*Measured at GUI sizes* (`icon-sheet-native.png`, `icon-sheet-6x-nearest.png`; base
square of each file, LANCZOS to 64 px and 32 px, luminance on opaque pixels):

| icon | px | mean | p10 / p50 / p90 | sharpness (‖laplacian‖/contrast) |
|---|---|---|---|---|
| melta | 64 | 86.7 | 19 / 73 / 174 | 1.93 |
| vanilla gun | 64 | 83.3 | 19 / 75 / 157 | 1.20 |
| vanilla laser | 64 | 83.3 | 19 / 71 / 164 | 1.05 |
| melta | 32 | 86.8 | 28 / 83 / 151 | 1.94 |
| vanilla gun | 32 | 83.8 | 26 / 77 / 152 | 1.70 |

So the tone register matches vanilla and the icon is *denser* in high-frequency detail
than vanilla — it is not blurred or badly downscaled. **Caveat:** at 32 px that density
reads as a busy rust-coloured disc rather than an instantly recognisable turret; vanilla
keeps bolder masses and more negative space. That is the limitation already recorded in
`DESIGN.md` (needs fewer, larger model plates — a model change, not another icon pass),
and it is why this item is a PASS on "correct and sharp" and not on "reads at a glance".

### 2e — damage is fire + a minor physical slice, no `thermal` anywhere — **PASS**

`grep -rn thermal --include=*.lua --include=*.cfg .` → one hit, prose in
`locale/en/locale.cfg:5`. The damage itself is split in two places, both fire-first:

* `control.lua:295` `victim.damage(dealt * (1 - C.physical_share), force, C.damage_type, turret)`
* `control.lua:298` `victim.damage(dealt * C.physical_share, force, C.damage_type_hit, turret)`
* `prototypes/melta.lua:78-79` the engine-side contact hit carries the same 0.85/0.15 split
* `constants.lua:21-23` `damage_type = "fire"`, `damage_type_hit = "physical"`, `physical_share = 0.15`

`git diff 700b897..HEAD -- constants.lua control.lua prototypes/melta.lua` shows **no**
damage arithmetic changed since the damage card measured it, so its numbers still stand:
89.59 / 13.44 / 77.44 damage per pulse against a plain / 100 % fire-immune /
behemoth-armoured target at 1.6x fuel.

### 2f — firing sound is louder, no clipping with several turrets — **PASS on "louder", not measurable by ear**

Measured with `ffmpeg astats` on the shipped files:

| file | peak | RMS | effective in the mix (× volume 0.7) |
|---|---|---|---|
| `sound/melta-burn.ogg` (loop) | −1.62 dBFS | −15.25 dBFS | **−18.35 dBFS** |
| `sound/melta-start.ogg` | −0.92 dBFS | −11.55 dBFS | −14.65 dBFS |
| `sound/melta-stop.ogg` | −1.87 dBFS | −19.59 dBFS | −22.69 dBFS |

For reference the vanilla flamethrower loop sits at −13.2 dBFS × 0.5 = −19.2 dBFS, so the
melta loop is now **~1 dB louder than a vanilla flamer loop** and ~15 dB louder than its
own previous version (−33.3 dBFS in the mix). All three cues carry
`aggregation = {max_count = 2, remove = true, count_already_playing = true}`, so a wall of
turrets behaves like at most two voices. Worst case for clipping is two identical loops in
exact phase: −4.7 dBFS per voice + 6.0 dB = **+1.3 dBFS** (would clip); two loops started
at different ticks sum incoherently at about −1.7 dBFS. **Not verified:** what the engine's
mixer actually outputs — this machine exposes no loopback/Stereo Mix device, and I cannot
listen. That is the one part of 2f a machine cannot close.

### 2g — beam only fires after the turret has rotated, and starts at the muzzle in all directions — **PASS**

The probe logs the head's real orientation each time it takes a picture. Mid-swing frames
(nothing drawn down the barrel, charge glow only) vs on-target frames (lance drawn):

| tick | state | orientation | lance along the axis |
|---|---|---|---|
| 80 | north, aligned from the start | 0.0000 turns | **yes**, first bright pixel 1.48 tiles from the pivot (`C.muzzle_forward` = 1.512) |
| 98 | 8 ticks into the turn to the east | 0.0240 turns | **no** (peak brightness along the axis 218, below the lance's 244) |
| 145 | east, arrived | 0.2500 turns | **yes**, from the muzzle, no gap |
| 158 | mid-turn to the south | 0.2920 turns | **no** (peak 219) |
| 205 | south, arrived | 0.5000 turns | **yes**, starts close to the housing — correct: the south muzzle projects to 0.39 tiles from the pivot |
| 218 | mid-turn to the west | 0.5120 turns | **no** (peak 235) |
| 265 | west, arrived | 0.7500 turns | **yes**, from the muzzle, no gap |

Screenshots: `07-windup-east.jpg`, `09-windup-south.jpg`, `11-windup-west.jpg` (no lance,
glow at the mouth) next to `05/08/10/12` (lance, aligned). This is the visual side of the
numeric proof in `t_bd3af40c` (muzzle anchor verified against Blender's camera for all 64
directions and against every shipped frame).

## 3. Regressions

| check | result | evidence |
|---|---|---|
| **rotation (`R`)** | **PASS** | `rotate()` moved the entity north → east (direction 0 → 4); the four pipe-connection positions are **identical as a set** before and after (they only change order, because the list rotates with the entity). Log: `connection set after rotate identical: true` |
| **deconstruction** | **PASS** | `order_deconstruction` → `to_be_deconstructed: true`; `cancel_deconstruction` → `false`. No error, turret still fuelled and working afterwards |
| **save / reload** | **PASS** | `--create` wrote a map that already contained a fuelled, east-facing turret; reloading it reports `valid dir=4 orient=0.2500 fluid=247.7 hp=1200`, 4 pipes on the map, 1 melta turret, identical connection set, and the mod's own `storage` entry survived (`built_at=0.5,200.5`) |
| **blueprint copy-paste** | **PARTIAL** | see below |
| **two-client desync** | **NOT TESTED** | needs two clients; proxy: `--benchmark 600 --benchmark-consistency` ran clean (exit 0, `checksum: 3830358549`, no state mismatch), and the mod holds no client-only state and draws no RNG |

### Why blueprint copy-paste is only PARTIAL

Factorio 2.1 has no scripting API for capturing a blueprint — `LuaPlayer.create_blueprint`
is gone (the old version of this probe failed on it) and
`LuaSurface.create_entities_from_blueprint_string` is documented as simulation-only. The
paste half was therefore reproduced with the call a paste ends in: `LuaEntity.clone{}`
plus `raise_built`, i.e. the same `on_built` path a real paste uses. Result: the pasted
turret keeps its direction (east), inherits the fluid (156.5 → 204.5 after being fed),
reports 4 pipe connections and `status 1` (working) — a real Ctrl+C/Ctrl+V by a player is
the only remaining gap, and there is no code path in the mod that distinguishes a paste
from any other build.

## 4. Files changed by this card

Mod code: **none**. Only evidence was added:

```
docs/verification/README.md
docs/verification/melta-end-to-end-verification.md   (this file)
docs/verification/in-game/*.jpg                      13 screenshots
docs/verification/detail/*.png                        3 1:1 crops
docs/verification/icon-sheet-native.png
docs/verification/icon-sheet-6x-nearest.png
docs/verification/logs/*.txt                          5 log extracts
docs/verification/harness/{melta-verify,melta-regress,melta-persist}/   probe mods, never shipped
```

## 5. Open issues

1. **South pipe join — closed as a measurement error, kept so nobody re-measures it.**
   The 0.23-tile figure came from comparing the hull's 1.28-tile south extent against a
   1.5-tile pipe mouth. A *vertical* pipe's near edge is drawn at 1.19 tiles (raised rim
   plus baked shadow project inboard on the screen's vertical axis), so the true join is
   −0.09 (overlap) and `97a327b`'s −0.09 was right. `graphics/_blender/pipe_sockets.py
   --check` reproduces the table in §2c, the 1:1 crop shows the collar meeting the hull,
   and `in-game/03-pipes-overview.jpg` shows no bare strip on any side.
2. **Icon legibility at 32 px** — technically correct and sharper than vanilla, but the
   silhouette does not read as a turret at inventory size. Known, documented in
   `DESIGN.md`; fixing it is a model change (fewer, larger plates).
3. **Sound was not heard and the engine mix was not captured** — no loopback device on
   this machine. File levels, volume and the aggregation clamp were measured; the
   worst-case two-voice sum (+1.3 dBFS, exact phase) is a theoretical risk, not an
   observed one.
4. **A real blueprint clipboard round trip was not exercised** (see above).
5. **Observation, not a defect:** anything that creates this turret from a script must
   pass `raise_built = true`. `control.lua` registers turrets on
   `on_built_entity`/`script_raised_built` (lines 659-662), so a script-created turret
   without that flag is invisible to the mod: it still has its fluid box, but no lance is
   drawn and no damage is applied. The first version of this harness hit exactly that and
   produced a silent, inert turret — worth knowing for `/c` spawning and for other mods.
