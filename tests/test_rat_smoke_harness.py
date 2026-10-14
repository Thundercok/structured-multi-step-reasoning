"""Smoke measurement contracts; all HTTP/model responses here are fixtures."""
import io
import json
import sys
import threading

import pytest

from scripts import run_dsa_core_smoke as smoke


def test_connection_failure_is_not_reported_as_cancellation_during_inference(monkeypatch):
    def refused(*args, **kwargs):
        raise ConnectionRefusedError('fixture: service unavailable')
    monkeypatch.setattr(smoke.urllib.request, 'urlopen', refused)
    client = smoke.InstrumentedSLMEngine()
    cancelled = threading.Event()
    state = client.arm_in_flight_cancel(cancelled, delay_ms=1000)
    meta = client.chat_with_meta([{'role': 'user', 'content': 'fixture'}], [])
    assert meta['error'] and not cancelled.is_set()
    assert state.get('cancel_requested_while_waiting', state.get('cancel_triggered_in_flight')) is False


@pytest.mark.parametrize('counts,known', [
    ({'eval_count': 2}, False), ({'prompt_eval_count': 4}, False),
    ({'prompt_eval_count': 4, 'eval_count': 2}, True),
])
def test_missing_token_counts_remain_unknown(monkeypatch, counts, known):
    data = {'message': {'content': 'fixture'}, 'done': True, **counts}
    monkeypatch.setattr(smoke.urllib.request, 'urlopen',
                        lambda *args, **kwargs: io.BytesIO(json.dumps(data).encode()))
    client = smoke.InstrumentedSLMEngine()
    client.chat_with_meta([{'role': 'user', 'content': 'fixture'}], [])
    record = client.call_Records[0]
    assert record['token_usage_known'] is known
    assert record['total_tokens'] == (6 if known else None)


def test_keyword_screen_does_not_certify_a_wrong_algorithm_explanation():
    result = smoke.evaluate_turn4_binary_search('mid=2 là ở giữa. Sau đó tiếp tục tìm bên trái dù đã khớp.')
    assert result['verdict'].endswith('requires_review')


def test_output_directory_is_never_reused_before_model_calls(tmp_path, monkeypatch):
    protected = tmp_path / 'existing'
    protected.mkdir()
    artifact = protected / 'live_dsa_smoke_plan_tasks_true.json'
    artifact.write_text('original evidence')
    calls = []
    monkeypatch.setattr(smoke, 'run_smoke_suite', lambda **kwargs: calls.append(kwargs) or {'evaluation': {}})
    monkeypatch.setattr(sys, 'argv', ['smoke', '--output-dir', str(protected), '--mode', 'omnibar'])
    with pytest.raises(SystemExit):
        smoke.main()
    assert calls == [] and artifact.read_text() == 'original evidence'


def test_fresh_output_outside_repository_is_supported(tmp_path, monkeypatch):
    output = tmp_path / 'new-run'
    monkeypatch.setattr(smoke, 'run_smoke_suite', lambda **kwargs: {'evaluation': {}, 'fixture': True})
    monkeypatch.setattr(sys, 'argv', ['smoke', '--output-dir', str(output), '--mode', 'omnibar'])
    assert smoke.main() == 0
    summary = json.loads((output / 'smoke_summary.json').read_text())
    target = summary['runs']['plan_tasks_true']['artifact']
    assert target == str(output / 'live_dsa_smoke_plan_tasks_true.json')


@pytest.mark.parametrize('waiting', [False, True])
def test_probe_does_not_finalize_fast_success_or_pending_input_as_cancelled(monkeypatch, waiting):
    message = {'content': 'fixture answer'} if not waiting else {
        'tool_calls': [{'function': {'name': 'create_natal_chart', 'arguments': {}}}],
    }
    data = {'message': message, 'done': True, 'prompt_eval_count': 4, 'eval_count': 2}
    monkeypatch.setattr(smoke.urllib.request, 'urlopen',
                        lambda *args, **kwargs: io.BytesIO(json.dumps(data).encode()))
    original = smoke.InstrumentedSLMEngine.arm_in_flight_cancel
    def defer_timer(self, event, **kwargs):
        # Deterministic fast-response fixture, independent of scheduler speed.
        return original(self, event, delay_ms=60000, request_timeout_s=kwargs['request_timeout_s'])
    monkeypatch.setattr(smoke.InstrumentedSLMEngine, 'arm_in_flight_cancel', defer_timer)
    report = smoke.run_smoke_suite(model_name='fixture', plan_tasks=False, max_steps=8, timeout_s=90)
    probe = report['turns'][5]
    assert probe['error'] is None
    assert report['final_history_turns'][5]['status'] == ('needs_input' if waiting else 'completed')
    assert report['evaluation']['lifecycle_and_context_contracts']['turn_6_cancel_flag_and_late_write_guards'] is False
    assert report['provenance']['native_equivalence_verified'] is False
    if waiting:
        assert report['final_history_turns'][5]['artifact_refs']
