"""
Native MLX Model Document QA and Realistic Performance Telemetry Runner.
Executes up to 12 real generation requests against local MLX checkpoint:
~/.cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/...
Captures raw Qt warnings, font family resolutions, psutil current RSS,
ru_maxrss peak RSS, idle CPU, and exact generation telemetry in calls.jsonl.
"""
import os
import sys
import json
import time
import re
import tempfile
import resource
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))
OUTPUT_DIR = WORKSPACE / "audit" / "rat_overnight_sweep_repair_20261019"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL_DIR = Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots/32f3e8ecf65426fc3306969496342d504bfa13f3"

def main():
    print("=== Starting Native Performance & MLX Document QA Session ===")
    
    # 1. Check model directory
    if not MODEL_DIR.exists():
        print(f"ERROR: Model directory {MODEL_DIR} not found.")
        sys.exit(1)
    print(f"Model path verified: {MODEL_DIR}")

    # 2. Check psutil
    try:
        import psutil
        psutil_ver = psutil.__version__
        psutil_path = psutil.__file__
        print(f"psutil {psutil_ver} imported from {psutil_path}")
    except ImportError as e:
        print(f"ERROR: psutil import failed: {e}")
        sys.exit(1)

    # 3. Setup Qt Application and raw warning interceptor
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import qInstallMessageHandler, QtMsgType
    from PyQt6.QtGui import QFont, QFontInfo
    from PyQt6.QtWidgets import QApplication

    captured_warnings = []

    def qt_message_handler(mode, context, message):
        captured_warnings.append(message)
        # also print to stderr
        sys.stderr.write(f"[Qt] {message}\n")

    qInstallMessageHandler(qt_message_handler)

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    default_font_resolved = QFontInfo(app.font()).family()
    mono_font_resolved = QFontInfo(QFont("Menlo")).family()
    print(f"Default font resolved: '{default_font_resolved}', Mono font resolved: '{mono_font_resolved}'")

    # 4. Initialize Local Database and Test Document
    from rat.crawler.db import Database
    from rat.engine.assistant_runtime import AssistantRuntime
    from rat.engine.mlx_document_session import MLXDocumentSession
    from rat.engine.selected_document_qa import answer_selected_document
    from rat.timetable.compositor import TimetableCompositor

    tmp_dir = Path(tempfile.mkdtemp(prefix="rat_native_perf_"))
    db_path = tmp_dir / "index.db"
    db = Database(str(db_path))

    doc_path = tmp_dir / "so_tay_quy_che_dao_tao_2026.txt"
    doc_content = (
        "QUY CHẾ ĐÀO TẠO ĐẠI HỌC VÀ HỌC PHẦN NĂM 2026\n\n"
        "Chương I: Quy định chung về học tín chỉ\n"
        "Điều 1: Năm học gồm 2 học kỳ chính (mỗi kỳ 15 tuần) và 1 học kỳ hè (8 tuần).\n"
        "Điều 2: Số tín chỉ tối đa sinh viên được đăng ký trong một học kỳ chính là 24 tín chỉ, "
        "và số tín chỉ tối thiểu là 14 tín chỉ đối với sinh viên học lực bình thường.\n"
        "Điều 3: Sinh viên có điểm trung bình tích lũy GPA dưới 2.0 chỉ được đăng ký tối đa 16 tín chỉ.\n"
        "Điều 4: Học phí mỗi tín chỉ cơ sở ngành là 850.000 VNĐ, tín chỉ chuyên ngành là 980.000 VNĐ.\n"
        "Điều 5: Hạn nộp đơn rút học phần có ghi nhận điểm W là trước tuần học thứ 6 của học kỳ.\n"
        "Điều 6: Điều kiện dự thi kết thúc học phần là sinh viên phải tham gia ít nhất 80% số tiết trên lớp.\n"
        "Điều 7: Điểm đánh giá bộ phận gồm: chuyên cần (10%), bài tập nhóm (20%), thi giữa kỳ (20%), "
        "và thi kết thúc học phần (50%). Điểm đạt học phần là từ 4.0 trên thang điểm 10.\n"
        "Điều 8: Sinh viên được bảo lưu kết quả học tập tối đa không quá 2 học kỳ liên tiếp.\n"
        "Điều 9: Thời gian tối đa để hoàn thành chương trình đào tạo chuẩn 4 năm là 6 năm.\n"
        "Điều 10: Chứng chỉ ngoại ngữ chuẩn đầu ra yêu cầu tối thiểu IELTS 5.5 hoặc TOEIC 650.\n"
    )
    doc_path.write_text(doc_content, encoding="utf-8")

    db.upsert_document({
        "file_path": str(doc_path),
        "file_name": doc_path.name,
        "file_ext": ".txt",
        "file_size": doc_path.stat().st_size,
        "created_at": 1729000000.0,
        "modified_at": 1729000000.0,
        "indexed_at": 1729000000.0,
        "content_text": doc_content,
        "summary": "Quy chế đào tạo đại học và học phần năm 2026",
    })

    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)

    # 5. Initialize MLXDocumentSession and measure load time
    print(f"Loading MLX document session from {MODEL_DIR}...")
    t_load_start = time.perf_counter()
    session = MLXDocumentSession(str(MODEL_DIR), max_context_tokens=4096)
    load_duration_s = session.load()
    t_load_total = time.perf_counter() - t_load_start
    print(f"MLX session loaded in {t_load_total:.2f}s (session report: {load_duration_s:.2f}s)")

    # 6. Execute up to 12 generation requests
    test_queries = [
        "Sinh viên được đăng ký tối đa bao nhiêu tín chỉ trong một học kỳ chính?",
        "Số tín chỉ tối thiểu sinh viên học lực bình thường phải đăng ký là bao nhiêu?",
        "Sinh viên có GPA dưới 2.0 được đăng ký tối đa bao nhiêu tín chỉ?",
        "Học phí một tín chỉ chuyên ngành là bao nhiêu tiền?",
        "Thời hạn rút học phần có ghi nhận điểm W là trước tuần thứ mấy?",
        "Điều kiện về chuyên cần để được dự thi kết thúc học phần là gì?",
        "Điểm thi kết thúc học phần chiếm bao nhiêu phần trăm trong điểm tổng kết?",
        "Sinh viên được bảo lưu kết quả học tập tối đa mấy học kỳ liên tiếp?",
        "Thời gian tối đa để hoàn thành chương trình đại học 4 năm là mấy năm?",
        "Chuẩn đầu ra ngoại ngữ yêu cầu chứng chỉ TOEIC tối thiểu bao nhiêu điểm?",
        "Học phí một tín chỉ cơ sở ngành là bao nhiêu?",
        "Điểm đạt học phần tối thiểu là bao nhiêu trên thang điểm 10?"
    ]

    calls_ledger = []
    calls_jsonl_path = OUTPUT_DIR / "calls.jsonl"

    print(f"Executing {len(test_queries)} native generation requests...")
    with open(calls_jsonl_path, "w", encoding="utf-8") as ledger_file:
        for idx, query in enumerate(test_queries, start=1):
            print(f"[{idx:02d}/12] Query: '{query}'")
            t_call_start = time.perf_counter()
            streamed_tokens = []
            
            def on_text(tok):
                streamed_tokens.append(tok)

            try:
                turn_ref = {"turn_id": f"perf-turn-{idx}", "conversation_id": "perf-conv-1"}
                exec_id = f"perf-exec-{idx}"
                
                resp = answer_selected_document(
                    runtime,
                    query,
                    str(doc_path),
                    model_client=session,
                    turn_ref=turn_ref,
                    execution_id=exec_id,
                    on_text=on_text,
                )
                
                duration_ms = (time.perf_counter() - t_call_start) * 1000.0
                qa_tel = getattr(resp, "qa_telemetry", {}) or {}
                
                entry = {
                    "call_index": idx,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "query": query,
                    "document_path": str(doc_path),
                    "status": "success" if resp.error is None else f"error:{resp.error}",
                    "attempts": 1,
                    "latency_ms": round(duration_ms, 2),
                    "prompt_tokens": qa_tel.get("prompt_tokens"),
                    "completion_tokens": qa_tel.get("completion_tokens"),
                    "reused_prefix_tokens": qa_tel.get("reused_prefix_tokens", 0),
                    "first_token_ms": qa_tel.get("first_token_ms"),
                    "prefill_ms": qa_tel.get("prefill_ms"),
                    "generation_ms": qa_tel.get("generation_ms"),
                    "answer_snippet": resp.answer[:120].strip() if resp.answer else "",
                    "all_satisfied": getattr(resp.reconciliation, "all_satisfied", None),
                }
                print(f"      -> Status: {entry['status']} | Latency: {entry['latency_ms']:.1f}ms | Tokens: {entry['prompt_tokens']} prompt, {entry['completion_tokens']} comp | First token: {entry['first_token_ms']}ms")
                print(f"      -> Answer: {entry['answer_snippet']}")
            except Exception as ex:
                duration_ms = (time.perf_counter() - t_call_start) * 1000.0
                entry = {
                    "call_index": idx,
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "query": query,
                    "document_path": str(doc_path),
                    "status": f"exception:{type(ex).__name__}: {str(ex)}",
                    "attempts": 1,
                    "latency_ms": round(duration_ms, 2),
                    "prompt_tokens": None,
                    "completion_tokens": None,
                    "reused_prefix_tokens": 0,
                    "first_token_ms": None,
                    "prefill_ms": None,
                    "generation_ms": None,
                    "answer_snippet": "",
                    "all_satisfied": False,
                }
                print(f"      -> ERROR: {entry['status']}")

            calls_ledger.append(entry)
            ledger_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
            ledger_file.flush()

    # 7. Collect performance and resource telemetry
    current_rss_bytes = psutil.Process().memory_info().rss
    current_rss_mb = round(current_rss_bytes / (1024 * 1024), 2)

    # On macOS ru_maxrss is in bytes
    raw_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = round(raw_maxrss / (1024 * 1024), 2)

    print("Measuring idle CPU for 1 second...")
    idle_cpu_percent = psutil.cpu_percent(interval=1.0)
    print(f"Current RSS: {current_rss_mb} MB, Peak RSS: {peak_rss_mb} MB, Idle CPU: {idle_cpu_percent}%")

    # Parse font warnings
    font_alias_warnings = [w for w in captured_warnings if "Populating font family aliases" in w]
    font_alias_warning_count = len(font_alias_warnings)
    font_alias_cost_ms = None
    if font_alias_warnings:
        m = re.search(r"took\s+(\d+(?:\.\d+)?)\s*ms", font_alias_warnings[0])
        if m:
            font_alias_cost_ms = float(m.group(1))

    # Evaluate gates
    gate_model_inference = len(calls_ledger) == 12 and all(c["status"] == "success" for c in calls_ledger)
    gate_token_budget = all(c["completion_tokens"] <= 640 for c in calls_ledger if c.get("completion_tokens"))
    gate_latency_90s = all(c["latency_ms"] <= 90000.0 for c in calls_ledger)

    perf_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "qpa_platform": os.environ.get("QT_QPA_PLATFORM", "offscreen"),
        "model_id": "mlx-community/Qwen3.5-4B-MLX-4bit",
        "model_path": str(MODEL_DIR),
        "real_model_calls_executed": len(calls_ledger),
        "model_load_time_s": round(t_load_total, 3),
        "default_font_family_resolved": default_font_resolved,
        "mono_font_family_resolved": mono_font_resolved,
        "font_alias_warning_count": font_alias_warning_count,
        "font_alias_population_cost_ms": font_alias_cost_ms,
        "raw_qt_warnings_count": len(captured_warnings),
        "raw_qt_warnings": captured_warnings,
        "current_rss_mb": current_rss_mb,
        "peak_rss_mb": peak_rss_mb,
        "idle_cpu_percent": idle_cpu_percent,
        "calls_ledger_file": str(calls_jsonl_path.relative_to(OUTPUT_DIR)),
        "gates": {
            "all_12_requests_succeeded": gate_model_inference,
            "token_budget_leq_640": gate_token_budget,
            "latency_leq_90s_per_request": gate_latency_90s,
            "font_alias_status": "warning_present" if font_alias_warning_count > 0 else "clean",
        },
        "unmeasured_fields": {
            "cocoa_native_window_frame_sync_ms": {
                "value": None,
                "reason": "Offscreen QPA platform used; native NSWindow Cocoa compositor frame sync requires interactive display server"
            },
            "gpu_hardware_thermal_throttle": {
                "value": None,
                "reason": "Requires root / IOKit hardware sensor query"
            }
        }
    }

    perf_json_path = OUTPUT_DIR / "native_performance.json"
    with open(perf_json_path, "w", encoding="utf-8") as f:
        json.dump(perf_data, f, indent=2, ensure_ascii=False)
    print(f"Saved native performance artifact to {perf_json_path}")

    # Clean up temp
    db.get_connection().close()
    print("=== Native Performance Session Complete ===")

if __name__ == "__main__":
    main()
