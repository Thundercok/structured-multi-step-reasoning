"""Reconstruct two overwritten synthetic r2 JSONs in a NEW folder from pinned snapshots.

No previous audit is edited. No native imports, model loading or inference.
"""
import hashlib,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
PRIOR=ROOT/'audit/rat_cot_runtime_codex_review_r2_20261020'
SNAP=PRIOR/'reviewed_source'
DEST=HERE/'recovered_r2_counterexamples';DEST.mkdir(exist_ok=True)

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module

old_runtime=load('reasoning._r2_recovery_runtime',SNAP/'reasoning/runtime.py')
old_bundle=load('reasoning._r2_recovery_bundle',SNAP/'reasoning/bundle.py')
probe=load('_r2_recovery_probe',PRIOR/'test_qwen_boundary_replay.py')
probe.ROOT=SNAP
probe.OnlineReasoningController=old_runtime.OnlineReasoningController
probe.create_synthetic_specimen_bundle=old_bundle.create_synthetic_specimen_bundle
probe.HERE=DEST
backend,counters,controller=probe.source_backend(fail_dispatch=4)
try:
    controller.solve('authored synthetic arithmetic fixture')
except RuntimeError as exc:
    failure={'counters':counters,'current_trace':backend.last_trace,'ledger':exc.cost_ledger.__dict__}
else:raise AssertionError('Pinned old failure path did not fail')
(DEST/'qwen_failure_case.json').write_text(json.dumps(failure,indent=2)+'\n')
backend,counters,controller=probe.source_backend(confidence=.99)
result=controller.solve('authored synthetic arithmetic fixture',max_generated_tokens=1)
cap={'counters':counters,'current_trace':backend.last_trace,'ledger':result.cost_ledger.__dict__}
(DEST/'qwen_token_cap_case.json').write_text(json.dumps(cap,indent=2)+'\n')
manifest=json.loads((PRIOR/'artifact_manifest.json').read_text())['files']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks={name:{'expected_r2_sha256':manifest[name]['sha256'],'recovered_sha256':sha(DEST/name),'current_prior_file_sha256':sha(PRIOR/name),'matches_original_manifest':sha(DEST/name)==manifest[name]['sha256']} for name in ('qwen_failure_case.json','qwen_token_cap_case.json')}
record={'evidence':'exact reconstruction of scripted synthetic fixtures using hash-pinned r2 runtime, bundle and Qwen source snapshots','input_sources':{str(p.relative_to(ROOT)):sha(p) for p in (SNAP/'reasoning/runtime.py',SNAP/'reasoning/bundle.py',SNAP/'qwen_mlx_backend.py',PRIOR/'test_qwen_boundary_replay.py')},'outputs':checks,'prior_files_modified':False,'real_model_calls':0}
(DEST/'recovery.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
assert all(x['matches_original_manifest'] for x in checks.values())
