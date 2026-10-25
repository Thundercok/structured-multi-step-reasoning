"""Read-only diagnostics of historical SC candidate scoring/cost; no inference."""
import collections
import hashlib
import json
from pathlib import Path
from experiments.research_study import check_answer

trace = Path('audit/run11_sweep_trace.jsonl')
data = Path('data/gen02_tune.json')
items = {i['id']: i for i in json.loads(data.read_text())['items']}
rows = [json.loads(line) for line in trace.read_text().splitlines()]
rows = [r for r in rows if r.get('arm') == 'SC']
mismatches = []
for row in rows:
    item = items.get(row['id'])
    if item is None:
        continue
    for index, candidate in enumerate(row.get('sc_candidates') or [], 1):
        literal = str(candidate).strip() == str(row['gold']).strip()
        checked = check_answer(candidate, item)
        if literal != checked:
            mismatches.append({'id': row['id'], 'family': row['family'], 'candidate_index': index,
                               'candidate': candidate, 'gold': row['gold'],
                               'literal_match': literal, 'procedural_checker': checked})
report = {
    'evidence_kind': 'historical_exposed_development_diagnostic', 'model_calls': 0,
    'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
    'dataset_sha256': hashlib.sha256(data.read_bytes()).hexdigest(),
    'sc_rows': len(rows), 'independent_groups': len({r['group_id'] for r in rows}),
    'families': dict(collections.Counter(r['family'] for r in rows)),
    'candidate_counts': dict(collections.Counter(len(r.get('sc_candidates') or []) for r in rows)),
    'rows_missing_dataset_item': [r['id'] for r in rows if r['id'] not in items],
    'exact_string_vs_procedural_scoring_mismatches': mismatches,
    'mismatch_count': len(mismatches),
    'cost_semantics': 'per_candidate_imputed_as_max_1_floor_total_completion_div_candidate_count',
    'per_candidate_tokens_observed': False, 'prompt_tokens_included_in_study_cost': False,
    'online_latency_measured_by_replay': False, 'held_out': False, 'stage0_changed': False,
}
out = Path(__file__).parent / 'source_diagnostic.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2))
print({k:v for k,v in report.items() if k not in ('exact_string_vs_procedural_scoring_mismatches',)})
