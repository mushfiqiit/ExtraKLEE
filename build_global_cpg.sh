#!/usr/bin/env bash
set -euo pipefail

TF_ROOT="/home/mushfiqur/Desktop/Github/tensorflow/tensorflow"
STAGE="/tmp/tf_cpg_stage"
OUT="/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/global.bin"
LOG="/tmp/joern_parse_global.log"

echo "[1/5] Preparing staging tree..."
rm -rf "$STAGE"
mkdir -p "$STAGE"

ln -s "$TF_ROOT/core" "$STAGE/core"
ln -s "$TF_ROOT/c" "$STAGE/c"
ln -s "$TF_ROOT/compiler" "$STAGE/compiler"
ln -s "$TF_ROOT/cc" "$STAGE/cc"
ln -s "$TF_ROOT/dtensor" "$STAGE/dtensor"

echo "[2/5] Removing previous output..."
rm -f "$OUT"

echo "[3/5] Resource tuning..."
ulimit -n 65535 || true   # helps avoid "too many open files" on huge trees

echo "[4/5] Running joern-parse..."
# Tune Xmx based on your RAM. Examples:
# 16G machine -> Xmx10g
# 32G machine -> Xmx24g
# 64G machine -> Xmx48g
JAVA_OPTS="-Xms4g -Xmx24g -XX:+UseG1GC -XX:MaxGCPauseMillis=200" \
  /usr/bin/time -v joern-parse "$STAGE" --output "$OUT" 2>&1 | tee "$LOG"

echo "[5/5] Done."
echo "global.bin: $OUT"
echo "log:        $LOG"