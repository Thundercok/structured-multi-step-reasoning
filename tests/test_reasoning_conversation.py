"""One RAT conversation with a composed fixture engine; no model service or weights."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest

from tests.test_flow_interaction import app, window, until
from tests.test_execution_flow import collect, runtime
from rat.engine.execution import ExecutionRequest, execution_response, render_backend_input
from rat.engine.meta_reasoner import build_composed_meta_reasoner
from rat.ui.assistant_worker import create_execution_worker
from rat.ui.reasoning_host import install_reasoning_engine
from reasoning.bundle import BundleValidationError, create_synthetic_specimen_bundle


class RecordingBackend:
    hidden_size = 2

    def __init__(self):
        self.inputs = []
        self.embeddings = []

    def embed(self, query):
        self.embeddings.append(query)
        return np.zeros(2)

    def run(self, strategy, query, **kwargs):
        self.inputs.append(query)
        return f'Authored fixture reply {len(self.inputs)}', .99, 2


def composed():
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    backend = RecordingBackend()
    return build_composed_meta_reasoner(bundle, backend, policy, allow_synthetic=True), backend


@contextmanager
def installed(app, engine):
    names = ('ratReasoningEngine', 'ratAllowSyntheticPolicy', 'ratReasoningConversation')
    previous = {name: app.property(name) for name in names}
    try:
        install_reasoning_engine(app, engine, allow_synthetic_policy=True)
        yield
    finally:
        for name, value in previous.items():
            app.setProperty(name, value)


def test_request_freezes_context_before_worker_and_evidence_uses_executed_snapshot(app):
    engine, backend = composed()
    target = runtime()
    context = {'history': [{'role': 'user', 'content': 'array=[2,4,6,8,10], target=8', 'turn_id': 'turn-2'}],
               'task_state': {'array': [2, 4, 6, 8, 10], 'target': 8}}
    request = ExecutionRequest('Sao phải dùng mid + 1?', 'followup', 3,
                               SimpleNamespace(turn_id='turn-3'), lane='reasoning', context=context)
    original = request.context_snapshot()
    context['history'][0]['content'] = 'MUTATED_AFTER_SUBMIT'
    context['task_state']['target'] = 100
    request.context['task_state']['array'].clear()
    returned = request.context_snapshot()
    returned['task_state']['target'] = -1
    worker = create_execution_worker(target, request, reasoning_engine=engine, allow_synthetic_policy=True)
    result = collect(app, worker)
    response = execution_response(request, result)
    assert 'MUTATED_AFTER_SUBMIT' not in backend.inputs[0]
    assert '[2, 4, 6, 8, 10]' in backend.inputs[0] and 'target=8' in backend.inputs[0]
    assert request.context_snapshot() == original == result.context_snapshot
    assert response.qa_telemetry['context_snapshot_hash'] == original['snapshot_hash']
    assert result.query == request.query == response.qa_telemetry['user_displayed_query']
    assert response.answer_verification_status == 'UNKNOWN'
    target.run.assert_not_called()


def test_explicit_old_references_survive_recent_context_window():
    request = ExecutionRequest('explain the selected result', turn_ref={
        'target_turn_id': 'turn-1', 'target_artifact_id': 'selected', 'target_revision': 4},
        context={'turn_references': [{'turn_id': f'turn-{i}', 'user_query': f'query {i}'} for i in range(1, 9)],
                 'history': [{'role': 'assistant', 'content': 'array facts absent from clipped reference'}],
                 'artifact_refs': [{'id': 'selected', 'revision': 4, 'inputs': {'target': 8}}] +
                                  [{'id': f'other-{i}', 'revision': 1} for i in range(6)]})
    text = render_backend_input(request.query, request.context_snapshot())
    assert 'query 1' in text and 'selected@v4' in text
    assert 'array facts absent from clipped reference' in text


@pytest.mark.parametrize('turn_ref', [
    {'target_turn_id': 'missing'},
    {'target_artifact_id': 'missing', 'target_revision': 4},
])
def test_missing_required_reference_fails_before_any_dispatch(app, turn_ref):
    engine, backend = composed()
    target = runtime()
    request = ExecutionRequest('explain that', lane='reasoning', turn_ref=turn_ref)
    worker = create_execution_worker(target, request, reasoning_engine=engine, allow_synthetic_policy=True)
    response = collect(app, worker)
    assert response.error == 'reasoning_context_unavailable'
    assert backend.inputs == backend.embeddings == []
    target.run.assert_not_called()


def test_host_rejects_unapproved_configuration_without_replacing_working_host(app):
    engine, backend = composed()
    with installed(app, engine):
        with pytest.raises(BundleValidationError):
            install_reasoning_engine(app, engine)
        assert app.property('ratReasoningEngine') is engine
        assert app.property('ratAllowSyntheticPolicy') is True
        assert app.property('ratReasoningConversation') is True
        assert backend.inputs == []


def test_typed_multiturn_conversation_uses_one_engine_and_preserves_history(window, app):
    engine, backend = composed()
    target = window.assistant_runtime
    target.run = Mock(side_effect=AssertionError('reasoning conversation fell back to assistant'))
    queries = ['Giải thích binary search bằng ví dụ nhỏ, chưa đưa code.',
               'Dùng mảng [2,4,6,8,10], tìm 8.', 'Sao phải dùng mid + 1?', 'Đổi sang tìm 6.']
    with installed(app, engine):
        for i, query in enumerate(queries, 1):
            window.chat_composer_input.setText(query)
            QTest.keyClick(window.chat_composer_input, Qt.Key.Key_Return)
            until(app, lambda: window._pending_chat_query is None and len(backend.inputs) == i)
            assert window.last_turn_telemetry['user_displayed_query'] == query
            assert window.last_turn_telemetry['bundle_review_status'] == 'synthetic_development_only'
        turns = window._conversation.turns()
        assert [t.query for t in turns] == queries
        assert [t.answer for t in turns] == [f'Authored fixture reply {i}' for i in range(1, 5)]
        assert len({t.execution_id for t in turns}) == 4
        assert len({t.turn_ref.conversation_id for t in turns}) == 1
        assert all(t.status == 'completed' for t in turns)
        assert '[2,4,6,8,10]' in backend.inputs[2]
        assert 'binary search' in backend.inputs[2].lower()
        assert 'fixture' in window.footer_status.text()
        window.chat_composer_input.setText('Bản nháp đang soạn')
        assert window.navigate_to_turn(turns[1].turn_id)
        assert window.chat_composer_input.text() == 'Bản nháp đang soạn'
        assert len(backend.inputs) == 4
        target.run.assert_not_called()
