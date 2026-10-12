import hashlib
import json
from pathlib import Path

import pytest

from experiments.think_on_demand_replay import (
    GEN02_TUNE_SHA256,
    RUN11_TRACE_SHA256,
    load_frozen_run11,
    replay_rows,
    summarize,
    write_analysis,
)


ROOT = Path(__file__).resolve().parents[1]
TRACE = ROOT / "audit" / "run11_sweep_trace.jsonl"
DATASET = ROOT / "data" / "gen02_tune.json"


@pytest.fixture(scope="module")
def frozen_source():
    return load_frozen_run11(TRACE, DATASET)


def test_frozen_artifact_hashes_and_factorial_are_revalidated(frozen_source):
    assert hashlib.sha256(TRACE.read_bytes()).hexdigest() == RUN11_TRACE_SHA256
    assert hashlib.sha256(DATASET.read_bytes()).hexdigest() == GEN02_TUNE_SHA256
    assert len(frozen_source["rows"]) == 571
    assert len(frozen_source["by_key"]) == 571
    assert len(frozen_source["checker_disagreements"]) == 8
    assert {row["arm"] for row in frozen_source["checker_disagreements"]} == {"SC"}


def test_replay_reproduces_headline_and_fail_closed_sensitivity(frozen_source):
    results = replay_rows(frozen_source, 0.02)
    summary = summarize(results, 0.02, repetitions=200)

    cot = summary["methods"]["fixed_cot"]
    assert cot["correct"] == 44
    assert cot["mean_logged_token_proxy"] == pytest.approx(483.1267605634)

    adaptive = summary["methods"]["posthoc_think_on_demand_fail_open"]
    assert adaptive["correct"] == 62
    assert adaptive["accuracy"] == pytest.approx(62 / 71)
    assert adaptive["mean_logged_token_proxy"] == pytest.approx(1021.0563380282)
    assert adaptive["mean_utility"] == pytest.approx(0.8528183099)
    assert adaptive["escalations"] == 20
    assert adaptive["rescues_vs_cot"] == 19
    assert adaptive["harms_vs_cot"] == 1

    fail_closed = summary["methods"]["posthoc_think_on_demand_fail_closed"]
    assert fail_closed["correct"] == 61
    assert fail_closed["mean_logged_token_proxy"] == pytest.approx(1100.1830985915)
    assert fail_closed["escalations"] == 23
    assert fail_closed["rescues_vs_cot"] == 19
    assert fail_closed["harms_vs_cot"] == 2


def test_frozen_loader_rejects_any_other_trace(tmp_path):
    changed = tmp_path / "changed.jsonl"
    changed.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="only the frozen Run 11 trace"):
        load_frozen_run11(changed, DATASET)


def test_writer_hashes_outputs_and_never_overwrites(tmp_path):
    output = tmp_path / "analysis"
    summary = write_analysis(
        TRACE, DATASET, output, 0.02, _bootstrap_repetitions=100,
    )
    assert summary["evidence_status"] == "exposed_development_posthoc_replay_only"
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "complete"
    assert manifest["model_calls"] is False
    assert manifest["uses_held_out_data"] is False
    assert manifest["source_trace_sha256"] == RUN11_TRACE_SHA256
    for name, expected in manifest["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected

    with pytest.raises(ValueError, match="Output already exists"):
        write_analysis(TRACE, DATASET, output, 0.02, _bootstrap_repetitions=10)
