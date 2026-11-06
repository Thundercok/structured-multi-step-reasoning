#!/bin/zsh
# Train the plain and counterfactual adapters one after the other, beside the VRPTW sweep.
# A guard pauses the trainer with SIGSTOP at 6% battery or off AC, and resumes it at 8% on AC.
# Refuses to overwrite a finished adapter. Run from the repo root.
set -u
OUT=audit/lora_gsm8k_20261105
ITERS=2000
FLOOR=6
RESUME=8
MATCH="mlx_lm lora .*--adapter-path adapters/gsm8k"

guard() {  # usage: guard <trainer-shell-pid> <log>
  local paused=0 batt ac
  while kill -0 $1 2>/dev/null; do
    batt=$(pmset -g batt | grep -oE '[0-9]+%' | head -1 | tr -d %)
    pmset -g batt | grep -q "AC Power" && ac=1 || ac=0
    print -r -- "$(date +%H:%M:%S) batt=$batt ac=$ac paused=$paused load=$(sysctl -n vm.loadavg) swap=$(sysctl -n vm.swapusage | awk '{print $6}') $(pmset -g therm | grep -E 'CPU_Speed_Limit' | tr -d ' \t')" >> $2
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

train() {  # usage: train <name> <data-dir>
  local adapter=adapters/$1 log=$OUT/train_$1.log
  if [[ -e $adapter/adapters.safetensors ]]; then
    echo "refusing to overwrite $adapter"; return 1
  fi
  {
    echo "cmd: structured_llm/train.sh $adapter $ITERS $2"
    echo "start: $(date)"
    echo "head: $(git rev-parse HEAD)"
    echo "data: $(shasum -a 256 $2/train.jsonl $2/valid.jsonl | cut -c1-16,65- | tr '\n' ' ')"
    echo "mlx: $(.venv/bin/pip list 2>/dev/null | grep -E '^mlx' | tr -s ' ' | tr '\n' ' ')"
  } > $log
  structured_llm/train.sh $adapter $ITERS $2 >> $log 2>&1 &
  local pid=$!
  guard $pid $OUT/train_$1_load.txt &
  local watcher=$!
  wait $pid
  local code=$?
  kill $watcher 2>/dev/null
  { echo "exit: $code"; echo "end: $(date)"; } >> $log
  [[ $code == 0 && -e $adapter/adapters.safetensors ]]
}

train gsm8k_plain_2000_s0 data/structured_gsm8k_v1 || { echo "plain failed"; exit 1; }
train gsm8k_cf_2000_s0 data/structured_gsm8k_cf_v1 || { echo "cf failed"; exit 2; }
echo "both done: $(date)"
