"""
rat.kernel.capabilities.timetable — Class schedule and campus calendar capability.

Registers:
- get_schedule: timetable retrieval for today/tomorrow/dates
- locate_room: campus building & floor room resolution
- get_group_availability: weekly golden windows across club members
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import re
from typing import Any, Dict, List, Optional

from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.data import load_club_members
from rat.timetable.model import TDTU_PERIODS, resolve_room_location


def create_timetable_capability(compositor: Optional[TimetableCompositor] = None) -> Capability:
    comp = compositor or TimetableCompositor(load_club_members())

    capability = Capability(
        name="timetable",
        title="Thời khóa biểu",
        description="Tra cứu lịch học sinh viên, phòng học và khung giờ rảnh nhóm.",
    )

    def handle_get_schedule(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        if context.get("get_schedule"):
            return context["get_schedule"](args.get("target_date", "today"), args.get("member_id") or context.get("member_id"), context.get("now_dt"))
        target_date = args.get("target_date", "today")
        member_id = args.get("member_id") or context.get("member_id")
        now_dt = context.get("now_dt") or datetime.now()

        # Re-use timetable logic
        active_members = comp.members
        if not active_members:
            return []
        member = next((m for m in active_members if m.id == member_id), None) if member_id else active_members[0]
        if not member:
            raise ValueError(f"Không tìm thấy sinh viên có mã: {member_id}")

        weekday_code_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
        weekday_name_map = {"T2": "Thứ Hai", "T3": "Thứ Ba", "T4": "Thứ Tư", "T5": "Thứ Năm",
                            "T6": "Thứ Sáu", "T7": "Thứ Bảy", "CN": "Chủ Nhật"}

        target_str = (target_date or "today").strip().lower()
        today_idx = now_dt.weekday()
        is_today = False
        selected_code = None

        if target_str in ("today", "hôm nay", "hom nay"):
            selected_code = weekday_code_map[today_idx]
            is_today = True
        elif target_str in ("tomorrow", "ngày mai", "ngay mai"):
            selected_code = weekday_code_map[(today_idx + 1) % 7]
        elif target_str in ("next", "tiếp theo", "tiep theo"):
            for offset in range(7):
                code = weekday_code_map[(today_idx + offset) % 7]
                if member.schedule.get(code):
                    selected_code = code
                    is_today = (offset == 0)
                    break
        else:
            for code, name in weekday_name_map.items():
                if target_str in (code.lower(), name.lower()):
                    selected_code = code
                    break

        if not selected_code:
            try:
                requested = datetime.strptime(target_str, "%Y-%m-%d")
                selected_code = weekday_code_map[requested.weekday()]
                is_today = requested.date() == now_dt.date()
            except ValueError:
                raise ValueError("Ngày không hợp lệ; dùng YYYY-MM-DD, today, tomorrow hoặc next")

        raw_sessions = sorted(member.schedule.get(selected_code, []), key=lambda s: s.start_period)
        day_label = weekday_name_map.get(selected_code, selected_code)

        results = []
        now_mins = now_dt.hour * 60 + now_dt.minute

        for s in raw_sessions:
            p_start = TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
            p_end = TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]

            status = "scheduled"
            if is_today:
                try:
                    sh, sm = map(int, p_start.split(":"))
                    eh, em = map(int, p_end.split(":"))
                    start_m = sh * 60 + sm
                    end_m = eh * 60 + em
                    if now_mins > end_m:
                        status = "completed"
                    elif start_m <= now_mins <= end_m:
                        status = "live"
                    else:
                        status = "upcoming"
                except Exception:
                    status = "scheduled"

            results.append({
                "course_name": s.course_name,
                "course_code": s.course_code,
                "room": s.room,
                "day": day_label,
                "day_code": selected_code,
                "time": f"{p_start} - {p_end}",
                "start_period": s.start_period,
                "end_period": s.end_period,
                "instructor": getattr(s, "lecturer", ""),
                "degree_level": s.degree_level,
                "status": status,
            })

        return results

    def handle_locate_room(args: Dict[str, Any], **context) -> Dict[str, Any]:
        room = args.get("room", "")
        return {"room": room, "location": resolve_room_location(room)}

    def handle_group_availability(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        return [asdict(w) for w in comp.find_golden_windows(min_ratio=0.8)[:5]]

    def schedule_actions(artifact: Artifact) -> List[ArtifactAction]:
        return [
            ArtifactAction(
                id=f"act_sched_today_{artifact.id}_{artifact.revision}",
                label="Hôm nay",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="get_schedule",
                params={"target_date": "today"},
            ),
            ArtifactAction(
                id=f"act_sched_tomorrow_{artifact.id}_{artifact.revision}",
                label="Ngày mai",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="get_schedule",
                params={"target_date": "tomorrow"},
            ),
        ]

    capability.register_operation(OperationDefinition(
        name="get_schedule",
        description=(
            "Retrieve student class schedule for today, tomorrow, or a specific day. "
            "Returns upcoming courses, rooms, start/end periods, and instructors."
        ),
        parameters={
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": "Target day to check: 'today', 'tomorrow', 'next', 'T2'..'CN', ISO date YYYY-MM-DD.",
                    "default": "today",
                },
                "member_id": {
                    "type": "string",
                    "description": "Optional member identifier. Defaults to active student.",
                },
            },
        },
        handler=handle_get_schedule,
        artifact_kind="schedule",
        available_actions=schedule_actions,
        updates_target=True,
    ))

    capability.register_operation(OperationDefinition(
        name="locate_room",
        description="Look up a campus room location from the local campus map.",
        parameters={
            "type": "object",
            "properties": {"room": {"type": "string"}},
            "required": ["room"],
        },
        handler=handle_locate_room,
    ))

    capability.register_operation(OperationDefinition(
        name="get_group_availability",
        description="Find weekly time windows when club members are available.",
        parameters={"type": "object", "properties": {}},
        handler=handle_group_availability,
    ))

    return capability
