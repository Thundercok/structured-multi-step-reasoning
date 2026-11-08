"""Unit tests for MSRA preference dataset builder and perturber."""

import json
from pathlib import Path
import pytest
from structured_llm.msra.build_preference_dataset import (
    generate_pairs_for_problem,
    perturb_calculation,
)


def test_perturb_calculation_numeric():
    perturbed, critique = perturb_calculation("10 * 5 = 50")
    assert "51" in perturbed or "50" in perturbed
    assert "Discrepancy" in critique
    assert "50" in critique


def test_generate_pairs_for_problem_structure():
    row = {
        "id": "test_1",
        "text": (
            "<|im_start|>user\nCalculate 10 + 20.<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n"
            "<step id=\"1\" budget_remaining=\"2.00\">\n"
            "  <subgoal>Calculate sum</subgoal>\n"
            "  <deps>None</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>10 + 20 = 30</execution>\n"
            "  <verification status=\"COMMIT\">Exact</verification>\n"
            "  <output_var>v1 = 30</output_var>\n"
            "</step>\n"
            "</think>\n\nAnswer: 30<|im_end|>"
        ),
    }

    pairs = generate_pairs_for_problem(row)
    assert len(pairs) == 3

    categories = [p.category for p in pairs]
    assert "anti_laziness" in categories
    assert "anti_conservatism" in categories
    assert "adversarial_verification" in categories

    for p in pairs:
        assert p.prompt.startswith("<|im_start|>user\nCalculate 10 + 20.<|im_end|>")
        assert len(p.chosen) > 0
        assert len(p.rejected) > 0
