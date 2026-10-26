"""Stage two melta test environments (before = git HEAD, after = working tree with
the balance patch) and run the balance probe in each, headless.

Usage: python run_balance.py before|after|both
Prints the [balance] log lines of each run.
"""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import io

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
REPO = r"H:/Factorio Mods/lilys-melta"
PROBE = os.path.join(REPO, r"docs/verification/harness/melta-balance-probe")
SCRATCH = r"C:/Users/Lily/AppData/Local/hermes/cache/scratch"
STEAM_ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
TICKS = "2200"

# the files this card changed; "after" = HEAD + these, everything else from HEAD so a
# sibling card's half-finished work cannot leak into the measurement
CHANGED = ["constants.lua", "control.lua", "data-updates.lua",
           "prototypes/tooltip.lua", "locale/en/locale.cfg", "locale/ru/locale.cfg"]


def extract_head(dest):
    """git archive HEAD -> dest (no checkout side effects, no dirty files)."""
    archive = subprocess.run(["git", "-C", REPO, "archive", "--format=tar", "HEAD"],
                             capture_output=True)
    if archive.returncode != 0:
        raise SystemExit("git archive failed: " + archive.stderr.decode("utf-8", "ignore")[-800:])
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(dest)


def copy_tree(src, dest):
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(src, dest)


def stage(label):
    root = os.path.join(SCRATCH, "melta-balance-" + label).replace("\\", "/")
    mods = root + "/mods"
    write = root + "/write"
    if os.path.exists(root):
        shutil.rmtree(root)
    os.makedirs(mods)
    os.makedirs(write, exist_ok=True)

    mod = mods + "/lilys-melta"
    extract_head(mod)
    if label == "after":
        for relative in CHANGED:
            source = os.path.join(REPO, relative.replace("/", os.sep))
            target = os.path.join(mod, relative.replace("/", os.sep))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copyfile(source, target)

    copy_tree(PROBE, mods + "/melta-balance-probe")

    mods_here = {}
    for entry in sorted(os.listdir(mods + "/lilys-melta")):
        mods_here[entry] = True
    print("staged %s: %d entries" % (label, len(mods_here)))

    mod_list = {
        "mods": [
            {"name": "base", "enabled": True},
            {"name": "lilys-melta", "enabled": True},
            {"name": "melta-balance-probe", "enabled": True},
            {"name": "space-age", "enabled": True},
            {"name": "elevated-rails", "enabled": True},
            {"name": "quality", "enabled": True},
            {"name": "recycler", "enabled": True},
        ]
    }
    with open(mods + "/mod-list.json", "w") as handle:
        json.dump(mod_list, handle, indent=2)

    with open(root + "/config.ini", "w") as handle:
        handle.write("[path]\nwrite-data=%s/write\n" % root)

    save = write + "/balance.zip"
    create = subprocess.run([EXE, "--config", root + "/config.ini", "--mod-directory", mods,
                             "--create", save], capture_output=True, text=True,
                            env=STEAM_ENV, timeout=900)
    print("%s create rc=%d" % (label, create.returncode))
    if create.returncode != 0:
        tail = (create.stdout or "")[-1500:] + (create.stderr or "")[-1500:]
        print(tail)
        log = write + "/factorio-current.log"
        if os.path.exists(log):
            text = open(log, errors="ignore").read()
            print("\n".join(text.splitlines()[-40:]))
        return None

    run = subprocess.run([EXE, "--config", root + "/config.ini", "--mod-directory", mods,
                          "--benchmark", save, "--benchmark-ticks", TICKS],
                         capture_output=True, text=True, env=STEAM_ENV, timeout=1800)
    print("%s benchmark rc=%d" % (label, run.returncode))
    log = write + "/factorio-current.log"
    lines = []
    if os.path.exists(log):
        text = open(log, errors="ignore").read()
        lines = [line for line in text.splitlines() if "[balance]" in line]
        errors = [line for line in text.splitlines()
                  if "Error" in line or "error:" in line or "Failed" in line]
        if errors:
            print("-- errors --")
            print("\n".join(errors[:15]))
    return lines


def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    labels = ["before", "after"] if which == "both" else [which]
    out = {}
    for label in labels:
        print("=" * 70)
        print("RUN", label)
        lines = stage(label)
        out[label] = lines or []
        for line in out[label]:
            print(line)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "balance_runs.json"), "w") as handle:
        json.dump(out, handle, indent=1)


main()
