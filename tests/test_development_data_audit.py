import copy
import json
from pathlib import Path

import pytest

from scripts.audit_development_data import ROOT, apply_curated_review, audit_dataset, digest, isolation_checks, problem_fingerprint, solve_procedural_query


def test_development_audit_verifies_all_development_rows_and_retains_blinded_test_hashes():
    review = json.loads((ROOT / "audit/development_data_review.json").read_text())
    baseline = json.loads((ROOT / "audit/development_audit_baseline.json").read_text())
    counts = []
    for record in baseline["datasets"]:
        output = audit_dataset(ROOT / record["path"], review)
        assert output["held_out_rows_sha256"] == record["held_out_rows_sha256"]
        assert all(row["split"] != "test" for row in output["development_outcomes"])
        counts.append(output["development_items_verified"])
    assert counts == [54, 108, 60]


def test_review_cannot_patch_held_out_items():
    dataset = json.loads((ROOT / "data/nckh_reasoning_dataset_draft.json").read_text())
    review = json.loads((ROOT / "audit/development_data_review.json").read_text())
    held = next(row for row in dataset["items"] if row["split"] == "test")
    review["item_corrections"][held["id"]] = {"query": "forbidden replacement"}
    with pytest.raises(ValueError, match="only reviewed development"):
        apply_curated_review(copy.deepcopy(dataset), review)


def test_builder_reproduces_reviewed_draft_and_held_out_rows_exactly():
    from scripts.build_nckh_dataset import build_dataset
    saved = json.loads((ROOT / "data/nckh_reasoning_dataset_draft.json").read_text())
    generated = build_dataset()
    assert digest(generated) == digest(saved)


def test_semantic_review_is_invalidated_by_changed_development_wording():
    dataset = json.loads((ROOT / "data/nckh_reasoning_dataset_draft.json").read_text())
    review = json.loads((ROOT / "audit/development_data_review.json").read_text())
    next(row for row in dataset["items"] if row["split"] == "train")["query"] += " Changed assumption."
    path = ROOT / "runs" / "unused-development-audit.json"
    # The reader can operate on an isolated path without writing any project data.
    from unittest.mock import patch
    with patch.object(Path, "read_text", return_value=json.dumps(dataset)):
        with pytest.raises(ValueError, match="semantically reviewed text"):
            audit_dataset(path, review)


def test_query_solver_rejects_nonunique_order_and_invalid_reference():
    with pytest.raises(ValueError, match="unique"):
        solve_procedural_query({"family": "order", "query": "4 runners (Alice, Bob, Carol, Dave) ran a race with no ties. Clues: Alice finished before Bob. Who finished in 4th place?"})
    with pytest.raises(ValueError, match="violates"):
        solve_procedural_query({"family": "g24", "query": "Using each of the numbers 10, 13, 2 and 3 exactly once, write an expression that equals 24.", "answer": "24"})


def test_name_permutations_and_clue_order_do_not_create_independent_problems():
    first = {"family": "order", "split": "dev", "meta": {"names": ["Alice", "Bob", "Carol"], "clues": [["b", 0, 1], ["a", 1, 2]], "ask": 2}}
    renamed = {"family": "order", "split": "test", "meta": {"names": ["Erin", "Frank", "Dave"], "clues": [["a", 2, 0], ["b", 1, 2]], "ask": 2}}
    assert problem_fingerprint(first) == problem_fingerprint(renamed)
    result = isolation_checks([first, renamed])
    assert result["problem_classes_crossing_splits"] == 1
    assert result["items_in_crossing_problem_classes"] == 2
    renamed["meta"]["ask"] = 0
    assert problem_fingerprint(first) != problem_fingerprint(renamed)


def test_metadata_cannot_hide_a_different_arithmetic_instance():
    item = {"family": "arith", "query": "A counter starts at 59. Apply these steps in order: (1) multiply the result by 2; (2) subtract 66. What is the final value of the counter?", "meta": {"start": 59, "steps": [["mul", 2], ["sub", 66]]}}
    assert solve_procedural_query(item)[0] == "52"
    item["meta"]["start"] = 60
    with pytest.raises(ValueError, match="metadata differs"):
        solve_procedural_query(item)
