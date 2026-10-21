# Artifact revision high-water mark — completed patch

The old store allowed a deleted or evicted ID to reappear with its previous revision in the same generation. That could make an old `(id, revision)` reference resolve to a different body and allow an old guarded write to target the replacement.

`ArtifactStore` now retains each ID's highest committed revision across deletion and eviction. Recreate must use a higher revision. `clear()` advances the generation and resets the ledger. `next_revision()` supplies a suggestion without reserving it; `put()` validates and commits under the existing RLock.

Validation order stays expected_generation → expected_revision against the active target → high-water revision check. Rejected writes do not evict live artifacts or advance the ledger. All fallible copies also complete before eviction or publication. `_waiting` uses the same captured generation for both revision allocation and put, so a reset between them rejects the old write.

## Changes

- `rat/kernel/contracts.py`: retained revision ledger, next_revision getter, strict publication guard and reset behavior.
- `rat/kernel/dispatcher.py`: `_waiting` obtains the next committed revision with its existing generation guard. The unrelated presentation change already present in the working tree is preserved.
- `tests/test_artifact_store_lifecycle.py`: 19 meaningful cases covering recreate/aliasing, late writes before and after replacement, error precedence, failed-put eviction/ledger safety, copy failure, capacity eviction, reset, allocation collisions, default and explicit InputRequest IDs, waiting eviction, reset between allocation and commit, old actions and bounded history.

`source_changes.diff` compares against the captured pre-edit files and includes the new test file. `existing_scoped_changes.diff` records the pre-existing dispatcher change separately. Source snapshots are under before/after; `.txt` suffixes for after snapshots avoid accidental pytest collection.

## Validation

- Focused lifecycle suite: **19 passed**, pytest exit 0; raw log in focused_tests.log.
- Exact core regression argv from the historical test_run.json: **292 passed**, pytest exit 0; raw log and hashes in core_regression.log/core_regression_run.json.
- All tracked validation source hashes were stable across the core run and still matched at packaging.
- Scoped git diff --check: exit 0.
- PYTHONDONTWRITEBYTECODE=1 and no cacheprovider. These are software tests, not model-quality, latency or Stage 0 evidence.

## Limits

The invariant applies to committed artifact revisions within a generation and versioned references/conditional writes. It does not establish an atomic multi-store context snapshot. ID-only lookup still selects the current entity; callers needing an exact version must retain revision and the runtime's conversation/generation binding.

The ledger uses O(distinct committed IDs in the generation) memory and is not pruned by capacity eviction. Custom handlers returning explicit Artifact IDs must request a higher revision or choose a fresh ID; put does not silently renumber their output. Concurrent revision suggestions may collide, with one commit accepted and the other rejected through the existing error flow.

This patch is ready for review. Context B1/B2 acceptance remains a separate review.
