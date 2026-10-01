"""
rat.timetable.model — Data models for University & Club Timetable Composition.
Specifically mapped to Ton Duc Thang University (TDTU) 15-period 5-shift academic system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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


@dataclass
class ClassSession:
    """A single scheduled class block in a member's timetable."""
    start_period: int
    end_period: int
    course_name: str
    room: str = ""
    degree_level: str = "undergrad"  # "undergrad" (Đại học) | "master" (Thạc sĩ/Cao học)
    course_code: str = ""
    lecturer: str = ""
    notes: str = ""

    @property
    def is_master(self) -> bool:
        return self.degree_level.lower() in ("master", "ths", "caohoc", "postgrad")

    @property
    def badge_text(self) -> str:
        return "🏛️ ThS" if self.is_master else "🎓 ĐH"

    @property
    def time_range_str(self) -> str:
        start_t = TDTU_PERIODS.get(self.start_period, ("??", "??", "", ""))[0]
        end_t = TDTU_PERIODS.get(self.end_period, ("??", "??", "", ""))[1]
        return f"{start_t} - {end_t}"

    def overlaps_period(self, period_id: int) -> bool:
        return self.start_period <= period_id <= self.end_period

    def overlaps_range(self, start: int, end: int) -> bool:
        return not (self.end_period < start or self.start_period > end)

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
        }

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
            notes=t[7] if len(t) > 7 else ""
        )


@dataclass
class ScheduleConflict:
    """Represents a conflict or tight transition between two class sessions."""
    day_code: str
    day_name: str
    session_a: ClassSession
    session_b: ClassSession
    conflict_type: str  # "overlap" (trùng tiết) | "tight_turnaround" (sát ca < 15 phút)
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
    """Full weekly timetable profile for one club member."""
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


def resolve_room_location(room: str) -> str:
    """
    Parses TDTU room identifier and returns campus building, floor, and facility notes.
    """
    if not room:
        return "Chưa xác định phòng"
    r = room.strip().upper()

    if "HOCTRUCTUYEN" in r or "ONLINE" in r:
        return "🌐 Học Trực Tuyến (LMS / MS Teams / Google Meet)"
    if "NTD" in r:
        return "🏟️ Nhà Thi Đấu Thể Thao Đa Năng TDTU (Tầng trệt)"
    if r.startswith("P15"):
        return f"🏢 Tòa P (Khu Ngoại Ngữ & Sáng Tạo) — Phòng {room}"

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


