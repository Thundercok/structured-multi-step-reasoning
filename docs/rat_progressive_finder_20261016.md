# Progressive finder — first headless slice

Implemented 2026-10-16. This supplies the fast retrieval foundation for RAT-FIND-01:
application aliases plus local indexed-file search, with query ownership and an
optional independent semantic stage. It is not yet connected to the composer,
does not launch applications, and does not add a CoT model controller.

## Implemented

`rat/engine/app_resolver.py` explicitly builds an immutable macOS application
catalog from `/Applications`, `/System/Applications` and `~/Applications`, or
caller-supplied roots. It reads bundle metadata, checks a declared executable
exists and records separate identities for separate installations. Traversal is
bounded and does not recurse inside app bundles. Nothing is launched.

The initial explicit alias table recognizes “Liên Minh Huyền Thoại”, “Liên Minh”
and “LoL” for an observed `League of Legends` bundle name. It does not manufacture
an installation or substitute Riot Client. Alias ambiguity returns multiple
candidates. This is metadata discovery, not code-signature verification or a
security attestation. A future launch operation must revalidate the chosen bundle
and require an opening request/selection. Rebuild the catalog explicitly after
install/uninstall changes; do not rescan it on every keystroke.

`Database.search_metadata()` queries the existing FTS5 index with literal ANDed
prefix terms and optional explicit extension/date filters. It returns only small
metadata/summary fields, not full `content_text` or vectors. Results are read-only
references to indexed files, not proof of a fresh document read. Missing files
are omitted. No new indexing or personal-file crawl is started.

`rat/engine/progressive_search.py` exposes:

- `SearchRequest` with query ID, cancellation, result limit and explicit filters.
- `ProgressiveSearch.initial()` for apps plus FTS/metadata; no embedding/model dependency.
- `snapshots()` yields that result before invoking any optional semantic provider.
- A provider returns indexed file paths; the engine validates index membership,
  existence and filters, deduplicates, then appends results. Existing result
  identities/order and a supplied selected identity are preserved.
- `SearchCoordinator` separates lexical and semantic work onto independent workers.
  Each holds one running job and one replaceable pending job. A new query cancels
  the previous request and replaces pending work, preventing a FIFO of old typing.

The semantic provider is an injection point, **not an already-wired embedding
backend**. By default only the lexical stage runs. A full result list or blank
query skips optional refinement. This is a bounded retrieval decision, not a
confidence estimate or proof that the best possible results were found.

## Minimal API use

```python
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.progressive_search import ProgressiveSearch, SearchRequest

catalog = ApplicationCatalog.scan()  # startup/worker, once before typing
finder = ProgressiveSearch('/absolute/path/existing-rat-index.db', catalog=catalog)
try:
    for snapshot in finder.snapshots(SearchRequest(1, 'Liên Minh')):
        for hit in snapshot.hits:
            print(hit.kind, hit.title, hit.path)
finally:
    finder.close_connection()  # same thread that used this connection
```

`SearchFilters` currently takes explicit extensions and modification dates. This
slice does not interpret arbitrary natural-language requests, strip “mở”, measure
game storage, or summarize documents. Those require routing/capabilities or the
existing selected-document model path. Unknown aliases simply yield no app match.

## Responsiveness, lifecycle and boundaries

Package exports in `rat.engine` and `rat.crawler` are now lazy. Previously an
import of the database could load indexing/search/model dependencies. NumPy is
imported inside vector operations instead of the lexical DB module. Existing
public package exports remain available on demand.

SQLite progress checks can abandon an obsolete query; the fast metadata request
uses a 50 ms database lock wait, then restores the prior connection timeout.
A locked/missing index reports `file_index_unavailable` while preserving app
matches. Semantic errors preserve lexical results. Error codes do not expose raw
provider exceptions. A worker callback error does not kill subsequent searches.

Worker callbacks must enqueue UI events, not manipulate Qt widgets. The eventual
UI receiver must check `coordinator.is_current(snapshot.query_id)` at delivery,
since a result can become stale while a queued event travels to the GUI. Keep
the GUI's current selection by resource ID when applying an appended result.
Requests have cooperative cancellation, not forced termination of a running
embedding kernel. `close(timeout=2)` cancels current/pending work, closes each
worker's own DB connection when it exits, and reports whether workers stopped;
an uncooperative provider can outlive this timeout. The owner must handle that
state without claiming successful backend cancellation.

Snapshots are transient retrieval projections. No second artifact/task store,
new research receipt system, model prompt, controller or UI surface is introduced.
The existing research harness/protocol and Stage 0 remain unchanged.

## Verification and measured limits

Thirteen new contract tests cover real synthetic bundles/indexed files, aliases,
multiple installations, missing/broken resources, filters, bounded projections,
semantic failures/unindexed paths, selection identity, late callbacks, pending-job
replacement, locked DB handling and subsequent requests after cancellation/errors.
A fresh subprocess blocks Qt, NumPy, model/embedding imports, network connects and
subprocess launches while exercising the actual app + file retrieval path.

The scoped regression command (including existing database, document Q&A, lifecycle
and Qt offscreen tests) and results are in
`audit/rat_progressive_finder_20261016/tests.xml`: **203 passed, 3 subtests passed
in 24.64 seconds**. Qt-containing regression tests ran offscreen outside the
filesystem sandbox; no native app window was opened for this task.

`audit/rat_progressive_finder_20261016/probe.py` created **5,000 actual synthetic
files** and matching FTS records in a temporary directory, then removed that
directory. Each query ran once plus 30 warm repetitions. Values below are complete
backend `initial()` call times; fixture creation, imports, catalog discovery,
queue/event transport, debounce, paint and model work are outside them. The first
call is not a controlled cold-filesystem measurement; fixture creation had just
warmed the OS cache.

| Query case | First API call | Warm median | Warm p95 |
| --- | ---: | ---: | ---: |
| Exact filename | 3.89 ms | 2.53 ms | 2.63 ms |
| Indexed content token | 0.78 ms | 0.61 ms | 0.64 ms |
| Broad term | 11.60 ms | 10.26 ms | 10.36 ms |
| No match | 0.61 ms | 0.50 ms | 0.54 ms |

Fresh imports took 31.7 ms. A separate read-only installed-app catalog scan took
256 ms and accepted 170 metadata/executable records, including one Safari match;
invalid bundles were skipped with a diagnostic. The scan did not launch apps or
persist an inventory of installed application names. Aliases for League of Legends
were tested on clearly synthetic bundles, not an observed game launch.

The probe blocked inference/GUI/NumPy dependencies and process launch, and recorded
zero network attempts. These small development observations do not establish
100,000-file performance, whole-app RAM, 100–200 ms native UI latency, relevance
quality, or behavior under concurrent model/indexer load. Raw repetitions, source
hashes and the reproduction script are preserved in the audit directory.

## Next integration boundary

Connect this coordinator to the existing composer/Workbench behind the existing
feature-gating conventions. Keep drafts, IME, keyboard focus and selected resource
identity. After retrieval interaction passes native acceptance, register opening
an explicitly selected app through the current dispatcher/receipt machinery.
Then connect selected-file questions to the resident MLX service. More general
structured reasoning needs its own adapter, goals, verifiers and reviewed budgets;
this fast finder alone does not establish a new CoT capability.
