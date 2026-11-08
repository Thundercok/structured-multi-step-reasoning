#!/bin/zsh
# Master Sequential Orchestrator for Multi-Step Structured Reasoning
# Chains all training phases sequentially to prevent Apple Silicon unified RAM contention.
# Run with: nohup audit/turbo_orchestrator.sh > audit/turbo_orchestrator.log 2>&1 &

set -u
cd "$(dirname "$0")/.."

LOG="audit/turbo_orchestrator.log"
echo "=== TURBO MASTER ORCHESTRATOR LAUNCHED at $(date) ===" | tee -a "$LOG"

notify() {
  local title="$1" msg="$2"
  osascript -e "display notification \"$msg\" with title \"$title\" sound name \"Glass\"" 2>/dev/null || true
}

# Phase 1: Complete GSM8K Enriched Sweep
GSM8K_REPORT="audit/lora_gsm8k_enriched_20261107/REPORT.md"
echo ">>> [Phase 1/4] Running GSM8K Enriched Sweep at $(date)..." | tee -a "$LOG"
if [[ -e "$GSM8K_REPORT" ]]; then
  echo ">>> [Phase 1/4] GSM8K Enriched sweep already completed. Skipping." | tee -a "$LOG"
else
  ./audit/lora_gsm8k_enriched_20261107/run_all.sh 2>&1 | tee -a "$LOG"
  echo ">>> [Phase 1/4] GSM8K Enriched sweep finished at $(date)." | tee -a "$LOG"
  notify "GSM8K Complete" "Enriched GSM8K evaluation and reports completed."
fi

# Phase 2: Run MATH Level 3-5 LoRA
echo ">>> [Phase 2/4] Launching MATH Level 3-5 LoRA Training at $(date)..." | tee -a "$LOG"
if [[ -e "adapters/math_lora_1000_s0/adapters.safetensors" ]]; then
  echo ">>> [Phase 2/4] MATH adapter already trained. Skipping." | tee -a "$LOG"
else
  ./audit/lora_math_20261107/run_math_training.sh 2>&1 | tee -a "$LOG"
  echo ">>> [Phase 2/4] MATH training complete at $(date)." | tee -a "$LOG"
  notify "MATH LoRA Complete" "MATH Level 3-5 adapter and evaluation complete."
fi

# Phase 3: Run MSRA Stage 1 Cold-Start SFT
echo ">>> [Phase 3/4] Launching MSRA Stage 1 Cold-Start SFT at $(date)..." | tee -a "$LOG"
if [[ -e "adapters/msra_coldstart_2000_s0/adapters.safetensors" ]]; then
  echo ">>> [Phase 3/4] MSRA Stage 1 adapter already trained. Skipping." | tee -a "$LOG"
else
  ./audit/lora_msra_20261107/run_msra_stage1.sh 2>&1 | tee -a "$LOG"
  echo ">>> [Phase 3/4] MSRA Stage 1 complete at $(date)." | tee -a "$LOG"
  notify "MSRA Stage 1 Complete" "Cold-start DAG SFT adapter and evaluation complete."
fi

# Phase 4: Run MSRA Stage 2 SimPO Preference Alignment
echo ">>> [Phase 4/4] Launching MSRA Stage 2 SimPO Optimization at $(date)..." | tee -a "$LOG"
if [[ -e "adapters/msra_simpo_1000_s0/adapters.safetensors" ]]; then
  echo ">>> [Phase 4/4] MSRA Stage 2 adapter already trained. Skipping." | tee -a "$LOG"
else
  ./audit/lora_msra_20261107/run_msra_stage2_simpo.sh 2>&1 | tee -a "$LOG"
  echo ">>> [Phase 4/4] MSRA Stage 2 complete at $(date)." | tee -a "$LOG"
  notify "MSRA SimPO Complete" "SimPO preference alignment completed."
fi

# Phase 5: Re-compile LaTeX Paper PDF
echo ">>> [Phase 5] Recompiling Academic Paper PDF..." | tee -a "$LOG"
(
  cd docs/paper
  /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
  /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/bibtex nckh_structured_reasoning >/dev/null 2>&1
  /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
)
notify "NCKH Pipeline Complete" "All phases and academic paper compiled successfully!"
echo "=== ALL TURBO PIPELINE PHASES COMPLETED at $(date) ===" | tee -a "$LOG"
