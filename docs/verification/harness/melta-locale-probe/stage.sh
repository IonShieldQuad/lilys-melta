#!/usr/bin/env bash
# Stage an isolated Factorio environment for the melta locale/tooltip check.
#
#   ./stage.sh new [rev] [language]   the working tree (what the card changes)
#   ./stage.sh head [rev] [language]  a git revision instead (the before/after pair)
#
# Her own install, saves, mod-list and factorio-current.log are never touched: the
# environment gets its own --config (write-data in scratch) and --mod-directory.
#
# Then, in the printed directory:
#   Factorio.exe --config <env>/config.ini --mod-directory <env>/mods --create <env>/write/scene.zip
#   grep -a "\[locale-probe\]" <env>/write/factorio-current.log   # resolved strings, no GUI
#   python capture.py <env> <env>/out                             # real tooltip screenshots
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCR="${MELTA_PROBE_SCRATCH:-C:/Users/Lily/AppData/Local/hermes/cache/scratch}"
KIND="${1:?usage: stage.sh new|head [rev] [language]}"
REV="${2:-HEAD}"
LANGUAGE_CODE="${3:-en}"
W="$SCR/melta-locale-$KIND-$LANGUAGE_CODE"

mkdir -p "$W/mods/lilys-melta" "$W/mods/melta-locale-probe" "$W/write" "$W/out"

if [ "$KIND" = "head" ]; then
  ( cd "$REPO" && tar -cf - --exclude=.git --exclude='*.zip' \
      info.json data.lua data-updates.lua control.lua constants.lua \
      prototypes graphics sound changelog.txt ) \
    | ( cd "$W/mods/lilys-melta" && tar -xf - )
  # the locale files from the revision, not from the working tree
  for f in locale/en/locale.cfg locale/ru/locale.cfg; do
    mkdir -p "$W/mods/lilys-melta/$(dirname "$f")"
    git -C "$REPO" show "$REV:$f" > "$W/mods/lilys-melta/$f"
  done
else
  ( cd "$REPO" && tar -cf - --exclude=.git --exclude='*.zip' \
      info.json data.lua data-updates.lua control.lua constants.lua \
      prototypes locale graphics sound changelog.txt ) \
    | ( cd "$W/mods/lilys-melta" && tar -xf - )
fi

cp "$REPO/docs/verification/harness/melta-locale-probe/"{info.json,control.lua} \
   "$W/mods/melta-locale-probe/"

# the key is `locale`, not `language` -- a config with `language=` is silently ignored
# and the game comes up in English, which is exactly what a locale check must not do
printf '[general]\r\nlocale=%s\r\n\r\n[path]\r\nwrite-data=%s/write\r\n' \
  "$LANGUAGE_CODE" "$W" > "$W/config.ini"

cat > "$W/mods/mod-list.json" <<JSON
{
  "mods": [
    {"name": "base", "enabled": true},
    {"name": "quality", "enabled": true},
    {"name": "space-age", "enabled": true},
    {"name": "elevated-rails", "enabled": true},
    {"name": "recycler", "enabled": true},
    {"name": "lilys-melta", "enabled": true},
    {"name": "melta-locale-probe", "enabled": true}
  ]
}
JSON

echo "staged $W"
