# Independent current B1 acceptance review

Decision: **Request changes; current B1 is not accepted for B2 wiring.**

Reviewed compiler SHA-256: `a0aea01b5ace4d27ea7cad586717f2d6351272b21d5b79c2c6615ec75b1359a9`.
The compiler remained unchanged through both runs. No product files were modified by this review.

The current B1, context-audit and ArtifactStore suites plus the original independent probes and round-2 provenance probes all pass: **92 test executions**. These include repeated product/independent cases and are not 92 unique scenarios. New independent checks produce **3 failures and 2 passing controls**. No live model calls or Qt runs were made.

## R3-1 [P1] A raw wrapper at an operation-result root is still decoded as a trusted link

Locations: `rat/engine/context_snapshot.py:262-279`, called by `:327-335`.

An unknown plugin returns a literal JSON object whose root is `{"$value_ref": ...}`. Compilation creates the normal trusted receipt-to-operation-result link. Validation returns true. Expanding the receipt resolves that trusted outer link, but `_resolve_deref_chain` then follows the literal wrapper at the raw operation-result root. This silently replaces the plugin's dictionary with the referenced string when the target exists. With a missing literal target the snapshot still validates, then expansion raises ValueError.

Both tests exercise the actual compiler, validator and receipt expansion, rather than injecting a malformed snapshot. Raw plugin output remains data even when its entire body has wrapper shape. The typed edge domain must be shared by decoding and validation at every hop; `operation_result` entities are not blanket authority to follow their root value.

Failing cases: both parameters of `test_unknown_result_root_literal_wrapper_stays_literal`. The list-containing-literal control passes.

## R3-2 [P2] A resolving foreign proof reference is accepted as current proof

Location: `rat/engine/context_snapshot.py:1292-1297`.

The compiler correctly excludes an old-turn/old-execution verification receipt from current `proof_refs`. However, inserting its existing typed entity reference into `observed_state.proof_refs` still passes validation. Closure alone is checked, without requiring the referenced receipt/entity to have current conversation/turn/execution/generation and committed proof authority. This is an independently malformed-snapshot validation probe, not a claim that ordinary compilation emits this state.

Failing case: `test_foreign_proof_entity_cannot_be_promoted_to_current_proof_ref`.

## Scope and next step

Keep the unchanged original and round-2 probes and these new probes as independent acceptance checks. Fix typed traversal at the root-result boundary and current-proof scope validation without loosening core `_in_execution`, changing canonical receipt values, or introducing another state store. Then rerun the focused suites and review current source hashes. The compiler's current equality and per-field replacement fixes pass the supplied regression cases; the blockers above are specific remaining origin/scope gaps.

Evidence: `test_run.json`, `existing.log`, `existing.xml`, `origin_scope_probes.py`, `origin_scope_run.json`, `origin_scope.log`, `origin_scope.xml`, and source manifests.
