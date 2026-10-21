"""Recover verified copies in r5 only; never overwrite a previous audit."""
import hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PRIOR = ROOT / 'audit/rat_cot_runtime_codex_review_r4_20261021'
SNAP = PRIOR / 'reviewed_source'
DEST = HERE / 'recovered_r4_counterexamples'
DEST.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

runtime = load('reasoning._r4_recovery_runtime', SNAP / 'reasoning/runtime.py')
bundle = load('reasoning._r4_recovery_bundle', SNAP / 'reasoning/bundle.py')
probe = load('_r4_recovery_probe', PRIOR / 'test_remaining_contracts.py')
probe.HERE = DEST
probe.helper.HERE = DEST
probe.helper.ROOT = SNAP
probe.helper.OnlineReasoningController = runtime.OnlineReasoningController
probe.helper.create_synthetic_specimen_bundle = bundle.create_synthetic_specimen_bundle
try:
    probe.test_failure_message_does_not_change_recorded_dispatch_count()
except AssertionError:
    reproduced = True
else:
    reproduced = False
relative = 'prior_probe_outputs/rat_cot_runtime_codex_review_r2_20261020/qwen_failure_case.json'
target = DEST / relative
target.parent.mkdir(parents=True, exist_ok=True)
copy_source = PRIOR / 'received_prior_drift/rat_cot_runtime_codex_review_r2_20261020/qwen_failure_case.json'
shutil.copy2(copy_source, target)
manifest = json.loads((PRIOR / 'artifact_manifest.json').read_text())['files']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
checks = {}
for name in ('error_message_dispatch_cases.json', relative):
    expected = manifest[name]['sha256']
    checks[name] = {'original_sha256': expected, 'recovered_copy_sha256': sha(DEST / name), 'matches_original_manifest': sha(DEST / name) == expected, 'recovered_path': str((DEST/name).relative_to(HERE))}

# Timing-bearing JUnit XML cannot be recreated honestly from source alone.
# Look only for an existing byte-identical XML backup under audit/.
entry = manifest['baseline.xml']
candidates = []
matches = []
for line in subprocess.check_output(['rg', '--files', '--hidden', '--no-ignore', 'audit', '-g', '*.xml'], cwd=ROOT, text=True).splitlines():
    path = ROOT / line
    if path.stat().st_size == entry['bytes']:
        candidates.append(line)
        if sha(path) == entry['sha256']:
            matches.append(line)
record = {
    'outputs': checks,
    'original_r4_failure_reproduced': reproduced,
    'source_inputs': {str(path.relative_to(ROOT)): sha(path) for path in (SNAP/'reasoning/runtime.py', SNAP/'reasoning/bundle.py', SNAP/'qwen_mlx_backend.py', PRIOR/'test_remaining_contracts.py', copy_source)},
    'baseline_xml': {'original_entry': entry, 'received_sha256': sha(PRIOR/'baseline.xml'), 'backup_search_scope': 'Existing XML files visible to rg --hidden --no-ignore under audit, filtered by original byte size.', 'same_size_candidates': candidates, 'byte_identical_backups': matches, 'reconstructed': False},
    'old_files_modified': False, 'real_model_calls': 0,
}
(HERE / 'recovery.json').write_text(json.dumps(record, indent=2)+'\n')
assert reproduced and all(x['matches_original_manifest'] for x in checks.values())
print(json.dumps({'verified_original_copies': len(checks), 'baseline_xml_backups_found': matches, 'old_files_modified': False}, indent=2))
