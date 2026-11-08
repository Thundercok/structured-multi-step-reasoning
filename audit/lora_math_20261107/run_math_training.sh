#!/bin/zsh
# Training and Evaluation harness for MATH Level 3-5 checkable problems.
# Trains adapters/math_lora_1000_s0 on data/math_source/structured_math_v1 (725 train, 76 valid).
# Evaluates on the held-out 100 dev questions from data/math_source/structured_math_v1/dev.jsonl.
# Protected by battery/AC power guard. Run from repo root.

set -u
OUT=audit/lora_math_20261107
ADAPTER=adapters/math_lora_1000_s0
DATA=data/math_source/structured_math_v1
ITERS=1000
FLOOR=6
RESUME=8
MATCH="mlx_lm lora .*--adapter-path $ADAPTER"

mkdir -p $OUT

guard() {  # usage: guard <pid> <log>
  local paused=0 batt ac
  while kill -0 $1 2>/dev/null; do
    batt=$(pmset -g batt | grep -oE '[0-9]+%' | head -1 | tr -d %)
    pmset -g batt | grep -q "AC Power" && ac=1 || ac=0
    print -r -- "$(date +%H:%M:%S) batt=$batt ac=$ac paused=$paused load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage | awk '{print $6}')" >> $2
    if [[ -n $batt ]]; then
      if (( !paused && (batt <= FLOOR || !ac) )); then
        pkill -STOP -f "$MATCH" && paused=1 && print -r -- "$(date +%H:%M:%S) PAUSE batt=$batt ac=$ac" >> $2
      elif (( paused && batt >= RESUME && ac )); then
        pkill -CONT -f "$MATCH" && paused=0 && print -r -- "$(date +%H:%M:%S) RESUME batt=$batt ac=$ac" >> $2
      fi
    fi
    sleep 60
  done
}

echo "=== Starting MATH LoRA Training at $(date) ==="
if [[ -e $ADAPTER/adapters.safetensors ]]; then
  echo "Refusing to overwrite finished adapter: $ADAPTER"
else
  log=$OUT/train.log
  {
    echo "cmd: structured_llm/train.sh $ADAPTER $ITERS $DATA"
    echo "start: $(date)"
    echo "head: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "data: $(shasum -a 256 $DATA/train.jsonl $DATA/valid.jsonl 2>/dev/null | cut -c1-16,65- | tr '\n' ' ')"
    echo "mlx: $(.venv/bin/pip list 2>/dev/null | grep -E '^mlx' | tr -s ' ' | tr '\n' ' ')"
  } > $log
  structured_llm/train.sh $ADAPTER $ITERS $DATA >> $log 2>&1 &
  pid=$!
  guard $pid $OUT/train_load.txt &
  watcher=$!
  wait $pid
  code=$?
  kill $watcher 2>/dev/null
  { echo "exit: $code"; echo "end: $(date)"; } >> $log
  echo "=== Finished training at $(date) (exit: $code) ==="
fi

echo "=== Evaluating on 100 MATH Dev questions at $(date) ==="
export HF_HUB_OFFLINE=1
eval_dir=$OUT/eval
mkdir -p $eval_dir

.venv/bin/python -m structured_llm.evaluate \
  --data $DATA/dev.jsonl \
  --limit 100 \
  --adapter $ADAPTER \
  --modes tuned \
  --out $eval_dir >> $eval_dir/eval_log.txt 2>&1

echo "=== MATH Training & Evaluation Complete at $(date) ==="
