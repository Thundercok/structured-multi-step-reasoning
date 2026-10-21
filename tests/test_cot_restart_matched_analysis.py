"""Paired inference/report guards; deterministic CPU checks only."""

import json

import pytest

from scripts.analyze_cot_restart_matched import audit_records, nominal_tango_ci, paired_summary


def test_supplied_tango_fixture_and_degenerate_boundaries():
    assert nominal_tango_ci(4, 0, 12) == pytest.approx([0.0100079911, 0.6093779111])
    positive = nominal_tango_ci(12, 0, 12)
    negative = nominal_tango_ci(0, 12, 12)
    assert positive[1] == 1 and negative[0] == -1
    assert negative == pytest.approx([-positive[1], -positive[0]])
    lo, hi = nominal_tango_ci(0, 0, 12)
    assert lo < 0 < hi and lo == pytest.approx(-hi)
    with pytest.raises(ValueError, match="invalid"):
        nominal_tango_ci(8, 5, 12)


def rows():
    values = {"A": (True, False, False), "F": (False, True, False), "CONT": (True, True, True)}
    return [{"question_id": f"q{i}", "arm": arm, "correct": correct,
             "completion_tokens": 10, "path_token_cost": 100}
            for arm, outcomes in values.items() for i, correct in enumerate(outcomes)]


def test_same_accuracy_different_paired_discordance_is_reported():
    summary = paired_summary(rows(), intervals=True)
    assert summary["arms"]["A"]["accuracy"] == summary["arms"]["F"]["accuracy"] == 1 / 3
    contrasts = {(r["X"], r["Y"]): r for r in summary["contrasts"]}
    assert (contrasts[("F", "A")]["b"], contrasts[("F", "A")]["c"]) == (1, 1)
    assert contrasts[("F", "A")]["delta"] == 0
    assert contrasts[("CONT", "A")]["delta"] == 2 / 3
    assert contrasts[("F", "CONT")]["delta"] == -2 / 3


def test_sensitivity_has_no_extra_interval_and_rejects_missing_or_duplicate_pairs():
    assert all(r["nominal_tango_95_ci"] is None for r in paired_summary(rows(), intervals=False)["contrasts"])
    with pytest.raises(ValueError, match="same questions"):
        paired_summary(rows()[:-1], intervals=False)
    with pytest.raises(ValueError, match="duplicate"):
        paired_summary(rows() + [rows()[0]], intervals=False)


def test_synthetic_or_incomplete_runs_cannot_enter_real_analysis(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "complete", "mock": True}))
    with pytest.raises(ValueError, match="completed real"):
        audit_records(tmp_path, {})
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "running", "mock": False}))
    with pytest.raises(ValueError, match="completed real"):
        audit_records(tmp_path, {})
