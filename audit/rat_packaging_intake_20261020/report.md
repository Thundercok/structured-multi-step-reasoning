# Packaging and PDF/OCR robustness — 2026-10-20

Completed the packaging/intake delivery on `main`. These are software and packaging
checks, not model-quality evidence or native GUI acceptance. No model inference,
personal indexing, Git commit, branch or remote operation was performed.

## Changes

- Desktop requirements now declare scikit-learn, scipy and gymnasium; the spec
  includes the canonical reasoning/intake packages without excluding those imports.
- Python source directories are no longer copied wholesale as data. Assets, the
  snapshot schema and ephemeris data are explicit; paths are relative to the spec.
- Installed optional MLX dylibs and Metal kernels are collected explicitly,
  resolving the missing libjaccl packaging dependency. No model weights are added.
- Build preflight checks versions, imports/resources and QtCore/plugin availability
  before output cleanup. Missing DMG input fails before cleanup; dependencies are
  never installed implicitly and cleanup targets only named RAT build outputs.
- PDF reads have stable typed error codes, password support, hard returned-text
  limits and explicit empty/no-text status. Short native digital text is retained;
  metadata alone no longer masks missing content. RAT keeps its empty-on-failure
  indexing contract and caps the formatted output, including metadata/markers.
- Tesseract shares one timeout across TSV/text fallback and does not retry a
  timeout/missing executable. Invalid TSV scores/boxes are skipped. Vision checks
  malformed images before framework initialization and handles false/error tuples.

## Validation

| Check | Result | Raw evidence |
| --- | --- | --- |
| Intake, packaging, separation and CLI regression | 75/75 pass | regression-delivery.xml, stdout/stderr and command JSON |
| Required research regression | 29/29 pass | research.xml, stdout/stderr and command JSON |
| Final-suite unique tests | 104 | Counted by classname/name, no earlier-run counts added |
| Offline shared-intake wheel | Built, installed in isolated venv, source bytes match | wheels-release/, isolated-wheel-install-release.*, isolated-wheel-smoke-release.* |
| macOS preflight and clean app build | Passed outside sandbox | qt-native-preflight.*, app-build-verified.* |
| Frozen archive/resources and model-free CLI | passed | bundle_validation_verified.json, frozen-bundle-verified.* |
| Actual macOS PDFKit on digital/error fixtures | Passed, OCR blocked | native_pdf_validation.json, native-pdf-fixtures.* |
| Shell syntax | Passed | shell-syntax.* |

The actual app output is `/private/tmp/rat-packaging-intake-20261020-verified-dist/rat.app`. The frozen CLI checks run `--help`
and `1 + 2` from an empty temporary working directory. Archive inspection checks
current shared-reader/adapter bytecode, reasoning/dependency inclusion, resource
bytes, the Cocoa plugin and optional MLX library/kernel presence without inference.
The real native PDF reader was separately checked on the authored digital,
encrypted, malformed and zero-page fixtures; OCR was replaced by a blocking
sentinel and no OCR attempts occurred. CoreGraphics emitted its expected malformed
input diagnostic, retained in raw stderr.

Six persisted authored PDFs cover digital, encrypted, malformed, zero-page,
blank-page and image-only input. The scanned raster was rendered and visually
inspected. Tests additionally cover AES-256/empty passwords, short native text,
missing PDF/crypto engines, OCR failures/timeouts, bad images and corrupt TSV.
Fixture/double results do not measure OCR accuracy. `fixtures.*` preserves the
initial stale-installed-package import failure; `fixtures-retry.*` records the
corrected fixture script with explicit checkout source resolution.

## Limits and preserved work

The existing broad source environment fails `pip check` for unrelated dependencies;
see environment-pip-check.*. No global environment repair was attempted. Only the
intake wheel was installed into a clean isolated environment. Full fresh desktop
dependency resolution and cross-platform GUI behavior are not certified here.

Qt CPU detection and frozen startup failed in the restricted sandbox; the same
Qt probe passed outside it. Both failures and native successes are retained.
The first app build is an intermediate sandbox build. Subsequent archive checks
caught stale cached PDF bytecode despite successful PyInstaller exits. Those
failures are retained in bundle_validation.json and frozen-bundle-release.*.
The verified bundle uses a fresh work directory and `--clean` and is checked
against current reader source. The standard build wrapper now uses `--clean`.
No raw logs were overwritten or failures relabeled.

Native GUI interaction, Gatekeeper/notarization, external Tesseract/language-pack
installation and MLX/model behavior remain separate acceptance. Native PDF reading
still exposes a string contract without structured truncation details. Blank and
scanned pages cannot be distinguished solely by absence of digital text; mixed
raster/text within one page is not fully diagnosed. Character limits bound returned
text, not parser execution time or peak memory.

The preexisting selected-document QA hidden import is preserved. No runtime
controller, worker, bundle-policy schema, fresh-data protocol, held-out queries,
model settings or research gate was changed by this work. The 29-test research
result is a software regression, not an independent acceptance or Stage 0 claim.

Review `changes.patch` against source_start/ rather than the repository-wide dirty
diff. source_end.json and artifact_manifest.json identify the delivered sources
and evidence. Ignored local venv/cache directories are not deliverable artifacts.
