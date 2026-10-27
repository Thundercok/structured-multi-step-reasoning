"""Diagnostic contracts only; these tests do not establish live app acceptance."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import check_rat_mini as check


def test_default_report_does_not_search_or_launch_translation(monkeypatch):
    monkeypatch.setattr(check, "vector_probe", lambda deps: {"status": "unavailable"})
    monkeypatch.setattr(check, "spotlight_probe", lambda *args: pytest.fail("implicit search"))
    report = check.collect_report()
    assert report["spotlight"]["status"] == "not_run"
    assert report["native_translation"]["status"] == "not_run"
    assert report["target"]["actual_target_tested"] is False
    assert report["embedding"]["status"] == "not_run"


def test_probe_import_is_headless_and_does_not_read_app_config():
    code = "import scripts.check_rat_mini, sys; "
    code += "assert not any(x in sys.modules for x in ('rat','PyQt6','objc','numpy','mlx','fastembed','onnxruntime'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_scope_and_filename_must_be_explicit_together(tmp_path):
    with pytest.raises(ValueError, match="together"):
        check.collect_report(scope=tmp_path)
    with pytest.raises(ValueError, match="single filename"):
        check.spotlight_probe(tmp_path, "../secret.txt")


def test_spotlight_does_not_trust_out_of_scope_or_missing_hits(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    wanted = root / 'a"b.txt'
    wanted.write_text("readable")
    outside = tmp_path / wanted.name
    outside.write_text("outside")
    link = root / "link"
    link.symlink_to(outside)
    seen = []
    def run(argv, **kwargs):
        seen.append(argv)
        return {"exit_code": 0, "stdout": "\0".join(map(str, [wanted, link, root / "gone"])), "stderr": ""}
    monkeypatch.setattr(check.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(check.shutil, "which", lambda name: "/usr/bin/mdfind")
    monkeypatch.setattr(check, "_run", run)
    result = check.spotlight_probe(root, wanted.name)
    assert result["verified_readable_hits"] == 1
    assert result["out_of_scope_hits"] == 1
    assert result["unreadable_or_stale_hits"] == 1
    assert str(outside) not in json.dumps(result)
    assert seen[0][-1] == 'kMDItemFSName == "a\\"b.txt"'


@pytest.mark.parametrize("result,reason", [
    ({"error": "timeout"}, "timeout"),
    ({"exit_code": -6, "stdout": "", "stderr": "native crash"}, "native_probe_failed"),
    ({"exit_code": 0, "stdout": "invalid", "stderr": ""}, "invalid_probe_response"),
])
def test_vector_probe_reports_timeout_crash_and_bad_json(monkeypatch, result, reason):
    monkeypatch.setattr(check, "_run", lambda *a, **k: result)
    assert check.vector_probe()["reason"] == reason


def test_frozen_vector_probe_uses_own_child_mode_not_python_flag(monkeypatch):
    commands = []
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    def run(command, **kwargs):
        commands.append(command)
        return {"exit_code": 0, "stdout": '{"status":"passed"}', "stderr": ""}
    monkeypatch.setattr(check, "_run", run)
    assert check.vector_probe()["status"] == "passed"
    assert commands == [[sys.executable, "--vector-child"]]


def test_embedding_bundle_hash_verified_before_inference_imports(tmp_path):
    from scripts.check_rat_mini_embedding import verify_bundle
    payload = b"not a model: checksum validation fixture"
    (tmp_path / "asset").write_bytes(payload)
    entry = {"rfilename": "asset", "size": len(payload),
             "lfs": {"sha256": hashlib.sha256(payload).hexdigest()}}
    manifest = {"files": [entry], "selected_bytes": len(payload)}
    size, observed = verify_bundle(tmp_path, manifest)
    assert size == len(payload) and observed[0]["sha256"] == entry["lfs"]["sha256"]
    (tmp_path / "asset").write_bytes(b"x" * len(payload))
    with pytest.raises(ValueError, match="SHA256"):
        verify_bundle(tmp_path, manifest)


def test_embedding_bundle_rejects_symlink_escape(tmp_path):
    from scripts.check_rat_mini_embedding import verify_bundle
    root = tmp_path / "model"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"x")
    (root / "asset").symlink_to(outside)
    with pytest.raises(ValueError, match="outside bundle"):
        verify_bundle(root, {"files": [{"rfilename": "asset"}]})
