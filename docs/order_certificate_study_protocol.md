# Offline ordering certificate extension

This is a headless, ordering-only extension of the supported research entry
point. It prepares a candidate release, tests same-output gate comparisons, and
now offers a guarded development-only collector. Its repairs have offline/mock
regressions; a [two-question measured development pilot](../audit/order_certificate_real_pilot_review_20261008.md)
has also been checked against raw artifacts. Neither establishes Stage 0,
confirmatory model quality or a cheap-verifier advantage.
The [draft addendum](../prereg/decision_rule_verified_pal_order_v2.md) specifies
the comparisons, proposed settings, cost scope and remaining review decisions.

## Reproduce the offline artifacts

Use the repository's research Python environment (Python 3.12 in this workspace).
Each preparation/smoke/analysis output path must be new; these modes never
overwrite a run directory or modify the input release.

```bash
python -m experiments.research_study --order-certificate-prepare data/order_confirmatory_gapB_100.json --output data/NEW_ORDER_CANDIDATE
python -m experiments.research_study --order-certificate-smoke --output audit/NEW_ORDER_SMOKE
python -m experiments.research_study --order-certificate-analysis audit/NEW_ORDER_SMOKE --output audit/NEW_ORDER_REPLAY
```

Preparation saves supported `dataset.json`, `plan.json`, `isolation.json`, report
and hashed manifest. It preserves prospective questions/labels and changes only
schema, split/identity fields and provenance. There are 8 exposed train items,
23 exposed calibration items and 100 prospective test items. Preparation performs
label-free canonical checks, not test-answer solving, semantic review or power
validation. Human review and publication eligibility remain explicitly pending.

Smoke uses 12 authored fixture questions and fabricated model outputs/costs,
three recorded seeds and four arms. It saves every raw prompt/output, termination
reason, decoding setting and per-call token component. There are no model calls,
no model download and no execution of generated Python. The native-thinking arm
is a schema fixture only; the real runtime adapter still needs development review.

Replay verifies source/settings/artifact hashes and the complete item × seed ×
arm matrix before recomputing policy paths. Changed inputs, missing selector
calls/prompts, mismatched execution answers and incomplete telemetry are rejected.
Offline CPU timing can vary on replay; paths, answers and token counts cannot.

## Development pilot and interruption safety

Software validation without MLX imports, model loading or GPU:

```bash
python -m experiments.research_study --order-certificate-pilot --order-pilot-mock --order-pilot-items 2 --seed 42 --output audit/NEW_ORDER_PILOT_MOCK
```

This mode selects only the exposed train pool (at most eight questions), never
test or calibration. Mock uses authored gold-aware outputs and placeholder
word-count token telemetry; its evidence is `synthetic_smoke` on dataset, each
record/call, journal, manifest and report. It is not a measured-model result.
Omitting `--order-pilot-mock` enables real MLX collection and must be a deliberate,
resource-approved development run after adapter review; no such run is made by
the offline checks. A development cap override is available as
`--order-pilot-thinking-tokens`; changing it requires a NEW output directory.

The authorized [eight-question development plan](../audit/order_dev8_contract_v2_plan_20261008.md)
uses `order-contract-v2`, an explicit zero-based candidate prompt and a bounded
single-index parser, with a bare-name PAL-answer prompt. Its native cap override
is 2,048. The scorer is unchanged; source/profile changes require a fresh run.
These jointly changed settings do not isolate the effect of any one repair.

The collector saves exact messages, rendered prompts for real calls, raw outputs,
termination, derived seeds, per-call caps, prompt/completion counts and generation
time. Actual PAL execution is a separate saved record linked to its generation.
The sandbox helper is not a security boundary; real generated code needs a
controlled environment. No test run or router fit is enabled by this pilot.

Resume uses the **same command and directory** only if mode/evidence, selected
data, settings, source hashes and runtime identity match. An unlabelled legacy
directory, mock-to-real switch, changed cap/seed/selection/source or corrupt
journal fails closed before model loading. Completed runs additionally verify
every artifact hash and return saved reports without rewriting them. A writer
lock prevents two collectors from updating the same run.

`calls.jsonl` is an append-only, checksummed journal. Each completed generation
is flushed/fsynced before execution or the next generation; each completed
execution is saved before proceeding. `records.json`/`records.jsonl` are derived
completed-arm snapshots, not the primary partial-call ledger. A valid fsynced
tail can be recovered when its manifest update lagged; a torn/corrupt tail is
preserved for review, never silently truncated. A generation interrupted before
completion may still have consumed resources not retained as completed-call
telemetry; do not claim crash-proof accounting of all attempted inference.

`summary.json` and `eval_rows.json` use the same scorer as study replay. Selected
branch/selector/native/PAL truncation is incorrect even if text matches gold.
Gate confusion labels FIRST-STAGE answer correctness, not fallback correctness.
Generation-time replay, execution diagnostics, offline verifier time and symbolic
CPU-path time are distinct; none establishes measured online end-to-end latency.

## Fair comparison and verifier boundary

W-certificate accepts a successful nonempty certificate PAL execution unless
generation was truncated. Verified-certificate uses the SAME generation/result,
but accepts only a valid certificate. Both use the SAME recorded fallback.
Answer-only W is reported separately because its prompt contract is different.
Fallback generates three full candidates and selects one, not a tree of thoughts.
An unselected length-stopped branch does not invalidate a complete chosen branch;
all branch/selector costs still count.

Verification consumes the entire supported question template and actual result
payload; unsupported prose, malformed certificates or failed executions escalate.
It uses neither item metadata nor gold. Correctness labels are used only after
the paths/answers are selected, for scoring and error diagnostics.

The generic verifier establishes uniqueness of the asked occupant by exact
symbolic solving. It is not a witness-only cheap check. The same query parser
plus solver appears as a mandatory standalone zero-model-token baseline, with
CPU time separate. If a reviewed release later supports witness-only verification,
that mode must be frozen before collection, not selected from test results.

## Statistics and evidence limits

Primary metrics use test rows only, with question-weighted means over three
seeds. Cluster bootstrapping retains all variants and seeds of each group.
The current software's −5 pp accuracy margin (changed from −2 pp) and 0.60
token-ratio threshold are **draft proposals**, not reviewed/frozen criteria.
Their diagnostic calculations use CI endpoints, not merely point estimates or
a CI containing zero. Sample-size/power justification and a boundary-safe
non-inferiority rule are still missing; the former claim of 80% power is withdrawn.
Single-group or degenerate accuracy-bootstrap cases cannot establish success.
Both fixed-candidate and same-contract W
comparisons are saved, along with first-stage confusion and rescue/harm counts.

Token cost sums all selected-path prompt and completion counts. Smoke counts are
synthetic; future measured counts would still be model-token counts, not total
compute. Replayed strategy time and fresh verifier/solver CPU time are separate,
neither a measured online latency claim.

QA assessment: **share as software-validation evidence only**. Source/schema/
isolation checks and passing tests do not establish human gold review, sufficient
power, checkpoint provenance, a confirmed cheap-verifier advantage or novelty.
Confirmatory measured ingestion/analysis is disabled until a reviewed execution
addendum and the existing campaign gates are satisfied. The development collector
does not override that restriction. No router expansion or UI work is included.
