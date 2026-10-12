import copy
import hashlib
import json

import pytest

from experiments.research_study import smoke_dataset, validate_dataset
from research_identity import canonical_problem_id, digest, problem_fingerprint
from scripts.build_procedural_research_data import ROOT, build_release, main
from scripts.gen_tasks import render_arith, render_order


def arithmetic(identifier, start, split):
    meta = {"start": start, "steps": [["add", 1]]}
    return {"id": identifier, "group_id": identifier, "split": split, "family": "arith", "checker": "arith", "level": 1, "meta": meta, "query": render_arith(meta), "answer": str(start + 1)}


def ordering(identifier, names, split):
    meta = {"names": names, "clues": [["b", 0, 1], ["a", 1, 2], ["b", 2, 3]], "ask": 3}
    return {"id": identifier, "group_id": identifier, "split": split, "family": "order", "checker": "order", "level": 1, "meta": meta, "query": render_order(meta), "answer": names[-1]}


def legacy(items):
    return {"meta": {"seed": 0, "sha256_items": digest(items)}, "items": items}


def inputs():
    main_items = [arithmetic(str(n), n, split) for n, split in ((1, "dev"), (2, "calib"), (3, "dev"), (4, "test"), (5, "test"))]
    main_items += [ordering("o1", ["Alice", "Bob", "Carol", "Dave"], "dev"), ordering("o2", ["Erin", "Frank", "Grace", "Heidi"], "test")]
    tune_items = [arithmetic(f"t{n}", n, "test" if n == 4 else "dev") for n in (4, 10, 11)]
    return legacy(main_items), legacy(tune_items)


def test_migration_excludes_tuning_and_never_promotes_reviewed_development_to_test():
    main_input, tune_input = inputs()
    before = copy.deepcopy((main_input, tune_input))
    main_data, tune_data, checks = build_release(main_input, tune_input)
    assert (main_input, tune_input) == before
    assert checks["cross_release_problem_overlap"] == 0
    assert checks["excluded_main_items"][0]["original_id"] == "4"
    assert checks["development_promoted_to_test"] == 0
    assert checks["demoted_original_test_items"] == 1
    order_rows = [row for row in main_data["items"] if row["family"] == "order"]
    assert len({(row["group_id"], row["split"]) for row in order_rows}) == 1
    assert all(row["split"] != "test" for row in order_rows)
    assert [row["source_provenance"]["original_id"] for row in main_data["items"] if row["split"] == "test"] == ["5"]
    assert all(row["split"] != "test" for row in tune_data["items"])
    assert all(row["review_status"] == "unreviewed" for row in main_data["items"])
    with pytest.raises(ValueError, match="tuning pools"):
        validate_dataset(tune_data)
    poisoned = copy.deepcopy(tune_data)
    poisoned["items"][0]["split"] = "test"
    with pytest.raises(ValueError, match="exposed tuning"):
        validate_dataset(poisoned, require_all_splits=False)


def test_split_assignment_is_independent_of_input_order_and_gold_answers():
    main_input, tune_input = inputs()
    first = build_release(main_input, tune_input)
    reordered = copy.deepcopy(main_input)
    reordered["items"].reverse()
    reordered["meta"]["sha256_items"] = digest(reordered["items"])
    reordered_release = build_release(reordered, tune_input)
    assert reordered_release[0]["items"] == first[0]["items"]
    assert reordered_release[1:] == first[1:]
    poisoned = copy.deepcopy(main_input)
    for row in poisoned["items"]:
        row["answer"] = "999" if row["family"] == "arith" else "Zed"
    poisoned["meta"]["sha256_items"] = digest(poisoned["items"])
    again = build_release(poisoned, tune_input)
    assert [(row["id"], row["group_id"], row["split"]) for row in first[0]["items"]] == [(row["id"], row["group_id"], row["split"]) for row in again[0]["items"]]


def test_validation_catches_renamed_problems_even_with_distinct_legacy_groups():
    data = smoke_dataset()
    for n, split in enumerate(("train", "test")):
        row = ordering(f"o{n}", ["Alice", "Bob", "Carol", "Dave"] if n == 0 else ["Erin", "Frank", "Grace", "Heidi"], split)
        row["answer_type"] = "text"
        data["items"].append(row)
    with pytest.raises(ValueError, match="Canonical procedural problem crosses"):
        validate_dataset(data)


def test_canonical_identity_preserves_operations_multisets_and_asked_rank():
    row = arithmetic("x", 10, "dev")
    assert canonical_problem_id(row) == canonical_problem_id({**row, "answer": "wrong", "id": "different"})
    changed = copy.deepcopy(row)
    changed["meta"]["steps"].append(["mul", 2])
    assert canonical_problem_id(changed) != canonical_problem_id(row)
    a = {"family": "g24", "meta": {"numbers": [1, 2, 2, 6]}}
    b = {"family": "g24", "meta": {"numbers": [6, 2, 1, 2]}}
    assert problem_fingerprint(a) == problem_fingerprint(b)
    b["meta"]["numbers"] = [1, 2, 6, 6]
    assert problem_fingerprint(a) != problem_fingerprint(b)
    row = ordering("x", ["Alice", "Bob", "Carol", "Dave"], "dev")
    repeated = copy.deepcopy(row)
    repeated["meta"]["clues"].append(row["meta"]["clues"][0])
    assert canonical_problem_id(row) == canonical_problem_id(repeated)
    repeated["meta"]["ask"] = 0
    assert canonical_problem_id(row) != canonical_problem_id(repeated)


def test_gap_clues_preserve_offset_and_legacy_identity():
    row = ordering("x", ["Alice", "Bob", "Carol", "Dave"], "train")
    legacy_id = canonical_problem_id(row)
    four_fields = copy.deepcopy(row)
    four_fields["meta"]["clues"] = [clue + [1 if clue[0] == "a" else 0] for clue in row["meta"]["clues"]]
    assert canonical_problem_id(four_fields) == legacy_id
    four_fields["meta"]["clues"].append(["g", 0, 3, 3])
    first = canonical_problem_id(four_fields)
    four_fields["meta"]["clues"][-1][-1] = 2
    assert canonical_problem_id(four_fields) != first


def test_validator_rejects_false_ids_checker_and_metadata():
    main_data, _, _ = build_release(*inputs())
    for patch in ({"problem_id": "fake"}, {"checker": "g24"}, {"query": "Different puzzle"}, {"answer_type": "text"}, {"meta": {"start": True, "steps": [["add", 1]]}}):
        poisoned = copy.deepcopy(main_data)
        poisoned["items"][0].update(patch)
        with pytest.raises(ValueError):
            validate_dataset(poisoned)


def test_invalid_source_hash_and_stale_development_review_fail_before_release():
    main_input, tune_input = inputs()
    corrupted = copy.deepcopy(main_input)
    corrupted["items"][0]["query"] = "changed"
    with pytest.raises(ValueError, match="hash"):
        build_release(corrupted, tune_input)
    record = {"query_sha256": "wrong", "verified_answer": "2"}
    with pytest.raises(ValueError, match="review no longer matches"):
        build_release(main_input, tune_input, reviews={"main": {"1": record}, "tuning": {}})


def test_release_manifest_and_saved_candidate_are_reproducible_and_non_overwriting(tmp_path):
    output = tmp_path / "release"
    main(["--output", str(output)])
    manifest = json.loads((output / "manifest.json").read_text())
    for name, expected in manifest["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    with pytest.raises(FileExistsError):
        main(["--output", str(output)])
    saved = ROOT / "data/procedural_research_v1"
    if saved.exists():
        # Frozen data must reproduce; implementation hashes legitimately change
        # when the harness evolves. Preserve the historical manifest as evidence.
        for name in ("main.json", "tuning.json", "checks.json", "report.md"):
            assert (saved / name).read_bytes() == (output / name).read_bytes()
        saved_manifest = json.loads((saved / "manifest.json").read_text())
        assert saved_manifest["artifact_sha256"] == manifest["artifact_sha256"]
        assert saved_manifest["inputs"] == manifest["inputs"]
