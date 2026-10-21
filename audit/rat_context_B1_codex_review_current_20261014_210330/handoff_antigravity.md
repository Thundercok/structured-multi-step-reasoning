# Anti: close receipt origin completely, then reconcile the current source handoff

Continue autonomously through implementation, meaningful tests and a reproducible
handoff. Codex has reviewed the **current** checkout rather than assuming your
earlier packet is still the whole source state.

Repository: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Read applicable AGENTS.md. Preserve research, DocAI and UI boundaries and all
shared working-tree edits. No git push/pull/reset/force. No real model calls.

Read this folder's `review.md`, `raw_receipt_probes.py`, `raw_receipt_probes.log`,
`core.log`, `core_run.json` and `manifest_start.json`. Read the existing Package B
decisions/ADR and earlier immutable probes. Compiler baseline SHA-256 is
`5ec3442d3cd1c0f2ee2f52747ffff02ee5992313bd538dce3f93b7f08ebceb14`.
The source now includes additional B1 fixes and runtime wiring. Do not overwrite
them with your older packet or claim the runtime is untouched.
Runtime also changed after Codex's test run; the 6 core failures are tied to the
frozen tested hash in `review.md`. Inspect `manifest_at_report.json` and the
post-test runtime diff, and rerun against your actual start source. Do not
attribute the frozen results to an untested later hash or overwrite concurrent work.

## 1. Implement the remaining B1 invariant, not seven case-specific patches

Current result: 120 existing test executions pass; new raw receipt probes have
7 failures and 1 passing control. The defect is one class: wrapper shape in an
unprojected native receipt slot is still treated as proof of projector origin.

Fix the graph boundary for copied raw operation_result (including pinned
artifact results), note_event and non-verifier verification_report values.
Do not decode a raw wrapper simply because it is at a legitimate receipt slot.
The seventh test uses the same artifact pin and `/payload` pointer as a genuine
projector link: target/shape whitelists alone cannot solve it.

Use a small explicit emitted-edge context/plan or safe raw-value envelope,
consistent with the approved transport and existing APIs. Decoder, closure,
cycle checks and receipt expansion must consult the same origin definition.
Unknown/optional raw values retain exact shape, types and contents. A genuine
projector link must still restore a payload containing a literal wrapper; the
passing control is mandatory. Keep canonical source payloads untouched.

Apply the solution to the complete adapter surface, including registered result
adapters and literal data in supported typed roots. Do not guess origin from
value equality, operation/issuer strings alone, full target shape, or slot names.
Do not invent an additional runtime truth store. Avoid unnecessary compression
where origin or exact equivalence cannot be proved.

## 2. Independently challenge the repair

Preserve all four independent probe files unchanged. Add product regressions for
the newly exposed paths and meaningful boundary controls. Exercise available,
missing and self-referencing literals; pinned/unpinned results; genuine projector
links; nested raw payloads; exact bool/number/string/list/null values; and decoding
after a JSON serialization roundtrip with an explicit trusted root/context.
Compare restored native values recursively by exact type/value, not only dict
equality or a fabricated `exact_match: true` flag. Keep input immutability.

Required focused suites:

```
tests/test_rat_context_snapshot.py
tests/test_rat_context_audit.py
tests/test_artifact_store_lifecycle.py
audit/rat_context_B1_codex_review_20261014_123157/review_probes.py
audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py
audit/rat_context_B1_independent_20261014_084657/origin_scope_probes.py
audit/rat_context_B1_codex_review_current_20261014_210330/raw_receipt_probes.py
```

Use `/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`,
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`. Run the exact core command
recorded in this folder's `core_run.json` and report actual results.

## 3. Triage the separate current planner compatibility failures

The current core result is **286 pass, 6 fail**, all in native planner/contract
ingress checks. Current schema uses `operations/respond`; regressions require
typed `outcomes`, including expected_args, and correct invalid ingress status.
This change is outside the attached B1 patch. Identify its current implementation
and concrete behavior with a source-to-test table. Preserve other contributors'
work and old assertions.

Do not silently roll back the planner, loosen core validation, or migrate the
tests to bless a protocol change. If that change has already been explicitly
authorized in your user session, include that decision and its compatibility
plan/evidence. Otherwise report this as a separate semantic decision needed from
Codex, with minimal reproductions. You can complete B1 without guessing that
decision. No planner/controller/registry policy expansion belongs in this repair.

## 4. Refresh the B2 preparation document against actual source

The earlier B2 document has stale call sites and an incorrect sanitization/minimal
fallback proposal. Replace the proposal in a **new** handoff document:

- Map the actual planner, actor, repair and finish model boundaries in current
  code. Include injected fixtures and queued calls that are not new boundaries.
- Specify `pre_vector == copied_vector == post_vector`, initial attempt plus at
  most two recopies. Include full current contract binding, journal scope/content,
  independent store epochs, active revisions/membership, selection IDs plus flag,
  event cursor, pending input and execution/cancel state as applicable.
- Recopies address incoherence. Do not prune mandatory context, omit obligations,
  or invent a minimal fallback after a validation/export failure. Report
  `context_build_failed` honestly and retain committed effects.
- Preserve native assistant/tool call IDs, ordering, budgets, repair limits,
  contract freeze and pending-input behavior. No new repair/controller loop.

Runtime wiring already exists locally. Treat it as separate existing work, not
as formally accepted B2. Do not add more wiring or redesign it during this B1
repair; report discrepancies with the agreed spec for the next review.

## 5. Finish with a reproducible packet

Create a new timestamped audit folder; leave all old packets intact. Freeze the
actual start source, compare against it rather than Git HEAD or an old packet,
and hash protected compiler/core/runtime/copier/schema/probe files before and
after testing. Report any concurrent drift separately from your intentional edits.

Include a runnable verifier, exact commands/interpreter, stdout/stderr/exit codes,
diff, asserted native-to-projected-to-restored examples, finding/test mapping,
an independent self-review and limitations. Status is `ready_for_codex_review`.
Distinguish B1 results from the unresolved planner compatibility and unreviewed
B2 work. Passing copied tests is repeated execution, not independent new evidence.

Return the complete package without requesting another prompt for routine steps.
Codex acceptance of B1 is still pending.
