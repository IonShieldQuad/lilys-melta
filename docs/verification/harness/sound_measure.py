"""Measure the melta sound set against the vanilla weapons it has to sit between.

Everything here reads the real OGG files (decode -> float, then maths). It never
trusts the generator's idea of what it wrote, which is the point: the generator
normalises, this script says whether the result is actually at the level and the
balance the prototype claims.

Usage (from the repo root):
    python docs/verification/harness/sound_measure.py \
        [--old-start path/to/HEAD/melta-start.ogg] [--old-burn ...]

Without the --old-* arguments the two replaced files are taken from git HEAD, so a
before/after table can be produced from any checkout:
    git show HEAD:sound/melta-start.ogg > /tmp/old-start.ogg   (or pass the path)

Tables printed:
  1. format + loudness  -- file dBFS RMS/peak x the `volume` field in the prototype
  2. layering           -- band energy relative to the file's total
  3. distinctness       -- the three variations against each other, and the shot
                           against the laser and gun turret profiles
  4. overlap            -- worst-case peak of two shots summed at prototype volume
  5. one-shot hygiene   -- onset, first-sample step, tail, loop seam
"""
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

RATE = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
MOD = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FACTORIO = r"E:/SteamLibrary/steamapps/common/Factorio"
FIGHT = os.path.join(FACTORIO, "data/base/sound/fight")
TMP = tempfile.mkdtemp(prefix="melta-measure-")


def tool(name):
    """CreateProcess cannot use an MSYS PATH entry; resolve to a native path."""
    found = shutil.which(name) or name
    if re.match(r"^/[a-z]/", found):
        found = found[1].upper() + ":" + found[2:]
    return found


FFMPEG, FFPROBE = tool("ffmpeg"), tool("ffprobe")


def decode(path):
    wav = os.path.join(TMP, "d.wav")
    subprocess.run([FFMPEG, "-y", "-v", "error", "-i", path, "-ac", "1", "-ar", str(RATE),
                    "-c:a", "pcm_s16le", wav], check=True)
    with wave.open(wav, "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0


def probe(path):
    return subprocess.run([FFPROBE, "-v", "error", "-show_entries",
                           "stream=codec_name,sample_rate,channels", "-of", "csv=p=0", path],
                          capture_output=True, text=True, check=True).stdout.strip()


def db(x):
    return 20 * np.log10(x + 1e-12)


BANDS = {"sub20-120": (20, 120), "low120-400": (120, 400), "mid400-2k": (400, 2000),
         "hi2k-6k": (2000, 6000), "air6k-16k": (6000, 16000)}


def bands(x):
    spec = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), 1 / RATE)
    total = spec[(freqs >= 20) & (freqs < 20000)].sum()
    return {k: 10 * np.log10(spec[(freqs >= lo) & (freqs < hi)].sum() / total + 1e-20)
            for k, (lo, hi) in BANDS.items()}


def git_head_file(rel, dest):
    try:
        blob = subprocess.run(["git", "-C", MOD, "show", "HEAD:" + rel],
                              capture_output=True, check=True).stdout
    except subprocess.CalledProcessError:
        return None
    with open(dest, "wb") as f:
        f.write(blob)
    return dest


def collect():
    """(path, label, volume) for the shipped set and the reference weapons."""
    shipped = [
        ("sound/melta-fire-1.ogg", "melta-fire-1 (shot A)", 0.7),
        ("sound/melta-fire-2.ogg", "melta-fire-2 (shot B)", 0.7),
        ("sound/melta-fire-3.ogg", "melta-fire-3 (shot C)", 0.7),
        ("sound/melta-burn.ogg", "melta-burn (held loop)", 0.7),
        ("sound/melta-stop.ogg", "melta-stop (shut-down)", 0.7),
    ]
    out = [(os.path.join(MOD, p), label, vol) for p, label, vol in shipped]
    refs = [
        ("flamethrower-turret-start-1.ogg", "vanilla flamer igniter", 0.5),
        ("flamethrower-turret-mid-1.ogg", "vanilla flamer loop", 0.5),
        ("gun-turret-gunshot-1.ogg", "vanilla gun turret shot", 0.4),
        ("laser-1.ogg", "vanilla laser turret shot", 0.5),
    ]
    out += [(os.path.join(FIGHT, f), label, vol) for f, label, vol in refs]
    return out


def main(argv):
    old = {}
    for i, a in enumerate(argv):
        if a.startswith("--old-") and i + 1 < len(argv):
            old[a[2:]] = argv[i + 1]
    if "old-start" not in old:
        p = git_head_file("sound/melta-start.ogg", os.path.join(TMP, "old-start.ogg"))
        if p:
            old["old-start"] = p
    if "old-burn" not in old:
        p = git_head_file("sound/melta-burn.ogg", os.path.join(TMP, "old-burn.ogg"))
        if p:
            old["old-burn"] = p

    entries = collect()
    for key, label in (("old-start", "melta-start (replaced)"), ("old-burn", "melta-burn (replaced)")):
        if key in old and os.path.exists(old[key]):
            entries.insert(2 if key == "old-start" else 3, (old[key], label, 0.7))

    print("=== 1. format + loudness (effective = file RMS dBFS + 20log10(volume)) ===")
    print("%-28s %-20s %6s %7s %7s %8s %9s"
          % ("file", "stream", "sec", "rms", "peak", "volume", "effective"))
    data = {}
    for path, label, vol in entries:
        if not os.path.exists(path):
            print("%-28s MISSING (%s)" % (label, path))
            continue
        x = decode(path)
        rms, pk = float(db(np.sqrt(np.mean(x ** 2)))), float(db(np.max(np.abs(x))))
        data[label] = {"path": path, "rms": rms, "peak": pk, "vol": vol,
                       "eff": rms + 20 * np.log10(vol), "sec": len(x) / RATE,
                       "bands": bands(x), "x": x}
        print("%-28s %-20s %6.2f %7.2f %7.2f %8.2f %9.2f"
              % (label, probe(path), len(x) / RATE, rms, pk, vol, rms + 20 * np.log10(vol)))

    print()
    print("=== 2. layering: band energy relative to the file's total ===")
    print("%-28s %s" % ("file", " ".join("%10s" % k for k in BANDS)))
    for label, d in data.items():
        print("%-28s %s" % (label, " ".join("%10.1f" % d["bands"][k] for k in BANDS)))

    shots = [data[k]["x"] for k in ("melta-fire-1 (shot A)", "melta-fire-2 (shot B)",
                                    "melta-fire-3 (shot C)") if k in data]
    if len(shots) == 3:
        print()
        print("=== 3. distinctness between the three variations ===")
        n = min(len(a) for a in shots)
        for i, j in itertools.combinations(range(3), 2):
            a = (shots[i][:n] - shots[i][:n].mean()) / (shots[i][:n].std() + 1e-12)
            b = (shots[j][:n] - shots[j][:n].mean()) / (shots[j][:n].std() + 1e-12)
            xc = float(np.max(np.abs(np.correlate(a[:n // 2], b[:n // 2], "full"))) / (n // 2))
            print("  shot %d vs shot %d: max cross-correlation %.3f" % (i + 1, j + 1, xc))
        print("  (1.000 would be the same file twice)")

        print()
        print("=== 3b. spectral distance from the weapons it must not sound like ===")
        b1 = data["melta-fire-1 (shot A)"]["bands"]
        for ref in ("vanilla laser turret shot", "vanilla gun turret shot", "vanilla flamer igniter"):
            if ref in data:
                d = float(np.sqrt(sum((b1[k] - data[ref]["bands"][k]) ** 2 for k in BANDS)))
                print("  %-28s %5.1f dB" % (ref, d))

        print()
        print("=== 4. overlap: two shots summed at the prototype volume ===")
        worst = -999.0
        for i in range(3):
            for j in range(3):
                a = shots[i] * 0.7
                b = shots[j] * 0.7
                for off_ms in (0, 5, 10, 20, 40):
                    off = int(off_ms / 1000 * RATE)
                    mix = a.copy()
                    if off < len(mix):
                        k = min(len(mix) - off, len(b))
                        mix[:k] += b[:k]
                    worst = max(worst, float(db(np.max(np.abs(mix)))))
        print("  worst peak over all 9 pairs x 5 offsets: %.2f dBFS" % worst)
        if "melta-burn (held loop)" in data:
            loop = data["melta-burn (held loop)"]["x"] * 0.7
            print("  two identical loops fully in phase (upper bound): %.2f dBFS"
                  % float(db(np.max(np.abs(loop * 2)))))

    print()
    print("=== 5. one-shot hygiene ===")
    for i in (1, 2, 3):
        key = "melta-fire-%d (shot %s)" % (i, "ABC"[i - 1])
        if key not in data:
            continue
        x = data[key]["x"]
        top = np.max(np.abs(x))
        onset = int(np.argmax(np.abs(x) > 0.10 * top)) / RATE * 1000
        head = np.max(np.abs(x[:int(0.005 * RATE)]))
        print("  %s: onset %.2f ms, first 5 ms %.1f dB below the file peak, sample0 %.4f, last %+.5f"
              % (key, onset, float(db(top) - db(head)), x[0], x[-1]))
    if "melta-burn (held loop)" in data:
        burn = data["melta-burn (held loop)"]["x"]
        step = abs(burn[0] - burn[-1])
        typical = float(np.mean(np.abs(np.diff(burn))))
        print("  loop seam: |last-first| %.5f vs mean |step| %.5f -> %s"
              % (step, typical, "continuous" if step < 3 * typical else "AUDIBLE JUMP"))

    with open(os.path.join(HERE, "sound-measure.json"), "w") as f:
        json.dump({k: {kk: vv for kk, vv in v.items() if kk != "x"} for k, v in data.items()},
                  f, indent=1)
    print("\nwrote %s" % os.path.join(HERE, "sound-measure.json"))


if __name__ == "__main__":
    main(sys.argv[1:])
