#!/bin/zsh
# Phased, crash-safe runner for docs/trace_dose_prereg.md.
# Safe to stop with Ctrl-C anytime (e.g. before playing LoL or closing laptop lid):
#   - `eval` and `interventions` flush every question and resume automatically.
#   - `train` skips any adapter that already has adapters.safetensors (~30 min per adapter).
#
# Subcommands:
#   status                 Show exact progress across all 10 (seed, ratio) cells
#   prep                   Build nested mix25/50/75 datasets & run pre-training checks (<10s)
#   train <seed> <ratio>   Train one adapter (~30 min), ratio in {25, 50, 75}, seed in {0, 1}
#   train-seed <seed>      Train all 3 new adapters for one seed (~1.5h)
#   eval <seed> <ratio>    Clean eval (500q, ~3.2h) + interventions (~1h) for one cell (resumable)
#   eval-seed <seed>       Run eval + interventions for all 5 ratios of one seed (resumable)
#   analyze                Run preregistered GLMM analysis once all 10 cells are complete

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/trace_dose_20261120"
SRC="audit/trace_source_20261117/data"
MIX="$RUN/data"
TEST="data/gsm_plus_v1/holdout_819.jsonl"
LIMIT=500
ITERS=200
LOG="$RUN/run.log"

EXPECTED_TEST_SHA="d079e99a5b9cef8d887f28ac39ac20b0a1b14cdee5b003a451d67087651f6e7a"
EXPECTED_SELF_SHA="fc3008919661319244a09d90acd352b6be95a5a586f6b6b1777c28239c6edf03"
EXPECTED_HUMAN_SHA="3723d40bcec4491bf76cf1621812232dd84a1653c7ec0bf309815538120a5a50"

sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
step() { echo ">>> $1 at $(date)" | tee -a "$LOG"; }

verify_inputs() {
  [[ "$(sha "$TEST")" == "$EXPECTED_TEST_SHA" ]] || { echo "ERROR: holdout_819.jsonl sha256 mismatch"; exit 1; }
  [[ "$(sha "$SRC/self/train.jsonl")" == "$EXPECTED_SELF_SHA" ]] || { echo "ERROR: self train.jsonl sha256 mismatch"; exit 1; }
  [[ "$(sha "$SRC/human/train.jsonl")" == "$EXPECTED_HUMAN_SHA" ]] || { echo "ERROR: human train.jsonl sha256 mismatch"; exit 1; }
}

adapter_for() {
  local seed=$1 ratio=$2
  case "$ratio" in
    0)   echo "adapters/trace_self_${ITERS}_s${seed}" ;;
    100) echo "adapters/trace_human_${ITERS}_s${seed}" ;;
    25|50|75) echo "adapters/trace_mix${ratio}_${ITERS}_s${seed}" ;;
    *) echo "ERROR: invalid ratio $ratio (use 0, 25, 50, 75, 100)" >&2; exit 1 ;;
  esac
}

cmd_prep() {
  verify_inputs
  step "prep nested mixes (seed 20261120)"
  .venv/bin/python -m structured_llm.trace_mix "$SRC" "$MIX" --seed 20261120 | tee -a "$LOG"
  step "check all 5 datasets"
  .venv/bin/python "$RUN/check.py" "$SRC" "$MIX" > "$RUN/check.json"
  cat "$RUN/check.json"
}

cmd_train_one() {
  local seed=$1 ratio=$2
  verify_inputs
  if [[ "$ratio" == "0" || "$ratio" == "100" ]]; then
    echo "ratio=$ratio already uses existing adapter $(adapter_for "$seed" "$ratio")"
    return 0
  fi
  [[ -f "$MIX/mix${ratio}/train.jsonl" ]] || cmd_prep
  local dst=$(adapter_for "$seed" "$ratio")
  if [[ -f "$dst/adapters.safetensors" ]]; then
    echo "skip train s${seed}_r${ratio}: $dst/adapters.safetensors already exists"
    return 0
  fi
  step "train s${seed}_r${ratio} -> $dst"
  structured_llm/train.sh "$dst" "$ITERS" "$MIX/mix${ratio}" 512 "$seed" > "$RUN/train_s${seed}_r${ratio}.log" 2>&1
  step "trained s${seed}_r${ratio}"
}

cmd_eval_one() {
  local seed=$1 ratio=$2
  verify_inputs
  local dst=$(adapter_for "$seed" "$ratio")
  [[ -f "$dst/adapters.safetensors" ]] || { echo "ERROR: missing adapter $dst (run train first)"; exit 1; }
  local out="$RUN/eval_s${seed}_r${ratio}"
  step "eval clean s${seed}_r${ratio} (limit $LIMIT)"
  .venv/bin/python -u -m structured_llm.evaluate \
    --adapter "$dst" --data "$TEST" --limit "$LIMIT" \
    --modes tuned --max-tokens 1024 --out "$out" >> "$RUN/eval_s${seed}_r${ratio}.log" 2>&1
  step "interventions s${seed}_r${ratio}"
  PYTHONPATH=. .venv/bin/python -u -c "
import sys; from pathlib import Path; sys.path.insert(0, 'scripts')
from run_scaleup_eval_300 import run_standard_interventions
run_standard_interventions(Path('$dst').resolve(), Path('$out'))
" >> "$RUN/interventions_s${seed}_r${ratio}.log" 2>&1
  step "done s${seed}_r${ratio}"
}

cmd_status() {
  .venv/bin/python -c "
import json
from pathlib import Path
from structured_llm.counterfactual import plan_intervention

run = Path('$RUN')
print(f'{\"Cell\":<10} {\"Adapter\":<9} {\"Eval\":<10} {\"Intervene\":<12}')
print('-' * 45)
for s in (0, 1):
    for r in (0, 25, 50, 75, 100):
        name = 'trace_self' if r == 0 else ('trace_human' if r == 100 else f'trace_mix{r}')
        ad = Path(f'adapters/{name}_200_s{s}/adapters.safetensors').exists()
        d = run / f'eval_s{s}_r{r}'
        ev_file = d / 'tuned.jsonl'
        in_file = d / 'tuned_interventions.jsonl'
        ev_rows = [json.loads(l) for l in ev_file.read_text().splitlines() if l.strip()] if ev_file.exists() else []
        in_rows = [json.loads(l) for l in in_file.read_text().splitlines() if l.strip()] if in_file.exists() else []
        if len(ev_rows) == 500:
            planned = sum(plan_intervention(x['output'], x['question'], x['id'])[0] is not None for x in ev_rows)
            in_str = f'{len(in_rows)}/{planned}'
        else:
            in_str = f'{len(in_rows)}/?'
        print(f's{s}_r{r:<6} {\"OK\" if ad else \"MISSING\":<9} {len(ev_rows)}/500     {in_str:<12}')
"
}

cmd_analyze() {
  step "analyze"
  .venv/bin/python "$RUN/analyze.py" "$RUN" > "$RUN/results.json" 2> "$RUN/analyze.log"
  step "analysis saved to $RUN/results.json"
  cat "$RUN/results.json"
}

case "${1:-}" in
  status)     cmd_status ;;
  prep)       cmd_prep ;;
  train)      cmd_train_one "${2:?seed}" "${3:?ratio}" ;;
  train-seed)
    seed="${2:?seed}"
    for r in 25 50 75; do cmd_train_one "$seed" "$r"; done
    ;;
  eval)       cmd_eval_one "${2:?seed}" "${3:?ratio}" ;;
  eval-seed)
    seed="${2:?seed}"
    for r in 0 25 50 75 100; do cmd_eval_one "$seed" "$r"; done
    ;;
  analyze)    cmd_analyze ;;
  *)
    sed -n '2,15p' "$0"
    exit 1
    ;;
esac
