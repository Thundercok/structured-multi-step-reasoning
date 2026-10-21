"""Packaging checks run without importing application services or model engines."""
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.check_packaging import ROOT, check_packaging


@pytest.fixture
def package_tree(tmp_path):
    for source in ("rat.spec", "requirements.txt", "document_intake/pyproject.toml"):
        target = tmp_path / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, target)
    # Keep local module/resource lookup on the real source tree, requirements/spec isolated.
    for package in ("rat", "reasoning"):
        (tmp_path / package).symlink_to(ROOT / package, target_is_directory=True)
    for name in ("pdf.py", "vision.py", "tesseract.py"):
        (tmp_path / "document_intake" / name).touch()
    return tmp_path


def test_source_packaging_contract():
    assert check_packaging(check_environment=False)["errors"] == []


def test_runtime_dependency_exclusions_are_rejected(package_tree):
    path = package_tree / "rat.spec"
    path.write_text(path.read_text().replace("excludes=[", "excludes=['sklearn', 'scipy',"))
    errors = check_packaging(package_tree, check_environment=False)["errors"]
    assert "runtime dependency excluded: sklearn" in errors
    assert "runtime dependency excluded: scipy" in errors


def test_undeclared_reasoning_dependency_is_rejected(package_tree):
    path = package_tree / "requirements.txt"
    path.write_text(path.read_text().replace("gymnasium>=0.29", ""))
    assert "desktop dependency undeclared: gymnasium" in check_packaging(package_tree, check_environment=False)["errors"]


def test_missing_installed_dependency_is_reported(monkeypatch):
    original = importlib.metadata.version
    def version(name):
        if name == "scikit-learn":
            raise importlib.metadata.PackageNotFoundError(name)
        return original(name)
    monkeypatch.setattr(importlib.metadata, "version", version)
    result = check_packaging()
    assert result["status"] == "failed"
    assert "not installed: scikit-learn>=1.3" in result["errors"]


def test_preflight_imports_no_application_or_inference_modules():
    code = "from scripts.check_packaging import check_packaging; import sys; "
    code += "assert not check_packaging(check_environment=False)['errors']; "
    code += "assert not any(n in sys.modules for n in ('rat','reasoning','mlx','mlx_lm','fastembed','PyQt6','objc'))"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_qt_import_failure_is_reported_before_build(monkeypatch):
    from types import SimpleNamespace
    from scripts import check_packaging as checker
    monkeypatch.setattr(checker.subprocess, "run", lambda *a, **k: SimpleNamespace(
        returncode=-6, stdout="", stderr="Incompatible processor: neon"))
    result = checker.check_packaging(check_environment=False, probe_qt=True)
    assert result["status"] == "failed"
    assert result["qt_probe"]["exit_code"] == -6


def test_qt_probe_timeout_is_reported(monkeypatch):
    from scripts import check_packaging as checker
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])
    monkeypatch.setattr(checker.subprocess, "run", timeout)
    result = checker.check_packaging(check_environment=False, probe_qt=True)
    assert result["status"] == "failed"
    assert result["qt_probe"]["error_type"] == "TimeoutExpired"


def test_dmg_only_missing_app_preserves_existing_outputs(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/build_app.sh", scripts / "build_app.sh")
    sentinel = tmp_path / "dist/keep.txt"
    sentinel.parent.mkdir()
    sentinel.write_text("existing output")
    result = subprocess.run(["bash", str(scripts / "build_app.sh"), "--dmg-only"], capture_output=True, text=True)
    assert result.returncode == 1
    assert sentinel.read_text() == "existing output"
    assert "requires an existing" in result.stderr or "requires macOS" in result.stderr


def test_failed_preflight_cannot_delete_previous_app_or_build(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(ROOT / "scripts/build_app.sh", scripts / "build_app.sh")
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    uname = fake_bin / "uname"
    uname.write_text("#!/bin/sh\nprintf 'Darwin\\n'\n")
    uname.chmod(0o755)
    python = fake_bin / "python"
    python.write_text("#!/bin/sh\nprintf 'fixture: missing build dependency\\n' >&2\nexit 23\n")
    python.chmod(0o755)
    sentinels = [tmp_path / "dist/rat.app/keep.txt", tmp_path / "build/rat/keep.txt"]
    for sentinel in sentinels:
        sentinel.parent.mkdir(parents=True)
        sentinel.write_text("previous output")
    env = dict(os.environ, PYTHON_BIN=str(python), PATH=str(fake_bin) + os.pathsep + os.environ["PATH"])
    result = subprocess.run(["bash", str(scripts / "build_app.sh")], env=env, capture_output=True, text=True)
    assert result.returncode == 23
    assert all(sentinel.read_text() == "previous output" for sentinel in sentinels)
