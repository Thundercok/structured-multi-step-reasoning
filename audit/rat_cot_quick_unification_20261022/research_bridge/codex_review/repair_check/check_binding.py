"""Authored approved-metadata binding probe; never approves a real policy."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
from reasoning.bundle import create_synthetic_specimen_bundle, validate_policy_bundle
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import MetaReasonerEngine

OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    files = ("reasoning/bundle.py", "reasoning/runtime.py", "tests/test_online_reasoning.py")
    before = {p: digest(ROOT / p) for p in files}
    ns = runpy.run_path(str(ROOT / "tests/test_online_reasoning.py"))
    setup = ns["TestFeaturePreprocessingContractAndRouteParity"]._make_vector_collector_setup
    query, records, policy, predictor, backend_cls = setup(lambda x: 6.0 + x, 6.8, 20.0)
    bundle, _ = create_synthetic_specimen_bundle(hidden_size=2)
    artifact = OUT / "authored_reviewed_policy.json"
    artifact.write_text(json.dumps({
        "lambda": policy.lam, "tau": policy.tau, "mean_cost": policy.mean_cost,
        "entry_cost_models": [{"coef": m.coef_.tolist(), "intercept": float(m.intercept_)}
                              for m in predictor.cost],
        "entry_perf_models": [{"constant": m.value} for m in predictor.perf],
        "embedding_normalization": "l2_unit",
    }, indent=2) + "\n")
    bundle = replace(bundle,
        review_status="approved", is_production_approved=True,
        review_scope="authored validation fixture only, no actual review approval",
        stopping_thresholds=tuple(policy.tau), mean_costs=tuple(policy.mean_cost),
        source_hashes={str(ROOT / p): h for p, h in before.items()},
        artifact_hashes={str(artifact): digest(artifact)},
        embedding_normalization="l2_unit",
    )

    def run(candidate, **kwargs):
        backend = backend_cls()
        backend.model_id = candidate.model_id
        backend.model_snapshot = candidate.model_snapshot
        backend.prompt_profile = candidate.prompt_profile
        report = validate_policy_bundle(candidate, policy, backend)
        controller = OnlineReasoningController(backend, policy, bundle=candidate, **kwargs)
        result = MetaReasonerEngine(controller=controller).solve(query)
        return {"is_valid": report.is_valid, "is_approved_metadata": report.is_approved,
                "bundle_normalization": candidate.embedding_normalization,
                "artifact_normalization": "l2_unit",
                "effective_normalization": controller.embedding_normalization,
                "route": result.strategy_path, "backend_calls": backend.calls}

    cases = {}
    for name, candidate, kwargs in (
        ("positive_matching_unit", bundle, {}),
        ("explicit_override_to_raw", bundle, {"embedding_normalization": "none"}),
        ("metadata_disagrees_with_artifact", replace(bundle, embedding_normalization="none"), {}),
        ("missing_declaration_but_unit_artifact", replace(bundle, embedding_normalization=None), {}),
    ):
        try:
            cases[name] = run(candidate, **kwargs)
        except Exception as exc:
            cases[name] = {"rejected": True, "exception": type(exc).__name__, "reason": str(exc)}
    assert cases["positive_matching_unit"].get("route") == ["COT"]
    assert before == {p: digest(ROOT / p) for p in files}
    _, record, *_ = ns["make_synthetic_parity_setup"]()
    fixture = ns["AuthoredRecordBackend"](record)
    result = {
        "evidence": "synthetic software probe with authored approved-metadata fixture",
        "real_policy_approved": False, "real_model_calls": 0, "source_sha256": before,
        "script_sha256": digest(Path(__file__)), "sources_unchanged": True,
        "cases": cases,
        "gold_in_fixture": "gold" in fixture.record,
        "correctness_in_fixture": any("correct" in a for a in fixture.record["attempts"].values()),
    }
    (OUT / "binding_probe.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
