# Staged GSM8K implementation review — 2026-10-24

**Verdict: request changes. Collector and sealed-validation acceptance remain
open.** F1/F2 intent is present and the five validation rows remain, but fresh
counterexamples contradict several completion/accounting/blinding claims.
No production code or protocol changed in this review. No candidate 48/48
content read, model/embedding calls made, bridge reopened or Stage 0 changed.
Checker C1–C3 acceptance is unaffected.

## Verification performed

Fresh regression command:

```bash
.venv/bin/python -m pytest tests/test_gsm8k_collector.py tests/test_gsm8k_routing_baseline.py tests/test_checker_dry_run.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py -q
```

Observed: **152 passed in 9.33s**, exit 0. The passing tests establish their
covered fixture behavior; they do not cover the cases below. Reproduce the
additional authored-fixture probes using:

```bash
.venv/bin/python audit/gsm8k_collector_implementation_review_20261024/probes.py
```

[Probe results](results.json) record current source hashes and the observed
failures. All input/output mutations occur in isolated temporary fixture runs.
No historical evidence or pending candidate is modified.

## G1 — [P1] Validate generation/tool payloads before committing success

`experiments/gsm8k_collector.py:505–544` accepts `StagedExecutionResult` without
validating counts, confidence, text, finish reason or elapsed time. A runner
returning **-100**, **2,048**, or **True** generated tokens produces a run marked
**complete**, storing respectively -100, 2,048 and 1 tokens. The negative count
also credits budget. The mere dataclass annotation is not runtime validation.

Require positive non-bool integer generated counts within the declared cap,
valid prompt counts, finite bounded confidence/nonnegative durations, supported
termination reasons and typed public/tool outputs before the success commit.
Reject invalid payloads while retaining started-attempt conservative accounting;
never fabricate a measured count by casting. Validate configured caps/budgets
and bind dispatch parameters to the pinned identity/settings too. Add matching
live and journal-recovery validation; do not validate only the normal mock.

## G2 — [P1] Restore accounting and resolve partially assembled stages on resume

`_read_journal` increments started calls but charges tokens only for terminal
generation events. A single orphan yields `status=quarantined`, started=1,
**budget_charged_tokens=0**, although a 1,024-token reservation is required.
Quarantine prevents redispatch, but the persisted accounting is still false.

Separately, `run_staged_collection:472` skips every previously dispatched key,
even when its generation outcome is durable but its record is not. A hard stop
just before the first DIRECT record append resumes with no unknown flag,
dispatches the remaining five conditions and returns **running**, with **5/6
records**. Repeating resume cannot finish because the missing condition always
gets skipped. PAL after generation/before tool and after tool/before record has
the same missing stage-recovery policy.

Reconstruct charges from starts plus validated outcomes, and distinguish
never-started, generation-unknown, tool-unknown, recoverable terminal evidence,
known generation failure and assembled records. Rebuild records purely from
sufficient persisted terminal evidence, retaining measured timing/trace. If the
chosen no-reexecution policy cannot complete a stage, explicitly halt with a
reason; never silently return running as if recovery succeeded. Do not rerun
generation or a saved tool to patch missing rows.

## G3 — [P1] Bind validation to the bank and sources committed at sealing

`experiments/gsm8k_routing_baseline.py:309–313` loads the current input manifest
and verifies that bank against its own current checksums. It does **not** compare
the input manifest/artifacts to `input_manifest_sha256` and
`input_artifact_sha256` recorded by the seal. It also does not enforce the
sealed analysis/protocol/atomic-writer source fingerprints.

Probe: seal an authored bank, change validation outcomes consistently, update
the bank's own checksums, then validate with the original sealed selection.
Validation reports **complete** while its output manifest still copies the
**old input-manifest hash**, misattributing the results to the original bank.

Require exact sealed input manifest/artifact identities and analysis/protocol
contract before consuming outcomes, and recheck integrity at commit. Reject a
new self-consistent bank after sealing instead of accepting it as the old bank.
If deliberate new-bank analysis is desired, it is a separately identified
reviewed workflow, not this seal's validation.

## G4 — [P1] Implement outcome-access isolation; poisoning is not an access test

`write_fitting_seal:253` still calls `research_pilot.verify_replay`, which
`json.loads` the **entire** combined `records.json` and dataset before filtering.
Thus the fitting command does load calibration outputs/gold. The pure fitter
does not use those outcomes to select rules, but that is a narrower claim than
the handoff's no-access assertion. Its poisoning test proves invariance, not
that the bytes/fields were never accessed.

The new staged collector also writes a pre-seal aggregate accuracy/report across
both roles (`gsm8k_collector.py:648–667`). No fitting-only bank reader, custodian
procedure or exposure ledger is implemented. Adding separate CLI names does not
establish the proposed boundary.

Create the planned fitting-only outcome view/reader, enumerate and protect all
validation-bearing journals/records/logs and suppress pre-seal aggregate scores.
Keep allowed structural metadata/hash access separate. Test with a reader that
raises upon opening validation payloads, in addition to selection-poisoning
tests. Document manual exposure limits and actual custody rather than claiming
that application code prevents all external file reads.

## G5 — [P2] Connect the new collection contract to the supported analysis path

The staged collector writes its own manifest with `identity`/mode and a different
artifact set. `write_fitting_seal` still accepts only the legacy pilot manifest
and calls `verify_replay`, which requires `pilot=true`, expected top-level
backend/evidence/strategy/source fields and `selection.json`. A completed new
staged run cannot feed that path as written. The CLI tests use `save_run` from
the old routing fixture helper, bypassing the new collector entirely.

Add an explicit source-pinned adapter/schema path and one actual end-to-end
fixture: staged collect -> fit seal -> validate, with all cost/identity/artifact
checks retained. Do not weaken legacy guards or rewrite historical manifests.
There is also only an abstract runner plus `MockStagedRunner`; no real backend
stage adapter exists. Label actual-backend parity as deferred, or implement and
verify the explicit generation/tool seam without claiming it from the mock.
Keep closed bridge acceptance outside this change.

## Additional required integrity checks in the same repair

`_verify_identity_contract` compares a subset of keys, not the promised full
identity; unlisted package/platform/tokenizer/template/seed-derivation fields
can change without rejection. Required identity completeness and dispatch
parameter equality need enforcement, not merely arbitrary dictionaries.

Journal recovery verifies hashes but not the full state/payload schema: unknown
event kinds fall through, condition keys are not consistently matched to their
started attempt, duplicate conditions with distinct attempt IDs are not rejected,
and `record_assembled` is accepted without requiring successful generation and
terminal PAL tool evidence. Add hash-valid malformed-transition probes rather
than only torn bytes/bad-checksum tests. These are part of the claimed fail-closed
contract and must be reviewed before calling the collector accepted.

## Handoff

Return G1–G5 plus the integrity checks to the implementation owner. Retain
F1's separate unknown charge and F2's correct parsing direction; expand tests
to the failure windows above. Fresh passing suites and these new counterexamples
must both be addressed. Do not open candidate data, run inference or treat the
152-test count as completion of the collector review.
