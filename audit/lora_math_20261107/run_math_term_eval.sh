#!/bin/zsh
# Evaluation and Interventions for MATH Terminated-512 LoRA adapter
# (adapters/math_lora_term_1000_s0) on the 100 MATH dev problems.
# Runs evaluation, causal interventions, statistical comparison, and PDF compilation.

set -u
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1

LOG="audit/lora_math_20261107/eval_term_run.log"
echo "=== MATH Terminated-512 Evaluation Pipeline Launched at $(date) ===" | tee -a "$LOG"

ADAPTER="adapters/math_lora_term_1000_s0"
DATA="data/math_source/structured_math_v1/dev.jsonl"
OUT="audit/lora_math_20261107/eval_term"

mkdir -p "$OUT"

echo ">>> [1/4] Running 100 Dev Evaluation on $ADAPTER at $(date)..." | tee -a "$LOG"
.venv/bin/python -m structured_llm.evaluate \
  --data "$DATA" \
  --limit 100 \
  --max-tokens 1024 \
  --adapter "$ADAPTER" \
  --modes tuned \
  --out "$OUT" >> "$LOG" 2>&1

echo ">>> [2/4] Running RQ2 Causal Interventions on $OUT at $(date)..." | tee -a "$LOG"
.venv/bin/python -m structured_llm.intervene \
  --run "$OUT" \
  --modes tuned \
  --adapter "$ADAPTER" >> "$LOG" 2>&1 || echo "Intervene returned status $?" >> "$LOG"

echo ">>> [3/4] Updating MATH Comparisons & Reports at $(date)..." | tee -a "$LOG"
PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py >> "$LOG" 2>&1

echo ">>> [4/4] Recompiling Academic Paper PDF at $(date)..." | tee -a "$LOG"
(
  cd docs/paper
  /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
  /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/bibtex nckh_structured_reasoning >/dev/null 2>&1
  /Users/thundercock2/Library/TinyTeX/bin/universal-darwin/pdflatex -interaction=nonstopmode nckh_structured_reasoning.tex >/dev/null 2>&1
) >> "$LOG" 2>&1

echo "=== MATH Terminated-512 Evaluation Pipeline Completed at $(date) ===" | tee -a "$LOG"
