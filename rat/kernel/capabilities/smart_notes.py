"""Smart Notes Capability — Universal Structured Note Synthesizer & Interactive Follow-up.

Transforms messy, unstructured thoughts, observations, logs or session notes
into an elegant, grounded, structured note artifact with action checklists,
grounded facts, interactive follow-ups, and SoL-Pi observation pack compression.

Follows the invariant rule: 'TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.'
"""
from __future__ import annotations

import copy
import hashlib
import re
from typing import Any, Dict, List, Optional

from rat.engine.verification import NoteVerifier
from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition


NOTE_PROPOSAL_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "domain", "summary", "key_facts", "analysis_sections", "risks_and_constraints", "action_items"],
    "properties": {
        "title": {"type": "string", "minLength": 1},
        "domain": {"type": "string", "enum": ["decision", "analysis", "technical", "research", "action_plan"]},
        "summary": {"type": "string", "minLength": 1},
        "key_facts": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["fact", "source"], "properties": {"fact": {"type": "string", "minLength": 1}, "source": {"type": "string"}}}},
        "analysis_sections": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["heading", "content", "badges"], "properties": {"heading": {"type": "string"},
                "content": {"type": "string"}, "badges": {"type": "array", "items": {"type": "string"}}}}},
        "risks_and_constraints": {"type": "array", "items": {"type": "string"}},
        "action_items": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "required": ["task", "done"], "properties": {"task": {"type": "string", "minLength": 1}, "done": {"type": "boolean"}}}},
    },
}


def observation_pack_formatter(res: Any) -> Any:
    """Format full structured note into a compact SoL-Pi Observation Pack for prompt context."""
    if not isinstance(res, dict):
        return res
    if res.get("artifact_kind") != "structured_note" and not res.get("note_id"):
        return res

    note_id = res.get("note_id") or "note_artifact"
    title = res.get("title", "Untitled Note")
    domain = res.get("domain", "general")
    summary = res.get("summary", "")
    key_facts = res.get("key_facts", [])
    action_items = res.get("action_items", [])
    risks = res.get("risks_and_constraints", [])

    return {
        "artifact_ref": note_id,
        "revision": res.get("revision", 1),
        "title": title,
        "domain": domain,
        "summary": summary,
        "key_facts_count": len(key_facts),
        "key_facts_excerpt": [f.get("fact") for f in key_facts[:3] if isinstance(f, dict)],
        "action_items_pending": [item.get("task") for item in action_items if isinstance(item, dict) and not item.get("done")][:5],
        "risks_and_constraints": risks[:3],
        "status": "note_reference_available" if res.get("artifact_id") else "uncommitted_note",
        "source_sha256": res.get("source_sha256"),
    }


def render_markdown_from_note(note_data: Dict[str, Any]) -> str:
    """Render a clean, elegant GitHub-style markdown presentation from note data."""
    title = note_data.get("title", "Untitled Note")
    domain = str(note_data.get("domain", "general")).upper()
    summary = note_data.get("summary", "")
    key_facts = note_data.get("key_facts", [])
    sections = note_data.get("analysis_sections", [])
    risks = note_data.get("risks_and_constraints", [])
    action_items = note_data.get("action_items", [])

    md_lines = [
        f"# 📋 {title}",
        f"> **Lĩnh vực:** `{domain}` | **Trạng thái:** `Có cấu trúc · xem phạm vi kiểm chứng`",
        "",
        f"**Tóm tắt cốt lõi:** {summary}",
        "",
        "---",
        "",
        "### 🔍 Dữ kiện Nền tảng (Grounded Facts)",
        "| STT | Dữ kiện quan sát | Phân loại nguồn |",
        "| :---: | :--- | :---: |",
    ]
    for idx, f in enumerate(key_facts, start=1):
        fact_text = f.get("fact", "") if isinstance(f, dict) else str(f)
        source_text = f.get("source", "context") if isinstance(f, dict) else "context"
        md_lines.append(f"| {idx} | {fact_text} | `{source_text}` |")

    if sections:
        md_lines.extend(["", "### 📊 Phân tích Chi tiết"])
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            badges_str = " ".join(f"`[{b}]`" for b in sec.get("badges", []))
            md_lines.append(f"#### {sec.get('heading', '')} {badges_str}")
            md_lines.append(sec.get("content", ""))
            md_lines.append("")

    if risks:
        md_lines.extend([
            "",
            "### ⚠️ Rủi ro & Vùng cấm cần tránh",
        ])
        for r in risks:
            md_lines.append(f"- 🚫 **{r}**")

    if action_items:
        md_lines.extend([
            "",
            "### ✅ Kế hoạch Hành động (Action Checklist)",
        ])
        for item in action_items:
            if isinstance(item, dict):
                check = "x" if item.get("done") else " "
                md_lines.append(f"- [{check}] {item.get('task')}")

    return "\n".join(md_lines)


def note_available_actions(artifact: Artifact) -> List[ArtifactAction]:
    """Generate interactive UI / Agent actions available on a structured note artifact."""
    actions: List[ArtifactAction] = []
    payload = artifact.payload or {}
    items = payload.get("action_items", [])
    for idx, item in enumerate(items[:4], start=1):
        if isinstance(item, dict) and not item.get("done"):
            task_str = item.get("task", "")
            task_snippet = task_str[:25]
            actions.append(ArtifactAction(
                id=f"act_done_{artifact.id}_{artifact.revision}_{idx}",
                label=f"✓ Xong: {task_snippet}",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="update_note_action_item",
                params={"task_match": task_str, "done": True},
                description=f"Đánh dấu việc '{task_str}' đã hoàn thành",
            ))
    actions.append(ArtifactAction(
        id=f"act_expand_{artifact.id}_{artifact.revision}",
        label="🔍 Mở rộng phân tích",
        target_artifact_id=artifact.id,
        target_revision=artifact.revision,
        operation_name="expand_note_section",
        params={"section_heading": "Phân tích Logic", "expansion_query": "Phân tích thêm các khía cạnh cần lưu ý"},
        input_schema={"type": "object", "properties": {"expansion_content": {"type": "string", "minLength": 1}},
                      "required": ["expansion_content"]},
        description="Mở rộng đào sâu nội dung ghi chú",
    ))
    return actions


def deterministic_note_synthesizer(
    raw_content: str,
    domain: str = "auto",
    title: Optional[str] = None,
    focus_question: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract input text mechanically; never fabricate analysis or offline model output."""
    text = (raw_content or "").strip()
    lower_text = text.lower()

    # 1. Domain Detection
    detected_domain = domain
    if domain == "auto":
        if any(k in lower_text for k in ("tarot", "pentacles", "wands", "swords", "cups", "bài", "lá", "hiero", "world", "tâm lý")):
            detected_domain = "analysis"
        elif any(k in lower_text for k in ("bug", "lỗi", "latency", "ms", "token", "cache", "api", "code", "exception", "timeout")):
            detected_domain = "technical"
        elif any(k in lower_text for k in ("chọn", "mua", "tặng", "lựa chọn", "nên", "phương án", "so sánh")):
            detected_domain = "decision"
        elif any(k in lower_text for k in ("nghiên cứu", "paper", "arxiv", "hypothesis", "benchmark")):
            detected_domain = "research"
        else:
            detected_domain = "action_plan"

    # 2. Title Synthesis
    inferred_title = title
    if not inferred_title:
        if focus_question:
            inferred_title = f"Ghi chú: {focus_question[:60]}"
        elif detected_domain == "analysis":
            inferred_title = "Phân tích Trải bài & Hiện trạng Tâm lý"
        elif detected_domain == "decision":
            inferred_title = "Kế hoạch Quyết định & Lựa chọn Tối ưu"
        elif detected_domain == "technical":
            inferred_title = "Báo cáo Kỹ thuật & Điều tra Vấn đề"
        elif detected_domain == "research":
            inferred_title = "Tổng hợp Nghiên cứu & Luận điểm"
        else:
            first_line = text.split("\n")[0][:60].strip()
            inferred_title = first_line if first_line else "Bản Ghi chú Đa năng"

    # 3. Key Facts Extraction (Grounded in text)
    key_facts: List[Dict[str, str]] = []
    card_patterns = re.findall(r"(\d+\s*(?:wands?|pentacles?|swords?|cups?|w|p|s|c)(?:\s*rev|\s*reversed)?)", lower_text)
    major_patterns = re.findall(r"((?:the\s+)?(?:hierophant|world|fool|magician|empress|emperor|chariot|strength|hermit|wheel|justice|hanged|death|temperance|devil|tower|star|moon|sun|judgment)(?:\s*rev|\s*reversed)?)", lower_text)
    for c in (card_patterns + major_patterns):
        key_facts.append({"fact": c.strip(), "source": "user_input"})

    for sentence in re.split(r"[,\n;]+", text):
        clean_s = sentence.strip()
        if len(clean_s) > 8 and not any(clean_s.lower() in f["fact"].lower() for f in key_facts):
            if any(k in clean_s.lower() for k in ("đau", "stress", "mệt", "deadline", "lỗi", "mua", "tặng", "fine dining", "spa")):
                key_facts.append({"fact": clean_s, "source": "user_context"})

    if not key_facts and text:
        key_facts.append({"fact": text[:120], "source": "user_input"})

    # 4. Risks & Constraints Extraction
    risks: List[str] = []
    for line in re.split(r"[,\n;]+", text):
        s = line.strip()
        if any(neg in s.lower() for k in ("tránh", "không nên", "dị ứng", "ghét", "rủi ro", "áp lực", "cấm", "lưu ý", "bẫy") for neg in (k,)):
            risks.append(s)

    # 5. Action Items Extraction
    action_items: List[Dict[str, Any]] = []
    for line in re.split(r"(?<=[.!?])\s+|[,\n;]+", text):
        s = line.strip()
        if any(act in s.lower() for act in ("cần", "đọc", "xem", "đặt", "mua", "soạn", "làm", "chuẩn bị", "kiểm tra", "tinh chỉnh", "đi", "hẹn", "order")):
            action_items.append({"task": s, "done": False})

    # 6. Summary Synthesis
    summary = (
        f"Ghi chú có cấu trúc cho chủ đề '{inferred_title}' thuộc nhóm {detected_domain}. "
        f"Ghi nhận {len(key_facts)} dữ kiện nền tảng, {len(risks)} lưu ý/rào cản và {len(action_items)} đầu việc hành động."
    )

    # 7. Analysis Sections Construction
    sections: List[Dict[str, Any]] = [
        {
            "heading": "Hiện trạng & Dữ kiện Quan sát",
            "content": "Các dữ kiện đầu vào được bóc tách và đối chiếu từ nội dung cung cấp:\n" +
                       "\n".join(f"- **{f['fact']}** (nguồn: `{f['source']}`)" for f in key_facts),
            "badges": ["fact_grounded", "verified_input"],
        },
    ]

    note_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    note_id = f"note-{note_hash}"

    partial_note = {
        "artifact_kind": "structured_note",
        "note_id": note_id,
        "revision": 1,
        "title": inferred_title,
        "domain": detected_domain,
        "summary": summary,
        "key_facts": key_facts,
        "analysis_sections": sections,
        "risks_and_constraints": risks,
        "action_items": action_items,
        "raw_content": text,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "synthesis_mode": "extractive",
        "_op_name": "synthesize_smart_note",
    }
    partial_note["markdown_rendered"] = render_markdown_from_note(partial_note)
    partial_note["raw_char_count"] = len(text)
    partial_note["structured_char_count"] = len(partial_note["markdown_rendered"])

    return partial_note


def create_smart_notes_capability(store=None) -> Capability:
    """Create and return the Smart Notes Capability."""
    capability = Capability(
        name="smart_notes",
        title="Ghi chép thông minh (Smart Notes)",
        description="Tổ chức dòng suy nghĩ thô thành ghi chú có cấu trúc CoT, kiểm chứng dữ kiện và nén ngữ cảnh theo SoL-Pi.",
    )
    verifier = NoteVerifier()

    def handle_synthesize(args: Dict[str, Any], **context) -> Dict[str, Any]:
        raw_content = args.get("raw_content", "").strip()
        if not raw_content:
            raise ValueError("Cần cung cấp nội dung ghi chép thô (raw_content).")

        domain = args.get("domain", "auto")
        title = args.get("title")
        focus_question = args.get("focus_question")

        # Synthesis belongs to the existing Agent model loop. The tool only
        # validates and stores its proposal; no hidden, unmetered nested call.
        proposal = args.get("structured_note")
        if proposal is None:
            structured_res = deterministic_note_synthesizer(raw_content, domain, title, focus_question)
        else:
            from rat.engine.task_state import validate_schema
            validate_schema(proposal, NOTE_PROPOSAL_SCHEMA)
            structured_res = copy.deepcopy(proposal)
            structured_res.update({
                "artifact_kind": "structured_note", "revision": 1,
                "synthesis_mode": "agent_proposal", "raw_content": raw_content,
                "source_sha256": hashlib.sha256(raw_content.encode("utf-8")).hexdigest(),
                "_op_name": "synthesize_smart_note",
            })
            structured_res["markdown_rendered"] = render_markdown_from_note(structured_res)
        from rat.engine.verification import ExecutionEvidence, VerificationStatus
        report = verifier.check_execution(ExecutionEvidence(
            "note-precommit", "synthesize_smart_note", args, structured_res, ""))
        if report.status == VerificationStatus.FAIL:
            raise ValueError("invalid_note: " + report.reason)
        # Dispatcher owns the only commit and canonical ID, after cancellation
        # and generation checks. A handler must never write to the store itself.
        return structured_res

    def handle_update_action_item(args: Dict[str, Any], **context) -> Dict[str, Any]:
        """Update or toggle a task in an existing structured note artifact."""
        target_art = context.get("target_artifact")
        if target_art is None:
            art_id = args.get("artifact_id")
            s = context.get("artifact_store") or getattr(context.get("runtime"), "artifact_store", None) or store
            if s and art_id:
                target_art = s.get(art_id)
        if target_art is None:
            raise ValueError("Cần bản ghi chú mục tiêu (target_artifact) để cập nhật việc cần làm.")

        payload = copy.deepcopy(target_art.payload)
        payload["_previous_note"] = {"revision": target_art.revision,
                                     "action_items": copy.deepcopy(payload.get("action_items", []))}
        action_items = payload.get("action_items", [])
        task_match = str(args.get("task_match") or "").lower().strip()
        item_index = args.get("item_index")
        done = bool(args.get("done", True))
        new_text = args.get("new_task_text")

        if item_index is None and task_match:
            matches = [item for item in action_items if isinstance(item, dict)
                       and task_match in str(item.get("task", "")).lower()]
            if len(matches) > 1:
                raise ValueError("ambiguous_note_task: dùng item_index để chọn một việc cụ thể")
        matched = False
        for idx, item in enumerate(action_items, start=1):
            if not isinstance(item, dict):
                continue
            item_task = str(item.get("task", "")).lower()
            if (item_index == idx if item_index is not None else task_match and task_match in item_task):
                item["done"] = done
                if new_text:
                    item["task"] = new_text.strip()
                matched = True
                break

        if not matched:
            raise ValueError(f"Không tìm thấy việc cần làm khớp với: {task_match or item_index}")

        payload["action_items"] = action_items
        payload["revision"] = target_art.revision + 1
        payload["markdown_rendered"] = render_markdown_from_note(payload)
        payload["_op_name"] = "update_note_action_item"
        from rat.engine.verification import ExecutionEvidence, VerificationStatus
        report = verifier.check_execution(ExecutionEvidence("note-precommit", "update_note_action_item", args, payload, ""))
        if report.status == VerificationStatus.FAIL:
            raise ValueError("invalid_note_update: " + report.reason)
        return payload

    def handle_expand_section(args: Dict[str, Any], **context) -> Dict[str, Any]:
        """Expand or deepen a section in an existing structured note artifact."""
        target_art = context.get("target_artifact")
        if target_art is None:
            art_id = args.get("artifact_id")
            s = context.get("artifact_store") or getattr(context.get("runtime"), "artifact_store", None) or store
            if s and art_id:
                target_art = s.get(art_id)
        if target_art is None:
            raise ValueError("Cần bản ghi chú mục tiêu (target_artifact) để mở rộng nội dung.")

        payload = copy.deepcopy(target_art.payload)
        heading_query = str(args.get("section_heading") or "").lower().strip()
        expansion_query = str(args.get("expansion_query") or "").strip()
        expansion_content = str(args.get("expansion_content") or "").strip()
        if not expansion_content:
            raise ValueError("note_expansion_requires_content: Agent cần soạn nội dung trước khi lưu; yêu cầu không phải kết quả phân tích")
        payload["_previous_note"] = {"revision": target_art.revision,
                                     "analysis_sections": copy.deepcopy(payload.get("analysis_sections", []))}
        new_facts = args.get("new_key_facts", [])

        if not expansion_query:
            raise ValueError("Cần nội dung hoặc yêu cầu mở rộng (expansion_query).")

        if new_facts:
            raw = " ".join(str(payload.get("raw_content", "")).casefold().split())
            existing_facts = payload.setdefault("key_facts", [])
            for f in new_facts:
                if isinstance(f, str) and f.strip():
                    if " ".join(f.casefold().split()) not in raw:
                        raise ValueError("ungrounded_note_fact: dữ kiện mới cần nằm trong nguồn gốc")
                    existing_facts.append({"fact": f.strip(), "source": "raw_content"})

        sections = payload.setdefault("analysis_sections", [])
        target_section = None
        for sec in sections:
            if isinstance(sec, dict) and heading_query in str(sec.get("heading", "")).lower():
                target_section = sec
                break

        if target_section is not None:
            target_section["content"] += f"\n\n**Bổ sung do Agent soạn (chưa xác minh diễn giải):**\n{expansion_content}"
            badges = target_section.setdefault("badges", [])
            if "expanded" not in badges:
                badges.append("expanded")
        else:
            sections.append({
                "heading": f"Mở rộng: {args.get('section_heading', 'Chi tiết bổ sung')}",
                "content": f"**Bổ sung do Agent soạn (chưa xác minh diễn giải):**\n{expansion_content}",
                "badges": ["follow_up", "expanded"],
            })

        payload["expansion_request"] = expansion_query
        payload["expansion_content"] = expansion_content

        payload["revision"] = target_art.revision + 1
        payload["markdown_rendered"] = render_markdown_from_note(payload)
        payload["_op_name"] = "expand_note_section"
        from rat.engine.verification import ExecutionEvidence, VerificationStatus
        report = verifier.check_execution(ExecutionEvidence("note-precommit", "expand_note_section", args, payload, ""))
        if report.status == VerificationStatus.FAIL:
            raise ValueError("invalid_note_expansion: " + report.reason)
        return payload

    # Operation 1: synthesize_smart_note
    capability.register_operation(
        OperationDefinition(
            name="synthesize_smart_note",
            description=(
                "Save a structured note from source text. Prepare structured_note in the Agent loop for synthesis; "
                "key_facts.fact must be exact excerpts of raw_content (case/whitespace ignored). "
                "Without structured_note this tool performs extractive organization only, no model call. "
                "Returns the canonical artifact_id and revision for later inspect/update operations."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "structured_note": NOTE_PROPOSAL_SCHEMA,
                    "raw_content": {
                        "type": "string",
                        "description": "Raw unstructured notes or brain-dump text to organize.",
                    },
                    "domain": {
                        "type": "string",
                        "enum": ["auto", "decision", "analysis", "technical", "research", "action_plan"],
                        "default": "auto",
                        "description": "Domain hint for structuring logic.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Optional title for the note.",
                    },
                    "focus_question": {
                        "type": "string",
                        "description": "Optional focal question or objective.",
                    },
                },
                "required": ["raw_content"],
            },
            handler=handle_synthesize,
            available_actions=note_available_actions,
            observation_formatter=observation_pack_formatter,
            verifier=verifier,
            artifact_kind="structured_note",
        )
    )

    # Operation 2: update_note_action_item
    capability.register_operation(
        OperationDefinition(
            name="update_note_action_item",
            description=(
                "Update or toggle an action item/task in an existing structured note (mark done/undone or edit task description). "
                "Creates a new revision preserving history."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "task_match": {
                        "type": "string",
                        "description": "Keyword or exact phrase matching the target action item to update.",
                    },
                    "item_index": {
                        "type": "integer",
                        "description": "Optional 1-based index of the action item in the checklist.",
                    },
                    "done": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether the action item is completed (checked) or pending.",
                    },
                    "new_task_text": {
                        "type": "string",
                        "description": "Optional replacement text for the task.",
                    },
                },
            },
            handler=handle_update_action_item,
            available_actions=note_available_actions,
            observation_formatter=observation_pack_formatter,
            verifier=verifier,
            target_kind="structured_note",
            artifact_kind="structured_note",
            updates_target=True,
        )
    )

    # Operation 3: expand_note_section
    capability.register_operation(
        OperationDefinition(
            name="expand_note_section",
            description=(
                "Deepen or expand a specific section, add detailed sub-points, or analyze a specific angle "
                "of an existing structured note based on user follow-up questions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "section_heading": {
                        "type": "string",
                        "description": "Heading or topic keyword of the section to expand.",
                    },
                    "expansion_content": {"type": "string", "minLength": 1,
                                          "description": "Actual additional analysis composed by the Agent, not the instruction. Interpretations remain unverified."},
                    "expansion_query": {
                        "type": "string",
                        "description": "Detailed follow-up instructions, insights, or sub-points to add.",
                    },
                    "new_key_facts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional new facts to bind to the note.",
                    },
                },
                "required": ["expansion_query", "expansion_content"],
            },
            handler=handle_expand_section,
            available_actions=note_available_actions,
            observation_formatter=observation_pack_formatter,
            verifier=verifier,
            target_kind="structured_note",
            artifact_kind="structured_note",
            updates_target=True,
        )
    )

    return capability
