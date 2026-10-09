"""Unit tests for Query-Derived Certificate Verifier on Ordering."""

import json
import itertools
import random
from pathlib import Path
import pytest

from scripts.verified_pal_order import (
    OrderVerificationStatus,
    OrderClue,
    OrderConstraintIR,
    parse_order_query,
    extract_order_certificate,
    verify_order_certificate,
    should_escalate,
    solve_order_query,
    verify_order_execution,
)

ROOT = Path(__file__).resolve().parent.parent


def test_parse_query_style_b():
    query = (
        "5 runners (Carol, Grace, Alice, Heidi, Frank) ran a race with no ties. "
        "Clues: Frank finished immediately before Grace; "
        "Carol finished 2 places ahead of Dave: if Carol is in position p, then Dave is in position p+2; "
        "Alice finished before Frank. "
        "Who finished in 2nd place?"
    )
    # Note: Dave is not in the runners list in the test string above, so parser must fail closed!
    ir = parse_order_query(query)
    assert ir is None, "Parser must reject queries where clue names aren't in runners list"

    # Now valid runners list containing all participants:
    valid_query = (
        "5 runners (Carol, Grace, Alice, Dave, Frank) ran a race with no ties. "
        "Clues: Frank finished immediately before Grace; "
        "Carol finished 2 places ahead of Dave: if Carol is in position p, then Dave is in position p+2; "
        "Alice finished before Frank. "
        "Who finished in 2nd place?"
    )
    ir = parse_order_query(valid_query)
    assert ir is not None
    assert ir.runners == ("Carol", "Grace", "Alice", "Dave", "Frank")
    assert ir.ask_rank == 2
    assert len(ir.clues) == 3
    # Check clue types
    assert ir.clues[0].clue_type == "immediately_before"
    assert ir.clues[0].runner_x == "Frank"
    assert ir.clues[0].runner_y == "Grace"
    assert ir.clues[0].offset == 1

    assert ir.clues[1].clue_type == "gap"
    assert ir.clues[1].runner_x == "Carol"
    assert ir.clues[1].runner_y == "Dave"
    assert ir.clues[1].offset == 2

    assert ir.clues[2].clue_type == "before"
    assert ir.clues[2].runner_x == "Alice"
    assert ir.clues[2].runner_y == "Frank"


def test_parse_query_style_a():
    query_a = (
        "5 runners (Alice, Bob, Carol, Dave, Erin) ran a race with no ties. "
        "Clues: Alice finished exactly 3 places ahead of Dave, with exactly 2 runners between them; "
        "Bob finished after Carol. "
        "Who finished in 4th place?"
    )
    ir = parse_order_query(query_a)
    assert ir is not None
    assert ir.ask_rank == 4
    assert len(ir.clues) == 2
    assert ir.clues[0].clue_type == "gap"
    assert ir.clues[0].offset == 3
    assert ir.clues[1].clue_type == "before"
    assert ir.clues[1].runner_x == "Carol"
    assert ir.clues[1].runner_y == "Bob"


def test_verify_valid_certificate():
    query = (
        "4 runners (Alice, Bob, Carol, Dave) ran a race with no ties. "
        "Clues: Alice finished before Bob; Bob finished immediately before Carol; Carol finished before Dave. "
        "Who finished in 3rd place?"
    )
    cert = {
        "order": ["Alice", "Bob", "Carol", "Dave"],
        "answer": "Carol",
    }
    res = verify_order_certificate(query, cert)
    assert res.status == OrderVerificationStatus.VALID
    assert not should_escalate(res)
    assert res.reason == "ok"


def test_verify_inverted_before_after():
    """Unit test for inverted before/after relation."""
    query = (
        "4 runners (Alice, Bob, Carol, Dave) ran a race with no ties. "
        "Clues: Alice finished before Bob; Bob finished immediately before Carol; Carol finished before Dave. "
        "Who finished in 3rd place?"
    )
    # Invert Alice and Bob
    cert_inverted = {
        "order": ["Bob", "Alice", "Carol", "Dave"],
        "answer": "Carol",
    }
    res = verify_order_certificate(query, cert_inverted)
    assert res.status == OrderVerificationStatus.INVALID
    assert should_escalate(res)
    assert "clue_violated" in res.reason


def test_verify_wrong_offset():
    """Unit test for gap offset translation error (e.g. k=3 instead of k=2)."""
    query = (
        "5 runners (Alice, Bob, Carol, Dave, Erin) ran a race with no ties. "
        "Clues: Alice finished 2 places ahead of Carol: if Alice is in position p, then Carol is in position p+2; "
        "Bob finished immediately before Dave. "
        "Who finished in 1st place?"
    )
    # Alice at 1, Carol at 4 (gap = 3 instead of 2)
    cert_wrong_offset = {
        "order": ["Alice", "Bob", "Dave", "Carol", "Erin"],
        "answer": "Alice",
    }
    res = verify_order_certificate(query, cert_wrong_offset)
    assert res.status == OrderVerificationStatus.INVALID
    assert should_escalate(res)
    assert "expected gap 2, got 3" in res.reason


def test_verify_missing_or_duplicate_runner():
    """Unit test for malformed runner permutation."""
    query = (
        "4 runners (Alice, Bob, Carol, Dave) ran a race with no ties. "
        "Clues: Alice finished before Bob. "
        "Who finished in 1st place?"
    )
    # Missing Dave, duplicated Bob
    cert_dup = {
        "order": ["Alice", "Bob", "Carol", "Bob"],
        "answer": "Alice",
    }
    res = verify_order_certificate(query, cert_dup)
    assert res.status == OrderVerificationStatus.INVALID
    assert should_escalate(res)
    assert "order_runner_set_mismatch" in res.reason


def test_verify_wrong_asked_position():
    """Unit test where order is valid but answer field names the wrong position."""
    query = (
        "4 runners (Alice, Bob, Carol, Dave) ran a race with no ties. "
        "Clues: Alice finished before Bob; Bob finished before Carol; Carol finished before Dave. "
        "Who finished in 3rd place?"
    )
    # Order is correct: 1=Alice, 2=Bob, 3=Carol, 4=Dave
    # But answer claims "Alice" (1st) instead of "Carol" (3rd)
    cert_wrong_ans = {
        "order": ["Alice", "Bob", "Carol", "Dave"],
        "answer": "Alice",
    }
    res = verify_order_certificate(query, cert_wrong_ans)
    assert res.status == OrderVerificationStatus.INVALID
    assert should_escalate(res)
    assert "answer_mismatch" in res.reason


def test_verify_unverifiable_on_missing_or_unparseable():
    """Unit test for fail-closed behavior on missing certificate or runtime crash."""
    query = (
        "4 runners (Alice, Bob, Carol, Dave) ran a race with no ties. "
        "Clues: Alice finished before Bob. "
        "Who finished in 1st place?"
    )
    res_none = verify_order_certificate(query, None)
    assert res_none.status == OrderVerificationStatus.UNVERIFIABLE
    assert should_escalate(res_none)

    res_empty = verify_order_certificate(query, "")
    assert res_empty.status == OrderVerificationStatus.UNVERIFIABLE
    assert should_escalate(res_empty)

    res_invalid_json = verify_order_certificate(query, "ValueError: code produced no result")
    assert res_invalid_json.status == OrderVerificationStatus.UNVERIFIABLE
    assert should_escalate(res_invalid_json)


def test_real_dataset_coverage():
    """Verify that 100% of ordering queries in gen02_tune and gen02_tune_gapB are parsed successfully."""
    tune_path = ROOT / "data/gen02_tune.json"
    if tune_path.exists():
        d = json.loads(tune_path.read_text())
        order_items = [it for it in d["items"] if it.get("family") == "order"]
        for it in order_items:
            ir = parse_order_query(it["query"])
            assert ir is not None, f"Failed to parse query for {it['id']}: {it['query']}"
            assert len(ir.runners) >= 5
            assert len(ir.clues) >= 2

    gapb_path = ROOT / "data/gen02_tune_gapB.json"
    if gapb_path.exists():
        d_gapb = json.loads(gapb_path.read_text())
        for it in d_gapb["items"]:
            ir = parse_order_query(it["query"])
            assert ir is not None, f"Failed to parse gapB query for {it['id']}: {it['query']}"
            assert len(ir.runners) >= 5
            assert len(ir.clues) >= 2

    conf_path = ROOT / "data/order_confirmatory_gapB_100.json"
    if conf_path.exists():
        d_conf = json.loads(conf_path.read_text())
        assert len(d_conf["items"]) == 100
        for it in d_conf["items"]:
            ir = parse_order_query(it["query"])
            assert ir is not None, f"Failed to parse confirmatory query for {it['id']}: {it['query']}"
            assert len(ir.runners) >= 5
            assert len(ir.clues) >= 2


_STRICT_QUERY = (
    "3 runners (Alice, Bob, Carol) ran a race with no ties. "
    "Clues: Alice finished before Bob; Bob finished before Carol. "
    "Who finished in 1st place?"
)
_STRICT_CERT = {"order": ["Alice", "Bob", "Carol"], "answer": "Alice"}


@pytest.mark.parametrize("query", [
    _STRICT_QUERY + " Carol finished first.",
    "Carol finished first. " + _STRICT_QUERY,
    _STRICT_QUERY.replace("Clues:", "Carol finished first. Clues:"),
    _STRICT_QUERY.replace("before Bob;", "before Bob; ;"),
    _STRICT_QUERY.replace("1st place?", "1th place?"),
    _STRICT_QUERY.replace("3 runners", "9" * 4500 + " runners"),
])
def test_parser_consumes_the_entire_query(query):
    assert parse_order_query(query) is None
    assert verify_order_certificate(query, _STRICT_CERT).status == OrderVerificationStatus.UNVERIFIABLE


@pytest.mark.parametrize("name", [[], {}, None, 1, True])
def test_bad_certificate_elements_return_a_status_instead_of_crashing(name):
    cert = {"order": [name, "Bob", "Carol"], "answer": "Alice"}
    result = verify_order_certificate(_STRICT_QUERY, cert)
    assert result.status == OrderVerificationStatus.INVALID
    assert should_escalate(result)


@pytest.mark.parametrize("payload", [
    'result = {"order": ["Alice", "Bob", "Carol"], "answer": "Alice"}',
    '{"order": ["Alice", "Bob", "Carol"], "answer": "Alice"}\nAnswer: Carol',
    '{"order": ["Alice", "Bob", "Carol"], "answer": "Alice", "answer": "Carol"}',
])
def test_only_whole_actual_payloads_are_certificates(payload):
    assert extract_order_certificate(payload) is None


def test_failed_execution_cannot_accept_a_literal_in_generated_source():
    result = verify_order_execution(_STRICT_QUERY, {
        "ok": False, "output": json.dumps(_STRICT_CERT), "finish_reason": "stop",
    })
    assert result.status == OrderVerificationStatus.UNVERIFIABLE
    result = verify_order_execution(_STRICT_QUERY, {
        "ok": True, "output": json.dumps(_STRICT_CERT), "finish_reason": "length",
    })
    assert result.status == OrderVerificationStatus.UNVERIFIABLE


def test_immediately_after_is_normalized_to_the_correct_direction():
    query = _STRICT_QUERY.replace("Alice finished before Bob", "Bob finished immediately after Alice")
    assert solve_order_query(query).answer == "Alice"
    assert verify_order_certificate(query, _STRICT_CERT).status == OrderVerificationStatus.VALID


def test_solver_abstains_on_ambiguity_and_inconsistent_constraints():
    ambiguous = _STRICT_QUERY.replace("; Bob finished before Carol", "")
    assert solve_order_query(ambiguous).status == "ambiguous"
    assert verify_order_certificate(ambiguous, _STRICT_CERT).status == OrderVerificationStatus.UNVERIFIABLE
    inconsistent = _STRICT_QUERY.replace("Bob finished before Carol", "Bob finished before Alice")
    assert solve_order_query(inconsistent).status == "unsatisfiable"


def test_unique_asked_occupant_does_not_require_a_unique_full_order():
    query = _STRICT_QUERY.replace("Bob finished before Carol", "Alice finished before Carol")
    solved = solve_order_query(query)
    assert solved.status == "solved"
    assert solved.answer == "Alice"
    assert solved.solution_count == 2
    assert verify_order_certificate(query, _STRICT_CERT).status == OrderVerificationStatus.VALID


@pytest.mark.parametrize("termination", [None, "error", "timeout"])
def test_unrecorded_or_failed_termination_is_unverifiable(termination):
    result = verify_order_execution(_STRICT_QUERY, {
        "ok": True, "output": json.dumps(_STRICT_CERT), "finish_reason": termination,
    })
    assert result.status == OrderVerificationStatus.UNVERIFIABLE


def test_symbolic_solver_matches_independent_exhaustive_fixture_oracle():
    from scripts.gen_tasks import render_order

    rng = random.Random(501)
    names = ["Alice", "Bob", "Carol", "Dave"]
    for _ in range(60):
        clues = []
        for _ in range(rng.randint(1, 5)):
            a, b = rng.sample(range(4), 2)
            kind = rng.choice(["a", "b", "g"])
            clues.append([kind, a, b, rng.randint(1, 3) if kind == "g" else 1 if kind == "a" else 0])
        ask = rng.randrange(4)
        occupants = set()
        for permutation in itertools.permutations(range(4)):
            positions = {runner: rank for rank, runner in enumerate(permutation)}
            if all((positions[a] < positions[b] if kind == "b" else positions[b] - positions[a] == offset) for kind, a, b, offset in clues):
                occupants.add(names[permutation[ask]])
        query = render_order({"names": names, "clues": clues, "ask": ask, "style": "B"})
        solved = solve_order_query(query)
        expected = "solved" if len(occupants) == 1 else "ambiguous" if occupants else "unsatisfiable"
        assert solved.status == expected
        assert solved.answer == (next(iter(occupants)) if len(occupants) == 1 else None)
