#!/usr/bin/env bash
# Rebuild the isolated Factorio run directory for the melta beam probe.
#   - a private write-data dir, so her saves/blueprints/log are never touched
#   - a COPY of the mod tree (not a link): the game reads files while other cards are
#     editing the repo, and a copy freezes the tree under test
#   - one probe mod that builds the scene and takes the screenshots
set -euo pipefail

SRC="H:/Factorio Mods/lilys-melta"
RUN="C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest-beam"
PROBE_SRC="C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest-beam-probe"

rm -rf "$RUN/mods/lilys-melta" "$RUN/mods/beam-probe"
mkdir -p "$RUN/mods/lilys-melta" "$RUN/write" "$RUN/out"

# explicit list: never copy .git, docs, zips or whatever editor temp file is lying
# around (other cards hold this same tree)
for item in info.json changelog.txt constants.lua control.lua data.lua data-updates.lua \
            prototypes graphics locale sound; do
  cp -r "$SRC/$item" "$RUN/mods/lilys-melta/"
done

cp -r "$PROBE_SRC" "$RUN/mods/beam-probe"

cat > "$RUN/config.ini" <<EOF
[path]
write-data=$RUN/write
[graphics]
max-texture-size=4096
EOF

cat > "$RUN/mods/mod-list.json" <<'EOF'
{
  "mods":
  [
    {"name": "base", "enabled": true},
    {"name": "lilys-melta", "enabled": true},
    {"name": "beam-probe", "enabled": true},
    {"name": "elevated-rails", "enabled": false},
    {"name": "quality", "enabled": false},
    {"name": "recycler", "enabled": false},
    {"name": "space-age", "enabled": false}
  ]
}
EOF

echo "run dir: $RUN"
find "$RUN/mods" -maxdepth 1 -mindepth 1 -printf '%f\n'
