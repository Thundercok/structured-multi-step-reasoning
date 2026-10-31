"""Synthetic fitted-policy integration; not model or calibration evidence."""
from pathlib import Path
import numpy as np
import pytest

from reasoning.entry_predictor import EntryChoice, EntryPredictor, EntryTrainingData
from reasoning.optimal_stopping import CalibrationData, IsotonicCalibrator, OptimalStoppingPolicy
from reasoning.reasoning_env import ReasoningAction as A, complexity_features
from reasoning.runtime import OnlineReasoningController
from rat.engine.meta_reasoner import MetaReasonerEngine
from experiments.research_study import collect_records, evaluate_records
from reasoning.bundle import PolicyBundle, validate_policy_bundle, BundleValidationError, create_synthetic_specimen_bundle


class Backend:
    hidden_size = 2

    def __init__(self, confidence=.1):
        self.confidence = confidence
        self.calls = []

    def embed(self, query):
        return np.zeros(self.hidden_size)

    def run(self, strategy, query):
        self.calls.append((strategy, query))
        return f"observed-{strategy.name}", self.confidence, 10 + int(strategy)


def fitted(choice=EntryChoice.LADDER):
    accuracy = np.zeros((8, 3))
    accuracy[:, choice] = 1
    predictor = EntryPredictor(lam=.02).fit(EntryTrainingData(
        embed=np.zeros((8, 2)), complexity=np.zeros((8, 3)),
        accuracy=accuracy, cost=np.full((8, 3), .1),
    ))
    return OptimalStoppingPolicy(.02, entry_predictor=predictor).fit(CalibrationData(
        conf=np.array([[.2] * 8, [.6] * 8, [.9] * 8]),
        correct=np.array([[0] * 8, [0] * 8, [1] * 8]),
        cost=np.full((3, 8), .1),
    ))


@pytest.mark.parametrize('choice,confidence,path', [
    (EntryChoice.LADDER, .1, [A.COT, A.SELF_CONSISTENCY, A.TOT]),
    (EntryChoice.LADDER, .95, [A.COT]),
    (EntryChoice.REACT, .1, [A.REACT]),
    (EntryChoice.PAL, .1, [A.PAL]),
])
def test_rat_executes_fitted_route_and_stopping_without_gold_or_legacy_branches(choice, confidence, path):
    backend = Backend(confidence)
    policy = fitted(choice)
    engine = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, policy, policy_source='synthetic-unit-fixture',
    ))
    # A legacy intent branch would use canned tuition numbers for this query.
    query = 'Tính học phí 123'
    result = engine.solve(query)
    assert [action for action, _ in backend.calls] == path
    assert all(q == query for _, q in backend.calls)
    assert result.answer == f'observed-{path[-1].name}'
    assert result.strategy_path == [action.name for action in path]
    assert result.tokens == sum(10 + int(action) for action in path)
    assert result.escalated == (len(path) > 1)
    assert result.execution_mode == 'online_policy'
    assert result.policy_source == 'synthetic-unit-fixture'
    assert result.verification_status == 'unverified'
    assert result.confidence_kind == 'backend_raw'
    replay = policy.run_episode(Backend(confidence), query, result.answer, lambda a, b: a == b)
    assert replay['path'] == result.strategy_path
    assert replay['cost'] == pytest.approx(result.tokens / 1000)
    engine.solve(query)
    assert len(backend.calls) == 2 * len(path)  # no stale cached costs/path


def test_stopping_applies_fitted_confidence_calibration():
    policy = fitted()
    calibrator = IsotonicCalibrator().fit(np.array([.01, .05, .5, .9]), np.array([0, 1, 1, 1]))
    assert calibrator.is_fitted
    assert calibrator.predict(.1) == pytest.approx(calibrator.predict(np.array([.1]))[0])
    policy.calibrators = [calibrator] * 3
    backend = Backend(.1)
    result = OnlineReasoningController(backend, policy, policy_source='synthetic').solve('query')
    assert len(result.observations) == 1  # raw .1 escalates; calibrated 1 stops
    assert result.observations[0].confidence == .1


def test_unfitted_or_inconsistent_policy_cannot_start_backend():
    backend = Backend()
    with pytest.raises(ValueError, match='fitted entry predictor'):
        OnlineReasoningController(backend, OptimalStoppingPolicy(.02), policy_source='synthetic')
    policy = fitted()
    policy.entry_predictor.lam = .5
    with pytest.raises(ValueError, match='same lambda'):
        OnlineReasoningController(backend, policy, policy_source='synthetic')
    assert not backend.calls


@pytest.mark.parametrize('confidence', [float('nan'), 1.1, True])
def test_invalid_observation_fails_without_escalation_or_canned_answer(confidence):
    backend = Backend(confidence)
    engine = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, fitted(), policy_source='synthetic',
    ))
    with pytest.raises(ValueError, match='confidence'):
        engine.solve('học phí 12')
    assert len(backend.calls) == 1


def test_backend_failure_is_not_replaced_by_a_legacy_response(monkeypatch):
    backend = Backend()
    def fail(*args):
        raise RuntimeError('backend unavailable')
    monkeypatch.setattr(backend, 'run', fail)
    engine = MetaReasonerEngine(controller=OnlineReasoningController(
        backend, fitted(), policy_source='synthetic',
    ))
    with pytest.raises(RuntimeError, match='backend unavailable'):
        engine.solve('học phí 12')


@pytest.mark.parametrize('tokens', [-1, True, 1.5])
def test_invalid_cost_does_not_become_a_reported_token_count(monkeypatch, tokens):
    backend = Backend()
    monkeypatch.setattr(backend, 'run', lambda *args: ('answer', .5, tokens))
    controller = OnlineReasoningController(backend, fitted(), policy_source='synthetic')
    with pytest.raises(ValueError, match='generated-token count'):
        controller.solve('query')


def test_invalid_embedding_prevents_strategy_calls(monkeypatch):
    backend = Backend()
    monkeypatch.setattr(backend, 'embed', lambda query: np.array([np.nan, 0]))
    controller = OnlineReasoningController(backend, fitted(), policy_source='synthetic')
    with pytest.raises(ValueError, match='embedding'):
        controller.solve('query')
    assert not backend.calls


class AuthoredRecordBackend:
    hidden_size = 2

    def __init__(self, record):
        # Whitelist ONLY allowable execution outputs; gold and correctness flags are strictly filtered out
        self.record = {
            "embedding": list(record.get("embedding", [])),
            "attempts": {
                strat_name: {
                    "answer": str(attempt["answer"]),
                    "confidence": float(attempt["confidence"]),
                    "tokens": int(attempt["tokens"]),
                }
                for strat_name, attempt in record.get("attempts", {}).items()
            },
        }
        self.calls = []

    def embed(self, query):
        return np.asarray(self.record["embedding"], dtype=float)

    def run(self, strategy, query, **kwargs):
        self.calls.append((strategy, query))
        attempt = self.record["attempts"][strategy.name]
        return attempt["answer"], float(attempt["confidence"]), int(attempt["tokens"])


def make_synthetic_parity_setup(
    choice=EntryChoice.LADDER,
    cot_conf=0.8,
    sc_conf=0.9,
    tot_conf=0.9,
    react_conf=0.85,
    pal_conf=0.92,
):
    query = "Tính học phí sinh viên khóa 2026"
    complexity = complexity_features(query, version=1).tolist()
    embedding = [0.1, 0.2]

    accuracy = np.zeros((8, 3))
    accuracy[:, choice] = 1.0
    full_predictor = EntryPredictor(lam=0.02).fit(EntryTrainingData(
        embed=np.full((8, 2), 0.1),
        complexity=np.full((8, 3), 0.5),
        accuracy=accuracy,
        cost=np.full((8, 3), 0.1),
    ))

    policy = OptimalStoppingPolicy(0.02, entry_predictor=full_predictor).fit(CalibrationData(
        conf=np.array([[0.2] * 8, [0.6] * 8, [0.9] * 8]),
        correct=np.array([[0] * 8, [0] * 8, [1] * 8]),
        cost=np.full((3, 8), 0.1),
    ))

    one_shot = EntryPredictor(0.02).fit(EntryTrainingData(
        embed=np.full((8, 2), 0.1),
        complexity=np.full((8, 3), 0.5),
        accuracy=accuracy,
        cost=np.full((8, 3), 0.1),
    ))

    record = {
        "id": "item-parity-01",
        "group_id": "group-01",
        "split": "test",
        "query": query,
        "embedding": embedding,
        "complexity": complexity,
        "embedding_ms": 1.5,
        "gold": "ans-correct",
        "attempts": {
            "COT": {"answer": "ans-cot", "confidence": cot_conf, "tokens": 15, "correct": True, "strategy_ms": 50.0},
            "SELF_CONSISTENCY": {"answer": "ans-sc", "confidence": sc_conf, "tokens": 45, "correct": True, "strategy_ms": 120.0},
            "TOT": {"answer": "ans-tot", "confidence": tot_conf, "tokens": 90, "correct": True, "strategy_ms": 250.0},
            "REACT": {"answer": "ans-react", "confidence": react_conf, "tokens": 60, "correct": True, "strategy_ms": 180.0},
            "PAL": {"answer": "ans-pal", "confidence": pal_conf, "tokens": 40, "correct": True, "strategy_ms": 110.0},
        },
    }
    return query, record, policy, full_predictor, one_shot


class TestHarnessEvaluateRecordsDirectParity:
    """Direct parity between evaluate_records in experiments.research_study and MetaReasonerEngine."""

    def test_ladder_early_stopping_parity(self):
        """When COT confidence is high, both harness full_policy and RAT engine stop at COT."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.LADDER, cot_conf=0.95
        )
        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert eval_full["path"] == ["COT"]
        assert result.strategy_path == eval_full["path"]
        assert result.answer == eval_full["answer"]
        assert result.tokens == eval_full["tokens"]
        assert result.escalated == eval_full["escalated"]
        assert [c[0].name for c in backend.calls] == eval_full["path"]

    def test_ladder_intermediate_escalation_parity(self):
        """When COT confidence is low and SC confidence is high, both escalate to SC and stop."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.LADDER, cot_conf=0.1, sc_conf=0.95
        )
        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert eval_full["path"] == ["COT", "SELF_CONSISTENCY"]
        assert result.strategy_path == eval_full["path"]
        assert result.answer == eval_full["answer"]
        assert result.tokens == eval_full["tokens"]
        assert result.escalated == eval_full["escalated"]
        assert [c[0].name for c in backend.calls] == eval_full["path"]

    def test_ladder_terminal_escalation_parity(self):
        """When both COT and SC confidence are low, both escalate all the way to TOT."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.LADDER, cot_conf=0.1, sc_conf=0.1, tot_conf=0.8
        )
        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert eval_full["path"] == ["COT", "SELF_CONSISTENCY", "TOT"]
        assert result.strategy_path == eval_full["path"]
        assert result.answer == eval_full["answer"]
        assert result.tokens == eval_full["tokens"]
        assert result.escalated == eval_full["escalated"]
        assert [c[0].name for c in backend.calls] == eval_full["path"]

    def test_entry_router_react_parity(self):
        """When predictor routes to REACT, both harness full_policy and RAT engine execute REACT only."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.REACT
        )
        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert eval_full["path"] == ["REACT"]
        assert result.strategy_path == eval_full["path"]
        assert result.answer == eval_full["answer"]
        assert result.tokens == eval_full["tokens"]
        assert result.escalated == eval_full["escalated"]
        assert [c[0].name for c in backend.calls] == eval_full["path"]

    def test_entry_router_pal_parity(self):
        """When predictor routes to PAL, both harness full_policy and RAT engine execute PAL only."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.PAL
        )
        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert eval_full["path"] == ["PAL"]
        assert result.strategy_path == eval_full["path"]
        assert result.answer == eval_full["answer"]
        assert result.tokens == eval_full["tokens"]
        assert result.escalated == eval_full["escalated"]
        assert [c[0].name for c in backend.calls] == eval_full["path"]

    def test_exact_threshold_boundary_stopping_parity(self):
        """Confidence exactly at threshold tau[0] must not escalate."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(choice=EntryChoice.LADDER)
        exact_tau0 = float(policy.tau[0])
        record["attempts"]["COT"]["confidence"] = exact_tau0

        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert eval_full["path"] == ["COT"]
        assert result.strategy_path == ["COT"]
        assert [c[0].name for c in backend.calls] == ["COT"]

    def test_isotonic_calibrator_parity(self):
        """Active isotonic calibrator mapping raw confidence into stopping decision."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.LADDER, cot_conf=0.1
        )
        calibrator = IsotonicCalibrator().fit(
            np.array([0.05, 0.1, 0.5, 0.9]),
            np.array([0.0, 1.0, 1.0, 1.0])
        )
        policy.calibrators = [calibrator] * 3

        eval_rows = evaluate_records([record], policy, full, one_shot)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")

        backend = AuthoredRecordBackend(record)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        # Raw conf is 0.1, which calibrator maps to 1.0 > tau[0], stopping at COT
        assert eval_full["path"] == ["COT"]
        assert result.strategy_path == ["COT"]
        assert [c[0].name for c in backend.calls] == ["COT"]

    def test_gold_label_independence(self):
        """Altering evaluator gold modifies correctness in evaluator results but zero changes in RAT routing or path."""
        query, record, policy, full, one_shot = make_synthetic_parity_setup(
            choice=EntryChoice.LADDER, cot_conf=0.95
        )
        record["attempts"]["COT"]["correct"] = True
        eval_orig = next(r for r in evaluate_records([record], policy, full, one_shot) if r["method"] == "full_policy")

        # Mutate gold/correctness
        record_mutated = dict(record)
        record_mutated["attempts"] = dict(record["attempts"])
        record_mutated["attempts"]["COT"] = dict(record["attempts"]["COT"])
        record_mutated["attempts"]["COT"]["correct"] = False
        record_mutated["gold"] = "different-gold"
        eval_mutated = next(r for r in evaluate_records([record_mutated], policy, full, one_shot) if r["method"] == "full_policy")

        # Correctness flipped in evaluator
        assert eval_orig["correct"] is True
        assert eval_mutated["correct"] is False

        # In RAT engine, gold does not enter the backend or policy
        backend = AuthoredRecordBackend(record_mutated)
        engine = MetaReasonerEngine(controller=OnlineReasoningController(
            backend, policy, policy_source="synthetic-parity-test"
        ))
        result = engine.solve(query)

        assert result.strategy_path == eval_orig["path"]
        assert result.answer == eval_orig["answer"]
        assert result.tokens == eval_orig["tokens"]
        assert [c[0].name for c in backend.calls] == ["COT"]

    def test_fixture_label_isolation(self):
        """Labels (gold and correctness flags) must be strictly absent from the backend double."""
        _, record, *_ = make_synthetic_parity_setup()
        assert "gold" in record
        assert any("correct" in a for a in record["attempts"].values())

        backend = AuthoredRecordBackend(record)
        # Verify physical absence of labels in the double's state
        assert "gold" not in backend.record
        assert not hasattr(backend, "gold")
        assert not any("correct" in a for a in backend.record["attempts"].values())


class TestFeaturePreprocessingContractAndRouteParity:
    """Verifies feature preprocessing contract binding, route parity, and legacy compatibility."""

    @staticmethod
    def _make_vector_collector_setup(cot_cost_fn, react_cost_val, pal_cost_val):
        from io import StringIO

        query = "Authored synthetic routing question"

        class VectorBackend:
            hidden_size = 2

            def __init__(self):
                self.calls = []

            def embed(self, query):
                return np.array([3.0, 4.0])

            def run(self, strategy, query, **kwargs):
                self.calls.append(strategy.name)
                return str(int(strategy)), 0.95, 10

        item = dict(
            id="synthetic-normalization",
            group_id="authored-normalization",
            split="test",
            query=query,
            answer="0",
            answer_type="number",
        )
        records = collect_records(VectorBackend(), [item], 42, lambda seed: None, StringIO())
        x = np.linspace(-1.0, 1.0, 100)
        embeddings = np.column_stack((x, np.sqrt(np.maximum(0.0, 1 - x * x))))
        predictor = EntryPredictor(lam=0.02).fit(EntryTrainingData(
            embed=embeddings,
            complexity=np.tile(complexity_features(query), (len(x), 1)),
            accuracy=np.ones((len(x), 3)),
            cost=np.column_stack((cot_cost_fn(x), np.full(len(x), react_cost_val), np.full(len(x), pal_cost_val))),
        ))
        policy = OptimalStoppingPolicy(0.02, entry_predictor=predictor).fit(CalibrationData(
            conf=np.array([[0.2] * 8, [0.6] * 8, [0.9] * 8]),
            correct=np.array([[0] * 8, [0] * 8, [1] * 8]),
            cost=np.full((3, 8), 0.1),
        ))
        return query, records, policy, predictor, VectorBackend

    def test_real_collector_vector_sensitive_ladder_parity(self):
        """Scale-sensitive predictor routes to LADDER when L2 unit normalized.

        Reproduces the reviewer's counterexample:
        - Raw vector [3.0, 4.0] has norm 5.0.
        - Unit vector is [0.6, 0.8] (x = 0.6).
        - At x = 0.6, COT cost is 6 + 0.6 = 6.6 < REACT cost 6.8 -> chooses COT.
        - At unnormalized x = 3.0, COT cost is 6 + 3.0 = 9.0 > REACT cost 6.8 -> would choose REACT.
        With embedding_normalization='l2_unit' bound, harness and runtime route identically to COT.
        """
        query, records, policy, predictor, backend_cls = self._make_vector_collector_setup(
            cot_cost_fn=lambda x: 6.0 + x, react_cost_val=6.8, pal_cost_val=20.0
        )
        eval_rows = evaluate_records(records, policy, predictor, predictor)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")
        assert eval_full["path"] == ["COT"]

        # 1. Parity via explicit parameter
        backend1 = backend_cls()
        controller1 = OnlineReasoningController(
            backend1, policy, policy_source="research-profile-test",
            embedding_normalization="l2_unit",
        )
        result1 = MetaReasonerEngine(controller=controller1).solve(query)
        assert result1.strategy_path == eval_full["path"] == ["COT"]
        assert result1.tokens == eval_full["tokens"] == 10
        assert result1.answer == eval_full["answer"]

        # 2. Parity via bundle contract
        bundle = PolicyBundle(
            bundle_id="research-unit-specimen",
            review_status="synthetic_development_only",
            model_id="synthetic-mock-v1",
            model_snapshot="synthetic-20261020-mock",
            prompt_profile="aligned-direct-cot-v1",
            strategy_settings={"ladder": ["COT", "SELF_CONSISTENCY", "TOT"]},
            backend_protocol="LLMBackend.v1",
            embedding_dimension=2,
            feature_schema_version=1,
            predictor_kind="EntryPredictor",
            lambda_val=0.02,
            stopping_thresholds=tuple(float(t) for t in policy.tau),
            mean_costs=tuple(float(c) for c in policy.mean_cost),
            calibrator_type=None,
            calibrator_semantics="raw_confidence_uncalibrated",
            cost_metadata={"token_unit": "thousands", "scope": "generated_tokens_only"},
            budget_token_semantics="generated_tokens_only",
            execution_mode="online_policy",
            source_hashes={"test": "test"},
            artifact_hashes={"test": "test"},
            dataset_versions={"test": "test"},
            train_calibration_provenance={"test": True},
            split_separation_verified=True,
            review_scope="offline_synthetic_development_testing_only",
            compatibility_conditions={"min_hidden_size": 2, "max_ladder_depth": 3},
            is_production_approved=False,
            embedding_normalization="l2_unit",
        )
        backend2 = backend_cls()
        controller2 = OnlineReasoningController(
            backend2, policy, bundle=bundle, allow_synthetic_bundle=True,
        )
        assert controller2.embedding_normalization == "l2_unit"
        result2 = MetaReasonerEngine(controller=controller2).solve(query)
        assert result2.strategy_path == eval_full["path"] == ["COT"]

    def test_real_collector_vector_sensitive_react_parity(self):
        """Scale-sensitive predictor routes to REACT under both harness and runtime."""
        # At x = 0.6, REACT cost 5.0 is lower than COT cost (6 + 0.6 = 6.6)
        query, records, policy, predictor, backend_cls = self._make_vector_collector_setup(
            cot_cost_fn=lambda x: 6.0 + x, react_cost_val=5.0, pal_cost_val=20.0
        )
        eval_rows = evaluate_records(records, policy, predictor, predictor)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")
        assert eval_full["path"] == ["REACT"]

        backend = backend_cls()
        controller = OnlineReasoningController(
            backend, policy, policy_source="research-react-test",
            embedding_normalization="l2_unit",
        )
        result = MetaReasonerEngine(controller=controller).solve(query)
        assert result.strategy_path == eval_full["path"] == ["REACT"]
        assert result.tokens == eval_full["tokens"] == 10

    def test_real_collector_vector_sensitive_pal_parity(self):
        """Scale-sensitive predictor routes to PAL under both harness and runtime."""
        # At x = 0.6, PAL cost 4.0 is lowest
        query, records, policy, predictor, backend_cls = self._make_vector_collector_setup(
            cot_cost_fn=lambda x: 6.0 + x, react_cost_val=8.0, pal_cost_val=4.0
        )
        eval_rows = evaluate_records(records, policy, predictor, predictor)
        eval_full = next(r for r in eval_rows if r["method"] == "full_policy")
        assert eval_full["path"] == ["PAL"]

        backend = backend_cls()
        controller = OnlineReasoningController(
            backend, policy, policy_source="research-pal-test",
            embedding_normalization="l2_unit",
        )
        result = MetaReasonerEngine(controller=controller).solve(query)
        assert result.strategy_path == eval_full["path"] == ["PAL"]
        assert result.tokens == eval_full["tokens"] == 10

    def test_legacy_bundle_unnormalized_raw_vector_semantics_preserved(self):
        """Legacy bundles with embedding_normalization=None/'none' preserve raw vector behavior."""
        query, records, policy, predictor, backend_cls = self._make_vector_collector_setup(
            cot_cost_fn=lambda x: 6.0 + x, react_cost_val=6.8, pal_cost_val=20.0
        )
        # Without normalization, raw vector [3.0, 4.0] gives x=3.0, COT cost 9.0 > REACT cost 6.8 -> chooses REACT
        backend = backend_cls()
        controller = OnlineReasoningController(
            backend, policy, policy_source="legacy-raw-test",
            embedding_normalization="none",
        )
        assert controller.embedding_normalization == "none"
        result = MetaReasonerEngine(controller=controller).solve(query)
        # Confirms legacy unnormalized behavior is strictly preserved
        assert result.strategy_path == ["REACT"]

        # Default None also preserves raw vector
        backend_default = backend_cls()
        controller_default = OnlineReasoningController(
            backend_default, policy, policy_source="legacy-default-test",
        )
        assert controller_default.embedding_normalization is None
        result_default = MetaReasonerEngine(controller=controller_default).solve(query)
        assert result_default.strategy_path == ["REACT"]

    def test_bundle_validation_embedding_normalization_contract(self):
        """PolicyBundle validation accepts valid embedding_normalization and rejects unsupported values."""
        # Valid l2_unit
        bundle_unit, policy = create_synthetic_specimen_bundle(
            hidden_size=2, lam=0.02, bundle_id="valid-unit", embedding_normalization="l2_unit"
        )
        report_unit = validate_policy_bundle(bundle_unit, policy, allow_synthetic=True)
        assert report_unit.is_valid

        # Valid none
        bundle_none, policy = create_synthetic_specimen_bundle(
            hidden_size=2, lam=0.02, bundle_id="valid-none", embedding_normalization="none"
        )
        report_none = validate_policy_bundle(bundle_none, policy, allow_synthetic=True)
        assert report_none.is_valid

        # Valid None (legacy)
        bundle_legacy, policy = create_synthetic_specimen_bundle(
            hidden_size=2, lam=0.02, bundle_id="valid-legacy", embedding_normalization=None
        )
        report_legacy = validate_policy_bundle(bundle_legacy, policy, allow_synthetic=True)
        assert report_legacy.is_valid

        # Invalid normalization raises BundleValidationError
        bundle_invalid = PolicyBundle(
            bundle_id="invalid-norm",
            review_status="synthetic_development_only",
            model_id="synthetic-mock-v1",
            model_snapshot="synthetic-20261020-mock",
            prompt_profile="aligned-direct-cot-v1",
            strategy_settings={"ladder": ["COT", "SELF_CONSISTENCY", "TOT"]},
            backend_protocol="LLMBackend.v1",
            embedding_dimension=2,
            feature_schema_version=1,
            predictor_kind="EntryPredictor",
            lambda_val=0.02,
            stopping_thresholds=bundle_unit.stopping_thresholds,
            mean_costs=bundle_unit.mean_costs,
            calibrator_type=None,
            calibrator_semantics="raw_confidence_uncalibrated",
            cost_metadata={"token_unit": "thousands", "scope": "generated_tokens_only"},
            budget_token_semantics="generated_tokens_only",
            execution_mode="online_policy",
            source_hashes={"reasoning/bundle.py": "test"},
            artifact_hashes={"test": "hash"},
            dataset_versions={"split": "v1"},
            train_calibration_provenance={"test": True},
            split_separation_verified=True,
            review_scope="test",
            compatibility_conditions={},
            is_production_approved=False,
            embedding_normalization="unsupported_min_max_norm",
        )
        with pytest.raises(BundleValidationError, match="Unsupported embedding_normalization"):
            validate_policy_bundle(bundle_invalid, policy, allow_synthetic=True)

    def test_approved_bundle_preprocessing_binding_and_conflict_rejection(self, tmp_path):
        """Authoritative artifact binding: approved bundles must match artifact normalization and reject caller overrides."""
        import json
        import hashlib
        from dataclasses import replace

        query, records, policy, predictor, backend_cls = self._make_vector_collector_setup(
            cot_cost_fn=lambda x: 6.0 + x, react_cost_val=6.8, pal_cost_val=20.0
        )
        specimen, _ = create_synthetic_specimen_bundle(hidden_size=2)
        artifact_path = tmp_path / "authored_reviewed_policy.json"
        artifact_data = {
            "lambda": policy.lam,
            "tau": list(policy.tau),
            "mean_cost": list(policy.mean_cost),
            "entry_cost_models": [
                {
                    "coef": getattr(
                        getattr(m, "best_estimator_", m).named_steps.get("head")
                        if hasattr(getattr(m, "best_estimator_", m), "named_steps")
                        else getattr(m, "best_estimator_", m),
                        "coef_",
                        np.array([]),
                    ).tolist(),
                    "intercept": float(
                        getattr(
                            getattr(m, "best_estimator_", m).named_steps.get("head")
                            if hasattr(getattr(m, "best_estimator_", m), "named_steps")
                            else getattr(m, "best_estimator_", m),
                            "intercept_",
                            0.0,
                        )
                    ),
                }
                for m in predictor.cost
            ],
            "entry_perf_models": [{"constant": m.value} for m in predictor.perf],
            "embedding_normalization": "l2_unit",
        }
        artifact_path.write_text(json.dumps(artifact_data, indent=2) + "\n")
        art_hash = hashlib.sha256(artifact_path.read_bytes()).hexdigest()

        src_path = Path(__file__).resolve()
        src_hash = hashlib.sha256(src_path.read_bytes()).hexdigest()

        approved_bundle = replace(
            specimen,
            bundle_id="approved-unit-bundle",
            review_status="approved",
            is_production_approved=True,
            review_scope="authored validation fixture only",
            stopping_thresholds=tuple(policy.tau),
            mean_costs=tuple(policy.mean_cost),
            source_hashes={str(src_path): src_hash},
            artifact_hashes={str(artifact_path): art_hash},
            embedding_normalization="l2_unit",
        )

        # 1. Positive control: approved bundle with matching unit normalization routes to COT
        backend_pos = backend_cls()
        backend_pos.model_id = approved_bundle.model_id
        backend_pos.model_snapshot = approved_bundle.model_snapshot
        backend_pos.prompt_profile = approved_bundle.prompt_profile
        report_pos = validate_policy_bundle(approved_bundle, policy, backend_pos)
        assert report_pos.is_valid and report_pos.is_approved
        controller_pos = OnlineReasoningController(backend_pos, policy, bundle=approved_bundle)
        assert controller_pos.embedding_normalization == "l2_unit"
        result_pos = MetaReasonerEngine(controller=controller_pos).solve(query)
        assert result_pos.strategy_path == ["COT"]

        # 2. Conflict 1: Caller attempting to override approved bundle's normalization is rejected
        backend_override = backend_cls()
        backend_override.model_id = approved_bundle.model_id
        backend_override.model_snapshot = approved_bundle.model_snapshot
        backend_override.prompt_profile = approved_bundle.prompt_profile
        with pytest.raises(ValueError, match="Conflicting embedding_normalization"):
            OnlineReasoningController(
                backend_override, policy, bundle=approved_bundle, embedding_normalization="none"
            )

        # 3. Conflict 2: Bundle metadata specifies 'none' but authoritative artifact declares 'l2_unit'
        bundle_conflict = replace(approved_bundle, embedding_normalization="none")
        with pytest.raises(BundleValidationError, match="conflicts with authoritative artifact"):
            validate_policy_bundle(bundle_conflict, policy, backend_pos)

        # 4. Conflict 3: Bundle metadata omits normalization (None) but authoritative artifact declares 'l2_unit'
        bundle_missing = replace(approved_bundle, embedding_normalization=None)
        with pytest.raises(BundleValidationError, match="missing explicit embedding_normalization"):
            validate_policy_bundle(bundle_missing, policy, backend_pos)

        # 5. Legacy control: unnormalized execution preserves raw vector behavior
        backend_legacy = backend_cls()
        controller_legacy = OnlineReasoningController(
            backend_legacy, policy, policy_source="legacy-raw", embedding_normalization="none"
        )
        assert controller_legacy.embedding_normalization == "none"
        result_legacy = MetaReasonerEngine(controller=controller_legacy).solve(query)
        assert result_legacy.strategy_path == ["REACT"]

