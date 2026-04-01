#!/usr/bin/env bash
set -euo pipefail

SRC="/home/mushfiqur/Desktop/Github/tensorflow/tensorflow"
STAGE="/tmp/tf_c_cpp_headers"
OUT="/home/mushfiqur/Desktop/Github/ExtraKLEE/joern-out/global.bin"

rm -rf "$STAGE"
mkdir -p "$STAGE"

# Include C/C++ sources + headers so class declarations in .h/.hpp are parsed.
rsync -a --prune-empty-dirs \
  --include='*/' \
  --include='*.c' \
  --include='*.cc' \
  --include='*.cpp' \
  --include='*.h' \
  --include='*.hpp' \
  --exclude='*' \
  "$SRC"/ "$STAGE"/

# Optional safety for large trees.
ulimit -n 65535 || true

# Keep heap explicit to reduce OOM risk on large projects.
JAVA_OPTS="-Xms4g -Xmx24g -XX:+UseG1GC" \
  joern-parse "$STAGE" --language C --output "$OUT"