# B1 acceptance review — 2026-10-15

Decision: **Request changes: one remaining compiler origin defect.**
The previous top-level raw-receipt defect is fixed by `projected_slots`.

Reviewed compiler: `37259475b6a861b483ecc37f35460844cae0e3daf1ad13f1875170fbfd952c28`,
matching Anti's latest packet. Monitored sources stayed stable during testing.
This review added audit/probe files only and made no model calls.

After testing, `assistant_runtime.py` changed again in the shared checkout. Core
results below apply to tested runtime hash
`ddf898f3c6544082df8d99191ab99e6fcc9476e12640283eac00b20c30ab83d9`.
The compiler remained unchanged. See `manifest_at_report.json`; this review does
not claim to have tested the later runtime hash.

## Results independently reproduced

| Suite | Passed | Failed | Collection errors |
| --- | ---: | ---: | ---: |
| Existing focused suites, including every earlier independent probe | 151 | 0 | 0 |
| New registered-result probes | 1 | 4 | 0 |
| Recorded core command against current checkout | 286 | 7 | 0 |

The existing focused count consists of 84 product context-snapshot cases,
6 context-audit cases, 19 ArtifactStore cases, and 15/14/5/8 independent probe
executions. The total 151 in Anti's prose is correct, but its per-file counts
(88/10/15 and 30 older probes) do not match the actual JUnit results. These are
test executions, including duplicated scenarios, not model-quality evidence.

## R5-1 [P1] Registered operation names still authorize raw children not emitted by a projector

Locations in reviewed source: `rat/engine/context_snapshot.py:257-269`,
`:327-344`, and the result-note substitution branches at `:943-970`.

An exported journal receipt for `record_work_note` contains a result such as:

```json
{"note": {"$value_ref": {"entity_ref": {"kind": "note_version", "conversation_id": "review-conv", "note_id": "n1", "revision": 1}, "pointer": ""}}}
```

The compiler leaves that child literal unchanged: it has no canonical note
`id`/`revision` for an exact-body substitution. Nevertheless,
`iter_projector_edges` and `_expand_operation_result_body` interpret it as a
projector link simply because the owner operation is named `record_work_note`.
The new receipt-level `projected_slots` only authorizes the **outer** result
link and does not record whether either inner field was substituted.

With the inline note present, validation succeeds and receipt expansion silently
replaces the literal wrapper with the canonical note. With the target absent,
validation rejects a literal as a broken structural link. The `note_event`
child has the same behavior. All four probes go through public journal record,
compile, validation and receipt expansion APIs; they do not mutate the snapshot.

The references deliberately use the exact kinds and empty pointer used by real
note/event adapters. A kind/pointer whitelist is not an origin proof. A registered
operation identifies an adapter; it does not prove that this invocation emitted
a particular wrapper. The compiler's deliberate raw-copy path must stay raw.

The positive control confirms that canonical note/event result bodies still
roundtrip correctly. Keep that and all earlier probe suites green.

Required change: extend explicit emitted-edge provenance to result subslots and
use it consistently in edge enumeration, dereference chains and all expansion
entry points. Only record slots actually rewritten after canonical identity and
exact-value checks. A trusted parent must not grant blanket authority to raw
descendants. Keep raw output, source stores, schema version and native argument/
contract values unchanged. Compression remains optional where it cannot be proved.

Evidence: `registered_result_probes.py`, `registered_result.log`,
`registered_result.xml`, `test_run.json` and frozen source copies.

## Separate current runtime/core state

The exact previously recorded core command now collects 293 cases. It has the
same six native planner/typed-contract compatibility failures as the last review,
plus `tests/test_work_context.py::test_dsa_six_turn_shared_conversation_core_contract`.
That additional assertion expects the cancelled-turn status in the last history
message, but the observed content is the query text. This reports an existing
regression failure, not a proven claim that every current model request loses
cancel information; that behavior requires its own runtime investigation.

Native schema still exposes `operations/respond`; old regressions require typed
`outcomes`/`expected_args` and invalid ingress metadata. These results are separate
from the B1 compiler repair. Keep the agreed scope: no matcher/planner redesign
or weakened assertions merely to turn this review green. The current runtime
hash and full output are recorded for the semantic compatibility decision.

## B2 document still overstates the copy check

The updated B2 document calls a second live `boundary()` sample the
`copied_vector`. That is not a vector derived from the captured bundle. In current
`runtime_context.py`, both `after` and the final check read live state. The document
must not claim `pre_vector == copied_vector == post_vector` has been implemented
by renaming three live samples. Full contract binding and copied content checks
remain a separate B2 acceptance item under the existing decisions.

All source manifests are available. No production files were modified by this
review, and no research inference experiment was run.
