"""Independent review probes; isolated fake records and Qt fixtures only."""
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
from fractions import Fraction

import pytest
from PyQt6.QtWidgets import QApplication, QPushButton

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("runner_review_r3", ROOT / "scripts/run_native_performance_session.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


@pytest.mark.parametrize("records,expected", [
    ([{"call_index": 1, "completion_tokens": 10}], 1),
    ([{"event": "request_start", "call_index": 1, "request_id": "r1"}], 1),
    ([{"event": "request_start", "call_index": 1, "request_id": "r1"},
      {"event": "request_complete", "call_index": 1, "request_id": "r1", "completion_tokens": 10}], 1),
    ([{"call_index": 1, "completion_tokens": 10},
      {"event": "request_start", "call_index": 2, "request_id": "r2"},
      {"event": "request_complete", "call_index": 2, "request_id": "r2", "completion_tokens": 10}], 2),
], ids=["legacy-control", "pending-start-control", "completed-pair", "legacy-plus-pair"])
def test_budget_counts_attempts_instead_of_event_lines(tmp_path, records, expected):
    ledger = tmp_path / "calls.jsonl"
    ledger.write_text("".join(json.dumps(r) + "\n" for r in records))
    assert runner.count_existing_attempts(ledger) == expected


@pytest.fixture
def fake_session_dir():
    # Keep the review's captured failing artifacts immutable. Later repairs can
    # select a fresh one-request fake run without editing these assertions.
    return Path(os.environ.get("RAT_REVIEW_FAKE_OUTPUT_DIR") or (HERE / "fake_session"))


@pytest.fixture
def fake_perf(fake_session_dir):
    """Artifact from the one-call --fake-backend command preserved in fake_command.json."""
    return json.loads((fake_session_dir / "native_performance.json").read_text())


def test_fake_session_does_not_claim_real_model_calls(fake_perf):
    assert fake_perf["model_id"].startswith("mock/")
    assert fake_perf["scope_classification"]["type"] == "offline_fake_backend_simulation"
    assert fake_perf["real_model_calls_executed"] == 0


def test_single_fake_request_cannot_verify_twelve_native_requests(fake_perf):
    assert fake_perf["gates"]["all_12_requests_succeeded"] is False
    assert fake_perf["scope_classification"]["status"] != "backend_inference_verified_12_calls"


def test_single_request_has_no_warm_distribution(fake_perf, fake_session_dir):
    ledger = [json.loads(s) for s in (fake_session_dir / "calls.jsonl").read_text().splitlines()]
    completed = [s for s in ledger if s.get("event") == "request_complete"]
    assert len(completed) == 1
    warm = fake_perf.get("warm_generation_latency_ms")
    assert warm is None or all(warm.get(k) is None for k in ("min", "max", "median", "call_8_ms")), warm


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("paths", [
    ("/Applications/League of Legends.app", "/Applications/League of Legends copy.app"),
    ("/Applications/League of Legends.app", "/Users/fixture/Applications/League of Legends.app"),
], ids=["renamed-copy-same-directory", "system-user-directory-control"])
def test_candidate_labels_distinguish_full_bundle_identity(app, paths):
    from rat.kernel.contracts import Artifact
    from rat.kernel.view_spec import StandardViewProvider
    from rat.ui.view_renderer import QtViewRenderer

    choices = [dict(name="League of Legends", path=p, bundle_id="com.fixture.league", version="1.0") for p in paths]
    artifact = Artifact("same-directory-probe", "input_request", payload=dict(operation_name="open_application",
        missing_fields=[], candidate_choices=choices, supplied_inputs={"name": "Liên Minh"}, prompt="Choose installation"))
    renderer = QtViewRenderer(StandardViewProvider().provide_view(artifact), artifact)
    renderer.setFixedWidth(420)
    renderer.show()
    for _ in range(4):
        app.processEvents()
    try:
        buttons = [b for b in renderer.findChildren(QPushButton) if b.objectName() == "CandidateBtn"]
        assert len(buttons) == 2 and all(b.isVisible() for b in buttons)
        assert all(p in b.toolTip() for p, b in zip(paths, buttons))
        assert len({b.text() for b in buttons}) == 2, [b.text() for b in buttons]
    finally:
        renderer.close()
        renderer.deleteLater()
        app.processEvents()


def test_200_golden_scores_hold_under_current_25_feature_schema():
    # Preserve the existing 200 raw/clamped/additive score checks exactly;
    # substitute only the feature-count contract claimed by this handoff.
    source = ROOT / "tests/test_reranker_golden.py"
    tree = copy.deepcopy(ast.parse(source.read_text(), filename=str(source)))
    changed = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert) and ast.unparse(node.test) == "len(candidate['_feats']) == 20":
            node.test.comparators[0].value = 25
            changed += 1
    assert changed == 1
    scope = {"__name__": "golden_schema_review"}
    exec(compile(ast.fix_missing_locations(tree), str(source), "exec"), scope)
    scope["test_200_query_document_golden_scores_and_feature_invariant"]()


@pytest.mark.parametrize("raw,expected", [
    ("Answer: 1 - 1/3 = 2/3", Fraction(2, 3)),
    ("Answer: x = 3/4", Fraction(3, 4)),
    ("Answer: 3*(45+55) - 4*(120-85) + 250/5 = 290", Fraction(290)),
], ids=["terminal-fraction", "named-fraction", "integer-conclusion-control"])
def test_untyped_terminal_fraction_keeps_denominator(raw, expected):
    from reasoning_strategies import extract_answer

    parsed = extract_answer(raw)
    # Both a retained equation and a scalar rational are valid representations;
    # neither may silently change the mathematical value of its conclusion.
    conclusion = parsed.rsplit("=", 1)[-1].strip()
    assert Fraction(conclusion) == expected, {"raw": raw, "parsed": parsed}
