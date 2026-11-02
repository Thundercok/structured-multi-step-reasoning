#!/bin/zsh
# Developer build only. Distributed Mini apps already include this binary.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-$ROOT/rat/bin/rat-hotkey}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
BUILD_ID="$(cd "$ROOT" && "$PYTHON_BIN" -c 'from rat.engine.mini_version import BUILD; print(BUILD)')"
mkdir -p "$(dirname "$OUTPUT")"
xcrun clang -arch arm64 -mmacosx-version-min=14.0 -framework Carbon \
  -DRAT_BUILD_ID="\"$BUILD_ID\"" -Wno-deprecated-declarations "$ROOT/tools/rat_hotkey.c" -o "$OUTPUT"
