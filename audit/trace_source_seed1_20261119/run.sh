#!/bin/zsh
# H3 replication at seed 1, per PREREG.md in this folder. Same data and settings as trace_source_20261117.
# Re-running resumes: evaluate skips finished ids; training is skipped once adapters.safetensors exists.

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/trace_source_seed1_20261119"
SRC="audit/trace_source_20261117/data"
TEST="data/gsm_plus_v1/test.jsonl"
ITERS=200
SEED=1
LOG="$RUN/run.log"
step() { echo ">>> $1 at $(date)" | tee -a "$LOG"; }
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }

[[ "$(sha "$TEST")" == e7ba71253d0f23f92d004d28e03855faff1ec229cf9b0f8e2d77be55d9b7b107 ]] \
  || { step "test.jsonl sha256 mismatch"; exit 1; }
[[ "$(sha "$SRC/self/train.jsonl")" == fc3008919661319244a09d90acd352b6be95a5a586f6b6b1777c28239c6edf03 ]] \
  || { step "self train sha256 mismatch"; exit 1; }
[[ "$(sha "$SRC/human/train.jsonl")" == 3723d40bcec4491bf76cf1621812232dd84a1653c7ec0bf309815538120a5a50 ]] \
  || { step "human train sha256 mismatch"; exit 1; }

for src in self human; do
  dst="adapters/trace_${src}_${ITERS}_s${SEED}"
  if [[ ! -f "$dst/adapters.safetensors" ]]; then
    step "train $src"
    structured_llm/train.sh "$dst" $ITERS "$SRC/$src" 512 $SEED > "$RUN/train_$src.log" 2>&1
  fi
done

for src in self human; do
  dst="adapters/trace_${src}_${ITERS}_s${SEED}"
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
.venv/bin/python audit/trace_source_20261117/analyze.py "$RUN" > "$RUN/results.json" 2> "$RUN/analyze.log"
step "done"
