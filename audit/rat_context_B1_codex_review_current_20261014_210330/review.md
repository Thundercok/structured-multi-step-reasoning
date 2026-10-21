# Codex review of current B1 source and attached Anti packet

Decision: **Request changes. B1 is not accepted.** Runtime wiring is present in
the current checkout; it is not accepted by this review either.

This review covers compiler hash
`5ec3442d3cd1c0f2ee2f52747ffff02ee5992313bd538dce3f93b7f08ebceb14`.
The attached Anti packet covers an earlier source state. Subsequent origin/scope
repairs and runtime changes already exist locally; their author/authorization
is not inferred from that packet. No production source was modified here.

The monitored compiler, runtime, copier, core, schema and probe sources stayed
unchanged between this review's start and finish hashes. Earlier exploratory
reads happened before that frozen boundary and are not the test baseline.

After tests completed, the shared checkout's runtime changed again, from tested
hash `725a2cbe0efc9ae32112e60106d689ea90cd9a3097f876ef0816067bb6fb74e5` to
`055a518ff5317a27f81e72861c30e4553b5760c5044c1c9fa3cbe1b455d5e584` when observed.
The compiler remained unchanged. Core counts below apply to the frozen tested
runtime, not a new acceptance claim for that later runtime. See
`manifest_at_report.json` and `runtime_changed_after_tests.patch`.

## Independent results

| Check | Pass | Fail | Collection errors |
| --- | ---: | ---: | ---: |
| Current product B1/context-audit/ArtifactStore plus all three earlier independent probe suites | 120 | 0 | 0 |
| New raw receipt-origin probes | 1 | 7 | 0 |
| Exact recorded core regression command | 286 | 6 | 0 |

Counts are test executions, including duplicated product/independent cases.
These are synthetic, headless software checks with no live model calls. The
earlier `384/384` statement is not evidence for the current runtime source.

## R4-1 [P1] Unprojected raw receipt values are still interpreted as emitted projector links

Locations: `rat/engine/context_snapshot.py:215-221`, `:335-352`,
`:991-1011`, `:1022-1025`, `:1038-1039`.

The shared edge extractor checks whether a receipt slot has wrapper shape, but
does not establish whether the compiler emitted that wrapper. Three paths copy
a native raw value straight into a receipt slot:

- An operation result with artifact pins, when its literal value does not equal
  the pinned payload and therefore no payload-link substitution occurs.
- A raw note-event value without a resolvable matching canonical event.
- A raw verification-report value from a non-verification issuer.

If that raw value is `{"$value_ref": ...}`, `iter_projector_edges` treats it as a
trusted edge. `_expand_receipt` independently follows it on wrapper shape as
well. For each of the three slots, an available target silently changes the raw
dictionary into `"RAW_MUST_STAY_LITERAL"`; a missing literal target rejects the
otherwise legitimate raw data as a broken structural ref. These six cases use
the public journal/compiler path and do not mutate a compiled snapshot.

A seventh test makes the literal use **the exact target kind, pinned artifact ID,
revision and `/payload` pointer that the real projector emits**. Validation
passes, then restoration replaces the literal with a different native payload.
Checking only target type, pointer shape or membership in artifact pins is
therefore insufficient.

The positive control proves the genuine receipt-to-artifact link still restores
a raw payload containing a literal wrapper, without decoding that descendant.
Keep this behavior while fixing the unprojected receipt paths.

Required behavior: decoding, pointer validation and cycle checks must use links
actually emitted by the typed projector. A copied native wrapper remains raw
regardless of slot name or whether it has the same shape as a real link. Use an
explicit origin representation/plan or a safe envelope for raw values; do not
substitute another key-name/target-shape whitelist. Preserve `rat.context/1`,
exact values/types, canonical data and current/historical authority.

Evidence: `raw_receipt_probes.py`, `raw_receipt_probes.log`, its XML result and
`test_run.json`. The initial six-case version and its output are retained too.

## Current runtime compatibility failures — separate from the Anti B1 attribution

Locations: `rat/engine/assistant_runtime.py:795-801`, `:1026-1061`.

The current native planning schema exposes only `operations` and `respond`.
It no longer exposes the typed `outcomes` declaration and `expected_args` fields
required by the existing contract regressions. The exact core command now fails:

- `test_native_planner_schema_can_express_outcomes`
- `test_native_planner_outcomes_are_not_rejected_as_task_state` (`StopIteration`)
- `test_planner_schema_advertises_typed_expected_args`
- Three planner-ingress cases of
  `test_malformed_nested_fields_are_invalid_at_all_contract_ingress`
  (`intent_coverage` becomes `unchecked`, where `invalid` is expected).

These are deterministic compatibility failures in this checkout. They are not
attributed to the attached B1 repair, whose packet says runtime was untouched.
Do not erase other work or weaken old assertions to make the result green. A
deliberate planner protocol change needs its own explicit semantic decision and
validation; otherwise preserve the established typed contract surface.

Evidence: `core.log`, `core_run.json`, `core.xml`, frozen runtime source and
source manifests. This review did not execute real inference.

## B2 preparation requires correction before it can guide implementation

The attached `b2_preparation.md` is documentation for an earlier runtime state.
Its retry proposal prunes unavailable refs and then uses a minimal fallback view;
the agreed spec permits recopying a changed boundary, not dropping mandatory
obligations. Its "pre/copies/post" section does not actually compare all three
vectors. It also describes a single physical model call while the current
runtime has a separate native planner invocation.

The current `runtime_context.py` already has a recopy loop without that minimal
fallback, so the bad fallback is a **documentation defect**, not a claim that
the current code executes it. Refresh documentation against current source and
the approved decisions. A full B2 acceptance review remains separate; passing
the B1 tests does not validate wiring, cancellation, budgets or native messages.

All review output is additive audit material. Historical packets and existing
product edits have been preserved.
