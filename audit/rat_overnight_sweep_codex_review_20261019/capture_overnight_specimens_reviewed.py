import os
import sys
import tempfile
import plistlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["RAT_WORKBENCH_SCENE"] = "1"
os.environ["RAT_WORKBENCH_FINDER"] = "1"
os.environ["RAT_REDUCE_MOTION"] = "1"

from PyQt6.QtCore import Qt, QPoint, QRect, QSize
from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QScrollArea
from PyQt6.QtTest import QTest

app = QApplication.instance() or QApplication([])
app.setProperty("ratReduceMotion", True)

out_dirs = [
    Path("audit/rat_overnight_sweep_final_20261019/visual_specimens"),
    Path("/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a"),
]
for d in out_dirs:
    d.mkdir(parents=True, exist_ok=True)

def pump(count=6):
    for _ in range(count):
        app.processEvents()
        QTest.qWait(15)

def save_specimen(widget, filename):
    pump(8)
    for d in out_dirs:
        p = d / filename
        widget.grab().save(str(p))
        print(f"Saved {p} ({widget.width()}x{widget.height()})")

with patch("rat.ui.assistant_worker.AssistantWorker.start"), \
     patch("rat.ui.feedback.FeedbackLog"), \
     patch("rat.ui.omnibar.SearchEngine"), \
     patch("rat.engine.hybrid_search.SearchEngine"), \
     patch("rat.engine.slm.slm_engine.is_service_running", return_value=False):

    from rat.ui.omnibar import OmnibarWindow
    from rat.crawler.db import Database
    from rat.engine.app_resolver import ApplicationCatalog
    from rat.engine.progressive_search import ProgressiveSearch, SearchRequest, SearchCoordinator
    from rat.engine.assistant_runtime import AgentResponse, AgentStep
    from rat.engine.completion import ExecutionJournal

    # Setup temporary directory and database with synthetic documents
    tmp_path = Path(tempfile.mkdtemp())
    db_file = tmp_path / "specimen.db"
    db = Database(str(db_file))

    # Synthetic file 1: slide DSA
    slide_file = tmp_path / "DSA_lecture_week5.pdf"
    slide_file.write_text("Slide bài giảng Cấu trúc dữ liệu và giải thuật tuần 5: Cây đỏ đen và Bảng băm.", encoding="utf-8")
    db.upsert_document({
        "file_path": str(slide_file),
        "file_name": slide_file.name,
        "file_ext": ".pdf",
        "file_size": 2048,
        "created_at": 1728500000,
        "modified_at": 1728500000,
        "indexed_at": 1728500000,
        "content_text": slide_file.read_text(encoding="utf-8"),
        "summary": "Slide bài giảng DSA tuần 5 về cây đỏ đen và bảng băm",
    })

    # Synthetic file 2: so tay sinh vien
    doc_file = tmp_path / "so_tay_sinh_vien_2026.txt"
    doc_file.write_text(
        "Điều 1: Đăng ký học phần theo tín chỉ.\n"
        "Điều 2: Sinh viên được đăng ký tối đa 24 tín chỉ mỗi học kỳ chính và 12 tín chỉ học kỳ hè.\n"
        "Điều 3: Rút học phần thực hiện trước tuần thứ 6.",
        encoding="utf-8"
    )
    db.upsert_document({
        "file_path": str(doc_file),
        "file_name": doc_file.name,
        "file_ext": ".txt",
        "file_size": len(doc_file.read_bytes()),
        "created_at": 1728000000,
        "modified_at": 1728000000,
        "indexed_at": 1728000000,
        "content_text": doc_file.read_text(encoding="utf-8"),
        "summary": "Sổ tay sinh viên 2026 quy định tín chỉ học kỳ",
    })

    # Synthetic apps for disambiguation
    def make_app(folder, name, bundle_id, version="1.0"):
        p = tmp_path / folder / f"{name}.app"
        (p / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        (p / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
            "CFBundleIdentifier": bundle_id,
            "CFBundleName": name,
            "CFBundleShortVersionString": version,
            "CFBundleExecutable": "app-bin",
        }))
        (p / "Contents" / "MacOS" / "app-bin").write_text("binary")
        return p

    app1 = make_app("Applications", "League of Legends", "com.riotgames.leagueoflegends", "14.21")
    app2 = make_app("Riot Games", "League of Legends", "com.riotgames.leagueoflegends", "14.22")
    catalog = ApplicationCatalog.scan([app1.parent, app2.parent])

    # Instantiate Omnibar Window
    win = OmnibarWindow()
    win._apply_assistant_model = lambda: None
    win.workbench_finder_enabled = True
    win._finder_catalog = catalog
    win._finder_search = ProgressiveSearch(str(db_file), catalog=catalog)
    win._finder_coordinator = SearchCoordinator(
        win._finder_search,
        on_update=lambda snap: win._finder_bridge.snapshot_ready.emit(snap),
    )
    win.show()
    pump(6)

    metadata = {
        "generated_at_utc": "2026-10-19T04:30:00Z",
        "qpa_platform": "offscreen",
        "capture_method": "Qt fixture replay via QWidget.grab() (qpa_platform=offscreen)",
        "python_version": sys.version.split()[0],
        "platform": f"{os.uname().sysname} {os.uname().release} ({os.uname().machine})",
        "specimens": {}
    }

    # =========================================================================
    # SPECIMEN 1: Desktop Light (Finder Search with Concise Chip & Scope Banner)
    # =========================================================================
    win.resize(620, 440)
    win._resize_overlay(620, 440)
    win.switch_section(0)
    finder_snap = win._finder_search.initial(SearchRequest(1, "Slide DSA sửa tuần trước"))
    win.workbench_scene.set_finder_snapshot(finder_snap)
    win._sync_compact_surface()
    win._fit_surface()
    pump(8)
    save_specimen(win, "specimen_1_desktop_light_finder_offscreen.png")
    metadata["specimens"]["desktop_light_finder"] = {
        "file": "specimen_1_desktop_light_finder_offscreen.png",
        "qpa_platform": "offscreen",
        "width": win.width(),
        "height": win.height(),
        "theme": "light",
        "mode": "compact_desktop_finder",
        "thought_trail_visible": win.workbench_thought_trail.isVisible(),
        "finder_chips": [c for c in finder_snap.intent.chips if isinstance(c, str)],
        "hit_count": len(finder_snap.hits),
    }

    # =========================================================================
    # SPECIMEN 2: Narrow 420px (Finder Search unclipped file action buttons)
    # =========================================================================
    win.resize(420, 520)
    win._resize_overlay(420, 520)
    win._fit_surface()
    pump(8)
    save_specimen(win, "specimen_2_narrow_420px_light_offscreen.png")
    metadata["specimens"]["narrow_420px_light"] = {
        "file": "specimen_2_narrow_420px_light_offscreen.png",
        "qpa_platform": "offscreen",
        "width": win.width(),
        "height": win.height(),
        "theme": "light",
        "mode": "narrow_420px_finder",
        "is_narrow": win._is_narrow(),
        "thought_trail_visible": win.workbench_thought_trail.isVisible(),
    }

    # =========================================================================
    # SPECIMEN 3a / 3b: Desktop Light (Document QA — Refined Level-1 Overview)
    # =========================================================================
    win.resize(652, 600)
    win._resize_overlay(652, 600)
    win.assistant_runtime.db = db
    ctx = {"db": db, "compositor": win.assistant_runtime.compositor}
    read_disp = win.assistant_runtime.dispatcher.execute_operation(
        "read_document",
        {"file_path": str(doc_file), "max_chars": 3000},
        context=ctx,
    )

    query = "Học kỳ chính được đăng ký tối đa bao nhiêu tín chỉ?"
    turn_snap = win._conversation.begin_turn(query)
    handle = win.chat_stream.create_streaming_message(
        strategy="Assistant",
        badge="Đang xử lý",
        turn_id=turn_snap.turn_ref.turn_id,
    )
    handle["generation"] = win._chat_generation
    handle["turn_ref"] = turn_snap.turn_ref
    handle["execution_id"] = turn_snap.execution_id
    handle["observed_sources"] = []
    win._assistant_handle = handle
    win._pending_chat_query = query
    win._show_interaction_surface()
    win.workbench_scene.begin_turn(
        query,
        generation=win._chat_generation,
        execution_id=turn_snap.execution_id,
        turn_id=turn_snap.turn_ref.turn_id,
        artifact_store=win.assistant_runtime.artifact_store,
    )

    step1 = AgentStep(
        step_number=1,
        thought="Đọc tài liệu sổ tay sinh viên",
        tool_name="read_document",
        tool_result=read_disp.result,
        artifacts=[read_disp.artifact],
    )
    win._on_assistant_step(handle, step1)

    journal = ExecutionJournal(
        conversation_id="conv-specimen-qa",
        execution_id=turn_snap.execution_id,
        turn_id=turn_snap.turn_ref.turn_id,
    )
    journal.start()
    journal.record_step(
        number=1,
        action="read_document",
        inputs={"file_path": str(doc_file)},
        status="success",
        outputs={"artifact_id": read_disp.artifact.id, "revision": 1},
        evidence_ref=f"{read_disp.artifact.id}@v1",
    )
    journal.record_step(
        number=2,
        action="answer",
        inputs={},
        status="success",
        outputs={"answer": "Sinh viên được đăng ký tối đa 24 tín chỉ mỗi học kỳ chính và 12 tín chỉ trong học kỳ hè."},
        evidence_ref=f"{read_disp.artifact.id}@v1",
    )
    journal.close(final_status="success")

    from rat.kernel.contracts import TurnContract, DeliveryReconciliation, ProofArtifact
    contract = TurnContract(
        contract_id="contract-specimen-qa",
        turn_id=turn_snap.turn_ref.turn_id,
        execution_id=turn_snap.execution_id,
        declared_goals=["answer"],
        status="fulfilled",
    )
    contract.attach_proof(ProofArtifact(
        proof_id="proof-qa-1",
        claim="answer_grounded_in_observed_excerpt",
        evidence_nodes=[f"{read_disp.artifact.id}@v1"],
        verifier_name="doc_reading_verifier",
        passed=True,
    ))
    reconcil = DeliveryReconciliation(
        reconciliation_id="rcpt-specimen-qa-1",
        turn_id=turn_snap.turn_ref.turn_id,
        execution_id=turn_snap.execution_id,
        status="satisfied",
        matched_proofs=["proof-qa-1"],
        contract=contract,
    )

    resp = AgentResponse(
        answer="Theo Điều 2 trong sổ tay sinh viên 2026, sinh viên được đăng ký tối đa 24 tín chỉ mỗi học kỳ chính và 12 tín chỉ trong học kỳ hè.",
        steps=[step1],
        total_time_ms=185.0,
        tool_call_count=1,
        token_estimate=32,
        sources=handle["observed_sources"],
        artifacts=[read_disp.artifact],
        journal=journal,
        reconciliation=reconcil,
    )
    win._on_assistant_response(handle, resp)
    win._fit_surface()
    pump(8)

    # Specimen 3a: Overview (Sources Top, Result Card with single untruncated answer, no duplicate excerpt)
    win.workbench_scene.overview_scroll.verticalScrollBar().setValue(0)
    pump(4)
    save_specimen(win, "specimen_3a_desktop_light_sources_top_offscreen.png")

    # Specimen 3b: Trace Bottom (Expanded Trace Box)
    win.workbench_scene.trace_expanded = True
    win.workbench_scene.trace_detail_lbl.show()
    win.workbench_scene._sync_trace_ui(
        win.workbench_scene.current_snapshot.trace_entries,
        reasoning_flow=win.workbench_scene.current_snapshot.reasoning_flow,
    )
    win.workbench_scene.overview_scroll.verticalScrollBar().setValue(
        win.workbench_scene.overview_scroll.verticalScrollBar().maximum()
    )
    pump(4)
    save_specimen(win, "specimen_3b_desktop_light_trace_bottom_offscreen.png")

    metadata["specimens"]["desktop_light_trace_qa"] = {
        "file_top": "specimen_3a_desktop_light_sources_top_offscreen.png",
        "file_bottom": "specimen_3b_desktop_light_trace_bottom_offscreen.png",
        "qpa_platform": "offscreen",
        "width": win.width(),
        "height": win.height(),
        "theme": "light",
        "mode": "desktop_grounded_trace_qa",
        "thought_trail_visible": win.workbench_thought_trail.isVisible(),
        "source_count": len(win.workbench_scene.current_snapshot.primary_sources),
        "reasoning_steps": [
            {"number": e.number, "status": e.status, "title": e.title, "detail": e.detail}
            for e in win.workbench_scene.current_snapshot.reasoning_flow
        ],
    }

    # =========================================================================
    # SPECIMEN 4: Desktop Dark (App Disambiguation + Left-aligned unclipped choices)
    # =========================================================================
    win.resize(620, 490)
    win._resize_overlay(620, 490)
    app.setProperty("ratDarkMode", True)
    win.workbench_scene._apply_theme()
    win._apply_theme()

    # Reset and trigger disambiguation turn
    win.workbench_scene.reset(generation=win._chat_generation + 1)
    disambig_query = "mở Liên Minh"
    turn_snap_d = win._conversation.begin_turn(disambig_query)
    win.workbench_scene.begin_turn(
        disambig_query,
        generation=win._chat_generation + 1,
        execution_id=turn_snap_d.execution_id,
        turn_id=turn_snap_d.turn_ref.turn_id,
        artifact_store=win.assistant_runtime.artifact_store,
    )

    # Disambiguation input_request artifact
    input_disp = win.assistant_runtime.dispatcher.execute_operation(
        "open_application",
        {"app_name": "Liên Minh", "query": disambig_query},
        context={"catalog": catalog, "launcher": lambda a: (True, None)},
    )
    win._on_artifact_result(win._chat_generation + 1, input_disp)
    win.workbench_scene._sync_compact_mode()
    win._fit_surface()
    pump(8)
    save_specimen(win, "specimen_4_desktop_dark_disambiguation_offscreen.png")

    metadata["specimens"]["desktop_dark_disambiguation"] = {
        "file": "specimen_4_desktop_dark_disambiguation_offscreen.png",
        "qpa_platform": "offscreen",
        "width": win.width(),
        "height": win.height(),
        "theme": "dark",
        "mode": "desktop_dark_app_disambiguation_trace",
        "thought_trail_visible": win.workbench_thought_trail.isVisible(),
        "candidate_choices": 2,
    }

    meta_json = json.dumps(metadata, indent=2)
    for d in out_dirs:
        (d / "specimens_metadata.json").write_text(meta_json)
    print("Successfully generated all 5 specimens and specimens_metadata.json!")

    win.shutdown()
