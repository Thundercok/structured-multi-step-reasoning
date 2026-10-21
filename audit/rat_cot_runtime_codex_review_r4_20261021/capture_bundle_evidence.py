"""Persist the exact approved-artifact fixtures used by the five r4 probes."""
import hashlib, importlib.util, json, sys
from dataclasses import asdict
from pathlib import Path
import pytest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('r4_remaining_contracts', HERE / 'test_remaining_contracts.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
actual_validate = probe.validate_policy_bundle
records = {}
for variant in ('malformed-json', 'missing-parameters', 'empty-cost-models', 'wrong-coefficient-shape', 'changed-performance-model'):
    dest = HERE / 'bundle_counterexamples' / variant
    dest.mkdir(parents=True, exist_ok=True)
    def capture(bundle, policy, backend):
        report = actual_validate(bundle, policy, backend)
        artifact = dest / 'fitted-policy.json'
        records[variant] = {
            'validation_report': asdict(report),
            'artifact_sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
            'declared_artifact_sha256': bundle.artifact_hashes[str(artifact)],
            'live_cost_coef': policy.entry_predictor.cost[0].coef_.tolist(),
            'live_performance_constant': policy.entry_predictor.perf[0].value,
        }
        return report
    probe.validate_policy_bundle = capture
    try:
        probe.test_approved_fitted_artifact_cannot_skip_parameter_validation(dest, variant)
    except pytest.fail.Exception:
        pass
    else:
        raise AssertionError(f'Current source no longer reproduces {variant}')
(HERE / 'bundle_parameter_cases.json').write_text(json.dumps(records, indent=2) + '\n')
print(json.dumps({k: v['validation_report'] for k, v in records.items()}, indent=2))
