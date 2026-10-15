"""Bounded, private development observations of a three-turn actual-PDF workflow.

This collector never copies PDFs, modifies the personal index/config, downloads
models, or equates a completed runtime with reviewed task quality. Raw requests
and replies can contain document text and must stay in its private output area.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rat.config import config
from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.timetable.compositor import TimetableCompositor
from rat.ui.chat_session import ConversationHistory
from scripts.run_dsa_core_smoke import InstrumentedSLMEngine, compute_source_hashes


class ModelCallBudgetExceeded(RuntimeError):
    pass


class BoundedSLMEngine(InstrumentedSLMEngine):
    """Include planning/repair calls in one hard HTTP-call budget."""

    def __init__(self, *, model, timeout_s, max_calls):
        super().__init__(model=model, default_timeout=timeout_s)
        self.max_calls = max_calls
        self.calls_started = 0
        self.budget_rejections = 0

    def chat_with_meta(self, messages, tools, timeout=90.0, max_tokens=640,
                       thinking=False, response_format=None):
        if self.calls_started >= self.max_calls:
            self.budget_rejections += 1
            raise ModelCallBudgetExceeded("global_model_call_budget_exhausted")
        self.calls_started += 1
        requested_timeout = self.default_timeout if timeout == 90.0 else timeout
        return super().chat_with_meta(
            messages, tools, timeout=min(float(requested_timeout), self.default_timeout, 90.0),
            max_tokens=min(int(max_tokens), 640), thinking=thinking,
            response_format=response_format,
        )


def json_default(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot record {type(value).__name__}")


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=json_default) + "\n")
    path.chmod(0o600)


def validate_output_path(output):
    """Resolve symlinks before checking that raw data cannot enter source files."""
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError("Output must be a fresh directory")
    if output.is_relative_to(REPO_ROOT):
        relative = output.relative_to(REPO_ROOT)
        if not relative.parts or relative.parts[0] != ".rat":
            raise ValueError("Private output must be outside the repository or in its ignored .rat area")
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--", str(relative)], cwd=REPO_ROOT,
            check=False, capture_output=True,
        )
        if ignored.returncode != 0:
            raise ValueError("The repository .rat output area must be ignored by Git")
    else:
        # A different checkout is not a private destination either.
        if any((parent / ".git").exists() for parent in output.parents):
            raise ValueError("Private output cannot be inside another Git checkout")
    return output


def file_fingerprint(path):
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    after = path.stat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, key) != getattr(after, key) for key in fields):
        raise ValueError("Source changed while fingerprinting")
    return {"path": str(path), "filename": path.name, "size_bytes": after.st_size,
            "modified_at_ns": after.st_mtime_ns, "sha256": digest.hexdigest()}


def validate_source(file_path, db):
    path = Path(file_path).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise ValueError("Source must be an existing PDF")
    if path.stat().st_size > 30 * 1024 * 1024:
        raise ValueError("Source exceeds the 30 MiB development-smoke limit")
    # Exact-path lookup only; preflight never reads the rest of the personal index.
    indexed = db.get_connection().execute(
        "SELECT id FROM documents WHERE file_path = ?", (str(path),)
    ).fetchone()
    if indexed is None:
        raise ValueError("Source must already be indexed at its exact existing path")
    from pypdf import PdfReader
    with path.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ValueError("Source PDF requires a password")
        page_count = len(reader.pages)
    if not 1 <= page_count <= 400:
        raise ValueError("Source must contain 1..400 pages for this bounded smoke")
    return {**file_fingerprint(path), "indexed_id": indexed[0], "page_count": page_count}


def default_requests(source, topic=None, passage_query=None):
    topic = topic or Path(source["filename"]).stem.replace("_", " ")
    passage_query = passage_query or topic
    return [
        f'Tìm đúng PDF "{source["filename"]}" về {topic} trong máy. '
        "Đọc trang PDF 1 và tóm tắt ngắn nội dung đã đọc.",
        f'Trong tài liệu đó, tìm đoạn về "{passage_query}", đọc trang tìm được '
        "và trích nguyên văn một câu kèm số trang PDF. Nếu chưa đọc được thì nói rõ.",
        "Gửi tôi file PDF gốc đó để tôi mở.",
    ]


def token_accounting(calls):
    known = bool(calls) and all(call.get("token_usage_known") is True for call in calls)
    return {
        "token_usage_known": known,
        "prompt_tokens": sum(c["prompt_tokens"] for c in calls) if known else None,
        "completion_tokens": sum(c["completion_tokens"] for c in calls) if known else None,
        "total_tokens": sum(c["total_tokens"] for c in calls) if known else None,
    }


def verify_file_artifacts(artifacts, source):
    """Only hash the authorized target; never follow an unrelated artifact path."""
    observations = []
    target = Path(source["path"])
    for artifact in artifacts:
        data = artifact.to_dict() if hasattr(artifact, "to_dict") else artifact
        if data.get("kind") != "document_file":
            continue
        payload = data.get("payload") or {}
        observed = {"artifact_id": data.get("id"), "revision": data.get("revision"),
                    "kind": "document_file", "verified_local_reference": False,
                    "native_click_observed": False}
        try:
            path = Path(payload.get("path", "")).expanduser().resolve(strict=True)
            if path != target:
                raise ValueError("attachment_target_mismatch")
            current = file_fingerprint(target)
            size = payload.get("size_bytes", payload.get("file_size"))
            observed["checks"] = {
                "delivery_operation": (data.get("provenance") or {}).get("operation_name") == "deliver_document",
                "delivered_flag": payload.get("delivered") is True,
                "found_flag": payload.get("found") is True,
                "local_reference": payload.get("delivery") == "local_reference",
                "filename_matches": payload.get("filename") == target.name,
                "size_matches": type(size) is int and size == current["size_bytes"],
                "artifact_sha256_matches": payload.get("sha256") == current["sha256"],
                "source_unchanged": all(current[k] == source[k] for k in
                                        ("sha256", "size_bytes", "modified_at_ns")),
            }
            observed["verified_local_reference"] = all(observed["checks"].values())
        except (OSError, ValueError, TypeError) as exc:
            observed["error"] = str(exc)
        observations.append(observed)
    return observations


def source_hashes():
    hashes = compute_source_hashes(REPO_ROOT)
    for name in ("scripts/run_rat_local_file_smoke.py", "rat/kernel/capabilities/documents.py",
                 "rat/engine/book_pages.py", "rat/engine/completion.py", "rat/ui/chat_session.py",
                 "rat/engine/context_snapshot.py", "rat/engine/runtime_context.py",
                 "rat/engine/snapshot.schema.json", "rat/ui/assistant_presenter.py",
                 "rat/ui/compact_results.py", "rat/ui/chat_stream.py", "rat/ui/experience.py"):
        path = REPO_ROOT / name
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return hashes


def run_local_file_smoke(*, file_path, output, model, db_path=None, requests=None,
                         topic=None, passage_query=None, max_steps=5,
                         timeout_s=60.0, max_model_calls=15, plan_tasks=True, discover_tools=False,
                         structured_context=False, native_limits=False):
    step_limit, timeout_limit = (8, 90) if native_limits else (5, 60)
    if (type(max_steps) is not int or not 1 <= max_steps <= step_limit
            or not math.isfinite(timeout_s) or not 0 < timeout_s <= timeout_limit
            or type(max_model_calls) is not int or not 1 <= max_model_calls <= 15):
        raise ValueError(f"Limits: 1..{step_limit} steps, timeout >0 and <={timeout_limit} seconds, 1..15 model calls")
    if requests is not None and (not 1 <= len(requests) <= 3
                                  or any(not isinstance(q, str) or not q.strip() for q in requests)):
        raise ValueError("Supply 1..3 nonempty requests")
    output = validate_output_path(output)
    database_path = Path(db_path or config.db_path).expanduser().resolve(strict=True)
    db = Database(str(database_path), read_only=True)
    try:
        source = validate_source(file_path, db)
        prompts = list(requests) if requests is not None else default_requests(source, topic, passage_query)
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        output.chmod(0o700)
        client = BoundedSLMEngine(model=model, timeout_s=timeout_s, max_calls=max_model_calls)
        journal = output / "raw_model_calls.jsonl"
        journal.touch(mode=0o600, exist_ok=False)
        client.record_path = journal
        hashes_start = source_hashes()
        report = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "collection_status": "running", "review_status": "pending", "quality_success": None,
            "evidence_scope": "actual_local_file_exposed_development_smoke_not_research_benchmark",
            "stage0_changed": False, "sources_are_artificial": False,
            "native_equivalence_verified": False, "native_click_observed": False,
            "source": source, "source_sha256": hashes_start,
            "database": {"path": str(database_path), "read_only": True},
            "configuration": {"model": client.model, "ollama_url": client.ollama_url,
                              "plan_tasks": plan_tasks, "discover_tools": discover_tools,
                              "structured_context": structured_context,
                              "native_limits": native_limits,
                              "max_steps_per_turn": max_steps,
                              "timeout_s_per_call": timeout_s, "max_completion_tokens_per_call": 640,
                              "max_model_calls": max_model_calls, "requested_turns": len(prompts)},
            "timing_scope": "measured client online wall time; includes inference/tools; excludes native GUI",
            "token_scope": "all observed call prompt/completion counts; unknown on failed or missing responses",
            "privacy": {"private_output": True, "original_pdf_copied": False,
                        "raw_document_text_may_be_present": True, "do_not_commit_or_upload": True},
            "turns": [],
        }
        write_json(output / "report.json", report)
        history, task_state, previous_sources = ConversationHistory(), {}, []
        started = time.perf_counter()
        try:
            runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True,
                                       plan_tasks=plan_tasks, discover_tools=discover_tools,
                                       structured_context=structured_context, model_client=client)
            for index, query in enumerate(prompts, start=1):
                if client.calls_started >= max_model_calls:
                    report["collection_status"] = "budget_exhausted"
                    break
                prior_messages, prior_refs = history.messages_with_turn_ids(), history.turn_references()
                snap = history.begin_turn(query)
                cursor = len(client.call_Records)
                tick = time.perf_counter()
                response = runtime.run(
                    query, max_steps=max_steps, history=prior_messages, previous_sources=previous_sources,
                    turn_ref=snap.to_turn_ref(history.conversation_id), execution_id=snap.execution_id,
                    conversation_id=history.conversation_id, turn_references=prior_refs,
                    task_state=dict(task_state), max_verification_repairs=1,
                )
                if not response.error and response.task_state_updated:
                    task_state = dict(response.task_state)
                previous_sources = response.sources or previous_sources
                metadata = {"execution_id": response.execution_id,
                            "artifact_refs": [{"artifact_id": a.id, "revision": a.revision}
                                              for a in response.artifacts],
                            "note_event_ids": [e["event_id"] for e in response.note_events],
                            "task_state": dict(task_state), "reconciliation": response.reconciliation,
                            "turn_contract": response.turn_contract}
                if response.error:
                    history.fail_turn(snap.turn_id, "cancelled" if response.error == "cancelled" else "failed",
                                      error=response.error, partial_answer=response.answer, **metadata)
                elif response.pending_input_request:
                    history.fail_turn(snap.turn_id, "needs_input", partial_answer=response.answer, **metadata)
                else:
                    history.complete_turn(snap.turn_id, response.answer, **metadata)
                calls = client.call_Records[cursor:]
                entry = {"turn_index": index, "query": query, "turn_id": snap.turn_id,
                         "execution_id": snap.execution_id,
                         "execution_id_matched": response.execution_id == snap.execution_id,
                         "online_wall_time_ms": round((time.perf_counter() - tick) * 1000, 2),
                         "prior_messages": prior_messages, "prior_turn_references": prior_refs,
                         "response": asdict(response), "raw_model_calls": calls,
                         "token_accounting": token_accounting(calls),
                         "file_attachment_observations": verify_file_artifacts(response.artifacts, source),
                         "quality_success": None, "review_status": "pending"}
                report["turns"].append(entry)
                write_json(output / "report.json", report)
                print(json.dumps({"turn": index, "runtime_error": response.error,
                                  "seconds": round(entry["online_wall_time_ms"] / 1000, 2),
                                  "quality_success": None}), flush=True)
                if client.budget_rejections:
                    report["collection_status"] = "budget_exhausted"
                    break
            else:
                report["collection_status"] = "completed"
        except ModelCallBudgetExceeded as exc:
            report["collection_status"] = "budget_exhausted"
            report["budget_stop_reason"] = str(exc)
        except Exception as exc:
            report["collection_status"] = "collector_error"
            report["collector_error"] = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            report["online_wall_time_ms"] = round((time.perf_counter() - started) * 1000, 2)
            report["model_calls_started"] = client.calls_started
            report["budget_rejections"] = client.budget_rejections
            report["token_accounting"] = token_accounting(client.call_Records)
            report["journal_errors"] = [c["journal_error"] for c in client.call_Records if c.get("journal_error")]
            report["source_sha256_end"] = source_hashes()
            report["source_changed_during_run"] = [
                name for name in hashes_start if hashes_start[name] != report["source_sha256_end"][name]]
            report["history"] = [turn.to_dict() for turn in history.turns()]
            write_json(output / "report.json", report)
        return report
    finally:
        db.get_connection().close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file-path", type=Path, required=True, help="Existing, exactly indexed PDF; never copied")
    parser.add_argument("--output", type=Path, required=True, help="Fresh private directory outside Git or ignored .rat")
    parser.add_argument("--db-path", type=Path, help="Existing index; opened read-only")
    parser.add_argument("--model", default=config.assistant_model or config.ollama_model, help="Installed Ollama override only")
    parser.add_argument("--topic", help="Document topic for the first request")
    parser.add_argument("--passage-query", help="Concise content keywords for the second request")
    parser.add_argument("--request", action="append", help="Override requests, repeat at most three times")
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--max-model-calls", type=int, default=15)
    parser.add_argument("--no-plan", action="store_true", help="Collect with the initial planner disabled")
    parser.add_argument("--discover-tools", action="store_true", help="Use the app's on-demand tool catalog")
    parser.add_argument("--structured-context", action="store_true", help="Expose full typed context to the model for diagnostics")
    parser.add_argument("--native-limits", action="store_true", help="Allow the GUI's 8 steps and 90 seconds per call; global call budget remains 15")
    args = parser.parse_args(argv)
    try:
        report = run_local_file_smoke(file_path=args.file_path, output=args.output, db_path=args.db_path,
                                      model=args.model, requests=args.request, topic=args.topic,
                                      passage_query=args.passage_query, max_steps=args.max_steps,
                                      timeout_s=args.timeout, max_model_calls=args.max_model_calls,
                                      plan_tasks=not args.no_plan, discover_tools=args.discover_tools,
                                      structured_context=args.structured_context, native_limits=args.native_limits)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"collection_status": report["collection_status"], "review_status": "pending",
                      "quality_success": None, "model_calls_started": report["model_calls_started"]}))
    return 0 if report["collection_status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
