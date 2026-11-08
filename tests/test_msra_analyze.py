"""Unit tests for MSRA DAG complexity analysis."""

import json
from pathlib import Path
import pytest
from structured_llm.msra.analyze_dag import analyze_dataset_dag


def test_analyze_dataset_dag_empty_and_valid(tmp_path):
    test_file = tmp_path / "test.jsonl"
    row1 = {
        "text": (
            "<|im_start|>user\nWhat is 2+2?<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n"
            "<step id=\"1\" budget_remaining=\"2.00\">\n"
            "  <subgoal>Calculate sum</subgoal>\n"
            "  <deps>None</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>2+2 = 4</execution>\n"
            "  <verification status=\"COMMIT\">Exact</verification>\n"
            "  <output_var>v1 = 4</output_var>\n"
            "</step>\n"
            "</think>\n\nAnswer: 4<|im_end|>"
        )
    }
    row2 = {
        "text": (
            "<|im_start|>user\nWhat is 4*2?<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n"
            "<step id=\"1\" budget_remaining=\"2.00\">\n"
            "  <subgoal>Calculate part 1</subgoal>\n"
            "  <deps>None</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>2*2 = 4</execution>\n"
            "  <verification status=\"COMMIT\">Exact</verification>\n"
            "  <output_var>v1 = 4</output_var>\n"
            "</step>\n\n"
            "<step id=\"2\" budget_remaining=\"2.00\">\n"
            "  <subgoal>Calculate part 2</subgoal>\n"
            "  <deps>v1 = 4</deps>\n"
            "  <capability>CAP:SYMBOLIC_CALC</capability>\n"
            "  <decision>SOLVE_LOCAL</decision>\n"
            "  <execution>4*2 = 8</execution>\n"
            "  <verification status=\"COMMIT\">Exact</verification>\n"
            "  <output_var>v2 = 8</output_var>\n"
            "</step>\n"
            "</think>\n\nAnswer: 8<|im_end|>"
        )
    }
    test_file.write_text(f"{json.dumps(row1)}\n{json.dumps(row2)}\n", encoding="utf-8")

    stats = analyze_dataset_dag(test_file)
    assert stats["total_problems"] == 2
    assert stats["total_nodes"] == 3
    assert stats["mean_steps_per_problem"] == 1.5
    assert stats["dependency_in_degree_distribution"]["0_deps"]["count"] == 2
    assert stats["dependency_in_degree_distribution"]["1_deps"]["count"] == 1
    assert stats["verification_distribution"]["COMMIT"] == 3
