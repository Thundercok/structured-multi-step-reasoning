#!/bin/zsh
# Single pass over the sealed GSM8K test, per docs/sealed_test_gsm8k_prereg.md.
# Re-running resumes: every step skips questions it already finished.

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/gsm8k_sealed_test_20261111"
TEST="data/gsm8k_sealed_test_v1/test.jsonl"
CF="adapters/gsm8k_cf_enriched_2000_s0"
PLAIN="adapters/gsm8k_enriched_2000_s0"
LOG="$RUN/run.log"
step() { echo ">>> $1 at $(date)" | tee -a "$LOG"; }

step "prepare"
HF_HUB_OFFLINE=0 .venv/bin/python "$RUN/prepare.py" >> "$LOG" 2>&1

for pair in cf:$CF plain:$PLAIN; do
  step "clean ${pair%%:*}"
  .venv/bin/python -u -m structured_llm.evaluate --adapter "${pair#*:}" --data "$TEST" --limit 1319 \
    --modes tuned --max-tokens 1024 --out "$RUN/eval_${pair%%:*}" >> "$RUN/eval_${pair%%:*}.log" 2>&1
done

for pair in cf:$CF plain:$PLAIN; do
  step "interventions ${pair%%:*}"
  PYTHONPATH=. .venv/bin/python -u -c "
import sys; from pathlib import Path; sys.path.insert(0, 'scripts')
from run_scaleup_eval_300 import run_standard_interventions
run_standard_interventions(Path('${pair#*:}').resolve(), Path('$RUN/eval_${pair%%:*}'))
" >> "$RUN/interventions_${pair%%:*}.log" 2>&1
done

step "primary analysis"
.venv/bin/python "$RUN/analyze.py" "$RUN/eval_cf" "$RUN/eval_plain" --out "$RUN/results_primary.json" >> "$LOG" 2>&1

step "base_prefill"
.venv/bin/python -u -m structured_llm.evaluate --data "$TEST" --limit 1319 --modes base_prefill \
  --max-tokens 1024 --out "$RUN/eval_base" >> "$RUN/eval_base.log" 2>&1

step "full analysis"
.venv/bin/python "$RUN/analyze.py" "$RUN/eval_cf" "$RUN/eval_plain" "$RUN/eval_base" --out "$RUN/results.json" >> "$LOG" 2>&1
step "finished"
