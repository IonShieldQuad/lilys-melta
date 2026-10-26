#!/usr/bin/env bash
# Stage an isolated Factorio environment for the item-order check (crafting-menu placement).
#
#   ./stage.sh new             the working tree (convenient, but it carries whatever sibling
#                              cards have uncommitted in this repo at that moment)
#   ./stage.sh rev <rev>       a committed tree, official mods OFF -- use this for evidence:
#                              it cannot be polluted by another worker's half-finished edit
#   ./stage.sh official [rev]  a committed tree with the official mod set ON (base + space age
#                              + quality + elevated rails + recycler) -- this is the turret
#                              ladder Lily actually sees, seven vanilla turrets plus the melta
#
# Her own install, saves, mod-list and factorio-current.log are never touched: the
# environment gets its own --config (write-data in scratch) and --mod-directory.
#
# Then, in the printed directory:
#   Factorio.exe --config <env>/config.ini --mod-directory <env>/mods --create <env>/write/scene.zip
#   Factorio.exe --config <env>/config.ini --mod-directory <env>/mods --dump-data
#   python check_order.py <env>/write/script-output/data-raw-dump.json
#   python run_gui.py <env> <env>/out/gui
set -euo pipefail

REPO="H:/Factorio Mods/lilys-melta"
SCR="${MELTA_PROBE_SCRATCH:-C:/Users/Lily/AppData/Local/hermes/cache/scratch}"
KIND="${1:?usage: stage.sh new|rev <rev>|official [rev]}"
REV="${2:-HEAD}"
W="$SCR/melta-itemorder-$KIND"

mkdir -p "$W/mods/lilys-melta" "$W/mods/melta-itemorder" "$W/write" "$W/out"

case "$KIND" in
  rev|official)
    # straight out of the object store, so the staged tree is exactly the commit
    git -C "$REPO" archive --format=tar --output="$W/src.tar" "$REV"
    python -c "import sys, tarfile; tarfile.open(sys.argv[1]).extractall(sys.argv[2])" \
      "$W/src.tar" "$W/mods/lilys-melta"
    ;;
  new)
    ( cd "$REPO" && tar -cf - --exclude=.git --exclude='*.zip' \
        info.json data.lua data-updates.lua control.lua constants.lua \
        prototypes locale graphics sound changelog.txt ) \
      | ( cd "$W/mods/lilys-melta" && tar -xf - )
    ;;
  *)
    echo "unknown kind $KIND (use new, rev or official)" >&2
    exit 2
    ;;
esac

cp "$REPO/docs/verification/harness/melta-itemorder/"{info.json,control.lua} "$W/mods/melta-itemorder/"

printf '[path]\r\nwrite-data=%s/write\r\n' "$W" > "$W/config.ini"

# space age adds rocket/tesla/railgun to the turret subgroup, so its ladder is a different
# (longer) list than base's -- stage the one the check is meant to prove
OFFICIAL="false"
[ "$KIND" = "official" ] && OFFICIAL="true"

cat > "$W/mods/mod-list.json" <<JSON
{
  "mods": [
    {"name": "base", "enabled": true},
    {"name": "quality", "enabled": $OFFICIAL},
    {"name": "space-age", "enabled": $OFFICIAL},
    {"name": "elevated-rails", "enabled": $OFFICIAL},
    {"name": "recycler", "enabled": $OFFICIAL},
    {"name": "lilys-melta", "enabled": true},
    {"name": "melta-itemorder", "enabled": true}
  ]
}
JSON

echo "staged $W"
