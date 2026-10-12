import copy
import json

import pytest

from experiments.research_study import main as collect
from scripts.summarize_development_pilot import main, paired, validate_records


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    folder = tmp_path_factory.mktemp("paired-pilot")
    collect(["--backend", "smoke", "--pilot", "--output", str(folder / "run")])
    return folder / "run"


def test_paired_diagnostics_use_original_questions_and_correct_discordance(smoke, tmp_path):
    output = tmp_path / "analysis"
    main(["--run", str(smoke), "--output", str(output)])
    summary = json.loads((output / "summary.json").read_text())
    both_low = next(row for row in summary["paired_strategy_differences"] if row["family"] == "all" and row["cap_per_call"] == 96)
    assert both_low["items"] == 48 and both_low["groups"] == 24
    assert both_low["both_incorrect"] == 48
    assert both_low["both_correct"] == both_low["became_correct"] == both_low["became_incorrect"] == 0
    for row in summary["paired_strategy_differences"] + summary["paired_cap_differences"]:
        assert sum(row[key] for key in ("both_correct", "both_incorrect", "became_correct", "became_incorrect")) == row["items"]
    assert summary["policy_fitted"] is False
    with pytest.raises(FileExistsError):
        main(["--run", str(smoke), "--output", str(output)])


@pytest.mark.parametrize("field", ["correct", "answer", "tokens", "group_id"])
def test_analysis_rejects_inconsistent_record_even_if_saved_hash_were_updated(smoke, field):
    dataset = json.loads((smoke / "dataset.json").read_text())
    rows = copy.deepcopy(json.loads((smoke / "records.json").read_text()))
    if field == "correct": rows[0][field] = not rows[0][field]
    elif field == "tokens": rows[0][field] += 1
    else: rows[0][field] = "inconsistent"
    with pytest.raises(ValueError):
        validate_records(dataset, rows)


def test_pairing_rejects_missing_or_duplicate_question_ids():
    with pytest.raises(ValueError, match="identical, unique"):
        paired([{"id": "a"}], [{"id": "b"}])
