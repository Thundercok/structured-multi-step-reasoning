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
    ("Tính giúp tôi 2 + 2", "2 + 2"),
    ("chuột ơi tính 100 * 5 giúp với", "100 * 5"),
    ("tính giúp 50 / 2", "50 / 2"),
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
