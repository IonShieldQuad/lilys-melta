"""Melta turret sounds -- synthesised jet/hiss, not a borrowed flame loop.

The beam is a high-pressure stream of superheated fuel, so the target is a jet
exhaust: a low rumble core, a band-passed roaring body that flutters, and a bright
sizzle on top. Everything is built in the frequency domain with random phase, which
makes the loop mathematically seamless (circular noise -> circular filters -> inverse
FFT), then wrapped so the start/stop cues match the loop.

    sound/melta-burn.ogg   2.0 s loop, played while the beam is held (cyclic_sound middle)
    sound/melta-start.ogg  0.45 s pressure build-up
    sound/melta-stop.ogg   0.6 s decay

Run: python melta_sounds.py
"""

import os

import numpy as np
import soundfile as sf

RATE = 22050
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def shaped_noise(seconds, bands, seed):
    """Seamless noise: random spectrum shaped by (centre, width, gain) bands, then
    tilted towards pink so it reads as moving air rather than as white hiss."""
    n = int(RATE * seconds)
    rng = np.random.default_rng(seed)
    spectrum = rng.normal(0.0, 1.0, n // 2 + 1) + 1j * rng.normal(0.0, 1.0, n // 2 + 1)
    freqs = np.fft.rfftfreq(n, 1.0 / RATE)
    envelope = np.zeros_like(freqs)
    for centre, width, gain in bands:
        envelope += gain * np.exp(-0.5 * ((freqs - centre) / width) ** 2)
    envelope *= 1.0 / (1.0 + freqs / 900.0) ** 1.1
    envelope[freqs < 40] *= freqs[freqs < 40] / 40.0
    return np.fft.irfft(spectrum * envelope, n)


def loop_seconds():
    return 2.0


def build_loop():
    seconds = loop_seconds()
    n = int(RATE * seconds)

    # low rumble: the mass of air being pushed
    rumble = shaped_noise(seconds, [(80, 60, 1.5), (180, 110, 1.0)], seed=1)
    # roaring body: pressurised flow, the "jet" part -- this must dominate
    roar = shaped_noise(seconds, [(450, 320, 2.0), (1100, 700, 1.6), (2600, 1100, 0.7)], seed=2)
    # sizzle: molten material and burning fuel, bright but only a top layer
    sizzle = shaped_noise(seconds, [(5500, 2000, 0.16), (9000, 2500, 0.07)], seed=3)

    # 7 Hz flutter on the roar gives it the throb of a pressure stream
    t = np.linspace(0, seconds, n, endpoint=False)
    flutter = 0.80 + 0.20 * np.sin(2 * np.pi * 7 * t) * np.sin(2 * np.pi * 1 * t)
    breath = 0.85 + 0.15 * np.sin(2 * np.pi * 0.5 * t)

    mix = rumble * 1.1 + roar * flutter * 1.0 + sizzle * breath * 0.5

    # crackle: a handful of short bright ticks, wrapped so they keep looping
    rng = np.random.default_rng(7)
    crackle = np.zeros(n)
    for _ in range(int(seconds * 14)):
        start = rng.integers(0, n)
        length = int(RATE * rng.uniform(0.004, 0.012))
        tick = np.exp(-np.linspace(0, 6, length)) * rng.uniform(0.05, 0.16)
        tone = rng.uniform(1200, 3500)
        for offset in range(length):
            crackle[(start + offset) % n] += tick[offset] * np.sin(2 * np.pi * tone * offset / RATE)

    mix = mix + crackle
    mix = soft_clip(mix)
    return normalise(mix, peak=0.85)


def build_start():
    """Pressure building: rising noise plus a low thump that falls away."""
    seconds = 0.45
    n = int(RATE * seconds)
    t = np.linspace(0, seconds, n, endpoint=False)
    noise = shaped_noise(seconds, [(700, 500, 1.4), (1900, 1000, 1.2), (4200, 1800, 0.4)], seed=11)
    rise = np.clip(t / seconds, 0, 1) ** 1.6
    jet = noise * rise * 2.2
    thump = np.sin(2 * np.pi * (110 * np.exp(-t * 6) + 45) * t) * np.exp(-t * 7) * 0.30
    return normalise(soft_clip(jet + thump), peak=0.9)


def build_stop():
    """Shut-down: the stream dies, the sizzle lingers a moment."""
    seconds = 0.6
    n = int(RATE * seconds)
    t = np.linspace(0, seconds, n, endpoint=False)
    noise = shaped_noise(seconds, [(600, 420, 1.2), (1700, 950, 1.0)], seed=21)
    hiss = shaped_noise(seconds, [(6000, 2400, 0.35)], seed=22)
    decay = np.exp(-t * 6.5)
    return normalise(soft_clip(noise * decay * 0.8 + hiss * np.exp(-t * 3.0) * 0.5), peak=0.8)


def soft_clip(signal):
    return np.tanh(signal * 1.4) / np.tanh(1.4)


def normalise(signal, peak=0.9):
    top = np.max(np.abs(signal)) or 1.0
    return signal / top * peak


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    files = {
        "melta-burn.ogg": build_loop(),
        "melta-start.ogg": build_start(),
        "melta-stop.ogg": build_stop(),
    }
    for name, samples in files.items():
        path = os.path.join(OUT, name)
        sf.write(path, samples.astype(np.float32), RATE, format="OGG", subtype="VORBIS")
        print("%-18s %.2fs  %d bytes" % (name, len(samples) / RATE, os.path.getsize(path)))
