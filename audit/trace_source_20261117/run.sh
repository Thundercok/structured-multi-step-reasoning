#!/bin/zsh
# Trace source (self vs human), 200 iterations, per docs/trace_source_prereg.md (commit 38a70de3).
# Re-running resumes: evaluate skips finished ids; training is skipped once adapters.safetensors exists.

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/trace_source_20261117"
TEST="data/gsm_plus_v1/test.jsonl"
ITERS=200
LOG="$RUN/run.log"
step() { echo ">>> $1 at $(date)" | tee -a "$LOG"; }

[[ "$(shasum -a 256 "$TEST" | cut -d' ' -f1)" == e7ba71253d0f23f92d004d28e03855faff1ec229cf9b0f8e2d77be55d9b7b107 ]] \
  || { echo "test.jsonl sha256 mismatch" | tee -a "$LOG"; exit 1; }

# 1. Self traces. Start at N=400; while K < ITERS, add 200 questions. keep() is never changed.
N=400
while true; do
  step "items $N"
  .venv/bin/python -m structured_llm.self_traces items $N "$RUN/items.jsonl" | tee -a "$LOG"
  step "base_prefill on $N"
  .venv/bin/python -u -m structured_llm.evaluate --data "$RUN/items.jsonl" --limit $N \
    --modes base_prefill --max-tokens 1024 --out "$RUN/gen" >> "$RUN/gen.log" 2>&1
  step "build"
  .venv/bin/python -m structured_llm.self_traces build "$RUN/gen/base_prefill.jsonl" "$RUN/data" | tee -a "$LOG"
  K=$(.venv/bin/python -c "import json; print(json.load(open('$RUN/data/manifest.json'))['kept'])")
  (( K >= ITERS )) && break
  (( N >= 4000 )) && { step "K=$K still below $ITERS at N=$N; stopping"; exit 1; }
  N=$(( N + 200 ))
done

# 2. Checks before training. Exits non-zero on a format mismatch.
step "checks"
.venv/bin/python "$RUN/check.py" "$RUN/data" | tee "$RUN/check.json"

# 3. Train. Plain hyperparameters, seed 0; only the data directory differs.
for src in self human; do
  dst="adapters/trace_${src}_${ITERS}_s0"
  if [[ ! -f "$dst/adapters.safetensors" ]]; then
    step "train $src"
    structured_llm/train.sh "$dst" $ITERS "$RUN/data/$src" > "$RUN/train_$src.log" 2>&1
  fi
done

# 4. Score on the 500 GSM-Plus items, then interventions.
for src in self human; do
  dst="adapters/trace_${src}_${ITERS}_s0"
  step "clean $src"
  .venv/bin/python -u -m structured_llm.evaluate --adapter "$dst" --data "$TEST" --limit 500 \
    --modes tuned --max-tokens 1024 --out "$RUN/eval_$src" >> "$RUN/eval_$src.log" 2>&1
  step "interventions $src"
  PYTHONPATH=. .venv/bin/python -u -c "
import sys; from pathlib import Path; sys.path.insert(0, 'scripts')
from run_scaleup_eval_300 import run_standard_interventions
run_standard_interventions(Path('$dst').resolve(), Path('$RUN/eval_$src'))
" >> "$RUN/interventions_$src.log" 2>&1
done

step "analysis"
.venv/bin/python "$RUN/analyze.py" > "$RUN/analyze.log" 2>&1
step "done"
