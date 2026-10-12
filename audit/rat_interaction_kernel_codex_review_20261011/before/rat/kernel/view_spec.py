"""
rat.kernel.view_spec — Declarative, versioned presentation contracts.

Independent of Qt widgets and AI model inference.
Defines:
- ViewBlock: primitive component vocabulary (summary, table, resource, input_form, actions, details)
- ViewSpec: versioned tree of blocks referencing real artifact data
- ViewProvider protocol & StandardViewProvider
- validate_view_spec: rejects unknown schemas, invented fields, and unregistered actions

Prepares architectural boundaries for future AI view proposals without code execution.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Tuple

from rat.kernel.contracts import Artifact, ArtifactAction, InputRequest
from rat.kernel.registry import CapabilityRegistry


SUPPORTED_SCHEMA_VERSIONS = {1}
SUPPORTED_BLOCK_TYPES = {
    "summary",
    "table",
    "rows",
    "resource",
    "input_form",
    "actions",
    "details",
}


@dataclass
class ViewBlock:
    """A single declarative UI block in a ViewSpec."""

    type: str  # "summary", "table", "rows", "resource", "input_form", "actions", "details"
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": copy.deepcopy(self.data),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewBlock:
        return cls(
            type=data.get("type", "summary"),
            data=dict(data.get("data", {})),
        )


@dataclass
class ViewSpec:
    """A versioned declarative presentation tree bound to an artifact revision."""

    schema_version: int
    artifact_id: str
    revision: int
    title: str = ""
    blocks: List[ViewBlock] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "revision": self.revision,
            "title": self.title,
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ViewSpec:
        blocks = [ViewBlock.from_dict(b) for b in data.get("blocks", [])]
        return cls(
            schema_version=data.get("schema_version", 1),
            artifact_id=data.get("artifact_id", ""),
            revision=data.get("revision", 1),
            title=data.get("title", ""),
            blocks=blocks,
        )


class ViewProvider(Protocol):
    """Protocol for providers that produce declarative ViewSpecs from artifacts."""

    def provide_view(self, artifact: Artifact, context: Optional[Dict[str, Any]] = None) -> ViewSpec:
        ...


def validate_view_spec(
    spec: ViewSpec,
    artifact: Artifact,
    registry: Optional[CapabilityRegistry] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Validate a ViewSpec against the artifact and registered capabilities.
    Rejects unknown versions, invalid artifact references, unsupported blocks,
    and invented actions/fields.
    """
    if spec.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        return False, f"unsupported_schema_version:{spec.schema_version}"

    if spec.artifact_id != artifact.id:
        return False, f"artifact_id_mismatch:{spec.artifact_id}!={artifact.id}"

    if spec.revision != artifact.revision:
        return False, f"revision_mismatch:{spec.revision}!={artifact.revision}"

    payload = artifact.payload or {}

    for i, block in enumerate(spec.blocks):
        if block.type not in SUPPORTED_BLOCK_TYPES:
            return False, f"unsupported_block_type:{block.type} at index {i}"

        data = block.data

        # Check field references in summary
        if block.type == "summary" and "fields" in data:
            for f in data["fields"]:
                if f not in payload and not any(f in str(v) for v in payload.values()):
                    # Field does not exist in payload
                    return False, f"invalid_field_reference:{f} in block {i}"

        # Check resource references
        if block.type == "resource":
            res = data.get("resource")
            if not res:
                return False, f"missing_resource_reference in block {i}"
            # Resource must either have inline data or correspond to known renderer
            if res not in ("wheel", "poster", "document_preview", "icon") and not data.get("content"):
                return False, f"unknown_resource_reference:{res} in block {i}"

        # Check action references
        if block.type == "actions" and "action_ids" in data:
            action_ids = data["action_ids"]
            # If actions are declared, ensure they are registered operations or valid action IDs
            if registry:
                for aid in action_ids:
                    # Check if action corresponds to an operation or declared action
                    op = registry.get_operation(aid)
                    valid_prefixes = ("edit_", "update_", "export_", "read_", "locate_", "refresh_", "submit_", "cancel_")
                    if op is None and not any(aid.startswith(prefix) for prefix in valid_prefixes):
                        return False, f"unregistered_action_id:{aid} in block {i}"

    return True, None


class StandardViewProvider:
    """Standard built-in provider generating predictable, complete views for core artifacts."""

    def provide_view(self, artifact: Artifact, context: Optional[Dict[str, Any]] = None) -> ViewSpec:
        kind = artifact.kind
        ctx = context or {}

        if kind == "natal_chart":
            return self._view_natal_chart(artifact, ctx)
        elif kind == "schedule":
            return self._view_schedule(artifact, ctx)
        elif kind == "document_search":
            return self._view_document_search(artifact, ctx)
        elif kind == "document_content":
            return self._view_document_content(artifact, ctx)
        elif kind == "input_request":
            return self._view_input_request(artifact, ctx)

        # Default fallback view for custom/test capabilities
        return self._view_generic(artifact, ctx)

    def _view_natal_chart(self, artifact: Artifact, context: Dict[str, Any]) -> ViewSpec:
        chart_data = artifact.payload.get("chart", artifact.payload)
        birth = chart_data.get("birth", artifact.inputs)
        name = birth.get("name", "Lá số cá nhân")
        date = birth.get("date", "")
        time_val = birth.get("time", "")
        place = birth.get("place", "")

        # Summary of big three
        positions = chart_data.get("positions", [])
        angles = chart_data.get("angles", {})
        sun = next((p.get("sign") for p in positions if p.get("id") == "sun"), "Mặt Trời")
        moon = next((p.get("sign") for p in positions if p.get("id") == "moon"), "Mặt Trăng")
        asc = angles.get("ASC")
        asc_sign = ""
        if asc is not None and isinstance(asc, (int, float)):
            from rat.astrology.chart import SIGNS
            sign_idx = int(asc // 30) % 12
            asc_sign = SIGNS[sign_idx][0]

        blocks: List[ViewBlock] = []

        # 1. Summary
        blocks.append(ViewBlock(
            type="summary",
            data={
                "title": f"✧ {name} · {date} {time_val} ({place})",
                "text": f"Mặt Trời: {sun} · Mặt Trăng: {moon}" + (f" · Cung Mọc: {asc_sign}" if asc_sign else ""),
                "badge": f"Phiên bản {artifact.revision}",
            },
        ))

        # 2. Resource: interactive vector wheel
        blocks.append(ViewBlock(
            type="resource",
            data={
                "resource": "wheel",
                "chart_data": chart_data,
            },
        ))

        # 3. Actions: quick controls
        blocks.append(ViewBlock(
            type="actions",
            data={
                "action_ids": ["update_birth_data", "export_natal_chart"],
                "actions": [
                    {
                        "id": "edit_time",
                        "label": "Đổi giờ sinh",
                        "operation": "update_birth_data",
                        "input_field": "time",
                        "current_value": time_val,
                    },
                    {
                        "id": "export_svg",
                        "label": "Xuất SVG",
                        "operation": "export_natal_chart",
                        "params": {"format": "svg"},
                    },
                    {
                        "id": "export_png",
                        "label": "Xuất PNG",
                        "operation": "export_natal_chart",
                        "params": {"format": "png"},
                    },
                    {
                        "id": "export_pdf",
                        "label": "Xuất PDF",
                        "operation": "export_natal_chart",
                        "params": {"format": "pdf"},
                    },
                ],
            },
        ))

        # 4. Details: positions & houses table
        pos_rows = []
        for p in positions:
            pos_rows.append([
                p.get("name", ""),
                p.get("glyph", ""),
                f"{p.get('sign', '')} {p.get('degree', 0):.2f}°",
                f"Nhà {p.get('house')}" if p.get("house") else "—",
            ])

        blocks.append(ViewBlock(
            type="details",
            data={
                "title": "Bảng vị trí thiên thể & góc chiếu",
                "table_headers": ["Thiên thể", "Ký hiệu", "Tọa độ", "Nhà"],
                "table_rows": pos_rows,
            },
        ))

        return ViewSpec(
            schema_version=1,
            artifact_id=artifact.id,
            revision=artifact.revision,
            title=f"Lá số · {name}",
            blocks=blocks,
        )

    def _view_schedule(self, artifact: Artifact, context: Dict[str, Any]) -> ViewSpec:
        items = artifact.payload.get("items", [])
        day_label = artifact.inputs.get("target_date", "Hôm nay")

        rows = []
        for s in items:
            rows.append([
                s.get("time", ""),
                s.get("course_name", ""),
                s.get("room", ""),
                s.get("instructor", ""),
            ])

        blocks = [
            ViewBlock(
                type="summary",
                data={
                    "title": f"Lịch học · {day_label}",
                    "text": f"Có {len(items)} ca học được ghi nhận.",
                },
            ),
            ViewBlock(
                type="table",
                data={
                    "headers": ["Thời gian", "Môn học", "Phòng", "Giảng viên"],
                    "rows": rows,
                    "items": items,
                },
            ),
            ViewBlock(
                type="actions",
                data={
                    "action_ids": ["get_schedule"],
                    "actions": [
                        {"id": "refresh_today", "label": "Hôm nay", "operation": "get_schedule", "params": {"target_date": "today"}},
                        {"id": "view_tomorrow", "label": "Ngày mai", "operation": "get_schedule", "params": {"target_date": "tomorrow"}},
                    ],
                },
            ),
        ]

        return ViewSpec(
            schema_version=1,
            artifact_id=artifact.id,
            revision=artifact.revision,
            title=f"Lịch học · {day_label}",
            blocks=blocks,
        )

    def _view_document_search(self, artifact: Artifact, context: Dict[str, Any]) -> ViewSpec:
        results = artifact.payload.get("items", artifact.payload.get("results", []))
        query = artifact.inputs.get("query", "")

        file_rows = []
        for f in results:
            file_rows.append([
                f.get("filename", ""),
                f.get("snippet", ""),
                f.get("path", ""),
            ])

        blocks = [
            ViewBlock(
                type="summary",
                data={
                    "title": f"Tìm kiếm tệp: {query}",
                    "text": f"Tìm thấy {len(results)} tệp liên quan trong chỉ mục.",
                },
            ),
            ViewBlock(
                type="table",
                data={
                    "headers": ["Tên tệp", "Nội dung", "Đường dẫn"],
                    "rows": file_rows,
                    "files": results,
                },
            ),
            ViewBlock(
                type="actions",
                data={
                    "action_ids": ["read_document"],
                    "actions": [
                        {
                            "id": f"read_{i}",
                            "label": f"Đọc {f.get('filename')}",
                            "operation": "read_document",
                            "params": {"file_path": f.get("path")},
                        }
                        for i, f in enumerate(results[:3])
                    ],
                },
            ),
        ]

        return ViewSpec(
            schema_version=1,
            artifact_id=artifact.id,
            revision=artifact.revision,
            title=f"Tài liệu · {query}",
            blocks=blocks,
        )

    def _view_document_content(self, artifact: Artifact, context: Dict[str, Any]) -> ViewSpec:
        doc = artifact.payload
        filename = doc.get("filename", "Tài liệu")
        content = doc.get("content", "")
        chars = doc.get("total_chars", len(content))

        blocks = [
            ViewBlock(
                type="summary",
                data={
                    "title": f"Nội dung tệp · {filename}",
                    "text": f"Đã đọc {len(content)} / {chars} ký tự.",
                },
            ),
            ViewBlock(
                type="details",
                data={
                    "title": "Trích xuất văn bản",
                    "content": content,
                },
            ),
        ]

        return ViewSpec(
            schema_version=1,
            artifact_id=artifact.id,
            revision=artifact.revision,
            title=f"Đọc tệp · {filename}",
            blocks=blocks,
        )

    def _view_input_request(self, artifact: Artifact, context: Dict[str, Any]) -> ViewSpec:
        req_data = artifact.payload
        prompt = req_data.get("prompt", "Vui lòng nhập thêm thông tin.")
        missing = req_data.get("missing_fields", [])
        candidates = req_data.get("candidate_choices")
        supplied = req_data.get("supplied_inputs", {})

        blocks = [
            ViewBlock(
                type="summary",
                data={
                    "title": "Cần thêm thông tin",
                    "text": prompt,
                },
            ),
            ViewBlock(
                type="input_form",
                data={
                    "operation_name": req_data.get("operation_name", ""),
                    "missing_fields": missing,
                    "candidate_choices": candidates,
                    "supplied_inputs": supplied,
                },
            ),
        ]

        return ViewSpec(
            schema_version=1,
            artifact_id=artifact.id,
            revision=artifact.revision,
            title="Nhập thông tin",
            blocks=blocks,
        )

    def _view_generic(self, artifact: Artifact, context: Dict[str, Any]) -> ViewSpec:
        blocks = [
            ViewBlock(
                type="summary",
                data={
                    "title": artifact.title or f"{artifact.kind} #{artifact.id}",
                    "text": f"Loại: {artifact.kind} · Phiên bản {artifact.revision}",
                },
            ),
            ViewBlock(
                type="details",
                data={
                    "title": "Dữ liệu kết quả",
                    "content": str(artifact.payload),
                },
            ),
        ]
        return ViewSpec(
            schema_version=1,
            artifact_id=artifact.id,
            revision=artifact.revision,
            title=artifact.title or artifact.kind,
            blocks=blocks,
        )
