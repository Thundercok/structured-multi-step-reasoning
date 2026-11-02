#!/bin/zsh
PY=/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/.venv/bin/python
export HF_HUB_OFFLINE=1
cd "$(dirname "$0")"
for spec in "mlx-community/Qwen3-8B-4bit 8b" "mlx-community/Qwen3.5-4B-MLX-4bit 4b"; do
  m=${spec% *}; tag=${spec#* }
  echo "=== $m"
  /usr/bin/time -l $PY -m mlx_lm lora --model "$m" --train --data data --fine-tune-type lora --num-layers 8 --batch-size 2 --iters 30 --learning-rate 1e-5 --max-seq-length 512 --grad-checkpoint --steps-per-report 10 --steps-per-eval 1000 --val-batches 1 --save-every 1000 --adapter-path "adapters_$tag" --seed 0 2>&1 | grep -v -E '^\s*$' | tail -40
  ls -la "adapters_$tag" 2>/dev/null
done
echo DONE
