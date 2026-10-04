"""Small, app-only helpers for conversational routing and recent context.

These do not change the research controller or any experiment prompts.
"""

from __future__ import annotations

import datetime
import json
import re
import uuid


CHAT_SYSTEM_PROMPT = (
    "Bạn là Chuột, trợ lý giúp người dùng hỏi đáp và suy nghĩ cùng nhau. "
    "Giọng bình thản, hơi mỉa nhẹ khi phù hợp; không cố pha trò, không mắng, "
    "không đổ lỗi hay chế giễu người dùng. Không thêm lời khen xã giao hay emoji; "
    "không cần câu nào cũng có lời mỉa. Khi họ bực hoặc cần giúp, ưu tiên giúp việc. "
    "Trả lời rõ ràng bằng tiếng Việt, đủ ý nhưng không dài dòng. "
    "Dựa vào các lượt trao đổi trước để trả lời yêu cầu mới nhất; không lặp lại lời chào "
    "hoặc hướng dẫn tính năng khi họ đang hỏi một việc cụ thể. "
    "Nếu thiếu thông tin, hỏi ngắn gọn; nếu không biết, nói rõ. "
    "Khi nhận danh sách tin nhắn JSON, role phân biệt người dùng và trợ lý; "
    "chỉ trả lời tin nhắn user cuối cùng, không viết tiếp cả cuộc hội thoại."
)


def normalize_chat_request(query: str) -> str:
    """Strip a leading address/polite wrapper, never a keyword inside a question."""
    text = query.strip()
    for _ in range(3):
        previous = text
        text = re.sub(
            r"^(?:(?:chào|chao|hello|hi|hey)\s+)?(?:chuột|chuot|rat)"
            r"(?:\s+(?:ơi|oi))?(?:\s*[,!:]\s*|\s+|$)",
            "", text, flags=re.I,
        )
        text = re.sub(r"^(?:cho\s+(?:tôi|mình|em)\s+hỏi\s*[,:]?\s*|hỏi\s*[,:]?\s*)", "", text, flags=re.I)
        text = re.sub(r"^(?:giúp|giup)\s+(?:tôi|toi|mình|minh|em)\s+", "", text, flags=re.I)
        text = text.strip()
        if text == previous:
            break
    return text


def extract_arithmetic_request(query: str) -> str | None:
    """Only a complete arithmetic request may go to the deterministic calculator."""
    text = normalize_chat_request(query)
    text = re.sub(
        r"^(?:(?:hãy|vui lòng|làm ơn|nhờ)\s+)?(?:tính|tinh|calc|calculate|=)\s*(?:(?:giúp|giup|hộ|ho|giùm|gium)\s*(?:tôi|toi|mình|minh|em)?\s*)?",
        "", text, flags=re.I,
    ).strip()
    text = re.sub(
        r"\s*(?:(?:giúp|giup|hộ|ho|giùm|gium)(?:\s+(?:tôi|toi|mình|minh|em|với|voi|nhé|nhe|nha))?|với|voi|nhé|nhe|nha)\s*[?!.]*$",
        "", text, flags=re.I,
    ).strip()
    text = re.sub(
        r"\s*(?:(?:bằng|bang|là|la|ra)\s+)?(?:bao nhiêu|bao nhieu|mấy|may)\s*(?:vậy|vay|thế|the|nhỉ|nhi)?\s*[?!.]*$",
        "", text, flags=re.I,
    ).strip().rstrip("?!")
    if len(text) > 160 or not re.search(r"\d", text):
        return None
    if not re.fullmatch(r"[0-9.\s+*/%()^\-]+", text):
        return None
    # Existing AST calculator understands exponentiation as **, not ^.
    return text.replace("^", "**").strip()


class ConversationHistory:
    """Keep completed turns only, bounded in both turns and prompt characters."""

    MAX_TURNS = 6
    MAX_CHARS = 6000

    def __init__(self) -> None:
        self._turns: list[tuple[str, str]] = []
        self.session_id: str = self._generate_session_id()
        self.created_at: datetime.datetime = datetime.datetime.now()

    @staticmethod
    def _generate_session_id() -> str:
        return f"c-{uuid.uuid4().hex[:4]}"

    def clear(self) -> None:
        self._turns.clear()
        self.session_id = self._generate_session_id()
        self.created_at = datetime.datetime.now()

    def get_tag_label(self) -> str:
        date_str = self.created_at.strftime("%d/%m · %H:%M")
        return f"#{self.session_id} · {date_str}"

    def add_turn(self, query: str, answer: str) -> None:
        if query.strip() and answer.strip():
            # A very long pasted message must not grow stored context without bound.
            limit = self.MAX_CHARS // 2
            self._turns.append((self._clip(query, limit), self._clip(answer, limit)))
            self._turns = self._turns[-self.MAX_TURNS:]

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        marker = "\n[… nội dung trước đã rút gọn]"
        return text if len(text) <= limit else text[:limit - len(marker)] + marker

    def messages(self) -> list[dict[str, str]]:
        turns: list[tuple[str, str]] = []
        used = 0
        for query, answer in reversed(self._turns):
            size = len(query) + len(answer)
            if used + size > self.MAX_CHARS:
                break
            turns.append((query, answer))
            used += size
        return [
            {"role": role, "content": content}
            for query, answer in reversed(turns)
            for role, content in (("user", query), ("assistant", answer))
        ]


def build_chat_prompt(query: str, history: list[dict[str, str]]) -> str:
    """Use the existing local generate endpoint with explicit, quoted chat roles."""
    if not history:
        return query
    messages = [*history, {"role": "user", "content": query}]
    return "Các lượt trao đổi, theo thứ tự thời gian:\n" + json.dumps(messages, ensure_ascii=False)
