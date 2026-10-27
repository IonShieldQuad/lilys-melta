#!/usr/bin/env bash
# Build the isolated Factorio run directory for the PORTAL GALLERY screenshots.
#   setup_gallery.sh <run-dir> <mod-tree>
# Then: python run_gallery.py <run-dir>   (it foregrounds the window; Factorio pauses when
# unfocused, which is what makes an unattended GUI run hang.)
set -euo pipefail
RUN="${1:?run dir}"; SRC="${2:?mod source}"
PROBE="$(cd "$(dirname "$0")" && pwd)/melta-gallery-probe"
rm -rf "$RUN"; mkdir -p "$RUN/mods/lilys-melta" "$RUN/write"
for item in info.json changelog.txt constants.lua control.lua data.lua data-updates.lua \
            prototypes graphics locale sound thumbnail.png thumbnail-144.png; do
  cp -r "$SRC/$item" "$RUN/mods/lilys-melta/"
done
cp -r "$PROBE" "$RUN/mods/gallery-probe"
printf '{"mods":[{"name":"base","enabled":true},{"name":"lilys-melta","enabled":true},{"name":"gallery-probe","enabled":true}]}' > "$RUN/mods/mod-list.json"
python - "$RUN" <<'PY'
import os, re, sys
run = sys.argv[1].replace('\', '/')
src = os.path.join(os.environ['APPDATA'], 'Factorio', 'config', 'config.ini')
text = re.sub(r'(?m)^write-data=.*$', 'write-data=%s/write' % run,
              open(src, encoding='utf-8', errors='ignore').read())
open(os.path.join(run, 'config.ini'), 'w', encoding='utf-8', newline='').write(text)
# the player's real config: a two-line [path] config dies at ROOT.sound
PY
echo "run dir: $RUN"
