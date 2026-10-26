# Melta firing sound — verification

**Scope:** sound only — `sound/_generator/melta_sounds.py`, `sound/*.ogg`, the
`cyclic_sound` block in `prototypes/entity.lua`, and the changelog entry. Beam, art,
pipes, tooltip and item order belong to other cards on the same board.

**Runs:** a staged copy of the tree (`base + lilys-melta + melta-sound-probe`, quality /
space-age / elevated-rails / recycler disabled), Factorio 2.1.23 (build 87750, win64,
steam). Every loudness number below comes from decoding the shipped OGGs and measuring
them (`harness/sound_measure.py`), not from the generator's own report.

**Verdict:** the layering, the level against the vanilla weapons, the peak budget, the
three variations and the prototype wiring are all measured and pass. "Sounds good in the
ear" is deliberately left open — this machine cannot capture its own audio output, so
that judgement is Lily's (see §6).

---

## 1. The brief, layer by layer

Each cue is synthesised from three layers, and each layer is placed in a different part
of the spectrum so that "is it there?" is a number instead of a matter of taste:

| layer | synthesis | band it owns | shot A/B/C | held loop |
|---|---|---|---|---|
| pressure release | gaussian noise at 2600 ± 1500 and 6800 ± 2600 Hz, sin² attack 1.5 ms then 40 ms decay, plus a falling 150 → 62 Hz thump for mass | 2–6 kHz + the first 5 ms | peak is in the first 5 ms | — |
| sizzle / roar | noise bands at 420, 1150 and 2800 Hz (30 ms attack, 60 ms hold, 200 ms decay) + hiss bands at 5200 / 9000 Hz + 7–12 molten spatter ticks per shot | 120 Hz–2 kHz, 2–16 kHz | mid −5.1, hi −6.0, air −11.2 | mid −4.8, hi −8.5 |
| turbopump | harmonic stack (1, 2, 3, 4, 6 ×) climbing 45 → 92 Hz over the first 0.20 s, 11×/17× blade whine, 9 Hz wobble | 20–120 Hz | sub −7.0 / −8.1 / −6.1 | sub −7.2 |

Bands are dB relative to the file's total energy (table in §3). Two things were tuned
against those numbers rather than by guessing:

- **The pump was inaudible in the first pass.** At `FIRE_GAIN.pump = -8.5 dB` the 20–120 Hz
  band measured −10.4 dB under the file's total while the loop it hands over to sits at
  −7.2, i.e. the rotor was buried under the roar. At −3.0 dB the shot's low band lands at
  −7.0, level with the loop, so the spin-up is heard as weight. Going further costs the
  hiss (each +5 dB of pump only buys ≈1.8 dB of band energy, because the mix is
  re-normalised to the same RMS).
- **The old firing cue was a thump, not a hiss.** `melta-start.ogg` measured −11.6 dBFS
  RMS with sub −1.7 dB and mid −24.2 dB: nearly all of its energy below 400 Hz, which is
  exactly the "dry thump" the brief asks to get away from. The new shots put −5 dB into
  400 Hz–2 kHz and −6 dB into 2–6 kHz.

## 2. Why `begin/middle/end` and not a per-shot `sound`

`attack_parameters.sound` is a `LayeredSound` (2.1) and retriggers on **every** shot. The
melta pulses at 7.5 shots/s (`C.cooldown = 8`), so a 0.62–0.70 s cue would be five voices
deep within half a second and smear — precisely what the brief says to avoid. The melta
holds a beam, so the cue that matches the weapon is the engine's cyclic one: one ignition,
a held loop, one shut-down, which is also the model the vanilla flamethrower turret uses
(`data/base/prototypes/entity/fire.lua:930`, three variations per slot at volume 0.5).

The three variations therefore live on `begin_sound`: `allow_random_repeat` defaults to
false, so a turret that stops and starts firing does not play the same ignition twice in a
row. The held loop (`melta-burn.ogg`) is a 2 s seamless loop — it is built circularly
(random phase → inverse FFT, every tone a whole number of cycles per loop, crackle wrapped
across the seam), so the seam measures `|last − first| 0.0156` against a mean sample step
of `0.0461`: continuous, no click every two seconds.

## 3. Loudness — where it sits against the mod and the vanilla ladder

`effective = file RMS dBFS + 20·log10(volume)`; the volume is the number in the prototype.

| cue | stream | sec | file RMS | file peak | volume | effective |
|---|---|---|---|---|---|---|
| melta-fire-1 | vorbis 44.1k mono | 0.62 | −15.36 | −3.28 | 0.70 | **−18.46** |
| melta-fire-2 | vorbis 44.1k mono | 0.70 | −15.36 | −3.03 | 0.70 | −18.46 |
| melta-fire-3 | vorbis 44.1k mono | 0.68 | −15.51 | −3.87 | 0.70 | −18.61 |
| melta-burn (held loop) | vorbis 44.1k mono | 2.00 | −15.32 | −4.38 | 0.70 | −18.42 |
| melta-stop | vorbis 44.1k mono | 0.60 | −19.59 | −5.72 | 0.70 | −22.69 |
| *melta-start (replaced)* | vorbis 22.05k mono | 0.45 | −11.55 | −0.92 | 0.70 | *−14.65* |
| *melta-burn (replaced)* | vorbis 22.05k mono | 2.00 | −15.25 | −0.47 | 0.70 | *−18.35* |
| vanilla flamer igniter | vorbis 44.1k stereo | 0.60 | −13.19 | −1.15 | 0.50 | −19.21 |
| vanilla flamer loop | vorbis 44.1k stereo | 3.24 | −13.72 | −2.44 | 0.50 | −19.74 |
| vanilla gun turret shot | vorbis 44.1k stereo | 1.47 | −17.92 | −0.75 | 0.40 | −25.88 |
| vanilla laser turret shot | vorbis 44.1k stereo | 0.50 | −20.22 | −3.64 | 0.50 | −26.24 |

Read off that table: the shot sits **0.75 dB above** the flamethrower turret's igniter and
1.3 dB above its loop, 7.4 dB above the gun turret and 7.8 dB above the laser turret. It is
the heaviest weapon sound in the comparison, and it is the same 0.70 volume the mod already
used, so nothing else in the mod shifts. The sustain loop and the shot are within 0.04 dB of
each other, which is what makes the ignition-to-loop handover inaudible as a step.

Mono is deliberate: the mod's other cues are mono and a turret is a point source, so stereo
would only add two copies of the same noise.

## 4. Clipping budget (the part that actually decides "no clicks")

- **Enforced after encoding, in a loop.** libvorbis overshoots a sharp transient by
  1.5–3 dB, so a file that is safe before the encoder can decode at −1.4 dBFS. The
  generator now encodes, decodes, measures the real peak and tightens the pre-encode
  ceiling until every cue decodes at or under −3 dBFS (fires needed 2–3 passes; the loop
  and the shut-down needed one). Files that were already shipped in the first pass had
  decoded peaks of −2.7 / −1.4 / −2.0 dBFS: exactly the state that would have clipped.
- **Two voices, all 45 combinations** (every variation pair, at 0 / 5 / 10 / 20 / 40 ms
  apart, both at volume 0.70): worst peak **−1.4 dBFS** for two different variations,
  **−0.11 dBFS** for the same variation twice — and that last case is prevented by
  `allow_random_repeat = false`, which makes two immediately consecutive ignitions pick
  different files.
- **Never three at once:** `aggregation.max_count = 2` caps this prototype's voices, so a
  wall of turrets raises the level instead of summing. `progress_threshold = 0.35` on the
  ignition releases its slot once the cue is a third through, so a second turret's
  ignition is not dropped because the first one's tail is still ringing.
- **Tail hygiene:** every one-shot starts at sample 0 with a value < 0.005 pre-encode and
  ends at < 1e-3, so there is no leading silence (onset 0.20–0.45 ms) and no end step.
  (After the Vorbis decode the first sample measures 0.003–0.039, i.e. −28 dBFS or lower:
  codec ringing, not a step out of silence.) No cue reports a `Flat factor` above 0, so no
  sample is clipped in the file itself.

## 5. Three variations that are actually different

| pair | max cross-correlation | RMS difference |
|---|---|---|
| shot 1 vs 2 | 0.195 | 0.00 dB |
| shot 1 vs 3 | 0.265 | 0.15 dB |
| shot 2 vs 3 | 0.172 | 0.15 dB |

1.000 would be the same file twice. The three differ in pump pitch (45→92, 52→98,
40→84 Hz), sizzle level, spatter count and length, while staying level-matched within
0.15 dB — so variation is heard as timbre, never as a loud shot and a quiet one.

Spectral distance from the weapons it must not sound like, over the five band energies:
laser turret **22.0 dB**, gun turret **12.4 dB**, flamethrower igniter **16.6 dB**.

## 6. Prototype wiring, asset hygiene, and what the game actually proved

Wiring (`prototypes/entity.lua`): `begin_sound` is a `variations` list of
`melta-fire-1/2/3.ogg` at volume 0.70, `middle_sound` is `melta-burn.ogg`,
`end_sound` is `melta-stop.ogg`; all three carry `aggregation` and an
`audible_distance_modifier` of 1.3–1.4.

- **Data stage** (`--create` on the staged copy): exit 0, no errors, no warnings, and the
  resolved prototype dumped from `data.raw` carries three variations with the expected
  volumes and aggregation. Every filename in it exists on disk, and a sweep of the staged
  `sound/` directory finds **no unreferenced `.ogg`** — `melta-start.ogg` is gone and
  nothing points at it.
- **GUI run** (plain `--load-game`, so a real audio device): `[Audio] Driver:wasapi,
  Device:Default device, Depth:32, Channels:2, Frequency:44100`, then `Loading sounds...`
  — the engine's own sound loader read the mod's OGGs and reported nothing — then the probe
  turret went through eight ignition → held → shut-down cycles (fluid 100 → 15 and back up,
  `shooting_target` non-nil throughout) with **zero errors or warnings** in the log.
- **Not proven here: that it sounds good.** This machine has no loopback capture device
  (only microphones), and Factorio writes no log line per played sound, so nothing in the
  log can attest to audibility. What is proven is that the files are valid Ogg Vorbis
  44.1 kHz mono, that the engine accepts and loads them, and that the turret fires them
  repeatedly without an error. The ear test is hers.
- **Harness trap worth remembering:** `--create`, `--benchmark` and
  `--load-game --until-tick` come up **headless** in this environment ("Running in
  headless mode" / "Audio is disabled"), so the engine never opens a sound file in those
  runs. Only a plain `--load-game` launch initialises WASAPI and loads the sound bank — a
  headless "no errors" says nothing about sound.

## 7. How to re-run

```bash
# measurements (any checkout; the replaced files default to git HEAD)
python docs/verification/harness/sound_measure.py

# regenerate the OGGs (needs numpy + ffmpeg on PATH; it re-checks everything after encoding)
python sound/_generator/melta_sounds.py

# load test: staged copy, data stage only
RUN=C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest-sound
cp -r sound prototypes locale data.lua data-updates.lua constants.lua control.lua info.json changelog.txt "$RUN/mods/lilys-melta/"
cp -r docs/verification/harness/melta-sound-probe "$RUN/mods/"
"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe" \
  --config "$RUN/config.ini" --mod-directory "$RUN/mods" --create "$RUN/write/scene.zip"
# ...then a plain --load-game of that save with SteamAppId=427520 for audio
```
