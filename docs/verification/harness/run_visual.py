"""Run the melta visual probe in a real GUI Factorio, retrying until it reports DONE.

Usage: python run_visual.py <run-dir>

One run dir = one config.ini + one mods/ tree. The map is created once headless, then
loaded in a GUI run (screenshots need a renderer). Retries exist because other cards on
this machine close whatever Factorio window is in front of them; the probe finishes in a
couple of seconds at 4x speed so it usually wins. The Steam build refuses a direct launch
unless the process is handed Steam's app ids.
"""
import os
import subprocess
import sys
import time

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520",
           SteamOverlayGameId="427520")
ATTEMPTS = 4

run = sys.argv[1].replace("\\", "/")
config = run + "/config.ini"
mods = run + "/mods"
save = run + "/write/visual.zip"
log = run + "/write/factorio-current.log"

os.makedirs(run + "/write", exist_ok=True)

if not os.path.exists(save):
    print("creating map ...", flush=True)
    created = subprocess.run([EXE, "--config", config, "--mod-directory", mods,
                              "--create", save],
                             capture_output=True, text=True, env=ENV, timeout=600)
    print("create rc=%d" % created.returncode, flush=True)
    if created.returncode != 0:
        print(created.stdout[-2000:], created.stderr[-2000:])
        raise SystemExit(1)


def attempt(number):
    if os.path.exists(log):
        os.remove(log)
    print("attempt %d: launching gui run ..." % number, flush=True)
    proc = subprocess.Popen([EXE, "--config", config, "--mod-directory", mods,
                             "--load-game", save], env=ENV)
    deadline = time.time() + 300
    state = "timeout"
    while time.time() < deadline:
        time.sleep(1)
        if os.path.exists(log):
            text = open(log, "r", errors="ignore").read()
            if "VIS PROBE DONE" in text:
                state = "done"
                break
            if "non-recoverable error" in text:
                state = "errored"
                break
        if proc.poll() is not None:
            state = "exited"
            break
    print("attempt %d: %s" % (number, state), flush=True)
    time.sleep(3)
    if proc.poll() is None:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"], capture_output=True)
    return state == "done"


ok = False
for number in range(1, ATTEMPTS + 1):
    if attempt(number):
        ok = True
        break
    time.sleep(2)

text = open(log, "r", errors="ignore").read() if os.path.exists(log) else ""
for line in text.splitlines():
    if "[vis]" in line:
        print(line.split("[vis] ", 1)[-1])
for line in text.splitlines():
    if "Error" in line or "error" in line:
        print("!! " + line.strip()[:300])
shots = run + "/write/script-output/visual"
if os.path.isdir(shots):
    print("shots:", len(os.listdir(shots)))
    for name in sorted(os.listdir(shots)):
        print("  ", name)
print("PROBE COMPLETE" if ok else "PROBE INCOMPLETE")
raise SystemExit(0 if ok else 1)
