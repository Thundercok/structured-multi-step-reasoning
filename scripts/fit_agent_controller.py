"""Fit the experimental RAT stopping predictor from reviewed paired outcomes.

This is not experiments.research_study and does not change its Stage 0 gate.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from rat.engine.controller import AgentStoppingController, FEATURE_NAMES


def synthetic_rows():
    rows = []
    for split, count in [('train', 24), ('calibration', 12), ('test', 8)]:
        for i in range(count):
            useful = i % 2 == 0
            features = [0.0] * len(FEATURE_NAMES)
            features[0] = 2
            features[4] = float(not useful)
            features[10] = 1
            rows.append(dict(id=f'{split}-{i}', group_id=f'{split}-group-{i}', split=split,
                             features=features, reviewed=True, quality_gain=0.8 if useful else -0.5,
                             delta_tokens=120))
    return rows


def fit_bundle(rows, output: Path, *, lam=0.05, evidence='measured_development'):
    if output.exists():
        raise ValueError('Output must be a new directory')
    if evidence == 'measured_development' and any(r.get('evidence') != 'measured_paired_continuation' for r in rows if r.get('split') != 'test'):
        raise ValueError('Measured fitting requires measured paired continuation provenance')
    policy = AgentStoppingController(lam).fit(rows, evidence=evidence)
    dataset = json.dumps(rows, ensure_ascii=False, indent=2)
    output.mkdir(parents=True)
    (output / 'dataset.json').write_text(dataset + '\n')
    (output / 'policy.json').write_text(json.dumps(policy.to_dict(), indent=2) + '\n')
    manifest = {
        'evidence': evidence, 'stage0_changed': False, 'research_study_result': False,
        'dataset_sha256': hashlib.sha256((dataset + '\n').encode()).hexdigest(),
        'policy_sha256': hashlib.sha256((output / 'policy.json').read_bytes()).hexdigest(),
        'controller_source_sha256': hashlib.sha256(Path('rat/engine/controller.py').read_bytes()).hexdigest(),
        'fitting_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'model_calls': 0, 'publication_review_required': True,
        'evaluation': 'Not evaluated on held-out labels during fitting',
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--smoke', action='store_true')
    source.add_argument('--dataset', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--lam', type=float, default=0.05)
    args = parser.parse_args()
    rows = synthetic_rows() if args.smoke else json.loads(args.dataset.read_text())
    if not isinstance(rows, list):
        parser.error('Dataset must be an array of reviewed paired outcomes')
    manifest = fit_bundle(rows, args.output, lam=args.lam, evidence='synthetic_smoke' if args.smoke else 'measured_development')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
