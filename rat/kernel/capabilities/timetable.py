"""
rat.kernel.capabilities.timetable — Universal Multi-Mode Timetable & Campus Scheduling Capability.

Exposes Agentic Reasoning Tools for:
- get_schedule: student course timetable lookup (Vietnam shifts & US clock time-blocks)
- locate_room: campus building, hall, and floor resolution (TDTU & US Universities)
- get_group_availability: weekly golden windows across club/group members
- find_free_slots: continuous clock timeline free time gap search
- detect_conflicts: session overlap, tight turnaround, and campus travel warnings
- auto_arrange_schedule: smart arrangement of study sessions, office hours, and group meetings
- export_schedule: RFC 5545 iCalendar (.ics) export
- import_schedule: RFC 5545 iCalendar (.ics) import
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import re
from typing import Any, Dict, List, Optional, Tuple

from rat.kernel.contracts import Artifact, ArtifactAction
from rat.kernel.registry import Capability, OperationDefinition
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.data import get_all_sample_members, load_club_members
from rat.timetable.model import (
    DAYS,
    DAY_TO_EN,
    DAY_TO_VN,
    TDTU_PERIODS,
    ClassSession,
    MemberSchedule,
    minutes_to_time,
    normalize_day_code,
    resolve_room_location,
    time_to_minutes,
)


def resolve_target_day_code(target_str: str, now_dt: datetime) -> Tuple[str, str, bool]:
    """
    Resolves various day expressions into (canonical_day_code, day_label, is_today).
    Handles Vietnamese, English, relative words ('today', 'tomorrow', 'next'), and ISO dates.
    """
    weekday_code_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
    raw = (target_str or "today").strip().lower()
    today_idx = now_dt.weekday()

    if raw in ("today", "hôm nay", "hom nay", "nay"):
        code = weekday_code_map[today_idx]
        return code, DAY_TO_VN.get(code, code), True

    if raw in ("tomorrow", "ngày mai", "ngay mai", "mai"):
        code = weekday_code_map[(today_idx + 1) % 7]
        return code, DAY_TO_VN.get(code, code), False

    if raw in ("next", "tiếp theo", "tiep theo"):
        code = weekday_code_map[today_idx]
        return code, DAY_TO_VN.get(code, code), True

    # Try canonical code or aliases
    norm = normalize_day_code(raw)
    if norm in DAY_TO_VN:
        is_today = (norm == weekday_code_map[today_idx])
        return norm, DAY_TO_VN[norm], is_today

    # Try ISO date YYYY-MM-DD
    try:
        dt = datetime.strptime(raw, "%Y-%m-%d")
        code = weekday_code_map[dt.weekday()]
        return code, DAY_TO_VN.get(code, code), (dt.date() == now_dt.date())
    except ValueError:
        pass

    # Try DD/MM/YYYY
    try:
        dt = datetime.strptime(raw, "%d/%m/%Y")
        code = weekday_code_map[dt.weekday()]
        return code, DAY_TO_VN.get(code, code), (dt.date() == now_dt.date())
    except ValueError:
        pass

    raise ValueError(f"Ngày không hợp lệ: '{target_str}'. Hãy dùng today, tomorrow, T2..CN, Monday..Sunday, hoặc YYYY-MM-DD.")


def create_timetable_capability(compositor: Optional[TimetableCompositor] = None) -> Capability:
    if compositor is None:
        try:
            members = load_club_members()
            # Also ensure sample US student is available in memory if not present
            if not any(m.id == "us_alex" for m in members):
                from rat.timetable.data import get_sample_us_member
                members = list(members) + [get_sample_us_member()]
            comp = TimetableCompositor(members)
        except Exception:
            comp = TimetableCompositor(get_all_sample_members())
    else:
        comp = compositor

    capability = Capability(
        name="timetable",
        title="Thời khóa biểu & Lịch học",
        description="Tra cứu lịch học sinh viên, phòng học, phát hiện xung đột, tìm giờ rảnh và điều phối lịch học tự động.",
    )

    def _resolve_member(member_id: Optional[str]) -> MemberSchedule:
        active_members = comp.members
        if not active_members:
            raise ValueError("Chưa có hồ sơ sinh viên nào trong hệ thống thời khóa biểu.")
        if member_id:
            m = next((mem for mem in active_members if mem.id == member_id or mem.name.lower() == member_id.lower()), None)
            if m:
                return m
            raise ValueError(f"Không tìm thấy sinh viên có mã/tên: '{member_id}'.")
        return active_members[0]

    # 1. Operation: get_schedule
    def handle_get_schedule(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        target_date = args.get("target_date", "today")
        member_id = args.get("member_id") or context.get("member_id")
        mode_filter = args.get("mode", "all")
        now_dt = context.get("now_dt") or datetime.now()

        member = _resolve_member(member_id)
        selected_code, day_label, is_today = resolve_target_day_code(target_date, now_dt)

        raw_sessions = member.get_day_sessions(selected_code)
        results: List[Dict[str, Any]] = []
        now_mins = now_dt.hour * 60 + now_dt.minute

        for s in raw_sessions:
            if mode_filter == "period" and s.mode != "period":
                continue
            if mode_filter == "clock" and s.mode != "clock":
                continue

            start_m = s.start_minutes
            end_m = s.end_minutes
            p_start = s.start_time or minutes_to_time(start_m)
            p_end = s.end_time or minutes_to_time(end_m)

            status = "scheduled"
            if is_today:
                if now_mins > end_m:
                    status = "completed"
                elif start_m <= now_mins <= end_m:
                    status = "live"
                else:
                    status = "upcoming"

            results.append({
                "course_name": s.course_name,
                "course_code": s.course_code,
                "room": s.room,
                "building": s.building,
                "day": day_label,
                "day_code": selected_code,
                "time": f"{p_start} - {p_end}",
                "start_time": p_start,
                "end_time": p_end,
                "start_period": s.start_period,
                "end_period": s.end_period,
                "instructor": getattr(s, "lecturer", ""),
                "degree_level": s.degree_level,
                "credits": s.credits,
                "mode": s.mode,
                "status": status,
                "badge": s.badge_text,
                "institution": member.institution,
            })

        return results

    # 2. Operation: locate_room
    def handle_locate_room(args: Dict[str, Any], **context) -> Dict[str, Any]:
        room = args.get("room", "")
        building = args.get("building", "")
        return {
            "room": room,
            "building": building,
            "location": resolve_room_location(room, building=building),
        }

    # 3. Operation: get_group_availability
    def handle_group_availability(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        min_ratio = float(args.get("min_ratio", 0.8))
        return [asdict(w) for w in comp.find_golden_windows(min_ratio=min_ratio)[:8]]

    # 4. Operation: find_free_slots
    def handle_find_free_slots(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        target_day = args.get("day", args.get("day_code", "today"))
        min_mins = int(args.get("min_minutes", 60))
        day_start = args.get("day_start_time", "08:00")
        day_end = args.get("day_end_time", "21:00")
        member_id = args.get("member_id") or context.get("member_id")
        now_dt = context.get("now_dt") or datetime.now()

        selected_code, day_name, _ = resolve_target_day_code(target_day, now_dt)
        slots = comp.find_free_slots_clock(
            day_code=selected_code,
            min_minutes=min_mins,
            day_start_time=day_start,
            day_end_time=day_end,
            member_id=member_id,
        )
        for slot in slots:
            slot["day_name"] = day_name
        return slots

    # 5. Operation: detect_conflicts
    def handle_detect_conflicts(args: Dict[str, Any], **context) -> List[Dict[str, Any]]:
        member_id = args.get("member_id") or context.get("member_id")
        member = _resolve_member(member_id)
        conflicts = comp.detect_schedule_conflicts(member)
        return [
            {
                "day_code": c.day_code,
                "day_name": c.day_name,
                "conflict_type": c.conflict_type,
                "session_a": c.session_a.course_name,
                "session_b": c.session_b.course_name,
                "message": c.message,
            }
            for c in conflicts
        ]

    # 6. Operation: auto_arrange_schedule
    def handle_auto_arrange_schedule(args: Dict[str, Any], **context) -> Dict[str, Any]:
        title = args.get("title", "Buổi họp / Học nhóm")
        duration = int(args.get("duration_minutes", 60))
        target_day = args.get("target_day", "today")
        preferred = args.get("preferred_window", "afternoon")
        member_id = args.get("member_id") or context.get("member_id")
        now_dt = context.get("now_dt") or datetime.now()

        selected_code, day_name, _ = resolve_target_day_code(target_day, now_dt)
        res = comp.auto_arrange_event(
            title=title,
            duration_minutes=duration,
            target_day=selected_code,
            preferred_window=preferred,
            member_id=member_id,
        )
        if not res:
            return {
                "success": False,
                "message": f"Không tìm thấy khoảng trống {duration} phút phù hợp vào {day_name} ({selected_code}).",
            }
        res["day_name"] = day_name
        return res

    # 7. Operation: export_schedule
    def handle_export_schedule(args: Dict[str, Any], **context) -> Dict[str, Any]:
        member_id = args.get("member_id") or context.get("member_id")
        member = _resolve_member(member_id)
        ics_text = comp.export_schedule_to_ics(member)
        return {
            "member_id": member.id,
            "member_name": member.name,
            "institution": member.institution,
            "ics_content": ics_text,
            "filename": f"schedule_{member.id}.ics",
        }

    # 8. Operation: import_schedule
    def handle_import_schedule(args: Dict[str, Any], **context) -> Dict[str, Any]:
        ics_content = args.get("ics_content", "")
        member_id = args.get("member_id", "imported_student")
        member_name = args.get("member_name", "Sinh viên mới")
        if not ics_content.strip():
            raise ValueError("Nội dung .ics rỗng; vui lòng cung cấp dữ liệu iCalendar hợp lệ.")
        new_member = comp.import_schedule_from_ics(ics_content, member_id, member_name)
        comp.members.append(new_member)
        total_courses = sum(len(v) for v in new_member.schedule.values())
        return {
            "success": True,
            "member_id": new_member.id,
            "member_name": new_member.name,
            "courses_imported": total_courses,
            "days_scheduled": list(new_member.schedule.keys()),
        }

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

    # Register all 8 Reasoning Operations
    capability.register_operation(OperationDefinition(
        name="get_schedule",
        description=(
            "Tra cứu lịch học của sinh viên theo ngày (today, tomorrow, T2..CN, Monday..Sunday, YYYY-MM-DD). "
            "Hỗ trợ cả hệ thống tín chỉ Việt Nam (TDTU ca/tiết) và Đại học Quốc tế/Mỹ (clock time blocks & campus halls)."
        ),
        parameters={
            "type": "object",
            "properties": {
                "target_date": {
                    "type": "string",
                    "description": "Ngày cần tra: 'today', 'tomorrow', 'next', 'Monday', 'T2'..'CN', 'YYYY-MM-DD'.",
                    "default": "today",
                },
                "member_id": {
                    "type": "string",
                    "description": "Mã sinh viên hoặc tên (ví dụ: 'm1' cho Huỳnh Nhật Huy, 'us_alex' cho Alex Miller). Mặc định là sinh viên đang kích hoạt.",
                },
                "mode": {
                    "type": "string",
                    "description": "Lọc chế độ hiển thị: 'all', 'period' (ca/tiết), 'clock' (giờ chuẩn).",
                    "default": "all",
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
        description="Tra cứu vị trí phòng học, giảng đường, tòa nhà trên bản đồ trường (TDTU & US Halls).",
        parameters={
            "type": "object",
            "properties": {
                "room": {"type": "string", "description": "Mã phòng (ví dụ: 'A608', 'C302', 'Wheeler 150', 'Soda 310')."},
                "building": {"type": "string", "description": "Tên tòa nhà (tùy chọn, ví dụ: 'Wheeler Hall', 'Soda Hall')."},
            },
            "required": ["room"],
        },
        handler=handle_locate_room,
    ))

    capability.register_operation(OperationDefinition(
        name="get_group_availability",
        description="Tìm khung giờ vàng (Golden Windows) mà các thành viên trong nhóm cùng rảnh trong tuần.",
        parameters={
            "type": "object",
            "properties": {
                "min_ratio": {
                    "type": "number",
                    "description": "Tỷ lệ rảnh tối thiểu (0.8 = 80%, 1.0 = 100% cả nhóm cùng rảnh).",
                    "default": 0.8,
                },
            },
        },
        handler=handle_group_availability,
    ))

    capability.register_operation(OperationDefinition(
        name="find_free_slots",
        description="Tìm các khoảng thời gian trống liên tục trong ngày để tự học, ôn bài hoặc họp nhóm.",
        parameters={
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "description": "Ngày cần tìm: 'today', 'tomorrow', 'T2'..'CN', 'Monday'..'Sunday'.",
                    "default": "today",
                },
                "min_minutes": {
                    "type": "integer",
                    "description": "Thời lượng trống tối thiểu cần tìm (phút), mặc định 60 phút.",
                    "default": 60,
                },
                "day_start_time": {
                    "type": "string",
                    "description": "Giờ bắt đầu khung ngày (HH:MM), mặc định '08:00'.",
                    "default": "08:00",
                },
                "day_end_time": {
                    "type": "string",
                    "description": "Giờ kết thúc khung ngày (HH:MM), mặc định '21:00'.",
                    "default": "21:00",
                },
                "member_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần tìm. Để trống nếu tìm khoảng trống chung cho cả nhóm.",
                },
            },
        },
        handler=handle_find_free_slots,
    ))

    capability.register_operation(OperationDefinition(
        name="detect_conflicts",
        description="Phân tích và cảnh báo xung đột lịch học: trùng giờ, sát ca gấp (<15p), và di chuyển giữa các tòa nhà khác nhau.",
        parameters={
            "type": "object",
            "properties": {
                "member_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần kiểm tra xung đột.",
                },
            },
        },
        handler=handle_detect_conflicts,
    ))

    capability.register_operation(OperationDefinition(
        name="auto_arrange_schedule",
        description="Tự động sắp xếp một buổi học thêm, ôn thi hoặc họp nhóm vào khung giờ trống tối ưu.",
        parameters={
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Tên buổi hẹn / học nhóm (ví dụ: 'Ôn tập Giải tích 2', 'Họp Lab AI').",
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "Thời lượng dự kiến (phút), ví dụ: 60, 90, 120.",
                    "default": 60,
                },
                "target_day": {
                    "type": "string",
                    "description": "Ngày mong muốn: 'today', 'tomorrow', 'T2'..'CN', 'Monday'..'Sunday'.",
                    "default": "today",
                },
                "preferred_window": {
                    "type": "string",
                    "description": "Buổi ưu tiên: 'morning' (sáng), 'afternoon' (chiều), 'evening' (tối), hoặc 'any' (bất kỳ).",
                    "default": "afternoon",
                },
                "member_id": {
                    "type": "string",
                    "description": "Mã sinh viên cần sắp xếp. Để trống nếu sắp xếp cho cả nhóm.",
                },
            },
            "required": ["title", "duration_minutes"],
        },
        handler=handle_auto_arrange_schedule,
    ))

    capability.register_operation(OperationDefinition(
        name="export_schedule",
        description="Xuất thời khóa biểu sinh viên ra định dạng tiêu chuẩn iCalendar (.ics) đồng bộ với Google Calendar / Apple Calendar.",
        parameters={
            "type": "object",
            "properties": {
                "member_id": {"type": "string", "description": "Mã sinh viên cần xuất lịch."},
            },
        },
        handler=handle_export_schedule,
    ))

    capability.register_operation(OperationDefinition(
        name="import_schedule",
        description="Nhập thời khóa biểu từ tệp iCalendar (.ics) từ Canvas, Blackboard hoặc Google Calendar.",
        parameters={
            "type": "object",
            "properties": {
                "ics_content": {"type": "string", "description": "Chuỗi văn bản định dạng iCalendar .ics."},
                "member_id": {"type": "string", "description": "Mã định danh sinh viên cần gán."},
                "member_name": {"type": "string", "description": "Tên sinh viên."},
            },
            "required": ["ics_content", "member_id", "member_name"],
        },
        handler=handle_import_schedule,
    ))

    return capability
