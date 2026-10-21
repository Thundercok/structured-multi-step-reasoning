"""Independent consolidation checks; fresh imports and a copied hash fixture only."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


def fresh(code):
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True,
                            text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("canonical_first", [False, True], ids=["root-first", "canonical-first"])
def test_module_identity_patch_private_helpers_and_legacy_pickle(canonical_first):
    code = '''
import importlib,json,pickle
from unittest.mock import patch
names = ["entry_predictor", "optimal_stopping", "reasoning_env", "reasoning_strategies"]
for name in names:
    order = ["reasoning."+name, name] if CANONICAL_FIRST else [name, "reasoning."+name]
    for module in order: importlib.import_module(module)
    assert importlib.import_module(name) is importlib.import_module("reasoning."+name)
import reasoning_strategies as shim
from reasoning import reasoning_strategies as canonical
assert hasattr(shim, "_eval_arith")
with patch("reasoning_strategies._eval_arith") as patched:
    assert canonical._eval_arith is patched
    assert canonical.safe_calculate.__globals__["_eval_arith"] is patched
from entry_predictor import EntryChoice
original_module = EntryChoice.__module__
try:
    EntryChoice.__module__ = "entry_predictor"
    old_pickle = pickle.dumps(EntryChoice.LADDER)
finally:
    EntryChoice.__module__ = original_module
assert pickle.loads(old_pickle) is EntryChoice.LADDER
assert pickle.loads(pickle.dumps(EntryChoice.LADDER)) is EntryChoice.LADDER
print(json.dumps(dict(identity=True,private_helper=True,patch_binding=True,legacy_pickle=True)))
'''.replace("CANONICAL_FIRST", repr(canonical_first))
    assert all(fresh(code).values())


@pytest.mark.parametrize("module", ["reasoning", "reasoning.reasoning_strategies"])
def test_lightweight_import_does_not_eager_load_ml_or_qt(module):
    data = fresh(f'''
import importlib,json,sys
importlib.import_module({module!r})
prefixes=("sklearn","gym","gymnasium","PyQt6","PyQt5","mlx")
heavy=[key for key in sys.modules if any(key == p or key.startswith(p+".") for p in prefixes)]
print(json.dumps(dict(heavy=heavy)))
''')
    assert data["heavy"] == []


def test_canonical_only_source_change_changes_fingerprint_without_changing_shim(tmp_path, monkeypatch):
    from experiments import research_study as study
    original = study.source_hashes()
    names = ["entry_predictor", "optimal_stopping", "reasoning_env", "reasoning_strategies"]
    assert all(name+".py" in original and "reasoning/"+name+".py" in original for name in names)
    assert "reasoning/__init__.py" in original
    for relative in original:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    monkeypatch.setattr(study, "ROOT", tmp_path)
    before = study.source_hashes()
    target = tmp_path / "reasoning/reasoning_strategies.py"
    target.write_bytes(target.read_bytes() + b"\n# independent fingerprint fixture\n")
    after = study.source_hashes()
    assert [name for name in before if before[name] != after[name]] == ["reasoning/reasoning_strategies.py"]
    assert before["reasoning_strategies.py"] == after["reasoning_strategies.py"]
