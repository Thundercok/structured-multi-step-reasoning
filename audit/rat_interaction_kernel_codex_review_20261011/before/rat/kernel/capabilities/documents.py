"""
rat.kernel.capabilities.documents — Local document search and reading capability.

Distinguishes finding a file from reading it.
Registers:
- search_documents: full-text search and candidates retrieval -> produces document_search artifact
- read_document: deep text extraction from indexed document -> produces document_content artifact
"""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from rat.crawler.db import Database
from rat.crawler.extractors import extract_document_content
from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition


def create_documents_capability(db: Optional[Database] = None) -> Capability:
    capability = Capability(
        name="documents",
        title="Tài liệu & Tệp tin",
        description="Tìm kiếm tệp trong chỉ mục RAT và đọc trích xuất nội dung văn bản.",
    )

    def get_db(context: Dict[str, Any]) -> Database:
        if db is not None:
            return db
        if "db" in context and context["db"] is not None:
            return context["db"]
        from rat.config import config
        return Database(config.db_path)

    def handle_search(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        query = (args.get("query") or "").strip()
        limit = args.get("limit", 5)
        if not query:
            return []

        database = get_db(context)
        clean_tokens = [t.lower() for t in re.split(r"[\s\-_,.:]+", query) if len(t) >= 2]
        candidates = database.search_candidates(keywords=clean_tokens, limit=limit * 2)

        results = []
        for c in candidates[:limit]:
            results.append({
                "filename": c.get("file_name", ""),
                "path": c.get("file_path", ""),
                "extension": c.get("file_ext", ""),
                "snippet": (c.get("summary") or c.get("file_name") or "")[:200],
                "score": round(float(c.get("rank", 1.0)), 2),
            })
        return results

    def handle_read(args: Dict[str, Any], **context) -> Dict[str, Any]:
        file_path = args.get("file_path", "")
        max_chars = args.get("max_chars", 3000)

        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return {
                "found": False,
                "error": f"Tệp không tồn tại trên hệ thống: {file_path}",
                "next_action_hint": "Use search_documents to retrieve an existing indexed path; do not guess paths.",
                "path": file_path,
            }

        database = get_db(context)
        if not database.get_document_by_path(str(p)):
            return {"found": False, "error": "Tệp chưa có trong chỉ mục RAT", "path": file_path}

        try:
            content = extract_document_content(str(p))
            if not content.strip():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    content = ""

            truncated = len(content) > max_chars
            extracted_snippet = content[:max_chars].strip()

            return {
                "found": True,
                "path": str(p),
                "filename": p.name,
                "content": extracted_snippet,
                "total_chars": len(content),
                "truncated": truncated,
            }
        except Exception as e:
            return {
                "found": False,
                "error": f"Lỗi đọc nội dung tệp: {e}",
                "path": file_path,
            }

    def search_actions(artifact: Artifact) -> List[ArtifactAction]:
        results = artifact.payload.get("items", artifact.payload.get("results", []))
        actions = []
        for i, item in enumerate(results[:3]):
            path = item.get("path")
            if path:
                actions.append(ArtifactAction(
                    id=f"act_read_doc_{artifact.id}_{i}",
                    label=f"Đọc {item.get('filename')}",
                    target_artifact_id=artifact.id,
                    target_revision=artifact.revision,
                    operation_name="read_document",
                    params={"file_path": path},
                    description=f"Đọc nội dung của tệp {item.get('filename')}",
                ))
        return actions

    capability.register_operation(OperationDefinition(
        name="search_documents",
        description=(
            "Search local indexed documents (slides, lecture notes, syllabus, lab guides) "
            "by filename, subject or content keywords. Try another query when results are irrelevant."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query containing course title or topic.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 8,
                },
            },
            "required": ["query"],
        },
        handler=handle_search,
        artifact_kind="document_search",
        available_actions=search_actions,
    ))

    capability.register_operation(OperationDefinition(
        name="read_document",
        description=(
            "Read content of an indexed document (.pdf, .pptx, .docx, .txt, .md). "
            "Requires an exact path returned by search_documents or previous source metadata. "
            "Never guess paths. If the path is unknown, search_documents first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Exact indexed path from a search result or previous source metadata.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters of text content to read (default 3000).",
                    "default": 3000,
                    "minimum": 1,
                    "maximum": 8000,
                },
            },
            "required": ["file_path"],
        },
        handler=handle_read,
        artifact_kind="document_content",
    ))

    return capability
