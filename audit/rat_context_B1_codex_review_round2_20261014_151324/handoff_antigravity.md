# Anti: complete B1 by closing the invariant classes in one implementation turn

The user wants this next turn to use your implementation capacity fully. Carry
this bounded package through code, adversarial tests, independent self-review,
and a reproducible handoff. Make routine implementation decisions yourself;
report a concrete spec conflict with a reproducer if one blocks completion.

Work in `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
`~/github/nesy-docai` currently resolves here. Read applicable AGENTS.md first.
Keep research/DocAI/UI outside this package. Do not git push/pull/reset/force.

## Current acceptance state and inputs

B1 is **not accepted**. Codex independently reran the unchanged 15 old probes
plus current B1/context-audit/ArtifactStore suites: 69 executions pass. The new
provenance suite has 12 failures and 2 passing controls. Compiler hash is
`8dea28d860d5cb207afb952dfef727628c963442ffc3eaf0d1513aa0d86ab598`, matching your
repair packet. All monitored source hashes stayed stable during review.

Read these local files yourself; use the actual APIs rather than examples from
chatbox reasoning or earlier failed shell attempts:

- `audit/rat_context_B1_codex_review_round2_20261014_151324/review.md`
- `audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py`
- `audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.log`
- `audit/rat_context_B_assignment_20261014/decisions.md` and `snapshot.schema.json`
- `docs/adr-004-rat-context-snapshot.md`
- `work/argon-b1-clarifications-20261014/antigravity_addendum.md`
- `rat/engine/context_snapshot.py`, `rat/engine/completion.py`, canonical notebook
  and Artifact/Receipt export APIs, and existing product tests.

Preserve historical audit packets, fixtures/schema, and both independent probe
files. Do not weaken assertions, skip failing tests, or report yourself accepted.
Use a fresh packet with status `ready_for_codex_review`; Codex decides acceptance.

## Deliverable 1 — one coherent projector/validator/decoder boundary

Replace the remaining name/shape-based authorization with trusted typed origin.
The current reset to `current_path=k` after resolving an outer operation-result
link reauthorizes raw plugin descendants. The current cycle walker follows every
wrapper in raw entity bodies. Both must be fixed by the same edge definition.

Design and implement a small explicit projector context/plan or equivalent
mechanical adapter. It must distinguish:

1. Links emitted by known typed projectors in a known entity/header/root.
2. Raw artifact payloads, unknown plugin results, source values and optional
   unmodeled data, even when they contain identical wrappers or familiar keys.
3. Proposal state, native operation arguments and contract expected values,
   which remain literal.

A trusted parent does not grant trust to its raw descendants. Equality does not
establish origin. Do not authorize by an arbitrary `source_ref` dictionary,
user-controlled labels, or same field name at a plausible path. If the decoding
helper needs explicit typed root/context, make that explicit and update real
call sites while preserving required fixture behavior and `rat.context/1`.
Compression is optional: keeping an unproven duplicate inline is acceptable.
Do not add a context store, registry/controller overhaul, or a matcher.

Pointer closure, resolution and cycle checks must traverse exactly this typed
graph. Real missing/cyclic typed refs still fail. Literal dangling refs and
literal cycles in raw JSON remain data. Include explicit unavailable records
under the existing semantics; an unavailable body must not fabricate a value.

## Deliverable 2 — exact lossless projection on every adapter path

Implement a shared recursive exact-value comparison where substitution requires
it. Distinguish bool from number, preserve nested JSON types, list order, full
key sets and every character of strings. Do not coerce, trim, paraphrase, or
match only IDs. Keep provenance checks separate from equality.

Audit every substitution branch, including note quote, source_ref.quote,
replacement links in both directions, event snapshot, result.note,
result.note_event, receipt.note_event and verification/result envelopes.
Check `quote` and `source_ref.quote` independently; do not create a missing field
or overwrite a differing literal. Only use version-link pointers after proving
the target text matches. Apply strict equality to nested adapter bodies; Python
dict equality permits `True == 1`. A same-ID/different-body conflict must stay
literal where optional, or produce an honest validation failure where canonical;
it must never silently change the body.

Preserve native metadata, statuses, timestamps, types and exact values. Keep all
needed current/historical note text inline. Keep scalar/list/null operation
results exact, with no invented artifact identity. An unknown plugin remains
raw even when its body equals a canonical note.

## Deliverable 3 — complete typed closure and current proof eligibility

Align current proof scope with existing core `_in_execution` semantics, including
conversation, turn, execution and generation. With a known boundary generation,
receipt generation `None` is not a current proof. Do not fill native missing IDs
or generation to make them appear current. Keep old/foreign observations clearly
outside current effect/proof eligibility. Do not change core matchers.

Validate closure of `observed_state.proof_refs` as well as indexes, pins and
confirmed constraints. Audit all declared typed-reference surfaces for closure,
scope, authority and identity; keep opaque historical receipt labels and literal
contract/source dictionaries separate from transport links. Full identity keys
include kind and conversation/execution scope; retain the passing control for
same ID/revision in different conversations.

Keep provisional progress from the existing joint reconciler: valid/nonempty/
eligible contract only, response pending, global match evidence, no fabricated
outcome-to-receipt map or terminal lifecycle conclusion. Preserve canonical
invalid flags/errors, distinct epochs and selection_set.

## Deliverable 4 — tests that challenge the invariant classes

First run the two immutable independent probe files unchanged against your fix.
Then add meaningful product regressions and a small reproducible adversarial
matrix covering each invariant class. Do not stop when the supplied probes pass.

- Raw wrappers at familiar keys and nested/list positions, available and missing
  targets, literal self/indirect cycles, known typed wrappers and real typed
  cycles. Exercise validation and actual receipt/entity restoration together.
- Exact roundtrip across supported JSON values/types, nested bool/number
  differences, key-set differences, whitespace, independent source quotes,
  replacements, event/result bodies and escaped pointer tokens.
- Scope mismatches one dimension at a time, missing generation, committed vs
  rejected proof, missing/explicit-unavailable typed refs, same full identity
  with conflicting bodies, and distinct scoped identities with the same ID.
- Existing invalid-contract and provisional progress behavior, and input
  immutability across compile/validate/expand calls.

Use deterministic differential roundtrip checks against the canonical input,
with recursive type-aware comparison; avoid assertions that simply repeat the
implementation. Reuse existing dependencies. Positive controls must show that
valid projector links still work and raw literals still survive. Keep generated
fixtures synthetic and do not call live models.

Validation interpreter:
`/Library/Frameworks/Python.framework/Versions/3.12/bin/python3`.
Default Homebrew Python 3.14 does not have pytest. Use
`PYTHONDONTWRITEBYTECODE=1` and `-p no:cacheprovider`.

Required focused files:

```
tests/test_rat_context_snapshot.py
tests/test_rat_context_audit.py
tests/test_artifact_store_lifecycle.py
audit/rat_context_B1_codex_review_20261014_123157/review_probes.py
audit/rat_context_B1_codex_review_round2_20261014_151324/provenance_probes.py
```

Run the exact core-regression argv recorded in
`audit/rat_core_reconciliation_fix_20261013/test_run.json` after the repair.
Report actual counts; product copies of independent cases are repeated test
executions, not new independent evidence. Investigate a failure to completion
within scope; preserve the failing output if an external blocker remains.

## Deliverable 5 — reproducible review packet and B2 preparation

Create a fresh timestamped audit folder. Include:

- Before/after source hashes covering every touched source, protected core/runtime
  files, schema/fixtures and immutable probe files; report any drift precisely.
- A diff against the source state at the start of this turn, separate from
  pre-existing changes in this shared checkout.
- A checked-in runnable verification script, exact argv/interpreter, stdout,
  stderr, exit status and durations. Do not merely write `exact_match: true`
  into JSON without generating it from executed assertions.
- Source-to-projected-to-restored examples generated by that script, with exact
  type/value and provenance checks, including the new formerly failing cases.
- A finding-to-change-to-test table, your independent self-review, and remaining
  limitations. Keep `ready_for_codex_review` as the status.

Once B1 is fixed and required tests pass, use the rest of this turn to prepare
**B2 documentation only**: map every actual model-call boundary in the current
runtime to its fresh copied inputs, the pre/copies/post vector, maximal 2 retries,
failure paths, native assistant/tool message constraints and validation cases.
Identify concrete call sites and changes needed; do not wire runtime yet.
This preparation must use current source and preserve budgets, cancel/reset,
pending input, contract freeze, queued tools, finish-only and injected fixture
protocols. Avoid a new repair/controller loop or a cross-store transaction claim.

B1 acceptance by Codex is still required before B2 implementation. Do not consume
this turn on UI, DocAI, learned policies, research-model runs or broad refactoring.
Complete the package and return a concise handoff with file paths and actual
validation results, without needing another prompt for routine steps.
