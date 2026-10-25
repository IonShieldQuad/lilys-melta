"""Assemble the evidence folder for the combined in-game verification pass.

Copies the curated screenshots out of the scratch run (JPEG for 1920x1080 world shots,
PNG for the inspect-panel crops), plus the three run logs, into
docs/verification/in-game-combined/ so the report's evidence is committed with the repo.

Usage: python collect_evidence.py <run dir> <repo docs dir>
"""
import os
import re
import shutil
import sys

from PIL import Image

run = sys.argv[1]
dst = sys.argv[2]

SHOTS = {
    "pipes": ["01-overview", "02-four-way", "03-join-north", "04-join-east",
              "05-capped-ports", "06-shapes", "07-straight", "08-corner",
              "09-t-junction", "10-cross", "11-dead-end", "12-join-south",
              "13-join-west", "14-normal-zoom", "15-capped-port-north"],
    "beam": ["01-six-firing", "02-close-lightoil", "03-close-meltafuel",
             "04-six-zoomed", "05-six-wide", "05-fade-3ticks", "06-fade-gone"],
    "reach": ["01-normal-15", "02-legendary-23"],
    "asteroids": ["01-overview", "02-small-cut", "03-big-cut"],
}

for sub, names in SHOTS.items():
    out = os.path.join(dst, sub)
    os.makedirs(out, exist_ok=True)
    for name in names:
        src = os.path.join(run, "write", "script-output", "combined", sub, name + ".png")
        if not os.path.exists(src):
            print("missing %s" % src)
            continue
        im = Image.open(src).convert("RGB")
        im.save(os.path.join(out, name + ".jpg"), quality=88, optimize=True)
        print("%s/%s.jpg" % (sub, name))

panels = os.path.join(dst, "panels")
os.makedirs(panels, exist_ok=True)
for q in ["normal", "uncommon", "rare", "epic", "legendary"]:
    src = os.path.join(run, "out", "hover", "crop", "panel_q_%s_leg%d.png" % (q, ["normal", "uncommon", "rare", "epic", "legendary"].index(q) + 1))
    if os.path.exists(src):
        shutil.copy(src, os.path.join(panels, "panel_%s.png" % q))
        print("panels/panel_%s.png" % q)
    else:
        print("missing %s" % src)

logs = os.path.join(dst, "logs")
os.makedirs(logs, exist_ok=True)
for name in ["create.log", "gui2.log", "long-run.log"]:
    src = os.path.join(run, "out", name)
    if os.path.exists(src):
        shutil.copy(src, os.path.join(logs, name))
        print("logs/%s" % name)

# measurement digest: every line the report quotes, in one place
keep = re.compile(r"prototype:|quality |pipes [AB]:|rock [0-9]:|KILL rock|pulse #|swing |crossing |"
                  r"reach |median_recent|objects total=|objects after kill|IDLE window|PROFILER|"
                  r"beam dummies|COMBINED PROBE DONE|display rocks")
lines = []
for name in ["create.log", "gui2.log", "long-run.log"]:
    path = os.path.join(run, "out", name)
    if not os.path.exists(path):
        continue
    lines.append("===== %s" % name)
    with open(path, "r", errors="ignore") as fh:
        for line in fh:
            if keep.search(line):
                lines.append(line.rstrip())
open(os.path.join(logs, "measurements.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("logs/measurements.txt (%d lines)" % len(lines))
