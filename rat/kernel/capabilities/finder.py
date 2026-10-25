"""Progressive Finder Reasoning Capability for RAT (RAT-FIND-01).

Implements agentic reasoning tools for retrieving local files and macOS applications
when the user cannot recall exact names (fuzzy purpose, approximate date, partial terms).
Adheres strictly to the invariant: "TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC."
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from rat.config import config
from rat.crawler.db import Database
from rat.engine.app_resolver import (
    Application,
    ApplicationCatalog,
    name_key,
    revalidate_application_bundle,
)
from rat.engine.finder_intent import (
    FinderIntentPlan,
    parse_finder_intent,
    is_report_row,
    is_slide_row,
)
from rat.engine.progressive_search import (
    ProgressiveSearch,
    SearchFilters,
    SearchHit,
    SearchRequest,
)
from rat.engine.verification import FinderVerifier
from rat.kernel.contracts import InputRequest
from rat.kernel.registry import Capability, OperationDefinition

logger = logging.getLogger(__name__)

FINDER_RESULTS_CONTRACT = {
    "type": "object",
    "required": ["query", "hits", "hit_count", "intent"],
    "properties": {
        "query": {"type": "string"},
        "resource_kind": {"type": "string"},
        "hit_count": {"type": "integer", "minimum": 0},
        "intent": {"type": "object"},
        "hits": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["resource_id", "kind", "title", "path"],
                "properties": {
                    "resource_id": {"type": "string"},
                    "kind": {"type": "string", "enum": ["application", "file"]},
                    "title": {"type": "string"},
                    "path": {"type": "string"},
                    "origin": {"type": "string"},
                    "snippet": {"type": "string"},
                    "bundle_id": {"type": ["string", "null"]},
                    "modified_at": {"type": ["number", "null"]},
                    "is_pdf": {"type": "boolean"},
                },
            },
        },
        "clarification_prompt": {"type": ["string", "null"]},
    },
}


def finder_observation_pack(res: Any) -> Any:
    """Format full finder results into a compact SoL-Pi Observation Pack for prompt context."""
    if not isinstance(res, dict) or "hits" not in res:
        return res
    query = res.get("query", "")
    hits = res.get("hits", [])
    hit_count = res.get("hit_count", len(hits))
    intent = res.get("intent", {})

    top = [
        f"[{h.get('kind', 'file')}] {h.get('title', '')} (path: {h.get('path', '')})"
        for h in hits[:5]
    ]
    return {
        "artifact_ref": res.get("artifact_id", "finder_results"),
        "query": query,
        "hit_count": hit_count,
        "top_candidates": top,
        "interpretation": intent.get("interpretation_chips", []),
        "needs_clarification": bool(intent.get("needs_clarification")),
        "clarification_reason": intent.get("clarification_reason", ""),
        "status": "finder_results_available",
    }


def deterministic_finder(
    query: str,
    db: Optional[Database] = None,
    catalog: Optional[ApplicationCatalog] = None,
    resource_kind: str = "any",
    limit: int = 8,
) -> Dict[str, Any]:
    """Execute progressive finder search and produce structured candidate results."""
    clean_query = str(query or "").strip()
    intent = parse_finder_intent(clean_query, catalog=catalog)

    hits: List[Dict[str, Any]] = []

    # 1. Application search
    search_apps = resource_kind in ("any", "application") or intent.resource_kind == "application"
    if search_apps and catalog is not None and catalog.applications:
        app_query = intent.target_app_query or intent.query_terms or clean_query
        app_candidates = list(catalog.search(app_query, limit=limit))
        for app in app_candidates:
            app_p = Path(app.path).resolve()
            try:
                revalidate_application_bundle(app_p)
                hits.append({
                    "resource_id": app.resource_id,
                    "kind": "application",
                    "title": app.name,
                    "path": str(app_p),
                    "origin": "macOS Applications",
                    "snippet": f"Ứng dụng macOS: {app.name} ({app.bundle_id})",
                    "bundle_id": app.bundle_id,
                    "modified_at": None,
                    "is_pdf": False,
                })
            except Exception:
                pass

    # 2. Local Document file search
    search_files = resource_kind in ("any", "file", "slide", "report") and intent.resource_kind != "application"
    if search_files and db is not None:
        filters = SearchFilters(
            extensions=intent.extensions,
            excluded_extensions=intent.excluded_extensions,
            date_min=intent.date_min,
            date_max=intent.date_max,
            date_max_exclusive=intent.date_max_exclusive,
            date_field=intent.date_field,
            slide_rule=(resource_kind == "slide" or intent.slide_rule),
            report_rule=(resource_kind == "report" or intent.report_rule),
            sort=intent.sort,
        )
        file_query = intent.query_terms or clean_query
        try:
            matched_rows = db.search_metadata(
                file_query,
                extensions=intent.extensions,
                excluded_extensions=intent.excluded_extensions,
                date_min=intent.date_min,
                date_max=intent.date_max,
                date_max_exclusive=intent.date_max_exclusive,
                date_field=intent.date_field,
                slide_rule=(resource_kind == "slide" or intent.slide_rule),
                report_rule=(resource_kind == "report" or intent.report_rule),
                sort=intent.sort,
                limit=limit,
            )
            for row in matched_rows:
                raw_path = row.get("file_path") or ""
                p = Path(raw_path).resolve()
                if p.exists() and p.is_file():
                    res_id = "doc-" + hashlib.sha256(str(p).encode()).hexdigest()[:12]
                    is_pdf = str(row.get("file_ext") or "").lower() == ".pdf"
                    hits.append({
                        "resource_id": res_id,
                        "kind": "file",
                        "title": row.get("file_name") or p.name,
                        "path": str(p),
                        "origin": "Indexed Local Files",
                        "snippet": row.get("summary") or row.get("file_name") or "",
                        "bundle_id": None,
                        "modified_at": row.get("modified_at"),
                        "is_pdf": is_pdf,
                    })
        except Exception as exc:
            logger.warning("Finder file search failed: %s", exc)

    # Bounded truncation
    bounded_hits = hits[:limit]

    clarification_prompt = None
    if intent.needs_clarification and not bounded_hits:
        chips_str = ", ".join(intent.interpretation_chips) if intent.interpretation_chips else clean_query
        clarification_prompt = (
            f"Yêu cầu '{clean_query}' chưa đủ thông tin hoặc có nhiều cách hiểu ({chips_str}). "
            "Bạn có thể bổ sung thêm từ khóa, định dạng tệp (slide, pdf, doc) hoặc ứng dụng cụ thể không?"
        )

    return {
        "query": clean_query,
        "resource_kind": resource_kind,
        "hit_count": len(bounded_hits),
        "intent": {
            "action": intent.action,
            "resource_kind": intent.resource_kind,
            "query_terms": intent.query_terms,
            "interpretation_chips": list(intent.interpretation_chips),
            "needs_clarification": intent.needs_clarification,
            "clarification_reason": intent.clarification_reason,
            "scope_note": intent.scope_note,
        },
        "hits": bounded_hits,
        "clarification_prompt": clarification_prompt,
    }


def create_finder_capability(
    db: Optional[Database] = None,
    catalog: Optional[ApplicationCatalog] = None,
) -> Capability:
    """Create Capability defining Progressive Finder reasoning tools."""
    capability = Capability(
        name="finder",
        title="Truy hồi tệp và ứng dụng (Progressive Finder)",
        description=(
            "Truy hồi thông tin tệp nội bộ và ứng dụng macOS khi người dùng không nhớ chính xác tên, "
            "dựa trên mô tả công dụng, từ khóa, định dạng (slide, báo cáo) hoặc mốc thời gian."
        ),
    )

    def _resolve_db(context: Dict[str, Any]) -> Optional[Database]:
        ctx_db = context.get("db")
        if isinstance(ctx_db, Database):
            return ctx_db
        if db is not None:
            return db
        try:
            return Database(config.db_path)
        except Exception:
            return None

    def _resolve_catalog(context: Dict[str, Any]) -> Optional[ApplicationCatalog]:
        ctx_cat = context.get("application_catalog") or context.get("catalog")
        if isinstance(ctx_cat, ApplicationCatalog):
            return ctx_cat
        if catalog is not None:
            return catalog
        platform = context.get("platform", sys.platform)
        if platform == "darwin":
            try:
                return ApplicationCatalog.scan()
            except Exception:
                return None
        return None

    def handle_find_file_or_app(args: Dict[str, Any], **context) -> Dict[str, Any]:
        query = str(args.get("query") or "").strip()
        resource_kind = str(args.get("resource_kind") or "any").strip().lower()
        limit = int(args.get("limit") or 8)

        active_db = _resolve_db(context)
        active_catalog = _resolve_catalog(context)

        return deterministic_finder(
            query=query,
            db=active_db,
            catalog=active_catalog,
            resource_kind=resource_kind,
            limit=limit,
        )

    def handle_reveal_in_finder(args: Dict[str, Any], **context) -> Dict[str, Any]:
        raw_path = str(args.get("file_path") or args.get("path") or "").strip()
        if not raw_path:
            raise ValueError("Thiếu đường dẫn tệp để hiển thị trong Finder.")
        p = Path(raw_path).resolve()
        if not p.exists():
            raise ValueError(f"Đường dẫn {p} không tồn tại trên hệ thống.")
        platform = context.get("platform", sys.platform)
        if platform == "darwin":
            subprocess.run(["open", "-R", str(p)], check=True)
            status = "revealed_in_finder"
        else:
            status = f"unsupported_platform_{platform}"
        return {
            "path": str(p),
            "status": status,
            "name": p.name,
        }

    op_find = OperationDefinition(
        name="find_file_or_app",
        description=(
            "Find local files or macOS applications when the user cannot remember the exact name. "
            "Accepts vague descriptions, functional purpose, partial keywords, or approximate time. "
            "Returns authentic candidates with real verified filesystem paths. Never guesses non-existent resources."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query, topic, partial name or description (e.g. 'slide tuần trước', 'app vẽ vector', 'báo cáo thực tập').",
                },
                "resource_kind": {
                    "type": "string",
                    "enum": ["any", "application", "file", "slide", "report"],
                    "description": "Optional category filter: any (default), application, file, slide, or report.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of candidate hits to return (default: 8).",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["query"],
        },
        handler=handle_find_file_or_app,
        artifact_kind="finder_results",
    )
    op_find.verifier = FinderVerifier()
    op_find.observation_formatter = finder_observation_pack
    capability.register_operation(op_find)

    op_reveal = OperationDefinition(
        name="reveal_in_finder",
        description="Reveal a verified local file or application bundle in macOS Finder (open -R).",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Exact verified local path on disk.",
                },
            },
            "required": ["path"],
        },
        handler=handle_reveal_in_finder,
    )
    capability.register_operation(op_reveal)

    return capability
