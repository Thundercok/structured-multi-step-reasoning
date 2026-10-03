import copy
import io

import numpy as np
import pytest

from experiments.research_study import check_answer, collect_records, smoke_dataset, validate_dataset
from reasoning_strategies import extract_answer, majority_vote, parse_answer_details
from research_scoring import numeric_literal
from scripts.gen_tasks import check


@pytest.mark.parametrize("answer", ["52 is incorrect", "not 52", "52 or 51", "52 is only an earlier estimate"])
def test_numeric_negation_and_alternatives_survive_parsing_and_are_rejected(answer):
    parsed = extract_answer(f"Answer: {answer}", answer_type="number")
    assert not check({"family": "arith", "answer": "52"}, parsed)
    assert not check_answer(parsed, {"answer_type": "number", "answer": "52"})


@pytest.mark.parametrize("answer", ["Heidi did not finish fourth", "Heidi or Zed", "Heidi or Bob", "Heidi finished in 1st place"])
def test_order_requires_one_asserted_name_and_consistent_ordinal(answer):
    item = {"family": "order", "answer": "Heidi", "meta": {"ask": 3}}
    assert not check(item, answer)
    assert check(item, "Heidi finished in 4th place")
    assert check(item, "Heidi.")


def test_expression_is_preserved_and_entire_equality_is_checked():
    item = {"family": "g24", "meta": {"numbers": [10, 13, 2, 3]}}
    for expression in ("10 + 13 + 3 - 2", "10 + 13 + 3 - 2 = 24"):
        parsed, status, _ = parse_answer_details(f"Answer: {expression}", answer_type="expression")
        assert parsed == expression and status == "marker"
        assert check(item, parsed)
    for expression in ("10+13+3-2 = 25", "10+13+3-2 = 24 = 100", "24", "10+13+3-2 = 24, but actually 25"):
        assert not check(item, extract_answer(f"Answer: {expression}", answer_type="expression"))


def test_expression_votes_do_not_merge_different_solutions_into_the_number_24():
    answers = ["10+13+3-2 = 24", "10 + 13 + 3 - 2 = 24", "(13+3)+(10-2)=24", "24", "25"]
    winner, ratio = majority_vote(answers, answer_type="expression")
    assert winner == "10+13+3-2=24"
    assert ratio == 2 / 5


def test_text_conflict_is_not_reduced_to_first_yes_no_and_aliases_are_exact():
    item = {"answer_type": "text", "answer": "No", "answer_aliases": ["không"]}
    assert not check_answer(extract_answer("Answer: No, the answer is Yes", answer_type="text"), item)
    assert check_answer(extract_answer("Answer: KHÔNG.", answer_type="text"), item)
    assert not check_answer("không hoặc có", item)
    assert not check_answer("not No", item)


@pytest.mark.parametrize("raw", ["**Answer: Frank**", "**Answer**: **Frank**", "Answer: **Frank**", "Answer: Answer: Frank", "Answer: **Answer: Frank**"])
def test_presentation_wrappers_do_not_turn_a_correct_name_into_a_format_failure(raw):
    parsed, status, _ = parse_answer_details(raw, answer_type="text")
    assert parsed == "Frank" and status == "marker"
    assert check({"family": "order", "answer": "Frank", "meta": {"ask": 0}}, parsed)


@pytest.mark.parametrize("candidate", ["Frank or Bob", "Frank did not finish first", "Frank finished in 2nd place", "Answer: Frank or Bob"])
def test_wrapped_contradictions_and_wrong_ordinals_remain_rejected(candidate):
    parsed = extract_answer(f"**Answer: {candidate}**", answer_type="text")
    assert not check({"family": "order", "answer": "Frank", "meta": {"ask": 0}}, parsed)


def test_wrapped_numeric_and_expression_candidates_retain_all_scoring_constraints():
    assert extract_answer("**Answer: **52****", answer_type="number") == "52"
    assert not check({"family": "arith", "answer": "52"}, extract_answer("**Answer: 52 is incorrect**", answer_type="number"))
    item = {"family": "g24", "meta": {"numbers": [1, 2, 3, 4]}}
    assert check(item, extract_answer("**Answer: 1*2*3*4=24**", answer_type="expression"))
    assert not check(item, extract_answer("**Answer: 1*2*3*4=25**", answer_type="expression"))
    assert not check_answer(extract_answer("**Answer: No. Answer: Yes**", answer_type="text"), {"answer_type": "text", "answer": "Yes"})


def test_decimal_separator_is_explicit_and_comma_is_not_silently_deleted():
    assert numeric_literal("1,234.5") == 1234.5
    assert numeric_literal("129,6", ",") == numeric_literal("129.6", ",")
    assert numeric_literal("129,6") is None
    assert numeric_literal("1,23,4", ",") is None
    item = {"answer_type": "number", "answer": "129.6", "decimal_separator": ","}
    parsed = extract_answer("Answer: 129,6", answer_type="number", decimal_separator=",")
    assert parsed == "129.6" and check_answer(parsed, item)
    assert check_answer("129,6", item)
    assert not check_answer("1296", item)


def test_invalid_alias_or_locale_metadata_is_rejected():
    dataset = smoke_dataset()
    for patch in ({"answer_aliases": "yes"}, {"answer_aliases": [" OK "]}, {"decimal_separator": ";"}):
        mutated = copy.deepcopy(dataset)
        mutated["items"][0].update(patch)
        with pytest.raises(ValueError):
            validate_dataset(mutated)


def test_collection_supplies_format_without_gold_to_backend():
    class Backend:
        def configure_answer_format(self, **fields):
            assert fields == {"answer_type": "expression", "decimal_separator": "."}
        def embed(self, query):
            return np.array([1.0, 0.0])
        def run(self, strategy, query):
            return "10+13+3-2=24", 0.5, 20
    item = {
        "id": "expression", "group_id": "expression", "split": "train", "query": "Use the four given numbers",
        "answer": "10+13+3-2", "answer_type": "text", "family": "g24", "meta": {"numbers": [10, 13, 2, 3]},
    }
    records = collect_records(Backend(), [item], 42, lambda seed: None, io.StringIO())
    assert all(attempt["correct"] for attempt in records[0]["attempts"].values())


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("**364**", "364"),
        ("**Answer: Erin**", "Erin"),
        ("Answer: Bob", "Bob"),
        ("Answer: (13 - 11) × (12 ÷ 1)", "(13 - 11) × (12 ÷ 1)"),
    ],
)
def test_k_raw_fixtures_normalization(raw, expected):
    from reasoning_strategies import normalize_answer

    assert normalize_answer(raw) == expected

