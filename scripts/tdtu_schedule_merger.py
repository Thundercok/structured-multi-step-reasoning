#!/usr/bin/env python3
"""
scripts/tdtu_schedule_merger.py
---------------------------------
Hệ thống Tự Động Hóa & Ghép Lịch Trình Sinh Viên TDTU Cho Câu Lạc Bộ.
- Phân tích thời khóa biểu 6 thành viên (Trích xuất từ cổng eti.tdtu.edu.vn / c-lichthi.tdtu.edu.vn)
- Tính toán ma trận rảnh/bận và nhận diện "Khung giờ vàng" (Golden Windows) cả nhóm đều rảnh.
- Xuất file iCalendar (.ics) đồng bộ Google Calendar & Apple Calendar.
"""

import json
import os
from datetime import datetime, timezone

# Định nghĩa các tiết học chuẩn của ĐH Tôn Đức Thắng (TDTU)
TDTU_PERIODS = {
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

DAYS = [
    ("T2", "Thứ 2", "2026-09-07"),
    ("T3", "Thứ 3", "2026-09-08"),
    ("T4", "Thứ 4", "2026-09-09"),
    ("T5", "Thứ 5", "2026-09-10"),
    ("T6", "Thứ 6", "2026-09-11"),
    ("T7", "Thứ 7", "2026-09-12"),
    ("CN", "Chủ Nhật", "2026-09-13"),
]

# Dữ liệu 6 thành viên CLB đã bóc tách từ các ảnh TKB TDTU
MEMBERS_DATA = [
    {
        "id": "m1",
        "name": "Huỳnh Nhật Huy",
        "mssv": "523C0012",
        "major": "Công nghệ Thông tin",
        "schedule": {
            "T2": [(1, 3, "Thực hành Giải tích ứng dụng CNTT 2", "A608"), (4, 6, "Giải tích ứng dụng CNTT 2", "F702")],
            "T3": [(7, 9, "Lập trình hàm", "F712"), (10, 12, "Thực hành Lập trình hàm", "A607")],
            "T4": [(4, 6, "Cấu trúc dữ liệu & giải thuật", "F702"), (7, 9, "Cấu trúc dữ liệu & giải thuật (Bù)", "C404")],
            "T5": [(1, 3, "Kỹ năng soạn thảo VB kỹ thuật", "C406"), (7, 9, "Giải tích ứng dụng CNTT", "F610")],
            "T6": [(1, 3, "Thực hành Giải tích ứng dụng CNTT", "A610"), (7, 9, "Thực hành Cấu trúc dữ liệu", "A707")],
            "T7": [],
            "CN": []
        }
    },
    {
        "id": "m2",
        "name": "Thành viên QTKD",
        "mssv": "K27-QTKD",
        "major": "Quản trị Kinh doanh / Tài chính",
        "schedule": {
            "T2": [],
            "T3": [(2, 6, "Quản lý sự thay đổi", "C411-A"), (7, 11, "Ứng dụng Big Data trong quản lý", "D0401-B")],
            "T4": [(1, 3, "HFIATA - Module 4 (Contract & Finance)", "C303"), (7, 9, "Khởi nghiệp & đổi mới sáng tạo", "D0306")],
            "T5": [],
            "T6": [],
            "T7": [(4, 6, "HFIATA - Module 4", "F707")],
            "CN": [(1, 3, "HFIATA - Module 4 (Online Bù)", "HOCTRUCTUYEN-3")]
        }
    },
    {
        "id": "m3",
        "name": "Phạm Vũ Thảo Nguyên",
        "mssv": "62500106",
        "major": "Khoa học Ứng dụng",
        "schedule": {
            "T2": [(10, 12, "GDTC 2 - Karate", "TRET-NTD-2"), (13, 15, "Sinh hoạt chủ nhiệm KHUD", "B406-A")],
            "T3": [(3, 6, "Hóa vô cơ", "C401"), (7, 9, "Hóa lý kỹ thuật 1", "B204")],
            "T4": [(1, 3, "Vẽ kỹ thuật", "B406-A"), (4, 6, "Nhập môn Phân tích Dữ liệu", "B406-B"), (7, 9, "Thực hành Vẽ kỹ thuật", "A703")],
            "T5": [(4, 6, "Kinh tế chính trị Mác-Lênin", "B204"), (7, 9, "Toán cao cấp trong KH sự sống", "C308")],
            "T6": [(1, 6, "Thí nghiệm Hóa đại cương", "C511")],
            "T7": [],
            "CN": []
        }
    },
    {
        "id": "m4",
        "name": "Thành viên Kiến trúc",
        "mssv": "K27-KT",
        "major": "Kiến trúc / Quy hoạch",
        "schedule": {
            "T2": [(4, 6, "Vật liệu trong kiến trúc", "D0101-B"), (7, 9, "Nhập môn quy hoạch", "D0105-A")],
            "T3": [],
            "T4": [(10, 12, "Lịch sử kiến trúc Phương Đông & VN", "D0102-A")],
            "T5": [],
            "T6": [(7, 9, "Chuyên đề thiết nội thất", "D0101-A"), (10, 12, "Khoa học môi trường kiến trúc", "D0101-A")],
            "T7": [(1, 3, "Chuyên đề kiến trúc nhà công nghiệp", "D0101-A")],
            "CN": []
        }
    },
    {
        "id": "m5",
        "name": "Thành viên CNSH",
        "mssv": "K27-CNSH",
        "major": "Công nghệ Sinh học / Y sinh",
        "schedule": {
            "T2": [(1, 3, "Tiếng Anh 3", "P15H03"), (7, 9, "Vật liệu sinh học", "F702")],
            "T3": [(1, 6, "Thí nghiệm Genomic phân tử", "C511"), (7, 9, "Vi sinh vật và bệnh học", "F410")],
            "T4": [(1, 3, "Tiếng Anh 3", "P15H03")],
            "T5": [(1, 3, "Thiết kế & phân tích thí nghiệm", "F507")],
            "T6": [(1, 3, "Tiếng Anh 3", "P15H03"), (7, 11, "Miễn dịch học", "F610")],
            "T7": [],
            "CN": []
        }
    },
    {
        "id": "m6",
        "name": "Thông Ngọc Lan Anh",
        "mssv": "624H0001",
        "major": "Kỹ thuật Hóa học",
        "schedule": {
            "T2": [(1, 6, "Thí nghiệm Hóa hữu cơ", "C513")],
            "T3": [(1, 3, "Hóa học xanh", "F412"), (4, 6, "Lịch sử Đảng Cộng sản VN", "B411")],
            "T4": [(1, 3, "Hóa phân tích", "F512"), (4, 6, "Quản trị công nghiệp", "F701")],
            "T5": [(4, 6, "Hóa sinh", "C205")],
            "T6": [(4, 6, "Kỹ thuật phân riêng", "F712")],
            "T7": [(4, 6, "Vật liệu học", "F302"), (7, 12, "Thí nghiệm Hóa lý kỹ thuật", "C512")],
            "CN": []
        }
    }
]

def analyze_availability():
    """Phân tích ma trận rảnh/bận và các khung giờ vàng"""
    results = {}
    total_members = len(MEMBERS_DATA)

    for day_code, day_name, date_str in DAYS:
        results[day_code] = {
            "name": day_name,
            "date": date_str,
            "periods": {}
        }
        for period_id, (t_start, t_end, shift, ca) in TDTU_PERIODS.items():
            busy_list = []
            free_list = []
            for member in MEMBERS_DATA:
                busy = False
                for start_p, end_p, course, room in member["schedule"].get(day_code, []):
                    if start_p <= period_id <= end_p:
                        busy_list.append({
                            "member": member["name"],
                            "course": course,
                            "room": room
                        })
                        busy = True
                        break
                if not busy:
                    free_list.append(member["name"])

            results[day_code]["periods"][period_id] = {
                "time": f"{t_start} - {t_end}",
                "shift": shift,
                "ca": ca,
                "free_count": len(free_list),
                "busy_count": len(busy_list),
                "ratio": len(free_list) / total_members,
                "free_members": free_list,
                "busy_details": busy_list
            }
    return results

def find_golden_slots(analysis, min_ratio=1.0):
    """Tìm các dải tiết rảnh liên tục đạt tỷ lệ mong muốn"""
    golden_windows = []
    for day_code, d_info in analysis.items():
        current_window = None
        for p_id in sorted(d_info["periods"].keys()):
            p_data = d_info["periods"][p_id]
            if p_data["ratio"] >= min_ratio:
                if current_window is None:
                    current_window = {
                        "day_code": day_code,
                        "day_name": d_info["name"],
                        "date": d_info["date"],
                        "start_period": p_id,
                        "end_period": p_id,
                        "ratio": p_data["ratio"],
                        "free_count": p_data["free_count"],
                        "busy_count": p_data["busy_count"],
                        "free_members": p_data["free_members"],
                        "busy_members": [b["member"] for b in p_data["busy_details"]]
                    }
                else:
                    current_window["end_period"] = p_id
            else:
                if current_window:
                    golden_windows.append(current_window)
                    current_window = None
        if current_window:
            golden_windows.append(current_window)
    return golden_windows

def export_ics(golden_windows, filepath="scripts/club_free_slots.ics"):
    """Tạo file iCalendar chuẩn để nhập vào Google Calendar hoặc Apple Calendar"""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//TDTU Club Planner//VN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Lich Trong Chung CLB (TDTU)",
        "X-WR-TIMEZONE:Asia/Ho_Chi_Minh",
    ]

    for idx, w in enumerate(golden_windows):
        start_time_str = TDTU_PERIODS[w["start_period"]][0]
        end_time_str = TDTU_PERIODS[w["end_period"]][1]
        
        dt_date = w["date"].replace("-", "")
        dt_start = f"{dt_date}T{start_time_str.replace(':', '')}00"
        dt_end = f"{dt_date}T{end_time_str.replace(':', '')}00"

        title = f"[CLB FREE] {w['day_name']}: Tiet {w['start_period']}-{w['end_period']} ({w['free_count']}/6 Ban Ranh)"
        desc = f"Khung gio ranh hop CLB.\\nRanh: {', '.join(w['free_members'])}\\nTiet {w['start_period']} - {w['end_period']} ({start_time_str} - {end_time_str})"

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:tdtu-club-{dt_start}-{idx}@club.tdtu.edu.vn",
            f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART;TZID=Asia/Ho_Chi_Minh:{dt_start}",
            f"DTEND;TZID=Asia/Ho_Chi_Minh:{dt_end}",
            f"SUMMARY:{title}",
            f"DESCRIPTION:{desc}",
            "STATUS:CONFIRMED",
            "END:VEVENT"
        ])

    lines.append("END:VCALENDAR")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\r\n".join(lines))
    print(f"✅ Đã xuất file iCalendar thành công: {filepath}")

def main():
    print("=" * 65)
    print("📊 BÁO CÁO PHÂN TÍCH LỊCH TRÌNH 6 THÀNH VIÊN CLB (TDTU)")
    print("=" * 65)

    analysis = analyze_availability()
    
    slots_100 = find_golden_slots(analysis, min_ratio=1.0)
    print(f"\n✨ KHUNG GIỜ VÀNG (100% CẢ 6 THÀNH VIÊN ĐỀU RẢNH) - Tổng cộng {len(slots_100)} khoảng:")
    for idx, s in enumerate(slots_100, 1):
        t_start = TDTU_PERIODS[s['start_period']][0]
        t_end = TDTU_PERIODS[s['end_period']][1]
        span = s['end_period'] - s['start_period'] + 1
        print(f"  {idx}. {s['day_name']} ({s['date']}): Tiết {s['start_period']:2d} -> {s['end_period']:2d} ({t_start} - {t_end}) | {span} tiết liền mạch")

    slots_80 = find_golden_slots(analysis, min_ratio=0.8)
    print(f"\n⚡ KHUNG GIỜ KHẢ DỤNG CAO (>= 80% THÀNH VIÊN RẢNH, 5/6 HOẶC 6/6) - Tổng cộng {len(slots_80)} khoảng:")
    for idx, s in enumerate(slots_80, 1):
        t_start = TDTU_PERIODS[s['start_period']][0]
        t_end = TDTU_PERIODS[s['end_period']][1]
        span = s['end_period'] - s['start_period'] + 1
        busy_txt = f" (Bận: {', '.join(s['busy_members'])})" if s['busy_members'] else " (100% FREE)"
        print(f"  {idx}. {s['day_name']} ({s['date']}): Tiết {s['start_period']:2d} -> {s['end_period']:2d} ({t_start} - {t_end}) | {s['free_count']}/6 rảnh{busy_txt}")

    export_ics(slots_80, "scripts/club_free_slots.ics")

if __name__ == "__main__":
    main()
