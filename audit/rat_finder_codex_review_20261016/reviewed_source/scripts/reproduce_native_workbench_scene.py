import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure scene flag is explicitly enabled
os.environ["RAT_WORKBENCH_SCENE"] = "1"
os.environ["RAT_REDUCE_MOTION"] = "1"

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

app = QApplication.instance() or QApplication([])

def get_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()

def get_git_info() -> dict:
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
    except Exception as e:
        head, branch = str(e), "unknown"
    return {"head": head, "branch": branch}

out_dir = Path("docs/evidence/rat_workbench_native")
out_dir.mkdir(parents=True, exist_ok=True)

relevant_files = [
    Path("rat/ui/workbench_scene.py"),
    Path("rat/ui/workbench.py"),
    Path("rat/ui/omnibar.py"),
    Path("rat/ui/surface_layout.py"),
    Path("rat/ui/theme.py"),
    Path("rat/ui/view_renderer.py"),
    Path("rat/ui/assistant_presenter.py"),
    Path("rat/engine/progressive_search.py"),
    Path("rat/engine/app_resolver.py"),
    Path("tests/test_workbench_scene.py"),
]
file_hashes = {str(f): get_file_sha256(f) for f in relevant_files if f.exists()}

git_info = get_git_info()
meta = {
    "execution_type": "native Qt fixture replay/widget capture",
    "disclaimer": (
        "Uses Cocoa Qt with patched worker, injected events, and QWidget.grab(); "
        "does not capture WindowServer framebuffer or establish real model execution; "
        "native IME text input composition remains unverified by automated setText()."
    ),
    "pid": os.getpid(),
    "timestamp_iso": datetime.now(timezone.utc).isoformat(),
    "platform": {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python_version": sys.version,
        "qpa_platform": app.platformName(),
    },
    "git": git_info,
    "source_hashes": file_hashes,
    "specimens": {},
}

print("=== NATIVE QT FIXTURE REPLAY / WIDGET CAPTURE ===")
print(f"PID: {meta['pid']}")
print(f"Timestamp: {meta['timestamp_iso']}")
print(f"Platform: {meta['platform']['system']} {meta['platform']['release']} ({meta['platform']['machine']})")
print(f"QPA: {meta['platform']['qpa_platform']}")
print(f"Git HEAD: {meta['git']['head']} (branch: {meta['git']['branch']})")


with patch("rat.ui.assistant_worker.AssistantWorker.start"), \
     patch("rat.ui.omnibar.Database") as mock_db, \
     patch("rat.ui.omnibar.SearchEngine") as mock_eng, \
     patch("rat.ui.feedback.FeedbackLog"), \
     patch("rat.engine.slm.slm_engine.is_service_running", return_value=False):

    mock_db.return_value.get_stats.return_value = {"total_files": 0}
    mock_db.return_value.get_recent_documents.return_value = []
    
    from rat.ui.omnibar import OmnibarWindow
    from rat.engine.assistant_runtime import AgentResponse, AgentStep

    win = OmnibarWindow()
    win._apply_assistant_model = lambda: None
    win.show()
    win.switch_section(0)
    for _ in range(5):
        app.processEvents()

    # Journey 1: Real file on disk
    tmp = Path(tempfile.mkdtemp())
    real_doc = tmp / "so_tay_sinh_vien_2026.txt"
    real_doc.write_text(
        "Điều 1: Đăng ký học phần theo tín chỉ.\n"
        "Điều 2: Sinh viên được đăng ký tối đa 24 tín chỉ mỗi học kỳ chính và 12 tín chỉ học kỳ hè.\n"
        "Điều 3: Rút học phần thực hiện trước tuần thứ 6.",
        encoding="utf-8"
    )
    win.assistant_runtime.db = MagicMock()
    win.assistant_runtime.db.get_document_by_path.side_effect = lambda p: {"file_path": str(real_doc), "file_name": real_doc.name} if p == str(real_doc) else None
    ctx = {"db": win.assistant_runtime.db, "compositor": win.assistant_runtime.compositor}
    read_dispatch = win.assistant_runtime.dispatcher.execute_operation("read_document", {"file_path": str(real_doc), "max_chars": 3000}, context=ctx)

    query = "Học kỳ chính được đăng ký tối đa bao nhiêu tín chỉ?"
    turn_snap = win._conversation.begin_turn(query)
    handle = win.chat_stream.create_streaming_message(strategy="Assistant", badge="Đang xử lý", turn_id=turn_snap.turn_ref.turn_id)
    handle["generation"] = win._chat_generation
    handle["turn_ref"] = turn_snap.turn_ref
    handle["execution_id"] = turn_snap.execution_id
    handle["observed_sources"] = []
    win._assistant_handle = handle
    win._pending_chat_query = query
    win._show_interaction_surface()
    win.workbench_scene.begin_turn(query, generation=win._chat_generation, execution_id=turn_snap.execution_id, turn_id=turn_snap.turn_ref.turn_id, artifact_store=win.assistant_runtime.artifact_store)

    step1 = AgentStep(step_number=1, thought="t1", tool_name="search_documents", tool_result=[{"path": str(real_doc), "filename": real_doc.name, "snippet": "Điều 2: Sinh viên được đăng ký tối đa 24 tín chỉ..."}])
    win._on_assistant_step(handle, step1)
    step2 = AgentStep(step_number=2, thought="t2", tool_name="read_document", tool_result=read_dispatch.result, artifacts=[read_dispatch.artifact])
    win._on_assistant_step(handle, step2)

    resp = AgentResponse(
        answer="Theo Điều 2 trong sổ tay sinh viên 2026, sinh viên được đăng ký tối đa 24 tín chỉ mỗi học kỳ chính và 12 tín chỉ trong học kỳ hè.",
        steps=[step1, step2],
        total_time_ms=150.0,
        tool_call_count=2,
        token_estimate=38,
        sources=handle["observed_sources"],
        artifacts=[read_dispatch.artifact],
    )
    win._on_assistant_response(handle, resp)
    win._fit_surface()
    for _ in range(10):
        app.processEvents()

    # Step A: Overview
    p1 = out_dir / "native_scene_overview.png"
    win.grab().save(str(p1))
    meta["specimens"]["overview"] = {"path": str(p1), "width": win.width(), "height": win.height()}
    print(f"Captured native overview: {p1} ({win.width()}x{win.height()})")

    # Step B: Source drilldown
    src_id = win.workbench_scene.current_snapshot.primary_sources[0].node_id
    win.workbench_scene.select_source(src_id)
    win._fit_surface()
    for _ in range(10):
        app.processEvents()
    assert win.workbench_scene.mode == "source_detail"
    p2 = out_dir / "native_scene_source_detail.png"
    win.grab().save(str(p2))
    meta["specimens"]["source_detail"] = {"path": str(p2), "width": win.width(), "height": win.height()}
    print(f"Captured native source detail: {p2} ({win.width()}x{win.height()})")

    # Step C: Back to overview
    win.workbench_scene.show_overview()
    for _ in range(5):
        app.processEvents()
    assert win.workbench_scene.mode == "overview"

    # Step D: Revision update
    dispatcher = win.assistant_runtime.dispatcher
    store = win.assistant_runtime.artifact_store
    natal_v1 = dispatcher.execute_operation(
        "create_natal_chart",
        {"name": "Nguyễn Văn A", "date": "2000-01-01", "time": "08:00", "place": "TP Hồ Chí Minh", "latitude": 10.8231, "longitude": 106.6297, "timezone": "Asia/Ho_Chi_Minh"}
    )
    table_v1 = dispatcher.execute_operation(
        "compose_result_table",
        {"title": "Bảng tổng hợp hồ sơ", "headers": ["Tiêu đề", "Giờ sinh"], "rows": [[{"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "title"}, {"artifact_id": natal_v1.artifact.id, "revision": 1, "field": "chart.birth.time"}]]},
        context={"artifact_store": store}
    )
    win._on_artifact_result(win._chat_generation, natal_v1)
    win._on_artifact_result(win._chat_generation, table_v1)
    actions = win.assistant_runtime.registry.actions_for(natal_v1.artifact)
    edit_action = next(a for a in actions if a.operation_name == "update_birth_data")
    natal_v2 = dispatcher.dispatch(edit_action, {"time": "09:30"}, win._artifact_context())
    win._on_artifact_result(win._chat_generation, natal_v2)
    win._fit_surface()
    for _ in range(10):
        app.processEvents()
    p3 = out_dir / "native_scene_revision_update.png"
    win.grab().save(str(p3))
    meta["specimens"]["revision_update"] = {"path": str(p3), "width": win.width(), "height": win.height()}
    print(f"Captured native revision update: {p3} ({win.width()}x{win.height()})")

    # Step E: Active stopped turn
    query2 = "Tính toán thêm số tín chỉ còn nợ?"
    turn_snap2 = win._conversation.begin_turn(query2)
    handle2 = win.chat_stream.create_streaming_message(strategy="Assistant", badge="Đang xử lý", turn_id=turn_snap2.turn_ref.turn_id)
    handle2["generation"] = win._chat_generation
    handle2["turn_ref"] = turn_snap2.turn_ref
    handle2["execution_id"] = turn_snap2.execution_id
    handle2["observed_sources"] = []
    win._assistant_handle = handle2
    win._pending_chat_query = query2
    mock_worker = MagicMock()
    win._current_reasoner = mock_worker
    win.workbench_scene.begin_turn(query2, generation=win._chat_generation, execution_id=turn_snap2.execution_id, turn_id=turn_snap2.turn_ref.turn_id, artifact_store=win.assistant_runtime.artifact_store)

    step_cancel = AgentStep(step_number=1, thought="Đang tìm kiếm thông tin phụ...", tool_name="search_documents")
    win._on_assistant_step(handle2, step_cancel)
    for _ in range(5):
        app.processEvents()

    win._cancel_assistant()
    assert mock_worker.requestInterruption.called
    assert win.workbench_scene.current_snapshot.phase == "cancelled"
    assert len(win.workbench_scene.current_snapshot.primary_sources) >= 1

    late_step = AgentStep(step_number=2, thought="Late step", tool_name="search_documents")
    win._on_assistant_step(handle2, late_step)
    assert win.workbench_scene.current_snapshot.phase == "cancelled"

    win._fit_surface()
    for _ in range(10):
        app.processEvents()
    p4 = out_dir / "native_scene_stopped.png"
    win.grab().save(str(p4))
    meta["specimens"]["stopped"] = {"path": str(p4), "width": win.width(), "height": win.height()}
    print(f"Captured native stopped: {p4} ({win.width()}x{win.height()})")

    # Step F: Narrow mode
    win.resize(420, 560)
    win._resize_overlay(420, 560)
    win._fit_surface()
    for _ in range(10):
        app.processEvents()
    assert win.width() <= 450
    assert win._is_narrow() is True
    scene = win.workbench_scene
    scene.overview_scroll.ensureWidgetVisible(scene.result_card)
    for _ in range(5):
        app.processEvents()
    p5 = out_dir / "native_scene_narrow.png"
    win.grab().save(str(p5))
    meta["specimens"]["narrow"] = {"path": str(p5), "width": win.width(), "height": win.height()}
    print(f"Captured native narrow: {p5} ({win.width()}x{win.height()})")

    # Step G: Dark mode
    win.resize(684, 560)
    win._resize_overlay(684, 560)
    app.setProperty("ratDarkMode", True)
    win._apply_theme()
    win._fit_surface()
    for _ in range(10):
        app.processEvents()
    p6 = out_dir / "native_scene_dark.png"
    win.grab().save(str(p6))
    meta["specimens"]["dark"] = {"path": str(p6), "width": win.width(), "height": win.height()}
    print(f"Captured native dark: {p6} ({win.width()}x{win.height()})")

    # Step H: Progressive finder suggestions & thought bubble
    app.setProperty("ratDarkMode", False)
    win._apply_theme()
    win._reset_chat()
    for _ in range(5):
        app.processEvents()

    from rat.crawler.db import Database
    from rat.engine.progressive_search import ProgressiveSearch, SearchCoordinator
    from rat.engine.app_resolver import ApplicationCatalog
    finder_db_file = tmp / "finder_demo.db"
    f_db = Database(str(finder_db_file))
    f_db.upsert_document(dict(
        file_path=str(real_doc),
        file_name="so_tay_sinh_vien_2026.txt",
        file_ext=".txt",
        file_size=len(real_doc.read_text()),
        created_at=1, modified_at=10, indexed_at=1,
        content_text=real_doc.read_text(),
        summary="Sổ tay sinh viên 2026: Đăng ký học phần theo tín chỉ",
    ))
    demo_catalog = ApplicationCatalog([], {})
    win.workbench_finder_enabled = True
    win._finder_catalog = demo_catalog
    win._finder_search = ProgressiveSearch(str(finder_db_file), catalog=demo_catalog)
    win._finder_coordinator = SearchCoordinator(
        win._finder_search,
        on_update=lambda snap: win._finder_bridge.snapshot_ready.emit(snap),
    )
    # Put companion in working state to display thought bubble
    win.set_mascot_state("working")
    win.chat_composer_input.setText("sinh viên")
    for _ in range(30):
        app.processEvents()
        if win.workbench_scene.finder_box.isVisible():
            break
        QTest.qWait(20)

    win.resize(620, 420)
    win._resize_overlay(620, 420)
    win._fit_surface()
    for _ in range(10):
        app.processEvents()
    p7 = out_dir / "native_scene_finder_suggestions.png"
    win.grab().save(str(p7))
    meta["specimens"]["finder_suggestions"] = {"path": str(p7), "width": win.width(), "height": win.height()}
    print(f"Captured native finder suggestions: {p7} ({win.width()}x{win.height()})")

    win.shutdown()

session_file = out_dir / "native_scene_session.json"
session_file.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Saved session metadata to {session_file}")
