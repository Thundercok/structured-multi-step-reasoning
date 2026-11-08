"""Unit tests for MSRA dataset converter."""

import json
from pathlib import Path
import pytest
from structured_llm.msra.convert_traces import (
    convert_chatml_row,
    convert_dataset_file,
    convert_pairs_to_nodes,
    convert_trace_to_msra_xml,
    extract_subgoal,
    parse_step_calc_pairs,
)
from structured_llm.msra.trace_parser import parse_trace
from structured_llm.msra.types import CapabilityTag, Decision, VerificationStatus


def test_extract_subgoal():
    assert extract_subgoal("Calculate the total clips sold in May: 48/2 = 24") == "Calculate the total clips sold in May"
    assert extract_subgoal("First find how many apples he ate. Then compute remainder.") == "Calculate how many apples he ate"
    assert extract_subgoal("Determine the unit price of one pencil.") == "Calculate the unit price of one pencil"


def test_parse_step_calc_pairs():
    think_text = """
    Step 1: Natalia sold 48/2 = 24 clips in May.
    Calc: 48/2=24
    Step 2: Natalia sold 48+24 = 72 clips altogether.
    Calc: 48+24=72
    """
    pairs = parse_step_calc_pairs(think_text)
    assert len(pairs) == 2
    assert pairs[0][0] == "Natalia sold 48/2 = 24 clips in May."
    assert pairs[0][1] == "48/2=24"
    assert pairs[1][0] == "Natalia sold 48+24 = 72 clips altogether."
    assert pairs[1][1] == "48+24=72"


def test_convert_pairs_to_nodes_dag_dependencies():
    pairs = [
        ("Step 1: Calculate May clips: 48/2 = 24", "48/2=24"),
        ("Step 2: Calculate total: 48+24 = 72", "48+24=72"),
    ]
    nodes = convert_pairs_to_nodes(pairs)
    assert len(nodes) == 2

    # Step 1 produces v1 = 24 with no dependencies
    assert nodes[0].output_var == {"v1": "24"}
    assert nodes[0].deps == {}

    # Step 2 uses 24 from step 1, so deps should include v1 = 24!
    assert nodes[1].output_var == {"v2": "72"}
    assert nodes[1].deps == {"v1": "24"}


def test_convert_trace_to_msra_xml_validity():
    think_text = """
    Step 1: Calculate the cost: 3 * 3 = $9
    Calc: 3*3=9
    Step 2: Calculate total payment: 2 + 9 = $11
    Calc: 2+9=11
    """
    xml_str = convert_trace_to_msra_xml(think_text)
    assert xml_str is not None
    assert '<step id="1"' in xml_str
    assert '<step id="2"' in xml_str

    # Must pass strict DAG parse_trace validation with 0 errors
    result = parse_trace(xml_str)
    assert result.is_valid
    assert len(result.errors) == 0
    assert len(result.nodes) == 2


def test_convert_chatml_row():
    chatml = (
        "<|im_start|>user\nHow much is 10 + 20?<|im_end|>\n"
        "<|im_start|>assistant\n<think>\n"
        "Step 1: Calculate sum: 10 + 20 = 30\n"
        "Calc: 10+20=30\n"
        "</think>\n\nAnswer: 30<|im_end|>"
    )
    converted = convert_chatml_row(chatml)
    assert converted is not None
    assert "<step id=\"1\"" in converted
    assert "Answer: 30" in converted
    assert "<|im_start|>user\nHow much is 10 + 20?<|im_end|>" in converted


def test_convert_dataset_file_temp(tmp_path):
    input_file = tmp_path / "in.jsonl"
    output_file = tmp_path / "out.jsonl"

    row = {
        "text": (
            "<|im_start|>user\nWhat is 5*5?<|im_end|>\n"
            "<|im_start|>assistant\n<think>\n"
            "Step 1: Calculate product: 5*5 = 25\n"
            "Calc: 5*5=25\n"
            "</think>\n\nAnswer: 25<|im_end|>"
        )
    }
    input_file.write_text(json.dumps(row) + "\n", encoding="utf-8")

    stats = convert_dataset_file(input_file, output_file)
    assert stats["converted"] == 1
    assert stats["skipped"] == 0

    out_lines = output_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(out_lines) == 1
    out_obj = json.loads(out_lines[0])
    assert "<step id=\"1\"" in out_obj["text"]
