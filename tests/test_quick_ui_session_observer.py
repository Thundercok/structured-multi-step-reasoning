"""Dev-observer safety contracts; no model responses or UI acceptance fixtures."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from scripts.run_rat_quick_ui_session import CallLedger, public_data, python_changes


def test_inflight_and_failed_requests_both_consume_global_cap(tmp_path):
    ledger = CallLedger(tmp_path, 1)
    call_id = ledger.begin("local", [], [])
    with pytest.raises(RuntimeError, match="budget_exhausted"):
        ledger.begin("local", [], [])
    ledger.finish(call_id, {"error": "timeout", "token_usage_known": False})
    with pytest.raises(RuntimeError, match="budget_exhausted"):
        ledger.begin("local", [], [])
    assert ledger.summary()[0]["error"] == "timeout"
    assert ledger.summary()[0]["prompt_tokens"] is None
    assert len(json.loads((tmp_path / "model-calls.json").read_text())) == 1


def test_concurrent_reservations_cannot_exceed_cap(tmp_path):
    ledger = CallLedger(tmp_path, 1)

    def reserve(_):
        try:
            return ledger.begin("local", [], [])
        except RuntimeError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(4)))
    assert results.count(1) == 1
    assert results.count(None) == 3


def test_private_model_fields_are_removed_recursively():
    assert public_data({"raw_response": {"thinking": "private", "message": {
        "reasoning_content": "private", "content": ""}}, "request": {"messages": []}}) == {
        "raw_response": {"message": {"content": ""}}, "request": {"messages": []}}


def test_qml_changes_reload_but_python_add_remove_or_edit_require_restart():
    before = {"desk.qml": "old", "worker.py": "same", "old.py": "old"}
    assert python_changes(before, {**before, "desk.qml": "new"}) == []
    assert python_changes(before, {"desk.qml": "new", "worker.py": "changed", "new.py": "new"}) == [
        "new.py", "old.py", "worker.py"]
