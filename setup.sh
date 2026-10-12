#!/usr/bin/env bash
# Root 1-Click launcher wrapper for rat setup
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/scripts/setup.sh" "$@"
