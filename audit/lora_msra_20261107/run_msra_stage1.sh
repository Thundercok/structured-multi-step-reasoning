#!/bin/zsh
set -u
cd "$(dirname "$0")/../.."

if [[ -e "audit/lora_math_20261107/eval/tuned.jsonl" && ! -e "audit/lora_math_20261107/eval/interventions_summary.json" ]]; then
  echo "=== Running MATH Level 3-5 RQ2 Interventions at $(date) ==="
  export HF_HUB_OFFLINE=1
  .venv/bin/python -m structured_llm.intervene \
    --run audit/lora_math_20261107/eval \
    --modes tuned \
    --adapter adapters/math_lora_1000_s0 >> audit/lora_math_20261107/eval/intervene_log.txt 2>&1 || echo "MATH intervene finished with status $?"
fi
PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py || echo "compare_math.py finished with status $?"
echo "=== MSRA Stage 1 Skipped (Scoped as Future Work) at $(date) ==="
