"""Tests for cross-strategy agreement canonicalizer and signal logic."""

import pytest
from scripts.agreement import canonicalize_answer


def test_arith_canonicalizer_units_fixture():
    # Primary prereg fixture: '192' vs '192 slices'
    assert canonicalize_answer("192", "arith") == canonicalize_answer("192 slices", "arith")
    assert canonicalize_answer("192", "arith") == "192"
    assert canonicalize_answer("192 slices", "arith") == "192"


def test_arith_canonicalizer_commas():
    assert canonicalize_answer("2,760", "arith") == "2760"
    assert canonicalize_answer("2760", "arith") == "2760"
    assert canonicalize_answer("2,760", "arith") == canonicalize_answer("2760", "arith")


def test_order_canonicalizer_casing_and_punctuation():
    # Order fixture: 'Carol.' vs 'carol'
    assert canonicalize_answer("Carol.", "order") == canonicalize_answer("carol", "order")
    assert canonicalize_answer("Carol.", "order") == "carol"
    assert canonicalize_answer("**Answer**: Bob.", "order") == "bob"
    assert canonicalize_answer("Frank", "order") == "frank"


def test_g24_canonicalizer_validity():
    meta = {"numbers": [3, 8, 3, 8]}
    # Valid expression evaluated by check24
    assert canonicalize_answer("8/(3-8/3)", "g24", meta) == "__VALID_24__"
    # Invalid expression
    assert canonicalize_answer("3+8+3+8", "g24", meta) != "__VALID_24__"
