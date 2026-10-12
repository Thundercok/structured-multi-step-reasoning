"""Offline held-out evaluation of a RAT controller on reviewed paired outcomes.

One-step utility replay is not online agent task completion or measured latency.
"""
import argparse
import hashlib
import json
from pathlib import Path
from rat.engine.controller import AgentStoppingController, validate_pair_cost


def evaluate(controller, rows):
    controller.validate_rows(rows)
    fitted_rows = [r for split in ('train', 'calibration') for r in rows if r['split'] == split]
    development_hash = hashlib.sha256(json.dumps(fitted_rows, sort_keys=True).encode()).hexdigest()
    if development_hash != controller.metadata.get('development_sha256'):
        raise ValueError('Development outcomes do not match the fitted artifact')
    test = [r for r in rows if r['split'] == 'test']
    if not test:
        raise ValueError('No held-out outcomes')
    fitted = set(controller.metadata.get('fitted_groups', []))
    results = []
    for row in test:
        if row['group_id'] in fitted or row.get('reviewed') is not True:
            raise ValueError('Held-out outcome is exposed or not reviewed')
        gain, cost = row['quality_gain'], row['delta_tokens']
        if not isinstance(gain, (float, int)) or isinstance(gain, bool) or not -1 <= gain <= 1 or not isinstance(cost, int) or isinstance(cost, bool):
            raise ValueError('Invalid paired outcome')
        if controller.metadata['evidence'] == 'measured_development' and row.get('evidence') != 'measured_paired_continuation':
            raise ValueError('Held-out outcomes need measured paired continuation provenance')
        if row.get('evidence') == 'measured_paired_continuation':
            validate_pair_cost(row)
        score = controller.predict(row['features'])
        continued = score > controller.threshold
        utility = gain - controller.cost_penalty_lambda * cost / 1000
        results.append({'id': row['id'], 'group_id': row['group_id'], 'continued': continued,
                        'selected_delta_utility': utility if continued else 0,
                        'always_continue_delta_utility': utility,
                        'delta_tokens': cost if continued else 0})
    return {'evidence': controller.metadata['evidence'], 'scope': 'paired_one_step_replay',
            'online_latency_measured': False, 'publication_review_required': True,
            'results': results, 'mean_selected_delta_utility': sum(r['selected_delta_utility'] for r in results) / len(results)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--allow-synthetic', action='store_true')
    args = p.parse_args()
    if args.output.exists():
        p.error('Output already exists')
    manifest = json.loads((args.bundle / 'manifest.json').read_text())
    for name, key in [('dataset.json', 'dataset_sha256'), ('policy.json', 'policy_sha256')]:
        if hashlib.sha256((args.bundle / name).read_bytes()).hexdigest() != manifest.get(key):
            p.error('Bundle integrity check failed: ' + name)
    controller = AgentStoppingController.from_dict(json.loads((args.bundle / 'policy.json').read_text()), allow_synthetic=args.allow_synthetic)
    rows = json.loads((args.bundle / 'dataset.json').read_text())
    report = evaluate(controller, rows)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))


if __name__ == '__main__':
    main()
