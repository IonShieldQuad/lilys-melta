#!/usr/bin/env bash
# Stage and run the pipe-connection probe for the melta turret.
#
#   ./run_connprobe.sh <reach>      # reach = the value written into C.pipe_reach
#
# Copies the mod into a scratch run dir, optionally rewrites C.pipe_reach in that
# copy only (the repo is never touched), --create's a save, --benchmark's 240 ticks
# and greps the "[conn]" log lines. Private write-data dir: her saves, mod-list and
# factorio-current.log are untouched.
set -euo pipefail

REACH="${1:-keep}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="${CONNPROBE_RUN:-C:/Users/Lily/AppData/Local/hermes/cache/scratch/ftest-connprobe-$REACH}"
FACTORIO="${FACTORIO:-E:/SteamLibrary/steamapps/common/Factorio/bin/x64/Factorio.exe}"

rm -rf "$RUN"
mkdir -p "$RUN/mods/lilys-melta" "$RUN/moddir/lilys-melta" "$RUN/moddir/melta-connprobe" \
         "$RUN/write" "$RUN/out"

for item in info.json changelog.txt constants.lua control.lua data.lua data-updates.lua \
            prototypes graphics locale sound; do
  if [ -e "$REPO/$item" ]; then
    cp -r "$REPO/$item" "$RUN/moddir/lilys-melta/"
  fi
done
cp "$REPO/docs/verification/harness/melta-connprobe/"* "$RUN/moddir/melta-connprobe/"

if [ "$REACH" != "keep" ]; then
  python - "$RUN/moddir/lilys-melta/constants.lua" "$REACH" <<'PY'
import io, re, sys
path, reach = sys.argv[1], sys.argv[2]
raw = open(path, "rb").read()
text = raw.decode("utf-8")
text, n = re.subn(r"(C\.pipe_reach\s*=\s*)-?[0-9.]+", r"\g<1>" + reach, text, count=1)
assert n == 1, "C.pipe_reach not rewritten"
open(path, "wb").write(text.encode("utf-8"))
print("patched C.pipe_reach ->", reach)
PY
fi

# a fact: the fluid the turret burns
grep -m1 'C.pipe_reach' "$RUN/moddir/lilys-melta/constants.lua" | sed 's/^/  /'

printf '[path]\r\nwrite-data=%s/write\r\n' "$RUN" > "$RUN/config.ini"

cat > "$RUN/moddir/mod-list.json" <<'EOF'
{
  "mods": [
    {"name": "base", "enabled": true},
    {"name": "lilys-melta", "enabled": true},
    {"name": "melta-connprobe", "enabled": true}
  ]
}
EOF

"$FACTORIO" --config "$RUN/config.ini" --mod-directory "$RUN/moddir" \
            --create "$RUN/save.zip" > "$RUN/create.log" 2>&1 || true
grep -c "Loading mod lilys-melta" "$RUN/create.log" | sed 's/^/  mod loaded lines: /'

"$FACTORIO" --config "$RUN/config.ini" --mod-directory "$RUN/moddir" \
            --benchmark "$RUN/save.zip" --benchmark-ticks 240 \
            > "$RUN/bench.log" 2>&1 || true

echo "== [conn] log (create: scene + prototype) =="
grep -h '\[conn\]' "$RUN/create.log" || echo "  (none)"
echo "== [conn] log (benchmark: flow over time) =="
grep -h '\[conn\]' "$RUN/write/factorio-current.log" || echo "  (none)"
echo "== errors =="
grep -iE "^Error|Failed to load|stack traceback" "$RUN/write/factorio-current.log" | head -10 || true
echo "run dir: $RUN"
