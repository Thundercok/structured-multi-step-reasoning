"""
tests/test_universal_timetable.py — Comprehensive Unit Tests for Universal Multi-Mode Timetable Engine.

Validates:
1. US College Student Profile (Clock mode, MWF/TuTh time blocks, campus buildings, credits).
2. Continuous Free Slot Search across arbitrary clock intervals.
3. Conflict Detection (Direct overlap and campus travel buffer warnings).
4. Auto-arranging Study / Review / Meeting Sessions into free windows.
5. RFC 5545 iCalendar (.ics) Two-Way Export & Import.
6. Interaction Kernel Agentic Reasoning Capability registration and execution.
"""

from datetime import datetime
import unittest

from rat.kernel.registry import CapabilityRegistry
from rat.kernel.capabilities.timetable import create_timetable_capability
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.data import (
    get_all_sample_members,
    get_default_club_members,
    get_sample_us_member,
)
from rat.timetable.ics import export_to_ics, import_from_ics
from rat.timetable.model import (
    DAYS,
    ClassSession,
    MemberSchedule,
    minutes_to_time,
    normalize_day_code,
    resolve_room_location,
    time_to_minutes,
)


class TestUniversalTimetableEngine(unittest.TestCase):
    def setUp(self):
        self.us_member = get_sample_us_member()
        self.tdtu_members = get_default_club_members()
        self.all_members = get_all_sample_members()
        self.compositor = TimetableCompositor(self.all_members)

    def test_us_member_profile_clock_mode(self):
        """Test UC Berkeley US student schedule loaded with clock mode sessions."""
        self.assertEqual(self.us_member.institution, "UC Berkeley")
        self.assertEqual(self.us_member.id, "us_alex")
        self.assertEqual(self.us_member.name, "Alex Miller")

        # Monday sessions
        t2_sessions = self.us_member.get_day_sessions("T2")
        self.assertEqual(len(t2_sessions), 2)
        s1 = t2_sessions[0]
        self.assertIn("CS 188", s1.course_name)
        self.assertEqual(s1.start_time, "10:00")
        self.assertEqual(s1.end_time, "11:30")
        self.assertEqual(s1.building, "Wheeler Hall")
        self.assertEqual(s1.credits, 4.0)
        self.assertEqual(s1.duration_minutes, 90)
        self.assertEqual(s1.badge_text, "🎓 US")

    def test_day_normalization(self):
        """Test multi-lingual and US day code parsing."""
        self.assertEqual(normalize_day_code("Monday"), "T2")
        self.assertEqual(normalize_day_code("mon"), "T2")
        self.assertEqual(normalize_day_code("MO"), "T2")
        self.assertEqual(normalize_day_code("Tuesday"), "T3")
        self.assertEqual(normalize_day_code("Wednesday"), "T4")
        self.assertEqual(normalize_day_code("Thursday"), "T5")
        self.assertEqual(normalize_day_code("Friday"), "T6")
        self.assertEqual(normalize_day_code("Saturday"), "T7")
        self.assertEqual(normalize_day_code("Sunday"), "CN")
        self.assertEqual(normalize_day_code("Thứ 2"), "T2")
        self.assertEqual(normalize_day_code("Chủ Nhật"), "CN")

    def test_time_conversions(self):
        """Test HH:MM string to minutes conversion and reverse."""
        self.assertEqual(time_to_minutes("00:00"), 0)
        self.assertEqual(time_to_minutes("08:30"), 510)
        self.assertEqual(time_to_minutes("14:15"), 855)
        self.assertEqual(time_to_minutes("2:30 PM"), 870)
        self.assertEqual(minutes_to_time(855), "14:15")
        self.assertEqual(minutes_to_time(510), "08:30")

    def test_continuous_free_slots_clock_search(self):
        """Test finding open time slots on a continuous clock timeline."""
        # On Monday (T2), Alex has classes 10:00-11:30 and 14:00-15:00.
        # Between 08:00 and 18:00, free slots should include:
        # 08:00 - 10:00 (120 mins)
        # 11:30 - 14:00 (150 mins)
        # 15:00 - 18:00 (180 mins)
        free_slots = self.compositor.find_free_slots_clock(
            day_code="T2",
            min_minutes=60,
            day_start_time="08:00",
            day_end_time="18:00",
            member_id="us_alex",
        )
        self.assertGreaterEqual(len(free_slots), 3)

        lunch_window = next((s for s in free_slots if s["start_time"] == "11:30"), None)
        self.assertIsNotNone(lunch_window)
        self.assertEqual(lunch_window["end_time"], "14:00")
        self.assertEqual(lunch_window["duration_minutes"], 150)

    def test_auto_arrange_study_event(self):
        """Test auto-arranging a 90-minute study session in open window."""
        res = self.compositor.auto_arrange_event(
            title="EECS 126 Midterm Review",
            duration_minutes=90,
            target_day="T2",
            preferred_window="afternoon",
            member_id="us_alex",
        )
        self.assertIsNotNone(res)
        self.assertTrue(res["success"])
        self.assertEqual(res["duration_minutes"], 90)
        # Should be placed in the afternoon free block (11:30-14:00 or 15:00+)
        start_min = time_to_minutes(res["start_time"])
        end_min = time_to_minutes(res["end_time"])
        self.assertEqual(end_min - start_min, 90)

    def test_campus_building_location_resolution(self):
        """Test room resolution for US halls and TDTU rooms."""
        loc_wheeler = resolve_room_location("Wheeler 150")
        self.assertIn("Wheeler Hall", loc_wheeler)

        loc_soda = resolve_room_location("Soda 310")
        self.assertIn("Soda Hall", loc_soda)

        loc_explicit = resolve_room_location("310", building="Soda Hall")
        self.assertIn("Soda Hall", loc_explicit)
        self.assertIn("Room 310", loc_explicit)

        loc_tdtu = resolve_room_location("A608")
        self.assertIn("Tòa A", loc_tdtu)

    def test_conflict_detection_cross_building_and_overlap(self):
        """Test detecting session overlap and tight turnaround between campus buildings."""
        conflicted_member = MemberSchedule(
            id="test_conflict",
            name="Conflicted Student",
            institution="UC Berkeley",
            schedule={
                "T2": [
                    ClassSession(
                        course_name="CS 61A",
                        start_time="10:00",
                        end_time="11:00",
                        building="Dwinelle Hall",
                        room="Dwinelle 155",
                        mode="clock",
                    ),
                    ClassSession(
                        course_name="Math 53 Overlap",
                        start_time="10:30",
                        end_time="12:00",
                        building="Wheeler Hall",
                        room="Wheeler 212",
                        mode="clock",
                    ),
                ],
                "T3": [
                    ClassSession(
                        course_name="Physics 7A",
                        start_time="09:00",
                        end_time="10:00",
                        building="LeConte Hall",
                        room="LeConte 1",
                        mode="clock",
                    ),
                    # Ends 10:00, next starts 10:10 (10 min gap across different buildings)
                    ClassSession(
                        course_name="Chemistry 1A",
                        start_time="10:10",
                        end_time="11:30",
                        building="Latimer Hall",
                        room="Latimer 120",
                        mode="clock",
                    ),
                ],
            },
        )
        conflicts = self.compositor.detect_schedule_conflicts(conflicted_member)
        self.assertEqual(len(conflicts), 2)

        types = [c.conflict_type for c in conflicts]
        self.assertIn("overlap", types)
        self.assertIn("campus_travel", types)

    def test_rfc5545_ics_export_and_import(self):
        """Test two-way iCalendar synchronization."""
        # 1. Export US student schedule to RFC 5545 ICS
        ics_text = self.compositor.export_schedule_to_ics(self.us_member)
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("END:VCALENDAR", ics_text)
        self.assertIn("BEGIN:VEVENT", ics_text)
        self.assertIn("CS 188", ics_text)
        self.assertIn("Wheeler Hall", ics_text)

        # 2. Import ICS back into new member
        imported = self.compositor.import_schedule_from_ics(
            ics_text=ics_text,
            member_id="imported_alex",
            member_name="Alex Miller (Imported)",
        )
        self.assertEqual(imported.id, "imported_alex")
        # Check sessions were reconstructed
        total_sessions = sum(len(v) for v in imported.schedule.values())
        self.assertGreater(total_sessions, 0)
        m_sessions = imported.get_day_sessions("T2")
        self.assertGreaterEqual(len(m_sessions), 1)
        self.assertIn("CS 188", m_sessions[0].course_name)

    def test_reasoning_capability_tools(self):
        """Test the 8 Reasoning Tools registered on the Interaction Kernel Capability."""
        cap = create_timetable_capability(compositor=self.compositor)
        reg = CapabilityRegistry()
        reg.register_capability(cap)

        op_names = list(cap.operations.keys())
        self.assertIn("get_schedule", op_names)
        self.assertIn("locate_room", op_names)
        self.assertIn("get_group_availability", op_names)
        self.assertIn("find_free_slots", op_names)
        self.assertIn("detect_conflicts", op_names)
        self.assertIn("auto_arrange_schedule", op_names)
        self.assertIn("export_schedule", op_names)
        self.assertIn("import_schedule", op_names)

        # 1. Test get_schedule for US student on Monday
        res_sched = reg.execute("get_schedule", {"target_date": "Monday", "member_id": "us_alex"})
        self.assertGreaterEqual(len(res_sched), 2)
        self.assertIn("CS 188", res_sched[0]["course_name"])
        self.assertEqual(res_sched[0]["building"], "Wheeler Hall")

        # 2. Test locate_room
        res_room = reg.execute("locate_room", {"room": "Wheeler 150"})
        self.assertIn("Wheeler Hall", res_room["location"])

        # 3. Test find_free_slots
        res_slots = reg.execute("find_free_slots", {"day": "Monday", "member_id": "us_alex", "min_minutes": 60})
        self.assertGreaterEqual(len(res_slots), 1)

        # 4. Test auto_arrange_schedule
        res_arrange = reg.execute(
            "auto_arrange_schedule",
            {
                "title": "Hackathon Brainstorm",
                "duration_minutes": 60,
                "target_day": "Monday",
                "member_id": "us_alex",
            },
        )
        self.assertTrue(res_arrange["success"])
        self.assertIn("recommendation", res_arrange)

        # 5. Test export_schedule
        res_export = reg.execute("export_schedule", {"member_id": "us_alex"})
        self.assertIn("BEGIN:VCALENDAR", res_export["ics_content"])


if __name__ == "__main__":
    unittest.main()
