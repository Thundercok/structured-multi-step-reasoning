#!/bin/bash
set -e

DIR="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-0.5B-Instruct-4bit"
BLOB_DIR="$DIR/blobs"
SNAPSHOT_DIR=$(ls -d $DIR/snapshots/* | head -n 1)
HASH="ddffab9cbc7bf6dde941c6724841eeca8981fcfa81ca20ff8efff1396326d153"
INCOMPLETE="$BLOB_DIR/$HASH.incomplete"
TARGET="$BLOB_DIR/$HASH"

mkdir -p "$BLOB_DIR"

echo "Downloading Qwen2.5-0.5B-Instruct-4bit safetensors (278 MB)..."
curl -C - -L --retry 10 --retry-delay 2 \
  -o "$INCOMPLETE" \
  "https://huggingface.co/mlx-community/Qwen2.5-0.5B-Instruct-4bit/resolve/main/model.safetensors"

mv "$INCOMPLETE" "$TARGET"
ln -sf "../../blobs/$HASH" "$SNAPSHOT_DIR/model.safetensors"
echo "Download complete and linked to $SNAPSHOT_DIR/model.safetensors!"
