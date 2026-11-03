# Project

Student research (NCKH): build a language model with structured thinking by fine-tuning
Qwen3-8B, and test by intervention whether its answers really depend on that thinking.
The object of study is the model, not a controller around it. Read
`docs/research_plan.md` before changing scope, evaluation or claims. That plan is a
proposal until the advisor confirms it in writing; never write that it was approved.

## Rebuild, 2026-11-02

The user authorized a full rebuild on 2026-11-02. The controller research code was removed
from the tree; the user restored RAT on 2026-11-03 to main alongside the research code.
Legacy controller code remains in git history at tag `pre-rebuild-20261102`. Do not delete
that tag: it also holds Spider adapter code whose destination import has not been verified,
and the decisions in the old `AGENTS.md`.

Do not restore old code as routine work. Do not remove these recovery and evidence
locations: `.migration-backups/`, `runs/`, `outputs/`, `dist/`, and the linked worktrees.

## Research rules

- Never read the official GSM8K test file, or a set derived from it such as GSM-Symbolic,
  until the user decides to in chat. Keep train, valid, dev and any sealed test disjoint;
  do not change a split or threshold after seeing its result.
- Do not use the old CoT or DIRECT prompts as baselines: their labels don't match what the
  model did (`audit/base_error_anatomy_20261102/`), so they would show a false gain.
- Publish only claims supported by raw outputs. Label smoke runs as smoke runs.
- Passing tests show the checks work; they are not evidence of model quality.
- Old controller results measured other prompts and items. Do not compare them directly.

## Commands

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m structured_llm.gsm8k
.venv/bin/python -m structured_llm.counterfactual
structured_llm/train.sh adapters/<name> 200 [data-dir]
.venv/bin/python -m structured_llm.evaluate --adapter adapters/<name> --limit 20 --out audit/<run>
.venv/bin/python -m structured_llm.intervene --run audit/<run> --adapter adapters/<name>
```

Training needs an idle machine where possible; the Metal limits in `structured_llm/train.sh` are required
on a 16 GB M1.

## Repo boundaries

This stays one repo. Research and RAT stay separable: research never imports RAT, and
RAT imports only the `structured_llm` modules listed in `tests/test_repo_boundaries.py`.
New tracked files must fit an owner there. Do not create another repo unless the user asks.
RAT Lite now lives in `Thundercok/offline-tool-routing-agent`; do not add it back here. Its
last working source here is tag `rat-lite-0.6.0`, which must stay.

## Git

Work on `main`. Do not create branches unless the user asks. Never pull, reset or force
unless the user says so in the same message. Commit and push only when asked.
