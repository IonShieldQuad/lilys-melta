"""Melta turret sounds -- synthesised, not borrowed.

The melta is a combustion weapon: it throws a pressurised stream of superheated
fuel. The firing sound is built as three layers, all synthesised here:

  1. PRESSURE RELEASE  a very short bright burst that starts on sample 0 (the valve
                       lets go), ~1.5 ms attack, ~40 ms decay: the sharp front.
  2. SIZZLE / ROAR     band-passed noise body burning under the whole shot, with
                       random molten-spatter ticks riding on it.
  3. TURBOPUMP         a low harmonic stack (~45-98 Hz) that spins up over the
                       first ~0.2 s and hums underneath, plus a faint blade whine.
                       This layer is what gives the shot its weight.

Files produced (44.1 kHz, mono, Ogg Vorbis in ../):

    melta-fire-1.ogg .. melta-fire-3.ogg   three variations of the shot
                                           (0.62 / 0.70 / 0.66 s, transient at sample 0)
    melta-burn.ogg  2.0 s seamless loop    the stream held down between shots
    melta-stop.ogg  0.6 s tail             the stream dying

The loop is built in the frequency domain with random phase and circular filters,
so it is seamless by construction: every tone in it completes a whole number of
cycles per loop and the crackle wraps around the seam. The shot variations share the
loop's three layers, so the transient hands over to the sustain without a timbre
jump.

Loudness is normalised by RMS, not by peak. A noise bed has a ~14 dB crest factor,
and peak-normalising it is exactly why the first version of the loop measured
-26 dBFS RMS while reading "normalised" (see the numbers in prototypes/entity.lua).
The targets below are the vanilla weapons measured with `ffmpeg astats` on the
installed game (`python docs/verification/harness/sound_measure.py` re-measures
both sides of the comparison):

    file                          RMS dBFS   volume   effective
    gun-turret-gunshot              -17.9      0.4      -25.9
    laser-1 (laser turret shot)     -20.2      0.5      -26.2
    flamethrower-turret-start       -13.2      0.5      -19.2    burst ignition
    flamethrower-turret-mid         -13.7      0.5      -19.7    sustain loop
    melta-fire-* (this script)      -15.4      0.7      -18.5    just above a flamer
    melta-burn   (this script)      -15.3      0.7      -18.4
    melta-stop   (this script)      -19.6      0.7      -22.7

Two gates run after the encode, because that is where a synthesised cue actually
breaks: the decoded peak must land under PEAK_CEIL_ENCODED (libvorbis overshoots a
sharp transient by 1.5-3 dB, and files that were safe before encoding decoded at
-1.4 dBFS), and the band energy of every layer must clear BAND_FLOOR, so a layer
that has been masked by the others fails the build instead of shipping silently.

Needs numpy and ffmpeg (the encoder) on PATH. Run: python melta_sounds.py
"""

import os
import shutil
import subprocess
import tempfile
import wave

import numpy as np

RATE = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

# target file RMS in dBFS, and the peak ceiling a single voice is allowed to hit
TARGET_RMS = {"fire": -15.2, "burn": -15.2, "stop": -19.5}
PEAK_CEIL = {"fire": -2.5, "burn": -2.2, "stop": -3.0}
# The ceiling that matters is the one measured AFTER the Vorbis decode: two voices
# of the same file at volume 0.7 must still sum under full scale, so each voice has
# to decode with >= 3 dB of headroom (per-voice peak -3 dBFS + volume -3.1 dB =
# -6.1, two in phase = -0.1). PEAK_CEIL above is only the starting point.
PEAK_CEIL_ENCODED = -3.0

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


# --------------------------------------------------------------- primitives --
def shaped_noise(seconds, bands, seed, tilt=900.0, tilt_pow=1.1):
    """Noise whose spectrum is a sum of gaussian bands, tilted towards pink so it
    reads as moving air rather than white hash. Built circularly (random phase ->
    inverse rfft), which is what makes the loop seamless."""
    n = int(RATE * seconds)
    rng = np.random.default_rng(seed)
    spectrum = rng.normal(0.0, 1.0, n // 2 + 1) + 1j * rng.normal(0.0, 1.0, n // 2 + 1)
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    envelope = np.zeros_like(freqs)
    for centre, width, gain in bands:
        envelope += gain * np.exp(-0.5 * ((freqs - centre) / width) ** 2)
    envelope *= 1.0 / (1.0 + freqs / tilt) ** tilt_pow
    envelope[freqs < 30] *= freqs[freqs < 30] / 30.0
    return np.fft.irfft(spectrum * envelope, n)


def env_ar(n, attack_s, tau_s, hold_s=0.0):
    """Attack / hold / exponential decay, all in absolute seconds. The attack is a
    squared sine so the onset is smooth: starting a sample at full amplitude is a
    click, and a weapon cue has enough transients without inventing one."""
    t = np.arange(n) / RATE
    attack = max(attack_s, 1.0 / RATE)
    rise = np.sin(np.clip(t / attack, 0.0, 1.0) * np.pi / 2) ** 2
    after = np.clip(t - attack - hold_s, 0.0, None)
    return rise * np.exp(-after / tau_s)


def turbopump(seconds, seed, f_low=45.0, f_high=92.0, spin_s=0.20,
              detune=0.004, wobble_hz=9.0, wobble_depth=0.10):
    """Low harmonic stack whose pitch climbs as the rotor spins up, with a faint
    blade whine. `detune=0` makes it exactly periodic over `seconds` (needed for
    the loop: a detuned harmonic does not close on itself and clicks at the seam)."""
    n = int(RATE * seconds)
    t = np.arange(n) / RATE
    rng = np.random.default_rng(seed)
    rpm = f_low + (f_high - f_low) * (1.0 - np.exp(-t / spin_s))
    phase = 2 * np.pi * np.cumsum(rpm) / RATE
    hum = np.zeros(n)
    for k, amp in ((1, 1.00), (2, 0.55), (3, 0.34), (4, 0.16), (6, 0.09)):
        drift = 1.0 + rng.uniform(-detune, detune) if detune else 1.0
        hum += amp * np.sin(k * phase * drift + rng.uniform(0, 2 * np.pi))
    # blade whine: narrow, quiet, sits above the hum
    whine = 0.055 * np.sin(11 * phase + 0.7) + 0.030 * np.sin(17 * phase + 2.1)
    hum *= 1.0 - wobble_depth * (0.5 + 0.5 * np.sin(2 * np.pi * wobble_hz * t))
    return hum + whine


def spatter(count, seconds, seed, lo=0.010, hi=0.035, bright=(1800, 6200)):
    """Molten spatter: short bright ticks at random times -- the sizzle's teeth."""
    n = int(RATE * seconds)
    rng = np.random.default_rng(seed)
    out = np.zeros(n)
    for _ in range(count):
        start = int(rng.uniform(0.02, seconds * 0.85) * RATE)
        length = int(RATE * rng.uniform(lo, hi))
        if start + length >= n:
            continue
        decay = np.exp(-np.linspace(0, 9, length))
        tone = np.sin(2 * np.pi * rng.uniform(*bright) * np.arange(length) / RATE)
        body = tone + 0.4 * rng.normal(0, 1, length) * np.exp(-np.linspace(0, 4, length))
        out[start:start + length] += decay * body * rng.uniform(0.25, 1.0)
    return out


# ------------------------------------------------------------------ the shot --
def rms1(x):
    return x / (np.sqrt(np.mean(x ** 2)) + 1e-12)


def peak1(x):
    return x / (np.max(np.abs(x)) + 1e-12)


# Layer gains in dB relative to each other. Every layer is normalised first (RMS
# for continuous beds, PEAK for the sparse ones), because the raw synthesis scales
# are meaningless: the low pump sums a handful of sines while the noise bands are
# divided by sqrt(n) by the inverse FFT, so an un-normalised mix is 99 % pump.
#
# `pump` was -8.5 dB in the first pass and the turbopump was inaudible next to the
# roar: measured, the 20-120 Hz band sat 10.4 dB under the total while the burn
# loop it hands over to sits at 7.3. At -3.0 the shot's low band measures -7.2 --
# level with the loop, so the rotor is heard as weight under the sizzle instead of
# being masked by it. Raising it further only trades the hiss away (each +5 dB of
# pump buys ~1.8 dB of band energy, because the mix is re-normalised).
FIRE_GAIN = {"release": 0.0, "thump": -7.0, "roar": -0.5, "hiss": -1.5, "sparks": -7.0, "pump": -3.0}
BURN_GAIN = {"rumble": -6.0, "roar": 0.0, "hiss": -4.5, "pump": -10.0, "crackle": -6.0}
STOP_GAIN = {"noise": 2.0, "hiss": -8.0, "pump": -6.0}


def g(table, key):
    return 10 ** (table[key] / 20.0)


def build_fire(seed, seconds, f_low, f_high, weight=1.0, sizzle=1.0, spatter_count=9):
    n = int(RATE * seconds)
    t = np.arange(n) / RATE

    # 1. pressure release: bright burst on the first sample, gone in ~40 ms
    release = shaped_noise(seconds, [(2600, 1500, 1.6), (6800, 2600, 0.9)], seed=seed + 100)
    release = rms1(release * env_ar(n, 0.0015, 0.040))
    # the valve body under the burst: a short falling thump, gives the release mass
    thump = np.sin(2 * np.pi * (150 * np.exp(-t * 40) + 62) * t + 0.4)
    thump = peak1(thump * env_ar(n, 0.0008, 0.030))

    # 2. sizzle / roar: the stream burning, the longest layer
    roar = shaped_noise(seconds, [(420, 300, 1.2), (1150, 650, 1.5), (2800, 1200, 0.7)], seed=seed + 200)
    roar = rms1(roar * env_ar(n, 0.030, 0.20, hold_s=0.06))
    hiss = shaped_noise(seconds, [(5200, 1900, 1.0), (9000, 2600, 0.55)], seed=seed + 300)
    hiss = rms1(hiss * env_ar(n, 0.010, 0.16, hold_s=0.02))
    sparks = peak1(spatter(spatter_count, seconds, seed + 400) * env_ar(n, 0.005, 0.30))

    # 3. turbopump underneath, spinning up from rest
    pump = turbopump(seconds, seed + 500, f_low=f_low, f_high=f_high)
    pump = rms1(pump * env_ar(n, 0.004, 0.45, hold_s=0.02))

    mix = (release * g(FIRE_GAIN, "release")
           + thump * g(FIRE_GAIN, "thump")
           + roar * g(FIRE_GAIN, "roar")
           + hiss * g(FIRE_GAIN, "hiss") * sizzle
           + sparks * g(FIRE_GAIN, "sparks") * sizzle
           + pump * g(FIRE_GAIN, "pump") * weight)

    # one shared tail so the layers die together instead of leaving a sizzle orphan
    return mix * np.clip((seconds - t) / 0.09, 0.0, 1.0) ** 1.5


# ------------------------------------------------------------------ the loop --
def build_burn(seconds=2.0):
    n = int(RATE * seconds)
    t = np.arange(n) / RATE

    rumble = rms1(shaped_noise(seconds, [(90, 70, 1.4), (200, 120, 0.9)], seed=1))
    roar = rms1(shaped_noise(seconds, [(480, 330, 1.9), (1150, 700, 1.5), (2700, 1100, 0.6)], seed=2))
    hiss = rms1(shaped_noise(seconds, [(5400, 2000, 0.16), (9000, 2500, 0.07)], seed=3))

    flutter = 0.80 + 0.20 * np.sin(2 * np.pi * 7 * t) * np.sin(2 * np.pi * 1 * t)
    breath = 0.85 + 0.15 * np.sin(2 * np.pi * 0.5 * t)

    # the turbopump is the layer that ties the loop to the shot: same harmonics at
    # running speed, no spin-up, detune off so it closes perfectly at the seam
    pump = rms1(turbopump(seconds, 600, f_low=92.0, f_high=92.0, spin_s=10.0, detune=0.0, wobble_depth=0.08))

    rng = np.random.default_rng(7)
    crackle = np.zeros(n)
    for _ in range(int(seconds * 14)):
        start = rng.integers(0, n)
        length = int(RATE * rng.uniform(0.004, 0.012))
        tick = np.exp(-np.linspace(0, 6, length)) * rng.uniform(0.05, 0.16)
        tone = rng.uniform(1200, 3500)
        for offset in range(length):
            crackle[(start + offset) % n] += tick[offset] * np.sin(2 * np.pi * tone * offset / RATE)

    mix = (rumble * g(BURN_GAIN, "rumble")
           + roar * flutter * g(BURN_GAIN, "roar")
           + hiss * breath * g(BURN_GAIN, "hiss")
           + pump * g(BURN_GAIN, "pump")
           + peak1(crackle) * g(BURN_GAIN, "crackle"))
    return mix


# ------------------------------------------------------------------- the end --
def build_stop(seconds=0.6):
    n = int(RATE * seconds)
    t = np.arange(n) / RATE
    noise = peak1(shaped_noise(seconds, [(600, 420, 1.2), (1700, 950, 1.0)], seed=21) * np.exp(-t * 6.5))
    hiss = rms1(shaped_noise(seconds, [(6000, 2400, 0.35)], seed=22) * np.exp(-t * 3.0))
    # the rotor winds down: the same harmonics falling in pitch
    pump = rms1(turbopump(seconds, 620, f_low=88.0, f_high=42.0, spin_s=0.30, detune=0.0))
    mix = (noise * g(STOP_GAIN, "noise") + hiss * g(STOP_GAIN, "hiss") + pump * g(STOP_GAIN, "pump"))
    return mix * np.clip((seconds - t) / 0.05, 0.0, 1.0)


# ------------------------------------------------------- matching + encoding --
def match_rms(signal, target_db, peak_ceil_db):
    """Scale to the target RMS, then soft-limit if that pushed the peak past the
    ceiling. Leaving headroom per voice is what keeps two turrets firing the same
    cue from summing over full scale."""
    for _ in range(4):
        rms = np.sqrt(np.mean(signal ** 2)) or 1e-9
        out = signal * (10 ** (target_db / 20.0) / rms)
        ceil = 10 ** (peak_ceil_db / 20.0)
        if np.max(np.abs(out)) <= ceil:
            return out
        signal = np.tanh(out / ceil * 1.15) * ceil / np.tanh(1.15)
    return signal


def write_int16_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        pcm = np.clip(np.round(samples * 32767.0), -32768, 32767).astype("<i2")
        w.writeframes(pcm.tobytes())


def encode(wav_path, ogg_path, quality=5):
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", wav_path,
                    "-c:a", "libvorbis", "-q:a", str(quality), ogg_path], check=True)


def stats(signal):
    rms = 20 * np.log10(np.sqrt(np.mean(signal ** 2)) + 1e-12)
    peak = 20 * np.log10(np.max(np.abs(signal)) + 1e-12)
    return rms, peak


# The three layers of the brief live in three different parts of the spectrum, so
# "is the layer there?" is answerable as a number instead of a matter of taste:
#   pump  45-98 Hz and its harmonics -> the sub band
#   roar  the burning stream        -> low/mid
#   hiss  the sizzle                -> 2-16 kHz
BANDS = {"sub20-120": (20, 120), "low120-400": (120, 400), "mid400-2k": (400, 2000),
         "hi2k-6k": (2000, 6000), "air6k-16k": (6000, 16000)}

# Band energy relative to the file's total, in dB. A layer that vanishes from this
# table has been masked by the others no matter what the mix code says it added.
BAND_FLOOR = {"fire": {"sub20-120": -11.0, "mid400-2k": -8.0, "hi2k-6k": -9.0, "air6k-16k": -16.0},
              "burn": {"sub20-120": -11.0, "mid400-2k": -8.0, "hi2k-6k": -11.0, "air6k-16k": -18.0},
              "stop": {"sub20-120": -9.0, "mid400-2k": -14.0, "hi2k-6k": -10.0}}


def band_balance(signal):
    spec = np.abs(np.fft.rfft(signal)) ** 2
    freqs = np.fft.rfftfreq(len(signal), 1 / RATE)
    total = spec[(freqs >= 20) & (freqs < 20000)].sum()
    out = {}
    for name, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        out[name] = float(10 * np.log10(spec[m].sum() / total + 1e-20))
    return out


def _values(text, key):
    out = []
    for line in text.splitlines():
        if key in line:
            out.append(line.split(key + ":")[1].strip())
    return out


def check_encoded(path):
    """Read the encoded file back: proving the OGG decodes to the loudness that was
    asked for is the only evidence that matters, since the encoder can shift a
    level slightly and clip a hot peak."""
    probe = subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                            "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", path],
                           capture_output=True, text=True, check=True).stdout.strip()
    out = subprocess.run([FFMPEG, "-hide_banner", "-nostats", "-i", path,
                          "-af", "astats=metadata=1:reset=0", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    return probe, float(_values(out, "RMS level dB")[0]), float(_values(out, "Peak level dB")[0]), float(_values(out, "Flat factor")[0])


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    jobs = [
        ("melta-fire-1.ogg", "fire", build_fire(1000, 0.62, 45.0, 92.0, weight=1.00, sizzle=1.00, spatter_count=9)),
        ("melta-fire-2.ogg", "fire", build_fire(2000, 0.70, 52.0, 98.0, weight=0.90, sizzle=1.00, spatter_count=12)),
        ("melta-fire-3.ogg", "fire", build_fire(3000, 0.66, 40.0, 84.0, weight=1.15, sizzle=0.85, spatter_count=7)),
        ("melta-burn.ogg", "burn", build_burn()),
        ("melta-stop.ogg", "stop", build_stop()),
    ]

    tmp = tempfile.mkdtemp(prefix="melta-snd-")
    print("%-18s %6s %7s %7s %9s %7s %8s  %s" % ("file", "sec", "rms", "peak", "rms/enc", "pk/enc", "flat", "stream"))
    for name, kind, raw in jobs:
        # The peak limit is enforced on the DECODED file, in a loop: libvorbis adds
        # 1.5-3 dB of overshoot on a sharp transient, so a file that is safe before
        # the encoder can decode above -1.5 dBFS. Two turrets firing that variation
        # within the same few milliseconds would then sum past full scale, which is
        # the clipping the card forbids. Each pass tightens the pre-encode ceiling by
        # whatever the decode overshot, and the RMS target is re-fitted to it.
        ceiling = PEAK_CEIL[kind]
        for attempt in range(5):
            out = match_rms(raw, TARGET_RMS[kind], ceiling)
            rms, peak = stats(out)
            # a one-shot must open on the transient and close on silence, or it clicks
            if kind == "fire":
                head = np.max(np.abs(out[:int(0.030 * RATE)]))
                assert head >= 0.7 * np.max(np.abs(out)), "the front is not the loudest moment: %.2f vs %.2f" % (head, np.max(np.abs(out)))
                assert abs(out[0]) < 0.005, "sample 0 jumps off zero (click): %.4f" % out[0]
            # a loop must NOT fade out (it is seamless by construction); the one-shots must
            if kind != "burn":
                assert abs(out[-1]) < 1e-3, "tail does not reach zero"
            wav = os.path.join(tmp, name + ".wav")
            write_int16_wav(wav, out)
            ogg = os.path.join(OUT, name)
            encode(wav, ogg)
            probe, enc_rms, enc_peak, flat = check_encoded(ogg)
            if enc_peak <= PEAK_CEIL_ENCODED:
                break
            ceiling -= (enc_peak - PEAK_CEIL_ENCODED) + 0.5
        else:
            raise SystemExit("%s: could not get the decoded peak under %.1f dBFS" % (name, PEAK_CEIL_ENCODED))
        print("%-18s %6.2f %7.2f %7.2f %9.2f %7.2f %8.3f  %s  -> %d bytes (ceiling %.1f, %d pass)"
              % (name, len(out) / RATE, rms, peak, enc_rms, enc_peak, flat, probe,
                 os.path.getsize(ogg), ceiling, attempt + 1))
        bal = band_balance(out)
        print("    bands rel dB: " + " ".join("%s %5.1f" % (k, v) for k, v in bal.items()))
        if abs(enc_rms - TARGET_RMS[kind]) > 1.0:
            raise SystemExit("%s: encoded RMS %.2f is off target %.2f" % (name, enc_rms, TARGET_RMS[kind]))
        if flat > 0.0:
            raise SystemExit("%s: Flat factor %.3f -- clipped samples in the encode" % (name, flat))
        for band, floor in BAND_FLOOR[kind].items():
            if bal[band] < floor:
                raise SystemExit("%s: the %s band is %.1f dB under the total (floor %.1f) -- "
                                 "that layer is masked, not layered" % (name, band, bal[band], floor))
