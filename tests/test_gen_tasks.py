import json
from pathlib import Path
import pytest

import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import gen_tasks
DATA_PATH = ROOT / "data" / "gen_v2.json"


def test_gen_tasks_selftest():
    # Verify built-in selftest passes without assertion error
    gen_tasks.selftest()


def test_gen_v2_json_file_verification():
    if not DATA_PATH.exists():
        pytest.skip("data/gen_v2.json not generated yet")
    assert gen_tasks.verify_file(str(DATA_PATH)) is True


def test_gen02_json_files_verification():
    for name in ["gen02_v2.json", "gen02_tune.json"]:
        p = ROOT / "data" / name
        assert p.exists(), f"{name} should exist"
        assert gen_tasks.verify_file(str(p)) is True


def test_check_contract_arith():
    item = {
        "family": "arith",
        "answer": "52",
        "meta": {"start": 59, "steps": [["mul", 2], ["sub", 66]]},
    }
    assert gen_tasks.check(item, "52")
    assert gen_tasks.check(item, "52.0")
    assert gen_tasks.check(item, "52 slices")
    assert gen_tasks.check(item, "$52")
    assert not gen_tasks.check(item, "51")
    assert not gen_tasks.check(item, "52 and 5")


def test_check_contract_order():
    item = {
        "family": "order",
        "answer": "Heidi",
        "meta": {"names": ["Bob", "Erin", "Grace", "Heidi"]},
    }
    assert gen_tasks.check(item, "Heidi")
    assert gen_tasks.check(item, "Heidi.")
    assert gen_tasks.check(item, "Heidi finished in 4th place")
    assert not gen_tasks.check(item, "Bob")
    assert not gen_tasks.check(item, "Heidi or Bob")


def test_order_gap_styles_and_verify():
    m = {
        "names": ["Alice", "Bob", "Carol"],
        "clues": [["g", 0, 1, 2]],  # Alice (pos 0) 2 places ahead of Bob (pos 2) -> Carol is in pos 1 (2nd place)
        "ask": 1,
    }
    # Style A (default)
    rendered_a = gen_tasks.render_order(m, gap_style="A")
    assert "Alice finished exactly 2 places ahead of Bob, with exactly 1 runner between them" in rendered_a
    item_a = {
        "family": "order",
        "query": rendered_a,
        "answer": "Carol",
        "meta": {**m, "gap_style": "A"},
    }
    assert gen_tasks.verify(item_a) is True

    # Style B
    rendered_b = gen_tasks.render_order(m, gap_style="B")
    expected_b = "Alice finished 2 places ahead of Bob: if Alice is in position p, then Bob is in position p+2"
    assert expected_b in rendered_b
    item_b = {
        "family": "order",
        "query": rendered_b,
        "answer": "Carol",
        "meta": {**m, "gap_style": "B"},
    }
    assert gen_tasks.verify(item_b) is True


def test_check_contract_g24():
    item = {
        "family": "g24",
        "answer": "((10+(13+3))-2)",
        "meta": {"numbers": [10, 13, 2, 3]},
    }
    # Accepts exact reference
    assert gen_tasks.check(item, "((10+(13+3))-2)")
    # Accepts alternative valid expressions matching numbers and evaluating to 24
    assert gen_tasks.check(item, "((10+13)+(3-2))")
    assert gen_tasks.check(item, "10 + 13 + 3 - 2 = 24")
    # Rejects invalid calculations or wrong numbers
    assert not gen_tasks.check(item, "10 + 13 + 2 + 3")  # 28 != 24
    assert not gen_tasks.check(item, "24")               # does not use numbers
    assert not gen_tasks.check(item, "(13 - 10) * 3 * 2") # 18 != 24
