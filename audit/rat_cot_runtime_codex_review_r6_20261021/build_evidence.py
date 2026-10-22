"""Read-only package, historical evidence, test and final-source reconciliation."""
from collections import Counter
from datetime import datetime, timezone
import hashlib, json, re, subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT/'audit/rat_cot_runtime_acceptance_20261020'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
read = lambda p: json.loads(p.read_text())
def write(name, data):
    (HERE/name).write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n')
def all_files(path):
    return {str(f.relative_to(path)): sha(f) for f in path.rglob('*') if f.is_file() and '__pycache__' not in f.parts and '.pytest_cache' not in f.parts and f.suffix!='.pyc'}
def junit(path):
    tree = ET.parse(path)
    cases = tree.findall('.//testcase')
    failures = [{'class': t.get('classname'), 'name': t.get('name')} for t in cases if t.find('failure') is not None]
    errors = [{'class': t.get('classname'), 'name': t.get('name')} for t in cases if t.find('error') is not None]
    skipped = sum(t.find('skipped') is not None for t in cases)
    return {'tests': len(cases), 'passed': len(cases)-len(failures)-len(errors)-skipped, 'failed': len(failures), 'errors': len(errors), 'skipped': skipped, 'failures': failures, 'error_cases': errors, 'class_counts': dict(Counter(t.get('classname') for t in cases)), 'xml_time_s': sum(float(t.get('time')) for t in tree.findall('.//testsuite'))}

initial = read(HERE/'integrity_initial.json')
before_sources = read(HERE/'source_start.json')['files']
after_sources = {name: sha(ROOT/name) for name in before_sources}
write('source_end.json', {'files': after_sources})
source_changes = {name: {'before': h, 'after': after_sources[name]} for name,h in before_sources.items() if after_sources[name]!=h}
incoming_now = all_files(SOURCE)
incoming_changes = {name: {'before': h, 'after': incoming_now.get(name)} for name,h in initial['incoming_files'].items() if incoming_now.get(name)!=h}
incoming_added = sorted(set(incoming_now)-set(initial['incoming_files']))
prior = {}
for name, record in initial['prior_reviews'].items():
    directory = ROOT/'audit'/name
    prior[name] = {'entries': record['entries'], 'mismatches_at_receipt': record['mismatches'], 'changes_during_r6': {f: {'before': h, 'after': sha(directory/f)} for f,h in record['current_files'].items() if sha(directory/f)!=h}, 'manifest_unchanged': sha(directory/'artifact_manifest.json')==record['manifest_sha256']}
submitted_sources = read(SOURCE/'source_end.json')['files']
submitted_artifacts = read(SOURCE/'artifact_manifest.json')
source_mismatches = {name: {'expected': h, 'actual': sha(ROOT/name)} for name,h in submitted_sources.items() if sha(ROOT/name)!=h}
artifact_mismatches = {name: {'expected': h, 'actual': sha(SOURCE/name)} for name,h in submitted_artifacts.items() if sha(SOURCE/name)!=h}
branch = subprocess.check_output(['git','branch','--show-current'], cwd=ROOT, text=True).strip()
status = subprocess.check_output(['git','status','--short'], cwd=ROOT, text=True)
(HERE/'git_status_final.txt').write_text(status)
integrity = {'source_snapshot_count': len(before_sources), 'source_changes_during_r6': source_changes, 'submitted_source_matches': len(submitted_sources)-len(source_mismatches), 'submitted_source_count': len(submitted_sources), 'source_mismatches': source_mismatches, 'submitted_artifact_matches': len(submitted_artifacts)-len(artifact_mismatches), 'submitted_artifact_count': len(submitted_artifacts), 'artifact_mismatches': artifact_mismatches, 'incoming_files_compared': len(initial['incoming_files']), 'incoming_changes': incoming_changes, 'incoming_added': incoming_added, 'prior_reviews': prior, 'ledger_sha256': sha(SOURCE/'calls.jsonl'), 'ledger_unchanged': sha(SOURCE/'calls.jsonl')==initial['ledger_sha256'], 'branch': branch, 'git_status_unchanged': status==(HERE/'git_status_initial.txt').read_text(), 'reviewer_production_edits': 0, 'reviewer_historical_edits': 0}
write('integrity_final.json', integrity)

packet = ROOT/'audit/cot_restart_fresh_data_review_20261016'
manifest = read(packet/'manifest.json')
refs = dict(manifest['inputs_sha256'])
refs.update({str((packet/name).relative_to(ROOT)): h for name,h in manifest['artifact_sha256'].items()})
checks = {name: {'expected': h, 'actual': sha(ROOT/name), 'matches': sha(ROOT/name)==h} for name,h in refs.items()}
write('data_integrity.json', {'checks': checks, 'passed': sum(x['matches'] for x in checks.values()), 'total': len(checks), 'structural_review': 'Inherited only for byte-identical pinned inputs from r1 data_integrity.json.', 'human_review': 'pending', 'held_out_queries_or_gold_emitted': False})

raw_checks = []
all_submitted_keys = []
for command in read(SOURCE/'commands.json'):
    xml = SOURCE/command['junit_xml']
    counts = junit(xml)
    all_submitted_keys.extend((t.get('classname'),t.get('name')) for t in ET.parse(xml).findall('.//testcase'))
    summaries = re.findall(r'(\d+) passed(?:, (\d+) skipped)? in ([\d.]+)s', (SOURCE/command['raw_log']).read_text())
    raw = summaries[-1] if summaries else None
    raw_checks.append({'name': command['name'], 'declared': command, 'junit': counts, 'raw_summary': raw, 'counts_match': raw is not None and int(raw[0])==command['passed']==counts['passed'] and counts['tests']==command['total_tests'] and counts['failed']==command['failed'] and counts['errors']==0, 'stdout_time_matches_declared': raw is not None and float(raw[2])==command['duration_s']})
old_regression = ROOT/'audit/rat_cot_runtime_codex_review_r5_20261021/received_artifacts/regression.xml'
current_regression = SOURCE/'regression.xml'
incident = read(SOURCE/'r4_baseline_xml_incident.json')
observed_xml = ROOT/incident['file']
write('submitted_evidence_crosscheck.json', {
    'suites': raw_checks,
    'all_counts_match': all(x['counts_match'] for x in raw_checks),
    'all_stdout_durations_match_declared': all(x['stdout_time_matches_declared'] for x in raw_checks),
    'submitted_execution_count': len(all_submitted_keys), 'distinct_class_and_test_name_identities': len(set(all_submitted_keys)), 'repeated_executions': len(all_submitted_keys)-len(set(all_submitted_keys)),
    'reused_regression': {'current_sha256': sha(current_regression), 'r5_received_sha256': sha(old_regression), 'byte_identical': sha(current_regression)==sha(old_regression), 'timestamp': ET.parse(current_regression).find('.//testsuite').get('timestamp'), 'scope': 'This exact 372-test transcript was already received before the r5 repair. Do not associate it with a new source freeze without explicit historical labeling.'},
    'r4_incident': {'expected_original_sha256': incident['expected_sha256'], 'recorded_actual_sha256': incident['actual_sha256'], 'observed_actual_sha256': sha(observed_xml), 'recorded_actual_matches_file': incident['actual_sha256']==sha(observed_xml), 'recorded_loss_status': incident['status'], 'original_xml_recovered': False},
})

baseline = junit(HERE/'baseline.xml')
new = junit(HERE/'trace_and_calibrator.xml')
groups = baseline['class_counts']
base_summary = {k:v for k,v in baseline.items() if k!='class_counts'}
new_summary = {k:v for k,v in new.items() if k!='class_counts'}
write('commands.json', [
    {'command': 'python audit/rat_cot_runtime_codex_review_r6_20261021/run_baseline.py', 'exit_code': 1, 'raw_log': 'baseline.txt', 'junit_xml': 'baseline.xml', 'result': base_summary, 'stdout_time_s': 44.88, 'host_permission': 'Offline Qt tests on host; no weights loaded or real inference.', 'subsets_already_in_baseline': {'mandatory_research': sum(groups[k] for k in ('tests.test_research_study','test_optimal_stopping','test_entry_predictor')), 'native_readiness': groups['tests.test_native_acceptance_readiness'], 'G1': groups['audit.rat_overnight_sweep_codex_review_r7_20261020.test_failed_request_reporting'], 'historical_runtime_probes': {'r2': 3, 'r3': 19, 'r4': 14, 'r5': 12}}},
    {'command': 'python -m pytest audit/rat_cot_runtime_codex_review_r6_20261021/test_trace_and_calibrator.py -q --junitxml=audit/rat_cot_runtime_codex_review_r6_20261021/trace_and_calibrator.xml', 'exit_code': 1, 'raw_log': 'trace_and_calibrator.txt', 'junit_xml': 'trace_and_calibrator.xml', 'result': new_summary, 'stdout_time_s': 2.78},
    {'command': 'python -m pytest test_qwen_mlx_backend_mocked.py test_reasoning_strategies.py tests/test_research_scoring.py -q', 'exit_code': 0, 'raw_log': 'backend_scoring.txt', 'passed': 68, 'skipped': 2, 'stdout_time_s': 3.87, 'skip_reason': 'Native MLX bfloat16 arrays unavailable in mocked environment.'},
    {'command': 'git apply --check repair_diff.patch; git apply repair_diff.patch, both against r5 source copies under r6/patch_replay_source only', 'exit_code': 0, 'record': 'patch_replay.json', 'matches_current_core_files': 3, 'production_modified': False, 'git_history_or_remote_modified': False},
    {'command': 'python audit/rat_cot_runtime_codex_review_r6_20261021/build_evidence.py', 'exit_code': 0, 'raw_log': 'final_checks.txt', 'initial_check': {'exit_code': 1, 'log': 'final_checks_timing_mismatch_detected.txt', 'reason': 'Detected three submitted command durations that disagree with their raw logs. Keep the mismatches as R10 evidence rather than assuming timing metadata is consistent.'}},
])
write('validation.json', {
    'review': 'r6', 'started_date_local': '2026-10-21', 'completed_date_local': '2026-10-22', 'timezone': 'Asia/Saigon', 'verdict': 'REQUEST_CHANGES',
    'open_findings': {'P1': ['R3','R5'], 'P2': ['R10']}, 'closed_this_review': ['R2'],
    'R12': 'Resolved with historical XML loss recorded; incident actual-digest metadata correction is tracked under R10. Original XML remains unavailable.',
    'retained_closed_scoped': ['R1','R4','R6','R7','R8','R9','R11','G1'],
    'baseline': base_summary, 'new_probes': new_summary,
    'backend_strategy_scoring': {'passed': 68, 'skipped': 2},
    'submitted_claims': {'executions': 497, 'distinct_test_identities': 464, 'repeated_executions': 33, 'all_pass_on_current_checkout_established': False},
    'real_model_calls': 0, 'git_history_or_remote_mutations': 0,
    'research_status': {'human_data_review': 'pending', 'Stage_0': 'unchanged; not established as passed', 'native_interactive_acceptance': 'pending'},
    'costs': 'Scripted synthetic generated-token counts; no full inference costs measured.',
    'timings': 'Software test wall time, not measured online model latency.',
    'scope': 'Current broad failures are reported, not repaired. Tests may contain stale UI or AST assumptions. No new product-bug claims are inferred from those failures alone.',
    'legacy_fixture_note': 'The r2 scripted _chat failure must expose structured dispatch state in a versioned fixture; successful generations followed by a strategy error do not prove another request was started.',
})
assert not source_changes and not artifact_mismatches and not incoming_changes and not incoming_added
assert source_mismatches==initial['source_mismatches']
assert all(not x['changes_during_r6'] and x['manifest_unchanged'] for x in prior.values())
assert integrity['ledger_unchanged'] and branch=='main'
assert all(x['matches'] for x in checks.values())
assert all(x['counts_match'] for x in raw_checks)
assert baseline['passed']==408 and baseline['failed']==9 and baseline['errors']==3
assert new['passed']==3 and new['failed']==4 and new['errors']==0
assert len(all_submitted_keys)==497 and len(set(all_submitted_keys))==464
print(json.dumps({'source_snapshot_unchanged': len(before_sources), 'source_manifest_matches': f'{len(submitted_sources)-len(source_mismatches)}/{len(submitted_sources)}', 'artifact_manifest_matches': f'{len(submitted_artifacts)}/{len(submitted_artifacts)}', 'incoming_files_unchanged': len(initial['incoming_files']), 'historical_known_lost_xml': 1, 'historical_changes_during_r6': 0, 'pinned_data_checks': len(checks), 'git_status_unchanged': integrity['git_status_unchanged']}, indent=2))
