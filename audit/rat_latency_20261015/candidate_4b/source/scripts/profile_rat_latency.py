"""Bounded live RAT development profile using an isolated, artificial document.

Uses the native app's actor settings and the existing recording transport, with
no planner, personal index, model download or saved configuration changes.
This is a diagnostic observation, not a model benchmark or NCKH experiment.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rat.config import config
from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.slm import SLMEngine
from rat.timetable.compositor import TimetableCompositor
from scripts.run_dsa_core_smoke import compute_source_hashes


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + '\n')


def resource_state(url):
    result = {'utc': datetime.now(timezone.utc).isoformat()}
    for name, command in (('swap', ['sysctl', 'vm.swapusage']),
                          ('vm', ['vm_stat']), ('processor', ['ollama', 'ps'])):
        try:
            value = subprocess.run(command, capture_output=True, text=True, timeout=4)
            result[name] = value.stdout.strip() if value.returncode == 0 else value.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            result[name] = {'error': str(exc)}
    try:
        with urllib.request.urlopen(url + '/api/ps', timeout=3) as reply:
            result['loaded_models'] = json.load(reply)
    except Exception as exc:
        result['loaded_models_error'] = str(exc)
    return result


class ProfileClient(SLMEngine):
    def __init__(self, *, output, model, url, max_calls):
        super().__init__(model=model, ollama_url=url)
        self.record_path = output / 'calls.jsonl'
        self.max_calls = max_calls
        self.call_Records = []

    def chat_with_meta(self, *args, **kwargs):
        if len(self.call_Records) >= self.max_calls:
            raise RuntimeError('diagnostic_model_call_budget_exhausted')
        print(f'model_call_started={len(self.call_Records) + 1}', flush=True)
        kwargs['timeout'] = min(float(kwargs.get('timeout', 90)), 60)
        result = super().chat_with_meta(*args, **kwargs)
        raw = result.get('raw_response') or {}
        known = result.get('token_usage_known') is True
        record = {'call_index': len(self.call_Records) + 1, **result,
                  'prompt_tokens': result.get('prompt_tokens') if known else None,
                  'completion_tokens': result.get('completion_tokens') if known else None}
        self.call_Records.append(record)
        with self.record_path.open('a') as journal:
            journal.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(json.dumps({'call': len(self.call_Records),
                          'wall_s': round(result['duration_ms'] / 1000, 3),
                          'prompt_tokens': result.get('prompt_tokens'),
                          'completion_tokens': result.get('completion_tokens'),
                          'prompt_s': (raw.get('prompt_eval_duration') or 0) / 1e9,
                          'generation_s': (raw.get('eval_duration') or 0) / 1e9,
                          'error': result.get('error')}, ensure_ascii=False), flush=True)
        return result


def profile(output, *, model=None, max_calls=5):
    url = config.ollama_url.rstrip('/')
    if urllib.parse.urlparse(url).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('This diagnostic requires a local Ollama endpoint')
    model = model or config.assistant_model or config.ollama_model
    with urllib.request.urlopen(url + '/api/tags', timeout=4) as reply:
        installed = json.load(reply)
    metadata = next((m for m in installed.get('models', []) if m['name'] == model), None)
    if metadata is None:
        raise ValueError('Select an already installed model; this script never downloads one')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    hashes = compute_source_hashes(ROOT)
    for name in ('rat/engine/runtime_context.py', 'rat/engine/context_snapshot.py',
                 'rat/kernel/capabilities/documents.py', 'scripts/profile_rat_latency.py'):
        hashes[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    source_dir = output / 'source'
    source_dir.mkdir()
    for name in hashes:
        source = ROOT / name
        if source.is_file():
            target = source_dir / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    manifest = {'evidence': 'measured_app_development_fixture', 'status': 'running',
                'utc_started': datetime.now(timezone.utc).isoformat(),
                'model': metadata, 'source_hashes': hashes,
                'runtime': {'plan_tasks': False, 'discover_tools': True,
                            'structured_context': False, 'max_steps': 5,
                            'timeout_s_per_call': 60, 'max_calls': max_calls},
                'stage0_changed': False, 'personal_index_used': False,
                'token_scope': 'reported_prompt_and_completion_per_invoked_call',
                'latency_scope': 'headless_online_client_and_reported_server_phases',
                'quality_scope': 'one_exposed_artificial_document_task_only'}
    write_json(output / 'manifest.json', manifest)
    document = output / 'latency_probe.txt'
    document.write_text('Ghi chú kiểm tra RAT.\nMã xác nhận: LOTUS-7319.\nPhòng học: B203.\n')
    db = Database(str(output / 'fixture.db'))
    db.get_connection().execute('''INSERT INTO documents
        (file_path,file_name,file_ext,file_size,created_at,modified_at,content_text,summary,normalized_text,indexed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)''',
        (str(document), document.name, '.txt', document.stat().st_size, 1, 1,
         document.read_text(), 'Ghi chú kiểm tra RAT', 'latency probe ghi chu kiem tra rat', 1))
    db.get_connection().commit()
    client = ProfileClient(output=output, model=model, url=url, max_calls=max_calls)
    runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]),
                               model_client=client, plan_tasks=False,
                               discover_tools=True, structured_context=False)
    goal = 'Tìm file latency_probe.txt trong máy, đọc nội dung rồi cho biết mã xác nhận ghi trong file.'
    write_json(output / 'fixture.json', {'query': goal, 'document': document.read_text(),
                                       'document_sha256': hashlib.sha256(document.read_bytes()).hexdigest()})
    resources = [resource_state(url)]
    stop = threading.Event()

    def sample():
        while not stop.wait(3):
            resources.append(resource_state(url))

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        response = runtime.run(goal, max_steps=5, now_dt=datetime(2026, 10, 15, 12),
                               conversation_id='latency-development-fixture',
                               turn_ref='turn-1', execution_id='latency-execution-1')
        write_json(output / 'response.json', asdict(response))
        steps = response.steps
        operations = [s.tool_name for s in steps if s.tool_name]
        read_observed = any(s.tool_name == 'read_document' and not s.error
                            and isinstance(s.tool_result, dict)
                            and s.tool_result.get('found') is True
                            and s.tool_result.get('path') == str(document)
                            and 'LOTUS-7319' in s.tool_result.get('content', '') for s in steps)
        quality = {'runtime_error': response.error, 'operations': operations,
                   'correct_code_in_answer': 'LOTUS-7319' in response.answer,
                   'read_correct_document': read_observed}
        quality['task_success'] = bool(not response.error and read_observed
                                       and quality['correct_code_in_answer'])
        manifest['status'] = 'completed'
    except Exception as exc:
        quality = {'task_success': False, 'error': str(exc)}
        manifest['status'] = 'failed'
    finally:
        wall_s = time.perf_counter() - started
        stop.set()
        sampler.join(timeout=15)
        resources.append(resource_state(url))
        write_json(output / 'resources.json', resources)
    calls = []
    for c in client.call_Records:
        raw = c.get('raw_response') or {}
        calls.append({'wall_s': c['duration_ms'] / 1000, 'error': c['error'],
                      'prompt_tokens': c['prompt_tokens'], 'completion_tokens': c['completion_tokens'],
                      'tools': len(c['request'].get('tools', [])),
                      'request_bytes': len(json.dumps(c['request'], ensure_ascii=False).encode()),
                      **{key: raw.get(key) for key in ('total_duration', 'load_duration',
                         'prompt_eval_duration', 'eval_duration', 'prompt_eval_cached_count')}})
    summary = {'wall_s': wall_s, 'quality': quality, 'calls': calls,
               'call_count': len(calls), 'source_changed_during_run':
               [name for name, sha in hashes.items() if (ROOT / name).is_file()
                and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha]}
    write_json(output / 'summary.json', summary)
    manifest['utc_finished'] = datetime.now(timezone.utc).isoformat()
    write_json(output / 'manifest.json', manifest)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--model')
    parser.add_argument('--max-calls', type=int, default=5, choices=range(1, 7))
    args = parser.parse_args()
    profile(args.output, model=args.model, max_calls=args.max_calls)
