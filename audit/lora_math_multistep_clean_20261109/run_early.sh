#!/bin/zsh
# Secondary analysis in docs/ablation_math_multistep_spec.md section 6: score
# the iteration-150 checkpoint of both groups on the same 100 questions.

set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

RUN="audit/lora_math_multistep_clean_20261109"
DEV="data/math_source/structured_math_v1/dev.jsonl"

if pgrep -f "$RUN/run.sh" > /dev/null; then
  echo "run.sh is still running; start this after it ends" >&2
  exit 1
fi

for pair in treatment:math_term_multistep131 control:math_term_random131; do
  group=${pair%%:*}
  name=${pair##*:}
  src="adapters/${name}_1000_s0"
  dst="adapters/${name}_150_s0"
  mkdir -p "$dst"
  cp "$src/0000150_adapters.safetensors" "$dst/adapters.safetensors"
  cp "$src/adapter_config.json" "$dst/"
  .venv/bin/python -u -m structured_llm.evaluate \
    --adapter "$dst" --data "$DEV" --limit 100 --modes tuned --max-tokens 1024 \
    --out "$RUN/eval_${group}_150" > "$RUN/eval_${group}_150.log" 2>&1
done

PYTHONPATH=. .venv/bin/python "$RUN/compare.py" \
  "$RUN/eval_treatment_150/tuned.jsonl" "$RUN/eval_control_150/tuned.jsonl" \
  > "$RUN/comparison_150.json"
