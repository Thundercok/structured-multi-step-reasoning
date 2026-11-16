#!/bin/zsh
# Plain at iterations 50, 200, 1000 on the 500 GSM-Plus items, per docs/sft_dose_response_prereg.md.
# Re-running resumes.

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/sft_dose_response_20261116"
TEST="data/gsm_plus_v1/test.jsonl"
SRC="adapters/gsm8k_enriched_2000_s0"
LOG="$RUN/run.log"
step() { echo ">>> $1 at $(date)" | tee -a "$LOG"; }

[[ "$(shasum -a 256 "$TEST" | cut -d' ' -f1)" == e7ba71253d0f23f92d004d28e03855faff1ec229cf9b0f8e2d77be55d9b7b107 ]] \
  || { echo "test.jsonl sha256 mismatch" | tee -a "$LOG"; exit 1; }

for it in 50 200 1000; do
  dst="adapters/gsm8k_enriched_ckpt${it}_s0"
  mkdir -p "$dst"
  cp "$SRC/$(printf %07d $it)_adapters.safetensors" "$dst/adapters.safetensors"
  cp "$SRC/adapter_config.json" "$dst/"
  step "clean $it"
  .venv/bin/python -u -m structured_llm.evaluate --adapter "$dst" --data "$TEST" --limit 500 \
    --modes tuned --max-tokens 1024 --out "$RUN/eval_$it" >> "$RUN/eval_$it.log" 2>&1
  step "interventions $it"
  PYTHONPATH=. .venv/bin/python -u -c "
import sys; from pathlib import Path; sys.path.insert(0, 'scripts')
from run_scaleup_eval_300 import run_standard_interventions
run_standard_interventions(Path('$dst').resolve(), Path('$RUN/eval_$it'))
" >> "$RUN/interventions_$it.log" 2>&1
done

step "analysis"
.venv/bin/python "$RUN/analyze.py" > "$RUN/analyze.log" 2>&1
step "done"
