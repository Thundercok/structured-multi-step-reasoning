"""Unit and integration tests for Smart Notes Capability, NoteVerifier, and SoL-Pi Observation Pack.

Follows the invariant rule: 'TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.'
"""
import copy
import json
import pytest

from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.verification import NoteVerifier, ExecutionEvidence, VerificationStatus
from rat.kernel import ActionDispatcher, ArtifactStore, build_default_registry
from rat.kernel.contracts import Artifact
from rat.kernel.capabilities.smart_notes import (
    create_smart_notes_capability,
    deterministic_note_synthesizer,
    observation_pack_formatter,
)


def test_deterministic_note_synthesizer_tarot():
    raw_tarot = (
        "mua gì tặng bạn gái tôi vào ngày 20/10. "
        "9 wands, 2 pentacles rev, hierophant rev, the world rev, 10 pentacles rev. "
        "bạn gái đang stress deadline, đau vai gáy nhiều ngày, nhà đang giục cưới và áp lực tiền bạc. "
        "dị ứng mấy món quà hình thức hoa to sáo rỗng. "
        "tính đi fine dining, làm spa và một night together."
    )
    res = deterministic_note_synthesizer(
        raw_content=raw_tarot,
        domain="auto",
        focus_question="Mua gì tặng bạn gái 20/10",
    )

    assert res["artifact_kind"] == "structured_note"
    assert "note-" in res["note_id"]
    assert res["domain"] in ("analysis", "decision")
    assert len(res["key_facts"]) >= 5
    assert any("9 wands" in f["fact"].lower() for f in res["key_facts"])
    assert any("2 pentacles" in f["fact"].lower() for f in res["key_facts"])
    assert len(res["risks_and_constraints"]) >= 1
    assert any("tránh" in r.lower() or "dị ứng" in r.lower() for r in res["risks_and_constraints"])
    assert len(res["action_items"]) >= 1
    assert "# 📋" in res["markdown_rendered"]
    assert "### 🔍 Dữ kiện Nền tảng" in res["markdown_rendered"]
    assert "### ✅ Kế hoạch Hành động" in res["markdown_rendered"]


def test_deterministic_note_synthesizer_technical():
    raw_tech = (
        "Hôm nay kiểm tra thấy latency tăng lên 4500ms khi gọi chat_with_meta qua SLM. "
        "Nghi ngờ do num_ctx tăng lên 8192 và prompt phình to vì chứa raw tool observation dài. "
        "Tránh việc gửi nguyên cả bảng dữ liệu uncompressed vào prompt. "
        "Cần kiểm tra cache hit rate, giảm max_tokens xuống 640 và bật Observation Pack."
    )
    res = deterministic_note_synthesizer(
        raw_content=raw_tech,
        domain="auto",
        title="Điều tra Latency SLM",
    )

    assert res["artifact_kind"] == "structured_note"
    assert res["domain"] == "technical"
    assert res["title"] == "Điều tra Latency SLM"
    assert len(res["key_facts"]) >= 1
    assert len(res["risks_and_constraints"]) >= 1
    assert any("tránh" in r.lower() for r in res["risks_and_constraints"])
    assert len(res["action_items"]) >= 1
    assert any("kiểm tra" in item["task"].lower() or "bật" in item["task"].lower() for item in res["action_items"])


def test_note_verifier_pass():
    raw = "bài rút 9 wands và 2 pentacles rev, bạn gái đau vai gáy, tránh hoa to, cần đặt spa thư giãn."
    res = deterministic_note_synthesizer(raw)
    verifier = NoteVerifier()

    evidence = ExecutionEvidence(
        id="ev-1",
        operation="synthesize_smart_note",
        args={"raw_content": raw},
        result=res,
        sha256="fake_sha",
    )
    report = verifier.check_execution(evidence)

    assert report.status == VerificationStatus.PASS
    assert "checked" in report.to_dict()
    assert "fact_grounding" in report.checked


def test_note_verifier_fail_ungrounded_facts():
    raw = "bài rút 9 wands và 2 pentacles rev, bạn gái đau vai gáy."
    res = deterministic_note_synthesizer(raw)
    # Intentionally inject an ungrounded hallucination not present in raw
    res["key_facts"].append({"fact": "mua phi cơ riêng và du thuyền triệu đô", "source": "hallucination"})

    verifier = NoteVerifier()
    evidence = ExecutionEvidence(
        id="ev-2",
        operation="synthesize_smart_note",
        args={"raw_content": raw},
        result=res,
        sha256="fake_sha",
    )
    report = verifier.check_execution(evidence)

    assert report.status == VerificationStatus.FAIL
    assert "grounding" in report.scope
    assert "không có căn cứ" in report.reason


def test_sol_pi_observation_pack_compression():
    raw_tarot = (
        "mua gì tặng bạn gái tôi vào ngày 20/10. "
        "9 wands, 2 pentacles rev, hierophant rev, the world rev, 10 pentacles rev. "
        "bạn gái đang stress deadline, đau vai gáy nhiều ngày, nhà đang giục cưới và áp lực tiền bạc. "
        "dị ứng mấy món quà hình thức hoa to sáo rỗng. "
        "tính đi fine dining, làm spa và một night together."
    )
    full_note = deterministic_note_synthesizer(raw_tarot)
    packed_view = observation_pack_formatter(full_note)

    full_serialized = json.dumps(full_note, ensure_ascii=False)
    packed_serialized = json.dumps(packed_view, ensure_ascii=False)

    full_chars = len(full_serialized)
    packed_chars = len(packed_serialized)

    compression_ratio = 1.0 - (packed_chars / full_chars)

    # Observation Pack must reduce character/token footprint by at least 65%
    assert compression_ratio >= 0.65
    assert packed_view["artifact_ref"] == full_note["note_id"]
    assert packed_view["status"] == "uncommitted_note"
    assert packed_view["title"] == full_note["title"]
    assert packed_view["domain"] == full_note["domain"]


def test_smart_notes_capability_registration_and_dispatch():
    store = ArtifactStore()
    registry = build_default_registry()
    op = registry.get_operation("synthesize_smart_note")
    assert op is not None
    assert op.verifier is not None
    assert op.observation_formatter is not None

    dispatcher = ActionDispatcher(registry, store)
    raw_input = "Lỗi timeout khi gọi resident model, cần kiểm tra model_path và giảm context."
    res = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": raw_input}, context={"artifact_store": store})

    assert res.status == "success"
    assert res.artifact is not None
    assert res.artifact.kind == "structured_note"
    assert res.result["artifact_kind"] == "structured_note"

    stored_art = store.get(res.result["note_id"])
    assert stored_art is not None
    assert stored_art.payload["title"] == res.result["title"]


def test_telemetry_tracking_in_runtime():
    store = ArtifactStore()
    registry = build_default_registry()

    # Create dummy model callable that simulates 1 tool call then final answer
    def dummy_model(goal, trajectory):
        if len(trajectory) == 0:
            return ModelDecision(
                thought="Tôi sẽ tổ chức ghi chú này.",
                tool_name="synthesize_smart_note",
                tool_args={"raw_content": "9 wands, 2 pentacles rev, bạn gái đau vai gáy, nên làm spa."},
                prompt_tokens=420,
                completion_tokens=65,
                cached_tokens=None,
            )
        return ModelDecision(
            thought="Đã hoàn tất.",
            final_answer="Bản ghi chú đã được lưu và kiểm chứng thành công.",
            prompt_tokens=310,
            completion_tokens=45,
            cached_tokens=None,
        )

    runtime = AssistantRuntime(
        registry=registry,
        artifact_store=store,
        model_callable=dummy_model,
        use_live_model=False,
    )

    resp = runtime.run("Hãy tổng hợp ghi chú", max_steps=4)

    assert resp.error is None
    assert resp.prompt_tokens == 730  # 420 + 310
    assert resp.completion_tokens == 110  # 65 + 45
    assert resp.total_tokens == 840
    assert resp.cached_tokens is None  # Accurately reports None when backend doesn't provide cache

    telemetry = resp.telemetry_breakdown
    assert telemetry["prompt_tokens"] == 730
    assert telemetry["completion_tokens"] == 110
    assert telemetry["token_usage_known"] is True
    assert "latencies" in telemetry
    assert telemetry["latencies"]["model_ms"] >= 0
    assert telemetry["latencies"]["tool_ms"] >= 0
    assert telemetry["latencies"]["total_ms"] >= 0


def test_multi_turn_observation_pack_context_savings():
    store = ArtifactStore()
    registry = build_default_registry()

    raw_note = (
        "Trải bài 20/10: 9 of wands, 2 of pentacles rev, hierophant rev, the world rev, 10 of pentacles rev. "
        "Bạn gái đau mỏi vai gáy nghiêm trọng, mất ngủ, áp lực deadline dồn dập, nhà giục cưới. "
        "Tuyệt đối tránh quà hình thức sáo rỗng hoa to phô trương. "
        "Kế hoạch: Đi spa trị liệu chuyên sâu, ăn casual fine dining, nghỉ ngơi trọn vẹn 1 đêm."
    )

    # 1. Run without observation pack
    runtime_unpacked = AssistantRuntime(
        registry=registry,
        artifact_store=store,
        use_live_model=False,
        enable_observation_pack=False,
    )
    raw_res = deterministic_note_synthesizer(raw_note)
    unpacked_obs = runtime_unpacked._model_observation(raw_res)

    # 2. Run with observation pack enabled (SoL-Pi)
    runtime_packed = AssistantRuntime(
        registry=registry,
        artifact_store=store,
        use_live_model=False,
        enable_observation_pack=True,
    )
    packed_obs = runtime_packed._model_observation(raw_res)

    unpacked_json = json.dumps(unpacked_obs, ensure_ascii=False)
    packed_json = json.dumps(packed_obs, ensure_ascii=False)

    unpacked_len = len(unpacked_json)
    packed_len = len(packed_json)

    savings_ratio = 1.0 - (packed_len / unpacked_len)

    assert savings_ratio >= 0.65
    assert packed_obs["status"] == "uncommitted_note"
    assert packed_obs["artifact_ref"] == raw_res["note_id"]


def test_update_note_action_item_via_dispatcher():
    store = ArtifactStore()
    registry = build_default_registry()
    dispatcher = ActionDispatcher(registry, store)

    raw_note = "Mua quà 20/10: 9 wands, bạn gái mệt. Cần đặt spa trị liệu và mua nến thơm."
    res1 = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": raw_note}, context={"artifact_store": store})
    assert res1.status == "success"
    art1 = res1.artifact
    assert art1.revision == 1

    # Now toggle action item via dispatcher (Option 2 interactive action)
    res2 = dispatcher.execute_operation(
        "update_note_action_item",
        {"task_match": "spa", "done": True, "artifact_id": art1.id, "revision": art1.revision},
        context={"artifact_store": store},
    )
    assert res2.status == "success"
    art2 = res2.artifact
    assert art2.revision == 2
    assert art2.id == art1.id

    # Verify action item is checked
    items = art2.payload["action_items"]
    spa_item = next(item for item in items if "spa" in item["task"].lower())
    assert spa_item["done"] is True
    assert "- [x]" in art2.payload["markdown_rendered"]


def test_expand_note_section_via_dispatcher():
    store = ArtifactStore()
    registry = build_default_registry()
    dispatcher = ActionDispatcher(registry, store)

    raw_note = "Mua quà 20/10: 9 wands, bạn gái đau vai gáy. Tránh đồ hình thức sáo rỗng."
    res1 = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": raw_note}, context={"artifact_store": store})
    art1 = res1.artifact

    # Expand section via follow-up
    res2 = dispatcher.execute_operation(
        "expand_note_section",
        {
            "section_heading": "Phân tích Logic",
            "expansion_query": "Nghiên cứu thêm về bẫy gò bó của Fine Dining",
            "expansion_content": "Phân tích bổ sung: bẫy gò bó của Fine Dining gây áp lực ngồi giữ kẽ 2 tiếng, không hợp bạn gái đang mệt mỏi.",
            "artifact_id": art1.id,
            "revision": art1.revision,
        },
        context={"artifact_store": store},
    )
    assert res2.status == "success"
    art2 = res2.artifact
    assert art2.revision == 2
    assert "bẫy gò bó của Fine Dining" in art2.payload["markdown_rendered"]
    assert any("expanded" in s.get("badges", []) for s in art2.payload["analysis_sections"])


def test_note_available_actions():
    from rat.kernel.capabilities.smart_notes import note_available_actions

    raw_note = "9 wands, bạn gái đau vai gáy. Cần đặt spa và mua nến thơm."
    res = deterministic_note_synthesizer(raw_note)
    art = Artifact(id="art-test-1", kind="structured_note", revision=1, payload=res)

    actions = note_available_actions(art)
    assert len(actions) >= 2
    assert any("update_note_action_item" == a.operation_name for a in actions)
    assert any("expand_note_section" == a.operation_name for a in actions)
    for a in actions:
        assert a.target_artifact_id == "art-test-1"
        assert a.target_revision == 1


def test_document_read_observation_pack_direct():
    from rat.kernel.capabilities.documents import document_read_observation_pack

    # Short content (< 400 chars) -> untouched
    short_res = {
        "found": True,
        "path": "/path/to/short.txt",
        "filename": "short.txt",
        "content": "This is a brief summary under four hundred characters.",
        "total_chars": 54,
        "truncated": False,
    }
    short_pack = document_read_observation_pack(short_res)
    assert short_pack == short_res
    assert short_pack["content"] == short_res["content"]

    # Long content (3000 chars) -> compressed
    long_text = "HEAD SECTION: Introduction to Operating Systems and Concurrency. " + ("A" * 2900) + " TAIL SECTION: Final Conclusion."
    long_res = {
        "found": True,
        "path": "/path/to/long_os_book.txt",
        "filename": "long_os_book.txt",
        "content": long_text,
        "total_chars": len(long_text),
        "truncated": False,
    }
    long_pack = document_read_observation_pack(long_res)
    assert long_pack["found"] is True
    assert long_pack["total_chars"] == len(long_text)
    assert long_pack["observation_pack_status"] == "compressed_sol_pi"
    assert "SoL-Pi Observation Pack: lược bớt" in long_pack["content"]
    assert "HEAD SECTION:" in long_pack["content"]
    assert "TAIL SECTION:" in long_pack["content"]

    # Compression effectiveness
    original_size = len(json.dumps(long_res))
    compressed_size = len(json.dumps(long_pack))
    compression_ratio = 1.0 - (compressed_size / original_size)
    assert compression_ratio >= 0.70  # Over 70% reduction in observation size


def test_document_read_observation_pack_runtime_integration(tmp_path):
    from rat.crawler.db import Database
    from rat.kernel.capabilities.documents import create_documents_capability

    # 1. Create a dummy db and index a long document
    db_file = tmp_path / "test_rat.db"
    db = Database(str(db_file))
    doc_file = tmp_path / "research_paper.txt"
    full_text = "BEGIN RESEARCH PAPER:\n" + ("Distributed Systems and Structured Reasoning Evidence. " * 50) + "\nEND RESEARCH PAPER."
    doc_file.write_text(full_text, encoding="utf-8")
    db.upsert_document({
        "file_path": str(doc_file),
        "file_name": doc_file.name,
        "file_ext": doc_file.suffix,
        "file_size": len(full_text),
        "summary": "Research Paper on Distributed Systems",
        "created_at": 1000.0,
        "modified_at": 1000.0,
        "indexed_at": 1000.0,
        "md5_hash": "dummy_md5",
        "content_text": full_text,
    })

    store = ArtifactStore()
    registry = build_default_registry()
    # Ensure documents capability uses this test db
    registry.register_capability(create_documents_capability(db=db))
    dispatcher = ActionDispatcher(registry, store)

    # 2. Execute read_document via dispatcher
    dispatch_res = dispatcher.execute_operation("read_document", {"file_path": str(doc_file)}, context={"artifact_store": store})
    assert dispatch_res.status == "success"
    raw_read_result = dispatch_res.result

    # 3. Check ArtifactStore has full 100% ground truth
    art = store.find_by_kind("document_content")[0]
    assert art.payload["content"] == full_text[:3000].strip()

    # 4. Compare runtime observations with enable_observation_pack True vs False
    runtime_unpacked = AssistantRuntime(
        db=db,
        registry=registry,
        artifact_store=store,
        use_live_model=False,
        enable_observation_pack=False,
    )
    obs_unpacked = runtime_unpacked._model_observation(raw_read_result, op_name="read_document")
    assert obs_unpacked["content"] == full_text[:3000].strip()
    assert "observation_pack_status" not in obs_unpacked

    runtime_packed = AssistantRuntime(
        db=db,
        registry=registry,
        artifact_store=store,
        use_live_model=False,
        enable_observation_pack=True,
    )
    obs_packed = runtime_packed._model_observation(raw_read_result, op_name="read_document")
    assert obs_packed["observation_pack_status"] == "compressed_sol_pi"
    assert len(obs_packed["content"]) < len(obs_unpacked["content"])
    assert "BEGIN RESEARCH PAPER:" in obs_packed["content"]
    assert "END RESEARCH PAPER." in obs_packed["content"]

    # Verify context savings
    unpacked_bytes = len(json.dumps(obs_unpacked, ensure_ascii=False))
    packed_bytes = len(json.dumps(obs_packed, ensure_ascii=False))
    savings = 1.0 - (packed_bytes / unpacked_bytes)
    assert savings >= 0.65



def test_note_has_one_canonical_id_and_preserves_original_source():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    raw = "Cần kiểm tra cache 4500ms."
    created = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": raw})
    assert len(store.list()) == 1
    assert created.result["artifact_id"] == created.result["note_id"] == created.artifact.id
    assert created.artifact.payload["raw_content"] == raw
    packed = observation_pack_formatter(created.result)
    assert packed["status"] == "note_reference_available"
    assert store.get(packed["artifact_ref"]).payload == created.result
    assert "Đã kiểm chứng" not in created.result["markdown_rendered"]


def test_duplicate_input_creates_distinct_artifacts_without_orphan_commits():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    first = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Cần kiểm tra cache."})
    second = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Cần kiểm tra cache."})
    assert first.status == second.status == "success"
    assert first.artifact.id != second.artifact.id
    assert len(store.list()) == 2


def test_extractive_tool_does_not_invent_actions_or_analysis_or_call_model():
    class ForbiddenModel:
        def chat_with_meta(self, *args, **kwargs):
            pytest.fail("Hidden nested model call")
    dispatcher = ActionDispatcher(build_default_registry(), ArtifactStore())
    result = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Paper reports 42 samples."},
                                          context={"model_client": ForbiddenModel()})
    assert result.status == "success"
    assert result.result["action_items"] == []
    assert result.result["risks_and_constraints"] == []
    assert "kiệt sức" not in result.result["markdown_rendered"]
    assert result.result["synthesis_mode"] == "extractive"


def test_no_note_answer_pass_without_evidence():
    assert NoteVerifier().check_answer("Chào", "Chào bạn", ()) is None


def test_shared_word_cannot_certify_false_numeric_claim():
    raw = "latency là 4500ms"
    result = deterministic_note_synthesizer(raw)
    result["key_facts"] = [{"fact": "latency là 1ms", "source": "input"}]
    report = NoteVerifier().check_execution(ExecutionEvidence("ev", "synthesize_smart_note", {"raw_content": raw}, result, ""))
    assert report.status == VerificationStatus.FAIL


def test_missing_and_ambiguous_task_do_not_mutate_note():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    created = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Cần kiểm tra cache, cần kiểm tra model."})
    for args in ({"task_match": "không tồn tại"}, {"task_match": "kiểm tra"}, {"item_index": 99}):
        result = dispatcher.execute_operation("update_note_action_item", {**args, "artifact_id": created.artifact.id, "revision": 1})
        assert result.status == "error"
        assert store.get(created.artifact.id).revision == 1
        assert store.get(created.artifact.id).payload == created.artifact.payload


def test_expansion_instruction_alone_is_not_analysis():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    created = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "latency 4500ms"})
    result = dispatcher.execute_operation("expand_note_section", {"artifact_id": created.artifact.id,
                                          "revision": 1, "expansion_query": "Vì sao chậm?"})
    assert result.status == "error"
    assert store.get(created.artifact.id).revision == 1


def test_note_source_hash_and_requested_toggle_are_checked():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    created = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Cần kiểm tra cache."})
    args = {"artifact_id": created.artifact.id, "revision": 1, "item_index": 1, "done": True}
    updated = dispatcher.execute_operation("update_note_action_item", args)
    assert updated.status == "success"
    ev = lambda result: ExecutionEvidence("ev", "update_note_action_item", args, result, "")
    verifier = NoteVerifier()
    assert verifier.check_execution(ev(updated.result)).status == VerificationStatus.PASS
    wrong = copy.deepcopy(updated.result)
    wrong["action_items"][0]["done"] = False
    assert verifier.check_execution(ev(wrong)).status == VerificationStatus.FAIL
    tampered = copy.deepcopy(updated.result)
    tampered["raw_content"] += " fake source"
    assert verifier.check_execution(ev(tampered)).status == VerificationStatus.FAIL
    assert store.get(created.artifact.id, revision=1).payload == created.artifact.payload
    stale = dispatcher.execute_operation("update_note_action_item", args)
    assert stale.status == "stale_revision"
    assert store.get(created.artifact.id).revision == 2


def test_packed_verification_wrapper_preserves_checks_and_canonical_reference():
    from rat.engine.assistant_runtime import model_observation
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    note = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": "Cần kiểm tra cache."})
    wrapped = {"observation": note.result, "verification": [{"status": "PASS", "scope": "structure"}]}
    packed = model_observation(wrapped, enable_observation_pack=True)
    assert packed["verification"] == wrapped["verification"]
    assert packed["observation"]["artifact_ref"] == note.artifact.id
    assert "markdown_rendered" not in packed["observation"]


def test_invalid_agent_proposal_cannot_commit():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    raw = "latency 4500ms"
    proposal = {k: v for k, v in deterministic_note_synthesizer(raw).items()
                if k in ("title", "domain", "summary", "key_facts", "analysis_sections", "risks_and_constraints", "action_items")}
    proposal["key_facts"] = [{"fact": "latency 1ms", "source": "raw"}]
    result = dispatcher.execute_operation("synthesize_smart_note", {"raw_content": raw, "structured_note": proposal})
    assert result.status == "error"
    assert not store.list()


def test_extractive_checklist_has_no_stale_duplicate_after_toggle():
    store = ArtifactStore()
    dispatcher = ActionDispatcher(build_default_registry(), store)
    created = dispatcher.execute_operation('synthesize_smart_note', {
        'raw_content': 'BEST-Route has a router. Việc cần làm: Đọc Section 3.'})
    assert created.status == 'success'
    assert created.result['action_items'] == [{'task': 'Việc cần làm: Đọc Section 3.', 'done': False}]
    updated = dispatcher.execute_operation('update_note_action_item', {
        'artifact_id': created.artifact.id, 'revision': 1, 'item_index': 1, 'done': True})
    assert updated.status == 'success'
    assert '- [x] Việc cần làm: Đọc Section 3.' in updated.result['markdown_rendered']
    assert '- [ ]' not in updated.result['markdown_rendered']
    assert created.artifact.payload['action_items'][0]['done'] is False
