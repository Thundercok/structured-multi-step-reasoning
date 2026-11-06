#!/bin/zsh
# Checkpoint noise check: score checkpoints 1000, 1500, 2000 of both adapters and base_prefill on valid_eval.jsonl.
# Same battery guard as run_training.sh. Resumable: evaluate.py skips questions already saved.
set -u
OUT=audit/lora_gsm8k_20261105
FLOOR=6
RESUME=8
MATCH="structured_llm.evaluate .*--out $OUT"

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

evaluate() {  # usage: evaluate <subdir> [--adapter dir] --modes ...
  local dir=$OUT/$1; shift
  mkdir -p $dir
  if [[ -e $dir/summary.json ]] && (( $(cat $dir/*.jsonl | wc -l) == 99 )); then
    echo "skip: $dir already has 99 rows"; return 0
  fi
  echo "cmd: .venv/bin/python -m structured_llm.evaluate --out $dir $*" >> $dir/eval_log.txt
  echo "start: $(date)" >> $dir/eval_log.txt
  .venv/bin/python -m structured_llm.evaluate --out $dir "$@" >> $dir/eval_log.txt 2>&1 &
  local pid=$!
  guard $pid $dir/load.txt &
  local watcher=$!
  # zsh's wait returns 145 (128 + SIGSTOP) when the guard pauses the job, so wait until it is really gone
  # and judge success by the saved rows, not by the exit code.
  local code
  while kill -0 $pid 2>/dev/null; do wait $pid; code=$?; done
  kill $watcher 2>/dev/null
  echo "exit: $code end: $(date)" >> $dir/eval_log.txt
  [[ -e $dir/summary.json ]] && (( $(cat $dir/*.jsonl | wc -l) == 99 ))
}

export HF_HUB_OFFLINE=1
VALID=data/structured_gsm8k_v1/valid_eval.jsonl
evaluate valid/base --data $VALID --limit 99 --modes base_prefill || exit 1
for it in 1000 1500 2000; do
  for a in gsm8k_plain_2000_s0 gsm8k_cf_2000_s0; do
    evaluate valid/${a}_it$it --data $VALID --limit 99 --adapter adapters/checkpoints/${a}_it$it --modes tuned || exit 2
  done
done
echo "all done: $(date)"
