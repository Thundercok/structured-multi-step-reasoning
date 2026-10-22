"""Authored approved-metadata fixtures exercise validation, not policy approval or quality."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from reasoning.bundle import BundleValidationError, create_synthetic_specimen_bundle, validate_policy_bundle
from reasoning.optimal_stopping import PlattCalibrator


def approved_fixture(tmp_path):
    bundle, policy = create_synthetic_specimen_bundle(hidden_size=2)
    policy.calibrators = [PlattCalibrator() for _ in policy.tau]
    for calibrator in policy.calibrators:
        calibrator.a, calibrator.b, calibrator.is_fitted = 0., -20., True
    artifact = tmp_path / 'fitted-policy.json'
    artifact.write_text(json.dumps({
        'lambda': policy.lam, 'tau': policy.tau, 'mean_cost': policy.mean_cost,
        'entry_cost_models': [{'coef': m.coef_.tolist(), 'intercept': float(m.intercept_)}
                              for m in policy.entry_predictor.cost],
        'entry_perf_models': [{'constant': m.value} for m in policy.entry_predictor.perf],
        'calibrators': [{'type': 'platt', 'a': c.a, 'b': c.b, 'is_fitted': c.is_fitted}
                        for c in policy.calibrators],
    }))
    source = Path(__file__).resolve()
    bundle = replace(bundle, review_status='approved', is_production_approved=True,
                     review_scope='authored validation fixture only', calibrator_type='platt',
                     calibrator_semantics='platt_probability',
                     source_hashes={str(source): hashlib.sha256(source.read_bytes()).hexdigest()},
                     artifact_hashes={str(artifact): hashlib.sha256(artifact.read_bytes()).hexdigest()})
    return bundle, policy, artifact


def test_reference_calibrated_policy_validates(tmp_path):
    bundle, policy, _ = approved_fixture(tmp_path)
    assert validate_policy_bundle(bundle, policy).is_valid


@pytest.mark.parametrize('mutation', ['a', 'b', 'fitted', 'count'])
def test_live_calibration_changes_cannot_reuse_approved_artifact(tmp_path, mutation):
    bundle, policy, _ = approved_fixture(tmp_path)
    assert validate_policy_bundle(bundle, policy).is_valid
    if mutation in ('a', 'b'):
        setattr(policy.calibrators[0], mutation, 20.)
    elif mutation == 'fitted':
        policy.calibrators[0].is_fitted = False
    else:
        policy.calibrators.pop()
    with pytest.raises(BundleValidationError, match='calibrator'):
        validate_policy_bundle(bundle, policy)


@pytest.mark.parametrize('mutation', ['type', 'fitted', 'count', 'missing', 'isotonic'])
def test_unsupported_or_incomplete_calibration_artifacts_fail_closed(tmp_path, mutation):
    bundle, policy, artifact = approved_fixture(tmp_path)
    data = json.loads(artifact.read_text())
    if mutation == 'type':
        data['calibrators'][0]['type'] = 'isotonic'
    elif mutation == 'fitted':
        del data['calibrators'][0]['is_fitted']
    elif mutation == 'count':
        data['calibrators'].pop()
    elif mutation == 'missing':
        del data['calibrators']
    else:
        bundle = replace(bundle, calibrator_type='isotonic')
    artifact.write_text(json.dumps(data))
    bundle = replace(bundle, artifact_hashes={str(artifact): hashlib.sha256(artifact.read_bytes()).hexdigest()})
    with pytest.raises(BundleValidationError, match='calibrat'):
        validate_policy_bundle(bundle, policy)
