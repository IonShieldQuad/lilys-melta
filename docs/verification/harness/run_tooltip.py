"""Prove the tooltip the player will read, headless.

Copies the already-staged `melta-balance-after` mod tree (HEAD + this card's files)
into a fresh env together with the locale probe, runs one `--create` (which runs
on_init, where `localised_print` resolves real locale strings) and prints the
[locale-probe] lines: every key plus the item and entity description bodies.
"""
import json
import os
import shutil
import subprocess

EXE = r"E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe"
SCRATCH = r"C:/Users/Lily/AppData/Local/hermes/cache/scratch"
STEAM_ENV = dict(os.environ, SteamAppId="427520", SteamGameId="427520", SteamOverlayGameId="427520")
REPO_PROBE = r"H:/Factorio Mods/lilys-melta/docs/verification/harness/melta-locale-probe"

root = SCRATCH + "/melta-tooltip"
if os.path.exists(root):
    shutil.rmtree(root)
os.makedirs(root + "/write")
shutil.copytree(SCRATCH + "/melta-balance-after/mods/lilys-melta", root + "/mods/lilys-melta")
shutil.copytree(REPO_PROBE, root + "/mods/melta-locale-probe")
with open(root + "/config.ini", "w") as handle:
    handle.write("[path]\nwrite-data=%s/write\n" % root)
with open(root + "/mods/mod-list.json", "w") as handle:
    json.dump({"mods": [
        {"name": "base", "enabled": True},
        {"name": "lilys-melta", "enabled": True},
        {"name": "melta-locale-probe", "enabled": True},
    ]}, handle, indent=2)

created = subprocess.run([EXE, "--config", root + "/config.ini", "--mod-directory", root + "/mods",
                          "--create", root + "/write/probe.zip"],
                         capture_output=True, text=True, env=STEAM_ENV, timeout=900)
print("create rc=%d" % created.returncode)
for line in (created.stdout or "").splitlines():
    if "locale-probe" in line or "melta-tooltip" in line:
        print(line)
log = root + "/write/factorio-current.log"
text = open(log, errors="ignore").read() if os.path.exists(log) else ""
for line in text.splitlines():
    if "[locale-probe]" in line or "localeprobe" in line or "Error" in line:
        print(line)
