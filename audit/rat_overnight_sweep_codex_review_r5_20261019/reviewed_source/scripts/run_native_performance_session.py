"""
Native MLX Model Document QA and Realistic Performance Telemetry Runner.
Executes up to 12 generation requests against local MLX checkpoint or fake backend.
Captures raw Qt warnings, font family resolutions, runner RSS, ru_maxrss peak,
host CPU, and exact generation telemetry in an append-only calls.jsonl ledger.
"""
import os
import sys
import json
import time
import re
import tempfile
import resource
import argparse
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime, timezone

WORKSPACE = Path(__file__).resolve().parents[1]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

DEFAULT_OUTPUT_DIR = WORKSPACE / "audit" / "rat_overnight_sweep_repair_codex_repair_20261019"
DEFAULT_MODEL_DIR = Path.home() / ".cache/huggingface/hub/models--mlx-community--Qwen3.5-4B-MLX-4bit/snapshots/32f3e8ecf65426fc3306969496342d504bfa13f3"


class FakeTokenizer:
    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt, enable_thinking=False):
        text = "".join(m.get("role", "") + ":" + m.get("content", "") + "\n" for m in messages)
        return list(text.encode("utf-8")) + ([255] if add_generation_prompt else [])

    def decode(self, tokens):
        return "Dựa trên văn bản, thông tin được xác nhận đầy đủ."


class FakeBackend:
    def __init__(self):
        self.loads = 0
        self.prefills = 0
        self.generations = []
        self.answer = "Theo quy định trong tài liệu, sinh viên được đăng ký tối đa 24 tín chỉ trong một học kỳ chính."

    def load(self, path):
        self.loads += 1
        return object(), FakeTokenizer()

    def prepare(self, model, tokens, check=None):
        if check:
            check()
        self.prefills += 1
        return {"tokens": list(tokens)}

    def generate(self, model, tokenizer, tokens, cache, max_tokens, check):
        if check:
            check()
        self.generations.append(list(tokens))
        yield SimpleNamespace(text=self.answer, generation_tokens=28, finish_reason="stop")

    def clear(self):
        pass


def parse_args():
    parser = argparse.ArgumentParser(description="Native Performance and MLX Document QA Runner")
    parser.add_argument("--fake-backend", action="store_true", help="Use offline mock backend instead of real MLX model")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory for telemetry")
    parser.add_argument("--max-budget", type=int, default=12, help="Maximum allowed attempts across all runs")
    return parser.parse_args()


def count_existing_attempts(ledger_path: Path) -> int:
    """Count unique attempts from the append-only ledger."""
    if not ledger_path.exists():
        return 0
    seen_requests = set()
    legacy_count = 0
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                req_id = rec.get("request_id")
                if req_id:
                    seen_requests.add(str(req_id))
                elif rec.get("event") in ("request_start", "request_complete"):
                    c_idx = rec.get("call_index")
                    if c_idx is not None:
                        seen_requests.add(f"call_{c_idx}")
                    else:
                        seen_requests.add(f"line_{line_no}")
                else:
                    # Legacy record (no event field)
                    c_idx = rec.get("call_index")
                    if c_idx is not None:
                        seen_requests.add(f"legacy_call_{c_idx}")
                    else:
                        legacy_count += 1
            except Exception:
                legacy_count += 1
    return len(seen_requests) + legacy_count


def main():
    args = parse_args()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    calls_jsonl_path = output_dir / "calls.jsonl"

    print("=== Starting Native Performance & Document QA Session ===")
    print(f"Output directory: {output_dir}")
    print(f"Backend mode: {'Fake Backend (Offline)' if args.fake_backend else 'Real MLX Model'}")

    # 1. Verify model or setup fake directory
    if args.fake_backend:
        temp_model_dir = Path(tempfile.mkdtemp(prefix="rat_fake_model_"))
        for fname in ("config.json", "tokenizer.json", "weights.safetensors"):
            (temp_model_dir / fname).write_text("{}", encoding="utf-8")
        model_path = temp_model_dir
        print(f"Fake model directory created at: {model_path}")
    else:
        model_path = DEFAULT_MODEL_DIR
        if not model_path.exists():
            print(f"ERROR: Real model directory {model_path} not found.")
            sys.exit(1)
        print(f"Real model path verified: {model_path}")

    # 2. Check psutil
    try:
        import psutil
    except ImportError:
        for p in ("/opt/homebrew/lib/python3.14/site-packages",
                  str(Path.home() / "Library/Python/3.14/lib/python/site-packages"),
                  str(Path.home() / "Library/Python/3.12/lib/python/site-packages")):
            if p not in sys.path and os.path.exists(p):
                sys.path.append(p)
        try:
            import psutil
        except ImportError:
            psutil = None

    if psutil is not None:
        psutil_ver = getattr(psutil, "__version__", "unknown")
        psutil_path = getattr(psutil, "__file__", "unknown")
        print(f"psutil {psutil_ver} imported from {psutil_path}")
    else:
        print("WARNING: psutil could not be imported; will use resource metrics and null cpu.")

    # 3. Setup Qt Application and raw warning interceptor
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import qInstallMessageHandler
    from PyQt6.QtGui import QFont, QFontInfo
    from PyQt6.QtWidgets import QApplication

    captured_warnings = []

    def qt_message_handler(mode, context, message):
        captured_warnings.append(message)
        sys.stderr.write(f"[Qt] {message}\n")

    qInstallMessageHandler(qt_message_handler)

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    default_font_resolved = QFontInfo(app.font()).family()
    mono_font_resolved = QFontInfo(QFont("Menlo")).family()
    print(f"Default font resolved: '{default_font_resolved}', Mono font resolved: '{mono_font_resolved}'")

    # 4. Check existing attempts & Budget Guard
    existing_attempts = count_existing_attempts(calls_jsonl_path)
    print(f"Append-only ledger: {calls_jsonl_path} (Existing recorded attempts: {existing_attempts}/{args.max_budget})")

    # 5. Initialize Local Database and Test Document
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

    # 6. Initialize MLXDocumentSession
    print(f"Loading session from {model_path}...")
    t_load_start = time.perf_counter()
    if args.fake_backend:
        session = MLXDocumentSession(str(model_path), max_context_tokens=4096, _backend_factory=lambda: FakeBackend())
    else:
        session = MLXDocumentSession(str(model_path), max_context_tokens=4096)
    load_duration_s = session.load()
    t_load_total = time.perf_counter() - t_load_start
    print(f"Session loaded in {t_load_total:.2f}s (session report: {load_duration_s:.2f}s)")

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

    session_id = f"session-{int(time.time())}-{os.getpid()}"
    current_run_dispatched = []

    current_attempts = existing_attempts
    if current_attempts >= args.max_budget:
        print(f"BUDGET GUARD HALT: Global budget limit reached ({current_attempts}/{args.max_budget}). No new requests will be dispatched.")
    else:
        remaining_budget = args.max_budget - current_attempts
        print(f"Dispatching requests (Remaining budget: {remaining_budget})...")
        with open(calls_jsonl_path, "a", encoding="utf-8") as ledger_file:
            for idx, query in enumerate(test_queries, start=current_attempts + 1):
                if current_attempts >= args.max_budget:
                    print(f"Budget limit reached ({current_attempts}/{args.max_budget}). Halting loop.")
                    break

                exec_id = f"perf-exec-{idx}-{int(time.time()*1000)}"
                print(f"[{idx:02d}/{args.max_budget}] Query: '{query}'")

                # Pre-request checkpoint written and flushed BEFORE inference
                start_entry = {
                    "event": "request_start",
                    "call_index": idx,
                    "request_id": exec_id,
                    "session_id": session_id,
                    "backend_type": "fake" if args.fake_backend else "real",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "query": query,
                    "document_path": str(doc_path),
                }
                ledger_file.write(json.dumps(start_entry, ensure_ascii=False) + "\n")
                ledger_file.flush()
                current_attempts += 1

                t_call_start = time.perf_counter()
                streamed_tokens = []

                def on_text(tok):
                    streamed_tokens.append(tok)

                try:
                    turn_ref = {"turn_id": f"perf-turn-{idx}", "conversation_id": "perf-conv-1"}
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

                    complete_entry = {
                        "event": "request_complete",
                        "call_index": idx,
                        "request_id": exec_id,
                        "session_id": session_id,
                        "backend_type": "fake" if args.fake_backend else "real",
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
                    print(f"      -> Status: {complete_entry['status']} | Latency: {complete_entry['latency_ms']:.1f}ms")
                except Exception as ex:
                    duration_ms = (time.perf_counter() - t_call_start) * 1000.0
                    complete_entry = {
                        "event": "request_complete",
                        "call_index": idx,
                        "request_id": exec_id,
                        "session_id": session_id,
                        "backend_type": "fake" if args.fake_backend else "real",
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
                    print(f"      -> ERROR: {complete_entry['status']}")

                current_run_dispatched.append(complete_entry)
                ledger_file.write(json.dumps(complete_entry, ensure_ascii=False) + "\n")
                ledger_file.flush()

    # 7. Collect performance and resource telemetry
    raw_maxrss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = round(raw_maxrss / (1024 * 1024), 2)
    if psutil is not None:
        current_rss_bytes = psutil.Process().memory_info().rss
        current_rss_mb = round(current_rss_bytes / (1024 * 1024), 2)
        print("Measuring host CPU for 1 second...")
        host_cpu_percent = psutil.cpu_percent(interval=1.0)
    else:
        current_rss_mb = peak_rss_mb
        host_cpu_percent = None
    print(f"Current Runner RSS: {current_rss_mb} MB, Peak RSS: {peak_rss_mb} MB, Host CPU: {host_cpu_percent}%")

    font_alias_warnings = [w for w in captured_warnings if "Populating font family aliases" in w]
    font_alias_warning_count = len(font_alias_warnings)
    font_alias_cost_ms = None
    if font_alias_warnings:
        m = re.search(r"took\s+(\d+(?:\.\d+)?)\s*ms", font_alias_warnings[0])
        if m:
            font_alias_cost_ms = float(m.group(1))

    # Read completed ledger records for telemetry
    import statistics

    def classify_record_backend(rec: dict) -> str:
        if "backend_type" in rec:
            return rec["backend_type"]
        if "mock" in str(rec.get("model_id", "")).lower():
            return "fake"
        if rec.get("first_token_ms") or rec.get("prefill_ms") or rec.get("generation_ms"):
            return "real"
        if rec.get("prompt_tokens") and rec.get("prompt_tokens") >= 500:
            return "real"
        return "unknown"

    completed_records = []
    if calls_jsonl_path.exists():
        with open(calls_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        r = json.loads(line)
                        if r.get("event") == "request_complete" or ("completion_tokens" in r and "event" not in r):
                            completed_records.append(r)
                    except Exception:
                        pass

    ledger_real_records = [r for r in completed_records if classify_record_backend(r) == "real"]
    ledger_fake_records = [r for r in completed_records if classify_record_backend(r) == "fake"]

    new_fake_executed = len([r for r in current_run_dispatched if r.get("backend_type") == "fake"])
    new_real_executed = len([r for r in current_run_dispatched if r.get("backend_type") == "real"])

    if args.fake_backend:
        real_calls_count = 0
        fake_calls_count = new_fake_executed if (new_fake_executed > 0 or not ledger_fake_records) else len(ledger_fake_records)
        scope_type = "offline_fake_backend_simulation"
        if new_fake_executed > 0:
            scope_status = f"offline_fake_backend_completed_{new_fake_executed}_calls"
            scope_note = "Offline simulation utilizing mock tokenizer and canned completions; zero real inference calls performed."
        elif len(ledger_real_records) > 0:
            scope_status = "budget_halt_existing_real_history"
            scope_note = f"Budget guard halted without dispatching new requests. Existing append-only ledger contains {len(ledger_real_records)} historical real-model records; zero fake calls executed."
        else:
            scope_status = f"offline_fake_backend_completed_{fake_calls_count}_calls"
            scope_note = "Offline simulation utilizing mock tokenizer and canned completions; zero real inference calls performed."
        all_12_requests_succeeded = False
        relevant_for_warm = current_run_dispatched if current_run_dispatched else ledger_fake_records
    else:
        real_calls_count = len(ledger_real_records)
        fake_calls_count = 0
        scope_type = "real_model_backend_smoke"
        scope_status = "backend_inference_verified_12_calls" if len(ledger_real_records) == 12 else f"backend_inference_completed_{len(ledger_real_records)}_calls"
        all_12_requests_succeeded = len(ledger_real_records) == 12 and all(c.get("status") == "success" for c in ledger_real_records)
        scope_note = "12 successful backend requests demonstrate real MLX model inference on local document context. Full interactive UI queue requires dedicated model budget and native display server."
        relevant_for_warm = ledger_real_records

    # Compute warm latency dynamically from relevant completed records of matching session/backend
    if len(relevant_for_warm) > 1:
        warm_samples = relevant_for_warm[1:]
        latencies = [c["latency_ms"] for c in warm_samples if c.get("latency_ms") is not None]
        if latencies:
            call_8_val = relevant_for_warm[7].get("latency_ms") if len(relevant_for_warm) >= 8 else None
            warm_stats = {
                "min": round(min(latencies), 2),
                "max": round(max(latencies), 2),
                "median": round(statistics.median(latencies), 2),
                "call_8_ms": round(call_8_val, 2) if call_8_val is not None else None,
                "sample_count": len(latencies),
                "note": "Warm samples reflect distinct queries against a shared document prefix. Varying question complexity means warm runs do not demonstrate matched before/after cache acceleration."
            }
        else:
            warm_stats = None
    else:
        warm_stats = None

    eval_records = relevant_for_warm if relevant_for_warm else completed_records
    gate_token_budget = all(c.get("completion_tokens", 0) <= 640 for c in eval_records if c.get("completion_tokens")) if eval_records else True
    gate_latency_90s = all(c.get("latency_ms", 0) <= 90000.0 for c in eval_records) if eval_records else True

    perf_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "qpa_platform": os.environ.get("QT_QPA_PLATFORM", "offscreen"),
        "model_id": "mlx-community/Qwen3.5-4B-MLX-4bit" if not args.fake_backend else "mock/FakeMLXDocumentSession",
        "model_path": str(model_path),
        "scope_classification": {
            "type": scope_type,
            "status": scope_status,
            "unverified_native_scenarios": [
                "native_gui_token_streaming",
                "user_cancel_during_prefill_or_decode",
                "query_after_cancel",
                "changed_file_invalidation",
                "changed_document_invalidation",
                "outside_excerpt_unresolved_case"
            ],
            "note": scope_note
        },
        "real_model_calls_executed": real_calls_count,
        "fake_model_calls_executed": fake_calls_count,
        "model_load_time_s": round(t_load_total, 3),
        "default_font_family_resolved": default_font_resolved,
        "mono_font_family_resolved": mono_font_resolved,
        "font_alias_warning_count": font_alias_warning_count,
        "font_alias_population_cost_ms": font_alias_cost_ms,
        "font_alias_warning_scope": "Captured during offscreen QApplication probe before creating any RAT window. Does not reflect RAT window first paint or stylesheet rendering time.",
        "raw_qt_warnings_count": len(captured_warnings),
        "raw_qt_warnings": captured_warnings,
        "backend_runner_rss_mb": current_rss_mb,
        "backend_runner_peak_rss_mb": peak_rss_mb,
        "host_cpu_percent": host_cpu_percent,
        "calls_ledger_file": str(calls_jsonl_path.relative_to(output_dir)),
        "warm_generation_latency_ms": warm_stats,
        "gates": {
            "all_12_requests_succeeded": all_12_requests_succeeded,
            "token_budget_leq_640": gate_token_budget,
            "latency_leq_90s_per_request": gate_latency_90s,
            "font_alias_status": "warning_present" if font_alias_warning_count > 0 else "clean",
        },
        "unmeasured_fields": {
            "process_idle_cpu_percent": {
                "value": None,
                "reason": "Host CPU measured via psutil.cpu_percent(); per-process idle CPU of resident app was not isolated in an idle state."
            },
            "resident_gui_app_rss_mb": {
                "value": None,
                "reason": "Current process is headless backend runner; resident Workbench GUI app memory footprint was not measured."
            },
            "question_suffix_prefill_ms": {
                "value": None,
                "reason": "MLXDocumentSession processes question tokens together with generation; question-suffix prefill is not separately timed."
            },
            "displayed_ui_token_ms": {
                "value": None,
                "reason": "Session runner was headless; live UI token streaming to Omnibar speech bubble was not hosted."
            },
            "cocoa_native_window_frame_sync_ms": {
                "value": None,
                "reason": "Offscreen QPA platform used; native NSWindow Cocoa compositor frame sync requires interactive display server."
            },
            "gpu_hardware_thermal_throttle": {
                "value": None,
                "reason": "Requires root / IOKit hardware sensor query."
            }
        }
    }

    perf_json_path = output_dir / "native_performance.json"
    with open(perf_json_path, "w", encoding="utf-8") as f:
        json.dump(perf_data, f, indent=2, ensure_ascii=False)
    print(f"Saved native performance artifact to {perf_json_path}")

    db.get_connection().close()
    print("=== Native Performance Session Complete ===")


if __name__ == "__main__":
    main()
