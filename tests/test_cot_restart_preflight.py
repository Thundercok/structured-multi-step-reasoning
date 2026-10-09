import copy
import hashlib
import json

import pytest

from scripts.gen_tasks import render_arith
from scripts.prepare_cot_restart import (
    DATASET, MENU, TRACE, analyze, canonical_folds, main, make_menu,
    reasoning_prefix, sentence_boundaries,
)


def fixture():
    meta = {"start": 10, "steps": [["add", 2], ["mul", 3]]}
    item = {"id": "a", "group_id": "a", "family": "arith", "level": 1,
            "split": "dev", "meta": meta, "query": render_arith(meta), "answer": "36"}
    row = {"id": "a", "group_id": "a", "family": "arith", "level": 1,
           "arm": "COT", "gold": "36", "correct": True, "finish_reason": "stop",
           "raw_output": "Start at ten. Add two. Multiply by three. Answer follows.\nAnswer: 36",
           "prompt_tokens": 15, "completion_tokens": 20}
    return [row], [item]


def test_checkpoint_prefixes_are_exact_and_have_no_final_answer_or_gold_lookup():
    raw = "Read the facts. Add two. Multiply by three. Check the result.\n**Answer: 36**"
    info, menu = make_menu(raw, len)
    assert info["explicit_answer_marker_count"] == 1
    assert [r["q_requested"] for r in menu] == list(MENU)
    for row in menu:
        assert row["prefix"] == raw[:row["cut_char"]]
        assert "Answer:" not in row["prefix"]
        assert hashlib.sha256(row["prefix"].encode()).hexdigest() == row["prefix_sha256"]
        assert 0 <= row["q_actual_retokenized"] < 1


def test_conservative_boundaries_skip_decimals_list_labels_abbreviations_and_code():
    body = '1. Dr. Bob computes 3.14. Next sentence!\n```python\nx = 1.2\nprint("bad.")\n```\nFinish.'
    points = sentence_boundaries(body)
    assert points[0] == 0
    assert 2 not in points
    assert not any(body[:point].endswith("Dr.") for point in points)
    assert all(not (body.index("```") <= point <= body.rindex("```")) for point in points)
    assert body.index("3.14.") + len("3.14.") in points
    assert len(body) not in points


def test_short_trace_collapses_menu_and_does_not_invent_steps():
    info, menu = make_menu("One sentence.\nAnswer: 36", len)
    assert info["distinct_menu_prefixes"] == 1
    assert info["interior_boundary_count"] == 0
    assert all(row["cut_char"] == 0 for row in menu)


def test_first_answer_block_is_removed_and_multiple_blocks_flagged():
    body, end, count = reasoning_prefix("Compute it.\nAnswer: 35\nRetry.\nAnswer: 36")
    assert body == "Compute it." and end == len(body) and count == 2


def test_outcomes_do_not_change_checkpoint_positions_or_group_folds():
    records, items = fixture()
    before = copy.deepcopy((records, items))
    summary, observations, checkpoints = analyze(records, items, len)
    changed = copy.deepcopy(records)
    changed[0]["correct"] = False
    other = analyze(changed, items, len)[2]
    assert checkpoints == other
    assert (records, items) == before
    assert summary["cot_traces"] == 1 and summary["checkpoint_rows"] == 4
    assert summary["model_calls"] == 0 and not summary["repair_values_measured"]
    assert all(set(row["model_input"]) == {"query", "prefix"} for row in checkpoints)
    assert observations[0]["retrospective_typed_correct"]


def test_truncated_correct_trace_keeps_denominator_and_truncation_flag():
    records, items = fixture()
    records[0]["finish_reason"] = "length"
    summary, observations, checkpoints = analyze(records, items, len)
    assert summary["cot_traces"] == 1 and len(checkpoints) == 4
    assert observations[0]["retrospective_typed_correct"]
    assert observations[0]["failure_profile"] == "truncation"
    assert not observations[0]["checkpoint_review_candidate"]


def test_repeated_canonical_questions_share_fold_despite_different_ids():
    _, items = fixture()
    duplicate = copy.deepcopy(items[0])
    duplicate.update(id="b", group_id="b", split="test")
    folds = canonical_folds(items + [duplicate])
    assert folds["a"] == folds["b"]


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "gold", "tokens", "finish"])
def test_rejects_inconsistent_source_records(mutation):
    records, items = fixture()
    if mutation == "duplicate":
        records.append(copy.deepcopy(records[0]))
    elif mutation == "missing":
        records.clear()
    elif mutation == "gold":
        records[0]["gold"] = "999"
    elif mutation == "tokens":
        records[0]["completion_tokens"] = -1
    else:
        records[0]["finish_reason"] = "unknown"
    with pytest.raises(ValueError):
        analyze(records, items, len)


def test_cost_proxy_counts_all_four_selection_and_evaluation_points():
    records, items = fixture()
    _, observations, checkpoints = analyze(records, items, len)
    row = observations[0]
    assert row["dense_matrix_completion_proxy_ms4_me4"] == 8 * sum(c["remaining_body_token_proxy"] for c in checkpoints)
    assert row["dense_matrix_input_proxy_ms4_me4"] == 8 * sum(15 + c["prefix_retokenized_tokens"] for c in checkpoints)


def test_existing_output_is_refused_before_any_inputs_are_read(tmp_path, monkeypatch):
    import scripts.prepare_cot_restart as module

    monkeypatch.setattr(module, "sha256_file", lambda _: pytest.fail("Inputs should not be read"))
    with pytest.raises(FileExistsError):
        main(["--output", str(tmp_path)])


def test_cpu_preflight_real_inputs_produce_hashed_development_only_artifacts(tmp_path):
    pytest.importorskip("tokenizers")
    output = tmp_path / "preflight"
    main(["--output", str(output)])
    manifest = json.loads((output / "manifest.json").read_text())
    summary = json.loads((output / "summary.json").read_text())
    observations = json.loads((output / "observations.json").read_text())
    checkpoints = [json.loads(line) for line in (output / "checkpoints.jsonl").read_text().splitlines()]
    source = [json.loads(line) for line in TRACE.read_text().splitlines()]
    by_id = {item["id"]: item for item in json.loads(DATASET.read_text())["items"]}
    assert summary["cot_traces"] == 100 and summary["source_records"] == 571
    assert summary["historical_correct"] == 58 and len(checkpoints) == 400
    assert summary["failure_profile"]["truncation"] == 23
    assert manifest["model_calls"] == 0 and not manifest["uses_held_out_data"]
    assert not manifest["future_model_execution_authorized"] and not manifest["stage0_changed"]
    assert {r["development_fold"] for r in observations} == {"dev_fit", "dev_eval"}
    assignments = {}
    for row in observations:
        assert assignments.setdefault(row["canonical_group_id"], row["development_fold"]) == row["development_fold"]
    assert len({row["checkpoint_id"] for row in checkpoints}) == 400
    for row in checkpoints:
        original = source[row["source_line"] - 1]
        payload = row["model_input"]
        assert original["arm"] == "COT" and original["id"] == row["id"]
        assert payload["prefix"] == original["raw_output"][:row["cut_char"]]
        assert payload["query"] == by_id[row["id"]]["query"]
        assert set(payload) == {"prefix", "query"}
        assert hashlib.sha256(payload["prefix"].encode()).hexdigest() == row["prefix_sha256"]
        assert hashlib.sha256(original["raw_output"].encode()).hexdigest() == row["source_raw_output_sha256"]
    for name, expected in manifest["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    with pytest.raises(FileExistsError):
        main(["--output", str(output)])
