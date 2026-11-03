# Structured-thinking LLM & RAT Desktop Reasoning

This repository houses two interconnected efforts:
1. **`structured_llm` (Research)**: Student research (NCKH) fine-tuning Qwen3-8B on Apple Silicon so its intermediate thinking follows verifiable structures (`<think>`, `Step`, `Calc`), and testing causal dependency via counterfactual interventions.
2. **`rat` (Apps)**: Desktop reasoning shell and on-device assistant (RAT and RAT Lite) providing smart semantic file search, app launching, zero-cloud translation, and local PDF reading on macOS.

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

### 2. Applications: RAT Desktop & RAT Lite (`rat`)

| Path | Contents |
| --- | --- |
| `mini_app.py` | RAT Lite entry point (on-device search and quick lookups) |
| `main.py` / `rat/main.py` | Full RAT desktop application entry point (unified desk, quick PDF, reasoning lab) |
| `rat/engine/` | Core engines: semantic index, app search, local translation, goal routing, QA |
| `rat/kernel/` | OS capabilities: Spotlight finder, window management, accessibility, daemon |
| `rat/ui/` | Qt Quick / QML interfaces for full RAT and Lite desks |
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

#### RAT Desktop & RAT Lite (`rat`)
To install full dependencies for the desktop reasoning shell, PDF reader, and meaning search (including fastembed):
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-mini.txt fastembed watchdog
```

### Running Research (`structured_llm`)

```bash
# Run research test suite
.venv/bin/python -m pytest tests/test_structured_trace.py tests/test_counterfactual.py -q

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

### Running RAT & RAT Lite (`rat`)

```bash
# Verify offline bundles and on-device readiness
python mini_app.py --check-bundle

# Launch RAT Lite (On-device Quick Search & Lookups)
python mini_app.py

# Launch Full RAT Desktop Application
python -m rat.main
# or in Quick PDF mode:
python -m rat.main quick-pdf

# Run RAT test suites
pytest tests/test_rat_mini*.py tests/test_quick_pdf.py tests/test_goal_routing.py
```

---

## Notes & History

- Earlier controller code is preserved at git tag `pre-rebuild-20261102`.
- RAT and RAT Lite were restored to `main` on 2026-11-03 alongside the research code under tag `rat-lite-0.6.0`.
- The research plan is documented in [docs/research_plan.md](docs/research_plan.md).
