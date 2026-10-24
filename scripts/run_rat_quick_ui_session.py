"""Observe a real native RAT session; all user actions go through the desktop.

No model doubles, transcript replay, automatic submissions or personal indexing.
Choose the --pdf through the app's file picker. Control-R reloads QML at idle
(tested on macOS); the controller, conversation and model remain alive.
Control-Shift-S captures the window. This runner never manages the Ollama daemon.
Read manifest.json for compact progress; raw requests/responses stay in files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_KEYS = {"thinking", "reasoning", "reasoning_content"}


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def public_data(value):
    if isinstance(value, dict):
        return {key: public_data(item) for key, item in value.items() if key not in PRIVATE_KEYS}
    if isinstance(value, list):
        return [public_data(item) for item in value]
    return value


def fingerprint(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_hashes():
    paths = list((ROOT / "rat/ui/quick").rglob("*.qml"))
    paths += [ROOT / name for name in (
        "rat/ui/quick_pdf_controller.py", "rat/ui/quick_app.py", "rat/ui/chat_session.py",
        "rat/ui/answer_presentation.py", "rat/ui/assistant_worker.py", "rat/ui/icon_provider.py",
        "rat/ui/pdf_snapshot_provider.py",
        "rat/engine/assistant_runtime.py", "rat/engine/selected_document_qa.py",
        "rat/engine/selected_pdf.py", "rat/engine/slm.py", "rat/engine/http_transport.py",
        "rat/engine/app_resolver.py",
        "rat/kernel/capabilities/documents.py", "scripts/run_rat_quick_ui_session.py",
        "scripts/record_ui.py",
    )]
    return {str(path.relative_to(ROOT)): fingerprint(path) for path in sorted(paths)}


def python_changes(before, after):
    return sorted(name for name in before.keys() | after.keys()
                  if name.endswith(".py") and before.get(name) != after.get(name))


class CallLedger:
    """Reserve before HTTP starts, including failed/in-flight attempts in the cap."""

    def __init__(self, output, limit):
        if limit < 0:
            raise ValueError("max_model_calls_must_be_nonnegative")
        self.output, self.limit = output, limit
        self.records = []
        self.lock = threading.Lock()

    def begin(self, model, messages, tools):
        with self.lock:
            if len(self.records) >= self.limit:
                raise RuntimeError("live_ui_model_call_budget_exhausted")
            record = {"id": len(self.records) + 1, "model": model,
                      "started_unix": time.time(), "state": "in_progress",
                      "messages": public_data(messages), "tools": public_data(tools)}
            self.records.append(record)
            write_json(self.output / "model-calls.json", self.records)
            return record["id"]

    def finish(self, call_id, result):
        with self.lock:
            record = self.records[call_id - 1]
            record.update(state="finished", finished_unix=time.time(), result=public_data(result))
            write_json(self.output / "model-calls.json", self.records)

    def summary(self):
        with self.lock:
            return [{"id": record["id"], "state": record["state"],
                     **{key: record.get("result", {}).get(key) for key in
                        ("error", "duration_ms", "prompt_tokens", "completion_tokens", "token_usage_known")}}
                    for record in self.records]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory; never overwrite a run")
    parser.add_argument("--pdf", type=Path, required=True, help="Genuine source; select it through the UI")
    parser.add_argument("--origin", required=True, help="Source URL or documented local origin")
    parser.add_argument("--model", default="qwen3:4b-instruct")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--max-model-calls", type=int, default=2)
    parser.add_argument("--label", default="UI iteration")
    parser.add_argument("--session-seconds", type=int, default=1800)
    parser.add_argument("--system-apps", action="store_true",
                        help="Read real .app metadata in /Applications and /System/Applications only")
    parser.add_argument("--record-desktop", action="store_true",
                        help="Record full desktop video during the session via macOS screencapture")
    parser.add_argument("--no-walkthrough", action="store_true",
                        help="Skip automatic walkthrough video generation from screenshots on close")
    parser.add_argument("--scenario", choices=["finder-suggestions", "chatbox-pdf-snapshot"], default=None,
                        help="Run an automated desktop acceptance scenario on the native window")
    args = parser.parse_args(argv)
    if args.max_model_calls < 0 or args.session_seconds < 1:
        parser.error("Invalid model budget/session duration")
    parsed = urllib.parse.urlparse(args.ollama_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Only local Ollama is supported; no document data may leave this runner")
    args.pdf = args.pdf.expanduser().resolve(strict=True)
    with args.pdf.open("rb") as source:
        if args.pdf.suffix.lower() != ".pdf" or source.read(5) != b"%PDF-":
            parser.error("Expected an existing genuine PDF")
    args.output_dir = args.output_dir.expanduser().resolve()
    if args.output_dir.exists():
        parser.error("Output directory already exists; preserve raw artifacts")
    # Read-only preflight; never pull a model or start/stop an unowned service.
    if args.max_model_calls > 0:
        with urllib.request.urlopen(args.ollama_url.rstrip("/") + "/api/tags", timeout=5) as reply:
            args.model_identity = json.load(reply)
        if args.model not in {item.get("name") for item in args.model_identity.get("models", [])}:
            parser.error("Requested model is not installed")
    else:
        try:
            with urllib.request.urlopen(args.ollama_url.rstrip("/") + "/api/tags", timeout=1) as reply:
                args.model_identity = json.load(reply)
        except Exception:
            args.model_identity = {"models": [{"name": args.model}], "note": "max_model_calls_zero_offline"}
    return args


def main(argv=None):
    args = parse_args(argv)
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    (output / "screenshots").mkdir()
    os.environ["RAT_STATE_DIR"] = str(output / "isolated-state")
    os.environ["RAT_DB_PATH"] = str(output / "isolated-state/rat_index.db")
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    sys.path.insert(0, str(ROOT))
    from PyQt6.QtCore import QCoreApplication, QEvent, QPointF, QTimer, QUrl, Qt
    from PyQt6.QtGui import QFont, QKeySequence, QShortcut
    from PyQt6.QtQml import QQmlEngine
    from PyQt6.QtQuick import QQuickItem, QQuickView, QQuickWindow
    from PyQt6.QtWidgets import QApplication
    from rat.engine.slm import SLMEngine
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.ui.quick_pdf_controller import QuickPDFController
    from rat.ui.quick_app import bind_desk_close, bind_desk_window
    from rat.ui.icon_provider import RatIconProvider

    ledger = CallLedger(output, args.max_model_calls)

    class ObservedModel(SLMEngine):
        def chat_with_meta(self, messages, tools, **kwargs):
            call_id = ledger.begin(self.model, messages, tools)
            try:
                result = super().chat_with_meta(messages, tools, **kwargs)
            except Exception as exc:
                ledger.finish(call_id, {"error": type(exc).__name__, "error_detail": str(exc)})
                raise
            ledger.finish(call_id, result)
            return result

        def close(self):
            pass  # HTTP resources are owned per request, not by this observer.

    app = QApplication([])
    app.setFont(QFont("Helvetica Neue", 13))
    if app.platformName() in {"offscreen", "minimal"}:
        raise RuntimeError("Native desktop required; do not label offscreen rendering as acceptance")
    model = ObservedModel(args.ollama_url, args.model)
    runtime = AssistantRuntime(model_client=model, discover_tools=True)
    runtime.document_model_client = model
    catalog = None
    if args.system_apps:
        from rat.engine.app_resolver import ApplicationCatalog
        app_roots = ("/Applications", "/System/Applications")
        catalog = ApplicationCatalog.scan(roots=app_roots, use_cache=False)
        write_json(output / "application-catalog.json", {
            "roots": app_roots, "issues": catalog.issues,
            "applications": [{"name": item.name, "path": item.path, "bundle_id": item.bundle_id}
                             for item in catalog.applications],
            "scope": "Real application metadata only; no personal-file indexing",
        })
    def handle_open_url(url):
        event("open_url", url=url.toString())
        return True

    controller = QuickPDFController(assistant_runtime=runtime, auto_init_finder=False,
                                    finder_catalog=catalog, open_url=handle_open_url)
    QQmlEngine.setObjectOwnership(controller, QQmlEngine.ObjectOwnership.CppOwnership)
    controller.copyReady.connect(app.clipboard().setText)
    controller.copyReady.connect(lambda text: (output / "copied-source.txt").write_text(text, encoding="utf-8"))
    QQuickWindow.setDefaultAlphaBuffer(True)
    view = QQuickView()
    view.setColor(Qt.GlobalColor.transparent)
    view.setFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    view.setTitle("RAT · " + args.label)
    RatIconProvider.register(view.engine(), "icon")
    state = {"revision": 0, "captures": [], "reloads": [], "warnings": [],
             "closed": False, "source_versions": [], "last_transition": None}
    timers = []
    captured = set()
    root = None
    provenance = {"path": str(args.pdf), "origin": args.origin, "sha256": fingerprint(args.pdf)}
    write_json(output / "document-provenance.json", provenance)
    write_json(output / "model-identity.json", args.model_identity)

    def event(kind, **data):
        with (output / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"at": time.time(), "kind": kind, **data}, ensure_ascii=False, default=str) + "\n")

    def editor():
        return root.findChild(QQuickItem, "draftEditor") if root is not None else None

    def checkpoint():
        draft = editor()
        turns = [turn.to_dict() for turn in controller.conversation.turns()]
        return {"conversation_id": controller.conversation.conversation_id,
                "conversation_sha256": hashlib.sha256(json.dumps(turns, sort_keys=True, default=str).encode()).hexdigest(),
                "draft": draft.property("text") if draft else "",
                "cursor": draft.property("cursorPosition") if draft else 0,
                "editor_focused": bool(draft and draft.property("activeFocus")),
                "snapshot": controller.snapshot, "model_calls": len(ledger.summary())}

    def save():
        turns = [turn.to_dict() for turn in controller.conversation.turns()]
        write_json(output / "conversation.json", turns)
        text = "# Hội thoại thật qua native RAT UI\n\n"
        for turn in turns:
            text += f"## Bạn\n\n{turn['query']}\n\n## Chuột\n\n{turn['answer']}\n\nTrạng thái: {turn['status']}\n\n"
        (output / "conversation.md").write_text(text, encoding="utf-8")
        snap = controller.snapshot
        write_json(output / "latest-snapshot.json", snap)
        write_json(output / "manifest.json", {
            "label": args.label, "native_platform": app.platformName(), "revision": state["revision"],
            "pdf": provenance, "model": args.model, "max_model_calls": args.max_model_calls,
            "calls": ledger.summary(), "view": snap["view"], "busy": snap["busy"],
            "turn_id": snap["turnId"], "status": snap["status"], "answer_excerpt": snap["answerExcerpt"],
            "verification": snap["answerVerification"], "captures": state["captures"],
            "reloads": state["reloads"], "qml_warnings": state["warnings"],
            "source_versions": [{"revision": item["revision"], "at": item["at"]}
                                for item in state["source_versions"]],
            "source_hashes_file": "source-versions.json", "closed": state["closed"],
            "walkthrough_mp4": "walkthrough.mp4" if (output / "walkthrough.mp4").exists() else None,
            "walkthrough_gif": "walkthrough.gif" if (output / "walkthrough.gif").exists() else None,
            "desktop_recording": "desktop-recording.mov" if (output / "desktop-recording.mov").exists() else None,
            "acceptance_scope": "Observed local UI session; no automatic semantic grading or Stage 0 claim",
        })

    def capture(manual=False, attempt=0):
        if state["closed"] or not view.isVisible() or root is None:
            return
        snap = controller.snapshot
        key = (state["revision"], snap["turnId"], snap["view"], snap["expanded"])
        if not manual and key in captured:
            return
        wanted = min(round(root.property("preferredWindowHeight")), view.screen().availableGeometry().height() - 32)
        paper = root.findChild(QQuickItem, "resultPaper")
        paper_top = paper.mapToScene(QPointF(0, 0)).y() if paper is not None else 0
        clear_frame = abs(view.height() - wanted) <= 2 and (not snap["expanded"] or paper_top >= 0)
        if not clear_frame and attempt < 8:
            # Wait for the production window-fit timer and a new rendered frame.
            # Do not resize outside the production fit rules to hide a layout bug.
            if timers:
                timers[0].start(0)
            view.requestUpdate()
            QTimer.singleShot(100, lambda: capture(manual, attempt + 1))
            return
        captured.add(key)
        name = f"r{state['revision']:02d}-{len(state['captures']) + 1:02d}-{snap['view']}-{'full' if snap['expanded'] else 'min'}.png"
        if not view.grabWindow().save(str(output / "screenshots" / name)):
            event("capture_failed", file=name)
            return
        label = root.findChild(QQuickItem, "minAnswerExcerpt")
        state["captures"].append({"file": "screenshots/" + name, "at": time.time(),
            "revision": state["revision"], "turn_id": snap["turnId"], "view": snap["view"],
            "expanded": snap["expanded"], "busy": snap["busy"], "status": snap["status"],
            "min_label": label.property("text") if label else "",
            "clear_frame": clear_frame, "window_height": view.height(),
            "preferred_height": wanted, "paper_top": paper_top,
            "calls_started": len(ledger.summary()),
            "disk_matches_loaded_source": source_hashes() == state["source_versions"][-1]["hashes"]})
        if not clear_frame:
            event("capture_partial", file=name, window_height=view.height(),
                  preferred_height=wanted, paper_top=paper_top)
        save()

    def changed():
        snap = controller.snapshot
        transition = {key: snap[key] for key in ("view", "busy", "expanded", "turnId", "executionId", "status")}
        if transition != state["last_transition"]:
            state["last_transition"] = transition
            event("ui", revision=state["revision"], **transition)
        save()
        # Coalesce signals; each revision/turn/view/mode gets one automatic image.
        QTimer.singleShot(300, capture)

    def load_qml(saved=None):
        nonlocal root
        hashes = source_hashes()
        view.setInitialProperties({"liveController": controller, "reduceMotion": True,
            "darkMode": saved["darkMode"] if saved else False,
            "mascotSource": QUrl.fromLocalFile(str(ROOT / "rat/assets/rat_mascot_cutout.png"))})
        view.setSource(QUrl.fromLocalFile(str(ROOT / "rat/ui/quick/PDFDesk.qml")))
        if view.status() != QQuickView.Status.Ready:
            raise RuntimeError("qml_load_failed: " + "; ".join(item.toString() for item in view.errors()))
        root = view.rootObject()
        state["revision"] += 1
        state["source_versions"].append({"revision": state["revision"], "at": time.time(), "hashes": hashes})
        write_json(output / "source-versions.json", state["source_versions"])
        if saved:
            for key, value in saved["properties"].items():
                root.setProperty(key, value)
            draft = editor()
            draft.setProperty("text", saved["checkpoint"]["draft"])
            draft.setProperty("cursorPosition", saved["checkpoint"]["cursor"])
            if saved["checkpoint"]["editor_focused"]:
                draft.forceActiveFocus()
        root.moveRequested.connect(view.startSystemMove)
        root.expandedChanged.connect(changed)
        root.darkModeChanged.connect(lambda: QTimer.singleShot(300, lambda: capture(True)))
        timers.extend((bind_desk_window(view), bind_desk_close(view, controller)))

    def reload_qml():
        nonlocal root
        if controller.snapshot["busy"] or controller._execution_workers:
            event("reload_refused", reason="request_or_worker_still_running")
            print('{"reload":"refused_busy"}', flush=True)
            return
        changed_python = python_changes(state["source_versions"][-1]["hashes"], source_hashes())
        if changed_python:
            event("reload_refused", reason="python_changed_restart_required", files=changed_python)
            print('{"reload":"restart_required"}', flush=True)
            return
        before = checkpoint()
        saved = {"checkpoint": before, "darkMode": root.property("darkMode"),
                 "properties": {key: root.property(key) for key in
                    ("answerSourcesOpen", "answerQuestionOpen", "sourceOpen", "logOpen")}}
        for timer in timers:
            timer.stop()
            timer.deleteLater()
        timers.clear()
        root = None
        view.setSource(QUrl())
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        view.engine().clearComponentCache()
        try:
            load_qml(saved)
        except Exception as exc:
            event("reload_failed", error=str(exc))
            state["closed"] = True
            save()
            app.exit(1)
            return
        after = checkpoint()
        record = {"revision": state["revision"], "at": time.time(),
                  "preserved": before == after, "before": before, "after": after}
        write_json(output / f"reload-r{state['revision']:02d}.json", record)
        state["reloads"].append({key: record[key] for key in ("revision", "at", "preserved")})
        event("reloaded", revision=state["revision"], preserved=record["preserved"])
        save()
        QTimer.singleShot(300, capture)
        print(json.dumps({"reload": state["revision"], "preserved": record["preserved"]}), flush=True)

    def warnings(items):
        state["warnings"].extend(item.toString() for item in items)
        event("qml_warning", messages=[item.toString() for item in items])

    view.engine().warnings.connect(warnings)
    load_qml()
    def capture_desktop():
        dt_name = f"desktop-r{state['revision']:02d}-{len(state['captures']) + 1:02d}-{int(time.time())}.png"
        dt_path = output / "screenshots" / dt_name
        try:
            from scripts.record_ui import take_screenshot
            take_screenshot(dt_path)
            event("desktop_screenshot", file="screenshots/" + dt_name)
        except Exception as exc:
            event("desktop_screenshot_failed", error=str(exc))

    view.resize(520, round(root.property("preferredWindowHeight")))
    view.setPosition(150, 350)
    shortcuts = []
    for key, callback in (("Ctrl+R", reload_qml), ("Meta+R", reload_qml),
                          ("Ctrl+Shift+S", lambda: capture(True)), ("Meta+Shift+S", lambda: capture(True)),
                          ("Ctrl+Shift+D", capture_desktop), ("Meta+Shift+D", capture_desktop)):
        shortcut = QShortcut(QKeySequence(key), view)
        shortcut.activated.connect(callback)
        shortcuts.append(shortcut)
    controller.changed.connect(changed)
    controller.ready()
    view.show()
    QTimer.singleShot(300, capture)
    expiry = QTimer(view)
    expiry.setSingleShot(True)
    expiry.timeout.connect(lambda: view.rootObject().closeRequested.emit() if root is not None else app.quit())
    expiry.start(args.session_seconds * 1000)

    desktop_recording_proc = None
    if args.record_desktop:
        dt_rec_path = output / "desktop-recording.mov"
        try:
            desktop_recording_proc = subprocess.Popen([
                "/usr/sbin/screencapture", "-v", "-k", "-C", str(dt_rec_path)
            ])
            event("desktop_recording_started", file="desktop-recording.mov")
        except Exception as exc:
            event("desktop_recording_start_failed", error=str(exc))

    if args.scenario == "finder-suggestions":
        def run_finder_suggestions_scenario():
            def step1():
                ed = editor()
                if ed is None:
                    return
                event("scenario_step", step="type_query", query="pro")
                ed.setProperty("text", "pro")
                QTimer.singleShot(400, step2)

            def step2():
                snap = controller.snapshot
                event("scenario_step", step="suggestions_shown", hits=len(snap.get("finderHits", [])))
                capture(manual=True)
                QTimer.singleShot(500, step3)

            def step3():
                see_more = root.findChild(QQuickItem, "seeMoreFinderHits")
                if see_more is not None:
                    event("scenario_step", step="expand_see_more")
                    see_more.clicked.emit()
                QTimer.singleShot(400, step4)

            def step4():
                event("scenario_step", step="expanded_shown", visible_count=len(root.property("visibleFinderHits") or []))
                capture(manual=True)
                event("scenario_step", step="select_hit_4")
                root.setProperty("selectedFinderIndex", 4)
                QTimer.singleShot(400, step5)

            def step5():
                bar = root.findChild(QQuickItem, "bottomActionBar")
                event("scenario_step", step="action_bar_visible", visible=bool(bar and bar.isVisible()))
                capture(manual=True)
                see_more = root.findChild(QQuickItem, "seeMoreFinderHits")
                if see_more is not None:
                    event("scenario_step", step="click_collapse")
                    see_more.clicked.emit()
                QTimer.singleShot(400, step6)

            def step6():
                idx = root.property("selectedFinderIndex")
                bar = root.findChild(QQuickItem, "bottomActionBar")
                event("scenario_step", step="collapsed_selection_reset", selected_index=idx, action_bar_visible=bool(bar and bar.isVisible()))
                capture(manual=True)
                QTimer.singleShot(500, step7)

            def step7():
                event("scenario_step", step="toggle_min_mode")
                controller.setExpanded(False)
                root.setProperty("expanded", False)
                QTimer.singleShot(400, step8)

            def step8():
                capture(manual=True)
                event("scenario_step", step="restore_full_mode")
                controller.setExpanded(True)
                root.setProperty("expanded", True)
                QTimer.singleShot(500, step9)

            def step9():
                # Demonstrate opening a real hit
                event("scenario_step", step="open_real_hit_0")
                ok = controller.openSelectedHit(0)
                event("scenario_step", step="opened_hit_result", success=ok)
                QTimer.singleShot(400, step10)

            def step10():
                back_btn = root.findChild(QQuickItem, "backFromFinder")
                if back_btn is not None:
                    event("scenario_step", step="click_back_to_workbench")
                    back_btn.clicked.emit()
                QTimer.singleShot(400, step11)

            def step11():
                ed = editor()
                draft_text = ed.property("text") if ed else ""
                event("scenario_step", step="workbench_restored", draft_text=draft_text, view=controller.snapshot["view"])
                capture(manual=True)
                QTimer.singleShot(600, lambda: view.rootObject().closeRequested.emit() if root is not None else app.quit())

            QTimer.singleShot(600, step1)

        run_finder_suggestions_scenario()

    elif args.scenario == "chatbox-pdf-snapshot":
        def run_chatbox_pdf_snapshot_scenario():
            view.resize(620, round(root.property("preferredWindowHeight")))

            def find_item(name):
                if root is None:
                    return None
                item = root.findChild(QQuickItem, name)
                if item is not None:
                    return item
                pending = list(root.childItems())
                while pending:
                    cand = pending.pop()
                    if cand.objectName() == name:
                        return cand
                    pending.extend(cand.childItems())
                return None

            def wait_until(predicate, next_step, *, polls=120, interval_ms=250):
                if predicate() or polls <= 0:
                    QTimer.singleShot(300, next_step)
                else:
                    QTimer.singleShot(interval_ms, lambda: wait_until(predicate, next_step, polls=polls - 1, interval_ms=interval_ms))

            def step1_select_pdf():
                event("scenario_step", step="select_genuine_pdf", pdf=str(args.pdf))
                controller.selectFile(str(args.pdf))
                wait_until(lambda: not controller.snapshot["busy"] and bool(controller.snapshot["fileName"]), step2_type_chat_draft)

            def step2_type_chat_draft():
                ed = editor()
                if ed is not None:
                    ed.setProperty("text", "BEST-Route chọn số mẫu sinh theo nguyên tắc nào ở trang đầu?")
                    ed.forceActiveFocus()
                send_btn = find_item("sendButton")
                event("scenario_step", step="pure_chatbox_ready",
                      send_icon=send_btn.property("iconName") if send_btn else "",
                      build_label=root.property("uiBuildLabel"))
                QTimer.singleShot(350, lambda: (capture(manual=True), QTimer.singleShot(450, step3_open_pdf_search)))

            def step3_open_pdf_search():
                search_btn = find_item("openPdfSearch")
                if search_btn is not None:
                    search_btn.clicked.emit()
                QTimer.singleShot(250, step3b_fill_pdf_search)

            def step3b_fill_pdf_search():
                field = find_item("pdfSearchField")
                if field is not None:
                    field.setProperty("text", "BEST-Route")
                event("scenario_step", step="pdf_search_popup_open", keyword="BEST-Route")
                QTimer.singleShot(300, lambda: (capture(manual=True), QTimer.singleShot(450, step4_run_pdf_search)))

            def step4_run_pdf_search():
                run_btn = find_item("runPdfSearch")
                if run_btn is not None:
                    run_btn.clicked.emit()
                wait_until(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "search", step5_capture_min_and_expand)

            def step5_capture_min_and_expand():
                ed = editor()
                event("scenario_step", step="pdf_search_unread_min",
                      matched_items=len(controller.snapshot.get("items", [])),
                      chat_draft_preserved=bool(ed and ed.property("text")))
                capture(manual=True)
                controller.setExpanded(True)
                QTimer.singleShot(550, step6_capture_snapshots_light_and_dark)

            def step6_capture_snapshots_light_and_dark():
                items = controller.snapshot.get("items", [])
                first_page = items[0]["page"] if items else 1
                snap_card = find_item(f"searchSnapshot_{first_page}")
                event("scenario_step", step="pdf_snapshots_rendered_light",
                      first_page=first_page,
                      snapshot_ready=bool(snap_card and snap_card.property("snapshotReady")),
                      snapshot_height=snap_card.height() if snap_card else 0)
                capture(manual=True)
                capture_desktop()
                root.setProperty("darkMode", True)
                QTimer.singleShot(450, lambda: step6b_restore_light(first_page))

            def step6b_restore_light(first_page):
                event("scenario_step", step="pdf_snapshots_rendered_dark", first_page=first_page)
                capture(manual=True)
                root.setProperty("darkMode", False)
                QTimer.singleShot(350, lambda: step6c_verify_reload(first_page))

            def step6c_verify_reload(first_page):
                reload_qml()
                QTimer.singleShot(450, lambda: step7_open_snapshot_page(first_page))

            def step7_open_snapshot_page(first_page):
                snap_card = find_item(f"searchSnapshot_{first_page}")
                event("scenario_step", step="click_snapshot_to_read_page", page=first_page)
                if snap_card is not None:
                    snap_card.activated.emit()
                else:
                    controller.readPage(first_page)
                wait_until(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "page", step8_after_page_read)

            def step8_after_page_read():
                event("scenario_step", step="page_opened_from_snapshot", page=controller.snapshot["pageNumber"])
                capture(manual=True)
                if args.max_model_calls >= 1:
                    QTimer.singleShot(500, step9_submit_direct_chat_question)
                else:
                    QTimer.singleShot(600, finish_scenario)

            def step9_submit_direct_chat_question():
                ed = editor()
                query_text = ed.property("text") if ed else ""
                event("scenario_step", step="submit_chatbox_enter_direct", query=query_text)
                root.submitDraft()
                QTimer.singleShot(350, lambda: capture(manual=True))
                wait_until(lambda: not controller.snapshot["busy"] and controller.snapshot["view"] == "answer", step10_expand_answer_sources, polls=240, interval_ms=500)

            def step10_expand_answer_sources():
                controller.setExpanded(True)
                QTimer.singleShot(400, step10b_toggle_sources)

            def step10b_toggle_sources():
                capture(manual=True)
                toggle = find_item("answerSourcesToggle")
                if toggle is not None and toggle.isVisible():
                    toggle.clicked.emit()
                    event("scenario_step", step="expand_answer_sources_snapshot")
                    QTimer.singleShot(500, lambda: (capture(manual=True), capture_desktop(), QTimer.singleShot(600, finish_scenario)))
                else:
                    QTimer.singleShot(600, finish_scenario)

            def finish_scenario():
                if root is not None:
                    root.closeRequested.emit()
                else:
                    app.quit()

            QTimer.singleShot(600, step1_select_pdf)

        run_chatbox_pdf_snapshot_scenario()

    print(json.dumps({"ready": True, "output": str(output), "model_cap": args.max_model_calls}), flush=True)
    try:
        code = app.exec()
    finally:
        state["closed"] = True
        if desktop_recording_proc is not None:
            try:
                desktop_recording_proc.send_signal(signal.SIGINT)
                desktop_recording_proc.wait(timeout=5)
                event("desktop_recording_finished", file="desktop-recording.mov")
            except Exception as exc:
                desktop_recording_proc.kill()
                event("desktop_recording_stop_failed", error=str(exc))
        for timer in timers:
            timer.stop()
        controller.close()
        runtime.close()
        event("closed", pdf_hash_unchanged=fingerprint(args.pdf) == provenance["sha256"])
        if not args.no_walkthrough and len(state["captures"]) >= 2:
            try:
                from scripts.record_ui import render_screenshots
                render_screenshots(output / "screenshots", output / "walkthrough", fps=1)
                event("walkthrough_rendered", mp4="walkthrough.mp4", gif="walkthrough.gif")
            except Exception as exc:
                event("walkthrough_render_failed", error=str(exc))
        save()
        view.setSource(QUrl())
        view.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
