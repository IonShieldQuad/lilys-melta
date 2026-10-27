#!/usr/bin/env bash
# Build the isolated Factorio run directory for the melta VISUAL probe (0.6.0 pass).
#
#   setup_visual.sh <run-dir> <mod-tree>
#
# <mod-tree> is either the working tree or a pristine copy (`git archive HEAD | tar -x`),
# which is how the before/after screenshots in docs/verification/visual-rework were made.
# The mod is COPIED, never linked: the game reads files while the repo is being edited.
set -euo pipefail

RUN="${1:?run dir}"
SRC="${2:?mod source}"
PROBE="$(cd "$(dirname "$0")" && pwd)/melta-visual-probe"

rm -rf "$RUN"
mkdir -p "$RUN/mods/lilys-melta" "$RUN/write"
for item in info.json changelog.txt constants.lua control.lua data.lua data-updates.lua \
            prototypes graphics locale sound; do
  cp -r "$SRC/$item" "$RUN/mods/lilys-melta/"
done
cp -r "$PROBE" "$RUN/mods/visual-probe"

cat > "$RUN/config.ini" <<INI
[path]
write-data=$RUN/write
[graphics]
max-texture-size=4096
INI

cat > "$RUN/mods/mod-list.json" <<'JSON'
{"mods":[
 {"name":"base","enabled":true},
 {"name":"lilys-melta","enabled":true},
 {"name":"visual-probe","enabled":true},
 {"name":"elevated-rails","enabled":false},
 {"name":"quality","enabled":false},
 {"name":"recycler","enabled":false},
 {"name":"space-age","enabled":false}]}
JSON

echo "run dir: $RUN"
