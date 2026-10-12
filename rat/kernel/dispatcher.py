"""Execute registered operations, retaining results and input continuations."""
from __future__ import annotations

import copy
from uuid import uuid4

from rat.kernel.contracts import Artifact, ArtifactAction, DispatchResult, ExecutionEvent, ExecutionState, InputRequest
from rat.kernel.registry import CapabilityRegistry


class StaleRevisionError(ValueError):
    pass


class AmbiguousArtifactError(ValueError):
    pass


class ActionDispatcher:
    def __init__(self, registry: CapabilityRegistry, store):
        self.registry, self.store = registry, store
        self.state = ExecutionState()

    def reset(self):
        self.store.clear()
        self.state = ExecutionState()

    def _event(self, kind, name, generation, artifact=None, payload=None, error=None):
        if self.store.generation == generation:
            self.state.record_event(ExecutionEvent(kind, name, artifact.id if artifact else None, payload, error=error))
            self.state.events[:] = self.state.events[-100:]

    def resolve_target_artifact(self, kind, target_artifact_id=None):
        if target_artifact_id:
            art = self.store.get(target_artifact_id)
            if art is None or art.kind != kind:
                raise ValueError("Không tìm thấy kết quả phù hợp để thao tác.")
            return art, None
        matches = self.store.find_by_kind(kind)
        if len(matches) <= 1:
            return (matches[0] if matches else None), None
        return None, InputRequest(
            operation_name="select_target_artifact",
            candidate_choices=[{"id": a.id, "name": a.inputs.get("name") or a.title, "revision": a.revision} for a in matches],
            prompt="Bạn muốn thay đổi kết quả nào?",
        )

    def _waiting(self, request, generation):
        previous = self.store.get(request.id)
        art = Artifact(request.id, "input_request", (previous.revision + 1) if previous else 1,
                       request.to_dict(), title="Cần thêm thông tin", status="waiting_input")
        self.store.put(art, expected_generation=generation)
        self._event("waiting_input", request.operation_name, generation, art, request)
        return DispatchResult("needs_input", input_request=request, artifact=art, result=request.to_dict())

    def _run(self, op, args, context, target=None, request_id=None):
        generation = self.store.generation
        self._event("operation_started", op.name, generation)
        try:
            context.setdefault("artifact_store", self.store)
            result = self.registry.execute(op.name, args, context=context)
            if isinstance(result, dict) and (result.get("error") or result.get("found") is False):
                raise ValueError(result.get("error") or "Thao tác chưa tạo được kết quả.")
            if isinstance(result, InputRequest):
                if request_id:
                    result.id = request_id
                result.operation_name = op.name
                if target:
                    result.target_artifact_id, result.target_revision = target.id, target.revision
                return self._waiting(result, generation)
            if op.result_contract is not None:
                from rat.engine.task_state import validate_schema
                validate_schema(result, op.result_contract, path="result")
            if self.store.generation != generation:
                return DispatchResult("cancelled", error="cancelled:conversation_reset")
            artifact = None
            if isinstance(result, Artifact):
                artifact = result
            elif op.artifact_kind is not None:
                update = target is not None and op.updates_target and op.artifact_kind == target.kind
                payload = copy.deepcopy(result) if isinstance(result, dict) else {"items": copy.deepcopy(result)}
                artifact = Artifact(
                    target.id if update else "art-" + uuid4().hex, op.artifact_kind,
                    target.revision + 1 if update else 1, payload, copy.deepcopy(args),
                    {"operation_name": op.name, **({"parent_revision": target.revision} if update else {})},
                    payload.get("title") or (target.title if update else op.description.split('.')[0]),
                )
                # Store resolved birth data, including geocoded values, rather than partial invocation inputs.
                if isinstance(payload.get("chart"), dict):
                    artifact.inputs = copy.deepcopy(payload["chart"]["birth"])
                if target and not update:
                    artifact.provenance["source_artifact_id"] = target.id
                    artifact.provenance["source_revision"] = target.revision
            if artifact:
                update = target and artifact.id == target.id
                self.store.put(artifact, expected_revision=target.revision if update else None,
                               expected_generation=generation)
                self._event("artifact_updated" if update else "artifact_created", op.name, generation, artifact)
            if request_id:
                self.store.delete(request_id)
            pending = self.state.pending_input_request
            if pending and pending.operation_name == op.name:
                self.store.delete(pending.id)
                self.state.pending_input_request = None
            self._event("operation_completed", op.name, generation, artifact)
            return DispatchResult("success", artifact=artifact, result=result)
        except Exception as exc:
            error = str(exc)
            status = "cancelled" if error.startswith("cancelled:") else "stale_revision" if error == "stale_revision" else "error"
            self._event("operation_failed", op.name, generation, error=error)
            return DispatchResult(status, error=error, artifact=target)

    def dispatch(self, action: ArtifactAction, user_inputs=None, context=None):
        target = self.store.get(action.target_artifact_id)
        if target is None:
            return DispatchResult("error", error="Kết quả này không còn trong cuộc hội thoại.")
        if target.revision != action.target_revision:
            return DispatchResult("stale_revision", artifact=target, error="Thao tác trên phiên bản cũ. Hãy dùng điều khiển mới nhất.")
        op = self.registry.get_operation(action.operation_name)
        if op is None:
            return DispatchResult("error", error="Thao tác chưa đăng ký.")
        if op.target_kind and target.kind != op.target_kind:
            return DispatchResult("error", error="Thao tác không áp dụng cho loại kết quả này.")
        allowed = op.parameters.get("properties", {})
        args = {k: copy.deepcopy(v) for k, v in target.inputs.items() if k in allowed and v is not None} if op.updates_target else {}
        args.update(copy.deepcopy(action.params))
        args.update(copy.deepcopy(user_inputs or {}))
        ctx = dict(context or {}, target_artifact=target, target_artifact_id=target.id, target_revision=target.revision)
        return self._run(op, args, ctx, target=target)

    def execute_operation(self, operation_name, args, target_artifact_id=None, context=None):
        op = self.registry.get_operation(operation_name)
        if op is None:
            return DispatchResult("error", error=f"Công cụ không xác định: {operation_name}")
        args = copy.deepcopy(args)
        target_id = (args.pop("artifact_id", None) if op.target_kind else None) or target_artifact_id
        revision = args.pop("revision", None) if op.target_kind or target_id else None
        if op.target_kind or target_id:
            try:
                target, clarification = self.resolve_target_artifact(op.target_kind, target_id)
                if clarification:
                    clarification.operation_name = operation_name
                    clarification.supplied_inputs = args
                    return self._waiting(clarification, self.store.generation)
                if target is None:
                    return DispatchResult("error", error="Chưa có kết quả để thao tác. Hãy tạo hoặc chọn kết quả trước.")
                action = ArtifactAction("native-" + op.name, op.name, target.id,
                                        revision if revision is not None else target.revision, op.name, args)
                return self.dispatch(action, context=context)
            except ValueError as exc:
                return DispatchResult("error", error=str(exc))
        request = self.state.pending_input_request
        request_id = None
        if request and request.operation_name == operation_name:
            args = {**request.supplied_inputs, **args}
            request_id = request.id
        return self._run(op, args, dict(context or {}), request_id=request_id)

    def resume_input(self, request_id, values, context=None):
        artifact = self.store.get(request_id)
        if artifact is None or artifact.kind != "input_request":
            return DispatchResult("error", error="Yêu cầu nhập này đã kết thúc hoặc thuộc cuộc hội thoại cũ.")
        request = InputRequest.from_dict(artifact.payload)
        values = copy.deepcopy(values)
        selection = values.pop("selected_candidate", None)
        if selection is not None:
            choices = request.candidate_choices or []
            if type(selection) is not int or not 0 <= selection < len(choices):
                return DispatchResult("error", error="Lựa chọn không hợp lệ.")
            choice = choices[selection]
            if "id" in choice:
                request.target_artifact_id, request.target_revision = choice["id"], choice["revision"]
            else:
                values.update({k: choice[k] for k in ("latitude", "longitude", "timezone")})
                values["place"] = choice["name"]
        args = {**request.supplied_inputs, **values}
        if request.target_artifact_id:
            op = self.registry.get_operation(request.operation_name)
            target = self.store.get(request.target_artifact_id)
            if target is None or target.revision != request.target_revision:
                return DispatchResult("stale_revision", error="Kết quả đã đổi trong lúc nhập thông tin.")
            ctx = dict(context or {}, target_artifact=target)
            return self._run(op, args, ctx, target=target, request_id=request.id)
        return self._run(self.registry.get_operation(request.operation_name), args, dict(context or {}), request_id=request.id)
