#!/usr/bin/env bash
# Stage an isolated Factorio run directory for the combined melta verification pass.
#
#   - private write-data dir: her saves, blueprints, mod-list and log are never touched
#   - a COPY of the mod tree under test, so edits in the repo cannot change the run
#   - base + space-age + quality + recycler + elevated-rails, all enabled: the pass has
#     to cover the asteroid channel (space-age) and quality scaling (quality) at once
#
# Then:
#   python docs/verification/harness/run_combined.py <run dir>     # --create the scene
#   python docs/verification/harness/hover_combined.py <run dir> <out dir>
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="${1:-C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest-combined}"

rm -rf "$RUN/mods/lilys-melta" "$RUN/mods/melta-combined"
mkdir -p "$RUN/mods/lilys-melta" "$RUN/mods/melta-combined" "$RUN/write" "$RUN/out"

for item in info.json changelog.txt constants.lua control.lua data.lua data-updates.lua \
            prototypes graphics locale sound; do
  if [ -e "$REPO/$item" ]; then
    cp -r "$REPO/$item" "$RUN/mods/lilys-melta/"
  fi
done

cp "$REPO/docs/verification/harness/melta-combined/"* "$RUN/mods/melta-combined/"

printf '[path]\r\nwrite-data=%s/write\r\n[graphics]\r\nmax-texture-size=4096\r\n' "$RUN" > "$RUN/config.ini"

cat > "$RUN/mods/mod-list.json" <<'EOF'
{
  "mods": [
    {"name": "base", "enabled": true},
    {"name": "elevated-rails", "enabled": true},
    {"name": "quality", "enabled": true},
    {"name": "recycler", "enabled": true},
    {"name": "space-age", "enabled": true},
    {"name": "lilys-melta", "enabled": true},
    {"name": "melta-combined", "enabled": true}
  ]
}
EOF

echo "staged $RUN"
find "$RUN/mods" -maxdepth 1 -mindepth 1 -printf '%f\n'
grep -c '' "$RUN/mods/lilys-melta/control.lua"
