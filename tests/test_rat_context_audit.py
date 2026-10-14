"""Validate offline context accounting and capture isolation; no AI measurement."""
import json
import sys

import pytest

from scripts import audit_rat_context as audit


def test_request_partition_accounts_for_multibyte_json_and_overhead():
    request = {"messages": [{"role": "system", "content": "Chuột"}, {"role": "user", "content": "Ghi giúp tôi 🐭"}],
               "tools": [{"name": "sample", "description": "đọc"}], "response_format": {"type": "object"}}
    result = audit.analyze_request(request)
    for unit in ("chars", "utf8_bytes"):
        assert sum(part[unit] for part in result["components"].values()) == result["total"][unit]
    assert result["total"]["utf8_bytes"] > result["total"]["chars"]


@pytest.mark.parametrize("same", [True, False])
def test_task_state_duplicate_requires_equal_structured_value(same):
    state = {"goal": "Đọc tài liệu", "remaining": ["Đọc"], "status": "in_progress"}
    other = state if same else {**state, "remaining": ["Ghi"]}
    request = {"messages": [
        {"role": "system", "content": "fixture"},
        {"role": "user", "content": "Previous model-authored task state: " + json.dumps(state)},
        {"role": "user", "content": json.dumps({"observation": {"task_state": other}})},
    ], "tools": []}
    assert bool(audit.analyze_request(request)["exact_task_state_duplicates"]) is same


def test_same_note_text_at_distinct_locations_is_not_marked_safe_to_remove():
    text = "Nguồn và trạng thái xác nhận phải được giữ riêng." * 2
    request = {"messages": [
        {"role": "user", "content": "Session work notes: " + json.dumps([{"text": text, "confirmed": True}])},
        {"role": "user", "content": "Prior replaced note versions: " + json.dumps([{"text": text, "confirmed": False}])},
    ], "tools": []}
    duplicate = audit.analyze_request(request)["repeated_text_values"][0]
    assert len(duplicate["locations"]) == 2
    assert duplicate["removal_safe_without_provenance_review"] is False


def test_cli_rejects_existing_output_before_running_fixtures(tmp_path, monkeypatch):
    output = tmp_path / "existing"
    output.mkdir()
    saved = output / "captures.json"
    saved.write_text("historical evidence")
    monkeypatch.setattr(sys, "argv", ["audit_rat_context", "--output", str(output)])
    monkeypatch.setattr(audit, "collect", lambda: pytest.fail("Fixtures must not execute on an existing output directory"))
    with pytest.raises(FileExistsError):
        audit.main()
    assert saved.read_text() == "historical evidence"


def test_native_mock_capture_restores_runtime_and_keeps_unmeasured_metrics_unknown():
    from rat.engine.assistant_runtime import AssistantRuntime
    original_call, original_run = AssistantRuntime._call_model, AssistantRuntime.run
    result = audit.collect()
    assert AssistantRuntime._call_model is original_call
    assert AssistantRuntime.run is original_run
    assert len(result.cases) == 12 and all(row["assertions_passed"] for row in result.cases)
    assert any(row["phase"] == "planner" for row in result.calls)
    assert any(row["phase"] == "actor" for row in result.calls)
    assert all(row["prompt_tokens"] is None and row["completion_tokens"] is None and row["server_durations"] is None for row in result.calls)
    assert all(sum(part["chars"] for part in row["measurements"]["components"].values()) == row["measurements"]["total"]["chars"] for row in result.calls)
