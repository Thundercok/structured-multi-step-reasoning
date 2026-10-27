#!/bin/zsh
# Diagnostic CLI only, not RAT Mini. Dependencies are prepared in an isolated
# directory by the caller; never installs into the application environment.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
: "${RAT_MINI_SPIKE_DEPS:?Set RAT_MINI_SPIKE_DEPS to the trusted apsw/sqlite-vec dependency directory}"
BUILD_TMP="$(mktemp -d /private/tmp/rat-mini-preflight.XXXXXX)"
trap 'rm -rf "$BUILD_TMP"' EXIT
export CLANG_MODULE_CACHE_PATH="$BUILD_TMP/clang-cache"
export SWIFT_MODULECACHE_PATH="$BUILD_TMP/swift-cache"
export PYINSTALLER_CONFIG_DIR="$BUILD_TMP/pyinstaller-cache"
export PYTHONPATH="$RAT_MINI_SPIKE_DEPS${PYTHONPATH:+:$PYTHONPATH}"
cd "$ROOT"
swiftc -target arm64-apple-macos14.0 tools/apple_translation_probe.swift -o "$BUILD_TMP/apple_translation_probe"
"$PYTHON_BIN" -m PyInstaller --noconfirm --clean --onedir --name rat-mini-preflight \
  --distpath "$ROOT/dist" --workpath "$BUILD_TMP/build" --specpath "$BUILD_TMP/spec" \
  --hidden-import apsw --hidden-import sqlite_vec --collect-binaries sqlite_vec \
  --copy-metadata sqlite-vec --copy-metadata apsw \
  --add-binary "$BUILD_TMP/apple_translation_probe:." scripts/check_rat_mini.py
ditto -c -k --keepParent "$ROOT/dist/rat-mini-preflight" "$ROOT/dist/RAT-Mini-Preflight.zip"
echo "Diagnostic only: $ROOT/dist/RAT-Mini-Preflight.zip"
