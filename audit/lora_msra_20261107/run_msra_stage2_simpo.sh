#!/bin/zsh
set -u
cd "$(dirname "$0")/../.."

echo "=== MSRA Stage 2 Skipped (Scoped as Future Work) at $(date) ==="
PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py || echo "compare_math.py finished with status $?"

if [[ ! -e "audit/lora_gsm8k_enriched_20261107/eval_cf/tuned.jsonl" ]]; then
  echo "=== Running Core-Scope GSM8K Counterfactual Enriched Sweep at $(date) ==="
  ./audit/lora_gsm8k_enriched_20261107/run_all.sh || echo "Deferred GSM8K run_all finished with status $?"
fi
