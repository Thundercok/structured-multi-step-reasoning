"""Record final scoped sources, raw-check outcomes and an artifact manifest."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
start = json.loads((HERE / 'source_start.json').read_text())
files = list(start) + ['scripts/check_packaging.py', 'tests/test_packaging_contract.py',
                      'tests/test_document_intake_robustness.py', 'docs/rat_packaging.md']
hashes, changes = {}, []
for name in files:
    data = (ROOT / name).read_bytes()
    hashes[name] = hashlib.sha256(data).hexdigest()
    target = HERE / 'source_end' / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    before = (HERE / 'source_start' / name).read_text() if name in start else ''
    changes.extend(difflib.unified_diff(before.splitlines(True), data.decode().splitlines(True),
                                      fromfile='before/' + name, tofile='after/' + name))
(HERE / 'source_end.json').write_text(json.dumps(hashes, indent=2) + '\n')
(HERE / 'changes.patch').write_text(''.join(changes))
status = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True, text=True, check=True)
(HERE / 'git_status_end.txt').write_text(status.stdout)

tests, identities = {}, set()
for label, filename in [('scoped', 'regression-delivery.xml'), ('research', 'research.xml')]:
    cases = list(ET.parse(HERE / filename).getroot().iter('testcase'))
    counts = {'total': len(cases), 'failed': 0, 'errors': 0, 'skipped': 0}
    for case in cases:
        identities.add((case.get('classname'), case.get('name')))
        for tag, key in [('failure', 'failed'), ('error', 'errors'), ('skipped', 'skipped')]:
            counts[key] += int(case.find(tag) is not None)
    counts['passed'] = counts['total'] - counts['failed'] - counts['errors'] - counts['skipped']
    tests[label] = counts

wheel = HERE / 'wheels-release/nesy_document_intake-0.1.0-py3-none-any.whl'
with zipfile.ZipFile(wheel) as archive:
    wheel_sources_match = all(archive.read('document_intake/' + name) == (ROOT / 'document_intake' / name).read_bytes()
                             for name in ('__init__.py', 'pdf.py', 'vision.py', 'tesseract.py'))
bundle = json.loads((HERE / 'bundle_validation_verified.json').read_text())
commands = {path.name.removesuffix('.command.json'): json.loads(path.read_text())['exit_code']
            for path in HERE.glob('*.command.json')}
result = {'status': 'complete' if bundle['status'] == 'passed' and wheel_sources_match
          and all(c['passed'] == c['total'] for c in tests.values()) else 'incomplete',
          'tests': tests, 'unique_tests_across_final_suites': len(identities),
          'command_exit_codes': commands, 'bundle_status': bundle['status'],
          'wheel_sources_match': wheel_sources_match,
          'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
          'preexisting_selected_document_qa_import_preserved': "'rat.engine.selected_document_qa'" in (ROOT / 'rat.spec').read_text(),
          'source_files_changed_from_start': [name for name, value in hashes.items() if start.get(name) != value],
          'model_calls': 0, 'gui_acceptance': 'not performed',
          'research_gate_changes': False,
          'environment_limitations': ['Existing source environment pip check has unrelated dependency conflicts.',
            'Qt/frozen CLI sandbox attempts failed; native preflight/build/CLI are recorded separately.',
            'Full desktop dependency installation into a clean environment was not tested offline.'],
          'scope': 'Packaging, shared PDF/OCR readers and RAT PDF indexing adapter only; Antigravity runtime/research files were not edited.'}
(HERE / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')

report = f'''# Packaging and PDF/OCR robustness — 2026-10-20

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
| Intake, packaging, separation and CLI regression | {tests['scoped']['passed']}/{tests['scoped']['total']} pass | regression-delivery.xml, stdout/stderr and command JSON |
| Required research regression | {tests['research']['passed']}/{tests['research']['total']} pass | research.xml, stdout/stderr and command JSON |
| Final-suite unique tests | {len(identities)} | Counted by classname/name, no earlier-run counts added |
| Offline shared-intake wheel | Built, installed in isolated venv, source bytes match | wheels-release/, isolated-wheel-install-release.*, isolated-wheel-smoke-release.* |
| macOS preflight and clean app build | Passed outside sandbox | qt-native-preflight.*, app-build-verified.* |
| Frozen archive/resources and model-free CLI | {bundle['status']} | bundle_validation_verified.json, frozen-bundle-verified.* |
| Actual macOS PDFKit on digital/error fixtures | Passed, OCR blocked | native_pdf_validation.json, native-pdf-fixtures.* |
| Shell syntax | Passed | shell-syntax.* |

The actual app output is `{bundle['bundle']}`. The frozen CLI checks run `--help`
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
'''
(HERE / 'report.md').write_text(report)

manifest = {}
for directory, dirs, names in os.walk(HERE):
    dirs[:] = [name for name in dirs if name not in {'isolated-venv', 'pyinstaller-cache', '__pycache__'}]
    for name in names:
        path = Path(directory) / name
        if path.name == 'artifact_manifest.json':
            continue
        manifest[str(path.relative_to(HERE))] = hashlib.sha256(path.read_bytes()).hexdigest()
(HERE / 'artifact_manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'status': result['status'], 'tests': tests,
                  'unique_tests': len(identities), 'artifact_entries': len(manifest)}))
