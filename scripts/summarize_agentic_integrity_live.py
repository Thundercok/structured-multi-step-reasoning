"""Summarize retained live evidence without generating or modifying responses."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'artifacts/rat_agentic_integrity_20261025'


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def main():
    attempts = []
    for folder in sorted(BASE.glob('live_*')):
        environment = json.loads((folder / 'environment.json').read_text()) if (folder / 'environment.json').exists() else {}
        calls = records(folder / 'model_calls.jsonl')
        known = [r for r in calls if r.get('response', {}).get('token_usage_known') is True]
        turns = []
        queries = {}
        for event in records(folder / 'ui_snapshots.jsonl'):
            snap = event.get('snapshot', {})
            if snap.get('turnId') and snap.get('userQuery'):
                queries[snap['turnId']] = snap['userQuery']
        for response in records(folder / 'responses.jsonl'):
            notes = []
            for step in response.get('steps', []):
                result = step.get('tool_result')
                if isinstance(result, dict) and result.get('artifact_kind') == 'structured_note':
                    notes.append({k: result.get(k) for k in ('note_id', 'revision', 'source_sha256',
                        'synthesis_mode', 'action_items', 'expansion_content')})
            turns.append({k: response.get(k) for k in ('turn_id', 'error', 'answer', 'completion_status',
                'answer_verification_status', 'prompt_tokens', 'completion_tokens', 'cached_tokens', 'total_time_ms')}
                | {'query': (response.get('turn_reference') or {}).get('query') or queries.get(response.get('turn_id'), ''),
                   'operations': [{'name': s.get('tool_name'), 'error': s.get('error')}
                                  for s in response.get('steps', []) if s.get('tool_name') or s.get('error')],
                   'observed_note_revisions': notes})
        transcript = ['# Actual live conversation — ' + folder.name, '',
                      'Recorded public prompts/responses; includes failures. No synthetic completions.', '']
        for turn in turns:
            transcript.extend(['## ' + str(turn.get('turn_id')), '',
                '**User:** ' + turn.get('query', ''), '', '**Assistant:**', '', turn.get('answer') or '(No public answer)', '',
                '**Runtime error:** ' + str(turn.get('error')), '',
                '**Verification:** ' + str(turn.get('answer_verification_status')), ''])
        (folder / 'conversation.md').write_text('\n'.join(transcript))
        screenshots = [{'path': str(p.relative_to(ROOT)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                       for p in sorted(folder.glob('*.png'))]
        attempts.append({'attempt': folder.name, 'environment': environment, 'logged_chat_calls': len(calls),
            'reported_prompt_tokens': sum(r['response']['prompt_tokens'] for r in known),
            'reported_completion_tokens': sum(r['response']['completion_tokens'] for r in known),
            'calls_with_unknown_usage': len(calls) - len(known),
            'call_errors': [r.get('response', {}).get('error') for r in calls if r.get('response', {}).get('error')],
            'turns': turns, 'screenshots': screenshots})
    summary = {'evidence_kind': 'actual_ui_local_model_acceptance_with_retained_failures',
        'acceptance': 'PARTIAL', 'first_attempt_complete_journey_passed': False,
        'cost_scope': 'reported prompt + completion for logged chat calls only; missing usage unknown; cache counts may be unavailable',
        'recording_limitations': 'live_01 observer failed; absent call records do not mean zero inference. No claim of full inference cost or online speedup.', 
        'research_stage0_changed': False, 'attempts': attempts}
    (BASE / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    audit = ROOT / 'audit/rat_agentic_integrity_20261025'
    manifest = []
    paths = [*BASE.glob('live_*/*.json'), *BASE.glob('live_*/*.jsonl'), *BASE.glob('live_*/*.png'), *BASE.glob('live_*/*.md')]
    for path in sorted(paths):
        manifest.append({'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (audit / 'evidence_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(json.dumps({'summary': str(BASE / 'summary.json'), 'attempts': len(attempts),
                      'turns': sum(len(a['turns']) for a in attempts), 'acceptance': 'PARTIAL'}))


if __name__ == '__main__':
    main()
