"""Validate the submitted same-document ledger is an actual single legacy request."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def test_same_document_fixture_contains_one_completed_unknown_request():
    folder=ROOT/'audit/rat_cot_runtime_acceptance_20261020/same_document_legacy_fake'
    records=[]
    invalid_lines=0
    for line in (folder/'calls.jsonl').read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            invalid_lines+=1
    completed=[r for r in records if isinstance(r,dict) and (r.get('event')=='request_complete' or ('completion_tokens' in r and 'event' not in r))]
    assert invalid_lines==0 and len(completed)==1, {'invalid_jsonl_lines':invalid_lines,'completed_request_records':len(completed)}
    perf=json.loads((folder/'native_performance.json').read_text())
    assert perf['historical_ledger_totals']['unknown_records']==1
    assert perf['scope_classification']['status']=='budget_halt_existing_unknown_history'
