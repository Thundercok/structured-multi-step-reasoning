# Structured Multi-Step Reasoning

Student research (NCKH) that fine-tunes a small model, Qwen3-8B, to write its thinking in checkable
steps (`<think>`, `Step`, `Calc`). It then edits a `Calc` result and measures whether the answer
depends on that thinking. The object of study is the model. **No thesis is held right now:** two
were tested and dropped on 2026-11-04.

The repository also holds **RAT**, the macOS app used as the project's demo. RAT is not part of the
research claims and does not load the fine-tuned model yet.

## Status

The [research plan](docs/research_plan.md) is a proposal. There is no final model yet; fine-tuned
results come from a 200-iteration trial adapter.

| Gate | Requires | Result so far |
| --- | --- | --- |
| 0. Format learned | `format_valid` at least 90% on dev | **Not met:** 70% |
| 1. A gap exists | Base model follows an edited `Calc` less than 95% of the time | **No gap on GSM8K:** 0 of 53 kept the old answer |
| 2. Room in the literature | No paper has done the main question | Passed provisionally, not yet a systematic review |
| 3a. MATH is checkable | At least 50% of hard problems can be checked | **Not met:** 23.3%, continuing on a labelled subset |
| 3b. MATH is hard enough | Comparison modes at most 90% correct | **Passed:** 64 and 55 of 100 |
| 4. A signal exists | Check catches at least 50% of wrong answers, at most 20% false alarms | **Not met for checks on the thinking:** equation checks caught 2 of 82 |

Under the plan, a failed gate 4 means choosing what to do next: drop the Q1 target and write up the
negative result, or take a new direction. That decision is open.

## Research

| Path | Contents |
| --- | --- |
| `structured_llm/trace.py` | Thinking format: render, parse, deterministic step checks |
| `structured_llm/gsm8k.py` | GSM8K conversion, splits and loading |
| `structured_llm/math_check.py`, `math_data.py` | SymPy equation checks and the checkable MATH subset |
| `structured_llm/counterfactual.py` | Re-execution, counterfactual training data, intervention planning |
| `structured_llm/train.sh` | LoRA fine-tuning within Metal limits for a 16 GB M1 |
| `structured_llm/evaluate.py` | Fine-tuned model against the comparison modes |
| `structured_llm/intervene.py` | Edits `Calc` results and records whether the answer follows |
| `structured_llm/analyze.py` | Rescores a run from its raw outputs |
| `structured_llm/pal.py` | Interprets model-written programs without `exec` |
| `data/` | Pinned GSM8K train set and splits; questions already seen are kept out of new splits |
| `audit/` | Raw outputs and notes for each measured run |
| `docs/` | Research plan, literature survey, earlier controller reports |

MATH problem text is not committed. With a local copy at `data/math_source/train.jsonl`,
`python -m structured_llm.math_data` rebuilds the subset.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python -m pytest tests/test_analyze.py tests/test_counterfactual.py tests/test_math_check.py tests/test_math_data.py tests/test_structured_trace.py -q

.venv/bin/python -m structured_llm.gsm8k
.venv/bin/python -m structured_llm.counterfactual
structured_llm/train.sh adapters/first 200
.venv/bin/python -m structured_llm.evaluate --adapter adapters/first --limit 20 --out audit/first
.venv/bin/python -m structured_llm.intervene --run audit/first --adapter adapters/first
.venv/bin/python -m structured_llm.analyze audit/first
```

## RAT

A resident macOS agent app: a runtime with tools, outcome contracts and verification, plus file
search by name and meaning, app launching, translation and PDF reading. Development steps are in
[rat/ROADMAP.md](rat/ROADMAP.md).

RAT is meant to run locally, but that is not finished: it still has cloud paths (Gemini, OpenAI,
Google Translate, MyMemory) that can run when API keys are set or local translation models are missing.

| Path | Contents |
| --- | --- |
| `main.py`, `rat/main.py` | Entry points |
| `rat/engine/` | Agent runtime, verification, search, translation, routing |
| `rat/kernel/` | Tool registry, dispatcher, contracts, capabilities |
| `rat/os/` | Menu bar, hotkeys, permissions, daemon, shell integration |
| `rat/ui/` | Qt Quick interface |
| `rat/crawler/`, `timetable/`, `astrology/`, `plugins/` | File indexing and optional domain tools |
| `reasoning/`, `research_scoring.py` | The earlier controller, which RAT still imports |
| `document_intake/` | PDF reading and OCR |
| `tools/` | Model preparation and the hotkey helper |

Requires Python 3.12 on macOS.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-rat.txt

python -m rat.main            # resident app in the menu bar
python -m rat.main quick-pdf  # PDF desk only

pytest tests/test_quick_pdf.py tests/test_goal_routing.py
```

Shortcuts: ⌃⌥Space shows or hides the desk. ⌥⇧R opens it and translates or explains the selected text.

## History

- The earlier controller research is at tag `pre-rebuild-20261102`. It did not beat always running
  PAL once a scoring error was fixed, and those results should not be compared with the current work.
- RAT Lite moved to [offline-tool-routing-agent](https://github.com/Thundercok/offline-tool-routing-agent).
  Its last working source here is tag `rat-lite-0.6.0`.
