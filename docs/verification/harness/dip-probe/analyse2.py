import re, statistics, collections

path = r"C:/Users/Lily/AppData/Local/hermes/cache/scratch/dip-probe/write/factorio-current.log"
rows = []
for line in open(path, encoding="utf-8", errors="replace"):
    m = re.search(r"\[dip\] t=(\d+) ph=(\w+) ghp=([\d.-]+) ammo=(-?\d+) fhp=([\d.-]+) ffluid=(-?\d+)", line)
    if m:
        rows.append((int(m.group(1)), m.group(2), float(m.group(3))))

rows.sort()
phases = ["none", "ammo", "turret", "both"]
print("gun turret: per-shot damage (drop in dummy health per shot), boundary ticks trimmed\n")
for ph in phases:
    seq = [(t, hp) for t, p, hp in rows if p == ph]
    if len(seq) < 10:
        continue
    seq = seq[3:-3]                      # trim transition contamination
    drops = [round(seq[i][1] - seq[i+1][1], 2) for i in range(len(seq)-1)]
    shots = [d for d in drops if d > 0.5]
    counts = collections.Counter(shots)
    print("  %-7s shots=%3d  drop sizes=%s  median=%.2f  std=%.3f" % (
        ph, len(shots), dict(sorted(counts.items())),
        statistics.median(shots) if shots else -1,
        statistics.pstdev(shots) if shots else -1))
