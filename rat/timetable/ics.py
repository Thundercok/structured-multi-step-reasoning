"""
rat.timetable.ics — RFC 5545 iCalendar Exporter and Parser.
Enables two-way synchronization with Apple Calendar, Google Calendar, Outlook, and Canvas.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
import re
from typing import Any, Dict, List, Optional
import uuid

from rat.timetable.model import ClassSession, normalize_day_code


def export_to_ics(
    sessions: List[ClassSession],
    calendar_name: str = "RAT University Schedule",
    timezone: str = "Asia/Ho_Chi_Minh",
    base_monday: Optional[datetime] = None,
) -> str:
    """Generate an RFC 5545 compliant iCalendar string for a list of class sessions."""
    # Find next or current Monday as base date
    if base_monday is None:
        today = datetime.now()
        # Days ahead to Monday (0 = Monday)
        diff = (today.weekday() - 0) % 7
        base_monday = today - timedelta(days=diff)

    day_offsets = {
        "T2": 0, "MO": 0,
        "T3": 1, "TU": 1,
        "T4": 2, "WE": 2,
        "T5": 3, "TH": 3,
        "T6": 4, "FR": 4,
        "T7": 5, "SA": 5,
        "CN": 6, "SU": 6,
    }

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//RAT Assistant//Universal Timetable Compositor//VI",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{calendar_name}",
        f"X-WR-TIMEZONE:{timezone}",
    ]

    for s in sessions:
        offset = day_offsets.get(s.day, 0)
        sess_date = base_monday + timedelta(days=offset)
        s_parts = (s.start_time or "08:00").split(":")
        e_parts = (s.end_time or "09:30").split(":")

        sh, sm = int(s_parts[0]), int(s_parts[1])
        eh, em = int(e_parts[0]), int(e_parts[1])

        dt_start = sess_date.replace(hour=sh, minute=sm, second=0)
        dt_end = sess_date.replace(hour=eh, minute=em, second=0)

        dt_stamp = datetime.now(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        start_str = dt_start.strftime("%Y%m%dT%H%M%S")
        end_str = dt_end.strftime("%Y%m%dT%H%M%S")
        uid = f"rat-sess-{uuid.uuid4().hex[:12]}@rat.local"

        byday_map = {
            "T2": "MO", "MO": "MO",
            "T3": "TU", "TU": "TU",
            "T4": "WE", "WE": "WE",
            "T5": "TH", "TH": "TH",
            "T6": "FR", "FR": "FR",
            "T7": "SA", "SA": "SA",
            "CN": "SU", "SU": "SU",
        }
        byday = byday_map.get(s.day, "MO")

        summary = f"[{s.badge_text}] {s.course_name}" if s.course_name else "Lớp học"
        if s.building and s.room and s.building != s.room:
            location = f"{s.building} ({s.room})"
        else:
            location = s.building or s.room or "TBD"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dt_stamp}",
            f"DTSTART;TZID={timezone}:{start_str}",
            f"DTEND;TZID={timezone}:{end_str}",
            f"RRULE:FREQ=WEEKLY;BYDAY={byday};COUNT=16",
            f"SUMMARY:{summary}",
            f"LOCATION:{location}",
            f"DESCRIPTION:Giảng viên: {s.instructor or 'Chưa rõ'}\\nPhòng: {location}\\nThời gian: {s.time_range_str}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)


def import_from_ics(ics_content: str) -> List[ClassSession]:
    """Parse standard iCalendar (RFC 5545) VEVENT entries into ClassSession objects."""
    sessions: List[ClassSession] = []
    events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_content, re.DOTALL)

    for ev in events:
        summary_m = re.search(r"SUMMARY:(.*?)(?:\r?\n)", ev)
        dtstart_m = re.search(r"DTSTART(?:;TZID=[^:]+)?:(\d{8}T\d{4,6})", ev)
        dtend_m = re.search(r"DTEND(?:;TZID=[^:]+)?:(\d{8}T\d{4,6})", ev)
        loc_m = re.search(r"LOCATION:(.*?)(?:\r?\n)", ev)
        rrule_m = re.search(r"RRULE:(.*?)(?:\r?\n)", ev)
        desc_m = re.search(r"DESCRIPTION:(.*?)(?:\r?\n)", ev)

        summary = summary_m.group(1).strip() if summary_m else "Class"
        location = loc_m.group(1).strip() if loc_m else ""

        # Remove prefix tags like [🎓 ĐH] or [CS101] from course name
        clean_name = re.sub(r"^\[.*?\]\s*", "", summary).strip() or summary

        start_time_str = "08:00"
        end_time_str = "09:30"
        day_code = "T2"

        if dtstart_m:
            raw_start = dtstart_m.group(1)
            try:
                dt_obj = datetime.strptime(raw_start[:13], "%Y%m%dT%H%M")
                start_time_str = dt_obj.strftime("%H:%M")
                weekday_idx = dt_obj.weekday()  # 0=Monday
                vn_days = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
                day_code = vn_days[weekday_idx]
            except Exception:
                pass

        if dtend_m:
            raw_end = dtend_m.group(1)
            try:
                dt_obj = datetime.strptime(raw_end[:13], "%Y%m%dT%H%M")
                end_time_str = dt_obj.strftime("%H:%M")
            except Exception:
                pass

        # Check RRULE for BYDAY overrides
        if rrule_m:
            byday_m = re.search(r"BYDAY=([A-Z,]+)", rrule_m.group(1))
            if byday_m:
                first_day = byday_m.group(1).split(",")[0].strip()
                day_code = normalize_day_code(first_day)

        instructor = ""
        if desc_m:
            inst_m = re.search(r"Giảng viên:\s*([^\\]+)", desc_m.group(1))
            if inst_m:
                instructor = inst_m.group(1).strip()

        session = ClassSession(
            course_name=clean_name,
            room=location,
            lecturer=instructor,
            start_time=start_time_str,
            end_time=end_time_str,
            day=day_code,
            mode="clock",
        )
        sessions.append(session)

    return sessions
