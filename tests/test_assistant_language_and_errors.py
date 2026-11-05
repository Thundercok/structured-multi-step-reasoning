"""Tests for assistant language mismatch retry and cause-specific failure messages."""
from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from PyQt6.QtGui import QGuiApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.language_check import is_mainly_cjk, is_vietnamese, reads_as_english
from rat.engine.selected_document_qa import answer_selected_document
from rat.timetable.compositor import TimetableCompositor
from rat.ui.quick_pdf_controller import QuickPDFController, describe_execution_error


def test_language_check_helpers():
    # Vietnamese detection
    assert is_vietnamese("app chỉnh ảnh") is True
    assert is_vietnamese("báo cáo tài chính quý 3") is True
    assert is_vietnamese("Quy chế đào tạo") is True
    assert is_vietnamese("What is this file?") is False
    assert is_vietnamese("") is False

    # CJK detection
    assert is_mainly_cjk("对不起，我没有找到…") is True
    assert is_mainly_cjk("Xin lỗi, tôi không tìm thấy tài liệu.") is False
    assert is_mainly_cjk("Lý Bạch (李白) là nhà thơ đời Đường.") is False
    assert is_mainly_cjk("") is False


def test_vietnamese_query_cjk_answer_retried_successfully(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("Dữ liệu thử nghiệm.")
    db = Database(str(tmp_path / "index.db"))
    db.upsert_document({
        "file_path": str(path),
        "file_name": path.name,
        "file_ext": ".txt",
        "file_size": path.stat().st_size,
        "created_at": 1,
        "modified_at": 1,
        "indexed_at": 1,
        "content_text": path.read_text(),
    })

    client = Mock()
    # First call returns Chinese; second call (retry) returns Vietnamese
    client.chat_with_meta.side_effect = [
        {
            "message": {"role": "assistant", "content": "对不起，我没有找到任何相关文件。"},
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "done_reason": "stop",
            "error": None,
        },
        {
            "message": {"role": "assistant", "content": "Xin lỗi, tôi không tìm thấy tài liệu phù hợp."},
            "prompt_tokens": 120,
            "completion_tokens": 15,
            "done_reason": "stop",
            "error": None,
        },
    ]

    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    resp = answer_selected_document(runtime, "Tìm tài liệu trong tệp này", str(path), model_client=client)

    assert client.chat_with_meta.call_count == 2
    # Verify retry instruction was passed
    retry_messages = client.chat_with_meta.call_args_list[1][0][0]
    assert any("tiếng Việt" in m["content"] for m in retry_messages)
    assert resp.error is None
    assert resp.answer == "Xin lỗi, tôi không tìm thấy tài liệu phù hợp."
    db.get_connection().close()


def test_vietnamese_query_cjk_answer_retried_fails_honest_error(tmp_path):
    path = tmp_path / "test.txt"
    path.write_text("Dữ liệu thử nghiệm.")
    db = Database(str(tmp_path / "index.db"))
    db.upsert_document({
        "file_path": str(path),
        "file_name": path.name,
        "file_ext": ".txt",
        "file_size": path.stat().st_size,
        "created_at": 1,
        "modified_at": 1,
        "indexed_at": 1,
        "content_text": path.read_text(),
    })

    client = Mock()
    # Both calls return Chinese
    client.chat_with_meta.side_effect = [
        {
            "message": {"role": "assistant", "content": "对不起，我没有找到任何相关文件。"},
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "done_reason": "stop",
            "error": None,
        },
        {
            "message": {"role": "assistant", "content": "对不起，我还是无法找到。"},
            "prompt_tokens": 120,
            "completion_tokens": 15,
            "done_reason": "stop",
            "error": None,
        },
    ]

    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
    resp = answer_selected_document(runtime, "Tìm tài liệu trong tệp này", str(path), model_client=client)

    assert client.chat_with_meta.call_count == 2
    assert resp.error == "language_mismatch"
    assert not resp.answer  # Must not return the CJK text!
    db.get_connection().close()


def test_controller_language_mismatch_shows_honest_error():
    app = QGuiApplication.instance() or QGuiApplication([])
    controller = QuickPDFController(auto_init_finder=False)
    controller.ready()
    try:
        from rat.engine.assistant_runtime import AgentResponse

        # Simulate execution response where model returned CJK
        turn = controller.conversation.begin_turn("app chỉnh ảnh")
        controller._current_turn_id = turn.turn_id
        controller._current_execution_id = turn.execution_id
        controller._last_user_query = "app chỉnh ảnh"
        controller._current_worker = Mock()

        cjk_resp = AgentResponse(
            answer="对不起，我没有找到…",
            steps=[],
            total_time_ms=100,
            tool_call_count=0,
            token_estimate=10,
            execution_id=turn.execution_id,
        )

        controller._on_execution_response(cjk_resp)
        snap = controller.snapshot
        assert snap["view"] == "answer"
        assert snap["answerText"] == ""
        assert "tiếng Việt" in snap["status"]
        assert "Yêu cầu chưa hoàn tất" not in snap["status"]
    finally:
        controller.close()


def test_describe_execution_error_replaces_generic_message():
    # Never returns generic "Yêu cầu chưa hoàn tất"
    errors = [
        "budget_exceeded",
        "timeout",
        "unresolved",
        "cancelled",
        "empty_model_response",
        "language_mismatch",
        "step_budget_exhausted",
        "token_budget_exhausted",
        "task_plan_failed:json_decode_error",
        "task_plan_failed:Connection refused",
        "unknown_tool:search_photos",
        "<urlopen error [Errno 61] Connection refused>",
        "selected_document_read_failed",
    ]
    for err in errors:
        msg = describe_execution_error(err)
        assert msg != "Yêu cầu chưa hoàn tất"
        assert len(msg) > 10


@pytest.mark.parametrize("text, english", [
    ("The deposit for a rental room is 7,000,000 VND.", True),
    ("Based on the rental agreement document I found, the deposit (tiền cọc) for a rental room is 7.000.000 đồng.", True),
    ("I don't have access to any information about a host.", True),
    ("Tiền cọc phòng trọ là 7.000.000 đồng.", False),
    ("Hợp đồng thuê hết hạn vào ngày 30 tháng 6 năm 2027.", False),
    ("TCP là giao thức có kết nối, còn UDP thì không.", False),
    ("Transformer là một kiến trúc mạng dùng cơ chế attention.", False),
    ("Tệp `the file is in the folder` đã được mở.", False),
    ("```python\nfor item in the_list:\n    print(item)\n```", False),
    ("Paris", False),
    ("", False),
])
def test_reads_as_english(text, english):
    assert reads_as_english(text) is english
