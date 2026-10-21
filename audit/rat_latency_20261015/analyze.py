"""Recheck saved development observations without making model calls."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def summarize(name):
    folder = ROOT / name
    manifest = read(folder / 'manifest.json')
    saved = read(folder / 'summary.json')
    response = read(folder / 'response.json')
    fixture = read(folder / 'fixture.json')
    resources = read(folder / 'resources.json')
    calls = [json.loads(line) for line in (folder / 'calls.jsonl').read_text().splitlines()]
    assert manifest['status'] == 'completed'
    assert not saved['source_changed_during_run']
    assert len(calls) == saved['call_count'] <= manifest['runtime']['max_calls']
    assert hashlib.sha256((folder / 'latency_probe.txt').read_bytes()).hexdigest() == fixture['document_sha256']
    for name, digest in manifest['source_hashes'].items():
        if digest is not None:
            assert hashlib.sha256((folder / 'source' / name).read_bytes()).hexdigest() == digest, name
    for call in calls:
        raw = call['raw_response']
        assert raw['done'] is True and not call['error'] and call['token_usage_known']
        assert raw['prompt_eval_count'] == call['prompt_tokens']
        assert raw['eval_count'] == call['completion_tokens']
    reads = [s for s in response['steps'] if s['tool_name'] == 'read_document'
             and not s['error'] and isinstance(s['tool_result'], dict)
             and s['tool_result'].get('found') is True
             and s['tool_result'].get('path') == str((folder / 'latency_probe.txt').resolve())
             and 'LOTUS-7319' in s['tool_result'].get('content', '')]
    success = bool(not response['error'] and reads and 'LOTUS-7319' in response['answer'])
    assert success == saved['quality']['task_success']
    phases = {key: sum(c['raw_response'].get(key, 0) for c in calls) / 1e9
              for key in ('load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')}
    return {'wall_s': saved['wall_s'], 'task_success': success, 'call_count': len(calls),
            'prompt_tokens': sum(c['prompt_tokens'] for c in calls),
            'completion_tokens': sum(c['completion_tokens'] for c in calls),
            'first_prompt_tokens': calls[0]['prompt_tokens'], 'server_phase_s': phases,
            'target_resident_before': any(m['name'] == manifest['model']['name']
                for m in resources[0].get('loaded_models', {}).get('models', [])),
            'swap_before': resources[0]['swap'], 'swap_after': resources[-1]['swap']}


def main():
    rows = {name: summarize(name) for name in ('baseline', 'baseline_4b', 'candidate_1p5', 'candidate_4b')}
    def without_descriptions(value):
        if isinstance(value, dict):
            return {k: without_descriptions(v) for k, v in value.items() if k != 'description'}
        if isinstance(value, list):
            return [without_descriptions(v) for v in value]
        return value
    def first_tools(name):
        call = json.loads((ROOT / name / 'calls.jsonl').read_text().splitlines()[0])
        return without_descriptions(call['request']['tools'])
    assert first_tools('baseline') == first_tools('candidate_1p5')
    assert first_tools('baseline_4b') == first_tools('candidate_4b')
    before, after = rows['baseline_4b'], rows['candidate_4b']
    result = {'scope': 'one_exposed_artificial_document_task_per_configuration',
              'inference_calls_in_analysis': 0, 'source_and_trace_checks_passed': True,
              'tool_catalog_and_parameter_constraints_unchanged': True,
              'runs': rows, 'four_b_observed_wall_reduction_fraction': 1 - after['wall_s'] / before['wall_s'],
              'four_b_prompt_token_reduction_fraction': 1 - after['prompt_tokens'] / before['prompt_tokens'],
              'causal_speedup_established': False, 'app_acceptance_established': False,
              'stage0_changed': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
