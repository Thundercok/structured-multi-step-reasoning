"""Launch production RAT UI with passive evidence logging for manual/CUA acceptance.

No submitted prompts, generated answers, UI input injection, or canned model
responses. Interact through the actual window. Uses only the existing local
qwen3:4b-instruct model; this is app acceptance, not a research campaign.
"""
from __future__ import annotations
import argparse
import dataclasses
from collections.abc import Mapping
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
os.environ.setdefault("QT_QUICK_BACKEND", "software")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pdf = ROOT / "work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf"
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    assert digest == "9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c"
    from rat.config import config
    config.db_path = str(out / "index.db")
    from rat.crawler.db import Database
    from document_intake.pdf import read_pdf
    db = Database(config.db_path)
    text = read_pdf(pdf)["full_text"]
    stat = pdf.stat()
    db.upsert_document({"file_path": str(pdf), "file_name": pdf.name, "file_ext": ".pdf",
        "file_size": stat.st_size, "created_at": stat.st_ctime, "modified_at": stat.st_mtime,
        "content_text": text, "summary": "BEST-Route — original arXiv paper", "indexed_at": time.time()})
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QGuiApplication
    from rat.engine.slm import SLMEngine
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.timetable.compositor import TimetableCompositor
    from rat.ui.quick_app import create_quick_desk
    app = QGuiApplication([sys.argv[0]])
    app.setOrganizationName("RATIntegrityAcceptance")
    app.setApplicationName("RAT")
    lock = threading.Lock()
    def append(name, data):
        with lock:
            with (out / name).open("a") as stream:
                stream.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")
    model = SLMEngine(model="qwen3:4b-instruct", ollama_url="http://localhost:11434")
    original_chat = SLMEngine.chat_with_meta
    def recorded_chat(client, messages, tools, **kwargs):
        started = time.perf_counter()
        record = {"timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
                  "model": client.model, "messages": messages, "tools": tools,
                  "options": {k: v for k, v in kwargs.items() if not callable(v)}}
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
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), model_client=model,
                               use_live_model=True, discover_tools=True, enable_observation_pack=True)
    view, controller = create_quick_desk(assistant_runtime=runtime, reduced_motion=True)
    assert view is not None
    # Observers only. Production submit/dispatcher/model/rendering stay intact.
    last_state = None
    def record_snapshot():
        nonlocal last_state
        snap = controller.snapshot
        state = json.dumps(snap, ensure_ascii=False, default=str, sort_keys=True)
        (out / "latest_snapshot.json").write_text(state)
        if state != last_state:
            append("ui_snapshots.jsonl", {"timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(), "snapshot": snap})
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
            (out / "artifacts.json").write_text(json.dumps([a.to_dict() for a in runtime.artifact_store.list()], ensure_ascii=False, indent=2))
        except Exception as exc:
            append("observer_errors.jsonl", {"error": str(exc)})
    controller._execution_delivered.connect(lambda request, response: record_response(response))
    timer = QTimer()
    timer.setInterval(1500)
    timer.timeout.connect(record_snapshot)
    timer.start()
    (out / "environment.json").write_text(json.dumps({"model": model.model,
        "model_digest": next(m["digest"] for m in json.loads(__import__('urllib.request', fromlist=['urlopen']).urlopen('http://localhost:11434/api/tags').read())["models"] if m["name"] == model.model),
        "pdf_path": str(pdf), "pdf_origin": "https://arxiv.org/pdf/2506.22716", "pdf_sha256": digest,
        "build": view.rootObject().property("uiBuildLabel"), "script": str(Path(__file__).resolve()),
        "mode": "live_ui_acceptance", "canned_responses": False}, ensure_ascii=False, indent=2))
    view.show()
    view.requestActivate()
    record_snapshot()
    print("APP_READY", str(out), flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
