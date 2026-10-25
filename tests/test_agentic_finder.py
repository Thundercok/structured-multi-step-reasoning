"""Tests for RAT-FIND-01: Agentic Progressive Finder Capability and FinderVerifier.

Verifies:
1. find_file_or_app reasoning tool execution via ActionDispatcher.
2. FinderVerifier: PASS on valid authentic paths, FAIL on hallucinated/nonexistent paths.
3. SoL-Pi Observation Pack formatting: compact representation reducing prompt tokens.
4. view_finder_results: ViewSpec projection for UI presentation.
5. QuickPDFController.findFileOrApp: integration through ActionDispatcher.
"""
from __future__ import annotations

from pathlib import Path
import plistlib
import sys
import tempfile
import pytest

from rat.crawler.db import Database
from rat.engine.app_resolver import ApplicationCatalog
from rat.engine.verification import ExecutionEvidence, FinderVerifier, VerificationStatus
from rat.kernel import ActionDispatcher, ArtifactStore, build_default_registry
from rat.kernel.capabilities.finder import (
    create_finder_capability,
    deterministic_finder,
    finder_observation_pack,
)
from rat.kernel.capabilities.views import view_finder_results
from rat.kernel.contracts import Artifact


def create_fixture_app(root: Path, name: str, bundle_id: str = "com.rat.fixture", executable: bool = True) -> Path:
    app_path = root / f"{name}.app"
    macos_dir = app_path / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    info_plist = app_path / "Contents" / "Info.plist"
    info_plist.write_bytes(
        plistlib.dumps({
            "CFBundleIdentifier": bundle_id,
            "CFBundleName": name,
            "CFBundleExecutable": "fixture-exec",
        })
    )
    if executable:
        (macos_dir / "fixture-exec").write_text("#!/bin/sh\necho fixture")
    return app_path


@pytest.fixture
def finder_env(tmp_path):
    apps_dir = tmp_path / "Applications"
    apps_dir.mkdir()
    app_calc = create_fixture_app(apps_dir, "Calculator", "com.apple.calculator")
    app_game = create_fixture_app(apps_dir, "League of Legends", "com.riotgames.leagueoflegends")

    catalog = ApplicationCatalog.scan([apps_dir])

    db_path = tmp_path / "finder_test.db"
    db = Database(str(db_path))

    # Add real files
    doc_slide = tmp_path / "bai_giang_tuan_3.pptx"
    doc_slide.write_text("Slide noi dung cau truc du lieu va giai thuat")
    db.upsert_document({
        "file_path": str(doc_slide),
        "file_name": doc_slide.name,
        "file_ext": ".pptx",
        "file_size": doc_slide.stat().st_size,
        "created_at": 1000.0,
        "modified_at": 1000.0,
        "indexed_at": 1000.0,
        "content_text": "Slide noi dung cau truc du lieu va giai thuat cay nhi phan",
        "summary": "Slide bai giang giai thuat",
    })

    doc_report = tmp_path / "bao_cao_tai_chinh.pdf"
    doc_report.write_text("%PDF-1.4 mock pdf content")
    db.upsert_document({
        "file_path": str(doc_report),
        "file_name": doc_report.name,
        "file_ext": ".pdf",
        "file_size": doc_report.stat().st_size,
        "created_at": 2000.0,
        "modified_at": 2000.0,
        "indexed_at": 2000.0,
        "content_text": "Bao cao tai chinh quy 3 nam 2026 doanh thu chi phi",
        "summary": "Bao cao tai chinh quy 3",
    })

    return {
        "tmp_path": tmp_path,
        "apps_dir": apps_dir,
        "catalog": catalog,
        "db": db,
        "app_calc": app_calc,
        "app_game": app_game,
        "doc_slide": doc_slide,
        "doc_report": doc_report,
    }


def test_find_file_or_app_deterministic(finder_env):
    """Test deterministic finder retrieves matching apps and files."""
    db = finder_env["db"]
    cat = finder_env["catalog"]

    # Search for an app by Vietnamese alias
    res_app = deterministic_finder("Liên Minh", db=db, catalog=cat)
    assert res_app["hit_count"] >= 1
    hit_app = res_app["hits"][0]
    assert hit_app["kind"] == "application"
    assert "League of Legends" in hit_app["title"]

    # Search for a slide
    res_slide = deterministic_finder("slide bài giảng", db=db, catalog=cat)
    assert res_slide["hit_count"] >= 1
    hit_slide = next(h for h in res_slide["hits"] if h["kind"] == "file")
    assert hit_slide["title"] == "bai_giang_tuan_3.pptx"

    # Search for a report
    res_report = deterministic_finder("báo cáo tài chính", db=db, catalog=cat)
    assert res_report["hit_count"] >= 1
    hit_rep = next(h for h in res_report["hits"] if h["kind"] == "file")
    assert hit_rep["title"] == "bao_cao_tai_chinh.pdf"
    assert hit_rep["is_pdf"] is True


def test_finder_verifier_pass(finder_env):
    """FinderVerifier PASS on authentic local resources."""
    db = finder_env["db"]
    cat = finder_env["catalog"]
    verifier = FinderVerifier()

    res = deterministic_finder("báo cáo tài chính", db=db, catalog=cat)
    ev = ExecutionEvidence(
        id="ev-1",
        operation="find_file_or_app",
        args={"query": "báo cáo tài chính"},
        result=res,
        sha256="fake-sha",
    )
    report = verifier.check_execution(ev)
    assert report.status == VerificationStatus.PASS
    assert "Toàn bộ tệp và ứng dụng" in report.reason


def test_finder_verifier_fail_on_hallucinated_file(finder_env):
    """FinderVerifier FAIL when a non-existent file path is returned."""
    verifier = FinderVerifier()
    res = {
        "query": "tài liệu bí mật",
        "hit_count": 1,
        "hits": [
            {
                "resource_id": "doc-fake",
                "kind": "file",
                "title": "secret.pdf",
                "path": "/nonexistent/secret.pdf",
            }
        ],
    }
    ev = ExecutionEvidence(
        id="ev-2",
        operation="find_file_or_app",
        args={"query": "tài liệu bí mật"},
        result=res,
        sha256="fake-sha",
    )
    report = verifier.check_execution(ev)
    assert report.status == VerificationStatus.FAIL
    assert "không tồn tại trên ổ đĩa" in report.reason


def test_finder_verifier_fail_on_broken_app(finder_env, tmp_path):
    """FinderVerifier FAIL when an invalid application without executable is returned."""
    verifier = FinderVerifier()
    broken_app = create_fixture_app(tmp_path, "BrokenApp", executable=False)
    res = {
        "query": "BrokenApp",
        "hit_count": 1,
        "hits": [
            {
                "resource_id": "app-broken",
                "kind": "application",
                "title": "BrokenApp",
                "path": str(broken_app),
            }
        ],
    }
    ev = ExecutionEvidence(
        id="ev-3",
        operation="find_file_or_app",
        args={"query": "BrokenApp"},
        result=res,
        sha256="fake-sha",
    )
    report = verifier.check_execution(ev)
    assert report.status == VerificationStatus.FAIL
    assert "không hợp lệ" in report.reason


def test_finder_observation_pack_compression(finder_env):
    """SoL-Pi Observation Pack for finder significantly reduces prompt context."""
    db = finder_env["db"]
    cat = finder_env["catalog"]

    res = deterministic_finder("báo cáo", db=db, catalog=cat)
    res["artifact_id"] = "art-finder-test"

    pack = finder_observation_pack(res)
    assert pack["artifact_ref"] == "art-finder-test"
    assert pack["hit_count"] == res["hit_count"]
    assert len(pack["top_candidates"]) <= 5
    assert pack["status"] == "finder_results_available"


def test_action_dispatcher_find_file_or_app(finder_env):
    """Verify ActionDispatcher dispatches find_file_or_app and commits artifact to ArtifactStore."""
    db = finder_env["db"]
    cat = finder_env["catalog"]

    registry = build_default_registry(db=db)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)

    res = dispatcher.execute_operation(
        "find_file_or_app",
        {"query": "Liên Minh", "resource_kind": "any"},
        context={"db": db, "catalog": cat, "platform": "darwin"},
    )
    assert res.status == "success"
    art = res.artifact
    assert art is not None
    assert art.kind == "finder_results"
    assert art.payload["hit_count"] >= 1
    assert any(h["kind"] == "application" for h in art.payload["hits"])

    # Check store has artifact
    stored = store.get(art.id)
    assert stored is not None
    assert stored.payload["query"] == "Liên Minh"


def test_view_finder_results_spec(finder_env):
    """view_finder_results formats a clean ViewSpec with summary and table blocks."""
    db = finder_env["db"]
    cat = finder_env["catalog"]

    res = deterministic_finder("báo cáo tài chính", db=db, catalog=cat)
    artifact = Artifact(
        id="art-find-view",
        revision=1,
        kind="finder_results",
        title="Truy hồi · báo cáo tài chính",
        payload=res,
        inputs={"query": "báo cáo tài chính"},
    )

    view_spec = view_finder_results(artifact, {})
    assert view_spec.title == "Truy hồi · báo cáo tài chính"
    assert len(view_spec.blocks) >= 2
    assert view_spec.blocks[0].type == "summary"
    assert view_spec.blocks[1].type == "table"


def test_assistant_runtime_agent_loop_calls_finder(finder_env):
    """Verify find_file_or_app is reachable and executable from the Agent loop in AssistantRuntime."""
    from unittest.mock import patch
    from rat.engine.assistant_runtime import AssistantRuntime

    db = finder_env["db"]
    cat = finder_env["catalog"]
    registry = build_default_registry(db=db)
    runtime = AssistantRuntime(db=db, registry=registry)
    runtime.use_live_model = True
    # inject mock catalog for testing
    finder_cap = create_finder_capability(db=db, catalog=cat)
    runtime.registry.get_operation("find_file_or_app").handler = (
        lambda args, **ctx: finder_cap.operations["find_file_or_app"].handler(args, **{**ctx, "catalog": cat})
    )

    tool_call = {
        "function": {
            "name": "find_file_or_app",
            "arguments": {"query": "Liên Minh", "resource_kind": "any"},
        }
    }
    replies = [
        {"message": {"role": "assistant", "content": "", "tool_calls": [tool_call]}, "prompt_tokens": 100, "completion_tokens": 20},
        {"message": {"role": "assistant", "content": "Tôi đã tìm thấy ứng dụng League of Legends."}, "prompt_tokens": 150, "completion_tokens": 30},
    ]
    with patch("rat.engine.slm.slm_engine.chat_with_meta", side_effect=replies):
        result = runtime.run("Mở hoặc tìm game Liên Minh giúp tôi")

    assert result.error is None
    assert result.tool_call_count == 1
    assert "League of Legends" in result.answer
    # Check verification report
    assert any(v["status"] == "PASS" and "grounding" in v["scope"] for v in result.steps[0].verification)
    # Check that artifact is committed to artifact store
    arts = runtime.artifact_store.find_by_kind("finder_results")
    assert len(arts) >= 1
    assert arts[0].payload["query"] == "Liên Minh"
    assert any(h["title"] == "League of Legends" for h in arts[0].payload["hits"])

