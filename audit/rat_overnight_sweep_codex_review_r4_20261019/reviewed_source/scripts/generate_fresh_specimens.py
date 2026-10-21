"""
Generate fresh desktop, narrow (420px), light, and dark visual specimens
reflecting visual refinements V1-V6, Spec V2 (ResultDeskCard collapse with short answer),
Spec V3 (folder prefix candidate buttons), and Spec V4 (reasoning trace in Finder/app states).
Saves images and metadata to audit/rat_overnight_sweep_repair_20261019/visual_specimens/
and mirrors to the artifact directory.
"""
import os
import sys
import json
import shutil
import platform
import plistlib
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["RAT_WORKBENCH_SCENE"] = "1"
os.environ["RAT_WORKBENCH_FINDER"] = "1"
os.environ["RAT_REDUCE_MOTION"] = "1"

from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])
app.setProperty("ratReduceMotion", True)
app.setProperty("ratWorkbenchScene", True)
app.setProperty("ratWorkbenchFinder", True)

ARTIFACT_DIR = Path("/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = Path(os.environ.get("SPECIMENS_OUTPUT_DIR") or (REPO_ROOT / "audit" / "rat_overnight_sweep_repair_codex_repair_20261019" / "visual_specimens"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

qpa_name = app.platformName()
VN_TZ = timezone(timedelta(hours=7))
FIXED_NOW = datetime(2026, 10, 18, 14, 0, 0, tzinfo=VN_TZ)

meta = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    "qpa_platform": qpa_name,
    "capture_method": f"Qt fixture replay via QWidget.grab() (qpa_platform={qpa_name})",
    "python_version": sys.version.split()[0],
    "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
    "specimens": {},
}

def main():
    print("=== Generating Fresh Visual Specimens (Offscreen) ===")
    with patch("rat.ui.assistant_worker.AssistantWorker.start"), \
         patch("rat.ui.omnibar.Database") as mock_db, \
         patch("rat.ui.omnibar.SearchEngine") as mock_eng, \
         patch("rat.ui.feedback.FeedbackLog"), \
         patch("rat.engine.slm.slm_engine.is_service_running", return_value=False):

        mock_db.return_value.get_stats.return_value = {"total_files": 2}
        mock_db.return_value.get_recent_documents.return_value = []

        from rat.ui.omnibar import OmnibarWindow
        from rat.crawler.db import Database
        from rat.engine.progressive_search import ProgressiveSearch, SearchRequest
        from rat.engine.app_resolver import ApplicationCatalog
        from rat.engine.assistant_runtime import AssistantRuntime
        from rat.engine.selected_document_qa import answer_selected_document
        from rat.timetable.compositor import TimetableCompositor

        win = OmnibarWindow()
        win._apply_assistant_model = lambda: None
        win.show()
        win.switch_section(0)
        for _ in range(5):
            app.processEvents()

        tmp = Path(tempfile.mkdtemp())

        # Set up synthetic index for natural Finder specimen ("Slide DSA sửa tuần trước")
        finder_db_file = tmp / "finder_specimen.db"
        f_db = Database(str(finder_db_file))
        slide_dir = tmp / "slides"
        slide_dir.mkdir(parents=True, exist_ok=True)
        dsa_pdf = slide_dir / "DSA_Lecture03_Trees.pdf"
        dsa_pdf.write_text("Bài giảng cấu trúc dữ liệu và giải thuật: Cây nhị phân và AVL Tree.", encoding="utf-8")
        dsa_pptx = slide_dir / "DSA_Week05_Graphs.pptx"
        dsa_pptx.write_text("Slide bài giảng DSA tuần 5: Đồ thị, BFS, DFS và Dijkstra.", encoding="utf-8")

        # Last week timestamp: Wednesday 2026-10-07 10:00 +07:00
        last_week_ts = datetime(2026, 10, 7, 10, 0, 0, tzinfo=VN_TZ).timestamp()
        f_db.upsert_document(dict(
            file_path=str(dsa_pdf),
            file_name=dsa_pdf.name,
            file_ext=".pdf",
            file_size=4096,
            created_at=last_week_ts - 86400,
            modified_at=last_week_ts,
            indexed_at=last_week_ts,
            content_text="Bài giảng cấu trúc dữ liệu và giải thuật: Cây nhị phân và AVL Tree.",
            summary="Slide bài giảng DSA Chương 3: Cây tìm kiếm nhị phân & AVL",
        ))
        f_db.upsert_document(dict(
            file_path=str(dsa_pptx),
            file_name=dsa_pptx.name,
            file_ext=".pptx",
            file_size=8192,
            created_at=last_week_ts - 3600,
            modified_at=last_week_ts + 3600,
            indexed_at=last_week_ts + 3600,
            content_text="Slide bài giảng DSA tuần 5: Đồ thị, BFS, DFS và Dijkstra.",
            summary="Slide DSA Tuần 5: Thuật toán đồ thị BFS / DFS",
        ))

        catalog = ApplicationCatalog()
        p_search = ProgressiveSearch(str(finder_db_file), catalog=catalog, now_fn=lambda: FIXED_NOW)
        final_finder_snap = p_search.initial(SearchRequest(1, "Slide DSA sửa tuần trước"))

        # -------------------------------------------------------------------------
        # Specimen 1: Desktop Light — Natural Finder Chips + 3-Dot Thought Bubble
        # -------------------------------------------------------------------------
        print("Capturing Specimen 1: Desktop Light Natural Finder...")
        app.setProperty("ratDarkMode", False)
        win._apply_theme()
        try:
            win._finder_bridge.snapshot_ready.disconnect()
        except Exception:
            pass
        win._finder_coordinator = None
        win.workbench_finder_enabled = True
        win.set_mascot_state("searching")
        win.chat_composer_input.blockSignals(True)
        win.chat_composer_input.setPlainText("Slide DSA sửa tuần trước")
        win.chat_composer_input.blockSignals(False)
        win._on_finder_snapshot_delivered(final_finder_snap)
        win.workbench_scene.trace_expanded = True
        win.workbench_scene._sync_trace_ui(
            win.workbench_scene.current_snapshot.trace_entries,
            reasoning_flow=win.workbench_scene.current_snapshot.reasoning_flow,
            qa_telemetry=win.workbench_scene.current_snapshot.qa_telemetry,
        )
        win.resize(684, 460)
        win._resize_overlay(684, 460)
        win._fit_surface()
        for _ in range(10):
            app.processEvents()

        p1_local = OUTPUT_DIR / f"specimen_1_desktop_light_finder_{qpa_name}.png"
        win.grab().save(str(p1_local))
        shutil.copy2(p1_local, ARTIFACT_DIR / p1_local.name)
        meta["specimens"]["desktop_light_finder"] = {
            "file": p1_local.name,
            "qpa_platform": qpa_name,
            "width": win.width(),
            "height": win.height(),
            "theme": "light",
            "mode": "compact_desktop_finder",
            "thought_trail_visible": win.thought_trail.isVisible(),
            "finder_chips": list(final_finder_snap.intent.interpretation_chips) if final_finder_snap.intent else [],
            "hit_count": len(final_finder_snap.hits),
        }

        # -------------------------------------------------------------------------
        # Specimen 2: Narrow (420px) Light — Reflowed Compact Workbench + 4 Buttons
        # -------------------------------------------------------------------------
        print("Capturing Specimen 2: Narrow (420px) Light Finder...")
        win.resize(420, 490)
        win._resize_overlay(420, 490)
        win._fit_surface()
        for _ in range(10):
            app.processEvents()
        if not win.workbench_scene.finder_box._rows:
            win._on_finder_snapshot_delivered(final_finder_snap)
            for _ in range(5):
                app.processEvents()

        first_row = next(iter(win.workbench_scene.finder_box._rows.values()))
        btn_geoms = {}
        for bname in ("btn_ask", "btn_open", "btn_preview", "btn_reveal"):
            btn = getattr(first_row, bname)
            btn_geoms[bname] = {
                "width": btn.width(),
                "height": btn.height(),
                "visible_region_non_empty": not btn.visibleRegion().isEmpty(),
            }

        p2_local = OUTPUT_DIR / f"specimen_2_narrow_420px_light_{qpa_name}.png"
        win.grab().save(str(p2_local))
        shutil.copy2(p2_local, ARTIFACT_DIR / p2_local.name)
        meta["specimens"]["narrow_420px_light"] = {
            "file": p2_local.name,
            "qpa_platform": qpa_name,
            "width": win.width(),
            "height": win.height(),
            "theme": "light",
            "mode": "narrow_420px_finder",
            "is_narrow": win._is_narrow(),
            "thought_trail_visible": win.thought_trail.isVisible(),
            "file_action_buttons": btn_geoms,
        }

        # -------------------------------------------------------------------------
        # Specimen 3: Desktop Light — Grounded Reasoning Trace + Document QA
        # -------------------------------------------------------------------------
        print("Capturing Specimen 3: Desktop Light QA...")
        win.workbench_scene.clear_finder_snapshot()
        win.resize(684, 560)
        win._resize_overlay(684, 560)

        real_doc = tmp / "so_tay_sinh_vien_2026.txt"
        doc_text = (
            "Điều 1: Đăng ký học phần theo tín chỉ.\n"
            "Điều 2: Sinh viên được đăng ký tối đa 24 tín chỉ mỗi học kỳ chính và 12 tín chỉ học kỳ hè.\n"
            "Điều 3: Rút học phần thực hiện trước tuần thứ 6."
        )
        real_doc.write_text(doc_text, encoding="utf-8")
        f_db.upsert_document(dict(
            file_path=str(real_doc),
            file_name=real_doc.name,
            file_ext=".txt",
            file_size=len(doc_text),
            created_at=last_week_ts,
            modified_at=last_week_ts,
            indexed_at=last_week_ts,
            content_text=doc_text,
            summary="Sổ tay sinh viên 2026",
        ))

        client = Mock()
        short_ans = (
            "Theo Điều 2 trong sổ tay sinh viên 2026, sinh viên được đăng ký tối đa "
            "24 tín chỉ mỗi học kỳ chính và 12 tín chỉ trong học kỳ hè."
        )
        client.chat_with_meta.return_value = dict(
            message={"content": short_ans},
            done_reason="stop",
            prompt_tokens=142,
            completion_tokens=38,
            error=None,
        )
        runtime = AssistantRuntime(db=f_db, compositor=TimetableCompositor([]), use_live_model=True)
        win.assistant_runtime = runtime

        query_qa = "Học kỳ chính được đăng ký tối đa bao nhiêu tín chỉ?"
        win._submit_chat_prompt(query_qa, selected_document_path=str(real_doc))
        handle = win._assistant_handle
        answer = answer_selected_document(
            runtime,
            query_qa,
            str(real_doc),
            model_client=client,
            turn_ref=handle["turn_ref"],
            execution_id=handle["execution_id"],
        )
        win.workbench_scene.projector.qa_telemetry = {
            "first_token_ms": 118.0,
            "total_ms": 420.0,
            "prompt_tokens": 142,
            "completion_tokens": 38,
            "reused_prefix_tokens": 96,
        }
        win._on_assistant_response(handle, answer)
        win.workbench_scene.trace_expanded = True
        win.workbench_scene._sync_trace_ui(
            win.workbench_scene.current_snapshot.trace_entries,
            reasoning_flow=win.workbench_scene.current_snapshot.reasoning_flow,
            qa_telemetry=win.workbench_scene.current_snapshot.qa_telemetry,
        )
        win.chat_composer_input.setPlainText("")
        win._fit_surface()
        for _ in range(10):
            app.processEvents()

        p3a_local = OUTPUT_DIR / f"specimen_3a_desktop_light_sources_top_{qpa_name}.png"
        win.grab().save(str(p3a_local))
        shutil.copy2(p3a_local, ARTIFACT_DIR / p3a_local.name)

        # Scroll overview so the answer and expanded reasoning trace are visible
        sb = win.workbench_scene.overview_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())
        for _ in range(5):
            app.processEvents()

        p3b_local = OUTPUT_DIR / f"specimen_3b_desktop_light_trace_bottom_{qpa_name}.png"
        win.grab().save(str(p3b_local))
        shutil.copy2(p3b_local, ARTIFACT_DIR / p3b_local.name)

        meta["specimens"]["desktop_light_trace_qa"] = {
            "file_top": p3a_local.name,
            "file_bottom": p3b_local.name,
            "qpa_platform": qpa_name,
            "width": win.width(),
            "height": win.height(),
            "theme": "light",
            "mode": "desktop_grounded_trace_qa",
            "thought_trail_visible": win.thought_trail.isVisible(),
            "result_card_hidden_for_short_answer": win.workbench_scene.result_card.isHidden(),
            "reasoning_steps": [
                {"number": e.number, "status": e.status, "title": e.title, "detail": e.detail}
                for e in win.workbench_scene.current_snapshot.reasoning_flow
            ],
        }

        # -------------------------------------------------------------------------
        # Specimen 4: Desktop Dark — App Disambiguation + Spec V3 Distinguishing Buttons
        # -------------------------------------------------------------------------
        print("Capturing Specimen 4: Desktop Dark Disambiguation (Spec V3)...")
        win._reset_chat()
        app.setProperty("ratDarkMode", True)
        win._apply_theme()

        lol_app_1 = tmp / "Applications" / "League of Legends.app"
        lol_app_2 = tmp / "Riot Games" / "League of Legends.app"
        for idx, app_dir in enumerate((lol_app_1, lol_app_2), start=1):
            (app_dir / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
            exe = app_dir / "Contents" / "MacOS" / "LeagueClient"
            exe.write_text("#!/bin/sh\n", encoding="utf-8")
            exe.chmod(0o755)
            info_plist = app_dir / "Contents" / "Info.plist"
            with info_plist.open("wb") as f:
                plistlib.dump({
                    "CFBundleIdentifier": "com.riotgames.leagueoflegends",
                    "CFBundleExecutable": "LeagueClient",
                    "CFBundleDisplayName": "League of Legends",
                    "CFBundleShortVersionString": f"14.2{idx}",
                }, f)

        multi_cat = ApplicationCatalog.scan([tmp / "Applications", tmp / "Riot Games"])
        win._finder_catalog = multi_cat
        with patch("rat.ui.assistant_worker.ArtifactWorker.start"):
            win._submit_chat_prompt("mở Liên Minh")
            worker = win._artifact_worker
            result = worker.callback()
            win._on_artifact_result(win._chat_generation, result)

        win.workbench_scene.trace_expanded = True
        win.workbench_scene._sync_trace_ui(
            win.workbench_scene.current_snapshot.trace_entries,
            reasoning_flow=win.workbench_scene.current_snapshot.reasoning_flow,
            qa_telemetry=win.workbench_scene.current_snapshot.qa_telemetry,
        )
        win.resize(684, 540)
        win._resize_overlay(684, 540)
        win._fit_surface()
        for _ in range(10):
            app.processEvents()

        p4_local = OUTPUT_DIR / f"specimen_4_desktop_dark_disambiguation_{qpa_name}.png"
        win.grab().save(str(p4_local))
        shutil.copy2(p4_local, ARTIFACT_DIR / p4_local.name)

        from PyQt6.QtWidgets import QPushButton
        candidate_buttons = [b.text() for b in win.workbench_scene.result_card.findChildren(QPushButton)]

        meta["specimens"]["desktop_dark_disambiguation"] = {
            "file": p4_local.name,
            "qpa_platform": qpa_name,
            "width": win.width(),
            "height": win.height(),
            "theme": "dark",
            "mode": "desktop_dark_app_disambiguation_trace",
            "thought_trail_visible": win.thought_trail.isVisible(),
            "candidate_button_labels": candidate_buttons,
            "reasoning_steps": [
                {"number": e.number, "status": e.status, "title": e.title, "detail": e.detail}
                for e in win.workbench_scene.current_snapshot.reasoning_flow
            ],
        }

        f_db.get_connection().close()
        win.shutdown()

    meta_json = json.dumps(meta, indent=2, ensure_ascii=False)
    (OUTPUT_DIR / "specimens_metadata.json").write_text(meta_json, encoding="utf-8")
    (ARTIFACT_DIR / "specimens_metadata.json").write_text(meta_json, encoding="utf-8")
    print("Specimens generation complete!")
    print(meta_json)

if __name__ == "__main__":
    main()
