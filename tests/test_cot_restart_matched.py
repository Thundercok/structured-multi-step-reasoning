"""Bounded plan/runner acceptance without model weights or inference."""

import copy
import json

import pytest

from experiments.cot_restart_addendum import DEFAULT_HISTORICAL_DIR
from experiments.cot_restart_matched import build_plan, prepare_plan, read_plan, run_plan
from experiments.cot_restart_pilot import MockLLM
from experiments.cot_restart_replay import score_replay


def historical_inputs():
    root = DEFAULT_HISTORICAL_DIR
    return (json.loads((root / "dataset.json").read_text())["items"],
            json.loads((root / "base_traces.json").read_text()))


def test_matched_caps_cover_m_sensitivity_and_both_d_weights_without_gold_selection():
    items, bases = historical_inputs()
    tokenizer = MockLLM.MockTokenizer()
    plan = build_plan(items, bases, tokenizer)
    assert len(plan["requests"]) == 36
    assert len({(r["question_id"], r["arm"]) for r in plan["requests"]}) == 36
    for request in plan["requests"]:
        assert request["completion_cap"] >= request["M_cap"] + 8
        assert request["completion_cap"] >= max(request["D_caps"].values())
        assert min(request["D_caps"].values()) > 0
        assert len(request["prompt_token_ids"]) == request["prompt_tokens"]
    limits = plan["limits"]
    assert limits["max_completion_tokens"] == sum(r["completion_cap"] for r in plan["requests"])
    assert limits["max_prompt_plus_completion_tokens"] == sum(
        r["prompt_tokens"] + r["completion_cap"] for r in plan["requests"])
    poisoned_items, poisoned_bases = copy.deepcopy(items), copy.deepcopy(bases)
    for item in poisoned_items:
        item["answer"] = "GOLD_MUST_NOT_SELECT_BUDGET"
        poisoned_bases[item["id"]]["correct"] = not poisoned_bases[item["id"]]["correct"]
    assert build_plan(poisoned_items, poisoned_bases, tokenizer) == plan
    assert "GOLD_MUST_NOT_SELECT_BUDGET" not in json.dumps(plan)


def test_plan_and_mock_runner_collect_all_cells_and_replay_required_caps(tmp_path):
    prepared, output = tmp_path / "plan", tmp_path / "mock"
    plan = prepare_plan(prepared, tokenizer=MockLLM.MockTokenizer())
    assert read_plan(prepared)["plan_sha256"] == plan["plan_sha256"]
    manifest = run_plan(prepared, output, mock=True)
    assert manifest["status"] == "complete" and manifest["evidence"] == "synthetic_mock"
    assert manifest["executed_model_calls"] == 36
    records = json.loads((output / "records.json").read_text())
    assert manifest["total_incurred_tokens"] == sum(r["total_tokens"] for r in records)
    assert manifest["total_completion_tokens"] == sum(r["completion_tokens"] for r in records)
    items, _ = historical_inputs()
    by_id = {item["id"]: item for item in items}
    tokenizer = MockLLM.MockTokenizer()
    for record in records:
        for cap in [record["M_cap"] + s for s in (-8, 0, 8)] + list(record["D_caps"].values()):
            scored = score_replay(record, tokenizer, cap, by_id[record["question_id"]],
                                  prefix_text=record["prefix_text"])
            assert scored["completion_tokens"] <= cap
            assert scored["full_response"].startswith(record["prefix_text"])
    head = manifest["journal_head"]
    resumed = run_plan(prepared, output, mock=True)
    assert resumed["journal_head"] == head and resumed["executed_model_calls"] == 36


def test_real_generation_guard_and_plan_checksum_fail_before_output_creation(tmp_path):
    prepared, output = tmp_path / "plan", tmp_path / "forbidden"
    prepare_plan(prepared, tokenizer=MockLLM.MockTokenizer())
    with pytest.raises(ValueError, match="explicit approval"):
        run_plan(prepared, output)
    assert not output.exists()
    data = json.loads((prepared / "plan.json").read_text())
    data["limits"]["max_attempted_calls"] = 100
    (prepared / "plan.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="checksum"):
        read_plan(prepared)


def test_failed_attempt_consumes_budget_and_does_not_silently_add_retry_calls(tmp_path, monkeypatch):
    import experiments.cot_restart_matched as matched

    prepared, output = tmp_path / "plan", tmp_path / "failed"
    prepare_plan(prepared, tokenizer=MockLLM.MockTokenizer())
    real_execute = matched.execute_llm_call
    monkeypatch.setattr(matched, "execute_llm_call", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("injected abort")))
    with pytest.raises(RuntimeError, match="injected abort"):
        run_plan(prepared, output, mock=True)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["failed_attempts"] == 1 and manifest["total_attempted_calls"] == 1
    assert manifest["cost_status"] == "unknown_incurred"
    monkeypatch.setattr(matched, "execute_llm_call", real_execute)
    with pytest.raises(RuntimeError, match="ceiling"):
        run_plan(prepared, output, mock=True)
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["total_attempted_calls"] <= 36
    assert manifest["executed_model_calls"] < 36


def test_prefix_and_q_validation():
    items, bases = historical_inputs()
    with pytest.raises(ValueError, match="menu point"):
        build_plan(items, bases, MockLLM.MockTokenizer(), q_star=.6)
    tampered = copy.deepcopy(bases)
    tampered[items[0]["id"]]["prefix_menu"][2]["prefix"] += "injected final answer"
    with pytest.raises(ValueError, match="base trace"):
        build_plan(items, tampered, MockLLM.MockTokenizer())
