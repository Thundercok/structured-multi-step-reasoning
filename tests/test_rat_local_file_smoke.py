"""Collector contracts on artificial local PDFs and HTTP fixtures; no inference."""
import io
import json
import sqlite3
from types import SimpleNamespace

import pytest
from pypdf import PdfWriter

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AgentResponse
from rat.kernel.contracts import Artifact
from scripts import run_dsa_core_smoke as shared
from scripts import run_rat_local_file_smoke as smoke


@pytest.fixture
def source(tmp_path):
    pdf = tmp_path / "academic-source.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with pdf.open("wb") as stream:
        writer.write(stream)
    db_path = tmp_path / "fixture-index.db"
    db = Database(str(db_path))
    db.upsert_document({"file_path": str(pdf), "file_name": pdf.name, "file_ext": ".pdf",
                        "file_size": pdf.stat().st_size, "created_at": 1, "modified_at": 1,
                        "indexed_at": 1, "content_text": "Artificial fixture metadata"})
    db.get_connection().close()
    return pdf, db_path


def fake_http(monkeypatch, *, include_counts=True):
    observed = []
    def reply(request, timeout):
        observed.append((json.loads(request.data), timeout))
        data = {"message": {"content": "Fixture response"}, "done": True}
        if include_counts:
            data.update(prompt_eval_count=7, eval_count=3)
        return io.BytesIO(json.dumps(data).encode())
    monkeypatch.setattr(shared.urllib.request, "urlopen", reply)
    return observed


def test_global_budget_counts_planning_calls_and_caps_each_http_request(monkeypatch, tmp_path):
    observed = fake_http(monkeypatch, include_counts=False)
    client = smoke.BoundedSLMEngine(model="fixture", timeout_s=60, max_calls=1)
    client.record_path = tmp_path / "calls.jsonl"
    client.record_path.touch()
    client.chat_with_meta([], [], timeout=120, max_tokens=8000, response_format={"type": "object"})
    with pytest.raises(smoke.ModelCallBudgetExceeded):
        client.chat_with_meta([], [])
    assert len(observed) == client.calls_started == 1
    assert observed[0][0]["options"]["num_predict"] == 640
    assert observed[0][1] == 60
    assert client.budget_rejections == 1
    record = json.loads(client.record_path.read_text())
    assert record["token_usage_known"] is False
    assert record["prompt_tokens"] is record["completion_tokens"] is record["total_tokens"] is None
    assert smoke.token_accounting(client.call_Records)["total_tokens"] is None


def test_output_rejects_reuse_tracked_paths_and_symlink_escape(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(smoke, "REPO_ROOT", repo)
    with pytest.raises(ValueError, match="outside the repository"):
        smoke.validate_output_path(repo / "audit" / "private-run")
    existing = tmp_path / "old-evidence"
    existing.mkdir()
    with pytest.raises(ValueError, match="fresh"):
        smoke.validate_output_path(existing)
    (repo / ".rat").symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError, match="outside the repository"):
        smoke.validate_output_path(repo / ".rat" / "would-be-tracked")


def test_ignored_rat_output_requires_git_ignore_confirmation(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setattr(smoke, "REPO_ROOT", repo)
    checks = []
    def check_ignore(command, **kwargs):
        checks.append(command)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(smoke.subprocess, "run", check_ignore)
    with pytest.raises(ValueError, match="must be ignored"):
        smoke.validate_output_path(repo / ".rat" / "run")
    assert checks[0][:3] == ["git", "check-ignore", "--quiet"]
    monkeypatch.setattr(smoke.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    assert smoke.validate_output_path(repo / ".rat" / "run") == repo / ".rat" / "run"


def test_source_preflight_requires_exact_indexed_pdf_and_cannot_write_index(source, tmp_path):
    pdf, db_path = source
    db = Database(str(db_path), read_only=True)
    metadata = smoke.validate_source(pdf, db)
    assert metadata["page_count"] == 1 and metadata["path"] == str(pdf)
    assert metadata["sha256"] == smoke.file_fingerprint(pdf)["sha256"]
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        db.get_connection().execute("DELETE FROM documents")
    unindexed = tmp_path / "unindexed.pdf"
    unindexed.write_bytes(pdf.read_bytes())
    with pytest.raises(ValueError, match="already be indexed"):
        smoke.validate_source(unindexed, db)
    db.get_connection().close()


def attachment(source_metadata, **overrides):
    payload = {"path": source_metadata["path"], "filename": source_metadata["filename"],
               "size_bytes": source_metadata["size_bytes"], "sha256": source_metadata["sha256"],
               "delivered": True, "found": True, "delivery": "local_reference", **overrides}
    return Artifact(id="fixture-delivery", kind="document_file", payload=payload,
                    provenance={"operation_name": "deliver_document"})


def test_delivery_verification_checks_file_bytes_not_prose_or_delivered_flag(source, tmp_path, monkeypatch):
    pdf, _ = source
    metadata = smoke.file_fingerprint(pdf)
    assert smoke.verify_file_artifacts([attachment(metadata)], metadata)[0]["verified_local_reference"]
    assert not smoke.verify_file_artifacts([attachment(metadata, sha256="invented")], metadata)[0]["verified_local_reference"]
    assert smoke.verify_file_artifacts([Artifact(id="prose", kind="text", payload={"delivered": True})], metadata) == []
    other = tmp_path / "another.pdf"
    other.write_bytes(pdf.read_bytes())
    # The collector must not read bytes from another path suggested by the model.
    monkeypatch.setattr(smoke, "file_fingerprint", lambda p: pytest.fail("unrelated path was hashed"))
    observed = smoke.verify_file_artifacts([attachment(metadata, path=str(other))], metadata)[0]
    assert observed["error"] == "attachment_target_mismatch"
    assert observed["verified_local_reference"] is False


def test_changed_source_invalidates_previously_delivered_metadata(source):
    pdf, _ = source
    metadata = smoke.file_fingerprint(pdf)
    artifact = attachment(metadata)
    with pdf.open("ab") as stream:
        stream.write(b"\n% fixture changed\n")
    observed = smoke.verify_file_artifacts([artifact], metadata)[0]
    assert observed["checks"]["source_unchanged"] is False
    assert observed["verified_local_reference"] is False


@pytest.mark.parametrize('native_limits', [False, True])
def test_collector_records_three_turns_with_context_and_read_only_index(source, tmp_path, monkeypatch, native_limits):
    pdf, db_path = source
    index_before = db_path.read_bytes()
    observed_http = fake_http(monkeypatch)
    calls = []
    class FixtureRuntime:
        def __init__(self, *, db, compositor, use_live_model, plan_tasks, discover_tools, structured_context, model_client):
            self.db, self.client = db, model_client
            assert db.read_only and use_live_model
            with pytest.raises(sqlite3.OperationalError):
                db.get_connection().execute("DELETE FROM documents")
        def run(self, query, **kwargs):
            calls.append(kwargs)
            self.client.chat_with_meta([{"role": "user", "content": query}], [])
            artifacts = [attachment(smoke.file_fingerprint(pdf))] if len(calls) == 3 else []
            return AgentResponse(answer=f"Fixture answer {len(calls)}", steps=[], total_time_ms=1,
                                 tool_call_count=0, token_estimate=0, artifacts=artifacts,
                                 is_live_model=True, execution_id=kwargs["execution_id"],
                                 turn_id=kwargs["turn_ref"].turn_id, task_state={"fixture": len(calls)},
                                 task_state_updated=True, sources=[{"path": str(pdf)}])
    monkeypatch.setattr(smoke, "AssistantRuntime", FixtureRuntime)
    output = tmp_path / "private-run"
    report = smoke.run_local_file_smoke(file_path=pdf, output=output, model="fixture",
                                       db_path=db_path, requests=["Locate", "Cite that page", "Send that file"],
                                       native_limits=native_limits, max_steps=8 if native_limits else 5,
                                       timeout_s=90 if native_limits else 60)
    assert report["collection_status"] == "completed" and len(report["turns"]) == 3
    assert report["review_status"] == "pending" and report["quality_success"] is None
    assert report["native_click_observed"] is False
    assert report["token_accounting"]["total_tokens"] == 30
    assert len(observed_http) == report["model_calls_started"] == 3
    assert {timeout for _, timeout in observed_http} == {90 if native_limits else 60}
    assert {call['max_steps'] for call in calls} == {8 if native_limits else 5}
    assert report['configuration']['native_limits'] is native_limits
    assert report['native_equivalence_verified'] is False
    assert calls[1]["history"][-1]["content"] == "Fixture answer 1"
    assert calls[1]["task_state"] == {"fixture": 1}
    assert calls[2]["previous_sources"] == [{"path": str(pdf)}]
    assert all(turn["execution_id_matched"] for turn in report["turns"])
    observed = report["turns"][2]["file_attachment_observations"][0]
    assert observed["verified_local_reference"] is True
    assert not list(output.glob("*.pdf"))
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / "report.json").stat().st_mode & 0o777 == 0o600
    recorded = json.loads((output / "report.json").read_text())
    assert recorded["privacy"]["do_not_commit_or_upload"] is True
    assert recorded["database"]["read_only"] is True
    assert db_path.read_bytes() == index_before


def test_collector_preserves_raw_journal_when_global_budget_stops_a_turn(source, tmp_path, monkeypatch):
    pdf, db_path = source
    requests = fake_http(monkeypatch)
    class BudgetFixtureRuntime:
        def __init__(self, **kwargs):
            self.client = kwargs["model_client"]
        def run(self, query, **kwargs):
            self.client.chat_with_meta([], [])
            self.client.chat_with_meta([], [])
            pytest.fail("global call limit was not enforced")
    monkeypatch.setattr(smoke, "AssistantRuntime", BudgetFixtureRuntime)
    output = tmp_path / "budget-run"
    report = smoke.run_local_file_smoke(file_path=pdf, output=output, db_path=db_path,
                                       model="fixture", max_model_calls=1)
    assert report["collection_status"] == "budget_exhausted"
    assert report["model_calls_started"] == len(requests) == 1
    assert report["budget_rejections"] == 1
    assert report["quality_success"] is None and report["review_status"] == "pending"
    records = (output / "raw_model_calls.jsonl").read_text().splitlines()
    assert len(records) == 1 and json.loads(records[0])["total_tokens"] == 10


@pytest.mark.parametrize("overrides", [
    {"max_steps": 6}, {"timeout_s": 61}, {"timeout_s": float("nan")},
    {"max_model_calls": 16}, {"requests": ["one"] * 4},
    {"native_limits": True, "max_steps": 9}, {"native_limits": True, "timeout_s": 91},
])
def test_invalid_budget_fails_before_db_output_or_http(tmp_path, monkeypatch, overrides):
    monkeypatch.setattr(smoke, "Database", lambda *a, **kw: pytest.fail("database opened"))
    output = tmp_path / "must-not-be-created"
    with pytest.raises(ValueError):
        smoke.run_local_file_smoke(file_path=tmp_path / "unused.pdf", output=output,
                                   model="fixture", **overrides)
    assert not output.exists()
