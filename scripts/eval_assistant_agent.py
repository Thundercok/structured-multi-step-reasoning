"""RAT development fixture check with raw traces and pending human review.

Live model calls use artificial local documents and a fixed timetable. These are
exposed development fixtures, not unseen tests or NCKH quality measurements.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.request

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.model import ClassSession, MemberSchedule
from rat.ui.chat_session import ConversationHistory


def run_check(mode, output, requests=None, model=None):
    if output.exists():
        raise ValueError('Output must be a new directory')
    output.mkdir(parents=True)
    from rat.engine.slm import slm_engine
    from rat.engine.slm import SLMEngine
    client = SLMEngine(model=model, ollama_url=slm_engine.ollama_url) if model else slm_engine
    evidence = 'synthetic_smoke' if mode == 'smoke' else 'measured_app_development_fixture'
    manifest = {'evidence': evidence, 'status': 'running', 'model': client.model if mode == 'live' else 'scripted_fixture',
                'review_status': 'pending', 'quality_claim': None, 'stage0_changed': False,
                'token_scope': 'all_call_prompt_and_completion' if mode == 'live' else 'synthetic_zero_tokens',
                'sources_are_artificial': True, 'controller': 'none', 'test_evaluation': False,
                'source_sha256': hashlib.sha256(Path('rat/engine/assistant_runtime.py').read_bytes()).hexdigest()}
    if mode == 'live':
        try:
            with urllib.request.urlopen(slm_engine.ollama_url + '/api/tags', timeout=5) as reply:
                manifest['model_metadata'] = json.load(reply)
        except Exception as exc:
            manifest['model_metadata_error'] = str(exc)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    with tempfile.TemporaryDirectory() as directory:
        fixture_dir = output.resolve() / 'fixture'
        fixture_dir.mkdir()
        file = fixture_dir / 'networks.txt'
        file.write_text('Networks NET101: TCP retransmits missing segments.\nExercise: explain timeout backoff.\nChapter 2: IP routing.\nChapter 3: TCP transport.')
        db = Database(str(Path(directory) / 'index.db'))
        db.get_connection().execute('''INSERT INTO documents
            (file_path,file_name,file_ext,file_size,created_at,modified_at,content_text,summary,normalized_text,indexed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (str(file), file.name, '.txt', file.stat().st_size, 1, 1, file.read_text(), 'Networks NET101 TCP transport', 'networks net101 tcp transport', 1))
        db.get_connection().commit()
        member = MemberSchedule(id='fixture-student', name='Fixture Student', schedule={
            'T2': [ClassSession(1, 3, 'Networks', 'B203', course_code='NET101')],
        })
        runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([member]), use_live_model=mode == 'live', model_client=client, plan_tasks=mode == 'live')
        conversation, sources, task_state = ConversationHistory(), [], {}
        requests = requests or ['Buổi học tiếp theo của mình cần chuẩn bị gì? Tìm và đọc tài liệu giúp mình.',
                               'Tóm tắt nội dung tài liệu đó thành 3 ý; mình đã hiểu phần IP routing rồi.']
        fixture = {'member': asdict(member), 'now': '2026-10-12T06:00:00', 'requests': requests,
                   'file_sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
        (fixture_dir / 'context.json').write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + '\n')
        for index, query in enumerate(requests):
            if mode == 'smoke':
                decisions = ([ModelDecision('', tool_name='get_schedule', tool_args={'target_date': 'next'}),
                    ModelDecision('', tool_name='search_documents', tool_args={'query': 'Networks'}),
                    ModelDecision('', tool_name='read_document', tool_args={'file_path': str(file)}),
                    ModelDecision('', final_answer='Fixture answer about TCP.')] if index == 0 else
                    [ModelDecision('', final_answer='Fixture follow-up answer.')])
                iterator = iter(decisions)
                runtime.model_callable = lambda goal, steps: next(iterator)
            response = runtime.run(query, history=conversation.context_messages(), previous_sources=sources, member_id=member.id,
                                   now_dt=datetime(2026, 10, 12, 6), max_steps=8, task_state=task_state)
            record = {'id': f'dev-{index}', 'query': query, 'evidence': evidence, 'review_status': 'pending',
                      'task_success': None, 'response': asdict(response)}
            with (output / 'records.jsonl').open('a') as stream:
                stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            if not response.error:
                conversation.add_turn(query, response.answer)
            else:
                conversation.add_attempt(query, 'cancelled' if response.error == 'cancelled' else 'failed')
            sources = response.sources or sources
            task_state = response.task_state or task_state
            print(json.dumps({'id': record['id'], 'error': response.error, 'tool_calls': response.tool_call_count,
                              'tokens': response.total_tokens, 'latency_ms': round(response.total_time_ms)}, ensure_ascii=False), flush=True)
        db.get_connection().close()
    manifest['status'] = 'completed'
    manifest['records_sha256'] = hashlib.sha256((output / 'records.jsonl').read_bytes()).hexdigest()
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['smoke', 'live'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--request', action='append', help='Override development requests; repeat for conversational follow-ups')
    parser.add_argument('--model', help='Installed Ollama model; no download or settings mutation')
    args = parser.parse_args()
    run_check(args.mode, args.output, args.request, args.model)


if __name__ == '__main__':
    main()
