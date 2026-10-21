"""Read-only end checks and machine-readable review evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib, json, re, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SUBMITTED = ROOT / 'audit/rat_cot_runtime_acceptance_20261020'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
read = lambda p: json.loads(p.read_text())
def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
def current_files(directory):
    return {str(p.relative_to(directory)): sha(p) for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p.suffix != '.pyc'}
def junit(path):
    tree = ET.parse(path)
    cases = tree.findall('.//testcase')
    failed = [x.attrib['name'] for x in cases if x.find('failure') is not None]
    errors = [x.attrib['name'] for x in cases if x.find('error') is not None]
    skipped = [x.attrib['name'] for x in cases if x.find('skipped') is not None]
    return {
        'tests': len(cases), 'passed': len(cases)-len(failed)-len(errors)-len(skipped),
        'failed': len(failed), 'errors': len(errors), 'skipped': len(skipped),
        'failures': failed,
        'class_counts': dict(Counter(x.attrib.get('classname', '') for x in cases)),
        'duration_xml_s': sum(float(s.attrib['time']) for s in tree.findall('.//testsuite')),
    }

initial = read(HERE / 'integrity_initial.json')
sources = read(HERE / 'source_start.json')['files']
end_sources = {name: sha(ROOT / name) for name in sources}
write('source_end.json', {'files': end_sources})
source_changed = {name: {'before': digest, 'after': end_sources[name]} for name, digest in sources.items() if digest != end_sources[name]}
incoming_now = current_files(SUBMITTED)
incoming_before = initial['incoming_files']
incoming_changed = {name: {'before': digest, 'after': incoming_now.get(name)} for name, digest in incoming_before.items() if incoming_now.get(name) != digest}
incoming_added = sorted(set(incoming_now) - set(incoming_before))
historical = {}
for name, info in initial['prior_reviews'].items():
    directory = ROOT / 'audit' / name
    changed = {f: {'before': digest, 'after': sha(directory / f)} for f, digest in info['current_files'].items() if sha(directory / f) != digest}
    historical[name] = {
        'manifest_entries': info['entries'],
        'preexisting_mismatches': info['mismatches'],
        'changes_during_r4': changed,
    }
source_manifest = read(SUBMITTED / 'source_end.json')['files']
source_mismatch = {f: {'expected': h, 'actual': sha(ROOT/f)} for f,h in source_manifest.items() if sha(ROOT/f) != h}
artifact_manifest = read(SUBMITTED / 'artifact_manifest.json')
artifact_mismatch = {f: {'expected': digest, 'actual': sha(SUBMITTED/f)} for f,digest in artifact_manifest.items() if sha(SUBMITTED/f) != digest}

packet = ROOT / 'audit/cot_restart_fresh_data_review_20261016'
manifest = read(packet / 'manifest.json')
expected_data = dict(manifest['inputs_sha256'])
expected_data.update({str((packet / name).relative_to(ROOT)): digest for name,digest in manifest['artifact_sha256'].items()})
data_checks = {f: {'expected': h, 'actual': sha(ROOT/f), 'matches': sha(ROOT/f) == h} for f,h in expected_data.items()}
write('data_integrity.json', {
    'checks': data_checks, 'passed': sum(x['matches'] for x in data_checks.values()), 'total': len(data_checks),
    'structural_review': 'Inherited only for byte-identical pinned inputs from r1 data_integrity.json; no rerun of semantic/human review.',
    'human_review': 'pending', 'held_out_queries_or_gold_emitted': False,
})

crosschecks = []
for item in read(SUBMITTED / 'commands.json'):
    counts = junit(SUBMITTED / item['junit_xml'])
    raw = (SUBMITTED / item['raw_log']).read_text()
    summaries = re.findall(r'(\d+) passed(?:, (\d+) skipped)? in ([\d.]+)s', raw)
    last_summary = summaries[-1] if summaries else None
    crosschecks.append({
        'name': item['name'], 'declared': item, 'xml': counts, 'raw_summary': last_summary,
        'counts_match': counts['tests'] == item['total_tests'] and counts['passed'] == item['passed'] and counts['failed'] == item['failed'] and counts['errors'] == 0 and last_summary is not None and int(last_summary[0]) == item['passed'],
        'raw_duration_matches_declared': last_summary is not None and float(last_summary[2]) == item['duration_s'],
    })
write('submitted_raw_crosscheck.json', {
    'suites': crosschecks,
    'all_declared_counts_match_raw_and_xml': all(x['counts_match'] for x in crosschecks),
    'all_raw_durations_match_commands_json': all(x['raw_duration_matches_declared'] for x in crosschecks),
    'attachment_duration_note': 'Pasted handoff and raw log say 4.04s for Qwen replay (XML 4.037s), while commands.json retains 2.37s. Counts agree at 3; this is stale command timing metadata.',
    'scope': 'Artifact consistency check; only suites in reviewer commands.json were independently executed in r4.',
})

baseline = junit(HERE / 'baseline.xml')
probes = junit(HERE / 'remaining_contracts.xml')
groups = baseline['class_counts']
commands = [
    {'command': 'python audit/rat_cot_runtime_codex_review_r4_20261021/run_baseline.py', 'exit_code': 0,
     'raw_log': 'baseline.txt', 'junit_xml': 'baseline.xml', 'result': baseline,
     'host_permission': 'Offline host execution for PyQt6; Qt runtime aborts in sandbox. No weights loaded or real inference.',
     'duration_stdout_s': 47.80,
     'components': {'submitted_372': 372, 'r3_boundary': 19, 'r2_native_replay': 3},
     'subsets_already_in_394': {
         'mandatory_research': sum(groups[k] for k in ('tests.test_research_study', 'test_optimal_stopping', 'test_entry_predictor')),
         'native_readiness': groups['tests.test_native_acceptance_readiness'],
         'G1_failed_reporting': groups['audit.rat_overnight_sweep_codex_review_r7_20261020.test_failed_request_reporting'],
     }},
    {'command': 'python -m pytest audit/rat_cot_runtime_codex_review_r4_20261021/test_remaining_contracts.py -q --junitxml=audit/rat_cot_runtime_codex_review_r4_20261021/remaining_contracts.xml',
     'exit_code': 1, 'raw_log': 'remaining_contracts.txt', 'junit_xml': 'remaining_contracts.xml', 'result': probes, 'duration_stdout_s': 3.23,
     'scope': 'Actual Qwen strategy and stream-loop source with MLX imports removed and scripted stream provider; no model constructor.'},
    {'command': 'python -m pytest test_qwen_mlx_backend_mocked.py test_reasoning_strategies.py tests/test_research_scoring.py -q',
     'exit_code': 0, 'raw_log': 'backend_scoring.txt', 'result': {'passed': 68, 'skipped': 2}, 'duration_stdout_s': 5.91,
     'skipped_reason': 'Native MLX bfloat16 arrays unavailable in mock environment.'},
    {'command': 'python audit/rat_cot_runtime_codex_review_r4_20261021/recover_historical_evidence.py',
     'exit_code': 0, 'raw_log': 'recovery.txt', 'record': 'recovery.json', 'verified_original_copies': 8},
    {'command': 'python audit/rat_cot_runtime_codex_review_r4_20261021/capture_bundle_evidence.py',
     'exit_code': 0, 'raw_log': 'bundle_parameter_cases.txt', 'record': 'bundle_parameter_cases.json', 'approved_invalid_fixtures': 5},
    {'command': 'python audit/rat_cot_runtime_codex_review_r4_20261021/build_validation.py',
     'exit_code': 0, 'raw_log': 'final_checks.txt',
     'earlier_attempts': [
         {'script_exit_code': 1, 'log': 'final_checks_initial_setup_error.txt', 'reason': 'Expected a wrapped files mapping; submitted artifact manifest uses a flat digest mapping. Reader fixed.'},
         {'script_exit_code': 1, 'log': 'final_checks_source_drift_detected.txt', 'reason': 'Three unrelated UI source changes detected. Preserved, recorded and explicitly excluded from final-checkout approval.'},
     ]},
]
write('commands.json', commands)
status = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
(HERE / 'git_status_final.txt').write_text(status)
branch = subprocess.check_output(['git','branch','--show-current'], cwd=ROOT, text=True).strip()
final_integrity = {
    'source_snapshot_count': len(sources), 'source_changed': source_changed,
    'submitted_source_matches': len(source_manifest)-len(source_mismatch), 'submitted_source_count': len(source_manifest), 'submitted_source_mismatches': source_mismatch,
    'submitted_artifact_matches': len(artifact_manifest)-len(artifact_mismatch), 'submitted_artifact_count': len(artifact_manifest), 'submitted_artifact_mismatches': artifact_mismatch,
    'incoming_files_compared': len(incoming_before), 'incoming_changed': incoming_changed, 'incoming_added': incoming_added,
    'prior_reviews': historical,
    'ledger_sha256': sha(SUBMITTED/'calls.jsonl'), 'ledger_unchanged': sha(SUBMITTED/'calls.jsonl') == initial['ledger_sha256'],
    'branch': branch,
    'git_status_unchanged': status == (HERE/'git_status_initial.txt').read_text(),
    'recovered_original_copies': 8,
    'reviewed_core_unchanged': all(end_sources[name] == sources[name] for name in ('reasoning/runtime.py', 'reasoning/bundle.py', 'qwen_mlx_backend.py', 'rat/ui/reasoning_worker.py')),
    'source_scope_note': 'Three unrelated UI files changed after baseline test completion according to recorded mtimes. Preserve them; the 394-pass run is not certification of the final UI checkout. See source_drift.json and end_source_drift/.',
}
write('integrity_final.json', final_integrity)
validation = {
    'review': 'r4', 'date': '2026-10-21', 'verdict': 'REQUEST_CHANGES',
    'open_findings': {'P1': ['R2','R3','R5'], 'P2': ['R12']},
    'closed_this_review': ['R11','R6'],
    'retained_closed_with_scope_limits': ['R1','R4','R7','R8','R9','R10','G1'],
    'baseline': {k:v for k,v in baseline.items() if k != 'class_counts'},
    'new_boundary_probes': {k:v for k,v in probes.items() if k != 'class_counts'},
    'backend_strategy_scoring': {'passed': 68, 'skipped': 2},
    'real_model_calls': 0, 'git_mutations': 0,
    'stage_0_gate': 'unchanged; not established as passed', 'human_data_review': 'pending',
    'native_interactive_acceptance': 'pending',
    'costs': 'Scripted synthetic generated-token counts, not full inference costs.',
    'timing': 'Software test wall time; not measured online model latency.',
    'historical_manifest_drift_at_receipt': 8, 'original_copies_recovered_in_r4': 8,
    'legacy_probe_scope': 'No requirement to pass r1/r2 contradictory unsupported-hard-cap expectations; immutable history retained. r3 uniform safe-rejection and caller-invariance contracts pass.',
    'final_checkout_scope': 'No blanket final-checkout approval: assistant_worker.py, omnibar.py and workbench_scene.py drifted during r4, with mtimes after the 394-test run. Four reviewed runtime/bundle/Qwen/reasoning_worker core files remain hash-identical. Newly observed rat/engine/execution.py and audit/rat_flow_optimization_20261021/ are out of review scope.',
}
write('validation.json', validation)
assert set(source_changed) == {'rat/ui/assistant_worker.py', 'rat/ui/omnibar.py', 'rat/ui/workbench_scene.py'}
assert set(source_mismatch) == set(source_changed) and not artifact_mismatch
assert final_integrity['reviewed_core_unchanged']
assert not incoming_changed and not incoming_added
assert not any(x['changes_during_r4'] for x in historical.values())
assert final_integrity['ledger_unchanged'] and branch == 'main'
assert all(x['matches'] for x in data_checks.values())
assert all(x['counts_match'] for x in crosschecks)
assert baseline['passed'] == 394 and probes['failed'] == 11 and probes['passed'] == 3
print(json.dumps({'source_unchanged': len(sources)-len(source_changed), 'source_drift': sorted(source_changed), 'reviewed_core_unchanged': final_integrity['reviewed_core_unchanged'], 'incoming_files_unchanged': len(incoming_before), 'submitted_sources_match_at_end': len(source_manifest)-len(source_mismatch), 'submitted_sources_match_at_receipt': initial['source_count']-len(initial['source_mismatches']), 'submitted_artifacts_match': len(artifact_manifest), 'pinned_data_checks': len(data_checks), 'historical_preexisting_drift': sum(len(x['preexisting_mismatches']) for x in historical.values()), 'historical_changes_during_r4': 0, 'git_status_unchanged': final_integrity['git_status_unchanged']}, indent=2))
