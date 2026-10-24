# GSM8K G1–G5 repair follow-up review — 2026-10-24

**Verdict: earlier counterexamples repaired, but full acceptance remains open
for H1–H3 below.** No production implementation changed during review, no
candidate data opened, no model/embedding calls, no bridge or Stage 0 change.

## Confirmed repairs

Fresh nine-file regression suite from the repair handoff: **165 passed in
9.63s**, exit 0. The repair author's verification script was copied into this
new directory and rerun without overwriting their evidence. Its assertions
pass; [verification.json](verification.json) records the results and source
hashes. Script: [verification_rerun.py](verification_rerun.py).

Verified: negative/over-cap/bool payloads rejected under the default cap;
unknown tokens remain reservations; orphan charge restored; generation-terminal
evidence reconstructs a DIRECT record without redispatch; bank swapping after
seal rejected; staged fitting avoids the validation-record file; pre-seal
aggregate accuracy suppressed; staged collect -> seal -> validation completes
on authored fixtures with five rows. These are specific tested repairs, not
proof that every promised integrity/blinding/real-backend contract is complete.

## H1 — [P1] Bind dispatch arguments to the pinned identity before any event

`experiments/gsm8k_collector.py:run_staged_collection` accepts its own
`token_budget`, `master_seed`, `strategies`, dataset and budget-envelope arguments
without matching them to checkpoint identity/settings. Result validation uses
the supplied cap, so it validates against the wrong contract if that cap was
changed. Constructor equality on resume cannot protect dispatch in this path.

Fresh probe: checkpoint identity cap **1,024**, seed **42**; invoke collection
with cap **2,048**, seed **999** and an authored 1,500-token outcome. Collection
marks **complete**, recording cap 2,048 and a seed derived from 999 beneath the
unchanged identity. The same journal subsequently conflicts with its own pinned
start-event checks. This was explicitly requested in G1's dispatch-parameter
binding repair, not covered by the new default-cap negative tests.

Required: one validated immutable execution contract feeds both dispatch and
resume. Reject mismatched cap/seed/action list/dataset and budget changes before
dispatch/journal mutation. Validate no duplicates/unknown conditions and require
identity completeness at creation as well as resume. Add a test that observes
zero runner dispatches and unchanged evidence on mismatch.

## H2 — [P1] Preserve measured-data/provenance gates on the staged input path

`experiments/gsm8k_routing_baseline.py:write_fitting_seal` enforces the 96-group,
48/48, pinned GSM8K source/Qwen provenance checks **only in the legacy branch**.
The staged branch interprets any evidence string not starting `synthetic` as
measured, defaults a missing evidence value to synthetic, and copies collection
source hashes without verifying them. It does not enforce the measured frame
or model/source identity there.

Probe: relabel a two-question authored staged bank with
`evidence="measured_development_pilot"`, no model provenance and
`source_hashes={"authored_unverified_source":"not-a-sha256"}`. Seal and validation
both succeed with **measured_development_saved_output_analysis**. This is a
controlled adversarial label test: all actual outputs remain synthetic and no
model executes. It demonstrates the removed validation boundary, not a measured
result.

Required: explicit evidence/backend allowlist, no inferred measured label,
shared measured eligibility checks across both schemas and verified exact
collection source identities. While only a mock staged runner exists, rejecting
all non-synthetic staged evidence is an acceptable safe implementation; retain
measured support as deferred until its contract is implemented/reviewed. Do not
weaken the historical guards or rewrite old source manifests.

## H3 — [P2] Report full collection cost across fitting and validation

`write_validation_evaluation` builds `summary["full_collection"]` exclusively
from `val_records`. Its name and the protocol's total collection-cost definition
include both roles and all three arms. The old combined mode sums the complete
record bank; the split mode now underreports that cost.

Probe on a two-question fixture: actual collection **6 calls / 1,240 generated
tokens**; validation output `full_collection` says **3 calls / 620 tokens**.
Prompt totals likewise omit fitting. Validation-only collection/path metrics
remain useful but must be labeled as such.

Required: obtain total calls, measured generated/prompt tokens from the sealed
complete bank or verified collection aggregates; retain separately named
validation-only totals. Preserve selected-path cost separately. Include unknown
reserved charges separately where applicable, never in measured-token totals.
Test differing fitting/validation costs so the failure cannot hide behind equal
synthetic counts.

## Reproduce and interpretation

```bash
.venv/bin/python audit/gsm8k_collector_repair_review_20261024/additional_probes.py
```

[Additional results](additional_results.json) record all three cases and source
hashes. Every generated/mutated bank is confined to temporary authored fixtures;
previous review artifacts are retained. The 165-test result does not cover these
asserted counterexamples. No extra test-suite repeat is needed until the next
implementation changes.

Stage-separation parity with an actual model backend remains deferred: only
interface/mock implementations exist. Legacy fitting still reads its combined
bank; its selection invariance is not a no-access guarantee. Staged fitting's
new split records are a narrower, real improvement. Dataset JSON/journal/manual
access custody limits should remain explicit in documentation.

Return H1–H3 to the implementation owner and recheck these probes after repairs.
Do not reopen checker C1–C3, open the 48/48 candidate, run model inference or
claim a campaign gate passed from this software work.
