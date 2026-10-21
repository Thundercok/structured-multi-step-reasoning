"""Independent value/provenance checks. Only fake or captured historical data.

The AST helper executes the actual runner's nested classifier in isolation; it
does not import/main the runner, initialize MLX or copy its implementation.
"""
import ast
from fractions import Fraction
import json
import os
from pathlib import Path

import pytest
from reasoning_strategies import extract_answer

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


@pytest.mark.parametrize("raw,expected", [
    ("Answer: 2 + 2 = 4; 1 / 4 = 1/4", Fraction(1, 4)),
    ("Therefore 2 + 2 = 4; 1 / 4 = 1/4", Fraction(1, 4)),
    ("Answer: x = 3/4", Fraction(3, 4)),
    ("Answer: 2 + 2 = 4; 4 * 2 = 8", Fraction(8)),
], ids=["marker-final-rational", "fallback-final-rational", "single-rational-control", "final-integer-control"])
def test_final_conclusion_not_earlier_intermediate_scalar(raw, expected):
    parsed = extract_answer(raw)
    # Accept a numeric result or a preserved final expression, as in prior probes.
    conclusion = parsed.rsplit("=", 1)[-1].strip()
    if "/" in conclusion:
        numerator, denominator = conclusion.split("/", 1)
        actual = Fraction(numerator.strip()) / Fraction(denominator.strip())
    else:
        actual = Fraction(conclusion)
    assert actual == expected, {"input": raw, "parsed": parsed, "expected": str(expected)}


@pytest.fixture(scope="module")
def actual_classifier():
    source = ROOT / "scripts/run_native_performance_session.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "classify_record_backend"]
    assert len(functions) == 1
    isolated = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    namespace = {}
    exec(compile(isolated, str(source), "exec"), namespace)
    return namespace["classify_record_backend"]


@pytest.mark.parametrize("kind,expected", [
    ("legacy-captured-fake", {"fake", "unknown"}),
    ("explicit-fake", {"fake"}),
    ("explicit-real", {"real"}),
    ("no-provenance", {"unknown"}),
])
def test_backend_provenance_never_inferred_real_from_timing_or_token_count(kind, expected, actual_classifier):
    if kind == "legacy-captured-fake":
        # This is genuine fake-run evidence from r3, with command/raw log preserved.
        records = [json.loads(line) for line in (HERE / "legacy_fake_calls.jsonl").read_text().splitlines()]
        record = next(r for r in records if r.get("event") == "request_complete")
        assert "backend_type" not in record and record["prompt_tokens"] >= 500
    elif kind.startswith("explicit-"):
        record = {"backend_type": kind.removeprefix("explicit-"), "prompt_tokens": 2031,
                  "first_token_ms": 0.531}
    else:
        record = {"event": "request_complete", "completion_tokens": 28}
    assert actual_classifier(record) in expected, {"kind": kind, "record": record}


@pytest.mark.parametrize("folder,expected_new_fake", [
    ("fake_session", 1), ("fake_history_halt", 0),
], ids=["fresh-fake-control", "budget-halt-on-tagged-fake-history"])
def test_executed_fake_count_describes_current_run(folder, expected_new_fake):
    output_root = Path(os.environ.get("RAT_REVIEW_R5_OUTPUT_DIR") or HERE)
    perf = json.loads((output_root / folder / "native_performance.json").read_text())
    if folder == "fake_history_halt":
        assert (output_root / folder / "calls.jsonl").read_bytes() == (output_root / "fake_session/calls.jsonl").read_bytes()
        log = (output_root / f"{folder}.txt").read_text()
        assert "No new requests will be dispatched" in log
    assert perf["fake_model_calls_executed"] == expected_new_fake, perf["scope_classification"]
