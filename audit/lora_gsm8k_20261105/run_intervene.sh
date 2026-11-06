#!/bin/zsh
# Intervene on the outputs of the adapter that passed gate 0 (tuned_cf) and on two base modes.
# Same battery guard as run_training.sh. Resumable: intervene.py skips traces already saved.
set -u
OUT=audit/lora_gsm8k_20261105
FLOOR=6
RESUME=8
MATCH="structured_llm.intervene .*--run $OUT"

guard() {  # usage: guard <pid> <log>
  local paused=0 batt ac
  while kill -0 $1 2>/dev/null; do
    batt=$(pmset -g batt | grep -oE '[0-9]+%' | head -1 | tr -d %)
    pmset -g batt | grep -q "AC Power" && ac=1 || ac=0
    print -r -- "$(date +%H:%M:%S) batt=$batt ac=$ac paused=$paused load=$(sysctl -n vm.loadavg)" >> $2
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

intervene() {  # usage: intervene <subdir> args...
  local dir=$OUT/$1; shift
  echo "cmd: .venv/bin/python -m structured_llm.intervene --run $dir $*" >> $dir/intervene_log.txt
  echo "start: $(date)" >> $dir/intervene_log.txt
  .venv/bin/python -m structured_llm.intervene --run $dir "$@" >> $dir/intervene_log.txt 2>&1 &
  local pid=$!
  guard $pid $dir/intervene_load.txt &
  local watcher=$!
  wait $pid
  local code=$?
  kill $watcher 2>/dev/null
  echo "exit: $code end: $(date)" >> $dir/intervene_log.txt
  return $code
}

export HF_HUB_OFFLINE=1
intervene eval_cf --modes tuned --adapter adapters/gsm8k_cf_2000_s0 || exit 1
intervene eval_base --modes base_prefill base_showcalc || exit 2
echo "all done: $(date)"
