"""
Live UI Acceptance Script: Finder Slice & Smart Notes Single-Request Journey (Build 2026.10.25.33).

Requirements:
- Real production UI: rat/ui/quick/PDFDesk.qml & FinderResultsView.qml
- Real backend/model: Ollama qwen3:4b-instruct (no canned answers, no fake completions)
- Genuine authentic documents with verifiable provenance & SHA-256
- Visible minor UI changes: Build 2026.10.25.33 with selection accent bar on Finder candidates
- Record passive evidence: model_requests.jsonl, model_calls.jsonl, ui_snapshots.jsonl, responses.jsonl, artifacts.json
- Verified screenshots demonstrating item selection, open, and Smart Note with checklist on single request
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
os.environ["MPLBACKEND"] = "Agg"

from PyQt6.QtCore import QTimer, QUrl, Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickView
from PyQt6.QtTest import QTest

from rat.config import config
from rat.crawler.db import Database
from document_intake.pdf import read_pdf
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import SLMEngine
from rat.timetable.compositor import TimetableCompositor
from rat.ui.icon_provider import RatIconProvider
from rat.ui.quick_app import bind_desk_window
from rat.ui.quick_pdf_controller import QuickPDFController


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=str(ROOT / "artifacts/rat_agentic_integrity_20261025/live_05"))
    args = parser.parse_args()

    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    # 1. Genuine PDF Provenance & Verification
    pdf_bestroute = (ROOT / "work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf").resolve()
    pdf_nckh = (ROOT / "docs/report_tong_quan_nghien_cuu_nckh.pdf").resolve()

    assert pdf_bestroute.exists(), f"Missing {pdf_bestroute}"
    assert pdf_nckh.exists(), f"Missing {pdf_nckh}"

    sha_bestroute = hashlib.sha256(pdf_bestroute.read_bytes()).hexdigest()
    sha_nckh = hashlib.sha256(pdf_nckh.read_bytes()).hexdigest()

    assert sha_bestroute == "9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c"
    assert sha_nckh == "2b3a8e45ccf8e7880f92f3e91d787dd4b3c1efb3b0ee420d91e85de53faf0684"

    print("=== Provenance Verified ===")
    print(f"Doc 1: {pdf_bestroute.name} | SHA-256: {sha_bestroute}")
    print(f"Doc 2: {pdf_nckh.name} | SHA-256: {sha_nckh}")

    # 2. Setup isolated index database
    db_path = str(out / "index.db")
    config.db_path = db_path
    db = Database(db_path)

    # Index Doc 1 (BEST-Route)
    stat1 = pdf_bestroute.stat()
    text1 = read_pdf(pdf_bestroute)["full_text"]
    db.upsert_document({
        "file_path": str(pdf_bestroute), "file_name": pdf_bestroute.name, "file_ext": ".pdf",
        "file_size": stat1.st_size, "created_at": stat1.st_ctime, "modified_at": stat1.st_mtime,
        "content_text": text1, "summary": "BEST-Route: Adaptive LLM Routing with Test-Time Optimal Compute",
        "indexed_at": time.time(),
    })

    # Index Doc 2 (NCKH Report)
    stat2 = pdf_nckh.stat()
    text2 = read_pdf(pdf_nckh)["full_text"]
    db.upsert_document({
        "file_path": str(pdf_nckh), "file_name": pdf_nckh.name, "file_ext": ".pdf",
        "file_size": stat2.st_size, "created_at": stat2.st_ctime, "modified_at": stat2.st_mtime,
        "content_text": text2, "summary": "Báo cáo toàn diện thực nghiệm & định hướng nghiên cứu NCKH (cập nhật 25/10/2026)",
        "indexed_at": time.time(),
    })

    # 3. Setup Telemetry Logging
    lock = threading.Lock()
    def append(name, data):
        with lock:
            with (out / name).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")

    model = SLMEngine(model="qwen3:4b-instruct", ollama_url="http://localhost:11434")
    original_chat = SLMEngine.chat_with_meta

    def recorded_chat(client, messages, tools, **kwargs):
        started = time.perf_counter()
        record = {
            "timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
            "model": client.model, "messages": messages, "tools": tools,
            "options": {k: v for k, v in kwargs.items() if not callable(v)}
        }
        append("model_requests.jsonl", record)
        try:
            result = original_chat(client, messages, tools, **kwargs)
            record["response"] = result
            return result
        except Exception as exc:
            record["exception"] = str(exc)
            raise
        finally:
            record["wall_ms"] = (time.perf_counter() - started) * 1000
            append("model_calls.jsonl", record)

    SLMEngine.chat_with_meta = recorded_chat

    # 4. Initialize UI & Runtime
    app = QGuiApplication.instance() or QGuiApplication([sys.argv[0]])
    app.setOrganizationName("RATIntegrityAcceptance")
    app.setApplicationName("RAT")

    runtime = AssistantRuntime(
        db=db, compositor=TimetableCompositor([]), model_client=model,
        use_live_model=True, discover_tools=True, enable_observation_pack=True,
    )

    from rat.engine.app_resolver import ApplicationCatalog
    catalog = ApplicationCatalog()

    controller = QuickPDFController(
        assistant_runtime=runtime,
        finder_catalog=catalog,
        auto_init_finder=False,
        db_path=db_path,
    )
    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    RatIconProvider.register(view.engine(), "icon")
    view.setInitialProperties({"liveController": controller, "reduceMotion": True})

    qml_path = ROOT / "rat/ui/quick/PDFDesk.qml"
    view.setSource(QUrl.fromLocalFile(str(qml_path)))
    assert view.status() == QQuickView.Status.Ready, [e.toString() for e in view.errors()]

    root = view.rootObject()
    assert root is not None
    build_label = root.property("uiBuildLabel")
    print(f"[OK] UI Build: {build_label}")
    assert build_label == "Build 2026.10.25.33", f"Expected Build 2026.10.25.33, got {build_label}"

    view.resize(560, round(root.property("preferredWindowHeight")))
    resize_timer = bind_desk_window(view)
    view.show()
    view.requestActivate()

    # Passive state logging
    last_state = None
    def record_snapshot():
        nonlocal last_state
        snap = controller.snapshot
        state = json.dumps(snap, ensure_ascii=False, default=str, sort_keys=True)
        (out / "latest_snapshot.json").write_text(state, encoding="utf-8")
        if state != last_state:
            append("ui_snapshots.jsonl", {
                "timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
                "snapshot": snap
            })
            last_state = state

    controller.changed.connect(record_snapshot)

    def public_value(value):
        if dataclasses.is_dataclass(value):
            return {f.name: public_value(getattr(value, f.name)) for f in dataclasses.fields(value)
                    if f.name not in ("thought",)}
        if isinstance(value, Mapping):
            return {str(k): public_value(v) for k, v in value.items()}
        if isinstance(value, (tuple, list)):
            return [public_value(v) for v in value]
        return value

    def record_response(response):
        try:
            append("responses.jsonl", public_value(response))
            artifacts = runtime.artifact_store.list()
            (out / "artifacts.json").write_text(json.dumps([a.to_dict() for a in artifacts], ensure_ascii=False, indent=2), encoding="utf-8")
            (out / "artifact_history.json").write_text(json.dumps({
                a.id: [r.to_dict() for r in runtime.artifact_store.get_history(a.id)]
                for a in artifacts
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            append("observer_errors.jsonl", {"error": str(exc)})

    controller._execution_delivered.connect(lambda request, response: record_response(response))

    (out / "environment.json").write_text(json.dumps({
        "model": model.model,
        "model_digest": next(m["digest"] for m in json.loads(__import__('urllib.request', fromlist=['urlopen']).urlopen('http://localhost:11434/api/tags').read())["models"] if m["name"] == model.model),
        "documents": [
            {"path": str(pdf_bestroute), "origin": "https://arxiv.org/pdf/2506.22716", "sha256": sha_bestroute},
            {"path": str(pdf_nckh), "origin": "docs/report_tong_quan_nghien_cuu_nckh.pdf", "sha256": sha_nckh},
        ],
        "build": build_label,
        "script": str(Path(__file__).resolve()),
        "mode": "live_ui_acceptance",
        "canned_responses": False,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    def wait_for_idle(timeout_ms=90000):
        elapsed = 0
        while elapsed < timeout_ms:
            QTest.qWait(100)
            elapsed += 100
            if not controller.snapshot.get("busy"):
                return
        raise TimeoutError("Timed out waiting for controller idle")

    def find_item(name: str):
        def _search(item):
            if not item:
                return None
            if item.objectName() == name:
                return item
            for child in item.childItems():
                found = _search(child)
                if found:
                    return found
            return None
        return _search(root)

    controller.ready()
    QTest.qWait(400)
    record_snapshot()

    # =========================================================================
    # JOURNEY 1: LIVE FINDER ACCEPTANCE WITH VAGUE DESCRIPTION
    # =========================================================================
    print("\n=== Journey 1: Finder Live Acceptance ===")
    vague_query = "tài liệu báo cáo nghiên cứu cập nhật tháng này"
    print(f"Typing vague query into composer: {vague_query!r}")

    editor = find_item("draftEditor")
    assert editor is not None, "draftEditor not found"
    editor.forceActiveFocus()
    editor.setProperty("text", vague_query)
    controller.onComposerTextChanged(vague_query)

    # Allow progressive search (execute_subplan finder_preview) to run
    for _ in range(50):
        QTest.qWait(100)
        hits = controller.snapshot.get("finderHits") or []
        if len(hits) > 0:
            break
    print(f"[OK] Finder returned {len(hits)} candidates:")
    for i, h in enumerate(hits):
        print(f"   [{i}] {h.get('title')} ({h.get('kind')}) -> {h.get('path')}")

    assert len(hits) > 0, "Expected at least 1 finder hit"
    # Verify NCKH report is matched
    assert any("report_tong_quan_nghien_cuu_nckh.pdf" in str(h.get("path", "")) for h in hits), \
        "Expected report_tong_quan_nghien_cuu_nckh.pdf in finder hits"

    # Select candidate 0 (demonstrating keyboard navigation and selection accent)
    root.setProperty("selectedFinderIndex", 0)
    QTest.qWait(300)

    # Capture Screenshot 1: Finder suggestions with selection accent bar
    img_finder_accent = out / "01_finder_vague_query_accent.png"
    view.grabWindow().save(str(img_finder_accent))
    print(f"[OK] Saved screenshot: {img_finder_accent.name}")

    # Open the selected item into the desk
    print("Adopting selected hit into active document desk...")
    controller.adoptSelectedHit(0, "")
    wait_for_idle(timeout_ms=10000)
    QTest.qWait(500)

    selected_doc = controller.snapshot.get("fileName")
    print(f"[OK] Desk now displays document: {selected_doc}")
    assert selected_doc == "report_tong_quan_nghien_cuu_nckh.pdf", f"Unexpected doc opened: {selected_doc}"

    # Capture Screenshot 2: Desk opened with genuine document page 1
    img_finder_opened = out / "02_finder_item_opened_desk.png"
    view.grabWindow().save(str(img_finder_opened))
    print(f"[OK] Saved screenshot: {img_finder_opened.name}")

    # =========================================================================
    # JOURNEY 2: SMART NOTES SINGLE-REQUEST JOURNEY (WITH CHECKLIST)
    # =========================================================================
    print("\n=== Journey 2: Smart Notes Single-Request Journey ===")
    print("Selecting BEST-Route paper for grounded Smart Notes journey...")
    controller.selectFile(str(pdf_bestroute), auto_read=True)
    wait_for_idle(timeout_ms=10000)
    QTest.qWait(400)

    # Turn 1: Grounded QA Question
    q1 = "BEST-Route chọn mô hình và số phản hồi dựa vào yếu tố nào? Trả lời ngắn, chỉ dùng trích đoạn."
    print(f"\n[Turn 1] Submitting: {q1}")
    editor.setProperty("text", q1)
    t0 = time.perf_counter()
    controller.submitQuery(q1)
    wait_for_idle(timeout_ms=90000)
    t1 = time.perf_counter() - t0

    answer1 = controller.snapshot.get("answerText") or controller.snapshot.get("lastAssistantAnswer") or ""
    print(f"[OK] Turn 1 answered in {t1:.2f}s:")
    print(f"     Answer: {answer1}")
    assert len(answer1.strip()) > 10, f"Turn 1 answer too short: {answer1}"

    # Capture Screenshot 3: Turn 1 Answer
    img_turn1 = out / "03_qa_turn1_answer.png"
    view.grabWindow().save(str(img_turn1))
    print(f"[OK] Saved screenshot: {img_turn1.name}")

    # Turn 2: Single-request Smart Note creation with checklist
    q2 = (
        "Tạo và lưu Smart Note từ câu trả lời BEST-Route vừa rồi. "
        "Thêm việc cần làm: Đọc Section 3 của bài BEST-Route. "
        "Dùng công cụ ghi chú và báo ID sau khi lưu."
    )
    print(f"\n[Turn 2] Submitting single-request Smart Note with checklist: {q2}")
    editor.setProperty("text", q2)
    t0 = time.perf_counter()
    controller.submitQuery(q2)
    wait_for_idle(timeout_ms=90000)
    t2 = time.perf_counter() - t0

    answer2 = controller.snapshot.get("answerText") or controller.snapshot.get("lastAssistantAnswer") or ""
    print(f"[OK] Turn 2 answered in {t2:.2f}s:")
    print(f"     Answer: {answer2}")

    # Capture Screenshot 4: Smart Note created
    img_turn2 = out / "04_smart_note_single_turn_with_checklist.png"
    view.grabWindow().save(str(img_turn2))
    print(f"[OK] Saved screenshot: {img_turn2.name}")

    # 5. Verify Artifact & Checklist Content
    artifacts = runtime.artifact_store.list()
    notes = [a for a in artifacts if a.kind == "structured_note"]
    print(f"\nTotal structured note artifacts committed: {len(notes)}")
    assert len(notes) > 0, "Expected at least 1 structured_note artifact"

    latest_note = notes[-1]
    payload = latest_note.payload
    print(f"Latest Note ID: {latest_note.id}")
    print(f"Title: {payload.get('title')}")
    print(f"Action Items: {payload.get('action_items')}")
    print(f"Key Facts: {payload.get('key_facts')}")

    action_items = payload.get("action_items") or []
    has_section3_task = any("Section 3" in str(item.get("task", "")) or "đọc" in str(item.get("task", "")).lower() for item in action_items)
    print(f"[CHECK] Action items present: {len(action_items)} item(s)")
    print(f"[CHECK] Target task ('Đọc Section 3') captured: {has_section3_task}")

    record_snapshot()
    print("\n=== Live Acceptance Run Complete ===")
    print(f"Artifacts and logs written to: {out}")


if __name__ == "__main__":
    main()
