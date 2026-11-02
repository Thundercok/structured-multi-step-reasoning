"""
rat.kernel.capabilities.web — Public web reading capability via Spider.

Registers:
- read_web_page: Scrapes a public HTTP(S) URL via the out-of-process Spider adapter
  and produces a verified, provenance-backed web_page_snapshot artifact.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from rat.crawler.spider_adapter import (
    SpiderAdapter,
    SpiderAdapterError,
    SpiderBinaryNotFoundError,
    SpiderEmptyContentError,
    SpiderHTTPError,
    SpiderParseError,
    SpiderSecurityGateError,
    SpiderSSRFBlockedError,
    SpiderTimeoutError,
    SpiderVersionMismatchError,
)
from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition

logger = logging.getLogger("rat.capabilities.web")


def create_web_capability(
    adapter: Optional[SpiderAdapter] = None,
    enabled: bool = False,
) -> Capability:
    """Create and configure the web capability bundle for RAT.

    NOTE on Network Gate: enabled defaults to False (fail-closed) because
    the underlying Spider CLI backend lacks per-hop destination IP and redirect
    enforcement. When False, invoking read_web_page returns an unavailable/security_gated error.
    """
    spider_adapter = adapter or SpiderAdapter()

    capability = Capability(
        name="web",
        title="Web & Nguồn trực tuyến",
        description="Đọc nội dung trang web công khai qua Spider crawler và trích xuất bản chụp có nguồn.",
    )

    def handle_read_web_page(args: Dict[str, Any], **context) -> Dict[str, Any]:
        url = (args.get("url") or "").strip()

        if not enabled:
            return {
                "found": False,
                "read": False,
                "error": (
                    "Khả năng duyệt web chưa được kích hoạt: backend Spider CLI hiện tại "
                    "chưa hỗ trợ kiểm soát địa chỉ IP kết nối và redirect trên từng hop mạng "
                    "(fail-closed default gate chống SSRF)."
                ),
                "url": url,
                "security_gated": True,
                "unavailable": True,
            }

        if not url:
            return {
                "found": False,
                "error": "URL không được để trống.",
                "url": url,
            }

        max_chars = args.get("max_chars", 6000)
        should_cancel = context.get("should_cancel")

        try:
            result = spider_adapter.scrape_page(
                url=url,
                max_chars=max_chars,
                should_cancel=should_cancel,
            )
        except SpiderSecurityGateError as exc:
            return {
                "found": False,
                "error": str(exc),
                "url": url,
                "security_gated": True,
                "unavailable": True,
            }
        except SpiderBinaryNotFoundError as exc:
            logger.warning(f"Spider binary not found: {exc}")
            return {
                "found": False,
                "error": str(exc),
                "url": url,
                "dependency_missing": True,
            }
        except SpiderVersionMismatchError as exc:
            logger.warning(f"Spider version mismatch: {exc}")
            return {
                "found": False,
                "error": str(exc),
                "url": url,
                "version_mismatch": True,
            }
        except SpiderSSRFBlockedError as exc:
            return {
                "found": False,
                "error": str(exc),
                "url": url,
                "security_blocked": True,
            }
        except SpiderParseError as exc:
            return {
                "found": False,
                "error": f"Lỗi cấu trúc dữ liệu từ crawler: {exc}",
                "url": url,
                "schema_error": True,
            }
        except (SpiderTimeoutError, SpiderHTTPError, SpiderEmptyContentError) as exc:
            return {
                "found": False,
                "error": str(exc),
                "url": url,
            }
        except SpiderAdapterError as exc:
            return {
                "found": False,
                "error": f"Lỗi thu thập dữ liệu qua Spider: {exc}",
                "url": url,
            }
        except Exception as exc:
            return {
                "found": False,
                "error": f"Lỗi không xác định khi đọc trang: {exc}",
                "url": url,
            }

        parsed = urlparse(result.final_url or url)
        domain = parsed.netloc or parsed.path.split("/")[0] or "web"

        return {
            "requested_url": result.requested_url,
            "final_url": result.final_url,
            "status_code": result.status_code,
            "content": result.content,
            "content_hash": result.content_hash,
            "truncated": result.truncated,
            "links": result.links,
            "headers": result.headers,
            "fetched_at": result.fetched_at,
            "engine": result.engine,
            "engine_version": result.engine_version,
            "title": f"Trang web · {domain}",
            "read": True,
            "found": True,
        }

    def web_page_actions(artifact: Artifact) -> List[ArtifactAction]:
        payload = artifact.payload
        url = payload.get("final_url") or payload.get("requested_url")
        actions = []
        if url and url.startswith("http"):
            actions.append(
                ArtifactAction(
                    id=f"refresh_web_page_{artifact.id}",
                    label="Tải lại trang",
                    target_artifact_id=artifact.id,
                    target_revision=artifact.revision,
                    operation_name="read_web_page",
                    params={"url": url},
                    description="Đọc lại nội dung mới nhất của trang web này.",
                )
            )
        return actions

    read_op = OperationDefinition(
        name="read_web_page",
        description=(
            "Fetch and read the content of a public web page using the Spider engine. "
            "Returns text/markdown content and saves a verified snapshot artifact with source hash and URL. "
            "Only supports public HTTP and HTTPS URLs; local/private addresses are blocked."
        ),
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Public HTTP or HTTPS URL to read, e.g. https://example.com/article",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters of content to extract (default 6000).",
                    "default": 6000,
                },
            },
            "required": ["url"],
        },
        handler=handle_read_web_page,
        artifact_kind="web_page_snapshot",
        present_result=True,
        available_actions=web_page_actions,
    )

    capability.register_operation(read_op)
    return capability
