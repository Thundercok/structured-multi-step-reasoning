"""Offline v2 selector-contract regressions, not model-quality evidence."""

import copy

import pytest

from experiments.order_certificate_study import (
    PROMPTS, SETTINGS, _selected_answer, format_selector_candidates, parse_selector_index,
)
from experiments.research_study import check_answer
from scripts.pilot_order_certificate import _spec


@pytest.mark.parametrize("text,index", [
    ("Best: 0", 0), ("Best: 1", 1), ("Best: 2", 2),
    ("Answer: 0", 0), ("Answer: 1", 1), ("Answer: 2", 2),
    ("Candidate 0", 0), ("Candidate 1", 1), ("Candidate 2", 2),
    ("\n BEST : 2 \n", 2), ("answer:1", 1), ("candidate 0", 0),
])
def test_single_explicit_zero_based_index_alias(text, index):
    assert parse_selector_index(text) == index


@pytest.mark.parametrize("text", [
    "", None, 2, "2", "Best: 3", "Best: -1", "Best: 02", "Best: 2.0",
    "Best: 2 or 1", "Best: 0\nBest: 0", "Best: 0\nAnswer: 2",
    "Choose Best: 2 because it is correct", "Answer: Grace", "Candidate 2: Grace",
    "Candidate: 2", "```\nBest: 2\n```", "Best: 2\nAnswer: Grace",
])
def test_ambiguous_out_of_range_or_nonindex_output_rejects(text):
    assert parse_selector_index(text) is None


def attempt(selector):
    return {"arm": "candidate_selection", "generations": [
        {"output": "Answer: Frank", "finish_reason": "stop"},
        {"output": "Answer: Grace", "finish_reason": "stop"},
        {"output": "Answer: Grace", "finish_reason": "stop"},
        {"output": selector, "finish_reason": "stop"},
    ]}


def test_observed_alias_selects_wrong_candidate_not_a_gold_aware_rescue():
    # Historic train example: tolerating its Answer: 2 fixes syntax, not quality.
    row = attempt("Answer: 2")
    answer, complete = _selected_answer(row)
    assert (answer, complete) == ("Grace", True)
    assert not check_answer(answer, {"family": "order", "answer": "Frank"})
    assert _selected_answer(attempt("Best: 0")) == ("Frank", True)


@pytest.mark.parametrize("selector", ["Best: 2", "Answer: 2", "Candidate 2"])
def test_format_alias_never_overrides_selected_or_selector_truncation(selector):
    row = attempt(selector)
    truncated_selector = copy.deepcopy(row)
    truncated_selector["generations"][-1]["finish_reason"] = "length"
    assert _selected_answer(truncated_selector) == ("", False)
    # Selected candidate 2 is length-stopped.
    # Candidates 0 and 1 are both stopped (two admissible alternatives).
    # Contract v3 never selects a truncated branch; with multiple alternatives, it abstains.
    row["generations"][2]["finish_reason"] = "length"
    assert _selected_answer(row) == ("", False)
    # If candidate 0 is ALSO length-stopped, candidate 1 is the sole admissible branch and is redirected to!
    row["generations"][0]["finish_reason"] = "length"
    assert _selected_answer(row) == ("Grace", True)
    # If candidate 1 is ALSO length-stopped, zero admissible branches remain -> abstain.
    row["generations"][1]["finish_reason"] = "length"
    assert _selected_answer(row) == ("", False)
    # When candidate 0 is restored and selected, it succeeds.
    row["generations"][0]["finish_reason"] = "stop"
    row["generations"][-1]["output"] = "Best: 0"
    assert _selected_answer(row) == ("Frank", True)


@pytest.mark.parametrize("text,expected", [
    ("Answer: Alice", "Alice"),
    ("Reasoning.\nAnswer: Alice", "Alice"),
    ("**Answer: Alice**", "Alice"),
    ("**Answer:** Alice", "Alice"),
    ("### Answer: Alice", "Alice"),
    ("## **Answer: Alice**", "Alice"),
    ("Answer: Alice\n**Answer: Alice**", "Alice"),
    (" \nAnswer: Alice\n \n", "Alice"),
    ("", ""),
    (None, ""),
    ("Answer: Zelda", ""),
    ("Answer: Alice or Bob", ""),
    ("Answer: Alice because she won", ""),
    ("Not Answer: Alice", ""),
    ("Answer: not Alice", ""),
    ("Answer: Alice\nAnswer: Bob", ""),
    ("Answer: Alice\n\n**Answer: Bob**", ""),
    ("Answer: Zelda\nAnswer: Alice", ""),
    ("**Answer: Alice", ""),
    ("Answer: Alice**", ""),
    ("Answer: Alice\nExtra explanation", ""),
    ("```\nAnswer: Alice\n```", ""),
])
def test_contract_v3_final_answer_parsing_and_rejection(text, expected):
    from experiments.order_certificate_study import _final_answer
    runners = ("Alice", "Bob")
    assert _final_answer(text, runners) == expected


def test_contract_v3_selection_guard_invariants():
    runners = ("Alice", "Bob")
    call = lambda text, finish="stop": {"output": text, "finish_reason": finish}

    # Sole admissible branch redirect when selected candidate is truncated.
    row = {
        "arm": "candidate_selection",
        "runners": runners,
        "generations": [
            call("Answer: Alice", "length"),
            call("**Answer: Bob**", "stop"),
            call("unfinished", "length"),
            call("Best: 0", "stop"),
        ],
    }
    assert _selected_answer(row) == ("Bob", True)

    # Never change an admissible choice even if another branch might be correct.
    row["generations"] = [
        call("Answer: Alice", "stop"),
        call("Answer: Bob", "stop"),
        call("Answer: Bob", "stop"),
        call("Best: 0", "stop"),
    ]
    assert _selected_answer(row) == ("Alice", True)

    # An invalid choice with TWO admissible alternatives must abstain, not rank or guess.
    row["generations"][0] = call("unfinished", "length")
    assert _selected_answer(row) == ("", False)

    # Truncated selector must abstain even if candidates are stopped.
    row["generations"][3] = call("Best: 1", "length")
    assert _selected_answer(row) == ("", False)

    # Out-of-range or invalid selector must abstain.
    row["generations"][3] = call("Best: 9", "stop")
    assert _selected_answer(row) == ("", False)


def test_collector_labels_every_raw_candidate_with_identical_zero_based_indices():
    outputs = ["Reasoning A\nAnswer: Frank", "Reasoning B\nAnswer: Grace", ""]
    formatted = format_selector_candidates(outputs)
    assert formatted == (
        "Candidate 0:\nReasoning A\nAnswer: Frank\nEnd Candidate 0\n\n"
        "Candidate 1:\nReasoning B\nAnswer: Grace\nEnd Candidate 1\n\n"
        "Candidate 2:\n\nEnd Candidate 2"
    )
    spec = _spec({"id": "fixture", "query": "Question"}, 42, "candidate_selection", 3, SETTINGS, outputs)
    assert spec["messages"] == [{"role": "user", "content": "Question\n" + PROMPTS["selector"] + "\n" + formatted}]
    assert spec["temperature"] == 0.0
    assert spec["max_tokens"] == 64


@pytest.mark.parametrize("outputs", [[], ["a", "b"], ["a", "b", "c", "d"], ["a", None, "c"]])
def test_missing_or_extra_candidates_cannot_be_hidden_in_selector_prompt(outputs):
    with pytest.raises(ValueError, match="exactly three"):
        format_selector_candidates(outputs)


def test_v2_profile_is_explicit_and_does_not_relax_order_scorer():
    assert SETTINGS["prompt_profile"] == "order-contract-v2"
    assert SETTINGS["selector_parser_profile"] == "single-zero-based-index-v2"
    assert "bare runner name string" in PROMPTS["pal_answer"]
    assert check_answer("Frank", {"family": "order", "answer": "Frank"})
    assert not check_answer("4th place: Frank", {"family": "order", "answer": "Frank"})
