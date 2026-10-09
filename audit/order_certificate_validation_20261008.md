# Ordering certificate offline validation — 2026-10-08

Assessment: share as SOFTWARE-VALIDATION evidence only. No real-model inference,
test-gold solving/review, publication freeze or Stage 0 change.

## Artifacts and reproducibility

- Candidate: `data/order_certificate_candidate_v1/`; four hashed artifacts.
- Synthetic run: `audit/order_certificate_smoke_20261008/`; six hashed artifacts.
- Replay: `audit/order_certificate_smoke_replay_20261008/`; three hashed artifacts.
- All manifests completed, all output SHA-256 checks passed, no model calls.
- Original candidate/development input hashes still match the saved manifest.
- Candidate splits: train 8, calibration 23, test 100. All 31 historical ordering
  items remain exposed development, regardless of their original split labels.
- Zero canonical overlap with eight available legacy/development/main sources.
  This does not establish semantic independence or adequate sample size.
- All 288 replay rows reproduced method/item/seed, paths, answers, correctness,
  prompt/completion/total token counts and verification status. Fresh offline
  CPU measurements are intentionally not required to match.

## Verified methodology checks

- Same certificate PAL/fallback outputs for W-certificate and Verified-certificate.
- Query-only exact symbolic baseline; generic uniqueness verification includes
  solving and is not presented as a free witness-only check.
- Whole-query and whole-result parsing; failed/unrecorded termination, malformed
  permutation, ambiguous asked occupant and source-literal substitution fail closed.
- Solver cross-checked against independent exhaustive permutations on 60 fixtures.
- Poisoning gold labels cannot change gate paths or verification status.
- Complete item/seed/arm telemetry required, including all selector inputs/costs.
- Cost identity uses the fallback mean conditional on rejection, checked against
  the sum of all invoked call costs.
- Seed observations stay within original group bootstrap clusters. CI endpoints,
  not a CI containing zero, determine the proposed noninferiority/token gate.
- Single-group and degenerate accuracy-bootstrap cases cannot establish success.
- Native-thinking outputs and tokens in smoke are fabricated fixtures only.

## Test command

```bash
python3.12 -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verified_pal_order.py tests/test_order_certificate_study.py tests/test_procedural_research_data.py tests/test_think_on_demand_replay.py tests/test_research_scoring.py tests/test_research_pilot.py tests/test_research_aggregate.py tests/test_direct_cot_analysis.py -q
```

Result: **168 passed**. `git diff --check` also passed. Includes all three
repository-mandated research harness/threshold/predictor tests.

## Remaining gates

Human generator/parser/gold/group/exposure/license review; power/sample-size and
boundary-safe statistical review; final choice of verifier mode; checkpoint
content provenance; native-thinking adapter, termination and token-accounting
validation on development; a reviewed execution freeze and campaign Stage 0.
The addendum is a draft, not a committed preregistration. Measured ingestion is
disabled. No conclusion about model quality, cascade superiority or algorithmic
novelty follows from these fixtures.

Pre-existing unrelated changes (`audit/_aborted_AG3/`, `data/gen02_v2b.json`,
`scripts/report_ag.py`) were left untouched. No commit/push/pull/reset performed.
