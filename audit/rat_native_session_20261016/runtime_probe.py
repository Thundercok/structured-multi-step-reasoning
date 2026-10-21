"""Two native-session questions through RAT's real selected-document runtime."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

state = dict(status='starting', started_utc=datetime.now(timezone.utc).isoformat(),
             network_attempts=0, max_generations=2, scope='Headless RAT fixture, not native UI acceptance')


def save():
    (OUT / 'runtime_manifest.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))


def guard(event, args):
    if event == 'socket.connect':
        state['network_attempts'] += 1
        raise PermissionError('Network disabled in native RAT session probe')


def deadline():
    state.update(status='timeout', error='180-second deadline')
    save()
    os._exit(124)


def main():
    sys.addaudithook(guard)
    timer = threading.Timer(180, deadline)
    timer.daemon = True
    timer.start()
    client = database = None
    save()
    try:
        import psutil
        from rat.engine.mlx_document_session import MLXDocumentSession
        from rat.engine.selected_document_qa import answer_selected_document, selected_document_messages, MAX_READ_CHARS
        from rat.engine.assistant_runtime import AssistantRuntime
        from rat.crawler.db import Database
        from rat.timetable.compositor import TimetableCompositor
        first_manifest = json.loads((OUT / 'manifest.json').read_text())
        if psutil.virtual_memory().available < first_manifest['weight_file_bytes'] + 300 * 2**20:
            raise RuntimeError('insufficient_available_memory')
        names = ['rat/engine/mlx_document_session.py', 'rat/engine/selected_document_qa.py',
                 'rat/engine/assistant_runtime.py', 'tests/test_mlx_document_session.py']
        state['sources'] = {}
        for name in names:
            data = (ROOT / name).read_bytes()
            target = OUT / 'runtime_source' / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            state['sources'][name] = hashlib.sha256(data).hexdigest()
        fixture = json.loads((ROOT / 'audit/rat_overnight_20261015/fixtures.json').read_text())[1]
        path = OUT / fixture['filename']
        path.write_text(fixture['content'])
        database = Database(str(OUT / 'runtime-fixture.db'))
        database.upsert_document(dict(file_path=str(path), file_name=path.name, file_ext='.txt',
            file_size=path.stat().st_size, created_at=1, modified_at=1, indexed_at=1,
            content_text=path.read_text()))
        runtime = AssistantRuntime(db=database, compositor=TimetableCompositor([]), use_live_model=True)
        client = MLXDocumentSession(first_manifest['model_path'])
        state['load_s'] = client.load()
        inputs = json.loads((OUT / 'inputs.json').read_text())
        preparation_read = runtime.registry.execute('read_document',
            {'file_path': str(path), 'max_chars': MAX_READ_CHARS})
        assert preparation_read['found']
        prepared_messages = selected_document_messages('', preparation_read, path.name)[:-1]
        state['preparation'] = client.prepare_context(prepared_messages)
        save()
        for index, question in enumerate(inputs['questions']):
            calls = []
            tick = time.perf_counter()
            response = answer_selected_document(runtime, question, str(path),
                                                model_client=client, on_model_call=calls.append)
            result = dict(question_index=index, wall_s=time.perf_counter()-tick,
                calls=calls, response=asdict(response),
                exact_code=not response.error and response.answer.strip().strip('`') == fixture['code'],
                read_source=any(s.get('path') == str(path) and s.get('read') for s in response.sources),
                committed_read=any(r.operation_name == 'read_document' and r.committed
                                  for r in response.execution_journal.receipts))
            with (OUT / 'runtime_calls.jsonl').open('a') as journal:
                journal.write(json.dumps(result, ensure_ascii=False) + '\n')
            print(json.dumps({k:result[k] for k in ('question_index','wall_s','exact_code','read_source','committed_read')}),flush=True)
            assert len(calls) == 1 and result['exact_code'] and result['read_source'] and result['committed_read']
            assert calls[0]['raw_response']['prefix_already_prepared']
        state['status'] = 'completed'
        state['source_changed'] = [n for n,h in state['sources'].items()
            if hashlib.sha256((ROOT/n).read_bytes()).hexdigest() != h]
    except Exception as error:
        state.update(status='failed', error=repr(error), traceback=traceback.format_exc())
        print(json.dumps({'error':repr(error)}),flush=True)
    finally:
        if client is not None:
            client.close()
            state['session_closed'] = not client.is_loaded
        if database is not None:
            database.get_connection().close()
        timer.cancel()
        state['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return 0 if state['status'] == 'completed' else 1


if __name__ == '__main__':
    sys.exit(main())
