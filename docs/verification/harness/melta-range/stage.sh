#!/usr/bin/env bash
# Stage an isolated Factorio environment for the melta range / quality / rotation probe.
#
#   ./stage.sh new        the working tree (what the card changes)
#   ./stage.sh head       git HEAD~1 of that work — pass a rev instead to pick any tree:
#                         ./stage.sh head d2216b2
#   ./stage.sh noquality  the working tree with the quality mod disabled
#
# Her own install, saves, mod-list and factorio-current.log are never touched: the
# environment gets its own --config (write-data in scratch) and --mod-directory.
#
# Then, in the printed directory:
#   Factorio.exe --config <env>/config.ini --mod-directory <env>/mods --create <env>/save.zip
#   Factorio.exe --config <env>/config.ini --mod-directory <env>/mods \
#                --benchmark <env>/save.zip --benchmark-ticks 320
#   grep "\[range\]" <env>/write/factorio-current.log
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
SCR="${MELTA_PROBE_SCRATCH:-C:/Users/Lily/AppData/Local/hermes/cache/scratch}"
KIND="${1:?usage: stage.sh new|head [rev]|noquality}"
REV="${2:-HEAD}"
ENV_NAME="melta-$KIND"
W="$SCR/$ENV_NAME"

rm -rf "$W"
mkdir -p "$W/mods/lilys-melta" "$W/mods/melta-range" "$W/write"

# the mod itself, from the repo worktree
( cd "$REPO" && tar -cf - --exclude=.git --exclude='*.zip' \
    info.json data.lua data-updates.lua control.lua constants.lua \
    prototypes locale graphics sound changelog.txt ) \
  | ( cd "$W/mods/lilys-melta" && tar -xf - )

if [ "$KIND" = "head" ]; then
  # the four files this card touches, as they were before it
  for f in constants.lua control.lua prototypes/entity.lua locale/en/locale.cfg; do
    git -C "$REPO" show "$REV:$f" > "$W/mods/lilys-melta/$f"
  done
fi

cp "$REPO/docs/verification/harness/melta-range/"{info.json,data.lua,control.lua} "$W/mods/melta-range/"

printf '[path]\r\nwrite-data=%s/write\r\n' "$W" > "$W/config.ini"

quality=true
[ "$KIND" = "noquality" ] && quality=false
cat > "$W/mods/mod-list.json" <<JSON
{
  "mods": [
    {"name": "base", "enabled": true},
    {"name": "quality", "enabled": $quality},
    {"name": "lilys-melta", "enabled": true},
    {"name": "melta-range", "enabled": true}
  ]
}
JSON

echo "staged $W"
