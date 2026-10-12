"""Compatibility tests are software checks; live OCR is explicitly opt-in."""
import os
import pytest

pytest.importorskip("z3", reason="Optional invoice tests require requirements-docai.txt")
pytest.importorskip("openpyxl")
pytest.importorskip("pypdf")
pytest.importorskip("requests")
pytest.importorskip("PIL")


def pytest_collection_modifyitems(items):
    for item in items:
        if item.name == "test_real_ocr_tokens_from_generated_hardcore_zip" and os.getenv("NESY_RUN_LIVE_OCR") != "1":
            item.add_marker(pytest.mark.skip(reason="Live OCR on synthetic rendered images is opt-in: NESY_RUN_LIVE_OCR=1"))


@pytest.fixture(autouse=True)
def isolate_upstream_outputs(tmp_path, monkeypatch):
    # Legacy constructors write invoice_registry.db in cwd. Keep tests away
    # from personal ledgers and repository outputs.
    monkeypatch.chdir(tmp_path)
