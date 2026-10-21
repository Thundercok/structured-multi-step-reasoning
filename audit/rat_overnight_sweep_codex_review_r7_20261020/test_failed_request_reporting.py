"""The actual reporting branch must distinguish attempted and successful calls.

Synthetic in-memory records only; no real backend/Qt initialization or inference.
"""
import ast
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def actual_report(records):
    source = ROOT / "scripts/run_native_performance_session.py"
    tree = ast.parse(source.read_text(), filename=str(source))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    classifier = next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name == "classify_record_backend")
    first = next(i for i,n in enumerate(main.body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "ledger_real_records" for t in n.targets))
    last = next(i for i in range(first, len(main.body)) if isinstance(main.body[i], ast.If)
                and isinstance(main.body[i].test, ast.Attribute) and main.body[i].test.attr == "fake_backend")
    code = compile(ast.fix_missing_locations(ast.Module(body=[copy.deepcopy(classifier)] + copy.deepcopy(main.body[first:last+1]), type_ignores=[])), str(source), "exec")
    ns = dict(args=SimpleNamespace(fake_backend=False), completed_records=records,
              current_run_dispatched=records)
    exec(code, ns)
    return {k:ns[k] for k in ["real_calls_count", "scope_status", "scope_note", "all_12_requests_succeeded"]}


@pytest.mark.parametrize("attempts,successful", [(12,False),(1,False),(12,True),(1,True)],
                         ids=["twelve-exceptions", "one-exception", "twelve-success-control", "one-success-control"])
def test_failed_attempts_never_claim_verified_or_successful_backend_requests(attempts, successful):
    records = [dict(event="request_complete", backend_type="real", session_id="synthetic-current-session",
                    request_id=f"synthetic-{i}", status="success" if successful else "exception:RuntimeError: fixture failure",
                    latency_ms=1, completion_tokens=1 if successful else None) for i in range(attempts)]
    report = actual_report(records)
    assert report["real_calls_count"] == attempts
    expected_verified = attempts == 12 and successful
    assert report["all_12_requests_succeeded"] is expected_verified
    if not successful:
        assert report["scope_status"] != "backend_inference_verified_12_calls", report
        assert f"{attempts} successful backend requests" not in report["scope_note"], report
    elif attempts == 12:
        assert report["scope_status"] == "backend_inference_verified_12_calls", report
