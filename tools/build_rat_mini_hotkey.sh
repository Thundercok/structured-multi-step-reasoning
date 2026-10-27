#!/bin/zsh
# Developer build only. Distributed Mini apps already include this binary.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT="${1:-$ROOT/rat/bin/rat-hotkey}"
mkdir -p "$(dirname "$OUTPUT")"
xcrun clang -arch arm64 -mmacosx-version-min=14.0 -framework Carbon \
  -Wno-deprecated-declarations "$ROOT/tools/rat_hotkey.c" -o "$OUTPUT"
