# Lightweight CLI startup — 16 October 2026

RAT's command entry points previously imported the resident GUI, file preview,
search coordinator and indexer before parsing even `--help`. A developer needed
Qt and NumPy for commands that did not use either of them.

`rat.main` now selects a command before importing its implementation. Resident
GUI and standalone astrology launches still install their exception hooks before
loading the GUI implementation. The root `main.py` uses the same dispatcher.
Importing `rat.main` or running a lightweight CLI command no longer installs GUI
exception hooks or creates the GUI crash-log directory.

`rat.cli` loads its database, indexer, search and file-preview dependencies in
the commands that use them. Search, indexing and document-answering behavior
are unchanged by this import refactor. Explicit open/reveal actions still use
their existing preview helpers. This change does not add an offline response
mode or replace the inference backend.

## Local startup observations

Three fresh-process observations were taken per command and phase. The table
uses the final source revision and median total subprocess wall time / peak
process RSS. No window, model or indexer was started. Crash-shield installation
was replaced in both phases to avoid modifying the user's log directory.

| Command | Before wall time | After wall time | Before peak RSS | After peak RSS |
| --- | ---: | ---: | ---: | ---: |
| `python -m rat.main --help` | 1.067 s | 0.272 s | 88.3 MiB | 24.7 MiB |
| `python -m rat.cli --help` | 0.449 s | 0.280 s | 68.1 MiB | 25.1 MiB |
| `python main.py --help` | 1.340 s | 0.243 s | 88.7 MiB | 25.3 MiB |

These are narrow development observations, not GUI startup, whole-machine RAM,
inference latency or model-quality measurements. Only the three modified entry
files were source-snapshotted; this is not a frozen benchmark distribution.
Background development work and OS caches were uncontrolled. Earlier after-run
samples were approximately 0.11 seconds, so a stable latency guarantee is not
established. Raw observations and intermediate runs are retained under
`audit/rat_headless_startup_20261016/`. The final after sample ran after our
regression processes had finished; the earlier overlapping run is labeled
`after-with-tests.json`.

## Validation

```sh
.venv/bin/python -m pytest tests/test_rat_headless_cli.py tests/test_database_lifecycle.py -q
```

Result: **26 passed**. Fresh-process checks deliberately make GUI, NumPy,
inference, search and index dependencies unavailable. Import, top-level and
subcommand help, shell-script generation, direct arithmetic and room lookup
still succeed without opening or changing the configured sentinel database,
contacting a service or launching another process. GUI routing checks preserve
exception-hook setup. The scoped whitespace and Python compilation checks pass.

The first import-boundary checks exposed a remaining eager database import,
which pulled in NumPy. Moving that import into the commands that use the
database resolved those failures; initial and final test artifacts are retained.

No UI source, persisted user settings, research harness, model defaults or
Stage 0 decision was changed. GUI search warmup and automatic background
indexing remain separate work; this result does not establish that the full
resident app is lightweight.
