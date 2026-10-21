"""Meaningful grouping, pairing and saved-artifact guards without inference."""

from pathlib import Path
import random

import numpy as np
import pytest

from experiments.cot_restart_pilot import file_sha256
from scripts.aggregate_cot_restart_matched import (
    ARMS, POINTS, aggregate, checked_files, compute_statistics, percentile,
)


def draws():
    groups = {"q1": "a", "q2": "a", "q3": "b"}
    results = []
    for seed_index in range(2):
        results.append([{"point": point, "question_id": identifier, "arm": arm,
                         "correct": arm == "F" and (identifier == "q3" or identifier == f"q{seed_index+1}"),
                         "completion_tokens": 10 + seed_index, "path_token_cost": 100 + seed_index,
                         "finish_reason": "stop", "parse_status": "marker", "replay_cap": 200}
                        for point in POINTS for identifier in groups for arm in ARMS])
    return results, groups


def test_question_average_and_group_bootstrap_keep_variants_and_do_not_inflate_n():
    rows, groups = draws()
    summary, means, distributions = compute_statistics(rows, groups, samples=200, seed=19)
    assert (summary["n_questions"], summary["n_original_groups"], summary["observed_draws"]) == (3, 2, 2)
    assert summary["points"]["M"]["arms"]["F"]["correct"] == pytest.approx(2/3)
    selected = {r["question_id"]: r["correct"] for r in means if r["point"] == "M" and r["arm"] == "F"}
    assert selected == {"q1": .5, "q2": .5, "q3": 1}
    # Independent direct calculation: a carries two questions, b carries one.
    rng = random.Random(19)
    expected = []
    for _ in range(200):
        sample = [rng.choice(["a", "b"]) for _ in range(2)]
        expected.append(2 / sum(2 if g == "a" else 1 for g in sample))
    assert distributions["M:F-A"]["correct"] == expected
    assert len(means) == len(POINTS) * len(ARMS) * 3
    contrast = next(c for c in summary["points"]["M"]["contrasts"] if (c["X"], c["Y"]) == ("F", "A"))
    assert contrast["correct"]["paired_group_percentile_95_ci"] == pytest.approx(np.quantile(expected, [.025, .975]))
    assert contrast["completion_tokens"]["delta"] == 0
    assert summary["M_questions_with_correctness_disagreement_between_draws"]["F"] == 2


def test_sensitivity_reuses_draws_has_no_intervals_and_preserves_all_questions():
    rows, groups = draws()
    rows[0][0]["correct"] = True  # A at M-8 changes on q1 without removing that question.
    summary, _, distributions = compute_statistics(rows, groups, samples=10)
    assert summary["unique_boundary_sensitive_questions"] == 1
    assert summary["n_questions"] == 3
    assert all(c["correct"]["paired_group_percentile_95_ci"] is None
               for c in summary["points"]["M_minus8"]["contrasts"])
    assert not any(key.startswith("M_minus8") for key in distributions)
    case = next(r for r in summary["sensitivity"] if r["question_id"] == "q1" and r["draw_index"] == 0)
    assert case["paired_differences"]["F-A"] == {"-8": 0, "0": 1, "8": 1}


@pytest.mark.parametrize("change", ["duplicate", "missing", "fractional"])
def test_incomplete_duplicate_or_nonbinary_draw_is_rejected(change):
    rows, groups = draws()
    if change == "duplicate":
        rows[1].append(rows[1][0])
    elif change == "missing":
        rows[1].pop()
    else:
        rows[1][0]["correct"] = .5
    with pytest.raises(ValueError):
        compute_statistics(rows, groups, samples=10)


def test_one_original_group_has_no_interval():
    rows, groups = draws()
    summary, _, distributions = compute_statistics(rows, {i: "single" for i in groups}, samples=10)
    assert summary["n_original_groups"] == 1
    assert all(c["correct"]["paired_group_percentile_95_ci"] is None for c in summary["points"]["M"]["contrasts"])
    assert distributions["M:F-A"] == {}


def test_percentile_matches_standard_linear_interpolation():
    values = [-1, -.5, 0, 0, .5, 1]
    assert [percentile(values, p) for p in [0, .025, .5, .975, 1]] == pytest.approx(np.quantile(values, [0, .025, .5, .975, 1]))


def test_changed_saved_artifact_and_path_escape_are_rejected(tmp_path):
    target = tmp_path / "replays.json"
    target.write_text("[]")
    hashes = {target.name: file_sha256(target)}
    assert checked_files(tmp_path, hashes, {target.name})
    target.write_text("[1]")
    with pytest.raises(ValueError, match="hash mismatch"):
        checked_files(tmp_path, hashes, {target.name})
    with pytest.raises(ValueError, match="within"):
        checked_files(tmp_path, {"../replays.json": hashes[target.name]}, set())


def test_existing_output_or_wrong_draw_count_fail_before_input_loading(tmp_path):
    with pytest.raises(ValueError, match="exactly draw"):
        aggregate([], tmp_path / "out")
    output = tmp_path / "existing"
    output.mkdir()
    with pytest.raises(ValueError, match="new directory"):
        aggregate([(Path("missing"),)*3]*2, output)
    assert list(output.iterdir()) == []
