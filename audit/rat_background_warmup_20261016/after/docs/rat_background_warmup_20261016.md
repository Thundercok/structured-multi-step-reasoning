# Background document warmup — 16 October 2026

Automatic semester-document warmup previously started even when folder watching
was disabled. It also collected every matching path across the configured trees
before indexing the first file, retaining a potentially large list in memory.

The resident launcher now schedules this warmup only when `auto_watch` is enabled
and configured roots exist. Its callback rechecks those settings, shutdown and
an already-running warmup before constructing another worker. The worker also
checks settings and cancellation at directory/file boundaries.

Warmup checks power state at the beginning of its worker run and skips that run
when on battery. This OS query stays off the GUI thread. Plugging in later does
not automatically resume the skipped run; a later permitted launch or explicit
index operation can update the index. Power changes during a running pass are
not monitored by this slice.

Eligible files are indexed as they are discovered. The worker no longer holds
a full-tree path queue; `os.walk` still enumerates the current directory. Normal
indexer exclusions now prune generated directories and macOS app bundles too.
Unchanged files retain the indexer's existing skip behavior.

This affects automatic academic-document warmup only. It does not disable the
explicit `index` command, change first-run onboarding indexing, alter the
watcher's existing behavior, evict inference models, or change UI source.

## Validation

```sh
.venv/bin/python -m pytest tests/test_semester_warmup.py tests/test_resident_warmup.py tests/test_watcher_lifecycle.py tests/test_rat_headless_cli.py -q
```

Final result: **43 passed, 6 subtests passed in 2.45 seconds**. Tests use temporary
synthetic files and fake indexers/threads, not personal documents or model calls.
They verify skipped runs never walk/index, the first file is processed before
discovery completes, stop/disable interrupts remaining work, normal directory
exclusions apply, and the launcher avoids duplicate workers. Watcher lifecycle
and lightweight CLI regressions remain passing. Scoped whitespace and Python
compilation checks pass.

An initial new fixture compared `/var/...` with macOS's resolved `/private/var/...`
path. Its expectation was normalized; the initial and final test artifacts are
both retained under `audit/rat_background_warmup_20261016/`, together with source
snapshots. No native UI acceptance, full-app RAM reduction, inference speedup or
model-quality claim is established by these checks. Research and Stage 0 are
unchanged.
