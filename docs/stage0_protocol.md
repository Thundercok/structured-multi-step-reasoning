# Stage 0: feedback and retrieval baseline

Stage 2 (Qwen/Meta-Reasoner measurements and training) remains frozen pending review
of the Stage 0 raw run. Existing reasoning results use a simulator, not measured
Qwen/MLX generation. A completed retrieval run does not establish relevance quality.

## Feedback

`rat/engine/feedback_log.py` stores impressions, impression_items, actions and
open_counts in `~/.rat/feedback.db`, separate from the index. Transactions use WAL,
foreign keys and a short lock timeout. Failure rolls back, logs a warning and lets
the user continue. Logging is local; queries and paths are personal data.

Both search windows use `rat/ui/feedback.py`. Visible lists are snapshotted after
sorting/inserting cards, on replacement and when shown again. Hidden results are
not impressions. Switching tabs, replacing results and hiding a window dismiss
the previous impression. `none` is recorded only when it has no action yet.
Open, reveal and terminal mean user activation attempts, not verified OS success.
Only open increments the count. Virtual `rat://` cards are excluded while their
positions remain reflected in the 1-based rank. Recent files have a blank query
and missing retrieval scores, and must be excluded from retrieval training.

Each impression also snapshots the parsed context, `static_heuristic_v1` ranker
label, Git SHA, search latency, and number of shown candidates. Each item stores the clamped
score shown to the user, the pre-clamp raw score, and a JSON map of the 20
additive heuristic contributions. The invariant is `raw_score = 5 + sum(feats)`.
The old sort still uses the clamped score; changing that would define a new
ranker and must use a different version label. Existing feedback databases are
migrated in place with defaults for historical rows.

Features: actual FTS5 `bm25 = -rank`, max chunk cosine, normalized production
`rrf_score` (0..100, not the unnormalized RRF sum), final heuristic score, age at
display and prior opens. Missing BM25 stays NULL: filename fallback rank -100 is
not a BM25 measurement. Stage 0 reads counts in the display transaction. Stage 1
must supply the actual ranking-time `raw_scores['prior_opens']`, which takes
precedence even when zero. Other learned features must follow the same contract.

Deleting historical actions does not recompute historical features. To clear all
history, quit the app before removing feedback.db and any feedback.db-wal/-shm
sidecars. Removing the main file while a WAL connection is active is unsafe.

## Reproduce

Run `python3 scripts/benchmark_stage0.py --iterations 3` from the repo, optionally
passing `--db`, `--queries` (JSON string array), and `--output`. The default query
set is a small smoke suite, not an established relevance benchmark.

The script backs up the live index via SQLite, derives counts from that snapshot,
hashes the snapshot and queries, and records git SHA, dirty status, source hashes,
package versions, UTC time, power source, platform and model name. Index model
identity/pooling is not recorded by the existing index, so compatibility is an
assumption, explicitly recorded in the manifest. Models must already be cached;
missing models or invalid vectors fail the run instead of silently using random
embeddings. No index content or file paths are included in samples.

Each method runs in a fresh process. Cold is its first query with lazy model/vector
loading included; Python import time is excluded and OS disk caches are not
flushed. One cold sample is descriptive only, not a tail-latency estimate. All
queries are warmed once before repeated warm samples. Query vectors are recomputed
each time; production query-result caching is not measured.

The manifest records `use_hyde=false` and `use_slm=false`; a completed baseline
must contain BM25, lexical, vector and hybrid runs, each with zero LLM/SLM calls.
Every raw warm sample retains its query ID and iteration. Paired latency intervals
resample query IDs as clusters after taking each query's median across iterations;
iterations of one query are not treated as independent observations.

The bm25 method measures weighted FTS5 with the same query/filter construction,
without filename fallback, fusion or reranking; its `fts5_ms` is isolated SQLite
retrieval, while its total includes decomposition/context setup. Other methods are
lexical, vector and four-way hybrid followed by production fusion and heuristic
reranking. Their `fts5_ms` includes filename/LIKE fallback. `vector_ms`
includes lazy vector loading in the cold sample and excludes query embedding.
Separate timers cover decomposition, embedding, lexical retrieval, vector search,
provenance, vision, fusion and reranking. The hybrid path excludes HyDE, sufficiency
evaluation, corrective cascade and UI formatting. It is not full SearchEngine.search.

SLM and LLM generation entry points raise on use and increment a counter; the run
asserts zero calls even if a caller catches the exception. Raw ordered samples,
query IDs, iteration, cold/warm phase, result/candidate counts, stage times, current
RSS and worker peak RSS accompany recomputable percentiles. A failed worker yields
a failed partial JSON, never a successful baseline. Do not average run percentiles
or infer statistical significance from this small default suite.
