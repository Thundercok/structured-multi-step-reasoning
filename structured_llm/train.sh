#!/bin/zsh
# LoRA fine-tune of Qwen3-8B on structured traces. Usage: train.sh <adapter-dir> [iters] [data-dir]
# The Metal limits are required on a 16 GB M1; see audit/lora_smoke_20261102/.
set -eu
cd "$(dirname "$0")/.."
ADAPTER=${1:?adapter directory}
ITERS=${2:-200}
DATA=${3:-data/structured_gsm8k_v1}
MAX_SEQ=${4:-512}
SEED=${5:-0}
MODEL="${HF_HOME:-$HOME/.cache/huggingface}/hub/models--mlx-community--Qwen3-8B-4bit/snapshots/545dc4251c05440727734bcd94334791f6ab0192"
export HF_HUB_OFFLINE=1 MLX_MAX_OPS_PER_BUFFER=10 MLX_MAX_MB_PER_BUFFER=512
/usr/bin/time -l .venv/bin/python -m mlx_lm lora --model "$MODEL" --train \
  --data "$DATA" --fine-tune-type lora --num-layers 8 \
  --batch-size 1 --iters "$ITERS" --learning-rate 5e-5 --max-seq-length "$MAX_SEQ" \
  --grad-checkpoint --steps-per-report 10 --steps-per-eval 50 --val-batches 10 \
  --save-every 50 --adapter-path "$ADAPTER" --seed "$SEED"
