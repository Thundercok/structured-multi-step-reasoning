"""Recover verified copies in r4 only; never write an earlier audit directory."""
import hashlib, importlib.util, json, shutil, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
PRIOR = ROOT / 'audit/rat_cot_runtime_codex_review_r3_20261020'
SNAP = PRIOR / 'reviewed_source'

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

old_runtime = load('reasoning._r3_recovery_runtime', SNAP / 'reasoning/runtime.py')
old_bundle = load('reasoning._r3_recovery_bundle', SNAP / 'reasoning/bundle.py')
probe = load('_r3_recovery_probe', PRIOR / 'test_boundary_contracts.py')
probe.ROOT = SNAP
probe.HERE = HERE / 'recovered_r3_counterexamples'
probe.HERE.mkdir(exist_ok=True)
probe.OnlineReasoningController = old_runtime.OnlineReasoningController
probe.create_synthetic_specimen_bundle = old_bundle.create_synthetic_specimen_bundle
calls = [
    ('caller-unsupported', lambda: probe.test_caller_name_does_not_change_identical_execution('test_unsupported_hard_cap_rejected_before_generation')),
    ('caller-ceiling', lambda: probe.test_caller_name_does_not_change_identical_execution('test_generated_token_ceiling_is_enforced_within_final_strategy')),
    ('decode-error', probe.test_decode_exception_preserves_already_yielded_token_cost),
    ('cancel-tokens', lambda: probe.test_cancel_after_stream_yield_accounts_for_generation_and_outcome('generated-tokens')),
    ('cancel-outcome', lambda: probe.test_cancel_after_stream_yield_accounts_for_generation_and_outcome('outcome-success')),
    ('between-sc', probe.test_inter_sample_cancel_does_not_invent_new_dispatch),
]
outcomes = {}
for name, call in calls:
    try:
        call()
    except AssertionError:
        outcomes[name] = 'original assertion failure reproduced'
    else:
        outcomes[name] = 'returned'

r2 = HERE / 'recovered_r2_counterexamples'
r2.mkdir(exist_ok=True)
for name in ('qwen_failure_case.json', 'qwen_token_cap_case.json'):
    shutil.copy2(PRIOR / 'recovered_r2_counterexamples' / name, r2 / name)

sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = {}
for dirname, dest in (
    ('rat_cot_runtime_codex_review_r2_20261020', r2),
    ('rat_cot_runtime_codex_review_r3_20261020', probe.HERE),
):
    directory = ROOT / 'audit' / dirname
    manifest = json.loads((directory / 'artifact_manifest.json').read_text())['files']
    for path in sorted(dest.glob('*.json')):
        expected = manifest[path.name]['sha256']
        checks[f'{dirname}/{path.name}'] = {
            'expected_original_sha256': expected,
            'recovered_copy_sha256': sha(path),
            'received_prior_file_sha256': sha(directory / path.name),
            'matches_original_manifest': sha(path) == expected,
            'recovered_path': str(path.relative_to(HERE)),
        }

record = {
    'method': 'Copy two already verified r2 originals; replay six scripted r3 counterexamples with hash-pinned historical source snapshots and native imports removed.',
    'source_inputs': {str(p.relative_to(ROOT)): sha(p) for p in (
        SNAP / 'reasoning/runtime.py', SNAP / 'reasoning/bundle.py',
        SNAP / 'qwen_mlx_backend.py', PRIOR / 'test_boundary_contracts.py',
    )},
    'original_assertion_outcomes': outcomes,
    'outputs': checks,
    'prior_files_modified': False,
    'real_model_calls': 0,
}
(HERE / 'recovery.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({'verified_original_copies': sum(x['matches_original_manifest'] for x in checks.values()), 'total': len(checks), 'original_assertion_outcomes': outcomes}, indent=2))
assert len(checks) == 8 and all(x['matches_original_manifest'] for x in checks.values())
