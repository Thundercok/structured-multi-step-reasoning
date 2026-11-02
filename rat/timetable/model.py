"""
rat.timetable.model — Universal Multi-Mode Data Models for Timetable & Schedule Composition.

Supports:
1. Period / Shift Mode (Ton Duc Thang University 15-period 5-shift & Asian modular systems)
2. Clock / Time-Block Mode (US Universities & International standard start-end clock times)
3. Event / Agenda Mode (Deadlines, office hours, review sessions, study blocks)
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

# Standard TDTU 15 Academic Periods
TDTU_PERIODS: Dict[int, Tuple[str, str, str, str]] = {
    1:  ("06:50", "07:40", "Sáng", "Ca 1"),
    2:  ("07:40", "08:30", "Sáng", "Ca 1"),
    3:  ("08:30", "09:20", "Sáng", "Ca 1"),
    4:  ("09:30", "10:20", "Sáng", "Ca 2"),
    5:  ("10:20", "11:10", "Sáng", "Ca 2"),
    6:  ("11:10", "12:00", "Sáng", "Ca 2"),
    7:  ("12:45", "13:35", "Chiều", "Ca 3"),
    8:  ("13:35", "14:25", "Chiều", "Ca 3"),
    9:  ("14:25", "15:15", "Chiều", "Ca 3"),
    10: ("15:25", "16:15", "Chiều", "Ca 4"),
    11: ("16:15", "17:05", "Chiều", "Ca 4"),
    12: ("17:05", "17:55", "Chiều", "Ca 4"),
    13: ("18:05", "18:55", "Tối", "Ca 5"),
    14: ("18:55", "19:45", "Tối", "Ca 5"),
    15: ("19:45", "20:35", "Tối", "Ca 5"),
}

# The 5 primary shifts (Ca học) aggregating periods for a clean, non-overwhelming timetable UI
SHIFTS: List[Tuple[str, str, str, Tuple[int, int]]] = [
    ("ca1", "Ca 1 (Sáng)", "06:50 - 09:20", (1, 3)),
    ("ca2", "Ca 2 (Sáng)", "09:30 - 12:00", (4, 6)),
    ("ca3", "Ca 3 (Chiều)", "12:45 - 15:15", (7, 9)),
    ("ca4", "Ca 4 (Chiều)", "15:25 - 17:55", (10, 12)),
    ("ca5", "Ca 5 (Tối)", "18:05 - 20:35", (13, 15)),
]

DAYS: List[Tuple[str, str, str]] = [
    ("T2", "Thứ 2", "2026-09-07"),
    ("T3", "Thứ 3", "2026-09-08"),
    ("T4", "Thứ 4", "2026-09-09"),
    ("T5", "Thứ 5", "2026-09-10"),
    ("T6", "Thứ 6", "2026-09-11"),
    ("T7", "Thứ 7", "2026-09-12"),
    ("CN", "Chủ Nhật", "2026-09-13"),
]

# Day mappings for universal multi-lingual / US format support
DAY_ALIASES: Dict[str, str] = {
    "T2": "T2", "2": "T2", "THU 2": "T2", "THỨ 2": "T2", "MO": "T2", "MON": "T2", "MONDAY": "T2",
    "T3": "T3", "3": "T3", "THU 3": "T3", "THỨ 3": "T3", "TU": "T3", "TUE": "T3", "TUESDAY": "T3",
    "T4": "T4", "4": "T4", "THU 4": "T4", "THỨ 4": "T4", "WE": "T4", "WED": "T4", "WEDNESDAY": "T4",
    "T5": "T5", "5": "T5", "THU 5": "T5", "THỨ 5": "T5", "TH": "T5", "THU": "T5", "THURSDAY": "T5",
    "T6": "T6", "6": "T6", "THU 6": "T6", "THỨ 6": "T6", "FR": "T6", "FRI": "T6", "FRIDAY": "T6",
    "T7": "T7", "7": "T7", "THU 7": "T7", "THỨ 7": "T7", "SA": "T7", "SAT": "T7", "SATURDAY": "T7",
    "CN": "CN", "8": "CN", "CHU NHAT": "CN", "CHỦ NHẬT": "CN", "SU": "CN", "SUN": "CN", "SUNDAY": "CN",
}

DAY_TO_VN: Dict[str, str] = {
    "T2": "Thứ 2", "T3": "Thứ 3", "T4": "Thứ 4", "T5": "Thứ 5",
    "T6": "Thứ 6", "T7": "Thứ 7", "CN": "Chủ Nhật",
}

DAY_TO_EN: Dict[str, str] = {
    "T2": "Monday", "T3": "Tuesday", "T4": "Wednesday", "T5": "Thursday",
    "T6": "Friday", "T7": "Saturday", "CN": "Sunday",
}

DAY_TO_ICAL: Dict[str, str] = {
    "T2": "MO", "T3": "TU", "T4": "WE", "T5": "TH", "T6": "FR", "T7": "SA", "CN": "SU",
}


def normalize_day_code(day_str: str) -> str:
    """Normalize day string (e.g. 'Monday', 'mo', 'Thứ 2', 'T2') to canonical 'T2'..'CN'."""
    clean = re.sub(r"[^A-Za-z0-9À-ỹ]", " ", day_str).strip().upper()
    return DAY_ALIASES.get(clean, DAY_ALIASES.get(day_str.strip().upper(), "T2"))


def time_to_minutes(time_str: str) -> int:
    """Convert time string ('HH:MM' or 'H:MM AM/PM') to minutes since midnight."""
    if not time_str:
        return 0
    t = time_str.strip().upper()
    is_pm = "PM" in t
    is_am = "AM" in t
    t = re.sub(r"[^\d:]", "", t)
    parts = t.split(":")
    if len(parts) == 1:
        h, m = int(parts[0]), 0
    else:
        h, m = int(parts[0]), int(parts[1])
    if is_pm and h < 12:
        h += 12
    if is_am and h == 12:
        h = 0
    return h * 60 + m


def minutes_to_time(minutes: int) -> str:
    """Convert minutes since midnight to 'HH:MM' format."""
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def period_to_time(period: int) -> Tuple[str, str]:
    """Get (start_time, end_time) for a given academic period."""
    if period in TDTU_PERIODS:
        return TDTU_PERIODS[period][0], TDTU_PERIODS[period][1]
    return "08:00", "09:00"


@dataclass
class ClassSession:
    """
    A scheduled class or event block in a student's timetable.
    
    Supports:
    - Period-based layout (TDTU, Vietnam, East Asian 15-period shifts)
    - Direct Clock-based layout (US & International university time blocks: e.g. MWF 10:00 - 11:30 AM)
    """
    start_period: int = 0
    end_period: int = 0
    course_name: str = ""
    room: str = ""
    degree_level: str = "undergrad"  # "undergrad" | "master" | "grad"
    course_code: str = ""
    lecturer: str = ""
    notes: str = ""

    # Universal & Multi-mode fields
    day: str = ""                # Canonical day code: "T2".."CN"
    start_time: str = ""         # "08:00", "14:15", etc.
    end_time: str = ""           # "09:30", "15:45", etc.
    building: str = ""          # e.g., "Soda Hall", "Cory Hall", "Tòa C"
    credits: float = 0.0         # Course credit units (e.g., 4.0)
    mode: str = "period"         # "period" | "clock" | "event"

    def __post_init__(self) -> None:
        # Auto-fill times from periods if provided
        if self.start_period > 0 and self.end_period > 0:
            if not self.start_time and self.start_period in TDTU_PERIODS:
                self.start_time = TDTU_PERIODS[self.start_period][0]
            if not self.end_time and self.end_period in TDTU_PERIODS:
                self.end_time = TDTU_PERIODS[self.end_period][1]
        elif self.start_time and self.end_time:
            self.mode = "clock"

    @property
    def is_master(self) -> bool:
        return self.degree_level.lower() in ("master", "ths", "caohoc", "postgrad", "grad")

    @property
    def instructor(self) -> str:
        return self.lecturer

    @instructor.setter
    def instructor(self, val: str) -> None:
        self.lecturer = val

    @property
    def badge_text(self) -> str:
        if self.is_master:
            return "🏛️ ThS"
        if self.mode == "clock":
            return "🎓 US"
        return "🎓 ĐH"

    @property
    def time_range_str(self) -> str:
        if self.start_period > 0 and self.end_period > 0:
            start_t = TDTU_PERIODS.get(self.start_period, ("??", "??", "", ""))[0]
            end_t = TDTU_PERIODS.get(self.end_period, ("??", "??", "", ""))[1]
            return f"{start_t} - {end_t}"
        if self.start_time and self.end_time:
            return f"{self.start_time} - {self.end_time}"
        return "TBD"

    @property
    def start_minutes(self) -> int:
        if self.start_time:
            return time_to_minutes(self.start_time)
        if self.start_period in TDTU_PERIODS:
            return time_to_minutes(TDTU_PERIODS[self.start_period][0])
        return 0

    @property
    def end_minutes(self) -> int:
        if self.end_time:
            return time_to_minutes(self.end_time)
        if self.end_period in TDTU_PERIODS:
            return time_to_minutes(TDTU_PERIODS[self.end_period][1])
        return 0

    @property
    def duration_minutes(self) -> int:
        return max(0, self.end_minutes - self.start_minutes)

    def overlaps_period(self, period_id: int) -> bool:
        if self.start_period > 0 and self.end_period > 0:
            return self.start_period <= period_id <= self.end_period
        # If in clock mode, compare against period's time range
        if period_id in TDTU_PERIODS:
            p_start = time_to_minutes(TDTU_PERIODS[period_id][0])
            p_end = time_to_minutes(TDTU_PERIODS[period_id][1])
            return self.overlaps_time(p_start, p_end)
        return False

    def overlaps_range(self, start: int, end: int) -> bool:
        if self.start_period > 0 and self.end_period > 0:
            return not (self.end_period < start or self.start_period > end)
        if start in TDTU_PERIODS and end in TDTU_PERIODS:
            r_start = time_to_minutes(TDTU_PERIODS[start][0])
            r_end = time_to_minutes(TDTU_PERIODS[end][1])
            return self.overlaps_time(r_start, r_end)
        return False

    def overlaps_time(self, other_start_min: int, other_end_min: int) -> bool:
        return not (self.end_minutes <= other_start_min or self.start_minutes >= other_end_min)

    def overlaps_session(self, other: ClassSession) -> bool:
        if self.start_period > 0 and other.start_period > 0:
            return self.overlaps_range(other.start_period, other.end_period)
        return self.overlaps_time(other.start_minutes, other.end_minutes)

    def to_dict(self) -> dict:
        return {
            "start": self.start_period,
            "end": self.end_period,
            "course": self.course_name,
            "room": self.room,
            "degree_level": self.degree_level,
            "course_code": self.course_code,
            "lecturer": self.lecturer,
            "notes": self.notes,
            "day": self.day,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "building": self.building,
            "credits": self.credits,
            "mode": self.mode,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ClassSession:
        return cls(
            start_period=d.get("start", d.get("start_period", 0)),
            end_period=d.get("end", d.get("end_period", 0)),
            course_name=d.get("course", d.get("course_name", "")),
            room=d.get("room", ""),
            degree_level=d.get("degree_level", "undergrad"),
            course_code=d.get("course_code", ""),
            lecturer=d.get("lecturer", ""),
            notes=d.get("notes", ""),
            day=d.get("day", ""),
            start_time=d.get("start_time", ""),
            end_time=d.get("end_time", ""),
            building=d.get("building", ""),
            credits=float(d.get("credits", 0.0)),
            mode=d.get("mode", "period" if d.get("start", 0) > 0 else "clock"),
        )

    @classmethod
    def from_tuple(cls, t: tuple) -> ClassSession:
        if len(t) == 3:
            return cls(start_period=t[0], end_period=t[1], course_name=t[2], room="")
        if len(t) == 4:
            return cls(start_period=t[0], end_period=t[1], course_name=t[2], room=t[3])
        if len(t) == 5:
            return cls(start_period=t[0], end_period=t[1], course_name=t[2], room=t[3], degree_level=t[4])
        return cls(
            start_period=t[0],
            end_period=t[1],
            course_name=t[2],
            room=t[3],
            degree_level=t[4],
            course_code=t[5] if len(t) > 5 else "",
            lecturer=t[6] if len(t) > 6 else "",
            notes=t[7] if len(t) > 7 else "",
        )


@dataclass
class ScheduleConflict:
    """Represents a conflict or tight transition between two class sessions."""
    day_code: str
    day_name: str
    session_a: ClassSession
    session_b: ClassSession
    conflict_type: str  # "overlap" (trùng tiết/giờ) | "tight_turnaround" (sát ca < 15 phút) | "campus_travel"
    message: str


@dataclass
class LiveClassStatus:
    """Current real-time status of a student's timetable."""
    current_time_str: str
    day_code: str
    day_name: str
    is_in_class: bool
    current_session: Optional[ClassSession] = None
    remaining_minutes: int = 0
    next_session: Optional[ClassSession] = None
    minutes_until_next: int = 0
    message: str = ""


@dataclass
class MemberSchedule:
    """Full weekly timetable profile for one student / member."""
    id: str
    name: str
    mssv: str = ""
    major: str = ""
    color_hex: str = "#3b82f6"
    schedule: Dict[str, List[ClassSession]] = field(default_factory=dict)
    active: bool = True
    is_dual_degree: bool = False
    master_major: str = ""
    master_mssv: str = ""
    institution: str = "TDTU"         # e.g., "TDTU", "UC Berkeley", "MIT", "Stanford"
    timezone: str = "Asia/Ho_Chi_Minh" # e.g., "America/Los_Angeles" for US West

    def is_busy_in_period(self, day_code: str, period_id: int) -> Optional[ClassSession]:
        sessions = self.schedule.get(day_code, [])
        for s in sessions:
            if s.overlaps_period(period_id):
                return s
        return None

    def is_busy_in_shift(self, day_code: str, start_period: int, end_period: int) -> List[ClassSession]:
        sessions = self.schedule.get(day_code, [])
        busy = []
        for s in sessions:
            if s.overlaps_range(start_period, end_period):
                busy.append(s)
        return busy

    def is_busy_at_time(self, day_code: str, time_str: str) -> Optional[ClassSession]:
        mins = time_to_minutes(time_str)
        for s in self.schedule.get(day_code, []):
            if s.start_minutes <= mins < s.end_minutes:
                return s
        return None

    def get_day_sessions(self, day_code: str) -> List[ClassSession]:
        norm = normalize_day_code(day_code)
        sessions = self.schedule.get(norm, [])
        # Return sorted by start time
        return sorted(sessions, key=lambda s: s.start_minutes)


@dataclass
class ShiftAvailability:
    """Availability analysis aggregated for a single shift in a day."""
    day_code: str
    day_name: str
    shift_id: str
    shift_name: str
    time_range: str
    start_period: int
    end_period: int
    total_active_members: int
    free_count: int
    busy_count: int
    ratio: float  # 0.0 to 1.0
    free_members: List[str]
    busy_details: List[Dict[str, str]]  # list of {"member": ..., "course": ..., "room": ...}


@dataclass
class GoldenWindow:
    """A continuous golden period where 100% or >=80% members are free."""
    day_code: str
    day_name: str
    date: str
    start_period: int
    end_period: int
    time_range: str
    ratio: float
    free_count: int
    total_count: int
    free_members: List[str]
    busy_members: List[str]

    @property
    def span_periods(self) -> int:
        return self.end_period - self.start_period + 1


def resolve_room_location(room: str, building: str = "") -> str:
    """
    Parses room identifier and returns campus building, floor, and facility notes.
    Supports both Vietnamese (TDTU) and International / US campuses.
    """
    if not room and not building:
        return "Chưa xác định phòng"
    
    # If explicit building provided
    if building:
        r_part = f" — Room {room}" if room else ""
        return f"📍 {building}{r_part}"

    r = room.strip().upper()

    if "HOCTRUCTUYEN" in r or "ONLINE" in r:
        return "🌐 Học Trực Tuyến (LMS / MS Teams / Zoom)"
    if "NTD" in r:
        return "🏟️ Nhà Thi Đấu Thể Thao Đa Năng TDTU (Tầng trệt)"
    if r.startswith("P15"):
        return f"🏢 Tòa P (Khu Ngoại Ngữ & Sáng Tạo) — Phòng {room}"

    # US Campus room patterns: e.g. "Soda 310", "Hearst 101", "Dwinelle 142"
    us_match = re.match(r"^([A-Z][a-zA-Z\s]+?)\s*(\d+[A-Za-z]?)$", room.strip())
    if us_match and len(us_match.group(1)) > 2:
        b_name, rm = us_match.group(1), us_match.group(2)
        return f"🏛️ {b_name} Hall — Room {rm}"

    prefix = r[0]
    num_part = ""
    for ch in r[1:]:
        if ch.isdigit():
            num_part += ch
        else:
            break

    floor = num_part[0] if num_part else "1"
    extra = ""
    if prefix == "C" and ("302" in r or "305" in r or "301" in r):
        extra = " • Viện Sau Đại Học TDTU"
    elif prefix == "A" and ("6" in num_part or "7" in num_part):
        extra = " • Lab máy tính CNTT"

    b_names = {
        "A": "Tòa A (CNTT & Hành Chính)",
        "B": "Tòa B (Giảng Đường Lý Thuyết)",
        "C": "Tòa C (KHUD & Sau Đại Học)",
        "D": "Tòa D (Kiến Trúc & QTKD)",
        "F": "Tòa F (Giảng Đường Lớn)",
    }
    b_name = b_names.get(prefix, f"Tòa {prefix}")
    return f"{b_name} — Tầng {floor} ({room}){extra}"
