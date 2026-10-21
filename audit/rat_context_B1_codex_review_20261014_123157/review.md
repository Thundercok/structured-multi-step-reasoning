# Codex review — RAT context projection B1

Verdict: **Request changes before B2 wiring.** Reviewed the actual compiler, tests, schema and B1 packet. This is a source/software review, not a model-quality or latency evaluation.

## Validation

Executed the 14 supplied B1 tests, 6 existing context audit tests and 15 independently specified acceptance probes. Result: **20 passed, 15 failed**, pytest exit 1. All failures are in the new probes; all existing tests still pass. Source hashes were stable during the run and still matched at packaging. The raw command/output is in test_run.json/tests.log; reproducible cases are in review_probes.py.

The earlier ArtifactStore patch has its own successful 19 focused / 292 core regression packet. No product source was edited by this B1 review.

## Findings

### 1. [P1] Field names authorize decoding inside raw data and literal contract arguments

Source: rat/engine/context_snapshot.py:183, expand_value_refs.

`active_slot` falls back to the local key name at every nesting level. A raw `proposal.state.nested.quote` or `contract.outcomes[].expected_args.nested.quote` therefore becomes a recognized slot solely because its key is quote. Both probes replace a literal wrapper dict with the target string RESOLVED_TARGET. This violates the requirement that expected values and raw user/model data stay literal; matching a field name is not projector provenance.

Fix: track exact projector-authorized locations in trusted structural context, not leaf-name matching or flags copied from raw bodies. Unknown/unmodeled payloads remain raw even when they contain familiar keys. If the current decoder API cannot know its trusted projection root/plan, make that information explicit rather than treating every nested quote/note/snapshot as authorized.

### 2. [P1] Re-parsing a canonical contract dict can discard runtime invalidity

Source: rat/engine/context_snapshot.py:273, _compute_provisional_progress.

The supported dict input is parsed through TurnContract.from_dict, the parser used for model proposals. It recomputes flags rather than preserving canonical is_valid/validation_errors. A canonical export with is_valid=false and runtime_binding_error stays invalid in runtime_obligations but its effect becomes met in progress when a matching receipt exists. Object input and dict input consequently have different semantics.

Fix: preserve canonical runtime validity/errors/frozen metadata for copied exports and validate structure without silently promoting the contract. Use the same accepted canonical representation for obligations and assessment. Malformed mandatory inputs must produce an explicit build error; declared invalid contracts must remain visible and unresolved. Do not change core proposal parsing or matching policy to hide this mismatch.

### 3. [P1] Claimed lossless projections change JSON values and overwrite unknown payloads

Sources: rat/engine/context_snapshot.py:483, :612, :629 and receipt operation_result pointer generation.

- Integer/list/bool/string no-artifact results expand to an extra `{result: ...}` object because their envelope is wrapped but the receipt pointer targets the whole object. All four type-preservation probes fail.
- An unknown plugin result containing note.id/revision is replaced by the canonical notebook body purely by shape/identity. The original text and plugin_field disappear.
- A quote string "42" becomes integer 42. A quote "source text" becomes " source text ". str conversion and strip equality do not establish exact value/type equality.

Fix: a scalar envelope can remain transport-compatible, but its receipt pointer must recover the original value/type. Keep unknown operation results raw unless a registered trusted projector permits a substitution and complete reconstruction is exact. Substitute quote/source_ref.quote/replacement/event fields only when the referenced canonical value is exactly equal, including type and whitespace; otherwise preserve literal fields independently.

The currently named lossless reconstruction test mostly expands an authored design fixture. It does not run compiler outputs through roundtrip comparisons with all original canonical inputs, so it misses these defects. Add generated-output roundtrip cases rather than changing raw input expectations.

### 4. [P1] Semantic validation accepts missing refs, conflicting duplicate identities and cycles

Sources: rat/engine/context_snapshot.py:196 and :918.

The semantic validator checks one-level value-ref targets/pointers but not the full typed ref domain or dereference graph. It accepts:

- A selected_results typed artifact ref with no inline entity or explicit unavailable entry.
- Two artifact entities with identical typed identity/revision and conflicting bodies; find_entity just returns the first.
- A schema-valid cycle between quote and source_ref.quote projection pointers.

These probes deliberately provide malformed snapshots to the validation API; they do not claim every normal compile call currently creates these states. They prove validate_context_snapshot is insufficient as the B2 acceptance gate advertised in the handoff.

Fix: validate typed refs at known structural positions, exact identity uniqueness/conflicts, namespace/scope/pointer closure and the actual dereference graph. Accept explicit unavailable refs according to the design. Cycle checking must follow projector refs, not arbitrary strings/history labels or literal fake wrappers. Expansion also needs bounded/explicit cycle failure so malformed inputs never recurse indefinitely.

### 5. [P2] Foreign verification receipts are exported as current proofs

Source: rat/engine/context_snapshot.py:634, _build_journal_entities_and_receipts.

A foreign conversation/execution/generation verification receipt in the supplied journal is added to current observed_state.proof_refs and passes semantic validation. Core reconciliation correctly excludes it, but the projected current-proof view still presents it as scoped_verification_proof. The negative case is relevant to the required stale-proof/scope guard; it is not evidence of a production race.

Fix: reject inconsistent mandatory journal scope or filter current receipts/proofs using the existing scope semantics. Old proofs belong only to explicit history/source views. Do not fill empty foreign identities with the current boundary to make checks pass.

### 6. [P2] Artifact metadata is dropped while labeled lossless

Source: rat/engine/context_snapshot.py:383, _build_artifact_entities.

The body is rebuilt from selected fields and omits canonical status, provenance and created_at. A waiting_input artifact therefore loses its status and source lineage while projection_status says lossless. Derived authority/owner labels are not a replacement for the canonical provenance fields.

Fix: preserve canonical exported metadata in the entity body, adding derived projection information separately. If an adapter is not lossless, keep its raw fallback and mark it accurately. Scope normalization must not fabricate native identity.

## What is already aligned

The implementation is headless, keeps the schema's separate epochs and selection_set flag, uses the existing joint reconciler, keeps global matched evidence and response pending, and does not wire the runtime loop. The supplied tests confirm useful happy paths. The findings above concern acceptance gaps, not a reason to redesign the controller.

## Next step

Fix B1 within context_snapshot.py and meaningful compiler tests, replay the unchanged probes into a fresh validation folder, then review the repaired packet. B2 remains after B1 acceptance. Runtime/native protocol/UI/model defaults and research gates stay outside this repair scope.
