#!/bin/zsh
# Overnight Mega-Suite Orchestrator
# Waits for current GSM8K CF Enriched run to finish, then runs:
# Phase 1: GSM8K Enriched (Plain + CF) tuned_tool runtime calculator evaluation (100 dev items each)
# Phase 2: MATH Terminated-512 LoRA (adapters/math_lora_term_1000_s0) training (1000 steps) + Dev-100 eval + interventions
# Phase 3: MSRA Stage 1 Cold-Start DAG SFT (2000 steps) + Stage 2 Reference-Free SimPO (1000 steps) + Dev-100 eval
# Phase 4: Recompiles docs/paper/nckh_structured_reasoning.pdf after every phase.

set -u
cd "$(dirname "$0")/.."
export HF_HUB_OFFLINE=1

LOG="audit/overnight_mega_suite.log"
echo "=== OVERNIGHT MEGA-SUITE ARMED at $(date) ===" | tee -a "$LOG"

# AC/Battery Protection (Floor=6%, Resume=8%)
FLOOR=6
RESUME=8

check_battery() {
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

# 0. Wait for currently running turbo_orchestrator.sh / run_all.sh to finish completely
echo ">>> [Wait] Waiting for active GSM8K CF Enriched pipeline (run_all.sh / turbo_orchestrator.sh) to finish..." | tee -a "$LOG"
while pgrep -f "turbo_orchestrator\.sh|lora_gsm8k_enriched_20261107/run_all\.sh|gsm8k_cf_enriched_2000_s0" >/dev/null 2>&1; do
  sleep 30
done
sleep 5
echo ">>> [Wait] Active pipeline finished at $(date)! Starting Overnight Mega-Suite..." | tee -a "$LOG"

compile_pdf() {
  echo ">>> Recompiling docs/paper/nckh_structured_reasoning.pdf at $(date)..." | tee -a "$LOG"
  (
    cd docs/paper
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/bibtex nckh_structured_reasoning >/dev/null 2>&1
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
    /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
  )
}

# Ensure reports & PDF from GSM8K CF Enriched are up to date
check_battery
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare_19_failing.py >> "$LOG" 2>&1
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare.py >> "$LOG" 2>&1
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/report_generator.py >> "$LOG" 2>&1
compile_pdf

# ==============================================================================
# PHASE 1: GSM8K Enriched Runtime Calculator Ablation (tuned_tool, Dev-100)
# ==============================================================================
check_battery
echo ">>> [Phase 1/3] Running GSM8K Enriched tuned_tool evaluation at $(date)..." | tee -a "$LOG"
.venv/bin/python -m structured_llm.evaluate --limit 100 --out audit/lora_gsm8k_enriched_20261107/eval_plain --adapter adapters/gsm8k_enriched_2000_s0 --modes tuned_tool >> "$LOG" 2>&1
check_battery
.venv/bin/python -m structured_llm.evaluate --limit 100 --out audit/lora_gsm8k_enriched_20261107/eval_cf --adapter adapters/gsm8k_cf_enriched_2000_s0 --modes tuned_tool >> "$LOG" 2>&1
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare_19_failing.py >> "$LOG" 2>&1
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/compare.py >> "$LOG" 2>&1
PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_enriched_20261107/report_generator.py >> "$LOG" 2>&1
compile_pdf
echo ">>> [Phase 1/3] GSM8K tuned_tool evaluation complete at $(date)." | tee -a "$LOG"

# ==============================================================================
# PHASE 2: MATH Terminated-512 LoRA (adapters/math_lora_term_1000_s0)
# ==============================================================================
check_battery
echo ">>> [Phase 2/3] Building data/structured_math_term_v1 & training math_lora_term_1000_s0 at $(date)..." | tee -a "$LOG"
PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/build_terminated_math.py >> "$LOG" 2>&1
if [[ ! -e "adapters/math_lora_term_1000_s0/adapters.safetensors" ]]; then
  structured_llm/train.sh adapters/math_lora_term_1000_s0 1000 data/structured_math_term_v1 > audit/lora_math_20261107/train_term.log 2>&1
fi
mkdir -p audit/lora_math_20261107/eval_term
check_battery
.venv/bin/python -m structured_llm.evaluate --data data/math_source/structured_math_v1/dev.jsonl --limit 100 --max-tokens 1024 --adapter adapters/math_lora_term_1000_s0 --modes tuned --out audit/lora_math_20261107/eval_term >> "$LOG" 2>&1
check_battery
.venv/bin/python -m structured_llm.intervene --run audit/lora_math_20261107/eval_term --modes tuned --adapter adapters/math_lora_term_1000_s0 >> "$LOG" 2>&1
PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py >> "$LOG" 2>&1
compile_pdf
echo ">>> [Phase 2/3] MATH Terminated-512 LoRA complete at $(date)." | tee -a "$LOG"

# ==============================================================================
# PHASE 3: Side-Scope MSRA Stage 1 (DAG Cold-Start) + Stage 2 (SimPO)
# ==============================================================================
check_battery
echo ">>> [Phase 3/3] Starting Side-Scope MSRA Stage 1 & Stage 2 SimPO at $(date)..." | tee -a "$LOG"
./audit/lora_msra_20261107/run_msra_stage1.sh >> "$LOG" 2>&1
if [[ -e "adapters/msra_coldstart_2000_s0/adapters.safetensors" ]]; then
  if [[ ! -e "data/msra_simpo_v1/train.jsonl" ]]; then
    PYTHONPATH=. .venv/bin/python -m structured_llm.msra.preference_builder --adapter adapters/msra_coldstart_2000_s0 --data data/msra_math_v1/train_meta.jsonl --out data/msra_simpo_v1 >> "$LOG" 2>&1
  fi
  if [[ ! -e "adapters/msra_simpo_1000_s0/adapters.safetensors" ]]; then
    PYTHONPATH=. .venv/bin/python -m structured_llm.msra.simpo_train --init-adapter adapters/msra_coldstart_2000_s0 --data data/msra_simpo_v1 --adapter-path adapters/msra_simpo_1000_s0 --iters 1000 > audit/lora_msra_20261107/train_simpo.log 2>&1
  fi
  PYTHONPATH=. .venv/bin/python -m structured_llm.msra.evaluate_msra --adapter adapters/msra_simpo_1000_s0 --limit 100 --out audit/lora_msra_20261107/eval_simpo_dev100.json >> "$LOG" 2>&1
  PYTHONPATH=. .venv/bin/python audit/lora_msra_20261107/compare_msra.py >> "$LOG" 2>&1
fi
compile_pdf
echo "=== ALL OVERNIGHT MEGA-SUITE PHASES COMPLETED at $(date) ===" | tee -a "$LOG"
