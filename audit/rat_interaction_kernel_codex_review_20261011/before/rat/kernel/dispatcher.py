"""
rat.kernel.dispatcher — ActionDispatcher binding controls and model actions to operations.

Ensures:
- Identical dispatcher semantics for direct UI controls and native model tool actions
- Stale revision detection (rejections prevent overwriting current artifacts from stale buttons)
- Ambiguity resolution (multiple target artifacts require explicit user clarification)
- Stable artifact IDs with monotonic revisions and preserved history
"""
from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional, Tuple

from rat.kernel.contracts import (
    Artifact,
    ArtifactAction,
    ArtifactStore,
    DispatchResult,
    InputRequest,
)
from rat.kernel.registry import CapabilityRegistry


class StaleRevisionError(ValueError):
    """Raised when an action targets an outdated artifact revision."""
    pass


class AmbiguousArtifactError(ValueError):
    """Raised when multiple candidate artifacts match and reference is unclear."""
    pass


class ActionDispatcher:
    """Dispatches actions and operations against versioned artifacts."""

    def __init__(self, registry: CapabilityRegistry, store: ArtifactStore) -> None:
        self.registry = registry
        self.store = store

    def resolve_target_artifact(
        self,
        kind: str,
        target_artifact_id: Optional[str] = None,
    ) -> Tuple[Optional[Artifact], Optional[InputRequest]]:
        """Resolve target artifact or return an InputRequest for clarification if ambiguous."""
        if target_artifact_id:
            art = self.store.get(target_artifact_id)
            return art, None

        matching = self.store.find_by_kind(kind)
        if len(matching) == 0:
            return None, None
        if len(matching) == 1:
            return matching[0], None

        # Multiple matching candidates: require explicit clarification!
        candidates = [
            {
                "id": a.id,
                "title": a.title or f"{a.kind} ({a.id})",
                "revision": a.revision,
                "name": a.inputs.get("name") or a.title,
            }
            for a in matching
        ]
        clarification_request = InputRequest(
            operation_name="select_target_artifact",
            candidate_choices=candidates,
            prompt="Hiện có nhiều kết quả đang được thảo luận. Bạn muốn áp dụng thay đổi cho kết quả nào?",
        )
        return None, clarification_request

    def dispatch(
        self,
        action: ArtifactAction,
        user_inputs: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DispatchResult:
        """Execute an ArtifactAction on its target artifact and revision."""
        latest = self.store.get(action.target_artifact_id)
        if latest is None:
            return DispatchResult(
                status="error",
                error=f"Không tìm thấy kết quả mục tiêu: {action.target_artifact_id}",
                action_id=action.id,
            )

        # Stale revision detection
        if action.target_revision != latest.revision:
            return DispatchResult(
                status="stale_revision",
                error=(
                    f"Thao tác trên phiên bản cũ (v{action.target_revision}). "
                    f"Kết quả hiện tại đã ở phiên bản mới hơn (v{latest.revision})."
                ),
                action_id=action.id,
                artifact=latest,
            )

        op = self.registry.get_operation(action.operation_name)
        if op is None:
            return DispatchResult(
                status="error",
                error=f"Thao tác chưa đăng ký: {action.operation_name}",
                action_id=action.id,
            )

        merged_args = copy.deepcopy(latest.inputs)
        merged_args.update(action.params)
        if user_inputs:
            merged_args.update(user_inputs)

        ctx = dict(context or {})
        ctx["target_artifact"] = latest
        ctx["target_artifact_id"] = latest.id
        ctx["target_revision"] = latest.revision

        try:
            result = self.registry.execute(action.operation_name, merged_args, context=ctx)
        except Exception as exc:
            return DispatchResult(
                status="error",
                error=str(exc),
                action_id=action.id,
                artifact=latest,
            )

        if isinstance(result, InputRequest):
            result.target_artifact_id = latest.id
            result.target_revision = latest.revision
            return DispatchResult(
                status="needs_input",
                input_request=result,
                action_id=action.id,
                artifact=latest,
            )

        if isinstance(result, Artifact):
            # Ensure revision continuity if replacing target
            if result.id == latest.id:
                result.revision = latest.revision + 1
                result.provenance["parent_revision"] = latest.revision
            self.store.put(result)
            return DispatchResult(status="success", artifact=result, action_id=action.id)

        # Standard payload dict returned by handler
        new_rev = latest.revision + 1
        new_provenance = dict(latest.provenance)
        new_provenance.update({
            "parent_revision": latest.revision,
            "action_id": action.id,
            "operation_name": action.operation_name,
            "updated_at": time.time(),
        })

        title = latest.title
        if isinstance(result, dict) and "title" in result:
            title = result["title"]
        elif "name" in merged_args and latest.kind == "natal_chart":
            title = f"Lá số · {merged_args['name']}"

        new_artifact = Artifact(
            id=latest.id,
            kind=latest.kind,
            revision=new_rev,
            payload=result if isinstance(result, dict) else {"data": result},
            inputs=merged_args,
            provenance=new_provenance,
            title=title,
            status="ready",
        )
        self.store.put(new_artifact)
        return DispatchResult(status="success", artifact=new_artifact, action_id=action.id)

    def execute_operation(
        self,
        operation_name: str,
        args: Dict[str, Any],
        target_artifact_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DispatchResult:
        """Execute a named operation directly (e.g. from assistant tool loop)."""
        op = self.registry.get_operation(operation_name)
        if op is None:
            return DispatchResult(
                status="error",
                error=f"Công cụ không xác định: {operation_name}",
            )

        # If modifying an existing artifact
        if target_artifact_id:
            latest = self.store.get(target_artifact_id)
            if latest is None:
                return DispatchResult(
                    status="error",
                    error=f"Không tìm thấy kết quả: {target_artifact_id}",
                )
            action = ArtifactAction(
                id=f"op_{operation_name}_{int(time.time()*1000)}",
                label=operation_name,
                target_artifact_id=latest.id,
                target_revision=latest.revision,
                operation_name=operation_name,
                params=args,
            )
            return self.dispatch(action, context=context)

        # Creating a new artifact or querying
        ctx = dict(context or {})
        try:
            result = self.registry.execute(operation_name, args, context=ctx)
        except Exception as exc:
            return DispatchResult(status="error", error=str(exc))

        if isinstance(result, InputRequest):
            return DispatchResult(status="needs_input", input_request=result)

        if isinstance(result, Artifact):
            self.store.put(result)
            return DispatchResult(status="success", artifact=result)

        # If operation produces an artifact kind, package it into an Artifact
        kind = op.artifact_kind
        if kind and isinstance(result, (dict, list)):
            art_id = f"art-{kind}-{int(time.time()*1000)}"
            title = f"{op.description.split('.')[0]}"
            if kind == "natal_chart" and isinstance(result, dict) and "chart" in result:
                name = args.get("name") or "Lá số cá nhân"
                title = f"✧ Lá số · {name}"
            elif kind == "schedule":
                target_date = args.get("target_date", "hôm nay")
                title = f"Lịch học · {target_date}"
            elif kind == "document_search":
                title = f"Tệp tin · {args.get('query', '')}"

            payload = result if isinstance(result, dict) else {"items": result}
            new_art = Artifact(
                id=art_id,
                kind=kind,
                revision=1,
                payload=payload,
                inputs=copy.deepcopy(args),
                provenance={"operation_name": operation_name, "created_at": time.time()},
                title=title,
                status="ready",
            )
            self.store.put(new_art)
            return DispatchResult(status="success", artifact=new_art, result=result)

        return DispatchResult(status="success", artifact=None, result=result)
