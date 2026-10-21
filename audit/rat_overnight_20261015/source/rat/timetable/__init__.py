"""
rat.timetable — University & Club Timetable Compositor.
Merges multi-member schedules, calculates availability matrices, and finds golden meeting windows.
"""

from rat.timetable.model import (
    TDTU_PERIODS,
    DAYS,
    SHIFTS,
    ClassSession,
    MemberSchedule,
    ShiftAvailability,
    GoldenWindow,
)
from rat.timetable.compositor import TimetableCompositor, availability_to_color
from rat.timetable.data import get_default_club_members, load_club_members, save_club_members

__all__ = [
    "TDTU_PERIODS",
    "DAYS",
    "SHIFTS",
    "ClassSession",
    "MemberSchedule",
    "ShiftAvailability",
    "GoldenWindow",
    "TimetableCompositor",
    "availability_to_color",
    "get_default_club_members",
    "load_club_members",
    "save_club_members",
]
