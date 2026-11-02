"""
rat.kernel.capabilities.documents — Local document search and reading capability.

Distinguishes finding a file from reading it.
Registers:
- search_documents: full-text search and candidates retrieval -> produces document_search artifact
- read_document: deep text extraction from indexed document -> produces document_content artifact
- search_book_pages / read_book_page: on-demand indexed PDF pages with source metadata
"""
from __future__ import annotations

import copy
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from rat.crawler.db import Database, remove_vietnamese_accents
from rat.crawler.extractors import extract_document_content
from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition


def document_read_observation_pack(res: Any) -> Any:
    """Format full document reading result into a compact SoL-Pi Observation Pack for prompt context."""
    if not isinstance(res, dict):
        return res
    if not res.get("found", False) or "content" not in res:
        return res

    content = res.get("content", "")
    total_chars = res.get("total_chars", len(content))
    # If content is short (<= 400 chars), keeping it in full is cheap and preserves direct details
    if len(content) <= 400:
        return res

    head_chars = 250
    tail_chars = 150
    omitted = len(content) - (head_chars + tail_chars)
    if omitted <= 0:
        return res

    head_snippet = content[:head_chars].strip()
    tail_snippet = content[-tail_chars:].strip()

    compressed_content = (
        f"{head_snippet}\n\n"
        f"... [SoL-Pi Observation Pack: lược bớt {omitted} ký tự trung gian; "
        f"bản gốc đầy đủ ({total_chars} ký tự) đã lưu an toàn trong ArtifactStore. "
        f"Dùng expand_document_context nếu cần trích xuất cụ thể] ...\n\n"
        f"{tail_snippet}"
    )

    pack = copy.deepcopy(res)
    pack["content"] = compressed_content
    pack["observation_pack_status"] = "compressed_sol_pi"
    pack["omitted_chars"] = omitted
    return pack


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
        literal_name = query.strip(' \"\'')
        candidates = []
        filename_query = Path(literal_name).suffix.casefold() in {'.pdf', '.txt', '.md', '.docx', '.pptx', '.xlsx', '.csv'}
        if filename_query:
            # Filename punctuation and one-digit assignment numbers are data,
            # not generic content terms. Search the complete indexed name before
            # an OR-style FTS query where "pdf" can overwhelm every other word.
            def name_key(value):
                return ' '.join(re.findall(r'[^\W_]+', remove_vietnamese_accents(Path(value or '').stem)))
            key = name_key(literal_name)
            if key:
                connection = database.get_connection()
                connection.create_function('rat_filename_key', 1, name_key, deterministic=True)
                rows = connection.execute('''
                    SELECT file_path, file_name, file_ext, file_size, modified_at, summary, -100.0 AS rank
                    FROM documents
                    WHERE LOWER(file_ext) = ? AND
                          (rat_filename_key(file_name) = ? OR rat_filename_key(file_name) LIKE ?)
                    ORDER BY CASE WHEN rat_filename_key(file_name) = ? THEN 0 ELSE 1 END, modified_at DESC
                    LIMIT ?''', (Path(literal_name).suffix.casefold(), key, '%' + key + '%', key, limit * 4)).fetchall()
                candidates = [dict(row) for row in rows if Path(row['file_path']).is_file()]
        if not candidates and not filename_query:
            clean_tokens = [t.lower() for t in re.findall(r'[^\W_]+', query) if len(t) >= 2 or t.isdigit()]
            candidates = database.search_candidates(keywords=clean_tokens, limit=limit * 4)

        results = []
        seen = set()
        for c in candidates:
            path = c.get('file_path', '')
            if path in seen or not Path(path).is_file():
                continue
            seen.add(path)
            results.append({
                "filename": c.get("file_name", ""),
                "path": c.get("file_path", ""),
                "extension": c.get("file_ext", ""),
                "snippet": (c.get("summary") or c.get("file_name") or "")[:200],
                "score": round(float(c.get("rank", 1.0)), 2),
                "read": False,
                "content_status": "search_metadata_only",
            })
            if len(results) >= limit:
                break
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
        selected = context.get("selected_document_path")
        if str(p) != selected and not database.get_document_by_path(str(p)):
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

    def handle_expand_context(args: Dict[str, Any], **context) -> Dict[str, Any]:
        file_path = args.get("file_path", "")
        max_chars = args.get("max_chars", 2000)
        target_excerpt = args.get("target_excerpt", "")
        page_num = args.get("page")
        offset = args.get("offset")
        query_term = (args.get("query") or args.get("keyword") or "").strip()
        p = Path(file_path).absolute()
        if not p.is_file():
            return {"found": False, "error": f"Tệp không tồn tại: {file_path}", "file_path": file_path}
        database = get_db(context)
        selected = context.get("selected_document_path")
        if str(p) != selected and not database.get_document_by_path(str(p)):
            return {"found": False, "error": "Tệp chưa có trong chỉ mục RAT", "file_path": file_path}
        try:
            content = extract_document_content(str(p))
            if not content.strip():
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    content = ""
            total_chars = len(content)
            start_idx = 0
            if target_excerpt and target_excerpt.strip() in content:
                match_pos = content.find(target_excerpt.strip())
                lead = max_chars // 3
                start_idx = max(0, match_pos - lead)
                end_idx = min(total_chars, match_pos + len(target_excerpt.strip()) + (max_chars - lead))
                expanded_snippet = content[start_idx:end_idx].strip()
            elif query_term:
                # Case-insensitive term location across document
                c_lower = content.lower()
                q_lower = query_term.lower()
                match_pos = c_lower.find(q_lower)
                if match_pos == -1:
                    # Try individual meaningful words (>= 4 chars)
                    words = [w for w in re.findall(r"[^\W_]+", q_lower) if len(w) >= 4]
                    for w in words:
                        pos = c_lower.find(w)
                        if pos != -1:
                            match_pos = pos
                            break
                if match_pos != -1:
                    lead = max_chars // 3
                    start_idx = max(0, match_pos - lead)
                    end_idx = min(total_chars, start_idx + max_chars)
                    expanded_snippet = content[start_idx:end_idx].strip()
                elif offset is not None and 0 <= offset < total_chars:
                    start_idx = offset
                    expanded_snippet = content[start_idx:min(total_chars, start_idx + max_chars)].strip()
                else:
                    expanded_snippet = content[:max_chars].strip()
            elif offset is not None and 0 <= offset < total_chars:
                start_idx = offset
                expanded_snippet = content[start_idx:min(total_chars, start_idx + max_chars)].strip()
            else:
                expanded_snippet = content[:max_chars].strip()
            return {
                "found": True,
                "file_path": str(p),
                "filename": p.name,
                "content": expanded_snippet,
                "total_chars": total_chars,
                "start_offset": start_idx,
                "expanded_chars": len(expanded_snippet),
                "page": page_num,
                "expanded": True,
                "truncated": bool(total_chars > len(expanded_snippet)),
            }
        except Exception as e:
            return {"found": False, "error": str(e), "file_path": file_path}

    def handle_open(args, **context):
        import subprocess
        path = Path(args["file_path"]).absolute()
        if not path.is_file() or not get_db(context).get_document_by_path(str(path)):
            raise ValueError("Tệp không tồn tại hoặc chưa có trong chỉ mục RAT.")
        subprocess.run(["/usr/bin/open", str(path)], check=True, capture_output=True)
        return {"opened": True, "path": str(path)}

    def handle_deliver(args, **context):
        """Publish a reference to the original file; never copy or upload its bytes."""
        import hashlib
        path = Path(args["file_path"]).absolute()
        if not path.is_file() or not get_db(context).get_document_by_path(str(path)):
            raise ValueError("Tệp không tồn tại hoặc chưa có trong chỉ mục RAT; cần tìm lại tệp trước.")
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                cancel = context.get("should_cancel")
                if callable(cancel) and cancel():
                    raise ValueError("cancelled:execution_cancelled")
                digest.update(chunk)
        after = path.stat()
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError("Tệp vừa thay đổi trong lúc chuẩn bị; hãy thử đưa tệp lại.")
        return {"found": True, "delivered": True, "delivery": "local_reference",
                "title": path.name, "path": str(path), "filename": path.name,
                "extension": path.suffix.lower(), "file_size": after.st_size,
                "size_bytes": after.st_size, "modified_at": after.st_mtime,
                "sha256": digest.hexdigest()}

    def indexed_pdf(file_path, context):
        path = Path(file_path).absolute()
        if path.suffix.lower() != ".pdf" or not path.is_file():
            raise ValueError("Cần đường dẫn tới tệp PDF đang tồn tại.")
        if not get_db(context).get_document_by_path(str(path)):
            raise ValueError("PDF chưa có trong chỉ mục RAT. Tìm sách bằng search_documents trước; không đoán đường dẫn.")
        return path

    def handle_page_search(args, **context):
        from rat.engine.book_pages import search_pages
        return search_pages(indexed_pdf(args["file_path"], context), args["query"],
                            start_page=args.get("start_page", 1), max_pages=args.get("max_pages", 400),
                            limit=args.get("limit", 5), context=context)

    def handle_page_read(args, **context):
        from rat.engine.book_pages import read_page
        return read_page(indexed_pdf(args["file_path"], context), args["page"],
                         max_chars=args.get("max_chars", 8000), context=context)

    def page_actions(artifact):
        actions = [ArtifactAction(
            id=f"act_read_page_{artifact.id}_{artifact.revision}_{item['page']}",
            label=f"Đọc trang PDF {item['page']}", target_artifact_id=artifact.id,
            target_revision=artifact.revision, operation_name="read_book_page",
            params={"file_path": item["path"], "page": item["page"]})
            for item in artifact.payload.get("items", [])]
        next_page = artifact.payload.get("next_start_page")
        if next_page:
            actions.append(ArtifactAction(
                id=f"act_next_pages_{artifact.id}_{artifact.revision}",
                label=f"Tìm tiếp từ trang PDF {next_page}", target_artifact_id=artifact.id,
                target_revision=artifact.revision, operation_name="search_book_pages",
                params={"file_path": artifact.payload["path"], "query": artifact.payload["query"],
                        "start_page": next_page, "limit": artifact.inputs.get("limit", 5),
                        "max_pages": artifact.inputs.get("max_pages", 400)}))
        return actions

    path_schema = {"type": "string", "description": "Exact indexed PDF path returned by search_documents."}
    capability.register_operation(OperationDefinition(
        "search_book_pages",
        "Find PDF passages matching all query words (case/accent insensitive). "
        "Use an exact indexed path from search_documents. Returns excerpts and 1-based PDF pages/labels, "
        "which may differ from printed numbers. After max_pages, continue at next_start_page. "
        "Report textless/scanned pages requiring OCR.",
        {"type": "object", "properties": {
            "file_path": path_schema, "query": {"type": "string", "maxLength": 300},
            "limit": {"type": "integer", "minimum": 1, "maximum": 12, "default": 5},
            "start_page": {"type": "integer", "minimum": 1, "default": 1},
            "max_pages": {"type": "integer", "minimum": 1, "maximum": 400, "default": 400},
        }, "required": ["file_path", "query"]}, handle_page_search,
        artifact_kind="book_page_search", available_actions=page_actions))
    capability.register_operation(OperationDefinition(
        "read_book_page",
        "Read a 1-based PDF page returned by search_book_pages or requested by the user, with citations. "
        "Report truncation/textless pages. Save quotes via record_work_note bound to the actual result field.",
        {"type": "object", "properties": {
            "file_path": path_schema, "page": {"type": "integer", "minimum": 1},
            "max_chars": {"type": "integer", "minimum": 1, "maximum": 12000, "default": 8000},
        }, "required": ["file_path", "page"]}, handle_page_read, artifact_kind="book_page_content",
        observation_formatter=document_read_observation_pack))

    capability.register_operation(OperationDefinition("open_document",
        "Open an exact indexed file in its default application only when the user explicitly requests opening it.",
        {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]}, handle_open))

    capability.register_operation(OperationDefinition(
        "deliver_document",
        "Attach an original indexed file when requested, using its exact observed path (search_documents first if unknown). "
        "Returns a local reference, metadata and hash; does not open, copy or upload the file.",
        {"type": "object", "properties": {"file_path": {"type": "string"}},
         "required": ["file_path"]}, handle_deliver, artifact_kind="document_file"))

    def search_actions(artifact: Artifact) -> List[ArtifactAction]:
        results = artifact.payload.get("items", artifact.payload.get("results", []))
        actions = []
        for i, item in enumerate(results[:3]):
            path = item.get("path")
            if path:
                actions.append(ArtifactAction(
                    id=f"act_open_doc_{artifact.id}_{i}", label=f"Mở {item.get('filename')}",
                    target_artifact_id=artifact.id, target_revision=artifact.revision,
                    operation_name="open_document", params={"file_path": path}))
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
            "Find indexed local files by filename, subject or content keywords; retry irrelevant results. "
            "Returns metadata only. Read contents with read_document or read_book_page."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Filename, subject or content keywords.",
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
            "Read an indexed PDF, PPTX, DOCX, TXT or MD file. Use an exact observed path from search_documents "
            "or prior sources; search first if unknown. Never guess paths."
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
        observation_formatter=document_read_observation_pack,
    ))

    capability.register_operation(OperationDefinition(
        name="expand_document_context",
        description="Expand the reading window of an indexed document to capture surrounding context around a target excerpt, page or offset.",
        parameters={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Exact path of the document.",
                },
                "target_excerpt": {
                    "type": "string",
                    "description": "Observed excerpt to expand context around.",
                },
                "query": {
                    "type": "string",
                    "description": "Search keyword or topic query to locate relevant context within document.",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number if known.",
                    "minimum": 1,
                },
                "offset": {
                    "type": "integer",
                    "description": "Character offset to start reading from.",
                    "minimum": 0,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters of text content to read (default 2000).",
                    "default": 2000,
                    "minimum": 500,
                    "maximum": 8000,
                },
            },
            "required": ["file_path"],
        },
        handler=handle_expand_context,
        artifact_kind="document_expanded_context",
    ))

    return capability
