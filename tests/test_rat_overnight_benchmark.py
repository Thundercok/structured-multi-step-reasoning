"""Synthetic transport/fixture checks; these do not measure model quality."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json

import pytest

from scripts import benchmark_rat_overnight as bench


def plan(tmp_path):
    return {'model': 'qwen3:4b-instruct', 'model_digest': bench.MODEL_DIGEST,
            'url': 'http://127.0.0.1:11434', 'output': str(tmp_path),
            'deadline': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            'trials': bench.matrix(), 'max_calls': 126, 'max_tokens_per_call': 640,
            'timeout_s': 90, 'context_tokens': 8192, 'thinking': False, 'temperature': 0.1}


def test_matrix_is_balanced_and_hard_call_upper_bound_is_correct():
    trials = bench.matrix()
    assert len(trials) == len({t['id'] for t in trials}) == 54
    assert sum(t['max_calls'] for t in trials) == 126
    assert set(Counter((t['case'], t['residency'], t['arm']) for t in trials).values()) == {3}
    for case in bench.CASES:
        for state in ('cold', 'resident'):
            for position in range(3):
                arms = [t['arm'] for t in trials if t['case'] == case and t['residency'] == state][position::3]
                assert set(arms) == set(bench.ARMS)


def test_budget_blocks_extra_calls_and_reserves_deadline_cleanup_time(tmp_path):
    settings = plan(tmp_path)
    deadline = datetime.fromisoformat(settings['deadline']).timestamp()
    clock = [deadline - 50]
    budget = bench.Budget(settings, now=lambda: clock[0])
    assert budget.timeout(90) == 30
    trial = {'max_calls': 1}
    budget.claim(trial)
    with pytest.raises(bench.BenchmarkStop, match='trial_call_budget'):
        budget.claim(trial)
    assert budget.calls == 1
    clock[0] = deadline - 19
    with pytest.raises(bench.BenchmarkStop, match='deadline'):
        budget.timeout()


def test_global_cap_stop_file_and_remote_endpoint_rejection(tmp_path):
    settings = plan(tmp_path)
    budget = bench.Budget(settings)
    budget.calls = 126
    with pytest.raises(bench.BenchmarkStop, match='global_call_budget'):
        budget.claim({'max_calls': 5})
    (tmp_path / 'STOP').touch()
    with pytest.raises(bench.BenchmarkStop, match='stop_file'):
        budget.check()
    settings['url'] = 'https://external.example'
    with pytest.raises(ValueError, match='local Ollama'):
        bench.validate_plan(settings)


def test_answer_without_actual_read_cannot_pass_end_to_end(tmp_path):
    item = {'code': 'LOTUS-7319', 'path': str(tmp_path / 'note.txt')}
    assert bench.evaluate('LOTUS-7319', item)['task_success']
    assert not bench.evaluate('LOTUS-7319', item, needs_read=True)['task_success']
    observed = {'tool_name': 'read_document', 'error': None, 'tool_result': {
        'found': True, 'path': item['path'], 'content': 'Mã: LOTUS-7319'}}
    assert bench.evaluate('LOTUS-7319', item, steps=[observed], needs_read=True)['task_success']
    observed['tool_result']['path'] = '/wrong/source.txt'
    assert not bench.evaluate('LOTUS-7319', item, steps=[observed], needs_read=True)['task_success']


def test_real_runtime_and_production_transport_with_scripted_server(tmp_path, monkeypatch):
    from rat.crawler.db import Database
    path = tmp_path / 'latency_short.txt'
    path.write_text('Mã xác nhận: LOTUS-7319.')
    item = {'filename': path.name, 'path': str(path), 'code': 'LOTUS-7319', 'content': path.read_text()}
    db = Database(str(tmp_path / 'fixture.db'))
    db.upsert_document({'file_path': str(path), 'file_name': path.name, 'file_ext': '.txt',
        'file_size': path.stat().st_size, 'created_at': 1, 'modified_at': 1, 'indexed_at': 1,
        'content_text': path.read_text()})
    settings = plan(tmp_path)
    budget = bench.Budget(settings)
    client = bench.make_client(settings, budget, lambda **kw: None)
    trial = {'id': 'fixture', 'arm': 'rat_e2e', 'max_calls': 5}
    client.trial = trial
    payloads = []

    def server(request, timeout):
        payload = json.loads(request.data)
        payloads.append(payload)
        observations = [m for m in payload['messages'] if m['role'] == 'tool']
        if not observations:
            function = {'name': 'search_documents', 'arguments': {'query': path.name}}
            message = {'role': 'assistant', 'tool_calls': [{'id': 'search', 'function': function}]}
        elif len(observations) == 1:
            function = {'name': 'read_document', 'arguments': {'file_path': str(path)}}
            message = {'role': 'assistant', 'tool_calls': [{'id': 'read', 'function': function}]}
        else:
            message = {'role': 'assistant', 'content': 'LOTUS-7319'}
        return BytesIO(json.dumps({'message': message, 'done': True, 'prompt_eval_count': 100,
                                  'eval_count': 10, 'done_reason': 'stop'}).encode())

    monkeypatch.setattr('urllib.request.urlopen', server)
    result = bench.execute_trial(settings, trial, item, db, client)
    assert result['quality']['task_success'] and budget.calls == 3
    assert [c['event'] for c in bench.load_lines(tmp_path / 'calls.jsonl')] == ['call_start', 'call_end'] * 3
    assert all(p['options'] == {'temperature': 0.1, 'num_predict': 640, 'num_ctx': 8192} for p in payloads)
    messages, tools, kwargs = bench.capture_native_request(db, item)
    assert len(tools) == 7 and any(item['content'] in m.get('content', '') for m in messages)
    assert provided_goal_in(messages, bench.provided_request(item))
    assert budget.calls == 3  # Request capture must not issue HTTP or consume inference.
    db.get_connection().close()


def provided_goal_in(messages, goal):
    return any(m.get('content') == goal for m in messages)


def test_transport_timeout_stops_future_work_and_preserves_unknown_usage(tmp_path, monkeypatch):
    settings = plan(tmp_path)
    budget = bench.Budget(settings)
    client = bench.make_client(settings, budget, lambda **kw: None)
    client.trial = {'id': 'failed', 'max_calls': 1}
    def fail(*args, **kwargs):
        raise TimeoutError('fixture timeout')
    monkeypatch.setattr('urllib.request.urlopen', fail)
    result = client.chat_with_meta([], [])
    assert result['error'] and result['token_usage_known'] is False
    with pytest.raises(bench.BenchmarkStop, match='transport_error'):
        budget.check()
    assert len(bench.load_lines(tmp_path / 'calls.jsonl')) == 2


def test_report_includes_failed_latencies_and_never_turns_unknown_counts_into_zero(tmp_path):
    for index, (success, wall) in enumerate(((True, 2), (False, 12))):
        trial = {'id': str(index), 'arm': 'bare', 'residency': 'cold'}
        bench.append_json(tmp_path / 'trials.jsonl', {'trial': trial, 'wall_s': wall,
                                                   'quality': {'task_success': success}})
        bench.append_json(tmp_path / 'calls.jsonl', {'event': 'call_end', 'trial_id': str(index),
            'result': {'token_usage_known': success, 'prompt_tokens': 10, 'completion_tokens': 3}})
    summary = bench.report(tmp_path)
    row = summary['groups'][0]
    assert row['n'] == 2 and row['successes'] == 1 and row['median_wall_s'] == 7
    assert row['prompt_tokens'] is None and row['completion_tokens'] is None
