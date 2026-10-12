"""
rat.main — Primary entry point for rat (GUI & CLI).
"""

from __future__ import annotations

import logging
import sys

from rat.cli import main as cli_main
from rat.os.app import run_resident_app
from rat.os.crash_shield import install_crash_shield
from rat.os.daemon import install_launch_agent, uninstall_launch_agent
from rat.os.shell_integration import generate_shell_init_script, install_to_user_zshrc

# Engage Enterprise-Grade Crash Shield & Exception Governance immediately
install_crash_shield()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] (%(name)s) %(message)s",
)


def main() -> None:
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd in ("search", "index", "status", "ask", "dedup", "--help", "-h"):
            cli_main()
            return
        elif cmd in ("init-shell", "shell"):
            print(generate_shell_init_script())
            return
        elif cmd == "install-shell":
            ok = install_to_user_zshrc()
            print("✓ Đã cài đặt tích hợp lệnh 'rat' vào ~/.zshrc!" if ok else "⚠️ Không thể ghi vào ~/.zshrc")
            return
        elif cmd in ("install-daemon", "install-service"):
            ok = install_launch_agent()
            print("✓ Đã cài đặt LaunchAgent tự động khởi động cùng macOS!" if ok else "⚠️ Cài đặt LaunchAgent thất bại")
            return
        elif cmd in ("uninstall-daemon", "uninstall-service"):
            ok = uninstall_launch_agent()
            print("✓ Đã gỡ bỏ LaunchAgent khỏi macOS!" if ok else "⚠️ Gỡ bỏ LaunchAgent thất bại")
            return
        elif cmd in ("--daemon", "-d"):
            run_resident_app(mode="daemon")
            return
        elif cmd == "spotlight":
            run_resident_app(mode="spotlight")
            return
        elif cmd in ("widget", "mini", "claude"):
            run_resident_app(mode="widget")
            return
        elif cmd in ("schedule", "tkb", "lich"):
            if len(sys.argv) > 2 and sys.argv[2] in ("--widget", "-w", "widget"):
                run_resident_app(mode="widget")
            else:
                run_resident_app(mode="schedule")
            return
        elif cmd == "finder":
            run_resident_app(mode="finder")
            return
        elif not cmd.startswith("-"):
            # 1-Action Direct CLI Resolver for Math, Campus Room, or Schedule queries
            import re
            query = " ".join(sys.argv[1:]).strip()

            # 1. Quick Math via AST safe_calculate
            calc_cand = re.sub(r"^(?:tính|tinh|calc|calculate|\=)\s*", "", query, flags=re.I).strip()
            if re.search(r"\d", calc_cand) and any(op in calc_cand for op in ["+", "*", "/", "%", "^", " - "]):
                try:
                    from reasoning_strategies import safe_calculate
                    res = safe_calculate(calc_cand)
                    if res and "Lỗi" not in res and res != "None":
                        print(f"🧮 Kết quả tính toán: {res}")
                        return
                except Exception:
                    pass

            # 2. Campus Room Guide
            m_room = re.search(r"\b([A-Fa-fCcFf]\d{3}|TRET-NTD-2)\b", query)
            if m_room:
                try:
                    from rat.timetable.model import resolve_room_location
                    rm = m_room.group(1).upper()
                    print(f"📍 Phòng {rm}: {resolve_room_location(rm)}")
                    return
                except Exception:
                    pass

            # 3. Live Agenda Query
            if any(k in query.lower() for k in ["hôm nay", "hom nay", "chiều nay", "chieu nay", "sáng nay", "sang nay", "lịch học", "lich hoc"]):
                try:
                    from rat.timetable.compositor import TimetableCompositor
                    from rat.timetable.data import load_club_members
                    comp = TimetableCompositor()
                    members = load_club_members()
                    huy = next((m for m in members if "Huy" in m.name), members[0])
                    agenda = comp.get_today_agenda(huy)
                    if agenda:
                        print(f"⚡ Hôm nay ({huy.name}) có {len(agenda)} ca học:")
                        for item in agenda:
                            s = item["session"]
                            deg = "[ThS]" if s.degree_level == "master" else "[ĐH]"
                            print(f"  • {item['badge']} [{item['start_time']} - {item['end_time']}] {deg} {s.course_name} (Phòng {s.room}) — {item['countdown']}")
                    else:
                        print(f"⚡ Hôm nay ({huy.name}) không có ca học nào trên TKB. Hoàn toàn rảnh!")
                    return
                except Exception as e:
                    logger.debug(f"CLI agenda error: {e}")

            # Fallback to semantic file search in CLI
            cli_main()
            return

    # Default 1-Action: summon sleek Master Spotlight HUD
    run_resident_app(mode="spotlight")


if __name__ == "__main__":
    main()
