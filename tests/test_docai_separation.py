"""The deferred DocAI module must not enter RAT/research startup."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def test_rat_registry_has_no_invoice_operation_or_docai_import():
    script = """
import builtins, sys
original = builtins.__import__
def guarded(name, *args, **kwargs):
    if name.split('.')[0] in {'nesy_docai', 'z3', 'streamlit', 'fastapi', 'PyQt6'}:
        raise AssertionError('Unexpected dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
from rat.kernel.capabilities import build_default_registry
registry = build_default_registry()
assert registry.get_operation('inspect_invoice') is None
assert not any(n.startswith('nesy_docai') for n in sys.modules)
"""
    result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

def test_docai_source_is_scoped_to_its_standalone_directory():
    assert not (ROOT / 'nesy_docai').exists()
    assert not (ROOT / 'rat/kernel/capabilities/invoices.py').exists()
    assert (ROOT / 'modules/docai/nesy_docai/service.py').is_file()
    assert (ROOT / 'modules/docai/requirements.txt').is_file()
