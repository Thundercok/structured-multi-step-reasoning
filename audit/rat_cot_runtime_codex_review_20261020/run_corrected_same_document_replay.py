"""A new, explicitly synthetic same-document request fixture; never edits submitted evidence."""
import hashlib,json,os
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'audit/rat_overnight_sweep_codex_review_r6_20261020/legacy_fake_calls.jsonl'
RECEIVED=ROOT/'audit/rat_cot_runtime_acceptance_20261020/calls.jsonl'
OUT=HERE/'corrected_same_document_replay'
OUT.mkdir(exist_ok=False)
records=[json.loads(s) for s in SOURCE.read_text().splitlines()]
record=next(r for r in records if r.get('event')=='request_complete' or ('completion_tokens' in r and 'event' not in r)).copy()
real=[json.loads(s) for s in RECEIVED.read_text().splitlines()]
record['document_path']=real[0]['document_path']
ledger=OUT/'calls.jsonl'
ledger.write_text(json.dumps(record,ensure_ascii=False)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before=sha(ledger)
cmd=[sys.executable,str(ROOT/'scripts/run_native_performance_session.py'),'--fake-backend','--max-budget','1','--output-dir',str(OUT)]
with (OUT/'run.txt').open('w') as log:
    p=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},stdout=log,stderr=subprocess.STDOUT)
perf=json.loads((OUT/'native_performance.json').read_text())
summary={'evidence':'reviewer-authored synthetic single legacy fake request with document_path replaced by historical real document path','source_fixture':str(SOURCE),'source_fixture_sha256':sha(SOURCE),'modified_field':'document_path','argv':cmd,'exit_code':p.returncode,'ledger_sha256_before':before,'ledger_sha256_after':sha(ledger),'real_calls':perf['real_model_calls_executed'],'fake_calls':perf['fake_model_calls_executed'],'status':perf['scope_classification']['status'],'historical':perf['historical_ledger_totals']}
(OUT/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
assert p.returncode==0 and summary['real_calls']==0 and summary['fake_calls']==0
assert summary['status']=='budget_halt_existing_unknown_history' and summary['historical']['unknown_records']==1
assert before==sha(ledger)
