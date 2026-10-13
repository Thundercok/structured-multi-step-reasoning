"""App-only prompt/context helpers; no Qt, index, model or research run needed."""

import json

import pytest

from rat.ui.chat_session import (
    ConversationHistory,
    build_chat_prompt,
    extract_arithmetic_request,
    normalize_chat_request,
)


@pytest.mark.parametrize("query, expected", [
    ("Giúp tôi tính 2+2", "2+2"),
    ("Chuột ơi, 2+2 bằng bao nhiêu?", "2+2"),
    ("Chào chuột, giúp mình tính (12 - 2) / 5", "(12 - 2) / 5"),
    ("tính 2^3", "2**3"),
    ("12-4", "12-4"),
    ("= 5 % 2", "5 % 2"),
])
def test_extracts_only_complete_arithmetic_requests(query, expected):
    assert extract_arithmetic_request(query) == expected


@pytest.mark.parametrize("query", [
    "Tôi có 2 ý tưởng + 3 phương án, giúp chọn hướng",
    "Giúp tôi giải thích vì sao 2+2=4",
    "Tôi đang bực mình vì chưa nghĩ ra mở bài",
    "__import__('os').system('echo unsafe')",
    "Tìm hướng giải bài này",
    "1" * 200 + "+ 1",
])
def test_prose_and_code_are_not_passed_to_calculator(query):
    assert extract_arithmetic_request(query) is None


def test_normalization_preserves_substantive_question():
    assert normalize_chat_request("Chuột ơi, giúp tôi nghĩ hướng dẫn cho bài viết") == "nghĩ hướng dẫn cho bài viết"
    assert normalize_chat_request("Tôi muốn giúp một bạn học") == "Tôi muốn giúp một bạn học"


def test_context_keeps_order_roles_and_latest_query_once():
    history = ConversationHistory()
    history.add_turn("Chọn hướng A hay B?", "Hướng B.")
    history.add_turn("Vì sao?", "Vì B phù hợp mục tiêu.")
    query = "Phản biện hướng vừa rồi."
    prompt = build_chat_prompt(query, history.messages())
    messages = json.loads(prompt.split("\n", 1)[1])
    assert [message["role"] for message in messages] == ["user", "assistant", "user", "assistant", "user"]
    assert messages[1]["content"] == "Hướng B."
    assert messages[-1]["content"] == query
    assert prompt.count(query) == 1


def test_context_is_bounded_in_turns_and_characters():
    history = ConversationHistory()
    for i in range(20):
        history.add_turn(f"Câu {i}", f"Đáp {i}")
    messages = history.messages()
    assert len(messages) == history.MAX_TURNS * 2
    assert messages[0]["content"] == "Câu 14"
    history.add_turn("q" * 20000, "a" * 20000)
    messages = history.messages()
    assert len(messages) == 2  # Still a complete turn, not an orphan assistant answer.
    assert sum(len(message["content"]) for message in messages) <= history.MAX_CHARS
    assert "đã rút gọn" in messages[-1]["content"]


def test_new_chat_clears_context_and_latest_query_is_not_clipped():
    history = ConversationHistory()
    history.add_turn("Câu trước", "Đáp trước")
    history.clear()
    assert history.messages() == []
    query = "Câu mới " * 2000
    assert build_chat_prompt(query, history.messages()) == query


def test_failed_request_survives_followup_without_becoming_a_successful_answer():
    history = ConversationHistory()
    query = 'Read my next-class notes; I have 20 minutes.'
    history.add_attempt(query)
    assert history.messages() == []
    context = history.context_messages()
    assert context[0] == {'role': 'user', 'content': query}
    status = json.loads(context[1]['content'])
    assert status['origin'] == 'runtime_execution_status'
    assert status['successful_answer_produced'] is False
    assert status['status'] == 'failed'
    history.add_turn('I already know IP routing.', 'I still need to read the notes.')
    assert history.context_messages()[0]['content'] == query
    history.clear()
    assert history.context_messages() == []


def test_turn_snapshots_keep_full_unclipped_history_while_model_window_stays_bounded():
    history = ConversationHistory()
    for idx in range(1, 10):
        t = history.begin_turn(f"Câu hỏi dài lượt {idx}: " + ("x" * 900))
        history.complete_turn(t.turn_id, f"Trả lời đầy đủ lượt {idx}: " + ("y" * 900))

    # Full unclipped UI/session snapshots remain intact for all 9 turns
    all_turns = history.turns()
    assert len(all_turns) == 9
    assert all_turns[0].turn_id == "turn-1"
    assert len(all_turns[0].answer) > 900
    assert all_turns[-1].turn_id == "turn-9"

    # Model context window remains bounded by MAX_TURNS and MAX_CHARS
    bounded = history.messages()
    assert len(bounded) <= history.MAX_TURNS * 2
    assert sum(len(m["content"]) for m in bounded) <= history.MAX_CHARS

    # Explicit cancel and interaction turns preserve lineage and turn_references
    t10 = history.begin_turn("Viết bảng trace đầy đủ")
    cancelled = history.cancel_turn(t10.turn_id, execution_id=t10.execution_id)
    assert cancelled.status == "cancelled"

    inter = history.record_interaction(
        "Cập nhật mục tiêu thành tìm 6",
        target_turn_id="turn-2",
        target_artifact_id="art-1",
        target_revision=1,
        note_ids=["note-1"],
    )
    assert inter.kind == "interaction" and inter.target_turn_id == "turn-2"
    refs = history.turn_references()
    assert any(r["turn_id"] == t10.turn_id and r["status"] == "cancelled" for r in refs)
    assert any(r["turn_id"] == inter.turn_id and r["target_turn_id"] == "turn-2" for r in refs)
