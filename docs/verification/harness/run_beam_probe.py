"""Run the beam probe in a real GUI Factorio, retrying until the probe reports DONE.

One argument: the run directory (with config.ini and mods/). The map is created once
headless, then loaded in a GUI run. Retries exist because other cards on this machine
close whatever Factorio window is in front of them -- the probe finishes in a couple of
seconds at 4x speed so it usually wins, but not always.

The Steam build refuses a direct launch ("Steam requires game restart, restarting...")
unless the process is handed Steam's app ids -- SteamAppId/SteamGameId in the environment
is enough, and it is what makes this scriptable without clicking a launch dialog.
"""
import os
import subprocess
import sys
import time

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
ATTEMPTS = 4

run = sys.argv[1].replace("\\", "/")
config = run + "/config.ini"
mods = run + "/mods"
save = run + "/write/beam.zip"
log = run + "/write/factorio-current.log"

os.makedirs(run + "/write", exist_ok=True)

if not os.path.exists(save):
    print("creating map ...", flush=True)
    created = subprocess.run([EXE, "--config", config, "--mod-directory", mods, "--create", save],
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
    deadline = time.time() + 240
    state = "timeout"
    while time.time() < deadline:
        time.sleep(1)
        if os.path.exists(log):
            text = open(log, "r", errors="ignore").read()
            if "BEAM PROBE DONE" in text:
                state = "done"
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
    if "[beam]" in line:
        print(line)
bad = [line for line in text.splitlines()
       if line.startswith(" ") and ("Error" in line or "error" in line)]
for line in bad[:10]:
    print("!! " + line)
print("PROBE COMPLETE" if ok else "PROBE INCOMPLETE")
raise SystemExit(0 if ok else 1)
