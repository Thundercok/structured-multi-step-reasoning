import copy
import hashlib

import pytest

from scripts.prepare_development_pilot import solve_24, verify_item, verify_model
from experiments.research_pilot import local_model_metadata, verify_model_provenance
from experiments.research_study import write_json
from scripts.gen_tasks import check24, render_arith, render_g24


@pytest.mark.parametrize("numbers", [[1, 3, 4, 6], [3, 3, 8, 8], [1, 1, 1, 8], [10, 13, 2, 3]])
def test_independent_subset_solver_uses_every_operand_once(numbers):
    answer = solve_24(numbers)
    assert check24(answer, numbers)
    assert check24(solve_24(list(reversed(numbers))), numbers)


def test_unreachable_target_and_invalid_operands_are_rejected():
    with pytest.raises(ValueError, match="no exact solution"):
        solve_24([1, 1, 1, 1])
    with pytest.raises(ValueError, match="positive integer"):
        solve_24([1, 2, 3, 0])


def test_query_solution_is_independent_of_reference_and_poisoned_gold_is_rejected():
    meta = {"start": 64, "steps": [["add", 60], ["sub", 9]]}
    item = {"id": "arithmetic", "group_id": "group", "split": "train", "level": 1,
            "family": "arith", "query": render_arith(meta), "answer": "115",
            "answer_type": "number", "meta": meta, "source_provenance": {}}
    row = verify_item(item)
    assert row["independent_answer"] == "115"
    assert row["human_review_status"] == "pending"
    item["answer"] = "116"
    with pytest.raises(ValueError, match="Gold disagrees"):
        verify_item(item)


def test_reference_expression_cannot_reuse_or_replace_operands():
    item = {"id": "g24", "group_id": "group", "split": "calibration", "level": 1,
            "family": "g24", "meta": {"numbers": [1, 3, 4, 6]}, "answer_type": "text",
            "answer": "6/(1-(3/4))", "source_provenance": {}}
    item["query"] = render_g24(item["meta"])
    assert verify_item(item)["automated_verification"] == "pass"
    item["answer"] = "6*4"
    with pytest.raises(ValueError, match="violates numbers"):
        verify_item(item)


def test_model_verification_checks_actual_content_including_git_blob_prefix(tmp_path):
    config = b'{"fixture": true}'
    weights = b"synthetic weights never loaded"
    (tmp_path / "config.json").write_bytes(config)
    (tmp_path / "model.safetensors").write_bytes(weights)
    metadata = {"id": "mlx-community/Qwen3-8B-4bit", "sha": "fixture-revision", "siblings": [
        {"rfilename": "config.json", "size": len(config), "blobId": hashlib.sha1(f"blob {len(config)}\0".encode()+config).hexdigest()},
        {"rfilename": "model.safetensors", "size": len(weights), "lfs": {"sha256": hashlib.sha256(weights).hexdigest()}},
    ]}
    verified = verify_model(tmp_path, metadata)
    assert verified["local_content_matches_upstream_revision"] is True
    assert verified["model_loaded"] is False
    model, hashes = local_model_metadata(str(tmp_path))
    path = tmp_path.parent / (tmp_path.name + "-provenance.json")
    write_json(path, verified)
    assert verify_model_provenance(path, model, hashes)["revision"] == "fixture-revision"
    with pytest.raises(ValueError, match="actual local model content"):
        verify_model_provenance(path, model, {**hashes, "model.safetensors": "0"*64})
    poisoned = copy.deepcopy(metadata)
    poisoned["siblings"][0]["blobId"] = hashlib.sha1(config).hexdigest()
    with pytest.raises(ValueError, match="content differs"):
        verify_model(tmp_path, poisoned)
    (tmp_path / "model.safetensors").write_bytes(b"x"*len(weights))
    with pytest.raises(ValueError, match="content differs"):
        verify_model(tmp_path, metadata)
