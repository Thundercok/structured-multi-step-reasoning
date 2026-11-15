#!/bin/zsh
# H1 on the 819-item GSM-Plus holdout, per docs/gsm_plus_h1_holdout_prereg.md. Re-running resumes.

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/gsm_plus_h1_holdout_20261115"
TEST="data/gsm_plus_v1/holdout_819.jsonl"
CF="adapters/gsm8k_cf_enriched_2000_s0"
PLAIN="adapters/gsm8k_enriched_2000_s0"
LOG="$RUN/run.log"
step() { echo ">>> $1 at $(date)" | tee -a "$LOG"; }

step "prepare"
.venv/bin/python "$RUN/prepare.py" >> "$LOG" 2>&1

for pair in cf:$CF plain:$PLAIN; do
  step "clean ${pair%%:*}"
  .venv/bin/python -u -m structured_llm.evaluate --adapter "${pair#*:}" --data "$TEST" --limit 819 \
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

step "analysis"
.venv/bin/python "$RUN/analyze.py" > "$RUN/analyze.log" 2>&1
step "done"
