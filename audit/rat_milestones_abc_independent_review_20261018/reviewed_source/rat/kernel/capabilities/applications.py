"""Checked macOS application launch capability.

Revalidates .app bundle path, Contents/Info.plist, CFBundleIdentifier, and
Contents/MacOS/<CFBundleExecutable> on disk before sending an OS launch request.
Never interpolates shell strings, never guesses paths outside the verified catalog,
and distinguishes OS launch acceptance from in-app/in-game login state.
"""
from __future__ import annotations

import subprocess
import sys
from typing import Any, Callable, Dict, Optional

from rat.engine.app_resolver import (
    Application,
    ApplicationCatalog,
    revalidate_application_bundle,
)
from rat.engine.finder_intent import parse_finder_intent
from rat.kernel.contracts import InputRequest
from rat.kernel.registry import Capability, OperationDefinition


APPLICATION_LAUNCH_CONTRACT = {
    "type": "object",
    "required": [
        "resource_id",
        "name",
        "path",
        "bundle_id",
        "launch_status",
        "status_label",
        "in_game_verified",
        "verification_note",
    ],
    "properties": {
        "title": {"type": "string"},
        "resource_id": {"type": "string"},
        "name": {"type": "string"},
        "path": {"type": "string"},
        "bundle_id": {"type": "string"},
        "version": {"type": "string"},
        "launch_status": {"type": "string", "enum": ["os_launch_accepted", "launch_request_sent"]},
        "os_launch_accepted": {"type": "boolean"},
        "status_label": {"type": "string"},
        "status_note": {"type": "string"},
        "in_game_verified": {"type": "boolean"},
        "verification_note": {"type": "string"},
    },
}


def create_applications_capability(
    catalog: Optional[ApplicationCatalog] = None,
    launcher: Optional[Callable[[Application], Any]] = None,
) -> Capability:
    capability = Capability(
        name="applications",
        title="Ứng dụng macOS",
        description="Tra cứu và gửi yêu cầu mở ứng dụng macOS (.app) đã xác thực trong danh mục.",
    )

    def _resolve_catalog(context: Dict[str, Any]) -> ApplicationCatalog:
        ctx_cat = context.get("application_catalog") or context.get("catalog")
        if isinstance(ctx_cat, ApplicationCatalog):
            return ctx_cat
        if catalog is not None:
            return catalog
        platform = context.get("platform", sys.platform)
        if platform != "darwin":
            return ApplicationCatalog(issues=("application_catalog_platform_unsupported",))
        return ApplicationCatalog.scan()

    def handle_open_application(args: Dict[str, Any], **context) -> Any:
        raw_query = str(args.get("query") or "").strip()
        resource_id = str(args.get("resource_id") or "").strip()
        path_arg = str(args.get("path") or args.get("candidate") or "").strip()
        bundle_id_arg = str(args.get("bundle_id") or "").strip()

        platform = context.get("platform", sys.platform)
        if platform != "darwin":
            raise ValueError("Thao tác mở ứng dụng .app chỉ hỗ trợ trên hệ điều hành macOS (darwin).")

        cat = _resolve_catalog(context)
        active_launcher = context.get("app_launcher") or launcher

        if raw_query:
            intent = parse_finder_intent(raw_query, catalog=cat)
            if intent.action == "negated_open":
                raise ValueError(
                    "Yêu cầu có từ phủ định ('đừng/không mở'); hệ thống giữ nguyên và không mở ứng dụng."
                )
        else:
            intent = None

        supplied = {
            k: v
            for k, v in args.items()
            if v is not None and str(v).strip() != ""
        }

        target_app: Optional[Application] = None
        if resource_id or path_arg:
            matches = [
                a
                for a in cat.applications
                if (resource_id and a.resource_id == resource_id)
                or (path_arg and a.path == path_arg)
            ]
            if not matches:
                raise ValueError("Ứng dụng được chọn không nằm trong danh mục .app đã xác thực.")
            if len(matches) > 1:
                return InputRequest(
                    operation_name="open_application",
                    supplied_inputs=supplied,
                    missing_fields=[],
                    candidate_choices=[
                        {
                            "resource_id": c.resource_id,
                            "name": c.name,
                            "path": c.path,
                            "bundle_id": c.bundle_id,
                            "version": c.version,
                        }
                        for c in matches
                    ],
                    prompt="Có nhiều bản cài đặt ứng dụng trùng khớp. Vui lòng chọn đúng đường dẫn cần mở:",
                )
            target_app = matches[0]
        else:
            target_query = ""
            if intent is not None:
                if intent.action == "open_app":
                    target_query = intent.target_app_query.strip()
                else:
                    target_query = (intent.query_terms or raw_query).strip()

            if not target_query or (intent is not None and intent.needs_clarification and not intent.target_app_query):
                return InputRequest(
                    operation_name="open_application",
                    supplied_inputs=supplied,
                    missing_fields=[
                        {
                            "name": "query",
                            "label": "Tên ứng dụng",
                            "type": "string",
                            "description": "Nhập tên ứng dụng muốn mở (ví dụ: Liên Minh, Safari)",
                            "required": True,
                        }
                    ],
                    prompt="Bạn muốn mở ứng dụng nào? Vui lòng nhập tên ứng dụng cần mở.",
                )

            candidates = list(cat.search(target_query, limit=10))
            if bundle_id_arg:
                candidates = [c for c in candidates if c.bundle_id == bundle_id_arg]

            if not candidates:
                raise ValueError(
                    f"Không tìm thấy ứng dụng khớp với '{target_query}' trong danh mục ứng dụng macOS đã xác thực."
                )

            if len(candidates) > 1:
                return InputRequest(
                    operation_name="open_application",
                    supplied_inputs={"query": target_query},
                    missing_fields=[],
                    candidate_choices=[
                        {
                            "resource_id": c.resource_id,
                            "name": c.name,
                            "path": c.path,
                            "bundle_id": c.bundle_id,
                            "version": c.version,
                        }
                        for c in candidates
                    ],
                    prompt=(
                        f"Có {len(candidates)} ứng dụng khớp với '{target_query}'. "
                        "Vui lòng chọn đúng ứng dụng hoặc bản cài đặt cần mở:"
                    ),
                )

            target_app = candidates[0]

        # Revalidate bundle path, Info.plist, CFBundleIdentifier, and executable on disk
        try:
            revalidated = revalidate_application_bundle(
                target_app.path,
                expected_bundle_id=target_app.bundle_id,
            )
        except Exception as exc:
            raise ValueError(
                f"Gói ứng dụng '{target_app.name}' ({target_app.path}) không còn hợp lệ trên ổ đĩa "
                f"(thiếu .app, Info.plist hoặc tệp thực thi: {exc})."
            ) from exc

        if callable(active_launcher):
            launch_outcome = active_launcher(revalidated)
            if isinstance(launch_outcome, tuple) and len(launch_outcome) == 2:
                ok, err_str = launch_outcome
                if not ok:
                    raise ValueError(err_str or f"Hệ điều hành từ chối yêu cầu mở ứng dụng '{revalidated.name}'.")
                launch_status = "os_launch_accepted"
            elif launch_outcome is False or (isinstance(launch_outcome, dict) and launch_outcome.get("ok") is False):
                err_msg = (
                    launch_outcome.get("error")
                    if isinstance(launch_outcome, dict) and launch_outcome.get("error")
                    else f"Hệ điều hành từ chối yêu cầu mở ứng dụng '{revalidated.name}'."
                )
                raise ValueError(err_msg)
            else:
                launch_status = (
                    launch_outcome.get("launch_status", "os_launch_accepted")
                    if isinstance(launch_outcome, dict)
                    else "os_launch_accepted"
                )
        else:
            proc = subprocess.run(
                ["/usr/bin/open", "-a", revalidated.path],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if proc.returncode != 0:
                stderr_clean = (proc.stderr or "").strip()[:160]
                raise ValueError(
                    f"Hệ điều hành từ chối lệnh mở ứng dụng '{revalidated.name}' "
                    f"(mã lỗi {proc.returncode}{': ' + stderr_clean if stderr_clean else ''})."
                )
            launch_status = "os_launch_accepted"

        status_label = "Đã gửi yêu cầu mở ứng dụng tới macOS"
        verification_note = (
            "Hệ điều hành đã nhận lệnh mở gói ứng dụng (.app). "
            "Trạng thái này chỉ xác nhận yêu cầu khởi chạy cấp hệ điều hành, "
            "không đồng nghĩa với việc ứng dụng đã đăng nhập hoặc người dùng đã vào trong màn hình trò chơi."
        )
        result_payload = {
            "title": f"Yêu cầu mở {revalidated.name}",
            "resource_id": revalidated.resource_id,
            "name": revalidated.name,
            "path": revalidated.path,
            "bundle_id": revalidated.bundle_id,
            "launch_status": launch_status,
            "os_launch_accepted": launch_status == "os_launch_accepted",
            "status_label": status_label,
            "status_note": verification_note,
            "in_game_verified": False,
            "verification_note": verification_note,
        }
        if revalidated.version and str(revalidated.version).strip():
            result_payload["version"] = str(revalidated.version).strip()
        return result_payload

    capability.register_operation(
        OperationDefinition(
            name="open_application",
            description=(
                "Open a verified macOS application (.app) from the local ApplicationCatalog after "
                "revalidating its bundle path, Info.plist, CFBundleIdentifier, and executable. "
                "Prompts for disambiguation when multiple installations or apps match."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Application name, alias, or open command (e.g., 'Liên Minh', 'League of Legends', 'Riot Client').",
                    },
                    "resource_id": {
                        "type": "string",
                        "description": "Exact application resource_id from ApplicationCatalog when disambiguated.",
                    },
                    "path": {
                        "type": "string",
                        "description": "Exact .app bundle path from ApplicationCatalog when disambiguated.",
                    },
                    "bundle_id": {
                        "type": "string",
                        "description": "Optional CFBundleIdentifier filter.",
                    },
                },
            },
            handler=handle_open_application,
            artifact_kind="application_launch",
            result_contract=APPLICATION_LAUNCH_CONTRACT,
        )
    )
    return capability
