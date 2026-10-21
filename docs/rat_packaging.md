# RAT installation and packaging

Desktop dependencies include the shared reasoning imports (`scikit-learn`,
`scipy`, `gymnasium`) and the local `document_intake` package. Research-only
installation remains separate through `requirements-research.txt`.

From the repository root, create an environment and install explicitly:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
bash scripts/build_app.sh --check
```

Preflight checks declared versions, local hidden imports, resources and prohibited
exclusions. The build wrapper also probes QtCore in a child process and checks
the platform plugin location before deleting outputs. It neither imports
application services nor initializes OCR/models,
downloads dependencies, indexes documents or launches the GUI. It reports missing
dependencies and leaves existing build outputs intact. `--spec-only` checks the
source/resource contract without validating the installed environment or Qt:

```sh
.venv/bin/python scripts/check_packaging.py --spec-only
```

Build the macOS app and DMG after preflight passes:

```sh
bash scripts/build_app.sh
bash scripts/build_app.sh --dmg-only  # requires existing dist/rat.app
```

Set `PYTHON_BIN` explicitly to use another environment. The build does not install
missing dependencies automatically. Cleanup is limited to the named RAT build
outputs; preflight and DMG input validation run first. The spec resolves paths
relative to its own location and keeps Python in the module archive, with only
assets, the snapshot schema and ephemeris resources copied as data.
PyInstaller runs with `--clean` to avoid stale analysis/archive caches. Build from
a stable source snapshot: source edits during analysis can invalidate the output,
even when the bundler exits successfully.

Dependency checks alone do not confirm a working standalone application. Validate
the actual frozen app on the target macOS/architecture, including Qt plugins,
resource access and optional capabilities. Ad-hoc signing is not notarization.
Tesseract requires its external executable and language packs. Optional astrology
requires `requirements-astrology.txt` and its existing license review. Native MLX
inference also needs its compatible runtime and local model; preflight does not
validate or activate it. Model weights, policies and personal indexes are not
created by preflight or supplied as app data by this spec. The existing build
exclusions for heavyweight optional stacks remain; native MLX acceptance is
separate from this base packaging check. When MLX is installed, its runtime
libraries and Metal kernels are collected explicitly; this does not supply
model weights or certify inference compatibility. A Qt CPU-feature probe failure
inside a sandbox must be resolved in the build environment before packaging;
do not bypass that check or distribute a bundle missing its platform plugins.

The shared intake package can also be built and installed independently offline
when build requirements are already installed:

```sh
python -m pip wheel ./document_intake --no-deps --no-build-isolation --no-index --wheel-dir /tmp/rat-intake-wheels
```

Install the resulting wheel in a fresh environment and verify imports from outside
the repository. Installing without extras intentionally leaves PDF/OCR engines
optional; calling the digital reader without pypdf raises `PDFReadError` with
`pdf_engine_unavailable`.
