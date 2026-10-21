# B1 repair handoff — Codex request changes

The B1 review is complete. Fix the source within B1 before B2 wiring. Review and runnable reproductions are in this folder's review.md and review_probes.py. Current result: 20 existing tests passed, 15 new acceptance probes failed; source hashes stayed stable. Preserve the original B1 packet and this failed-review packet.

Repair scope: rat/engine/context_snapshot.py and compiler tests. Preserve the newly fixed ArtifactStore high-water behavior and the existing dispatcher presentation change. Do not change completion matchers, freeze/controller policies, runtime call loop, budgets, registry ordering, UI, defaults, DocAI or research gates to make fixtures pass.

## Required semantics

1. Authorized value-ref locations come from trusted typed projector context. Leaf names quote/note/snapshot at arbitrary depth are insufficient. Proposal, expected_args, operation_args and unknown raw result bodies must remain literal. Do not add a self-authenticating marker inside untrusted payloads.
2. Runtime canonical dict exports retain their validity/errors/frozen/source metadata. Obligations and progress must use the same accepted representation; do not reclassify invalid exports as valid model proposals. Keep invalid declared contracts unresolved and mandatory export/binding failures explicit.
3. Roundtrip values must match their canonical source exactly, including JSON types and whitespace. A scalar/list result may use an internal envelope but must dereference the original inner value. Unknown note-shaped plugin output stays raw. Optional ref compression is unnecessary when exact reconstruction/provenance is unavailable.
4. Validate structural typed ref closure, duplicates/conflicting bodies, namespace/scope and dereference cycles. Explicit unavailable refs remain allowed under the design. Old history labels and raw fake wrappers are not graph edges. Decoder failures must be explicit/bounded.
5. Current receipts/proofs must have current scope, or the mandatory input must be rejected; foreign history must not be relabeled current. Preserve native identity rather than filling foreign/missing scope with boundary identity.
6. Artifact canonical metadata, including status/provenance/timestamp, stays inline; derive projection labels separately. Preserve full note revision text and existing raw event/result/receipt data through exact expansion.

Codex has decided the semantics above. Routine API mechanics may be selected within B1; if trusted projector-root information requires a new compiler/decoder input, make it explicit and explain it in the repair handoff. Do not invent a new store or trusted flag in raw JSON. Preserve the rat.context/1 public transport shape unless a concrete schema discrepancy is reported for review.

## Validation

- Add meaningful regressions to product tests using the review probes' original invariants. Do not remove failed cases, downgrade literal equality to str/strip equality or alter raw fixture values to accommodate data loss.
- Run tests/test_rat_context_snapshot.py, tests/test_rat_context_audit.py and this folder's review_probes.py, then the new tests/test_artifact_store_lifecycle.py and exact core regression argv from audit/rat_core_reconciliation_fix_20261013/test_run.json.
- Use PYTHONDONTWRITEBYTECODE=1 and -p no:cacheprovider. Execute stored argv as a list, not shell eval. No live model, personal-file indexing or new dependencies.
- Save a fresh repair folder with raw commands/results, source hashes start/end, exact before/after canonical roundtrips, raw fallback cases, source diff and handoff_codex.md. Record actual counts; passing old fixtures alone is insufficient.
- Preserve authored design fixtures and historical hashes. If decoder tests need explicit trusted projector plans, provide fixture-specific plans without overwriting the old design packets or weakening authority/losslessness assertions.

Return the B1 repair packet to Codex review before starting B2. The review does not establish measured model quality, token savings, latency or a Stage 0 change. Do not git push/pull/reset/force.
