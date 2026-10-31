from pathlib import Path

import pytest

from experiments.think_on_demand_replay import load_frozen_run11


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "gen02_tune.json"


def test_frozen_loader_rejects_any_other_trace(tmp_path):
    changed = tmp_path / "changed.jsonl"
    changed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="only the frozen Run 11 trace"):
        load_frozen_run11(changed, DATASET)
