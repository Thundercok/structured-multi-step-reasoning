# Structured-thinking LLM & RAT Desktop Reasoning

This repository holds one research project and the desktop app that will run its model:
1. **`structured_llm` (Research)**: Student research (NCKH) fine-tuning Qwen3-8B on Apple Silicon so its intermediate thinking follows verifiable structures (`<think>`, `Step`, `Calc`), and testing causal dependency via counterfactual interventions.
2. **`rat` (Agent harness and app)**: Desktop agent runtime with tools, contracts and verification, plus semantic file search, app launching, translation and PDF reading on macOS. It does not load the fine-tuned model yet.

Research never imports RAT. `tests/test_repo_boundaries.py` enforces that boundary so the two can still be split later.

---

## Repository Map

### 1. Research: Structured Thinking & Interventions (`structured_llm`)

| Path | Contents |
| --- | --- |
| `structured_llm/trace.py` | Format: render, parse and deterministic step checks |
| `structured_llm/gsm8k.py` | GSM8K conversion, canonical splits and data loading |
| `structured_llm/counterfactual.py` | Deterministic re-execution, counterfactual training data, intervention planning |
| `structured_llm/train.sh` | LoRA fine-tuning with Metal-bounded resource limits |
| `structured_llm/evaluate.py` | Fine-tuned model vs base-model comparisons on the dev split |
| `structured_llm/intervene.py` | Intervenes on intermediate calculation results to test answer dependency |
| `structured_llm/pal.py` | Program-aided math execution without arbitrary `exec` |
| `data/gsm8k_source/` | Pinned GSM8K train set, license and manifest |
| `data/gsm8k_development*/` | Prior development questions excluded from new splits |
| `docs/research_plan.md` | Research plan, experimental design, and progress status |

### 2. Agent harness and app (`rat`)

| Path | Contents |
| --- | --- |
| `main.py` / `rat/main.py` | RAT desktop application entry point (unified desk, quick PDF) |
| `rat/engine/` | Agent runtime, verification, semantic index, app search, local translation, goal routing, QA |
| `rat/kernel/` | OS capabilities: Spotlight finder, window management, accessibility, daemon |
| `rat/ui/` | Qt Quick / QML interfaces |
| `document_intake/` | Local document parsing and OCR extraction |
| `tools/` | Bundle preparation and offline model conversion tools |

---

## How to Run

### Setup Environment

#### Research (`structured_llm`)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

#### RAT (`rat`)
To install full dependencies for the desktop reasoning shell, PDF reader, and meaning search (including fastembed):
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-mini.txt fastembed watchdog
```

### Running Research (`structured_llm`)

```bash
# Run research test suite
.venv/bin/python -m pytest tests/test_analyze.py tests/test_counterfactual.py tests/test_math_check.py tests/test_math_data.py tests/test_structured_trace.py -q

# Prepare data and splits
.venv/bin/python -m structured_llm.gsm8k
.venv/bin/python -m structured_llm.counterfactual

# Fine-tune with LoRA
structured_llm/train.sh adapters/first 200

# Evaluate against base model
.venv/bin/python -m structured_llm.evaluate --adapter adapters/first --limit 20 --out audit/first

# Run causal intervention audit
.venv/bin/python -m structured_llm.intervene --run audit/first --adapter adapters/first
```

### Running RAT (`rat`)

```bash
# Launch the RAT desktop application (resident app)
python -m rat.main
# Runs as a resident macOS app with top menu bar icon, single-instance enforcement,
# and hide-on-close window behavior (closing the window hides rather than quits).
# Global shortcuts (Carbon-based, no macOS Accessibility permissions required):
#   - ⌃⌥Space (Control+Option+Space): Toggle RAT Desk (show / hide).
#   - ⌥⇧R (Option+Shift+R): Summon RAT Desk & run QuickLook Selection (translate/explain).

# Or run in standalone Quick PDF mode:
python -m rat.main quick-pdf

# Run RAT test suites
pytest tests/test_quick_pdf.py tests/test_goal_routing.py
```

---

## Notes & History

- Earlier controller code is preserved at git tag `pre-rebuild-20261102`.
- RAT was restored to `main` on 2026-11-03 alongside the research code.
- RAT Lite moved to [offline-tool-routing-agent](https://github.com/Thundercok/offline-tool-routing-agent) on 2026-11-03. Its last working source here is tag `rat-lite-0.6.0`.
- The research plan is documented in [docs/research_plan.md](docs/research_plan.md).
