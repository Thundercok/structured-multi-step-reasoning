"""Run five offline CLI cases with new outputs and explicit fake mode only."""
import hashlib,json,os
from pathlib import Path
import shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SOURCE=ROOT/'audit/rat_cot_runtime_acceptance_20261020'
DEST=HERE/'fresh_replays'
DEST.mkdir(exist_ok=False)
cases=[('fake_session',1,None),('fake_history_halt',1,DEST/'fake_session/calls.jsonl'),('locked_ledger_replay',12,SOURCE/'calls.jsonl'),('legacy_fake_history_halt',1,SOURCE/'legacy_fake_history_halt/calls.jsonl'),('same_document_legacy_fake',1,SOURCE/'same_document_legacy_fake/calls.jsonl')]
results=[]
for name,budget,seed in cases:
    out=DEST/name;out.mkdir()
    seed_hash=None
    if seed:
        shutil.copy2(seed,out/'calls.jsonl')
        seed_hash=hashlib.sha256(seed.read_bytes()).hexdigest()
    cmd=[sys.executable,str(ROOT/'scripts/run_native_performance_session.py'),'--fake-backend','--max-budget',str(budget),'--output-dir',str(out)]
    with (DEST/f'{name}.txt').open('w') as log:
        result=subprocess.run(cmd,cwd=ROOT,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},stdout=log,stderr=subprocess.STDOUT)
    perf=json.loads((out/'native_performance.json').read_text()) if (out/'native_performance.json').is_file() else {}
    ledger_hash=hashlib.sha256((out/'calls.jsonl').read_bytes()).hexdigest() if (out/'calls.jsonl').is_file() else None
    results.append(dict(case=name,argv=cmd,exit_code=result.returncode,real_calls=perf.get('real_model_calls_executed'),fake_calls=perf.get('fake_model_calls_executed'),scope_classification=perf.get('scope_classification'),seed_ledger_sha256=seed_hash,end_ledger_sha256=ledger_hash,seed_ledger_preserved=seed_hash==ledger_hash if seed else None))
(DEST/'commands.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
sys.exit(0 if all(r['exit_code']==0 and r['real_calls']==0 for r in results) else 1)
