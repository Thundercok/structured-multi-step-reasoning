"""Tests for semantic enrichment of GSM8K Step 1 reasoning traces."""

import pytest
from structured_llm.gsm8k import convert, enrich_step1_prose
from structured_llm.counterfactual import counterfactual
from structured_llm.trace import check

SAMPLE_ROW = {
    "question": "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell in May?",
    "answer": "Natalia sold 48/2 = <<48/2=24>>24 clips in May.\nNatalia sold 48+24 = <<48+24=72>>72 clips altogether in April and May.\n#### 72",
}

SAMPLE_MONEY_ROW = {
    "question": "Adam bought 3 sandwiches, for $3 each, and a bottle of water for $2. How much did Adam pay?",
    "answer": "Adam bought 3 sandwiches, so he paid 3 * 3 = $<<3*3=9>>9 for them.\nIn total Adam bought products for 2 + 9 = $<<2+9=11>>11.\n#### 11",
}


def test_enrich_step1_prose_already_prefixed():
    assert enrich_step1_prose("Calculate the cost of gas") == "Calculate the cost of gas"
    assert enrich_step1_prose("Calculate total gas") == "Calculate the total gas"


def test_enrich_step1_prose_leading_the():
    prose = "The total amount of money that Vivienne gets is 40*400 = 16000"
    enr = enrich_step1_prose(prose)
    assert enr.startswith("Calculate the total amount of money that Vivienne gets:")
    assert "::" not in enr


def test_enrich_step1_prose_first_find():
    prose = "First find the total amount of cleaner used for the dogs: 6 * 6 = 36 ounces"
    enr = enrich_step1_prose(prose)
    assert enr == "Calculate the total amount of cleaner used for the dogs: 6 * 6 = 36 ounces"


def test_enrich_step1_prose_the_costs():
    prose = "The popcorn costs 8 - 3 = $5."
    enr = enrich_step1_prose(prose)
    assert enr.startswith("Calculate the cost of the popcorn:")


def test_enrich_step1_prose_there_are_unit():
    prose = "There are 400/4 = 100 white homes in Belize."
    enr = enrich_step1_prose(prose)
    assert enr.startswith("Calculate the number of white homes:")


def test_enrich_step1_prose_money_and_time():
    prose_money = "Adam bought 3 sandwiches, so he paid 3 * 3 = $9 for them."
    enr_money = enrich_step1_prose(prose_money)
    assert enr_money.startswith("Calculate the cost:")

    prose_time = "Jackie spends a total of 8 + 8 + 3 = 19 hours on work, exercise, and sleeping."
    enr_time = enrich_step1_prose(prose_time)
    assert enr_time.startswith("Calculate the total hours:")


def test_convert_enrich_flag():
    # enrich_step1=False (default behavior)
    trace_raw, reason_raw = convert(SAMPLE_ROW, enrich_step1=False)
    assert reason_raw is None
    assert "Step 1: Natalia sold" in trace_raw
    assert "Step 1: Calculate the" not in trace_raw

    # enrich_step1=True
    trace_enr, reason_enr = convert(SAMPLE_ROW, enrich_step1=True)
    assert reason_enr is None
    assert "Step 1: Calculate the number of clips: Natalia sold" in trace_enr

    # Strict grammar check passes
    res = check(trace_enr, SAMPLE_ROW["question"])
    assert not res["errors"]
    assert res["format_valid"] is True


def test_counterfactual_enrich_flag():
    made_raw, _ = counterfactual(SAMPLE_ROW, "seed1", enrich_step1=False)
    assert made_raw is not None
    assert "Step 1: Calculate the" not in made_raw["trace"]

    made_enr, _ = counterfactual(SAMPLE_ROW, "seed1", enrich_step1=True)
    assert made_enr is not None
    assert "Step 1: Calculate the" in made_enr["trace"]

    # Check validity of counterfactual trace
    res = check(made_enr["trace"], made_enr["question"])
    assert not res["errors"]
    assert res["format_valid"] is True
