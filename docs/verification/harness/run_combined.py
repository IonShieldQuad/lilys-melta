"""Create the combined-probe map headless, then benchmark it for the long (5 minute) run.

Usage:
  python run_combined.py <run dir> [--ticks N]

The map is built in the probe's on_init, so `--create` writes a save that already holds
every region (pipes, quality row, six firing meltas, asteroids, reach/rotation rig).
`--benchmark` then simulates it: no player exists there, so the probe skips the hover
legs and the screenshots and only logs measurements -- which is exactly the run used for
the 5-minute error sweep and the profiler.
"""
import os
import re
import subprocess
import sys
import time

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")

run = sys.argv[1].replace("\\", "/")
ticks = 18000
if "--ticks" in sys.argv:
    ticks = int(sys.argv[sys.argv.index("--ticks") + 1])

config = run + "/config.ini"
mods = run + "/mods"
save = run + "/write/scene.zip"
log = run + "/write/factorio-current.log"
os.makedirs(run + "/write", exist_ok=True)


def run_logged(label, args, timeout=3600):
    print("%s ..." % label, flush=True)
    if os.path.exists(log):
        os.remove(log)
    t0 = time.time()
    proc = subprocess.run([EXE, "--config", config, "--mod-directory", mods] + args,
                          capture_output=True, text=True, env=ENV, timeout=timeout)
    print("%s rc=%d in %.0f s" % (label, proc.returncode, time.time() - t0), flush=True)
    if proc.returncode != 0:
        print(proc.stdout[-3000:])
        print(proc.stderr[-3000:])
    if not os.path.exists(log):
        print("!! no log written")
        return proc.returncode
    text = open(log, "r", errors="ignore").read()
    keep = [l for l in text.splitlines() if l.strip()]
    open(run + "/out/%s.log" % label, "w", encoding="utf-8").write(text)
    bad = [l for l in keep if re.search(r"\bError\b|\berror\b|LuaError|stack traceback", l)]
    print("%s: %d log lines, %d error-ish lines" % (label, len(keep), len(bad)))
    for line in bad[:8]:
        print("   !! " + line[:220])
    return proc.returncode


if "--benchmark-only" not in sys.argv:
    run_logged("create", ["--create", save])
if "--create-only" in sys.argv:
    print("CREATE COMPLETE")
    raise SystemExit(0)
run_logged("benchmark", ["--benchmark", save, "--benchmark-ticks", str(ticks)])

text = open(run + "/out/benchmark.log", "r", errors="ignore").read()
for line in text.splitlines():
    if "[comb]" in line and ("drops" in line or "PROFILE" in line or "DONE" in line
                            or "ARRIVED" in line or "crossing" in line or "KILL" in line
                            or "reach " in line or "objects" in line or "prototype" in line
                            or "quality " in line or "FAILED" in line):
        print(line)
print("CREATE+BENCHMARK COMPLETE")
