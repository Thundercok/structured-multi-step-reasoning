"""
rat.kernel.capabilities.natal — Natal chart capability adapter.

Provides registered operations:
- search_birth_places: coordinates and timezone candidate search
- create_natal_chart: deterministic chart calculation with InputRequest for missing data
- update_birth_data: direct or model-driven modification with revision management
- export_natal_chart: headless export to SVG, PNG, PDF
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from rat.astrology.chart import BirthData, calculate_chart
from rat.astrology.places import Place, search_places
from rat.astrology.export import export_chart
from rat.kernel.contracts import Artifact, ArtifactAction, InputRequest
from rat.kernel.registry import Capability, OperationDefinition


def create_natal_capability() -> Capability:
    capability = Capability(
        name="natal_chart",
        title="Bản đồ sao cá nhân",
        description="Lập bản đồ sao chiêm tinh chính xác, tra cứu tọa độ nơi sinh và xuất biểu đồ.",
    )

    def handle_search_places(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        query = args.get("query", "").strip()
        if not query:
            raise ValueError("Query không được để trống")
        from rat.astrology.places import search_places
        places = search_places(query)
        return [asdict(p) for p in places]

    def handle_create_chart(args: Dict[str, Any], **context) -> Any:
        # Check required fields
        name = args.get("name", "Lá số cá nhân")
        date = args.get("date")
        time_val = args.get("time")
        place = args.get("place")
        latitude = args.get("latitude")
        longitude = args.get("longitude")
        timezone = args.get("timezone")
        time_known = args.get("time_known", True)

        supplied = {k: v for k, v in args.items() if v is not None}
        missing_fields = []

        if not date:
            missing_fields.append({
                "name": "date",
                "label": "Ngày sinh",
                "type": "date",
                "description": "Định dạng YYYY-MM-DD",
                "required": True,
            })
        if not time_val and time_known:
            missing_fields.append({
                "name": "time",
                "label": "Giờ sinh",
                "type": "time",
                "description": "Định dạng HH:MM",
                "required": True,
            })
        if not place:
            missing_fields.append({
                "name": "place",
                "label": "Nơi sinh",
                "type": "string",
                "description": "Tên thành phố hoặc tỉnh/thành",
                "required": True,
            })

        candidates = None
        if (latitude is None or longitude is None or timezone is None) and place:
            from rat.astrology.places import search_places
            try:
                candidates = search_places(place)
            except Exception:
                candidates = ()

            if not candidates:
                missing_fields.append({
                    "name": "place",
                    "label": "Nơi sinh",
                    "type": "string",
                    "description": "Không tìm thấy tọa độ. Vui lòng nhập lại tên thành phố",
                    "required": True,
                })
            elif len(candidates) == 1:
                chosen = candidates[0]
                latitude = chosen.latitude
                longitude = chosen.longitude
                timezone = chosen.timezone
                supplied["latitude"] = latitude
                supplied["longitude"] = longitude
                supplied["timezone"] = timezone

        candidate_choices = [asdict(c) for c in candidates] if (candidates and len(candidates) > 1 and "selected_candidate" not in args) else None

        if missing_fields or candidate_choices:
            return InputRequest(
                operation_name="create_natal_chart",
                supplied_inputs=supplied,
                missing_fields=missing_fields,
                candidate_choices=candidate_choices,
                prompt="Vui lòng cung cấp thêm thông tin ngày, giờ hoặc chọn nơi sinh để lập lá số chính xác.",
            )

        # Build BirthData and calculate chart
        birth_params = {
            "name": name,
            "date": str(date),
            "time": "12:00" if not time_known else str(time_val),
            "place": str(place),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "timezone": str(timezone),
            "time_known": bool(time_known),
            "house_system": args.get("house_system", "P"),
            "zodiac": args.get("zodiac", "tropical"),
            "fold": args.get("fold"),
            "max_orb": float(args.get("max_orb", 8.0)),
        }

        chart = calculate_chart(BirthData(**birth_params))
        return {
            "chart": chart.to_dict(),
            "title": f"✧ Lá số · {name}",
        }

    def handle_update_birth(args: Dict[str, Any], **context) -> Any:
        target_art = context.get("target_artifact")
        existing_inputs = target_art.inputs if target_art else {}
        merged = dict(existing_inputs)
        merged.update({k: v for k, v in args.items() if v is not None and v != ""})
        # If place changed, clear old coords so they are re-queried
        if "place" in args and args["place"] != existing_inputs.get("place"):
            merged.pop("latitude", None)
            merged.pop("longitude", None)
            merged.pop("timezone", None)
        return handle_create_chart(merged, **context)

    def handle_export_chart(args: Dict[str, Any], **context) -> Dict[str, Any]:
        target_art = context.get("target_artifact")
        if not target_art:
            raise ValueError("Cần lá số mục tiêu để xuất.")
        chart_dict = target_art.payload.get("chart", target_art.payload)
        birth_data = BirthData(**chart_dict["birth"])
        chart = calculate_chart(birth_data)

        fmt = args.get("format", "svg")
        out_path = args.get("output_path")
        if not out_path:
            name_slug = birth_data.name.replace(" ", "_").lower()
            out_path = Path.home() / f"la_so_{name_slug}.{fmt}"

        exported = export_chart(chart, out_path, format=fmt)
        return {
            "exported_path": str(exported),
            "format": fmt,
            "filename": exported.name,
            "message": f"Đã xuất thành công tại: {exported}",
        }

    def chart_available_actions(artifact: Artifact) -> List[ArtifactAction]:
        chart_data = artifact.payload.get("chart", artifact.payload)
        birth = chart_data.get("birth", artifact.inputs)
        current_time = birth.get("time", "12:00")
        return [
            ArtifactAction(
                id=f"act_edit_time_{artifact.id}_{artifact.revision}",
                label="Đổi giờ sinh",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="update_birth_data",
                params={"time": current_time},
                description="Điều chỉnh giờ sinh và tính lại lá số",
            ),
            ArtifactAction(
                id=f"act_export_svg_{artifact.id}_{artifact.revision}",
                label="Xuất SVG",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="export_natal_chart",
                params={"format": "svg"},
                description="Xuất tệp vector SVG",
            ),
            ArtifactAction(
                id=f"act_export_png_{artifact.id}_{artifact.revision}",
                label="Xuất PNG",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="export_natal_chart",
                params={"format": "png"},
                description="Xuất ảnh PNG độ phân giải cao",
            ),
            ArtifactAction(
                id=f"act_export_pdf_{artifact.id}_{artifact.revision}",
                label="Xuất PDF",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="export_natal_chart",
                params={"format": "pdf"},
                description="Xuất tài liệu vector PDF",
            ),
        ]

    capability.register_operation(OperationDefinition(
        name="search_birth_places",
        description="Look up actual coordinates and IANA timezones for a birth city/place. Query only the place name, never a person's name or birth date/time. Returns candidates; ask which one when ambiguous. Use observed coordinates rather than guessing.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "minLength": 2, "maxLength": 200}},
            "required": ["query"],
        },
        handler=handle_search_places,
    ))

    capability.register_operation(OperationDefinition(
        name="create_natal_chart",
        description="Calculate a real natal astrology chart from birth date, local birth time, coordinates and IANA timezone. Ask for missing birth information; never invent it. Look up coordinates with search_birth_places. When time is unknown, use time_known=false and time=12:00 only as a provisional epoch; houses/axes are omitted.",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "maxLength": 100},
                "date": {"type": "string"},
                "time": {"type": "string"},
                "place": {"type": "string"},
                "latitude": {"type": "number", "minimum": -89.9, "maximum": 89.9},
                "longitude": {"type": "number", "minimum": -180, "maximum": 180},
                "timezone": {"type": "string"},
                "time_known": {"type": "boolean"},
                "house_system": {"type": "string", "enum": ["P", "W", "E", "K", "O", "R"]},
                "zodiac": {"type": "string", "enum": ["tropical", "sidereal_lahiri"]},
                "fold": {"type": "integer", "enum": [0, 1]},
                "max_orb": {"type": "number", "minimum": 0.1, "maximum": 10},
            },
            "required": ["date", "time", "place", "latitude", "longitude", "timezone"],
        },
        handler=handle_create_chart,
        artifact_kind="natal_chart",
        available_actions=chart_available_actions,
    ))

    capability.register_operation(OperationDefinition(
        name="update_birth_data",
        description="Update birth time, date, or location on an existing calculated natal chart and recalculate.",
        parameters={
            "type": "object",
            "properties": {
                "time": {"type": "string"},
                "date": {"type": "string"},
                "place": {"type": "string"},
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "timezone": {"type": "string"},
            },
        },
        handler=handle_update_birth,
        artifact_kind="natal_chart",
        available_actions=chart_available_actions,
    ))

    capability.register_operation(OperationDefinition(
        name="export_natal_chart",
        description="Export the active natal chart to SVG, PNG, or PDF file on disk.",
        parameters={
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": ["svg", "png", "pdf"]},
                "output_path": {"type": "string"},
            },
            "required": ["format"],
        },
        handler=handle_export_chart,
    ))

    return capability
