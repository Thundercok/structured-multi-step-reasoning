"""Reproducible SOFTWARE fixture audit; never live model/UI acceptance.

JSON byte sizes compare representations of the same note. They are not token,
inference-cost, latency-saving, or semantic-equivalence measurements.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.verification import ExecutionEvidence, NoteVerifier
from rat.kernel import ActionDispatcher, ArtifactStore, build_default_registry
from rat.kernel.capabilities.smart_notes import observation_pack_formatter


def run_audit(output_dir="audit/rat_smart_notes_software_20261025"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    store, registry = ArtifactStore(), build_default_registry()
    dispatcher = ActionDispatcher(registry, store)
    raw = "Điều tra latency 4500ms. Cần kiểm tra cache. Tránh gửi bảng dữ liệu dài vào prompt."
    create_args = {"raw_content": raw, "title": "Ghi chú kỹ thuật"}
    created = dispatcher.execute_operation("synthesize_smart_note", create_args)
    assert created.status == "success", created.error
    toggle_args = {"artifact_id": created.artifact.id, "revision": 1, "item_index": 1, "done": True}
    toggled = dispatcher.execute_operation("update_note_action_item", toggle_args)
    assert toggled.status == "success", toggled.error
    expand_args = {"artifact_id": created.artifact.id, "revision": 2,
                   "section_heading": "Phân tích", "expansion_query": "Cần đo thêm gì?",
                   "expansion_content": "Đề xuất kiểm tra cache; chưa có số đo cache để kết luận nguyên nhân."}
    expanded = dispatcher.execute_operation("expand_note_section", expand_args)
    assert expanded.status == "success", expanded.error
    verifier = NoteVerifier()
    checks = [verifier.check_execution(ExecutionEvidence(str(i), op, args, result.result, "")).to_dict()
              for i, (op, args, result) in enumerate([
                  ("synthesize_smart_note", create_args, created),
                  ("update_note_action_item", toggle_args, toggled),
                  ("expand_note_section", expand_args, expanded)])]
    packed = observation_pack_formatter(expanded.result)
    size = lambda value: len(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    full_bytes, packed_bytes = size(expanded.result), size(packed)

    from rat.kernel.capabilities.documents import document_read_observation_pack
    doc_raw = {"found": True, "path": "/path/dummy.txt", "filename": "dummy.txt",
               "content": "HEAD: Operating systems and structured reasoning. " + ("Evidence notes. " * 150) + " TAIL: Finished.",
               "total_chars": 2350, "truncated": False}
    doc_packed = document_read_observation_pack(doc_raw)
    doc_full_bytes, doc_packed_bytes = size(doc_raw), size(doc_packed)

    def fixture_model(goal, trajectory):
        if not trajectory:
            return ModelDecision("Cần tạo ghi chú kỹ thuật từ nguồn", tool_name="synthesize_smart_note", tool_args=create_args,
                                 prompt_tokens=520, completion_tokens=85)
        return ModelDecision("Hoàn thành ghi chú", final_answer="Đã lưu ghi chú; diễn giải chưa được xác minh.",
                             prompt_tokens=280, completion_tokens=40)

    runtime = AssistantRuntime(registry=registry, model_callable=fixture_model, use_live_model=False,
                               enable_observation_pack=True)
    response = runtime.run("Tạo ghi chú kỹ thuật", max_steps=3)
    report = {
        "timestamp": datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
        "evidence_kind": "synthetic_software_fixture", "live_inference": False, "ui_acceptance": False,
        "source_kind": "authored_test_input", "source_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "checks": checks, "fixture_runtime_error": response.error,
        "representation_sizes": {"full_json_bytes": full_bytes, "packed_json_bytes": packed_bytes,
            "byte_reduction_pct": round(100 * (1 - packed_bytes / full_bytes), 2),
            "semantic_equivalence_checked": False, "model_token_savings_measured": False},
        "document_observation_pack_sizes": {
            "full_json_bytes": doc_full_bytes,
            "packed_json_bytes": doc_packed_bytes,
            "byte_reduction_pct": round(100 * (1 - doc_packed_bytes / doc_full_bytes), 2),
        },
        "synthetic_runtime_telemetry": {"provenance": "assigned_by_fixture_model",
            "prompt_tokens": response.prompt_tokens, "completion_tokens": response.completion_tokens,
            "total_tokens": response.total_tokens, "cached_tokens": response.cached_tokens},
        "canonical_artifact_id": created.artifact.id, "latest_revision": expanded.artifact.revision,
        "passed": all(c["status"] == "PASS" for c in checks) and response.error is None,
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    (out / "artifacts.json").write_text(json.dumps([a.to_dict() for a in store.get_history(created.artifact.id)],
                                                   ensure_ascii=False, indent=2))
    (out / "README.md").write_text(
        "# Smart Notes software fixture audit\n\n"
        f"Software checks: {'PASS' if report['passed'] else 'FAIL'}. No live model or UI acceptance.\n\n"
        "The 800 prompt / 125 completion tokens are assigned by fixture_model. "
        "They test accounting only and are not inference measurements.\n\n"
        f"Serialized JSON sizes: {full_bytes} bytes full / {packed_bytes} bytes packed. "
        "This makes no claim of semantic equivalence; it measures representation size only. "
        "It does not measure tokenizer counts, full inference cost, or online speedup.\n\n"
        f"Document Observation Pack: {doc_full_bytes} bytes full / {doc_packed_bytes} bytes packed "
        f"({round(100 * (1 - doc_packed_bytes / doc_full_bytes), 2)}% representation reduction).\n\n"
        "PASS applies to input excerpts, source hash, structure and requested mutations. "
        "Summaries, interpretations and suggested actions remain unverified. "
        "Artifacts and revisions are in artifacts.json.\n")
    print(json.dumps({"report": str(out / "report.json"), "passed": report["passed"]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="audit/rat_smart_notes_software_20261025")
    args = parser.parse_args()
    raise SystemExit(0 if run_audit(args.output_dir)["passed"] else 1)
