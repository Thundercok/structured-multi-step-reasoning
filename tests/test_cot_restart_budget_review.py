"""Cap support and item-level plateau guards, without inference."""

from scripts.review_cot_restart_budget import ARMS, cap_request, transition_rows


def test_d_plus8_requires_trace_even_if_an_early_eos_was_recorded():
    record = {"D_caps": {"0": 100, "1": 50}, "completion_cap": 100,
              "completion_tokens": 10, "finish_reason": "stop"}
    assert not cap_request(record, 0, 8)["available"]
    assert cap_request(record, 0, -8)["cap"] == 92
    assert cap_request(record, 1, 8)["available"]
    record["D_caps"]["1"] = 5
    assert not cap_request(record, 1, -8)["available"]


def test_same_total_correct_does_not_hide_opposite_item_transitions():
    indexed = {}
    for point in ("M", "D_w0"):
        for i in ("one", "two"):
            for arm in ARMS:
                correct = (i == "one") if point == "M" else (i == "two")
                indexed[point, i, arm] = {"correct": correct, "replay_cap": 20,
                                         "completion_tokens": 10, "finish_reason": "stop", "parse_status": "marker",
                                         "parsed_answer": "x", "full_response": "Answer: x"}
    rows = transition_rows({"indexed": indexed, "groups": {"one": "g1", "two": "g2"}})
    assert len(rows) == 6 and all(r["correctness_changed"] for r in rows)
    assert sum(r["M"]["correct"] for r in rows) == sum(r["D_w0"]["correct"] for r in rows)
