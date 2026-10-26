"""In-game look pass: screenshot the melta turret next to vanilla turrets.

Stages an isolated run directory (its own write-data, so her saves / mod-list / log are
untouched), copies the mod tree under test plus the `melta-look` probe, `--create`s the
scene headless, then loads it in a GUI Factorio -- the only place the sprite atlas is
built -- and collects the screenshots the probe requests.

    python docs/verification/harness/run_look.py <run dir> [--tree <repo or dir>]

`--tree` defaults to the repo this file lives in, so the normal use is "screenshot the
working tree". Point it at a `git archive` export to photograph another revision
(that is how the before/after pair is produced).

Screenshots land in <run>/write/script-output/look/; the probe logs `MELTA LOOK DONE`.
Steam needs the AppID in the environment (`SteamAppId=427520`), otherwise the binary
prints "Steam requires game restart" and exits before anything renders.
"""
import os
import re
import shutil
import subprocess
import sys
import time

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520",
           SteamOverlayGameId="427520")
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
COPY = ["info.json", "changelog.txt", "constants.lua", "control.lua", "data.lua",
        "data-updates.lua", "prototypes", "graphics", "locale", "sound"]


def stage(run, tree):
    moddir = os.path.join(run, "mods")
    os.makedirs(os.path.join(moddir, "lilys-melta"), exist_ok=True)
    os.makedirs(os.path.join(moddir, "melta-look"), exist_ok=True)
    os.makedirs(os.path.join(run, "write"), exist_ok=True)
    for item in COPY:
        src = os.path.join(tree, item)
        if not os.path.exists(src):
            continue
        dst = os.path.join(moddir, "lilys-melta", item)
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    for item in ("info.json", "data.lua", "control.lua"):
        shutil.copy2(os.path.join(HERE, "melta-look", item),
                     os.path.join(moddir, "melta-look", item))
    with open(os.path.join(run, "config.ini"), "w", newline="\r\n") as fh:
        fh.write("[path]\nwrite-data=%s/write\n[graphics]\nmax-texture-size=4096\n"
                 % run.replace("\\", "/"))
    with open(os.path.join(moddir, "mod-list.json"), "w") as fh:
        fh.write('{"mods": [{"name": "base", "enabled": true}, '
                 '{"name": "lilys-melta", "enabled": true}, '
                 '{"name": "melta-look", "enabled": true}]}\n')
    return moddir


def create(run, moddir):
    save = os.path.join(run, "write", "look.zip")
    log = os.path.join(run, "write", "factorio-current.log")
    if os.path.exists(log):
        os.remove(log)
    subprocess.run([EXE, "--config", os.path.join(run, "config.ini"),
                    "--mod-directory", moddir, "--create", save],
                   capture_output=True, text=True, env=ENV, timeout=900)
    text = open(log, errors="ignore").read() if os.path.exists(log) else ""
    errs = [l for l in text.splitlines()
            if re.search(r"Error|error while running|stack traceback", l)]
    for line in errs[:8]:
        print("   !! " + line[:220])
    print("create: %d log lines, %d error-ish, save=%s"
          % (len(text.splitlines()), len(errs), os.path.exists(save)))
    return save


def gui(run, moddir, save, attempts=3):
    log = os.path.join(run, "write", "factorio-current.log")
    for number in range(1, attempts + 1):
        # A previous attempt's process can still hold the log open for a few seconds
        # after taskkill returns; removing it then raises WinError 32 and kills the
        # whole pass. Wait for the handle instead of assuming it is gone.
        for _ in range(30):
            try:
                if os.path.exists(log):
                    os.remove(log)
                break
            except PermissionError:
                time.sleep(1)
        print("attempt %d: launching gui ..." % number, flush=True)
        proc = subprocess.Popen([EXE, "--config", os.path.join(run, "config.ini"),
                                 "--mod-directory", moddir, "--load-game", save],
                                env=ENV)
        deadline = time.time() + 420
        state = "timeout"
        while time.time() < deadline:
            time.sleep(1)
            try:
                if os.path.exists(log):
                    text = open(log, errors="ignore").read()
                    if "MELTA LOOK DONE" in text:
                        state = "done"
                        break
                    if "Error while running" in text or "Failed to load mods" in text:
                        state = "error"
                        break
            except (PermissionError, OSError):
                pass
            if proc.poll() is not None:
                state = "exited"
                break
        print("attempt %d: %s" % (number, state), flush=True)
        time.sleep(2)
        if proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/F"],
                           capture_output=True)
            try:
                proc.wait(timeout=30)
            except Exception:
                pass
        if state == "done":
            return True
        time.sleep(5)
    return False


def main():
    run = os.path.abspath(sys.argv[1])
    tree = HERE
    if "--tree" in sys.argv:
        tree = os.path.abspath(sys.argv[sys.argv.index("--tree") + 1])
    if not os.path.exists(os.path.join(tree, "info.json")):
        raise SystemExit("--tree %s has no info.json (not a mod tree)" % tree)
    print("tree:", tree)
    moddir = stage(run, tree)
    save = create(run, moddir)
    ok = gui(run, moddir, save)

    log = os.path.join(run, "write", "factorio-current.log")
    text = open(log, errors="ignore").read() if os.path.exists(log) else ""
    for line in text.splitlines():
        if "[look]" in line:
            print(line)
    for line in text.splitlines():
        if re.search(r"Error|Failed to load", line) and "0." not in line[:6]:
            print("!! " + line[:220])
    out = os.path.join(run, "write", "script-output", "look")
    names = sorted(os.listdir(out)) if os.path.isdir(out) else []
    print("screenshots in", out)
    for name in names:
        print("   ", name)
    print("LOOK PASS COMPLETE" if ok and names else "LOOK PASS INCOMPLETE")
    raise SystemExit(0 if ok and names else 1)


main()
