"""
rat.timetable.compositor — Calculation Engine for Multi-Member Timetable Merging.
Calculates availability matrices, extracts Golden Windows, detects conflicts,
and exports to iCalendar / Chat format.

Supports both:
- Period / Shift Mode (Vietnam & East Asian academic systems)
- Clock / Time-Block Mode (US Universities & continuous time intervals)
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional, Tuple

from rat.timetable.model import (
    DAYS,
    SHIFTS,
    TDTU_PERIODS,
    ClassSession,
    GoldenWindow,
    LiveClassStatus,
    MemberSchedule,
    ScheduleConflict,
    ShiftAvailability,
    minutes_to_time,
    normalize_day_code,
    time_to_minutes,
)
from rat.timetable.ics import export_to_ics, import_from_ics


def availability_to_color(ratio: float) -> Dict[str, str]:
    """
    Soft, readable palette for schedule availability cards.
    """
    if ratio >= 0.99:
        # 100% free — soft sage
        return {
            "bg": "#dcfce7",
            "bg_hover": "#bbf7d0",
            "border": "#86efac",
            "text": "#166534",
            "badge": "100%",
            "desc": "Cả nhóm đều rảnh",
        }
    elif ratio >= 0.79:
        # 80% free — warm butter
        return {
            "bg": "#fef3c7",
            "bg_hover": "#fde68a",
            "border": "#fde047",
            "text": "#854d0e",
            "badge": "Đa số",
            "desc": "Hầu hết đều rảnh",
        }
    elif ratio >= 0.49:
        # Half the group free — soft lilac
        return {
            "bg": "#ede9fe",
            "bg_hover": "#ddd6fe",
            "border": "#c4b5fd",
            "text": "#5b21b6",
            "badge": "Một nửa",
            "desc": "Khoảng nửa nhóm rảnh",
        }
    else:
        # Less than half free — quiet stone
        return {
            "bg": "#f8fafc",
            "bg_hover": "#f1f5f9",
            "border": "#e2e8f0",
            "text": "#64748b",
            "badge": "Kẹt lịch",
            "desc": "Đa số bận học",
        }


def degree_to_style(degree_level: str) -> Dict[str, str]:
    """
    Gentle color distinction for undergraduate and master classes.
    """
    if degree_level.lower() in ("master", "ths", "caohoc", "postgrad", "grad"):
        return {
            "bg": "#f1ebf8",
            "bg_hover": "#e7def2",
            "border": "#d8c8e9",
            "text": "#5e4d76",
            "tag_bg": "#8d6eac",
            "tag_fg": "#ffffff",
            "badge": "ThS",
            "level_name": "Thạc sĩ",
        }
    else:
        return {
            "bg": "#eaf1f8",
            "bg_hover": "#dfeaf4",
            "border": "#c8d9e8",
            "text": "#405c75",
            "tag_bg": "#5e829f",
            "tag_fg": "#ffffff",
            "badge": "ĐH",
            "level_name": "Đại học",
        }


class TimetableCompositor:
    """Engine merging member schedules and computing availability."""

    def __init__(self, members: Optional[List[MemberSchedule]] = None) -> None:
        self.members: List[MemberSchedule] = members or []

    @property
    def active_members(self) -> List[MemberSchedule]:
        return [m for m in self.members if m.active]

    def set_member_active(self, member_id: str, active: bool) -> None:
        for m in self.members:
            if m.id == member_id:
                m.active = active
                break

    def toggle_member(self, member_id: str) -> bool:
        for m in self.members:
            if m.id == member_id:
                m.active = not m.active
                return m.active
        return False

    def compute_shift_matrix(self) -> Dict[str, Dict[str, ShiftAvailability]]:
        """
        Computes availability for each of the 5 Shifts across 7 Days.
        Returns: { day_code: { shift_id: ShiftAvailability } }
        """
        active = self.active_members
        total_active = len(active)
        matrix: Dict[str, Dict[str, ShiftAvailability]] = {}

        for day_code, day_name, _ in DAYS:
            matrix[day_code] = {}
            for shift_id, shift_name, time_range, (start_p, end_p) in SHIFTS:
                free_members: List[str] = []
                busy_details: List[Dict[str, str]] = []

                if total_active == 0:
                    ratio = 0.0
                else:
                    for m in active:
                        busy_sessions = m.is_busy_in_shift(day_code, start_p, end_p)
                        if busy_sessions:
                            for s in busy_sessions:
                                p_str = f"Tiết {s.start_period}-{s.end_period}" if s.start_period > 0 else s.time_range_str
                                busy_details.append({
                                    "member": m.name,
                                    "member_id": m.id,
                                    "color": m.color_hex,
                                    "course": s.course_name,
                                    "room": s.room or "Chưa rõ phòng",
                                    "periods": p_str,
                                })
                        else:
                            free_members.append(m.name)

                    ratio = len(free_members) / total_active

                matrix[day_code][shift_id] = ShiftAvailability(
                    day_code=day_code,
                    day_name=day_name,
                    shift_id=shift_id,
                    shift_name=shift_name,
                    time_range=time_range,
                    start_period=start_p,
                    end_period=end_p,
                    total_active_members=total_active,
                    free_count=len(free_members),
                    busy_count=len(busy_details),
                    ratio=ratio,
                    free_members=free_members,
                    busy_details=busy_details,
                )

        return matrix

    def compute_period_matrix(self) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """
        Computes detailed availability for each of the 15 individual periods across 7 days.
        """
        active = self.active_members
        total_active = len(active)
        matrix: Dict[str, Dict[int, Dict[str, Any]]] = {}

        for day_code, day_name, date_str in DAYS:
            matrix[day_code] = {}
            for p_id, (t_start, t_end, shift, ca) in TDTU_PERIODS.items():
                busy_list = []
                free_list = []

                for m in active:
                    session = m.is_busy_in_period(day_code, p_id)
                    if session:
                        busy_list.append({
                            "member": m.name,
                            "member_id": m.id,
                            "course": session.course_name,
                            "room": session.room,
                        })
                    else:
                        free_list.append(m.name)

                ratio = (len(free_list) / total_active) if total_active > 0 else 0.0
                matrix[day_code][p_id] = {
                    "time": f"{t_start} - {t_end}",
                    "shift": shift,
                    "ca": ca,
                    "free_count": len(free_list),
                    "busy_count": len(busy_list),
                    "ratio": ratio,
                    "free_members": free_list,
                    "busy_details": busy_list,
                }

        return matrix

    def find_golden_windows(self, min_ratio: float = 0.8) -> List[GoldenWindow]:
        """
        Scans for continuous free periods matching or exceeding min_ratio (e.g. 1.0 or 0.8).
        """
        active = self.active_members
        total_active = len(active)
        if total_active == 0:
            return []

        period_matrix = self.compute_period_matrix()
        windows: List[GoldenWindow] = []

        for day_code, day_name, date_str in DAYS:
            day_data = period_matrix[day_code]
            current_window: Optional[Dict[str, Any]] = None

            for p_id in sorted(day_data.keys()):
                p_info = day_data[p_id]
                if p_info["ratio"] >= min_ratio:
                    if current_window is None:
                        current_window = {
                            "day_code": day_code,
                            "day_name": day_name,
                            "date": date_str,
                            "start_period": p_id,
                            "end_period": p_id,
                            "free_members_set": set(p_info["free_members"]),
                            "busy_members_set": {b["member"] for b in p_info["busy_details"]},
                            "min_ratio_seen": p_info["ratio"],
                            "min_free_seen": p_info["free_count"],
                        }
                    else:
                        current_window["end_period"] = p_id
                        current_window["free_members_set"] &= set(p_info["free_members"])
                        current_window["busy_members_set"] |= {b["member"] for b in p_info["busy_details"]}
                        current_window["min_ratio_seen"] = min(current_window["min_ratio_seen"], p_info["ratio"])
                        current_window["min_free_seen"] = min(current_window["min_free_seen"], p_info["free_count"])
                else:
                    if current_window:
                        windows.append(self._build_golden_window(current_window, total_active))
                        current_window = None

            if current_window:
                windows.append(self._build_golden_window(current_window, total_active))

        return windows

    def _build_golden_window(self, w_data: dict, total_active: int) -> GoldenWindow:
        start_p = w_data["start_period"]
        end_p = w_data["end_period"]
        t_start = TDTU_PERIODS[start_p][0]
        t_end = TDTU_PERIODS[end_p][1]
        time_range = f"{t_start} - {t_end}"

        free_m = sorted(list(w_data["free_members_set"]))
        busy_m = sorted(list(w_data["busy_members_set"]))

        return GoldenWindow(
            day_code=w_data["day_code"],
            day_name=w_data["day_name"],
            date=w_data["date"],
            start_period=start_p,
            end_period=end_p,
            time_range=time_range,
            ratio=w_data["min_ratio_seen"],
            free_count=w_data["min_free_seen"],
            total_count=total_active,
            free_members=free_m,
            busy_members=busy_m,
        )

    def generate_ics_content(self, min_ratio: float = 0.8) -> str:
        """
        Generates standard RFC 5545 iCalendar content for all golden windows.
        """
        windows = self.find_golden_windows(min_ratio=min_ratio)
        total_active = len(self.active_members)

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//rat Timetable Compositor//VN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            "X-WR-CALNAME:Lịch Trống Chung CLB",
            "X-WR-TIMEZONE:Asia/Ho_Chi_Minh",
        ]

        now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        for idx, w in enumerate(windows):
            start_time_str = TDTU_PERIODS[w.start_period][0]
            end_time_str = TDTU_PERIODS[w.end_period][1]

            dt_date = w.date.replace("-", "")
            dt_start = f"{dt_date}T{start_time_str.replace(':', '')}00"
            dt_end = f"{dt_date}T{end_time_str.replace(':', '')}00"

            badge = "100% RẢNH" if w.free_count == total_active else f"{w.free_count}/{total_active} Rảnh"
            title = f"[CLB FREE] {w.day_name}: Tiết {w.start_period}-{w.end_period} ({badge})"
            
            free_str = ", ".join(w.free_members) if w.free_members else "Không có"
            busy_str = f"\\nBận: {', '.join(w.busy_members)}" if w.busy_members else ""
            desc = f"Khung giờ rảnh sinh hoạt / họp CLB.\\nRảnh ({w.free_count}/{total_active}): {free_str}{busy_str}\\nThời gian: {start_time_str} - {end_time_str}"

            lines.extend([
                "BEGIN:VEVENT",
                f"UID:rat-club-{dt_start}-{idx}@rat.local",
                f"DTSTAMP:{now_utc}",
                f"DTSTART;TZID=Asia/Ho_Chi_Minh:{dt_start}",
                f"DTEND;TZID=Asia/Ho_Chi_Minh:{dt_end}",
                f"SUMMARY:{title}",
                f"DESCRIPTION:{desc}",
                "STATUS:CONFIRMED",
                "END:VEVENT",
            ])

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    def generate_chat_message(self) -> str:
        """
        Generates a beautifully formatted, aesthetic announcement message.
        """
        active = self.active_members
        total = len(active)
        if total == 0:
            return "⚠️ Chưa có thành viên nào được kích hoạt để tính lịch."

        windows_100 = self.find_golden_windows(min_ratio=1.0)
        windows_80 = [w for w in self.find_golden_windows(min_ratio=0.8) if w.free_count < total]

        names_str = ", ".join([m.name for m in active])

        lines = [
            "🍵 **LỊCH TRỐNG CHUNG CLB — KHUNG GIỜ VÀNG** 🍵",
            f"👥 **Thành viên tham gia ({total} bạn):** {names_str}",
            "━" * 28,
        ]

        if windows_100:
            lines.append("✨ **KHUNG GIỜ VÀNG (100% CẢ NHÓM ĐỀU RẢNH):**")
            for idx, w in enumerate(windows_100, 1):
                span = w.span_periods
                lines.append(f"  {idx}. 🌿 **{w.day_name}**: Tiết {w.start_period} ➔ {w.end_period} ({w.time_range}) • {span} tiết liền mạch")
        else:
            lines.append("🌿 *Không có khung giờ nào 100% rảnh trong tuần này.*")

        lines.append("")

        if windows_80:
            lines.append(f"☀️ **KHUNG GIỜ KHẢ DỤNG CAO (≥80% RẢNH, {total-1}/{total} BẠN):**")
            for idx, w in enumerate(windows_80, 1):
                busy_str = f" *(Kẹt: {', '.join(w.busy_members)})*" if w.busy_members else ""
                lines.append(f"  {idx}. ☀️ **{w.day_name}**: Tiết {w.start_period} ➔ {w.end_period} ({w.time_range}) • {w.free_count}/{total} bạn rảnh{busy_str}")

        lines.extend([
            "",
            "━" * 28,
            "💡 *Được tính toán và đồng bộ tự động từ rat Timetable Compositor.*",
        ])

        return "\n".join(lines)

    def compute_unified_individual_schedule(
        self,
        member: MemberSchedule,
        filter_level: str = "all",
        search_query: str = ""
    ) -> Dict[str, List[ClassSession]]:
        """
        Computes merged, sorted individual schedule for a member across the 7 days.
        filter_level: 'all' | 'undergrad' | 'master'
        search_query: case-insensitive query across course name, room, lecturer, code.
        """
        q = search_query.strip().lower()
        unified: Dict[str, List[ClassSession]] = {}

        for day_code, _, _ in DAYS:
            sessions = member.schedule.get(day_code, [])
            filtered: List[ClassSession] = []

            for s in sessions:
                # 1. Level filter
                if filter_level == "undergrad" and s.is_master:
                    continue
                elif filter_level == "master" and not s.is_master:
                    continue

                # 2. Text query filter
                if q:
                    haystack = f"{s.course_name} {s.room} {s.course_code} {s.lecturer} {s.notes} {s.building}".lower()
                    if q not in haystack:
                        continue

                filtered.append(s)

            # Sort ascending by start time / start period
            filtered.sort(key=lambda s: s.start_minutes)
            unified[day_code] = filtered

        return unified

    def detect_schedule_conflicts(self, member: MemberSchedule) -> List[ScheduleConflict]:
        """
        Identifies class session overlaps and tight turnaround warnings.
        Supports both period overlaps and clock-time overlaps.
        """
        conflicts: List[ScheduleConflict] = []
        weekday_dict = dict([(d[0], d[1]) for d in DAYS])

        for day_code, day_name in weekday_dict.items():
            sessions = sorted(member.schedule.get(day_code, []), key=lambda s: s.start_minutes)
            n = len(sessions)
            for i in range(n):
                for j in range(i + 1, n):
                    s1 = sessions[i]
                    s2 = sessions[j]

                    # Direct Overlap
                    is_overlap = False
                    if s1.start_period > 0 and s2.start_period > 0:
                        is_overlap = s1.overlaps_range(s2.start_period, s2.end_period)
                    else:
                        is_overlap = s1.overlaps_time(s2.start_minutes, s2.end_minutes)

                    if is_overlap:
                        p1_str = f"Tiết {s1.start_period}-{s1.end_period}" if s1.start_period > 0 else s1.time_range_str
                        p2_str = f"Tiết {s2.start_period}-{s2.end_period}" if s2.start_period > 0 else s2.time_range_str
                        conflicts.append(ScheduleConflict(
                            day_code=day_code,
                            day_name=day_name,
                            session_a=s1,
                            session_b=s2,
                            conflict_type="overlap",
                            message=f"Trùng lịch học {day_name}: [{s1.badge_text}] {s1.course_name} ({p1_str}) trùng với [{s2.badge_text}] {s2.course_name} ({p2_str})!"
                        ))
                    else:
                        # Turnaround check
                        gap = s2.start_minutes - s1.end_minutes
                        if 0 <= gap <= 15:
                            # If across distinct degree levels or distinct campus buildings
                            is_cross_level = (s1.degree_level != s2.degree_level)
                            is_diff_building = (s1.building and s2.building and s1.building != s2.building)
                            
                            c_type = "campus_travel" if is_diff_building else "tight_turnaround"
                            conflicts.append(ScheduleConflict(
                                day_code=day_code,
                                day_name=day_name,
                                session_a=s1,
                                session_b=s2,
                                conflict_type=c_type,
                                message=f"Chuyển ca gấp {day_name} ({gap} phút): [{s1.badge_text}] {s1.course_name} xong lúc {s1.end_time or minutes_to_time(s1.end_minutes)} ➔ [{s2.badge_text}] {s2.course_name} ({s2.room}) vào học lúc {s2.start_time or minutes_to_time(s2.start_minutes)}!"
                            ))

        return conflicts

    def compute_live_status(
        self,
        member: MemberSchedule,
        current_dt: Optional[datetime] = None
    ) -> LiveClassStatus:
        """
        Calculates real-time academic status: in-class countdown, upcoming class, or finished for the day.
        """
        if current_dt is None:
            current_dt = datetime.now()

        weekday_map = {
            0: ("T2", "Thứ 2"),
            1: ("T3", "Thứ 3"),
            2: ("T4", "Thứ 4"),
            3: ("T5", "Thứ 5"),
            4: ("T6", "Thứ 6"),
            5: ("T7", "Thứ 7"),
            6: ("CN", "Chủ Nhật"),
        }
        day_code, day_name = weekday_map[current_dt.weekday()]
        now_mins = current_dt.hour * 60 + current_dt.minute
        time_str = current_dt.strftime("%H:%M:%S")

        day_sessions = member.schedule.get(day_code, [])
        sorted_sessions = sorted(day_sessions, key=lambda s: s.start_minutes)

        # 1. Check if currently inside any class session
        for s in sorted_sessions:
            start_m = s.start_minutes
            end_m = s.end_minutes

            if start_m <= now_mins <= end_m:
                rem = end_m - now_mins
                msg = f"Đang diễn ra: [{s.badge_text}] {s.course_name} ({s.room or 'Chưa rõ phòng'}) — Còn {rem} phút"
                return LiveClassStatus(
                    current_time_str=time_str,
                    day_code=day_code,
                    day_name=day_name,
                    is_in_class=True,
                    current_session=s,
                    remaining_minutes=rem,
                    next_session=None,
                    minutes_until_next=0,
                    message=msg,
                )

        # 2. Check upcoming session today
        upcoming: List[Tuple[int, ClassSession]] = []
        for s in sorted_sessions:
            start_m = s.start_minutes
            if start_m > now_mins:
                upcoming.append((start_m - now_mins, s))

        if upcoming:
            upcoming.sort(key=lambda x: x[0])
            diff_m, next_s = upcoming[0]
            msg = f"Tiết tiếp theo: [{next_s.badge_text}] {next_s.course_name} ({next_s.time_range_str} tại {next_s.room or 'Chưa rõ phòng'}) — Bắt đầu sau {diff_m} phút"
            return LiveClassStatus(
                current_time_str=time_str,
                day_code=day_code,
                day_name=day_name,
                is_in_class=False,
                current_session=None,
                remaining_minutes=0,
                next_session=next_s,
                minutes_until_next=diff_m,
                message=msg,
            )

        # 3. No more sessions today
        if not sorted_sessions:
            msg = f"Hôm nay ({day_name}) bạn không có lịch học nào. Tận hưởng ngày nghỉ nhé! 🌿"
        else:
            msg = f"Hôm nay ({day_name}) đã kết thúc tất cả {len(sorted_sessions)} môn học! ✨"

        return LiveClassStatus(
            current_time_str=time_str,
            day_code=day_code,
            day_name=day_name,
            is_in_class=False,
            current_session=None,
            remaining_minutes=0,
            next_session=None,
            minutes_until_next=0,
            message=msg,
        )

    def generate_unified_ics(self, member: MemberSchedule, filter_level: str = "all") -> str:
        """
        Generates standard RFC 5545 iCalendar format for a member's unified schedule.
        """
        sched = self.compute_unified_individual_schedule(member, filter_level=filter_level)
        date_dict = dict([(d[0], d[2]) for d in DAYS])

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//rat Timetable Compositor Unified//VN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:TKB Hop Nhat - {member.name}",
            f"X-WR-TIMEZONE:{member.timezone or 'Asia/Ho_Chi_Minh'}",
        ]

        now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        event_idx = 0

        for day_code, sessions in sched.items():
            date_str = date_dict.get(day_code, "2026-09-07")
            dt_date = date_str.replace("-", "")

            for s in sessions:
                event_idx += 1
                t_start_str = s.start_time or (TDTU_PERIODS.get(s.start_period, ("07:00", ""))[0] if s.start_period > 0 else "08:00")
                t_end_str = s.end_time or (TDTU_PERIODS.get(s.end_period, ("", "08:00"))[1] if s.end_period > 0 else "09:00")

                dt_start = f"{dt_date}T{t_start_str.replace(':', '')}00"
                dt_end = f"{dt_date}T{t_end_str.replace(':', '')}00"

                title = f"[{s.badge_text}] {s.course_name}"
                if s.room:
                    title += f" - {s.room}"

                desc_parts = [
                    f"Mon hoc: {s.course_name}",
                    f"Bac dao tao: {'Thac si / Cao hoc' if s.is_master else 'Dai hoc'}",
                    f"Thoi gian: {s.time_range_str}",
                ]
                if s.course_code:
                    desc_parts.append(f"Ma mon: {s.course_code}")
                if s.lecturer:
                    desc_parts.append(f"Giang vien: {s.lecturer}")
                if s.room:
                    desc_parts.append(f"Phong hoc: {s.room}")
                if s.building:
                    desc_parts.append(f"Toa nha: {s.building}")
                if s.notes:
                    desc_parts.append(f"Ghi chu: {s.notes}")

                desc = "\\n".join(desc_parts)

                lines.extend([
                    "BEGIN:VEVENT",
                    f"UID:rat-tkb-{member.id}-{dt_start}-{event_idx}@rat.local",
                    f"DTSTAMP:{now_utc}",
                    f"DTSTART;TZID={member.timezone or 'Asia/Ho_Chi_Minh'}:{dt_start}",
                    f"DTEND;TZID={member.timezone or 'Asia/Ho_Chi_Minh'}:{dt_end}",
                    f"SUMMARY:{title}",
                    f"DESCRIPTION:{desc}",
                    f"LOCATION:{s.room or s.building or member.institution}",
                    "STATUS:CONFIRMED",
                    "END:VEVENT",
                ])

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines)

    def generate_unified_clipboard_text(self, member: MemberSchedule, filter_level: str = "all") -> str:
        """
        Formats a comprehensive markdown summary of the member's schedule for easy copying.
        """
        lines = [
            f"🎓 **THỜI KHÓA BIỂU HỢP NHẤT — {member.name.upper()}**",
            f"📌 Cơ sở đào tạo: {member.institution or 'TDTU'}",
            f"📌 Bậc đào tạo: {('Song bằng Đại học & Thạc sĩ' if member.is_dual_degree else 'Đại học')}",
            f"🆔 MSSV / ID: {member.mssv or 'N/A'} • Chuyên ngành: {member.major or 'N/A'}",
        ]
        if member.is_dual_degree:
            lines.append(f"🏛️ Học viên ThS: {member.master_mssv or 'N/A'} • Chuyên ngành: {member.master_major or 'N/A'}")
        lines.append("━" * 32)

        sched = self.compute_unified_individual_schedule(member, filter_level=filter_level)
        total_courses = 0
        total_undergrad = 0
        total_master = 0

        weekday_dict = dict([(d[0], d[1]) for d in DAYS])
        for day_code, day_name in weekday_dict.items():
            sessions = sched.get(day_code, [])
            if not sessions:
                continue
            lines.append(f"\n📅 **{day_name.upper()}** ({len(sessions)} môn):")
            for s in sessions:
                total_courses += 1
                if s.is_master:
                    total_master += 1
                else:
                    total_undergrad += 1
                lecturer_txt = f" • GV: {s.lecturer}" if s.lecturer else ""
                code_txt = f"[{s.course_code}] " if s.course_code else ""
                room_txt = f" (Phòng {s.room})" if s.room else ""
                p_info = f"Tiết {s.start_period}-{s.end_period} " if s.start_period > 0 else ""
                lines.append(f"  • {s.badge_text} **{code_txt}{s.course_name}**{room_txt}")
                lines.append(f"    🕒 {p_info}({s.time_range_str}){lecturer_txt}")

        lines.extend([
            "",
            "━" * 32,
            f"📊 **Tổng kết**: {total_courses} môn học ({total_undergrad} môn ĐH, {total_master} môn ThS)",
            "💡 *Được đồng bộ tự động từ rat Timetable Compositor.*"
        ])
        return "\n".join(lines)

    def compute_workload_stats(self, member: MemberSchedule) -> Dict[str, Any]:
        """
        Calculates weekly workload metrics: total periods/hours, undergrad vs master breakdown,
        shift distribution (morning, afternoon, evening), and stress level.
        """
        total_periods = 0
        ug_periods = 0
        ms_periods = 0
        morning_shifts = 0
        afternoon_shifts = 0
        evening_shifts = 0

        for day_code, _, _ in DAYS:
            sessions = member.schedule.get(day_code, [])
            for s in sessions:
                if s.start_period > 0 and s.end_period > 0:
                    periods = s.end_period - s.start_period + 1
                else:
                    # Clock mode: approximate 50 mins = 1 period
                    periods = max(1, round(s.duration_minutes / 50))
                
                total_periods += periods
                if s.is_master:
                    ms_periods += periods
                else:
                    ug_periods += periods

                start_min = s.start_minutes
                if start_min < 720:  # Before 12:00
                    morning_shifts += 1
                elif start_min < 1080:  # Before 18:00
                    afternoon_shifts += 1
                else:
                    evening_shifts += 1

        if total_periods <= 15:
            intensity = "chill"
            intensity_label = "🌿 Vừa phải (Chill)"
            intensity_color = "#16a34a"
        elif total_periods <= 28:
            intensity = "balanced"
            intensity_label = "⚖️ Cân bằng"
            intensity_color = "#2563eb"
        elif total_periods <= 36:
            intensity = "heavy"
            intensity_label = "⚡ Cường độ cao"
            intensity_color = "#d97706"
        else:
            intensity = "overload"
            intensity_label = "🚨 Quá tải / Căng thẳng"
            intensity_color = "#dc2626"

        return {
            "total_periods": total_periods,
            "undergrad_periods": ug_periods,
            "master_periods": ms_periods,
            "morning_classes": morning_shifts,
            "afternoon_classes": afternoon_shifts,
            "evening_classes": evening_shifts,
            "intensity": intensity,
            "intensity_label": intensity_label,
            "intensity_color": intensity_color,
            "ug_ratio": (ug_periods / total_periods) if total_periods > 0 else 0.0,
            "ms_ratio": (ms_periods / total_periods) if total_periods > 0 else 0.0,
        }

    def get_today_agenda(
        self,
        member: MemberSchedule,
        current_dt: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Returns structured timeline agenda for today, tracking status:
        'live' (in-progress), 'upcoming', or 'completed'.
        """
        if current_dt is None:
            current_dt = datetime.now()

        weekday_map = {
            0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"
        }
        day_code = weekday_map[current_dt.weekday()]
        now_mins = current_dt.hour * 60 + current_dt.minute

        sessions = sorted(member.schedule.get(day_code, []), key=lambda s: s.start_minutes)
        agenda = []

        for s in sessions:
            start_m = s.start_minutes
            end_m = s.end_minutes

            if now_mins > end_m:
                status = "completed"
                badge = "ĐÃ KẾT THÚC"
                countdown_txt = "Đã hoàn thành"
            elif start_m <= now_mins <= end_m:
                status = "live"
                badge = "ĐANG DIỄN RA"
                rem = end_m - now_mins
                countdown_txt = f"Còn {rem} phút nữa hết giờ"
            else:
                status = "upcoming"
                badge = "SẮP TỚI"
                diff = start_m - now_mins
                if diff >= 60:
                    countdown_txt = f"Bắt đầu sau {diff // 60}h{diff % 60:02d}p"
                else:
                    countdown_txt = f"Bắt đầu sau {diff} phút"

            agenda.append({
                "session": s,
                "status": status,
                "badge": badge,
                "countdown": countdown_txt,
                "start_time": s.start_time or minutes_to_time(start_m),
                "end_time": s.end_time or minutes_to_time(end_m),
            })

        return agenda

    # =========================================================================
    # UNIVERSAL MULTI-MODE / US & CONTINUOUS CLOCK TIMELINE CAPABILITIES
    # =========================================================================

    def find_free_slots_clock(
        self,
        day_code: str,
        min_minutes: int = 60,
        day_start_time: str = "08:00",
        day_end_time: str = "21:00",
        member_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Finds continuous free time blocks on a clock timeline (e.g. 08:00 to 21:00).
        If member_id is None, finds slots where ALL active members are free.
        """
        norm_day = normalize_day_code(day_code)
        active = [m for m in self.active_members if (member_id is None or m.id == member_id)]
        if not active:
            return []

        day_start_m = time_to_minutes(day_start_time)
        day_end_m = time_to_minutes(day_end_time)

        # Collect all busy intervals across target members
        busy_intervals: List[Tuple[int, int]] = []
        for m in active:
            for s in m.schedule.get(norm_day, []):
                s_start = max(day_start_m, s.start_minutes)
                s_end = min(day_end_m, s.end_minutes)
                if s_start < s_end:
                    busy_intervals.append((s_start, s_end))

        # Merge overlapping busy intervals
        busy_intervals.sort(key=lambda x: x[0])
        merged_busy: List[Tuple[int, int]] = []
        for start, end in busy_intervals:
            if not merged_busy or merged_busy[-1][1] < start:
                merged_busy.append((start, end))
            else:
                merged_busy[-1] = (merged_busy[-1][0], max(merged_busy[-1][1], end))

        # Find gaps between merged busy intervals
        free_slots: List[Dict[str, Any]] = []
        curr = day_start_m

        for b_start, b_end in merged_busy:
            gap = b_start - curr
            if gap >= min_minutes:
                free_slots.append({
                    "day_code": norm_day,
                    "start_time": minutes_to_time(curr),
                    "end_time": minutes_to_time(b_start),
                    "duration_minutes": gap,
                    "description": f"Trống {gap} phút ({minutes_to_time(curr)} - {minutes_to_time(b_start)})",
                })
            curr = max(curr, b_end)

        if (day_end_m - curr) >= min_minutes:
            gap = day_end_m - curr
            free_slots.append({
                "day_code": norm_day,
                "start_time": minutes_to_time(curr),
                "end_time": minutes_to_time(day_end_m),
                "duration_minutes": gap,
                "description": f"Trống {gap} phút ({minutes_to_time(curr)} - {minutes_to_time(day_end_m)})",
            })

        return free_slots

    def auto_arrange_event(
        self,
        title: str,
        duration_minutes: int,
        target_day: str = "T2",
        preferred_window: str = "afternoon",  # "morning" (08:00-12:00) | "afternoon" (13:00-18:00) | "evening" (18:00-21:00) | "any"
        member_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Auto-arranges a new study block, group meeting, or project session in an optimal free window.
        """
        window_bounds = {
            "morning": ("08:00", "12:00"),
            "afternoon": ("13:00", "18:00"),
            "evening": ("18:00", "21:30"),
            "any": ("08:00", "21:30"),
        }
        w_start, w_end = window_bounds.get(preferred_window, ("08:00", "21:30"))
        slots = self.find_free_slots_clock(
            day_code=target_day,
            min_minutes=duration_minutes,
            day_start_time=w_start,
            day_end_time=w_end,
            member_id=member_id
        )

        if not slots and preferred_window != "any":
            # Fallback to any window
            slots = self.find_free_slots_clock(
                day_code=target_day,
                min_minutes=duration_minutes,
                day_start_time="08:00",
                day_end_time="21:30",
                member_id=member_id
            )

        if not slots:
            return None

        # Pick the first suitable slot
        best = slots[0]
        start_min = time_to_minutes(best["start_time"])
        end_min = start_min + duration_minutes

        return {
            "title": title,
            "day": normalize_day_code(target_day),
            "start_time": minutes_to_time(start_min),
            "end_time": minutes_to_time(end_min),
            "duration_minutes": duration_minutes,
            "original_free_slot": best,
            "success": True,
            "recommendation": f"Sắp xếp thành công '{title}' vào {best['day_code']} ({minutes_to_time(start_min)} - {minutes_to_time(end_min)})",
        }

    def import_schedule_from_ics(self, ics_text: str, member_id: str, member_name: str) -> MemberSchedule:
        """Imports an iCalendar file (.ics) and returns a MemberSchedule."""
        sessions = import_from_ics(ics_text)
        sched: Dict[str, List[ClassSession]] = {}
        for s in sessions:
            if s.day not in sched:
                sched[s.day] = []
            sched[s.day].append(s)

        return MemberSchedule(
            id=member_id,
            name=member_name,
            schedule=sched,
            active=True
        )

    def export_schedule_to_ics(self, member: MemberSchedule) -> str:
        """Exports member schedule using the universal RFC 5545 exporter."""
        all_sessions = []
        for day, sessions in member.schedule.items():
            for s in sessions:
                if not s.day:
                    s.day = day
                all_sessions.append(s)
        return export_to_ics(
            sessions=all_sessions,
            calendar_name=f"Schedule - {member.name}",
            timezone=member.timezone or "Asia/Ho_Chi_Minh"
        )
