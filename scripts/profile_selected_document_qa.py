"""Three bounded selected-file observations on saved artificial fixtures."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime
from rat.engine.selected_document_qa import answer_selected_document, MODEL
from rat.engine.slm import SLMEngine
from rat.timetable.compositor import TimetableCompositor


def api(endpoint, body=None):
    request = urllib.request.Request('http://127.0.0.1:11434/api/' + endpoint,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=10) as reply:
        return json.load(reply)


def main():
    output = ROOT / 'audit/rat_selected_qa_20261016'
    output.mkdir(exist_ok=False)
    fixtures = json.loads((ROOT / 'audit/rat_overnight_20261015/fixtures.json').read_text())
    names = ['rat/engine/selected_document_qa.py', 'rat/engine/assistant_runtime.py',
             'rat/engine/slm.py', 'scripts/profile_selected_document_qa.py']
    sources = {n: hashlib.sha256((ROOT / n).read_bytes()).hexdigest() for n in names}
    for name in names:
        target = output / 'source' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    manifest = {'status': 'running', 'utc': datetime.now(timezone.utc).isoformat(),
        'evidence': 'measured_app_development_fixture', 'cases': 3, 'max_inference_calls': 3,
        'source_hashes': sources, 'model': MODEL, 'ollama': api('version'),
        'model_metadata': next(m for m in api('tags')['models'] if m['name'] == MODEL),
        'stage0_changed': False, 'latency_scope': 'online headless selected-file read and one answer',
        'token_scope': 'reported prompt and completion; not full inference cost'}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    db = Database(str(output / 'fixture.db'))
    client = SLMEngine(model=MODEL, ollama_url='http://127.0.0.1:11434')
    rows = []
    try:
        for fixture in fixtures:
            path = output / fixture['filename']
            path.write_text(fixture['content'])
            db.upsert_document({'file_path': str(path), 'file_name': path.name, 'file_ext': '.txt',
                'file_size': path.stat().st_size, 'created_at': 1, 'modified_at': 1, 'indexed_at': 1,
                'content_text': path.read_text()})
            api('generate', {'model': MODEL, 'keep_alive': 0, 'stream': False})
            before = api('ps')
            assert not any(m['name'] == MODEL for m in before['models'])
            calls = []
            runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([]), use_live_model=True)
            question = f'Trong tài liệu {fixture["filename"]}, mã xác nhận là gì? Chỉ trả mã xác nhận, không giải thích.'
            started = time.perf_counter()
            response = answer_selected_document(runtime, question, str(path), model_client=client,
                on_model_call=calls.append)
            row = {'case': fixture['id'], 'initial_model_state': 'cold', 'wall_s': time.perf_counter() - started,
                'calls': calls, 'response': asdict(response),
                'task_success': bool(not response.error and response.answer.strip().strip('`') == fixture['code']
                    and any(s.get('path') == str(path) and s.get('read') for s in response.sources))}
            rows.append(row)
            with (output / 'trials.jsonl').open('a') as journal:
                journal.write(json.dumps(row, ensure_ascii=False) + '\n')
                journal.flush()
            print(json.dumps({'case': row['case'], 'wall_s': row['wall_s'], 'calls': len(calls),
                              'task_success': row['task_success'], 'error': response.error}), flush=True)
            if response.error or len(calls) != 1:
                break
        manifest['status'] = 'completed' if len(rows) == 3 else 'stopped'
    finally:
        api('generate', {'model': MODEL, 'keep_alive': 0, 'stream': False})
        manifest['models_after_cleanup'] = api('ps')
        manifest['source_changed'] = [n for n, sha in sources.items()
            if hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != sha]
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        db.get_connection().close()


if __name__ == '__main__':
    main()
