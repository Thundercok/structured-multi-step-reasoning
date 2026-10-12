"""Compare installed models on exposed paraphrases; final task quality needs review.

Every paraphrase uses the same underlying fixture/group. There is no claim of a
held-out test and no automatic label based merely on whether a tool was called.
"""
import argparse
import hashlib
import json
from pathlib import Path
from scripts.eval_assistant_agent import run_check

CONVERSATIONS = (
    ['Buổi học tiếp theo của mình cần chuẩn bị gì? Tìm và đọc tài liệu giúp mình. Mình có 20 phút.',
     'Rút lại thành 3 ý; mình đã hiểu IP routing rồi.'],
    ['Bạn xem mình sắp học môn gì, đọc tài liệu môn đó và giúp chuẩn bị trong 20 phút.',
     'Bỏ phần IP routing vì mình biết rồi, ưu tiên bài tập nhé.'],
    ['Please find my next class and read its notes. Make a 20-minute preparation plan.',
     'I already understand IP routing. Focus on the exercise and preserve the time budget.'],
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['live', 'smoke'], required=True)
    parser.add_argument('--model', action='append', help='Repeat to compare installed Ollama models; never downloads')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    rows = []
    for model_index, model in enumerate(args.model or [None]):
        for variant, requests in enumerate(CONVERSATIONS):
            directory = args.output / f'model-{model_index}-variant-{variant}'
            run_check(args.mode, directory, requests, model)
            manifest = json.loads((directory / 'manifest.json').read_text())
            for line in (directory / 'records.jsonl').read_text().splitlines():
                record = json.loads(line)
                response = record['response']
                observed = [step['tool_name'] for step in response['steps'] if step['tool_name']]
                rows.append({'id': f'{directory.name}-{record["id"]}', 'group_id': 'network-preparation-fixture',
                    'split': 'exposed_development', 'model': manifest['model'], 'query': record['query'],
                    'response': response['answer'], 'error': response['error'], 'observed_tools': observed,
                    'reported_tokens': response['total_tokens'], 'measured_latency_ms': response['total_time_ms'],
                    'document_read_observed': any(s.get('type') == 'document' and s.get('read') for s in response['sources']),
                    'completion_self_report': response['completion_status'],
                    'task_success': None, 'grounding_score': None, 'constraint_score': None, 'review_status': 'pending',
                    'trace': str(directory / 'records.jsonl')})
    payload = {'evidence': 'synthetic_smoke' if args.mode == 'smoke' else 'measured_app_development_fixture',
               'stage0_changed': False, 'grouping': 'all paraphrases share the same fixture group; not held out',
               'token_scope': 'all reported prompt+completion counts',
               'review_rubric': 'Rate final task completion, support in read evidence, retained time/prior-knowledge constraints; diagnose model, context or tool failure. Tool presence and model self-report alone do not imply success.',
               'rows': rows}
    (args.output / 'review.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
