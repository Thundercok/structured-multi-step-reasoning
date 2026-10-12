# Index integrity before relevance tuning

RAT must return a ranked list of relevant files, not one preselected filename.
The user has not confirmed a previous successful retrieval, so there is no
known-good quality baseline. Fix index correctness before tuning E2 or making
claims about model quality. This is a bounded prerequisite for the optional
retrieval demo, not a replacement for the main NCKH research study.

## Root cause and prevention

`Database.upsert_document` used `cursor.lastrowid` after an upsert. Updating an
existing path can return a previous insert's ID (or zero on a fresh connection),
not the updated document's ID. The indexer passes that ID to chunk storage.
Consequently a dense-search join could combine one file's path and chunk text
with another file's name, extension and timestamps.

The fix selects the persisted ID by its unique file path within the existing
write transaction. Chunk storage validates the ID/path pair and embedding row
count before replacing data; replacement is transactional. Document deletion
also deletes chunks by path rather than relying on disabled foreign-key
cascades. Dense retrieval and VectorCache preload require both ID and path to
match, so legacy mismatches cannot leak mixed metadata into results.

These safeguards do not repair already-corrupt rows, verify embedding-model
provenance, or guarantee topical relevance. Restart RAT after deploying the
updated code. The cache now follows committed updates/deletions automatically;
embedding freshness relative to the source file still needs separate evaluation.

## Import and snapshot isolation

Importing the core search/config/database modules or constructing `Database`
no longer creates a database or migrates its schema. Normal writable database
initialization happens on first connection use. Config directories are created
on explicit config save, not import.

Set `RAT_DB_PATH=/absolute/path/to/index.db` **before importing RAT** to select
the index used by its global instances. This selects a path; it does not make
the database read-only. Use `Database(path, read_only=True)` for snapshot reads:
it opens an existing file with SQLite `mode=ro` and `query_only`, without schema
initialization. Reading a live WAL database can still involve SQLite sidecars;
use a closed SQLite backup when byte-stable evidence is required.

## Read-only audit

The repair script uses only Python's standard library, independent of application
initialization. Older RAT versions migrated schema through global Database
construction, so an old snapshot's hash must not be assumed unchanged after import.
It is compatible with Python 3.10 or newer.

```bash
python scripts/repair_index_links.py --db "$HOME/.rat/rat_index.db"
```

Default mode opens the source read-only and reports counts from one read
transaction. It does not run a crawler, generate embeddings, call an LLM,
repair rows or change crawl roots. `quick_check=ok` alone does not establish
correct chunk/document relationships.

## Repair a new copy only

```bash
python scripts/repair_index_links.py \
  --db /path/to/frozen-index.db \
  --output-db /path/to/new-repaired-index.db > /path/to/repair-report.json
```

- SQLite's backup API captures committed WAL data consistently; do not copy
  the live `.db` file alone.
- Existing destinations and in-place repair are refused. The output's parent
  directory must already exist.
- A chunk with an exact `file_path` match in `documents` is relinked to that
  document's ID. This assumes the stored chunk path identifies its source;
  it does not validate text freshness or embeddings.
- A chunk without any matching document path moves to
  `quarantined_document_chunks` in the output copy, preserving its original
  ID, parent ID, path, text, vector and a reason. No personal source files are
  deleted, and the source index stays unchanged.
- Changes to the copy are transactional. Counts and `quick_check` are checked
  before commit. The JSON report includes the closed output database's hash.
  A failed attempt may leave an unactivated output file; do not use it as a
  repaired index without a successful report.
- Do not automatically put this copy into service: stop RAT/crawler/watchers,
  take a fresh live backup, review/repair that fresh copy, validate retrieval,
  and approve a separate migration. A stale audit snapshot can omit newer
  indexed files. Keep source and quarantine data until the migration is verified.

Reports and snapshots contain personal paths/text. Keep them outside the Git
repository; do not push them or include them in paper artifacts without review.

## Embedding consistency

Production embedding failures now raise `EmbeddingError` instead of fabricating
random or zero vectors. Non-finite values, zero norms and incorrect output shapes
are rejected and never cached. Empty requests remain no-op/sentinel operations.
Existing vectors are not automatically replaced, and legacy model identity is
still unknown.

```bash
python scripts/audit_embedding_drift.py \
  --db /path/to/closed-snapshot.db --sample-size 300 --seed 42 \
  --output /path/to/new-embedding-audit.json
```

The audit requires an already-cached real model; it is offline, rejects a nonempty
WAL and never overwrites a report. It samples sorted chunk IDs without replacement,
using only valid ID/path links. It re-embeds stored chunk text with current
preprocessing and records per-chunk cosines, hashes, package/model identities,
source hashes and before/after snapshot hashes. It does not repair embeddings.

Cosine below the declared threshold flags inconsistency, **not proof of model
mixing**: pooling, preprocessing, package changes, earlier fallback vectors or
stale text/vector pairs can also cause it. Grouping uses the document's latest
`indexed_at` week in UTC, not the vector's unrecorded creation date. Small weekly
groups do not estimate population rates reliably. Preserve FastEmbed's pooling
change warning rather than hiding it.

## Atomic indexing and cache freshness

The indexer extracts content and generates embeddings before changing the index.
`Database.replace_document` publishes metadata, FTS text and replacement chunks
in one transaction. Embedding failure keeps the previous complete version;
failed SQL writes roll back the whole replacement. Empty, whitespace-only or
short content clears obsolete semantic chunks while keeping the current text
available to lexical search. The unchanged-file check requires identical
modification timestamps and sizes, so edits within the same second are processed.

Each `VectorCache` owns a lazy read-only connection to its selected database.
Before searching, it checks SQLite's `PRAGMA data_version` and reloads its vector
matrix when another connection has committed a change. Versions are compared
on that same dedicated connection, as required by the
[SQLite contract](https://www.sqlite.org/pragma.html#pragma_data_version).
Scoring and lazy text enrichment share a read transaction, so a concurrent write
cannot pair an old vector with new chunk text. Results use persisted positive
chunk IDs; indexing no longer appends synthetic IDs to a global cache. Separate
databases retain separate results, and deletion/rename events become visible
without restarting the cache. `close()` releases its owned connection and arrays.
Legacy append/remove hooks only invalidate the cache; writes must reach SQLite
first.

The first search after a commit reloads all chunk vectors. Unchanged searches
reuse the matrix, but no new large-index latency or relevance result is claimed.
Files that change without changing either timestamp or size, or during content
extraction/generation, still need stronger source-version validation.

## Watcher lifecycle

Constructing `FolderWatcher` does not start its queue worker. Startup is tracked
and synchronized, duplicate starts are ignored, and shutdown cancels startup
even while folders are being scheduled or the observer is starting. Restart uses
a new watchdog observer. Queue waits are interruptible; late events are rejected
after shutdown, and an individual indexing error is logged without killing the
queue worker.

Shutdown waits up to two seconds. An index operation already executing may finish
later; another watcher generation cannot start while prior threads remain alive.
The direct `RatFileEventHandler` constructor retains its default autostart
behavior for existing callers.

## Compound-query correctness

Protected Vietnamese compounds are now matched as whole words, longest first,
and their consumed spans are excluded from residual keywords. Thus `slides giải
tích` does not leak separate `giải` and `tích` topic points into unrelated files.
Independent occurrences outside the phrase remain searchable. FTS query building
preserves compounds as quoted phrases rather than concatenating them into
`giaitich`; the final token keeps prefix matching. Production and the BM25
benchmark share this builder.

This changes parser/candidate behavior, not the heuristic weights. It requires a
new baseline with source hashes; it is not evidence of score-instrumentation
equivalence or judged relevance improvement. A semantic-only candidate can still
match a filename keyword when lexical top-k omitted it. E2 remains unimplemented;
any future per-query topic state must be local, never shared on the reranker.

## Verification

```bash
python -m pytest tests/test_index_integrity.py tests/test_index_link_repair.py -q
python -m pytest tests/test_database_lifecycle.py tests/test_embedder_integrity.py \
  tests/test_embedding_audit.py tests/test_query_compounds.py tests/test_fts_phrases.py -q
python -m pytest tests/test_vector_cache_freshness.py tests/test_indexer_consistency.py \
  tests/test_watcher_lifecycle.py -q
```

Tests cover update-after-insert and fresh-connection IDs, wrong-parent rejection,
embedding-row mismatch, atomic rollback, deletion, both dense retrieval paths,
copy-only repair, quarantine preservation, no overwrite, idempotence, failure
rollback, committed WAL data and the default read-only CLI. New regressions also
cover cached insertion/replacement/deletion, external and concurrent writes,
metadata filters, database isolation, rename events, atomic FTS/chunk rollback,
failed embeddings, shortened content and watcher startup/shutdown races. Set
`RAT_DB_PATH` to a temporary database before running these core checks. Tests use
synthetic embeddings, fake observers and an unscheduled watchdog observer; they
do not measure judged relevance or a running desktop application's performance.

Validation checkpoint, 2026-10-08: **103 passed** on Python 3.12, including the
three new regression suites, existing integrity/lifecycle/embedding/query checks,
relevance-pool helpers and the existing watcher extension-filter check. Reproduce
the combined check with a fresh temporary `RAT_DB_PATH`:

```bash
python -m pytest tests/test_vector_cache_freshness.py tests/test_indexer_consistency.py \
  tests/test_watcher_lifecycle.py tests/test_index_integrity.py tests/test_index_link_repair.py \
  tests/test_database_lifecycle.py tests/test_embedder_integrity.py tests/test_embedding_audit.py \
  tests/test_query_compounds.py tests/test_fts_phrases.py tests/test_relevance_pool.py \
  tests/test_portability_and_performance.py::TestPortabilityAndPerformance::test_watcher_filters_unsupported_extensions -q
```

After correctness checks, collect graded judgments for multiple relevant files
per query. Prioritize Precision@5 and nDCG@10; report recall only with a clearly
defined judged pool or sufficiently complete relevant set. Keep tuning queries
separate from held-out evaluation. Do not treat passing tests or a repaired
index as evidence that E2, adaptive reasoning, or the overall app works well.

Foreign-key activation/migration, event logging and embedding provenance need a
separate reviewed migration. The legacy schema already declares `ON DELETE
CASCADE`, but enforcement was disabled; blindly enabling it on wrong ID/path
links risks cascading through another file's chunks. Do not automatically
exclude Git working trees: they contain real study files too. A future labeling
pool should deduplicate copies by content hash and combine multiple retrieval
methods plus random candidates, with development and held-out query groups fixed
before tuning. The existing diagnostic queries are development data, not a
sealed test set.

## Next engineering work

Priority scores use `(impact + risk) × (6 − effort)`, with 1–5 ratings.
These are engineering estimates, not measured model outcomes.

| Order | Work | Impact / risk / effort | Score | Estimated effort and purpose |
| --- | --- | --- | --- | --- |
| 1 | Add isolated RAT core checks to CI | 4 / 4 / 2 | 32 | About half a day; catch index/cache/watcher regressions automatically alongside the existing research checks. |
| 2 | Validate source versions across extraction and commit | 4 / 5 / 3 | 27 | About 1–2 days; detect edits during indexing and coordinate in-flight work with delete/move events. |
| 3 | Record embedding identity and plan legacy-vector migration | 4 / 4 / 4 | 16 | Several days plus review; make model/preprocessing changes auditable before replacing existing vectors. |

The current phase repairs transactional/index lifecycle correctness. Follow it
with CI and source-version checks; evaluate retrieval on a separate reviewed
query pool before changing relevance weights. Embedding migration remains a
separate deployment step with preserved snapshots.
