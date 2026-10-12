"""App-only paired development collector. Leaves all quality labels for review."""
import argparse
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
import tempfile

from rat.crawler.db import Database
from rat.engine.assistant_runtime import AssistantRuntime, ModelDecision
from rat.engine.paired_continuation import canonical_bytes, collect_pair
from rat.timetable.compositor import TimetableCompositor
from rat.timetable.model import ClassSession, MemberSchedule


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['live', 'smoke'], required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--group-id', required=True, help='Underlying problem; keep all paraphrases in this group/split')
    parser.add_argument('--split', choices=['train', 'calibration', 'test'], required=True)
    parser.add_argument('--tool', choices=['get_schedule', 'search_documents', 'read_document'], default='read_document')
    parser.add_argument('--model')
    parser.add_argument('--request', default='Tìm và đọc tài liệu Networks, giải thích bài tập TCP timeout backoff. Mình có 20 phút và đã hiểu IP routing.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    file = args.output.resolve() / 'networks.txt'
    file.write_text('Networks NET101. TCP retransmits missing segments. Exercise: explain timeout backoff. After consecutive timeouts, double the retransmission timeout; use acknowledgment and retry limits. IP routing is in a separate chapter.\n')
    from rat.engine.slm import SLMEngine, slm_engine
    client = SLMEngine(model=args.model, ollama_url=slm_engine.ollama_url) if args.model else slm_engine
    with tempfile.TemporaryDirectory() as temporary:
        db = Database(str(Path(temporary) / 'index.db'))
        db.get_connection().execute('''INSERT INTO documents
            (file_path,file_name,file_ext,file_size,created_at,modified_at,content_text,summary,normalized_text,indexed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)''', (str(file), file.name, '.txt', file.stat().st_size, 1, 1,
              file.read_text(), 'Networks NET101 TCP', 'networks net101 tcp', 1))
        db.get_connection().commit()
        member = MemberSchedule(id='fixture-student', name='Fixture Student', schedule={'T2': [ClassSession(1, 3, 'Networks', 'B203', course_code='NET101')]})
        runtime = AssistantRuntime(db=db, compositor=TimetableCompositor([member]), use_live_model=args.mode == 'live', model_client=client, plan_tasks=args.mode == 'live')
        if args.mode == 'smoke':
            def fixture(goal, steps):
                if not steps:
                    return ModelDecision('', tool_name='search_documents', tool_args={'query': 'Networks'})
                if steps[-1].tool_name == 'search_documents':
                    return ModelDecision('', tool_name='read_document', tool_args={'file_path': str(file)})
                return ModelDecision('', final_answer='Fixture: no document read.' if steps[-1].tool_result.get('error') else 'Fixture: timeout backoff doubles timeout.')
            runtime.model_callable = fixture
        result = collect_pair(runtime, args.request, proposal_tool=args.tool,
                              member_id=member.id, now_dt=datetime(2026, 10, 12, 6))
        db.get_connection().close()
    (args.output / 'collection.json').write_bytes(canonical_bytes(result))
    if result['pair']:
        pair = result['pair']
        (args.output / 'pair.json').write_bytes(canonical_bytes(pair))
        row = {'id': args.output.name, 'group_id': args.group_id, 'split': args.split,
               'features': pair['features'], 'quality_gain': None, 'reviewed': False,
               'evidence': 'measured_paired_continuation' if args.mode == 'live' else 'synthetic_smoke',
               'stop_tokens': pair['stop']['total_tokens'], 'continue_tokens': pair['continue']['total_tokens'],
               'delta_tokens': pair['continue']['total_tokens'] - pair['stop']['total_tokens'],
               'pair_trace_sha256': result['pair_trace_sha256']}
        (args.output / 'pending_row.json').write_bytes(canonical_bytes(row))
        (args.output / 'review_template.json').write_bytes(canonical_bytes({'pair_trace_sha256': result['pair_trace_sha256'],
            'reviewer': '', 'stop_quality': None, 'continue_quality': None,
            'rubric': '0..1: fulfill requested work, grounded in read content, respect 20-minute limit and skip already-known IP routing', 'notes': ''}))
    manifest = {'status': result['status'], 'model': client.model if args.mode == 'live' else 'scripted_fixture',
                'evidence': 'measured_app_development_fixture' if args.mode == 'live' else 'synthetic_smoke',
                'sources_are_artificial': True, 'stage0_changed': False, 'review_status': 'pending',
                'token_scope': 'reported_prompt_and_completion' if args.mode == 'live' else 'synthetic_zero_tokens',
                'group_id': args.group_id, 'split': args.split}
    (args.output / 'manifest.json').write_bytes(canonical_bytes(manifest))
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
