"""Versioned artifact lifecycle regressions; all state and operations are local fixtures."""
import pytest

from rat.kernel.contracts import Artifact, ArtifactAction, ArtifactStore, InputRequest
from rat.kernel.dispatcher import ActionDispatcher
from rat.kernel.registry import CapabilityRegistry, OperationDefinition


def artifact(artifact_id="a", revision=1, value="original", created_at=1):
    return Artifact(artifact_id, "fixture", revision, {"value": value}, created_at=created_at)


def input_dispatcher(store=None, request_id=None):
    def handler(args, **context):
        if "second" not in args:
            ids = {"id": request_id} if request_id is not None else {}
            return InputRequest("input_fixture", supplied_inputs=dict(args),
                                missing_fields=[{"name": "second", "type": "string"}], **ids)
        return {"value": args["first"] + args["second"]}

    registry = CapabilityRegistry()
    registry.register_operation(OperationDefinition(
        "input_fixture", "Input lifecycle fixture", {
            "type": "object",
            "properties": {"first": {"type": "string"}, "second": {"type": "string"}},
            "required": ["first"],
        }, handler, artifact_kind="fixture",
    ))
    return ActionDispatcher(registry, store if store is not None else ArtifactStore())


def test_deleted_revision_cannot_alias_recreated_body():
    store = ArtifactStore()
    store.put(artifact())
    assert store.delete("a")
    assert store.get_history("a") == []
    with pytest.raises(ValueError, match="^non_monotonic_revision$"):
        store.put(artifact(value="replacement"))
    replacement = store.put(artifact(revision=2, value="replacement"))
    assert replacement.revision == 2
    assert store.get("a", revision=1) is None
    assert store.get("a", revision=2).payload == {"value": "replacement"}


@pytest.mark.parametrize("recreated", [False, True])
def test_stale_update_cannot_resurrect_or_overwrite_deleted_target(recreated):
    store = ArtifactStore()
    store.put(artifact())
    generation = store.generation
    store.delete("a")
    if recreated:
        store.put(artifact(revision=2, value="replacement"))
    with pytest.raises(ValueError, match="^stale_revision$"):
        store.put(artifact(revision=2, value="stale write"),
                  expected_revision=1, expected_generation=generation)
    current = store.get("a")
    assert (current.payload if current else None) == ({"value": "replacement"} if recreated else None)
    assert store.next_revision("a") == (3 if recreated else 2)


@pytest.mark.parametrize("generation,expected_revision,error", [
    (1, 1, "cancelled:conversation_reset"),
    (0, 1, "stale_revision"),
    (0, 2, "non_monotonic_revision"),
])
def test_generation_then_target_revision_then_high_water_error_priority(generation, expected_revision, error):
    store = ArtifactStore()
    store.put(artifact(revision=2))
    with pytest.raises(ValueError) as caught:
        store.put(artifact(revision=2, value="rejected"),
                  expected_generation=generation, expected_revision=expected_revision)
    assert str(caught.value) == error
    assert store.get("a").payload == {"value": "original"}
    assert store.next_revision("a") == 3


@pytest.mark.parametrize("revision,guards,error", [
    (9, {"expected_generation": 1}, "cancelled:conversation_reset"),
    (9, {"expected_revision": 1}, "stale_revision"),
    (1, {}, "non_monotonic_revision"),
])
def test_rejected_put_does_not_evict_live_body_or_consume_revision(revision, guards, error):
    store = ArtifactStore(max_artifacts=1)
    store.put(artifact())
    store.delete("a")
    store.put(artifact("live", value="keep", created_at=2))
    before = store.get("live").to_dict()
    with pytest.raises(ValueError) as caught:
        store.put(artifact(revision=revision, value="rejected"), **guards)
    assert str(caught.value) == error
    assert store.get("live").to_dict() == before
    assert [a.id for a in store.list()] == ["live"]
    assert store.next_revision("a") == 2
    assert store.next_revision("live") == 2


def test_copy_failure_happens_before_eviction_or_high_water_mutation():
    class Uncopyable(dict):
        def __deepcopy__(self, memo):
            raise RuntimeError("fixture copy failure")

    store = ArtifactStore(max_artifacts=1)
    store.put(artifact("live", value="keep"))
    candidate = artifact("new", revision=7)
    candidate.payload = Uncopyable()
    with pytest.raises(RuntimeError, match="fixture copy failure"):
        store.put(candidate)
    assert [a.id for a in store.list()] == ["live"]
    assert store.get("live").payload == {"value": "keep"}
    assert store.next_revision("new") == 1


def test_capacity_eviction_preserves_revision_high_water():
    store = ArtifactStore(max_artifacts=1)
    store.put(artifact())
    store.put(artifact("b", created_at=2))
    assert store.get("a") is None
    with pytest.raises(ValueError, match="^non_monotonic_revision$"):
        store.put(artifact(value="rejected"))
    assert store.get("b") is not None
    store.put(artifact(revision=store.next_revision("a"), value="recreated", created_at=3))
    assert store.get("a").revision == 2
    assert store.get("a", revision=1) is None
    assert store.get("b") is None
    assert store.next_revision("b") == 2


def test_clear_starts_fresh_revisions_but_rejects_old_generation_guards():
    store = ArtifactStore()
    store.put(artifact(revision=4))
    old_generation = store.generation
    store.clear()
    assert store.generation == old_generation + 1
    assert store.next_revision("a", expected_generation=store.generation) == 1
    store.put(artifact(value="fresh epoch"), expected_generation=store.generation)
    with pytest.raises(ValueError, match="^cancelled:conversation_reset$"):
        store.next_revision("a", expected_generation=old_generation)
    with pytest.raises(ValueError, match="^cancelled:conversation_reset$"):
        store.put(artifact(revision=5, value="old write"), expected_generation=old_generation)
    assert store.get("a").revision == 1
    assert store.get("a").payload == {"value": "fresh epoch"}


def test_revision_suggestions_do_not_reserve_or_silently_bump_conflicting_writes():
    store = ArtifactStore()
    assert store.next_revision("a") == store.next_revision("a") == 1
    store.put(artifact())
    first = store.next_revision("a")
    second = store.next_revision("a")
    assert first == second == 2
    store.put(artifact(revision=first, value="first write"), expected_revision=1)
    with pytest.raises(ValueError, match="^non_monotonic_revision$"):
        store.put(artifact(revision=second, value="second write"))
    assert store.get("a").payload == {"value": "first write"}
    assert [a.revision for a in store.get_history("a")] == [1, 2]
    assert store.next_revision("a") == 3


def test_default_input_request_continues_then_closes_and_new_request_is_fresh():
    dispatcher = input_dispatcher()
    initial = dispatcher.execute_operation("input_fixture", {"first": "a"})
    assert initial.status == "needs_input"
    request_id = initial.input_request.id
    continued = dispatcher.resume_input(request_id, {})
    assert continued.status == "needs_input"
    assert continued.input_request.id == request_id and continued.artifact.revision == 2
    completed = dispatcher.resume_input(request_id, {"second": "b"})
    assert completed.status == "success" and completed.result == {"value": "ab"}
    assert dispatcher.store.get(request_id) is None
    assert dispatcher.state.pending_input_request is None
    assert dispatcher.resume_input(request_id, {"second": "c"}).status == "error"
    fresh = dispatcher.execute_operation("input_fixture", {"first": "x"})
    assert fresh.status == "needs_input"
    assert fresh.input_request.id != request_id and fresh.artifact.revision == 1


def test_explicit_input_request_id_recreate_uses_next_committed_revision():
    dispatcher = input_dispatcher(request_id="fixed-input")
    initial = dispatcher.execute_operation("input_fixture", {"first": "a"})
    assert initial.artifact.revision == 1
    continued = dispatcher.resume_input("fixed-input", {})
    assert continued.artifact.revision == 2
    assert dispatcher.resume_input("fixed-input", {"second": "b"}).status == "success"
    recreated = dispatcher.execute_operation("input_fixture", {"first": "x"})
    assert recreated.status == "needs_input"
    assert recreated.input_request.id == "fixed-input"
    assert recreated.artifact.revision == 3
    assert dispatcher.store.get("fixed-input", revision=1) is None


def test_waiting_request_eviction_does_not_reset_its_revision():
    store = ArtifactStore(max_artifacts=1)
    dispatcher = input_dispatcher(store)
    initial = dispatcher.execute_operation("input_fixture", {"first": "a"})
    request_id = initial.input_request.id
    store.put(artifact("unrelated", created_at=initial.artifact.created_at + 1))
    assert store.get(request_id) is None
    continued = dispatcher.execute_operation("input_fixture", {})
    assert continued.status == "needs_input"
    assert continued.input_request.id == request_id
    assert continued.artifact.revision == 2


def test_clear_between_waiting_allocation_and_put_rejects_old_epoch(monkeypatch):
    store = ArtifactStore()
    store.put(Artifact("fixed-input", "input_request", revision=4))
    store.delete("fixed-input")
    dispatcher = input_dispatcher(store, request_id="fixed-input")
    original_next = store.next_revision
    allocations = []

    def allocate_then_clear(artifact_id, *, expected_generation=None):
        revision = original_next(artifact_id, expected_generation=expected_generation)
        allocations.append((revision, expected_generation))
        store.clear()
        return revision

    monkeypatch.setattr(store, "next_revision", allocate_then_clear)
    result = dispatcher.execute_operation("input_fixture", {"first": "a"})
    assert allocations == [(5, 0)]
    assert result.status == "cancelled" and result.error == "cancelled:conversation_reset"
    assert store.list() == [] and dispatcher.state.pending_input_request is None
    assert original_next("fixed-input", expected_generation=1) == 1


def test_old_versioned_action_cannot_target_recreated_artifact():
    store = ArtifactStore()
    calls = []

    def handler(args, **context):
        calls.append(dict(args))
        return {"value": args["value"]}

    registry = CapabilityRegistry()
    registry.register_operation(OperationDefinition(
        "update_fixture", "Update fixture", {"type": "object", "properties": {"value": {"type": "string"}}},
        handler, artifact_kind="fixture", target_kind="fixture", updates_target=True,
    ))
    dispatcher = ActionDispatcher(registry, store)
    store.put(artifact())
    old_action = ArtifactAction("old", "Old action", "a", 1, "update_fixture", {"value": "stale"})
    store.delete("a")
    store.put(artifact(revision=2, value="replacement"))
    assert dispatcher.dispatch(old_action).status == "stale_revision"
    assert calls == [] and store.get("a").payload == {"value": "replacement"}
    current_action = ArtifactAction("current", "Current action", "a", 2, "update_fixture", {"value": "updated"})
    result = dispatcher.dispatch(current_action)
    assert result.status == "success" and result.artifact.revision == 3
    assert store.get("a", revision=1) is None
    assert store.get("a", revision=2).payload == {"value": "replacement"}
    assert store.get("a").payload == {"value": "updated"}


def test_history_trimming_and_copy_isolation_preserve_lifecycle_identity():
    store = ArtifactStore(max_history_per_artifact=1)
    returned = store.put(artifact())
    returned.payload["value"] = "outside mutation"
    assert store.get("a").payload == {"value": "original"}
    store.put(artifact(revision=2, value="new"))
    assert store.get("a", revision=1) is None
    store.delete("a")
    assert store.next_revision("a") == 3
    with pytest.raises(ValueError, match="^non_monotonic_revision$"):
        store.put(artifact(revision=2, value="revived"))
    store.put(artifact(revision=3, value="recreated"))
    assert [a.revision for a in store.get_history("a")] == [3]
