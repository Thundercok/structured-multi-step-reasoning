#!/bin/zsh
# Clean one-step ablation: train and score both groups, then apply the rule in
# docs/ablation_math_multistep_spec.md section 5.

set -u
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/lora_math_multistep_clean_20261109"
DEV="data/math_source/structured_math_v1/dev.jsonl"
LOG="$RUN/run.log"

run_group() {
  local group=$1 adapter=$2 data=$3
  echo ">>> $group: training $adapter at $(date)" | tee -a "$LOG"
  structured_llm/train.sh "$adapter" 1000 "$data" 512 0 > "$RUN/train_$group.log" 2>&1 || {
    echo ">>> $group: training failed at $(date)" | tee -a "$LOG"
    return 1
  }
  echo ">>> $group: scoring at $(date)" | tee -a "$LOG"
  .venv/bin/python -u -m structured_llm.evaluate \
    --adapter "$adapter" --data "$DEV" --limit 100 --modes tuned --max-tokens 1024 \
    --out "$RUN/eval_$group" >> "$RUN/eval_$group.log" 2>&1 || {
    echo ">>> $group: scoring failed at $(date)" | tee -a "$LOG"
    return 1
  }
}

exit_code=0
run_group treatment adapters/math_term_multistep131_1000_s0 data/structured_math_term_multistep131_v1 || exit_code=1
run_group control adapters/math_term_random131_1000_s0 data/structured_math_term_random131_v1 || exit_code=1

if [[ $exit_code -eq 0 ]]; then
  PYTHONPATH=. .venv/bin/python "$RUN/compare.py" >> "$LOG" 2>&1 || exit_code=1
fi
echo ">>> finished with status $exit_code at $(date)" | tee -a "$LOG"
exit $exit_code
