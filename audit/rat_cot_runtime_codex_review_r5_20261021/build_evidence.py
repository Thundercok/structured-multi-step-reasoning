"""Read-only reconciliation of the received package and this review's executions."""
from collections import Counter
from datetime import datetime, timezone
import hashlib, json, re, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'audit/rat_cot_runtime_acceptance_20261020'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
read = lambda p: json.loads(p.read_text())
def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
def files(path):
    return {str(p.relative_to(path)): sha(p) for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p.suffix != '.pyc'}
def junit(name):
    tree = ET.parse(name)
    cases = tree.findall('.//testcase')
    failures = [{'class': t.attrib.get('classname'), 'name': t.attrib.get('name')} for t in cases if t.find('failure') is not None or t.find('error') is not None]
    skipped = sum(t.find('skipped') is not None for t in cases)
    return {'total': len(cases), 'passed': len(cases)-len(failures)-skipped, 'failed': len(failures), 'skipped': skipped, 'failures': failures, 'class_counts': dict(Counter(t.attrib.get('classname') for t in cases)), 'xml_time_s': sum(float(t.attrib['time']) for t in tree.findall('.//testsuite'))}

initial = read(HERE / 'integrity_initial.json')
start_sources = read(HERE / 'source_start.json')['files']
end_sources = {name: sha(ROOT/name) for name in start_sources}
write('source_end.json', {'files': end_sources})
source_changed = {name: {'before': h, 'after': end_sources[name]} for name,h in start_sources.items() if end_sources[name] != h}
incoming_now = files(SOURCE)
incoming_changed = {name: {'before': h, 'after': incoming_now.get(name)} for name,h in initial['incoming_files'].items() if incoming_now.get(name) != h}
incoming_added = sorted(set(incoming_now)-set(initial['incoming_files']))
previous = {}
for name, data in initial['prior_reviews'].items():
    directory = ROOT/'audit'/name
    changed = {f: {'before': h, 'after': sha(directory/f)} for f,h in data['current_files'].items() if sha(directory/f) != h}
    previous[name] = {'manifest_entries': data['entries'], 'mismatches_at_receipt': data['mismatches'], 'changes_during_r5': changed, 'manifest_unchanged': sha(directory/'artifact_manifest.json') == data['manifest_sha256']}
submitted_sources = read(SOURCE/'source_end.json')['files']
submitted_artifacts = read(SOURCE/'artifact_manifest.json')
source_mismatch = {name: {'expected': h, 'actual': sha(ROOT/name)} for name,h in submitted_sources.items() if sha(ROOT/name) != h}
artifact_mismatch = {name: {'expected': h, 'actual': sha(SOURCE/name)} for name,h in submitted_artifacts.items() if sha(SOURCE/name) != h}
branch = subprocess.check_output(['git','branch','--show-current'], cwd=ROOT, text=True).strip()
status = subprocess.check_output(['git','status','--short'], cwd=ROOT, text=True)
(HERE/'git_status_final.txt').write_text(status)
integrity = {
    'snapshot_sources': len(start_sources), 'source_changes_during_r5': source_changed,
    'submitted_source_matches_at_receipt': len(submitted_sources)-len(initial['source_mismatches']),
    'submitted_source_matches_at_end': len(submitted_sources)-len(source_mismatch), 'submitted_source_count': len(submitted_sources),
    'submitted_source_mismatches_at_end': source_mismatch,
    'submitted_artifact_matches': len(submitted_artifacts)-len(artifact_mismatch), 'submitted_artifact_count': len(submitted_artifacts), 'submitted_artifact_mismatches': artifact_mismatch,
    'incoming_files_compared': len(initial['incoming_files']), 'incoming_changed': incoming_changed, 'incoming_added': incoming_added,
    'prior_reviews': previous, 'ledger_sha256': sha(SOURCE/'calls.jsonl'), 'ledger_unchanged': sha(SOURCE/'calls.jsonl') == initial['ledger_sha256'],
    'branch': branch, 'git_status_unchanged': status == (HERE/'git_status_initial.txt').read_text(),
    'reviewer_production_edits': 0, 'reviewer_historical_edits': 0,
}
write('integrity_final.json', integrity)

packet = ROOT/'audit/cot_restart_fresh_data_review_20261016'
manifest = read(packet/'manifest.json')
data_refs = dict(manifest['inputs_sha256'])
data_refs.update({str((packet/name).relative_to(ROOT)): h for name,h in manifest['artifact_sha256'].items()})
data_checks = {name: {'expected': h, 'actual': sha(ROOT/name), 'matches': sha(ROOT/name) == h} for name,h in data_refs.items()}
write('data_integrity.json', {'checks': data_checks, 'passed': sum(x['matches'] for x in data_checks.values()), 'total': len(data_checks), 'structural_review': 'Inherited only for pinned byte-identical inputs from r1 data_integrity.json.', 'human_review': 'pending', 'held_out_queries_or_gold_emitted': False})

submitted_raw = []
for command in read(SOURCE/'commands.json'):
    counts = junit(SOURCE/command['junit_xml'])
    matches = re.findall(r'(\d+) passed(?:, (\d+) skipped)? in ([\d.]+)s', (SOURCE/command['raw_log']).read_text())
    raw = matches[-1] if matches else None
    submitted_raw.append({'name': command['name'], 'declared': command, 'junit': counts, 'raw_summary': raw, 'counts_match': raw is not None and int(raw[0]) == command['passed'] == counts['passed'] and command['total_tests'] == counts['total'] and counts['failed'] == command['failed'], 'raw_duration_matches_declared': raw is not None and float(raw[2]) == command['duration_s']})
write('submitted_raw_crosscheck.json', {'suites': submitted_raw, 'all_counts_match': all(x['counts_match'] for x in submitted_raw), 'all_raw_durations_match_declared': all(x['raw_duration_matches_declared'] for x in submitted_raw), 'repair_diff_files': re.findall(r'^diff --git a/(.*?) b/', (SOURCE/'repair_diff.patch').read_text(), re.MULTILINE), 'scope': 'Consistency of the received package only; current source mismatch and reviewer test results are recorded separately.'})

baseline = junit(HERE/'baseline.xml')
new = junit(HERE/'binding_and_dispatch.xml')
groups = baseline['class_counts']
baseline_summary = {k:v for k,v in baseline.items() if k != 'class_counts'}
new_summary = {k:v for k,v in new.items() if k != 'class_counts'}
write('commands.json', [
    {'command': 'python audit/rat_cot_runtime_codex_review_r5_20261021/run_baseline.py', 'exit_code': 1, 'raw_log': 'baseline.txt', 'junit_xml': 'baseline.xml', 'result': baseline_summary, 'duration_stdout_s': 48.32, 'host_permission': 'Offline Qt tests on host; no weights loaded or real inference.', 'subsets_already_in_baseline': {'mandatory_research': sum(groups[k] for k in ('tests.test_research_study','test_optimal_stopping','test_entry_predictor')), 'r2_qwen_replay': groups['audit.rat_cot_runtime_codex_review_r2_20261020.test_qwen_boundary_replay'], 'r3_contracts': groups['audit.rat_cot_runtime_codex_review_r3_20261020.test_boundary_contracts'], 'r4_contracts': groups['audit.rat_cot_runtime_codex_review_r4_20261021.test_remaining_contracts'], 'G1': groups['audit.rat_overnight_sweep_codex_review_r7_20261020.test_failed_request_reporting']}, 'initial_attempt': {'exit_code': 1, 'raw_log': 'baseline_initial.txt', 'junit_xml': 'baseline_initial.xml', 'passed': 400, 'failed': 8, 'reviewer_setup_failures': 5, 'reason': 'Copied legacy_fake_calls.jsonl was missing at redirected HERE. Runner fixed; historical directories unchanged.'}},
    {'command': 'python -m pytest audit/rat_cot_runtime_codex_review_r5_20261021/test_binding_and_dispatch.py -q --junitxml=audit/rat_cot_runtime_codex_review_r5_20261021/binding_and_dispatch.xml', 'exit_code': 1, 'raw_log': 'binding_and_dispatch.txt', 'junit_xml': 'binding_and_dispatch.xml', 'result': new_summary, 'duration_stdout_s': 3.36, 'initial_attempt': {'raw_log': 'binding_and_dispatch_initial.txt', 'junit_xml': 'binding_and_dispatch_initial.xml', 'passed': 3, 'failed': 9, 'duration_stdout_s': 5.22, 'followup_change': 'Accept safe pre-dispatch rejection of unsupported ReAct settings; capture scores at nonzero authored fixture features. Same 9 failures remain.'}},
    {'command': 'python -m pytest test_qwen_mlx_backend_mocked.py test_reasoning_strategies.py tests/test_research_scoring.py -q', 'exit_code': 0, 'raw_log': 'backend_scoring.txt', 'passed': 68, 'skipped': 2, 'duration_stdout_s': 7.11, 'skip_reason': 'Native MLX bfloat16 arrays unavailable in the mock environment.'},
    {'command': 'python audit/rat_cot_runtime_codex_review_r5_20261021/recover_r4_evidence.py', 'exit_code': 0, 'raw_log': 'recovery.txt', 'record': 'recovery.json', 'verified_original_copies': 2, 'baseline_xml_verified_backup_found': False},
    {'command': 'python audit/rat_cot_runtime_codex_review_r5_20261021/build_evidence.py', 'exit_code': 0, 'raw_log': 'final_checks.txt'},
])
write('validation.json', {
    'review': 'r5', 'date_local': '2026-10-21', 'timezone': 'Asia/Saigon', 'verdict': 'REQUEST_CHANGES',
    'open_findings': {'P1': ['R2','R3','R5'], 'P2': ['R12']},
    'repairs_confirmed': ['SC/ToT configured loops and r4 budgets', 'r4 partial-token and cancellation accounting cases', 'r4 five artifact mutation rejections', 'eight original r2/r3 counterexamples restored'],
    'retained_closed_scoped': ['R1','R4','R6','R7','R8','R9','R10','R11','G1'],
    'baseline': baseline_summary, 'new_probes': new_summary,
    'backend_strategy_scoring': {'passed': 68, 'skipped': 2},
    'historical_drift_at_receipt': 3, 'historical_changes_during_r5': 0, 'verified_original_copies_recovered_to_r5': 2,
    'baseline_r4_xml_recovery': 'No matching backup found among existing audit XML files. Timings not reconstructed.',
    'real_model_calls': 0, 'git_mutations': 0,
    'research_status': {'human_data_review': 'pending', 'Stage_0': 'unchanged; not established as passed', 'native_interactive_acceptance': 'pending'},
    'costs': 'Scripted synthetic generated-token counts; no full inference costs measured.',
    'timings': 'Software test wall time, not measured online model latency.',
    'UI_scope': 'Five UI/test source files differ from submission at receipt. Three current UI assertions fail. No product-bug conclusion or repair of those parallel changes is made here.',
    'legacy_probe_scope': 'No requirement to preserve contradictory unsupported-hard-cap expectations. The r2 fake _chat failure seam also lacks structured dispatch evidence; version that fixture instead of retaining production exception-message heuristics.',
})
assert not source_changed and not artifact_mismatch and not incoming_changed and not incoming_added
assert source_mismatch == initial['source_mismatches']
assert all(not x['changes_during_r5'] and x['manifest_unchanged'] for x in previous.values())
assert integrity['ledger_unchanged'] and branch == 'main'
assert all(x['matches'] for x in data_checks.values())
assert all(x['counts_match'] and x['raw_duration_matches_declared'] for x in submitted_raw)
assert baseline['passed'] == 405 and baseline['failed'] == 3 and new['passed'] == 3 and new['failed'] == 9
print(json.dumps({'source_snapshot_unchanged': len(start_sources), 'submitted_sources_match': f'{len(submitted_sources)-len(source_mismatch)}/{len(submitted_sources)}', 'submitted_artifacts_match': f'{len(submitted_artifacts)}/{len(submitted_artifacts)}', 'incoming_files_unchanged': len(initial['incoming_files']), 'historical_preexisting_drift': sum(len(x['mismatches_at_receipt']) for x in previous.values()), 'historical_changes_during_r5': 0, 'pinned_data_checks': len(data_checks), 'git_status_unchanged': integrity['git_status_unchanged']}, indent=2))
