# Codex independent B1 repair review — round 2

Decision: **Request changes; B1 has not been accepted. B2 wiring remains gated.**

Reviewed compiler SHA-256: `8dea28d860d5cb207afb952dfef727628c963442ffc3eaf0d1513aa0d86ab598`.
It matches Anti's repair manifest. No tracked review source changed during this run.
The previous repair packet's `b1_repair_verified_and_accepted` is an implementer
self-status, not Codex acceptance.

The original 15 independent acceptance probes now pass unchanged. Independent
rerun also passed the current 29 B1 tests, 6 context-audit tests and 19
ArtifactStore tests: **69 test executions passed**. Fifteen product regressions
duplicate the earlier independent cases, so 69 is not a count of unique scenarios.
The new suite has **12 failures and 2 passing controls**, without collection errors.
The 292-test core suite was reported by Anti and was not rerun in this review.
All verification is headless software testing; no model calls or quality claims.

## R2-1 [P1] A resolved payload reauthorizes familiar raw keys; validation also treats raw data as graph edges

Locations: `rat/engine/context_snapshot.py:202-210`, `:266-310`.

An unknown plugin returns `{"quote": {"$value_ref": ...}}`, pointing to an
artifact's `/payload/value`. The receipt's outer `operation_result` wrapper is a
legitimate projector link, but its target is a raw plugin body. After resolving
the envelope, the decoder resets `current_path=k`, so the raw `quote` is decoded
to `"RESOLVED_TARGET"`. The same happens for raw `note`, `snapshot` and
`verification_report` keys. All four snapshots validate successfully before the
silent mutation. The trusted outer edge does not grant decoding authority to its
raw descendants.

The validator independently treats a raw plugin `quote` wrapper targeting a
missing artifact as a broken structural ref. Its cycle walker scans every
`$value_ref` in every entity body, even a literal in `artifact.payload.quote`,
and rejects an otherwise valid raw artifact because the literal describes a
self-cycle. Decoder, closure and cycle checking disagree about the authorized
graph and do not know the projector origin.

Six failing cases: four `test_raw_unknown_result_familiar_key_does_not_authorize_decode`
parameters, `test_raw_unknown_result_dangling_literal_ref_is_not_structural_reference`,
and `test_raw_artifact_literal_cycle_is_not_projector_graph_edge`.

Required fix: derive edges from trusted typed projector context, and share that
definition between decoding, pointer validation and cycle checking. Raw payloads
remain opaque, including when their literal wrapper points to an available target.
Key spelling, wrapper shape, value equality, or a resolved parent edge cannot
authorize a raw child. Keep genuine typed cycles and missing refs detectable.

## R2-2 [P1] Four projection paths still fail exact roundtrip

Locations: `rat/engine/context_snapshot.py:565-567`, `:572-592`, `:711`, `:795-802`.

- A note's `quote` equals the source value, but `source_ref.quote` contains a
  different literal. The compiler rewrites both fields to the first value,
  losing the second. Check each field independently before deduplicating.
- `replaces_text` is replaced by the previous revision's `/text` without an
  exact value check. The analogous `replaced_by_text` branch has the same
  unconditional replacement. A link identity alone is not proof of equal text.
- The registered note-result adapter uses Python dictionary equality. Nested
  `confirmed=1` compares equal to `confirmed=True`, so restoration changes an
  integer into a boolean. Equality must preserve JSON types recursively; apply
  it consistently to event and result substitutions as well.
- A receipt `note_event` is replaced with the inline event solely by matching
  `event_id`. A different `kind` and an extra field disappear while validation
  succeeds. Preserve the literal body, or reject an actual canonical conflict;
  do not silently replace it with another body.

Four failing tests: `test_note_and_source_ref_quote_preserve_independent_exact_values`,
`test_replacement_text_is_not_rewritten_without_exact_value_match`,
`test_trusted_note_result_equality_must_distinguish_bool_from_number`, and
`test_receipt_event_same_id_different_body_is_not_silently_replaced`.

## R2-3 [P2] Missing generation becomes current proof eligibility

Location: `rat/engine/context_snapshot.py:674-679`, with header normalization at
`:760-763`.

With boundary generation 0, a verification receipt with matching IDs but native
generation `None` is added to current `proof_refs`. Existing core
`completion._in_execution` requires `receipt.generation == owner.generation`
whenever the owner generation is present. The compiler therefore presents a proof
that core excludes. Its receipt header also fills native generation `None` with
0, obscuring the mismatch; empty native IDs have similar fallback assignments.

Failing test: `test_proof_without_generation_is_not_current_generation_proof`.
Use the existing scope semantics, retain missing/foreign metadata honestly, and
keep excluded material distinguishable from current proof. Do not loosen core
matching to accommodate projection.

## R2-4 [P2] Typed proof refs escape closure validation

Location: `rat/engine/context_snapshot.py:1045-1080`.

Adding `observed_state.proof_refs=[{kind: verification_report, execution_id:
review-exec, receipt_id: missing}]` to an empty snapshot yields `(True, [])`.
This is an explicit typed ref, unlike an opaque history label, and has neither
an inline entity nor an explicit unavailable record.

Failing test: `test_missing_typed_proof_ref_requires_explicit_unavailable`.
Include proof refs in closure, and audit other declared typed-reference surfaces
against the schema and ADR. A present entity still requires the right scope and
authority to be a current proof.

## Passing controls and evidence

An unknown plugin whose raw note body exactly equals a canonical note remains
raw, and entity identity uses the complete typed ref: identical artifact IDs and
revisions in different conversations do not collide. Keep both behaviors.

Evidence is in `provenance_probes.py`, `provenance_probes.log`,
`existing_regressions.log`, `test_run.json`, XML results, and source manifests.
`context_snapshot.py.txt` and `test_rat_context_snapshot.py.txt` freeze reviewed
inputs. `bootstrap_python314.json` records an initial interpreter-only failure
(default Python 3.14 lacks pytest); test results use the project's Python 3.12.

This review changed audit files only. The supplied source and product tests were
not modified. Historical packets remain intact.
