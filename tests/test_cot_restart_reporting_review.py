"""Strata decomposition and exact sign-flip diagnostics without model calls."""

import pytest

from scripts.review_cot_restart_reporting import INTERVAL_POINTS, sign_flip, strata_tables


def test_strata_reconstruct_total_pair_effect_and_keep_fixed_o():
    base = {"right1": True, "right2": True, "wrong1": False, "wrong2": False}
    values = {"A": [False, True, False, True], "F": [True, True, True, False], "CONT": [True, True, False, False]}
    rows = [{"point": point, "question_id": i, "arm": arm, "correct": correct}
            for point in INTERVAL_POINTS for arm, outcomes in values.items() for i, correct in zip(base, outcomes)]
    tables = strata_tables(rows, base)
    chosen = [next(c for c in t["contrasts"] if (c["X"], c["Y"]) == ("F", "A")) for t in tables if t["point"] == "M"]
    assert [(c["b"], c["c"]) for c in chosen] == [(1, 0), (1, 1)]
    assert sum(c["contribution_to_all_question_delta"] for c in chosen) == .25
    assert next(t for t in tables if t["point"] == "M" and t["stratum"] == "base_correct")["correct"]["O"] == 2
    assert next(t for t in tables if t["point"] == "M" and t["stratum"] == "base_wrong")["correct"]["O"] == 0
    with pytest.raises(ValueError, match="duplicate"):
        strata_tables(rows+[rows[0]], base)


def test_exhaustive_sign_flip_preserves_zero_groups_and_two_sided_ties():
    result = sign_flip([1, 1], 2)
    assert result["assignments"] == 4 and result["two_sided_p"] == .5
    with_zeros = sign_flip([1, 1]+[0]*10, 12)
    assert with_zeros["assignments"] == 4096 and with_zeros["two_sided_p"] == .5
    assert sign_flip([0, 0], 2)["two_sided_p"] == 1
    assert sign_flip([-1, -1], 2)["two_sided_p"] == .5
    with pytest.raises(ValueError, match="half-integer"):
        sign_flip([.3], 1)
