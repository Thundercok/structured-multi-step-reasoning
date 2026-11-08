#!/bin/zsh
# Multi-Seed Training & Evaluation Suite for GSM8K Enriched Counterfactual LoRA
# Trains Seed 1 (s1) and Seed 2 (s2) for 2,000 steps each, evaluates on Dev-100,
# runs causal interventions, and aggregates Mean ± Std.
# Protected by Battery/AC Power Guard. Run from repo root.

set -u
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

LOG="audit/lora_gsm8k_enriched_20261107/multiseed_run.log"
echo "=== GSM8K MULTI-SEED SUITE LAUNCHED at $(date) ===" | tee -a "$LOG"

FLOOR=6
RESUME=8
DATA="data/structured_gsm8k_cf_enriched_v1"
DEV_DATA="data/structured_gsm8k_enriched_v1/dev.jsonl"
ITERS=2000

check_power() {
  while true; do
    local b_info=$(pmset -g batt 2>/dev/null || true)
    if echo "$b_info" | grep -q "AC Power"; then
      break
    fi
    local pct=$(echo "$b_info" | grep -oE '[0-9]+%' | head -1 | tr -d %)
    if [[ -n "$pct" && "$pct" -le "$FLOOR" ]]; then
      echo ">>> [Battery Guard] Battery low (${pct}% <= ${FLOOR}%), pausing until AC power connected or battery >= ${RESUME}%..." | tee -a "$LOG"
      while true; do
        sleep 60
        local b_curr=$(pmset -g batt 2>/dev/null || true)
        local p_curr=$(echo "$b_curr" | grep -oE '[0-9]+%' | head -1 | tr -d %)
        if echo "$b_curr" | grep -q "AC Power" || [[ -n "$p_curr" && "$p_curr" -ge "$RESUME" ]]; then
          echo ">>> [Battery Guard] Power restored (batt=${p_curr}%), resuming..." | tee -a "$LOG"
          break
        fi
      done
    fi
    break
  done
}

compile_pdf() {
  echo ">>> Recompiling academic paper PDF..." | tee -a "$LOG"
  (
    cd docs/paper
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/bibtex nckh_structured_reasoning >/dev/null 2>&1
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
  ) >> "$LOG" 2>&1 || true
}

for seed in 1 2; do
  ADAPTER="adapters/gsm8k_cf_enriched_2000_s${seed}"
  EVAL_DIR="audit/lora_gsm8k_enriched_20261107/eval_cf_s${seed}"
  TRAIN_LOG="audit/lora_gsm8k_enriched_20261107/train_gsm8k_cf_enriched_2000_s${seed}.log"

  echo "------------------------------------------------------------------------" | tee -a "$LOG"
  echo ">>> [Seed ${seed}] Starting pipeline for $ADAPTER at $(date)..." | tee -a "$LOG"

  # 1. Training
  if [[ -e "$ADAPTER/adapters.safetensors" ]]; then
    echo ">>> [Seed ${seed}] Adapter $ADAPTER already exists. Skipping training." | tee -a "$LOG"
  else
    check_power
    echo ">>> [Seed ${seed}] Training $ADAPTER ($ITERS steps, seed=$seed)..." | tee -a "$LOG"
    structured_llm/train.sh "$ADAPTER" "$ITERS" "$DATA" 512 "$seed" > "$TRAIN_LOG" 2>&1
    echo ">>> [Seed ${seed}] Training complete at $(date)." | tee -a "$LOG"
  fi

  # 2. Dev-100 Evaluation
  mkdir -p "$EVAL_DIR"
  if [[ -e "$EVAL_DIR/tuned.jsonl" && $(wc -l < "$EVAL_DIR/tuned.jsonl") -ge 100 ]]; then
    echo ">>> [Seed ${seed}] Evaluation on Dev-100 already complete. Skipping." | tee -a "$LOG"
  else
    check_power
    echo ">>> [Seed ${seed}] Evaluating on 100 Dev questions at $(date)..." | tee -a "$LOG"
    .venv/bin/python -m structured_llm.evaluate \
      --data "$DEV_DATA" \
      --limit 100 \
      --max-tokens 1024 \
      --adapter "$ADAPTER" \
      --modes tuned \
      --out "$EVAL_DIR" >> "$LOG" 2>&1
    echo ">>> [Seed ${seed}] Dev evaluation complete at $(date)." | tee -a "$LOG"
  fi

  # 3. Causal Interventions
  if [[ -e "$EVAL_DIR/interventions_summary.json" ]]; then
    echo ">>> [Seed ${seed}] Causal interventions already evaluated. Skipping." | tee -a "$LOG"
  else
    check_power
    echo ">>> [Seed ${seed}] Running causal interventions at $(date)..." | tee -a "$LOG"
    .venv/bin/python -m structured_llm.intervene \
      --run "$EVAL_DIR" \
      --modes tuned \
      --adapter "$ADAPTER" >> "$LOG" 2>&1 || echo "Intervene returned status $?" >> "$LOG"
  fi

  # 4. Aggregate available seeds so far
  .venv/bin/python audit/lora_gsm8k_enriched_20261107/aggregate_seeds.py >> "$LOG" 2>&1
  compile_pdf
done

echo "=== ALL MULTI-SEED RUNS COMPLETED at $(date) ===" | tee -a "$LOG"
