"""Built-in mechanical tools: timetable lookup, document search, arithmetic."""

from __future__ import annotations

import ast
import math
import operator
import re
from datetime import datetime
from typing import Any, Dict, List, Optional


def get_schedule(
    compositor,
    target_date: Optional[str] = "today",
    member_id: Optional[str] = None,
    now_dt: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Mechanical timetable arithmetic: returns structured class sessions.
    """
    from rat.timetable.model import TDTU_PERIODS
    now = now_dt or datetime.now()
    target_str = (target_date or "today").strip().lower()

    # Find member
    member = compositor.members[0] if compositor.members else None
    if member_id:
        found = next((m for m in compositor.members if m.id == member_id or m.name == member_id), None)
        if found is None:
            raise ValueError("Thành viên không có trong thời khóa biểu")
        member = found

    if not member:
        return []

    weekday_code_map = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}
    weekday_name_map = {
        "T2": "Thứ Hai", "T3": "Thứ Ba", "T4": "Thứ Tư",
        "T5": "Thứ Năm", "T6": "Thứ Sáu", "T7": "Thứ Bảy", "CN": "Chủ Nhật"
    }

    # Resolve requested day code
    selected_code: Optional[str] = None
    is_today = False

    if target_str in ("today", "hôm nay", "hom nay", "now", "hiện tại"):
        selected_code = weekday_code_map[now.weekday()]
        is_today = True
    elif target_str in ("tomorrow", "ngày mai", "ngay mai", "mai"):
        tomorrow_idx = (now.weekday() + 1) % 7
        selected_code = weekday_code_map[tomorrow_idx]
    elif target_str in ("next", "tiếp theo", "tiep theo"):
        # Check today first
        today_code = weekday_code_map[now.weekday()]
        today_agenda = compositor.get_today_agenda(member, now)
        live_or_upcoming = [item for item in today_agenda if item["status"] in ("live", "upcoming")]
        if live_or_upcoming:
            s = live_or_upcoming[0]["session"]
            st = live_or_upcoming[0]["status"]
            p_start = s.start_time or TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
            p_end = s.end_time or TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]
            return [{
                "course_name": s.course_name,
                "course_code": s.course_code,
                "room": s.room,
                "day": weekday_name_map.get(today_code, today_code),
                "day_code": today_code,
                "time": f"{p_start} - {p_end}",
                "start_period": s.start_period,
                "end_period": s.end_period,
                "instructor": getattr(s, "lecturer", ""),
                "degree_level": s.degree_level,
                "status": st,
            }]
        # Scan the whole week, including when tomorrow is a day off.
        for offset in range(1, 8):
            code = weekday_code_map[(now.weekday() + offset) % 7]
            if member.schedule.get(code):
                selected_code = code
                break
        if selected_code is None:
            return []
    else:
        english_weekday_map = {
            "monday": "T2", "mon": "T2",
            "tuesday": "T3", "tue": "T3",
            "wednesday": "T4", "wed": "T4",
            "thursday": "T5", "thu": "T5",
            "friday": "T6", "fri": "T6",
            "saturday": "T7", "sat": "T7",
            "sunday": "CN", "sun": "CN",
        }
        for eng_name, eng_code in english_weekday_map.items():
            if eng_name == target_str:
                selected_code = eng_code
                break

        if not selected_code:
            # Check explicit code or name
            for code, name in weekday_name_map.items():
                if code.lower() == target_str or name.lower() == target_str:
                    selected_code = code
                    break

    if not selected_code:
        try:
            requested = datetime.strptime(target_str, "%Y-%m-%d")
            selected_code = weekday_code_map[requested.weekday()]
            is_today = requested.date() == now.date()
        except ValueError:
            raise ValueError("Ngày không hợp lệ; dùng YYYY-MM-DD, today, tomorrow hoặc next")

    raw_sessions = sorted(member.schedule.get(selected_code, []), key=lambda s: s.start_period)
    day_label = weekday_name_map.get(selected_code, selected_code)

    results = []
    now_mins = now.hour * 60 + now.minute

    for s in raw_sessions:
        p_start = s.start_time or TDTU_PERIODS.get(s.start_period, ("00:00", "00:00", "", ""))[0]
        p_end = s.end_time or TDTU_PERIODS.get(s.end_period, ("23:59", "23:59", "", ""))[1]

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


def search_documents(db, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Mechanical FTS & candidate search: locates course slides and documents.
    """
    q = (query or "").strip()
    if not q:
        return []

    # Split into search tokens
    clean_tokens = [t.lower() for t in re.split(r"[\s\-_,.:]+", q) if len(t) >= 2]
    candidates = db.search_candidates(keywords=clean_tokens, limit=limit * 2)

    results = []
    for c in candidates[:limit]:
        results.append({
            "filename": c.get("file_name", ""),
            "path": c.get("file_path", ""),
            "extension": c.get("file_ext", ""),
            "snippet": (c.get("summary") or c.get("file_name") or "")[:200],
            "score": round(float(c.get("rank", 1.0)), 2),
        })
    return results


def calculate(expression):
    """Small arithmetic with bounded intermediate values and no code execution."""
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 80:
        raise ValueError("Expression is too large")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
                  ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
                  ast.Pow: operator.pow}

    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = node.value
        elif isinstance(node, ast.UnaryOp) and type(node.op) in (ast.UAdd, ast.USub):
            value = evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow):
                if abs(right) > 1000 or (isinstance(left, int) and right > 0 and left.bit_length() * right > 4096):
                    raise ValueError("Exponent exceeds the calculator budget")
            value = operations[type(node.op)](left, right)
        else:
            raise ValueError("Unsupported arithmetic expression")
        if type(value) not in (int, float) or (isinstance(value, int) and value.bit_length() > 4096) or (isinstance(value, float) and not math.isfinite(value)):
            raise ValueError("Result exceeds the calculator budget")
        return value

    return str(evaluate(tree.body))
