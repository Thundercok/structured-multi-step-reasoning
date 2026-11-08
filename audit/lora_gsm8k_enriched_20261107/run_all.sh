#!/bin/zsh
# Overnight full training and evaluation of semantically enriched GSM8K adapters.
# 1. Trains adapters/gsm8k_enriched_2000_s0 on data/structured_gsm8k_enriched_v1
# 2. Trains adapters/gsm8k_cf_enriched_2000_s0 on data/structured_gsm8k_cf_enriched_v1
# 3. Evaluates both on 100 dev items (tuned mode, no prefill intervention)
# 4. Runs intervention analysis and comparison table
# Protected by automatic battery/AC pause/resume guard. Run from repo root.

set -u
OUT=audit/lora_gsm8k_enriched_20261107
ITERS=2000
FLOOR=6
RESUME=8
MATCH_TRAIN="mlx_lm lora .*--adapter-path adapters/gsm8k"
MATCH_EVAL="structured_llm.evaluate .*--out $OUT"

mkdir -p $OUT

guard_train() {  # usage: guard_train <pid> <log>
  local paused=0 batt ac
  while kill -0 $1 2>/dev/null; do
    batt=$(pmset -g batt | grep -oE '[0-9]+%' | head -1 | tr -d %)
    pmset -g batt | grep -q "AC Power" && ac=1 || ac=0
    print -r -- "$(date +%H:%M:%S) batt=$batt ac=$ac paused=$paused load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage | awk '{print $6}') $(pmset -g therm 2>/dev/null | grep -E 'CPU_Speed_Limit' | tr -d ' \t')" >> $2
    if [[ -n $batt ]]; then
      if (( !paused && (batt <= FLOOR || !ac) )); then
        pkill -STOP -f "$MATCH_TRAIN" && paused=1 && print -r -- "$(date +%H:%M:%S) PAUSE batt=$batt ac=$ac" >> $2
      elif (( paused && batt >= RESUME && ac )); then
        pkill -CONT -f "$MATCH_TRAIN" && paused=0 && print -r -- "$(date +%H:%M:%S) RESUME batt=$batt ac=$ac" >> $2
      fi
    fi
    sleep 60
  done
}

guard_eval() {  # usage: guard_eval <pid> <log>
  local paused=0 batt ac
  while kill -0 $1 2>/dev/null; do
    batt=$(pmset -g batt | grep -oE '[0-9]+%' | head -1 | tr -d %)
    pmset -g batt | grep -q "AC Power" && ac=1 || ac=0
    print -r -- "$(date +%H:%M:%S) batt=$batt ac=$ac paused=$paused load=$(sysctl -n vm.loadavg)" >> $2
    if [[ -n $batt ]]; then
      if (( !paused && (batt <= FLOOR || !ac) )); then
        pkill -STOP -f "$MATCH_EVAL" && paused=1 && print -r -- "$(date +%H:%M:%S) PAUSE batt=$batt ac=$ac" >> $2
      elif (( paused && batt >= RESUME && ac )); then
        pkill -CONT -f "$MATCH_EVAL" && paused=0 && print -r -- "$(date +%H:%M:%S) RESUME batt=$batt ac=$ac" >> $2
      fi
    fi
    sleep 60
  done
}

train() {  # usage: train <name> <data-dir>
  local adapter=adapters/$1 log=$OUT/train_$1.log
  if [[ -e $adapter/adapters.safetensors ]]; then
    echo "Refusing to overwrite finished adapter: $adapter"
    return 0
  fi
  echo "=== Starting training for $1 at $(date) ==="
  {
    echo "cmd: structured_llm/train.sh $adapter $ITERS $2"
    echo "start: $(date)"
    echo "head: $(git rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "data: $(shasum -a 256 $2/train.jsonl $2/valid.jsonl 2>/dev/null | cut -c1-16,65- | tr '\n' ' ')"
    echo "mlx: $(.venv/bin/pip list 2>/dev/null | grep -E '^mlx' | tr -s ' ' | tr '\n' ' ')"
  } > $log
  nohup structured_llm/train.sh $adapter $ITERS $2 >> $log 2>&1 &
  local pid=$!
  guard_train $pid $OUT/train_${1}_load.txt &
  local watcher=$!
  wait $pid
  local code=$?
  kill $watcher 2>/dev/null
  { echo "exit: $code"; echo "end: $(date)"; } >> $log
  echo "=== Finished training for $1 at $(date) (exit: $code) ==="
  [[ $code == 0 && -e $adapter/adapters.safetensors ]]
}

evaluate() {  # usage: evaluate <subdir> [--adapter dir] --modes ...
  local dir=$OUT/$1; shift
  mkdir -p $dir
  echo "=== Evaluating $dir at $(date) ==="
  echo "cmd: .venv/bin/python -m structured_llm.evaluate --limit 100 --out $dir $*" >> $dir/eval_log.txt
  echo "start: $(date)" >> $dir/eval_log.txt
  nohup .venv/bin/python -m structured_llm.evaluate --limit 100 --out $dir "$@" >> $dir/eval_log.txt 2>&1 &
  local pid=$!
  guard_eval $pid $dir/load.txt &
  local watcher=$!
  wait $pid
  local code=$?
  kill $watcher 2>/dev/null
  echo "exit: $code end: $(date)" >> $dir/eval_log.txt
  return $code
}

intervene() {  # usage: intervene <subdir> args...
  local dir=$OUT/$1; shift
  echo "=== Running interventions for $dir at $(date) ==="
  echo "cmd: .venv/bin/python -m structured_llm.intervene --run $dir $*" >> $dir/intervene_log.txt
  echo "start: $(date)" >> $dir/intervene_log.txt
  nohup .venv/bin/python -m structured_llm.intervene --run $dir "$@" >> $dir/intervene_log.txt 2>&1 &
  local pid=$!
  guard_eval $pid $dir/intervene_load.txt &
  local watcher=$!
  wait $pid
  local code=$?
  kill $watcher 2>/dev/null
  echo "exit: $code end: $(date)" >> $dir/intervene_log.txt
  return $code
}

# 1. Quick probe (40 iters) to verify Metal allocation & loss drop
if [[ ! -e adapters/gsm8k_enriched_probe/adapters.safetensors ]]; then
  echo "--- Running 40-step probe check ---"
  structured_llm/train.sh adapters/gsm8k_enriched_probe 40 data/structured_gsm8k_enriched_v1 > $OUT/probe.log 2>&1
  echo "--- Probe check finished ---"
fi

# 2. Train enriched plain adapter (7,061 items, 2,000 steps)
train gsm8k_enriched_2000_s0 data/structured_gsm8k_enriched_v1 || { echo "gsm8k_enriched_2000_s0 failed"; exit 1; }

# 3. Train enriched counterfactual adapter (10,180 items, 2,000 steps)
train gsm8k_cf_enriched_2000_s0 data/structured_gsm8k_cf_enriched_v1 || { echo "gsm8k_cf_enriched_2000_s0 failed"; exit 2; }

# 4. Evaluate both adapters on 100 dev items (clean tuned mode, no prefill prompt)
export HF_HUB_OFFLINE=1
evaluate eval_plain --adapter adapters/gsm8k_enriched_2000_s0 --modes tuned || echo "eval_plain finished with error"
evaluate eval_cf --adapter adapters/gsm8k_cf_enriched_2000_s0 --modes tuned || echo "eval_cf finished with error"

# 5. Run interventions
if [[ ! -e $OUT/eval_plain/interventions_summary.json ]]; then
  intervene eval_plain --modes tuned --adapter adapters/gsm8k_enriched_2000_s0 || echo "intervene plain finished with error"
fi
intervene eval_cf --modes tuned --adapter adapters/gsm8k_cf_enriched_2000_s0 || echo "intervene cf finished with error"

# 6. Run comparison matrix & report generator
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/test_19_failing.py || echo "test_19_failing.py finished with error"
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare.py || echo "compare.py finished with error"
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/report_generator.py || echo "report_generator.py finished with error"
osascript -e 'display notification "All GSM8K enriched jobs and reports completed!" with title "GSM8K LoRA Suite" sound name "Glass"' 2>/dev/null || true

echo "=== ALL OVERNIGHT JOBS COMPLETED at $(date) ==="
