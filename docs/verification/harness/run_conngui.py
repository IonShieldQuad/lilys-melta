"""Run the pipe-connection probe in a real GUI Factorio and collect its screenshots.

The map is created once headless (that is where on_init builds the scene and the
engine's connection graph is logged), then loaded in a GUI run: only a GUI builds
the sprite atlas, so this is also the only place a wrong `width`/`height` on the new
port sprites would fail.

Argument: the run directory (with config.ini and mods/). The probe writes
`MELTA CONNGUI DONE` to the log when its screenshot schedule finishes; this retries
because other cards on this machine close whatever Factorio window is in front.

Screenshots land in <run>/write/script-output/conn/.
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
mods = run + "/moddir"
save = run + "/save.zip"
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
    deadline = time.time() + 420
    state = "timeout"
    while time.time() < deadline:
        time.sleep(1)
        if os.path.exists(log):
            text = open(log, "r", errors="ignore").read()
            if "MELTA CONNGUI DONE" in text:
                state = "done"
                break
        if proc.poll() is not None:
            state = "exited"
            break
    print("attempt %d: %s" % (number, state), flush=True)
    time.sleep(2)
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
    if "[conn]" in line and ("shot" in line or "overlay" in line or "DONE" in line):
        print(line)
errors = [line for line in text.splitlines()
          if "Error" in line and not line.startswith("   0.")]
for line in errors[:10]:
    print("!! " + line)
out = run + "/write/script-output/conn"
print("screenshots in", out)
for name in sorted(os.listdir(out)) if os.path.isdir(out) else []:
    print("  ", name)
print("GUI PASS COMPLETE" if ok else "GUI PASS INCOMPLETE")
raise SystemExit(0 if ok else 1)
