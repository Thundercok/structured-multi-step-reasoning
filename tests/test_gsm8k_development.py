import copy

import pytest

from scripts.prepare_gsm8k_development import build_items, parse_gold
from experiments.research_study import validate_dataset


def test_training_selection_does_not_depend_on_answers_and_groups_do_not_cross_splits():
    rows = [{"question": f"A child has {i} books. How many books?", "answer": f"#### {i}"} for i in range(1, 31)]
    items, _, selection = build_items(rows, "pinned-fixture", 24, 42)
    poisoned = copy.deepcopy(rows)
    for row in poisoned:
        row["answer"] = "#### 9999"
    repeated, _, second = build_items(poisoned, "pinned-fixture", 24, 42)
    assert selection == second
    assert [(r["id"], r["group_id"], r["split"]) for r in items] == [(r["id"], r["group_id"], r["split"]) for r in repeated]
    assert sum(r["split"] == "train" for r in items) == 12
    assert sum(r["split"] == "calibration" for r in items) == 12
    assert len({r["group_id"] for r in items}) == 24
    assert all(r["source_provenance"]["original_split"] == "train" for r in items)
    dataset = {"name": "fixture", "version": "1", "source": "fixture", "license": "fixture",
               "role": "development_tuning", "items": items}
    validate_dataset(dataset, pilot=True)
    with pytest.raises(ValueError, match="tuning pools"):
        validate_dataset(dataset)


@pytest.mark.parametrize("invalid", ["#### 1,2", "#### 2 or 3", "#### 1\n#### 2", "#### NaN", "no delimiter"])
def test_gold_extraction_rejects_ambiguous_or_partial_numbers(invalid):
    with pytest.raises(ValueError):
        parse_gold(invalid)


def test_gold_extraction_preserves_numeric_value():
    assert parse_gold("Worked solution\n#### 12,345") == "12345"
    assert parse_gold("Worked solution\n#### -2.50") == "-2.5"


def test_new_development_sample_excludes_exposed_queries_and_keeps_original_source_lines():
    import hashlib
    from experiments.research_study import normalized_text
    rows = [{"question": f"A child has {i} books. How many books?", "answer": f"#### {i}"} for i in range(1, 101)]
    old, _, _ = build_items(rows, "pinned-fixture", 24, 42)
    identities = {hashlib.sha256(normalized_text(item["query"]).encode()).hexdigest() for item in old}
    new, _, selection = build_items(rows, "pinned-fixture", 48, 42, exclude_identities=identities)
    assert not {item["group_id"] for item in old} & {item["group_id"] for item in new}
    assert selection["excluded_normalized_queries"] == 24
    assert len(new) == 48
    for item in new:
        source_line = item["source_provenance"]["line_1based"]
        assert item["id"] == f"gsm8k-dev-{source_line:05d}"
        assert rows[source_line - 1]["question"] == item["query"]
    poisoned = copy.deepcopy(rows)
    for row in poisoned:
        row["answer"] = "#### 9999"
    repeated, _, _ = build_items(poisoned, "pinned-fixture", 48, 42, exclude_identities=identities)
    assert [(r["group_id"], r["split"]) for r in new] == [(r["group_id"], r["split"]) for r in repeated]
