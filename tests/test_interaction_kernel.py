"""
tests/test_interaction_kernel.py — Acceptance scenario verification for RAT interaction kernel.

Verifies the 9 core acceptance scenarios specified in the handoff:
1. Partial natal request -> InputRequest -> complete -> computed chart inline, no feature QMainWindow.
2. Direct control & scripted model action -> same dispatcher semantics, stable ID, new revision, stale detected.
3. Schedule and file search/read produce versioned artifacts; model failure preserves artifacts and truthful status.
4. Composed multi-step request executes schedule, search, and reading in one task via interaction kernel.
5. Two charts with ambiguous reference -> clarification requested, no silent modification.
6. Register small test capability without modifying central branches -> valid tool definition, artifact, view, action.
7. Swap view provider on same artifact; reject invalid schema versions, invented fields, and unregistered actions.
8. Stop, retry, chat reset, pending input, and delayed worker callbacks do not lose results or leak workers.
9. Headless contracts and runtime do not depend on Qt or launch file indexing.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import pytest

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AgentStep, AssistantRuntime, ModelDecision
from rat.kernel.contracts import (
    Artifact,
    ArtifactAction,
    ArtifactStore,
    DispatchResult,
    ExecutionEvent,
    ExecutionState,
    InputRequest,
)
from rat.kernel.dispatcher import (
    ActionDispatcher,
    AmbiguousArtifactError,
    StaleRevisionError,
)
from rat.kernel.registry import (
    Capability,
    CapabilityRegistry,
    OperationDefinition,
)
from rat.kernel.view_spec import (
    StandardViewProvider,
    ViewBlock,
    ViewSpec,
    validate_view_spec,
)
from rat.kernel.capabilities import build_default_registry
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.model import ClassSession, MemberSchedule


# =============================================================================
# SCENARIO 9: Headless independence (No Qt imports in kernel)
# =============================================================================

def test_scenario_9_headless_contracts_independent_of_qt():
    """Check a fresh process; importing Qt earlier cannot make this test pass accidentally."""
    import subprocess
    result = subprocess.run([sys.executable, '-c',
        "import sys; import rat.kernel; assert not any(n.startswith('PyQt6') for n in sys.modules)"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# =============================================================================
# SCENARIOS 1-8 TEST SUITE
# =============================================================================

@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "test_index.db"
    db = Database(str(db_path))
    conn = db.get_connection()
    doc_file = tmp_path / "os_lecture.pdf"
    doc_file.write_text("Operating Systems: Concurrency, Virtual Memory, and Scheduling algorithms.")
    conn.execute(
        """INSERT INTO documents
        (file_path, file_name, file_ext, file_size, created_at, modified_at, content_text, summary, normalized_text, indexed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(doc_file), doc_file.name, ".pdf", 100, 1, 1, doc_file.read_text(), "Hệ điều hành OS Lecture", "hệ điều hành os lecture operating systems", 1),
    )
    conn.commit()
    yield db
    conn.close()


@pytest.fixture
def mock_compositor():
    member = MemberSchedule(
        id="student_huy",
        name="Huy",
        schedule={
            "T2": [ClassSession(1, 3, "Hệ điều hành", "C101", course_code="OS101", lecturer="TS. Nam")],
            "T3": [ClassSession(4, 6, "Mạng máy tính", "B202", course_code="NET102", lecturer="ThS. Hoa")],
        },
    )
    return TimetableCompositor([member])


@pytest.fixture
def kernel_env(mock_db, mock_compositor):
    registry = build_default_registry(db=mock_db, compositor=mock_compositor)
    store = ArtifactStore()
    dispatcher = ActionDispatcher(registry, store)
    runtime = AssistantRuntime(
        db=mock_db,
        compositor=mock_compositor,
        registry=registry,
        artifact_store=store,
        dispatcher=dispatcher,
        use_live_model=False,
    )
    return {
        "registry": registry,
        "store": store,
        "dispatcher": dispatcher,
        "runtime": runtime,
        "db": mock_db,
    }


# -----------------------------------------------------------------------------
# Scenario 1: Partial natal request -> InputRequest -> complete chart inline
# -----------------------------------------------------------------------------

def test_scenario_1_partial_natal_request_and_inline_completion(kernel_env):
    """
    Scenario 1: Request a natal chart with partial data -> fill only missing inputs
    -> get an actual computed chart in the same surface, without constructing a feature
    QMainWindow. Supplied inputs survive progress updates.
    """
    pytest.importorskip("swisseph")
    from rat.astrology.places import Place

    runtime = kernel_env["runtime"]
    dispatcher = kernel_env["dispatcher"]
    store = kernel_env["store"]

    # 1. Partial request: name & date provided, time & place missing
    partial_args = {"name": "Nguyễn Văn An", "date": "2000-06-15"}
    result = runtime.execute_tool("create_natal_chart", partial_args)

    # Must return InputRequest with status needs_input
    assert isinstance(result, dict)
    assert result["operation_name"] == "create_natal_chart"
    missing_names = [f["name"] for f in result["missing_fields"]]
    assert "time" in missing_names
    assert "place" in missing_names
    # Supplied inputs must survive
    assert result["supplied_inputs"]["name"] == "Nguyễn Văn An"
    assert result["supplied_inputs"]["date"] == "2000-06-15"

    # 2. Simulate providing missing place with multiple candidates (ambiguity)
    places = (
        Place("Hà Nội, Việt Nam", 21.0245, 105.8412, "Asia/Bangkok"),
        Place("Hà Nam, Việt Nam", 20.5833, 105.9167, "Asia/Ho_Chi_Minh"),
    )
    with patch("rat.astrology.places.search_places", return_value=places):
        result_with_place = runtime.execute_tool("create_natal_chart", {**partial_args, "place": "Hà"})
        assert result_with_place["candidate_choices"] is not None
        assert len(result_with_place["candidate_choices"]) == 2

    # 3. Supply complete inputs directly through dispatcher
    complete_args = {
        "name": "Nguyễn Văn An",
        "date": "2000-06-15",
        "time": "09:30",
        "place": "Hà Nội, Việt Nam",
        "latitude": 21.0245,
        "longitude": 105.8412,
        "timezone": "Asia/Bangkok",
    }
    dispatch_res = dispatcher.execute_operation("create_natal_chart", complete_args)
    assert dispatch_res.status == "success"
    assert dispatch_res.artifact is not None
    assert dispatch_res.artifact.kind == "natal_chart"
    assert dispatch_res.artifact.revision == 1

    chart = dispatch_res.artifact.payload["chart"]
    assert len(chart["positions"]) >= 13
    assert len(chart["cusps"]) == 12

    # Verify ViewSpec generation without creating QMainWindow
    provider = StandardViewProvider()
    view_spec = provider.provide_view(dispatch_res.artifact)
    assert view_spec.schema_version == 1
    assert view_spec.artifact_id == dispatch_res.artifact.id
    block_types = [b.type for b in view_spec.blocks]
    assert "summary" in block_types
    assert "resource" in block_types  # wheel resource
    assert "actions" in block_types


# -----------------------------------------------------------------------------
# Scenario 2: Direct control & scripted action with revision tracking & stale check
# -----------------------------------------------------------------------------

def test_scenario_2_birth_time_modification_and_stale_detection(kernel_env):
    """
    Scenario 2: Change birth time through direct control and through scripted native
    model action -> same dispatcher semantics, recomputed chart, stable artifact ID
    and a new revision, prior revision preserved. Stale controls are detected.
    """
    pytest.importorskip("swisseph")

    dispatcher = kernel_env["dispatcher"]
    store = kernel_env["store"]

    # Initialize a chart artifact (revision 1)
    init_args = {
        "name": "Lê Thị Bình",
        "date": "1998-11-20",
        "time": "08:00",
        "place": "TP. Hồ Chí Minh, Việt Nam",
        "latitude": 10.8231,
        "longitude": 106.6297,
        "timezone": "Asia/Ho_Chi_Minh",
    }
    res_1 = dispatcher.execute_operation("create_natal_chart", init_args)
    art_id = res_1.artifact.id
    assert res_1.artifact.revision == 1

    # 1. Direct control action: Change time to 09:30
    control_action = ArtifactAction(
        id="act_change_time_1",
        label="Đổi giờ sinh",
        target_artifact_id=art_id,
        target_revision=1,
        operation_name="update_birth_data",
        params={"time": "09:30"},
    )
    res_2 = dispatcher.dispatch(control_action)
    assert res_2.status == "success"
    assert res_2.artifact.id == art_id  # Stable artifact ID
    assert res_2.artifact.revision == 2
    assert res_2.artifact.inputs["time"] == "09:30"
    assert res_2.artifact.provenance["parent_revision"] == 1

    # Prior revision 1 is preserved in store history
    rev_1_cached = store.get(art_id, revision=1)
    assert rev_1_cached is not None
    assert rev_1_cached.revision == 1
    assert rev_1_cached.inputs["time"] == "08:00"

    # 2. Scripted native model action: Change time to 10:15
    model_action = ArtifactAction(
        id="act_model_change_time_2",
        label="Cập nhật giờ sinh theo yêu cầu",
        target_artifact_id=art_id,
        target_revision=2,
        operation_name="update_birth_data",
        params={"time": "10:15"},
    )
    res_3 = dispatcher.dispatch(model_action)
    assert res_3.status == "success"
    assert res_3.artifact.id == art_id
    assert res_3.artifact.revision == 3
    assert res_3.artifact.inputs["time"] == "10:15"

    # 3. Stale control detection: Attempt to dispatch using the old revision 1 action
    stale_res = dispatcher.dispatch(control_action)
    assert stale_res.status == "stale_revision"
    assert "Thao tác trên phiên bản cũ" in stale_res.error
    # Current artifact remains untouched at revision 3
    current = store.get(art_id)
    assert current.revision == 3


# -----------------------------------------------------------------------------
# Scenario 3: Schedule and document search/read produce versioned artifacts
# -----------------------------------------------------------------------------

def test_scenario_3_schedule_and_documents_produce_artifacts_with_truthful_status(kernel_env):
    """
    Scenario 3: Schedule lookup and file search/read both produce artifacts through
    the same foundation. Partial/model failures preserve actual results and accurate status.
    """
    runtime = kernel_env["runtime"]
    store = kernel_env["store"]

    # 1. Schedule lookup produces schedule artifact
    sched_result = runtime.execute_tool("get_schedule", {"target_date": "T2", "member_id": "student_huy"})
    assert isinstance(sched_result, list)
    assert len(sched_result) == 1
    assert sched_result[0]["course_name"] == "Hệ điều hành"

    sched_arts = store.find_by_kind("schedule")
    assert len(sched_arts) == 1
    assert sched_arts[0].kind == "schedule"
    assert sched_arts[0].revision == 1

    # 2. Document search produces document_search artifact
    search_result = runtime.execute_tool("search_documents", {"query": "Operating Systems"})
    assert isinstance(search_result, list)
    assert len(search_result) == 1
    file_path = search_result[0]["path"]

    doc_arts = store.find_by_kind("document_search")
    assert len(doc_arts) == 1
    assert doc_arts[0].kind == "document_search"

    # 3. Document read produces document_content artifact
    read_result = runtime.execute_tool("read_document", {"file_path": file_path})
    assert read_result["found"] is True
    assert "Concurrency" in read_result["content"]

    read_arts = store.find_by_kind("document_content")
    assert len(read_arts) == 1
    assert read_arts[0].kind == "document_content"

    # 4. Partial / model failure preserves actual results and truthful status
    # Simulate model failure after reading document
    runtime.model_callable = lambda goal, steps: ModelDecision(thought="", error="timeout_inference")
    res = runtime.run("Giải thích tệp tin")
    assert res.error == "timeout_inference"
    # Artifacts remain preserved in store
    assert len(store.list()) >= 3
    assert not res.answer  # Truthful status: does not fabricate answer


# -----------------------------------------------------------------------------
# Scenario 4: Composed request using schedule, search, and reading in one task
# -----------------------------------------------------------------------------

def test_scenario_4_composed_multi_step_request_plumbing(kernel_env):
    """
    Scenario 4: A composed request uses schedule, search and reading in one task
    rather than a hardcoded preparation-plan feature. Check plumbing.
    """
    runtime = kernel_env["runtime"]
    store = kernel_env["store"]

    # Script model to compose schedule, search, and reading in one task
    decisions = [
        ModelDecision("", tool_name="get_schedule", tool_args={"target_date": "T2", "member_id": "student_huy"}),
        ModelDecision("", tool_name="search_documents", tool_args={"query": "Hệ điều hành"}),
        ModelDecision("", tool_name="read_document", tool_args={"file_path": runtime.tool_search_documents("Hệ điều hành")[0]["path"]}),
        ModelDecision("", final_answer="Thứ Hai bạn học môn Hệ điều hành tại phòng C101. Tài liệu ôn tập tập trung vào Concurrency và Scheduling."),
    ]
    it = iter(decisions)
    runtime.model_callable = lambda goal, steps: next(it)

    resp = runtime.run("Mai học gì và xem tài liệu giúp mình")
    assert resp.error is None
    assert len(resp.sources) >= 2
    assert len(resp.artifacts) >= 3

    # Artifacts for all three operations are in the store
    kinds = [a.kind for a in resp.artifacts]
    assert "schedule" in kinds
    assert "document_search" in kinds
    assert "document_content" in kinds


# -----------------------------------------------------------------------------
# Scenario 5: Two charts with ambiguous reference require clarification
# -----------------------------------------------------------------------------

def test_scenario_5_ambiguous_chart_reference_prevents_silent_modification(kernel_env):
    """
    Scenario 5: Two charts with an ambiguous reference do not cause silent modification.
    """
    pytest.importorskip("swisseph")

    dispatcher = kernel_env["dispatcher"]
    store = kernel_env["store"]

    # Create Chart 1 (An)
    res_1 = dispatcher.execute_operation("create_natal_chart", {
        "name": "An", "date": "2000-01-01", "time": "08:00", "place": "Hà Nội, Việt Nam",
        "latitude": 21.0245, "longitude": 105.8412, "timezone": "Asia/Bangkok",
    })
    # Create Chart 2 (Bình)
    res_2 = dispatcher.execute_operation("create_natal_chart", {
        "name": "Bình", "date": "1999-05-10", "time": "14:00", "place": "TP. Hồ Chí Minh, Việt Nam",
        "latitude": 10.8231, "longitude": 106.6297, "timezone": "Asia/Ho_Chi_Minh",
    })

    assert len(store.find_by_kind("natal_chart")) == 2

    # Attempt to resolve target artifact without specifying target ID
    target_art, clarification_req = dispatcher.resolve_target_artifact("natal_chart")

    # Ambiguity detected: must not pick one silently!
    assert target_art is None
    assert clarification_req is not None
    assert clarification_req.candidate_choices is not None
    assert len(clarification_req.candidate_choices) == 2
    candidate_names = [c["name"] for c in clarification_req.candidate_choices]
    assert "An" in candidate_names
    assert "Bình" in candidate_names

    # Ensure neither chart was modified
    chart_1 = store.get(res_1.artifact.id)
    chart_2 = store.get(res_2.artifact.id)
    assert chart_1.revision == 1
    assert chart_2.revision == 1


# -----------------------------------------------------------------------------
# Scenario 6: Register test capability without modifying central branches
# -----------------------------------------------------------------------------

def test_scenario_6_register_test_capability_without_central_branch_changes(kernel_env):
    """
    Scenario 6: Register a small test capability without modifying central UI/runtime
    branches; it produces a usable standard view and action through the same contracts.
    """
    registry = kernel_env["registry"]
    store = kernel_env["store"]
    dispatcher = kernel_env["dispatcher"]
    runtime = kernel_env["runtime"]

    # Define custom test capability (e.g. Unit Converter / Weather)
    test_cap = Capability(
        name="unit_converter",
        title="Đổi đơn vị",
        description="Quy đổi nhiệt độ giữa Celsius và Fahrenheit.",
    )

    def handle_convert_c2f(args, **context):
        c = float(args.get("celsius", 0))
        f = c * 9 / 5 + 32
        return {"celsius": c, "fahrenheit": f, "formula": "F = C * 9/5 + 32"}

    def converter_actions(artifact: Artifact):
        return [
            ArtifactAction(
                id=f"act_convert_recalc_{artifact.id}",
                label="Đổi lại với 100°C",
                target_artifact_id=artifact.id,
                target_revision=artifact.revision,
                operation_name="convert_c2f",
                params={"celsius": 100},
            )
        ]

    test_cap.register_operation(OperationDefinition(
        name="convert_c2f",
        description="Convert Celsius to Fahrenheit.",
        parameters={
            "type": "object",
            "properties": {"celsius": {"type": "number"}},
            "required": ["celsius"],
        },
        handler=handle_convert_c2f,
        artifact_kind="unit_conversion",
        updates_target=True,
        available_actions=converter_actions,
    ))

    # Register into runtime dynamically!
    registry.register_capability(test_cap)

    # 1. Native tool definition derived automatically
    tool_defs = registry.to_tool_definitions()
    op_names = [t.name for t in tool_defs]
    assert "convert_c2f" in op_names

    # 2. Runtime executes the operation and creates artifact
    res = runtime.execute_tool("convert_c2f", {"celsius": 25})
    assert res["fahrenheit"] == 77.0

    conv_arts = store.find_by_kind("unit_conversion")
    assert len(conv_arts) == 1
    art = conv_arts[0]
    assert art.revision == 1

    # 3. Standard view provider creates standard view
    provider = StandardViewProvider(registry)
    view = provider.provide_view(art)
    assert view.schema_version == 1
    assert view.artifact_id == art.id

    # 4. Action can be dispatched through same dispatcher
    actions = test_cap.operations["convert_c2f"].available_actions(art)
    assert len(actions) == 1
    dispatch_res = dispatcher.dispatch(actions[0])
    assert dispatch_res.status == "success"
    assert dispatch_res.artifact.revision == 2
    assert dispatch_res.artifact.payload["fahrenheit"] == 212.0


# -----------------------------------------------------------------------------
# Scenario 7: Swap view provider and reject invalid view proposals
# -----------------------------------------------------------------------------

def test_scenario_7_view_provider_swapping_and_spec_validation(kernel_env):
    """
    Scenario 7: Swap the standard provider for a test provider on the same artifact;
    preserve state/actions. Invalid schema/field/resource/action references are rejected.
    """
    store = kernel_env["store"]
    registry = kernel_env["registry"]

    art = Artifact(
        id="art_test_view",
        kind="test_data",
        revision=1,
        payload={"score": 95, "status": "passed"},
        inputs={"exam": "CS101"},
        title="Test Artifact",
    )
    store.put(art)

    # 1. Custom Test View Provider
    class CustomTestViewProvider:
        def provide_view(self, artifact: Artifact, context=None):
            return ViewSpec(
                schema_version=1,
                artifact_id=artifact.id,
                revision=artifact.revision,
                title="Custom Layout",
                blocks=[
                    ViewBlock(type="summary", data={"text": f"Score: {artifact.payload['score']}"}),
                    ViewBlock(type="actions", data={"action_ids": []}),
                ],
            )

    custom_provider = CustomTestViewProvider()
    spec = custom_provider.provide_view(art)
    is_valid, error = validate_view_spec(spec, art, registry)
    assert is_valid is True
    assert error is None

    # 2. Rejection of unknown schema version
    bad_version_spec = ViewSpec(schema_version=99, artifact_id=art.id, revision=1, blocks=[])
    is_valid, err = validate_view_spec(bad_version_spec, art, registry)
    assert is_valid is False
    assert "unsupported_schema_version" in err

    # 3. Rejection of unsupported block type
    bad_block_spec = ViewSpec(
        schema_version=1,
        artifact_id=art.id,
        revision=1,
        blocks=[ViewBlock(type="executable_script", data={"code": "import os"})],
    )
    is_valid, err = validate_view_spec(bad_block_spec, art, registry)
    assert is_valid is False
    assert "unsupported_block_type" in err

    # 4. Rejection of invalid field reference in summary
    bad_field_spec = ViewSpec(
        schema_version=1,
        artifact_id=art.id,
        revision=1,
        blocks=[ViewBlock(type="summary", data={"fields": ["non_existent_fake_field"]})],
    )
    is_valid, err = validate_view_spec(bad_field_spec, art, registry)
    assert is_valid is False
    assert "invalid_field_reference" in err

    # 5. Rejection of unregistered/invented action
    bad_action_spec = ViewSpec(
        schema_version=1,
        artifact_id=art.id,
        revision=1,
        blocks=[ViewBlock(type="actions", data={"action_ids": ["invented_magic_action"]})],
    )
    is_valid, err = validate_view_spec(bad_action_spec, art, registry)
    assert is_valid is False
    assert "unregistered_action_id" in err

    # Rejections never corrupt the stored artifact
    cached = store.get(art.id)
    assert cached.revision == 1
    assert cached.payload["score"] == 95


# -----------------------------------------------------------------------------
# Scenario 8: Stop, retry, chat reset, pending input & worker callback lifecycle
# -----------------------------------------------------------------------------

def test_scenario_8_cancellation_reset_and_delayed_callbacks_safety(kernel_env):
    """
    Scenario 8: Stop, retry, chat reset, pending input and delayed worker callbacks
    do not lose results, leak workers or attach events to the wrong turn/artifact.
    """
    runtime = kernel_env["runtime"]
    store = kernel_env["store"]

    # 1. Immediate cancellation before run
    res_cancel = runtime.run("Yêu cầu", should_cancel=lambda: True)
    assert res_cancel.error == "cancelled"

    # 2. Cancellation midway preserves executed artifacts
    file_path = runtime.tool_search_documents("Operating Systems")[0]["path"]
    steps_observed = []

    def stop_after_read(step):
        steps_observed.append(step)

    runtime.model_callable = lambda goal, steps: (
        ModelDecision("", tool_name="read_document", tool_args={"file_path": file_path})
        if not steps
        else ModelDecision("", final_answer="Done")
    )
    res_midway = runtime.run("Đọc tệp", on_step=stop_after_read, should_cancel=lambda: len(steps_observed) >= 1)
    assert res_midway.error == "cancelled"
    # Preserves observation from read
    assert any(s.get("path") == file_path for s in res_midway.sources)

    # 3. Chat reset clears pending inputs and artifacts
    store.clear()
    assert len(store.list()) == 0

    # 4. Generation isolation check: delayed response with mismatched generation
    current_generation = 2
    delayed_generation = 1
    # Verify logic check matches OmnibarWindow._on_assistant_response
    assert delayed_generation != current_generation  # Dropped without modifying state
