# Research artifact index

This checkpoint preserves research code, data candidates and supporting audit
files. Human/source review and main-study measurements remain pending.
Synthetic evidence validates software; historical exposed tuning outcomes do
not establish held-out model quality, controller superiority or calibrated
difficulty. No main-study manuscript result is ready to publish from this index.

| Evidence | Location | Status and use |
| --- | --- | --- |
| Historical Qwen3-8B H4 raw outputs | `audit/G_sweep_trace.jsonl`, `audit/G_summary.txt`, `audit/G_completion_verification.json`, `audit/G_dirty.diff` | 188 records; original scoring retained. DIRECT 96 / CoT 1,024 caps confound instruction and budget. Cache snapshot name does not authenticate loaded weights. |
| Preserved partial H4 checkpoint | `audit/qwen3-8b-tuning-checkpoint-20261003/` | Historical 148-record checkpoint and resume-runner snapshot; not the final sweep. |
| H4 retrospective scoring/gold review | `audit/qwen3-8b-tuning-review-20261003/`, `scripts/review_tuning_sweep.py`, `audit/h4_tuning_review_validation.json` | Reproduces pinned legacy scores and separately checks typed scoring on exposed tuning data. Agent review; human review pending. |
| Development content/source audit | `audit/development-data-20261003-final/`, `audit/development_data_review.json`, `audit/development-source-evidence.json`, `audit/development_audit_baseline.json`, `audit/scoring_audit_cases.json`, `scripts/audit_development_data.py` | Independent agent calculations, wording repairs, source/license evidence and blind test fingerprints. No human sign-off. |
| Canonical procedural data candidate | `data/procedural_research_v1/`, `scripts/build_procedural_research_data.py`, `audit/procedural_data_validation.json` | Main 179/177 and tuning 94/91 items/groups; cross-release canonical identities disjoint. Frozen historical producing hashes retained. Publication and prior-test-exposure review pending. |
| Development pilot software validation | `audit/development-pilot-validation-20261004/`, `experiments/research_pilot.py`, `tests/test_research_pilot.py` | Saved synthetic matched-budget smoke/replay, label-independent selection preview, software validation. No measured model inference or policy fit. |
| Multi-seed aggregation software validation | `audit/research_aggregate_validation.json`, `experiments/research_aggregate.py`, `tests/test_research_aggregate.py` | Historical synthetic validation; fresh smoke/aggregate evidence referenced in the pilot validation. Average seeds per question before group bootstrap. No new independent questions from repeated seeds. |

Historical audit manifests may refer to local `runs/` directories excluded from
Git; their hashes remain historical evidence. Saved pilot smoke/replay inputs
and outputs are included in `audit/` for inspection from a fresh checkout.
Rebuild or rerun into a new directory with the corresponding source revision;
never update old source hashes to match newer code.

The supported entry point is `python -m experiments.research_study`. Review
`docs/development_pilot_protocol.md` before measured pilot collection. Freeze
main-study data/model/prompts/caps/seeds/lambda separately after pilot review.
The existing Stage 0 decision remains in `docs/stage0_gate_decision.md`.
