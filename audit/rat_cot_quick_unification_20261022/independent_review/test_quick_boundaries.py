"""Targeted Quick lifecycle/reference probes on the submitted QML fixture host."""
from pathlib import Path
from threading import Event
import json

from PyQt6.QtTest import QTest

from tests.test_quick_unified_flow import app, quick_env, wait_for
from rat.kernel.contracts import Artifact

HERE = Path(__file__).resolve().parent

def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def test_new_turn_binds_its_own_source_artifact_not_previous_telemetry(quick_env):
    controller = quick_env.controller
    for label in ('A', 'B'):
        artifact = Artifact(id='artifact-' + label, kind='text', revision=1,
                            title='Source ' + label, inputs={'case': label}, payload={'answer': label})
        controller.assistant_runtime.artifact_store.put(artifact)
        controller.conversation.add_turn('source ' + label, 'authored ' + label,
                                         turn_id='source-' + label, artifact_refs=[artifact.to_dict()])
    observations = []
    for label in ('A', 'B'):
        assert controller.submit('Explain source ' + label, target_turn_id='source-' + label,
                                 target_artifact_id='artifact-' + label, target_revision=1)
        wait_for(lambda: not controller.snapshot['busy'])
        turn = controller.conversation.turns()[-1]
        observations.append({'requested_source': label, 'turn_id': turn.turn_id,
                             'bound_artifact_refs': turn.artifact_refs,
                             'response_telemetry': controller.snapshot['telemetry']})
    save('artifact_identity.json', observations)
    assert observations[-1]['bound_artifact_refs'], observations
    assert observations[-1]['bound_artifact_refs'][0].get('artifact_id', observations[-1]['bound_artifact_refs'][0].get('id')) == 'artifact-B', observations


def test_old_execution_status_cannot_overwrite_completed_new_turn(quick_env):
    controller = quick_env.controller
    entered, release = Event(), Event()
    counter = {'calls': 0}
    old_results = []
    def controlled_run(strategy, query, **kwargs):
        counter['calls'] += 1
        if counter['calls'] == 1:
            entered.set()
            assert release.wait(5), 'probe failed to release authored backend'
            if kwargs.get('should_cancel', lambda: False)():
                raise RuntimeError('cancelled_authored_old_execution')
        return 'authored new result', .99, 3
    quick_env.backend.run = controlled_run
    assert controller.submit('authored old request')
    wait_for(entered.is_set)
    old_worker = controller._current_worker
    old_worker.response_ready.connect(old_results.append)
    try:
        controller.cancel()
        assert controller.submit('authored new request')
        wait_for(lambda: not controller.snapshot['busy'])
        completed = dict(controller.snapshot)
        release.set()
        wait_for(lambda: old_worker.isFinished())
        QTest.qWait(50)
        after = dict(controller.snapshot)
        save('late_execution_status.json', {
            'new_completed_status': completed['status'], 'after_old_callback_status': after['status'],
            'new_turn_status': controller.conversation.turns()[-1].status,
            'old_result_statuses': [r.status for r in old_results],
            'old_cost_ledgers': [r.cost_ledger for r in old_results],
            'current_telemetry': after['telemetry'],
        })
        assert after['answerText'] == completed['answerText']
        assert after['status'] == completed['status']
    finally:
        release.set()
        assert old_worker.wait(5000)
        quick_env.app.processEvents() if hasattr(quick_env, 'app') else QTest.qWait(20)


def test_close_does_not_claim_worker_finished_while_generation_is_running(quick_env):
    controller = quick_env.controller
    entered, release = Event(), Event()
    def held_run(strategy, query, **kwargs):
        entered.set()
        assert release.wait(5), 'probe failed to release authored backend'
        return 'authored response', .99, 2
    quick_env.backend.run = held_run
    assert controller.submit('authored slow request')
    wait_for(entered.is_set)
    worker = controller._current_worker
    try:
        reported_closed = controller.close()
        still_running = worker.isRunning()
        save('close_inflight.json', {'close_reported_success': reported_closed,
                                    'reasoning_worker_still_running': still_running,
                                    'controller_keeps_current_worker': controller._current_worker is not None})
        assert not (reported_closed and still_running)
    finally:
        release.set()
        assert worker.wait(5000)
        QTest.qWait(20)
