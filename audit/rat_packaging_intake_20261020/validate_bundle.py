"""Inspect the real frozen archive/resources and exercise two model-free CLI paths."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import CodeType

from PyInstaller.archive.readers import CArchiveReader

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
bundle = Path(sys.argv[1])
output_name = sys.argv[2] if len(sys.argv) > 2 else 'bundle_validation.json'
executable = bundle / 'Contents/MacOS/rat'


def signature(code):
    def constant(value):
        if isinstance(value, CodeType):
            return signature(value)
        if isinstance(value, tuple):
            return tuple(constant(v) for v in value)
        return value
    return (code.co_code, code.co_names, code.co_varnames, code.co_flags,
            code.co_argcount, code.co_kwonlyargcount, code.co_posonlyargcount,
            code.co_freevars, code.co_cellvars, tuple(constant(v) for v in code.co_consts))


pkg = CArchiveReader(str(executable))
archive = pkg.open_embedded_archive('PYZ.pyz')
checks = {}
for module in ('document_intake.pdf', 'document_intake.vision', 'document_intake.tesseract',
               'rat.crawler.extractors'):
    source = ROOT / (module.replace('.', '/') + '.py')
    checks[module + ':current_bytecode'] = signature(archive.extract(module)) == signature(
        compile(source.read_bytes(), str(source), 'exec'))
for module in ('reasoning.entry_predictor', 'reasoning.optimal_stopping', 'reasoning.reasoning_env',
               'reasoning.reasoning_strategies', 'sklearn', 'scipy', 'gymnasium', 'pypdf'):
    checks[module + ':included'] = module in archive.toc
for relative in ('rat/engine/snapshot.schema.json', 'rat/assets/rat_mascot.png',
                 'rat/astrology/ephemeris/manifest.json'):
    resource = bundle / 'Contents/Resources' / relative
    checks[relative + ':source_match'] = resource.is_file() and resource.read_bytes() == (ROOT / relative).read_bytes()
for name in ('libqcocoa.dylib', 'libjaccl.dylib', 'mlx.metallib'):
    checks[name + ':included'] = any(bundle.rglob(name))

env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
cli = {}
with tempfile.TemporaryDirectory(prefix='rat-frozen-cli-', dir='/private/tmp') as workdir:
    for label, args in (('help', ['--help']), ('calculator', ['1 + 2'])):
        result = subprocess.run([str(executable), *args], cwd=workdir, env=env,
                                capture_output=True, text=True, timeout=30)
        cli[label] = {'argv': [str(executable), *args], 'exit_code': result.returncode,
                      'stdout': result.stdout, 'stderr': result.stderr}
        checks[label + ':exit_success'] = result.returncode == 0
    checks['help:expected_output'] = 'usage:' in cli['help']['stdout'].lower()
    checks['calculator:expected_output'] = '3' in cli['calculator']['stdout'] and 'Kết quả' in cli['calculator']['stdout']
result = {'status': 'passed' if all(checks.values()) else 'failed', 'bundle': str(bundle),
          'executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),
          'checks': checks, 'cli': cli, 'model_calls': 0,
          'scope': 'archive/resources and frozen CLI only; no GUI or model acceptance'}
(HERE / output_name).write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(json.dumps(result, indent=2, ensure_ascii=False))
raise SystemExit(not all(checks.values()))
