"""Small, app-only helpers for conversational routing, turn identity, and recent context.

These do not change the research controller or any experiment prompts.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
import json
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from rat.engine.persona import COMPANION_PERSONA
from rat.engine.work_notes import TurnRef


CHAT_SYSTEM_PROMPT = (
    COMPANION_PERSONA +
    "Bạn là Chuột, trợ lý giúp người dùng hỏi đáp và suy nghĩ cùng nhau. "
    "Giọng bình thản, thân thiện; không cố pha trò, không mắng, "
    "không đổ lỗi hay chế giễu người dùng. Không thêm lời khen xã giao hay emoji; "
    "Khi họ bực hoặc cần giúp, ưu tiên giúp việc. "
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
        text = re.sub(r"^(?:giúp|giup)\s+(?:tôi|toi|mình|minh)\s+", "", text, flags=re.I)
        text = text.strip()
        if text == previous:
            break
    return text


def extract_arithmetic_request(query: str) -> str | None:
    """Only a complete arithmetic request may go to the deterministic calculator."""
    text = normalize_chat_request(query)
    text = re.sub(r"^(?:tính|tinh|calc|calculate|=)\s*", "", text, flags=re.I)
    text = re.sub(
        r"\s*(?:(?:bằng|bang|là|la|ra)\s+)?(?:bao nhiêu|bao nhieu|mấy|may)\s*[?!.]*$",
        "", text, flags=re.I,
    ).strip().rstrip("?!")
    if len(text) > 160 or not re.search(r"\d", text):
        return None
    if not re.fullmatch(r"[0-9.\s+*/%()^\-]+", text):
        return None
    # Existing AST calculator understands exponentiation as **, not ^.
    return text.replace("^", "**").strip()


@dataclass
class TurnSnapshot:
    """Full unclipped snapshot of a conversation turn or direct interaction."""

    turn_ref: TurnRef
    execution_id: str
    query: str
    answer: str = ""
    status: str = "in_progress"  # "in_progress" | "completed" | "failed" | "cancelled" | "needs_input"
    artifact_refs: List[Dict[str, Any]] = field(default_factory=list)
    note_ids: List[str] = field(default_factory=list)
    note_event_ids: List[str] = field(default_factory=list)
    task_state: Dict[str, Any] = field(default_factory=dict)
    reconciliation: Optional[Dict[str, Any]] = None
    reconciliation_status: str = "unchecked"
    # Historical declaration for continuity, never a journal or proof for a new execution.
    turn_contract: Optional[Dict[str, Any]] = None

    @property
    def turn_id(self) -> str:
        return self.turn_ref.turn_id

    @property
    def turn_number(self) -> int:
        return self.turn_ref.turn_number

    @property
    def kind(self) -> str:
        return self.turn_ref.kind

    @property
    def target_turn_id(self) -> Optional[str]:
        return self.turn_ref.target_turn_id

    @property
    def target_artifact_id(self) -> Optional[str]:
        return self.turn_ref.target_artifact_id

    @property
    def target_revision(self) -> Optional[int]:
        return self.turn_ref.target_revision

    def to_turn_ref(self, conversation_id: Optional[str] = None) -> TurnRef:
        if conversation_id and conversation_id != self.turn_ref.conversation_id:
            return TurnRef(
                conversation_id=conversation_id,
                turn_id=self.turn_ref.turn_id,
                kind=self.turn_ref.kind,
                turn_number=self.turn_ref.turn_number,
                target_turn_id=self.turn_ref.target_turn_id,
                target_artifact_id=self.turn_ref.target_artifact_id,
                target_revision=self.turn_ref.target_revision,
            )
        return self.turn_ref

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_ref": self.turn_ref.to_dict(),
            "turn_id": self.turn_ref.turn_id,
            "conversation_id": self.turn_ref.conversation_id,
            "turn_number": self.turn_ref.turn_number,
            "kind": self.turn_ref.kind,
            "target_turn_id": self.turn_ref.target_turn_id,
            "target_artifact_id": self.turn_ref.target_artifact_id,
            "target_revision": self.turn_ref.target_revision,
            "execution_id": self.execution_id,
            "query": self.query,
            "answer": self.answer,
            "status": self.status,
            "artifact_refs": copy.deepcopy(self.artifact_refs),
            "note_ids": list(self.note_ids),
            "note_event_ids": list(self.note_event_ids),
            "task_state": copy.deepcopy(self.task_state),
            "reconciliation": copy.deepcopy(self.reconciliation) if self.reconciliation is not None else None,
            "reconciliation_status": self.reconciliation_status,
            "turn_contract": copy.deepcopy(self.turn_contract),
        }


class ConversationHistory:
    """Bound completed answers and an honest context of incomplete requests.

    Separates the full session turn history (for UI and lookback references)
    from the bounded text window sent to the model.
    """

    MAX_TURNS = 6
    MAX_CHARS = 6000

    def __init__(self, conversation_id: Optional[str] = None) -> None:
        self._conversation_id: str = conversation_id or ("conv-" + uuid4().hex[:12])
        self._turn_seq: int = 0
        self._turns: list[tuple[str, str]] = []
        self._context_turns: list[tuple[str, str]] = []
        self._context_turn_ids: list[str] = []
        self._turn_snapshots: Dict[str, TurnSnapshot] = {}
        self._turn_order: List[str] = []
        self._cancelled_executions: set[str] = set()

    @property
    def conversation_id(self) -> str:
        return self._conversation_id

    def clear(self) -> None:
        self._conversation_id = "conv-" + uuid4().hex[:12]
        self._turn_seq = 0
        self._turns.clear()
        self._context_turns.clear()
        self._context_turn_ids.clear()
        self._turn_snapshots.clear()
        self._turn_order.clear()
        self._cancelled_executions.clear()

    def begin_turn(
        self,
        query: str,
        *,
        kind: str = "chat",
        turn_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        target_turn_id: Optional[str] = None,
        target_artifact_id: Optional[str] = None,
        target_revision: Optional[int] = None,
    ) -> TurnSnapshot:
        """Issue a stable TurnRef and execution_id for a new turn or direct interaction."""
        self._turn_seq += 1
        tid = turn_id or (f"turn-{self._turn_seq}" if kind == "chat" else f"interaction-{self._turn_seq}")
        t_ref = TurnRef(
            conversation_id=self._conversation_id,
            turn_id=tid,
            kind=kind,
            turn_number=self._turn_seq,
            target_turn_id=target_turn_id,
            target_artifact_id=target_artifact_id,
            target_revision=target_revision,
        )
        exec_id = execution_id or f"exec-{uuid4().hex[:12]}"
        snap = TurnSnapshot(
            turn_ref=t_ref,
            execution_id=exec_id,
            query=query.strip(),
            status="in_progress",
        )
        self._turn_snapshots[tid] = snap
        if tid not in self._turn_order:
            self._turn_order.append(tid)
        return copy.deepcopy(snap)

    def complete_turn(
        self,
        turn_id: str,
        answer: str,
        *,
        execution_id: Optional[str] = None,
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        note_ids: Optional[List[str]] = None,
        note_event_ids: Optional[List[str]] = None,
        task_state: Optional[Dict[str, Any]] = None,
        reconciliation: Optional[Any] = None,
        turn_contract: Optional[Any] = None,
    ) -> TurnSnapshot:
        """Commit a completed turn; reject late callbacks from cancelled executions."""
        snap = self._turn_snapshots.get(turn_id)
        if snap is None:
            raise ValueError(f"Unknown turn_id: {turn_id}")
        if execution_id is not None and execution_id in self._cancelled_executions:
            raise ValueError("cancelled:turn_cancelled")
        if snap.execution_id in self._cancelled_executions or snap.status == "cancelled":
            raise ValueError("cancelled:turn_cancelled")
        if execution_id is not None and snap.execution_id != execution_id:
            raise ValueError("cancelled:execution_mismatch")
        if snap.status == "completed" and snap.answer == answer.strip():
            return copy.deepcopy(snap)
        if snap.status not in ("in_progress", "needs_input"):
            raise ValueError("turn_already_finalized")

        snap.answer = answer.strip()
        snap.status = "completed"
        if artifact_refs is not None:
            snap.artifact_refs = copy.deepcopy(artifact_refs)
        if note_ids is not None:
            snap.note_ids = list(dict.fromkeys([*snap.note_ids, *note_ids]))
        if note_event_ids is not None:
            snap.note_event_ids = list(dict.fromkeys([*snap.note_event_ids, *note_event_ids]))
        if task_state is not None:
            snap.task_state = copy.deepcopy(task_state)
        if turn_contract is not None:
            snap.turn_contract = copy.deepcopy(turn_contract.to_dict() if hasattr(turn_contract, 'to_dict') else turn_contract)
        if reconciliation is not None:
            snap.reconciliation = reconciliation.to_dict() if hasattr(reconciliation, "to_dict") else copy.deepcopy(reconciliation)
            snap.reconciliation_status = snap.reconciliation.get("declared_scope_completion", "completed") if isinstance(snap.reconciliation, dict) else "completed"

        if snap.kind == "chat" and snap.query and snap.answer:
            limit = self.MAX_CHARS // 2
            turn = (self._clip(snap.query, limit), self._clip(snap.answer, limit))
            self._turns.append(turn)
            self._turns = self._turns[-self.MAX_TURNS:]
            self._context_turns.append(turn)
            self._context_turns = self._context_turns[-self.MAX_TURNS:]
            self._context_turn_ids.append(snap.turn_id)
            self._context_turn_ids = self._context_turn_ids[-self.MAX_TURNS:]
        return copy.deepcopy(snap)

    def fail_turn(
        self,
        turn_id: str,
        status: str = "failed",
        *,
        error: Optional[str] = None,
        execution_id: Optional[str] = None,
        partial_answer: str = "",
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        note_ids: Optional[List[str]] = None,
        note_event_ids: Optional[List[str]] = None,
        task_state: Optional[Dict[str, Any]] = None,
        reconciliation: Optional[Any] = None,
        turn_contract: Optional[Any] = None,
    ) -> TurnSnapshot:
        if status not in ("failed", "cancelled", "needs_input"):
            raise ValueError("Unknown incomplete execution status")
        snap = self._turn_snapshots.get(turn_id)
        if snap is None:
            raise ValueError(f"Unknown turn_id: {turn_id}")
        if execution_id is not None and snap.execution_id != execution_id:
            raise ValueError("cancelled:execution_mismatch")
        if snap.status == status:
            return copy.deepcopy(snap)
        if snap.status not in ("in_progress", "needs_input"):
            raise ValueError("turn_already_finalized")
        if status == "cancelled":
            self._cancelled_executions.add(snap.execution_id)
            if execution_id is not None:
                self._cancelled_executions.add(execution_id)
        snap.status = status
        if partial_answer:
            snap.answer = partial_answer.strip()
        if artifact_refs is not None:
            snap.artifact_refs = copy.deepcopy(artifact_refs)
        if note_ids is not None:
            snap.note_ids = list(dict.fromkeys([*snap.note_ids, *note_ids]))
        if note_event_ids is not None:
            snap.note_event_ids = list(dict.fromkeys([*snap.note_event_ids, *note_event_ids]))
        if task_state is not None:
            snap.task_state = copy.deepcopy(task_state)
        if turn_contract is not None:
            snap.turn_contract = copy.deepcopy(turn_contract.to_dict() if hasattr(turn_contract, 'to_dict') else turn_contract)
        if reconciliation is not None:
            snap.reconciliation = reconciliation.to_dict() if hasattr(reconciliation, "to_dict") else copy.deepcopy(reconciliation)
            snap.reconciliation_status = snap.reconciliation.get("declared_scope_completion", status) if isinstance(snap.reconciliation, dict) else status

        if snap.kind == "chat" and snap.query:
            event = json.dumps({
                "origin": "runtime_execution_status",
                "status": status,
                "successful_answer_produced": False,
            })
            # A clarification is part of the actual dialogue, while completion remains false.
            context_answer = event
            if status == 'needs_input' and snap.answer:
                context_answer = self._clip(snap.answer, self.MAX_CHARS // 2 - len(event) - 2) + '\n\n' + event
            self._context_turns.append((self._clip(snap.query, self.MAX_CHARS // 2), context_answer))
            self._context_turns = self._context_turns[-self.MAX_TURNS:]
            self._context_turn_ids.append(snap.turn_id)
            self._context_turn_ids = self._context_turn_ids[-self.MAX_TURNS:]
        return copy.deepcopy(snap)

    def cancel_turn(
        self,
        turn_id: str,
        *,
        execution_id: Optional[str] = None,
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        note_ids: Optional[List[str]] = None,
        note_event_ids: Optional[List[str]] = None,
        task_state: Optional[Dict[str, Any]] = None,
        reconciliation: Optional[Any] = None,
        turn_contract: Optional[Any] = None,
    ) -> TurnSnapshot:
        return self.fail_turn(
            turn_id,
            "cancelled",
            execution_id=execution_id,
            artifact_refs=artifact_refs,
            note_ids=note_ids,
            note_event_ids=note_event_ids,
            task_state=task_state,
            reconciliation=reconciliation,
            turn_contract=turn_contract,
        )

    def record_interaction(
        self,
        description: str,
        *,
        turn_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        target_turn_id: Optional[str] = None,
        target_artifact_id: Optional[str] = None,
        target_revision: Optional[int] = None,
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        note_ids: Optional[List[str]] = None,
        note_event_ids: Optional[List[str]] = None,
    ) -> TurnSnapshot:
        """Record a direct user control interaction with its own TurnRef and target link."""
        snap = self.begin_turn(
            description,
            kind="interaction",
            turn_id=turn_id,
            execution_id=execution_id,
            target_turn_id=target_turn_id,
            target_artifact_id=target_artifact_id,
            target_revision=target_revision,
        )
        return self.complete_turn(
            snap.turn_id,
            "",
            execution_id=snap.execution_id,
            artifact_refs=artifact_refs,
            note_ids=note_ids,
            note_event_ids=note_event_ids,
        )

    def add_turn(
        self,
        query: str,
        answer: str,
        *,
        turn_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        note_ids: Optional[List[str]] = None,
        note_event_ids: Optional[List[str]] = None,
        task_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[TurnSnapshot]:
        if query.strip() and answer.strip():
            if turn_id and turn_id in self._turn_snapshots:
                return self.complete_turn(
                    turn_id,
                    answer,
                    execution_id=execution_id,
                    artifact_refs=artifact_refs,
                    note_ids=note_ids,
                    note_event_ids=note_event_ids,
                    task_state=task_state,
                )
            snap = self.begin_turn(query, kind="chat", turn_id=turn_id, execution_id=execution_id)
            return self.complete_turn(
                snap.turn_id,
                answer,
                execution_id=snap.execution_id,
                artifact_refs=artifact_refs,
                note_ids=note_ids,
                note_event_ids=note_event_ids,
                task_state=task_state,
            )
        return None

    def add_attempt(
        self,
        query: str,
        status: str = "failed",
        *,
        turn_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        artifact_refs: Optional[List[Dict[str, Any]]] = None,
        note_ids: Optional[List[str]] = None,
        note_event_ids: Optional[List[str]] = None,
        task_state: Optional[Dict[str, Any]] = None,
    ) -> Optional[TurnSnapshot]:
        if status not in ("failed", "cancelled", "needs_input"):
            raise ValueError("Unknown incomplete execution status")
        if query.strip():
            if turn_id and turn_id in self._turn_snapshots:
                return self.fail_turn(
                    turn_id,
                    status,
                    execution_id=execution_id,
                    artifact_refs=artifact_refs,
                    note_ids=note_ids,
                    note_event_ids=note_event_ids,
                    task_state=task_state,
                )
            snap = self.begin_turn(query, kind="chat", turn_id=turn_id, execution_id=execution_id)
            return self.fail_turn(
                snap.turn_id,
                status,
                execution_id=snap.execution_id,
                artifact_refs=artifact_refs,
                note_ids=note_ids,
                note_event_ids=note_event_ids,
                task_state=task_state,
            )
        return None

    def get_turn(self, turn_id: Any) -> Optional[TurnSnapshot]:
        norm = f"turn-{turn_id}" if isinstance(turn_id, int) else str(turn_id)
        snap = self._turn_snapshots.get(norm)
        return copy.deepcopy(snap) if snap is not None else None

    def turns(self, include_interactions: bool = True) -> List[TurnSnapshot]:
        """Full unclipped session turn snapshots, independent of model window truncation."""
        items: List[TurnSnapshot] = []
        for tid in self._turn_order:
            snap = self._turn_snapshots[tid]
            if not include_interactions and snap.kind != "chat":
                continue
            items.append(copy.deepcopy(snap))
        return items

    def turn_references(self) -> List[Dict[str, Any]]:
        """Lightweight references for all turns (including text-only replies and interactions) without a separate store."""
        refs: List[Dict[str, Any]] = []
        for tid in self._turn_order:
            snap = self._turn_snapshots[tid]
            refs.append({
                "turn_id": snap.turn_id,
                "turn_number": snap.turn_number,
                "kind": snap.kind,
                "target_turn_id": snap.target_turn_id,
                "target_artifact_id": snap.target_artifact_id,
                "target_revision": snap.target_revision,
                "execution_id": snap.execution_id,
                "status": snap.status,
                "user_query": self._clip(snap.query, 240),
                "assistant_summary": self._clip(snap.answer, 360) if snap.answer else "",
                "artifact_refs": copy.deepcopy(snap.artifact_refs),
                "note_ids": list(snap.note_ids),
                "note_event_ids": list(snap.note_event_ids),
                "task_goal": snap.task_state.get("goal", "") if isinstance(snap.task_state, dict) else "",
                "reconciliation_status": snap.reconciliation_status,
                "reconciliation": copy.deepcopy(snap.reconciliation) if snap.reconciliation is not None else None,
                "unresolved_reasons": (snap.reconciliation or {}).get("unresolved_reasons", []),
                "turn_contract": copy.deepcopy(snap.turn_contract),
                "turn_contract_context": "historical_declaration_not_current_proof" if snap.turn_contract else None,
            })
        return refs

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        marker = "\n[… nội dung trước đã rút gọn]"
        return text if len(text) <= limit else text[:limit - len(marker)] + marker

    def messages(self) -> list[dict[str, str]]:
        """Successful completed turns only; status notices are never answers."""
        return self._bounded_messages(self._turns)

    def context_messages(self) -> list[dict[str, str]]:
        """Include failed/cancelled user requests with explicitly attributed status."""
        return self._bounded_messages(self._context_turns)

    def messages_with_turn_ids(self) -> List[Dict[str, Any]]:
        """Actual dialogue only; execution status belongs in turn references.

        An empty failed turn has no assistant utterance. In particular, its
        runtime status JSON must not become something the companion said.
        """
        turns: list[tuple[str, str, str]] = []
        used = 0
        paired = list(zip(self._context_turn_ids, self._context_turns))
        for tid, (query, answer) in reversed(paired):
            snap = self._turn_snapshots.get(tid)
            if snap and snap.status != 'completed':
                answer = (self._clip(snap.answer, self.MAX_CHARS // 2)
                          if snap.status == 'needs_input' and snap.answer else '')
            size = len(query) + len(answer)
            if used + size > self.MAX_CHARS:
                break
            turns.append((tid, query, answer))
            used += size
        return [
            {"role": role, "content": content, "turn_id": tid}
            for tid, query, answer in reversed(turns)
            for role, content in (("user", query), ("assistant", answer))
            if content
        ]

    def _bounded_messages(self, records) -> list[dict[str, str]]:
        turns: list[tuple[str, str]] = []
        used = 0
        for query, answer in reversed(records):
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
