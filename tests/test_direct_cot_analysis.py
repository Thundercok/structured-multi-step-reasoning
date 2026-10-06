import hashlib
import json

import pytest

from experiments import direct_cot_analysis as analysis
from experiments import research_pilot as pilot
from experiments import research_study as study


def read(directory, name):
    return json.loads((directory / name).read_text())


def collect_aligned_smoke(output):
    study.main([
        "--backend", "smoke", "--pilot", "--strategies", "DIRECT", "COT",
        "--prompt-profile", "aligned-direct-cot-v1", "--max-tokens", "512",
        "--output", str(output),
    ])


def rewrite_records_with_valid_hash(directory, mutate):
    records = read(directory, "records.json")
    mutate(records)
    study.write_json(directory / "records.json", records)
    manifest = read(directory, "manifest.json")
    manifest["artifact_sha256"]["records.json"] = hashlib.sha256(
        (directory / "records.json").read_bytes()
    ).hexdigest()
    study.write_json(directory / "manifest.json", manifest)


def test_analysis_replays_hashed_calibration_attempts_without_model_calls(tmp_path, monkeypatch):
    source, output = tmp_path / "pilot", tmp_path / "analysis"
    collect_aligned_smoke(source)
    source_manifest = (source / "manifest.json").read_bytes()

    def forbidden(*args, **kwargs):
        pytest.fail("DIRECT/CoT analysis must never call a model")

    monkeypatch.setattr(pilot.PilotSmokeBackend, "run", forbidden)
    study.main([
        "--direct-cot-analysis", str(source), "--direct-cot-budget", "512",
        "--lam", "0.02", "--output", str(output),
    ])

    manifest = read(output, "manifest.json")
    summary = read(output, "summary.json")
    results = read(output, "results.json")
    policy = read(output, "policy.json")
    dataset = read(source, "dataset.json")
    source_records = read(source, "records.json")
    calibration_ids = {item["id"] for item in dataset["items"] if item["split"] == "calibration"}

    assert manifest["status"] == "complete"
    assert manifest["development_only"] is True
    assert manifest["publication_ready"] is False
    assert manifest["policy_fitted"] is False
    assert manifest["evidence"] == "synthetic_smoke_analysis"
    assert manifest["source_manifest_sha256"] == hashlib.sha256(source_manifest).hexdigest()
    assert (source / "manifest.json").read_bytes() == source_manifest
    assert summary["evaluation_split"] == "calibration"
    assert summary["development_decision"]["status"] == "software_only"
    assert summary["manipulation_gate"]["valid"] is False
    assert summary["decision_settings"]["eligible"] is False
    assert {row["id"] for row in results} == calibration_ids
    assert {row["method"] for row in results} == set(analysis.METHODS)
    assert all(row["path"] in (["DIRECT"], ["COT"], ["DIRECT", "COT"]) for row in results)
    assert all(row["uses_gold_at_decision_time"] == (row["method"] == "oracle_direct_cot_utility") for row in results)
    assert policy["fit_split"] is None
    assert policy["uses_gold_at_runtime"] is False

    source_index = {(row["id"], row["strategy"]): row for row in source_records}
    for row in results:
        invoked = [source_index[row["id"], strategy] for strategy in row["path"]]
        assert row["generated_tokens"] == sum(source_row["tokens"] for source_row in invoked)
        assert row["prompt_tokens"] == sum(
            generation["prompt_tokens"]
            for source_row in invoked
            for generation in source_row["trace"]["generations"]
        )
        assert row["total_tokens"] == row["generated_tokens"] + row["prompt_tokens"]
    for name, digest in manifest["artifact_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest


def test_analysis_rejects_legacy_profile_and_tampered_artifacts_before_output(tmp_path):
    legacy = tmp_path / "legacy"
    study.main([
        "--backend", "smoke", "--pilot", "--strategies", "DIRECT", "COT",
        "--max-tokens", "512", "--output", str(legacy),
    ])
    rejected = tmp_path / "legacy-analysis"
    with pytest.raises(SystemExit):
        study.main(["--direct-cot-analysis", str(legacy), "--output", str(rejected)])
    assert not rejected.exists()

    aligned = tmp_path / "aligned"
    collect_aligned_smoke(aligned)
    (aligned / "records.json").write_text("[]\n")
    tampered = tmp_path / "tampered-analysis"
    with pytest.raises(SystemExit):
        study.main(["--direct-cot-analysis", str(aligned), "--output", str(tampered)])
    assert not tampered.exists()


@pytest.mark.parametrize("corruption", ["correctness", "parsed_answer", "evidence"])
def test_analysis_rejects_semantically_corrupt_rehashed_pilots(tmp_path, corruption):
    source = tmp_path / f"source-{corruption}"
    collect_aligned_smoke(source)
    if corruption == "correctness":
        rewrite_records_with_valid_hash(
            source, lambda records: records[0].__setitem__("correct", not records[0]["correct"]),
        )
    elif corruption == "parsed_answer":
        def corrupt_answer(records):
            records[0]["answer"] = "not-the-recorded-output"
            records[0]["correct"] = False
        rewrite_records_with_valid_hash(source, corrupt_answer)
    else:
        manifest = read(source, "manifest.json")
        manifest["evidence"] = "measured_development_pilot"
        study.write_json(source / "manifest.json", manifest)

    output = tmp_path / f"analysis-{corruption}"
    with pytest.raises(SystemExit):
        study.main(["--direct-cot-analysis", str(source), "--output", str(output)])
    assert not output.exists()


def record(strategy, *, correct, parse_status="marker", finish_reason="stop", tokens=10,
           prompt_tokens=2, output=None):
    answer = "right" if correct else "wrong"
    return {
        "strategy": strategy,
        "answer": answer,
        "correct": correct,
        "confidence": 0.5,
        "tokens": tokens,
        "strategy_ms": 1.0,
        "trace": {
            "parse_status": parse_status,
            "generations": [{
                "output": output if output is not None else f"Answer: {answer}",
                "tokens": tokens,
                "prompt_tokens": prompt_tokens,
                "finish_reason": finish_reason,
            }],
        },
    }


def test_fixed_policy_escalates_only_on_format_or_length_and_counts_both_calls():
    items = {
        "train": {"id": "train", "group_id": "train-group", "split": "train"},
        "stop": {"id": "stop", "group_id": "stop-group", "split": "calibration"},
        "rescue": {"id": "rescue", "group_id": "rescue-group", "split": "calibration"},
        "harm": {"id": "harm", "group_id": "harm-group", "split": "calibration"},
    }
    records = {
        ("train", "DIRECT"): record("DIRECT", correct=True),
        ("train", "COT"): record("COT", correct=True, output="Reason.\nAnswer: right"),
        ("stop", "DIRECT"): record("DIRECT", correct=True, tokens=11, prompt_tokens=3),
        ("stop", "COT"): record("COT", correct=False, tokens=21, prompt_tokens=4),
        ("rescue", "DIRECT"): record(
            "DIRECT", correct=False, parse_status="fail", finish_reason="length",
            tokens=12, prompt_tokens=3, output="unfinished",
        ),
        ("rescue", "COT"): record(
            "COT", correct=True, tokens=22, prompt_tokens=4,
            output="Reason.\nAnswer: right",
        ),
        ("harm", "DIRECT"): record(
            "DIRECT", correct=True, parse_status="fallback", tokens=13, prompt_tokens=3,
            output="right",
        ),
        ("harm", "COT"): record(
            "COT", correct=False, tokens=23, prompt_tokens=4,
            output="Reason.\nAnswer: wrong",
        ),
    }
    fixture = {
        "items": items,
        "records": records,
        "manifest": {"backend": "mlx"},
        "provenance_valid": True,
        "review_valid": True,
        "budget": 1024,
    }

    results = analysis.evaluate(fixture, 0.02)
    indexed = {(row["id"], row["method"]): row for row in results}
    assert indexed["stop", "direct_cot_format_or_length"]["path"] == ["DIRECT"]
    assert indexed["rescue", "direct_cot_format_or_length"]["path"] == ["DIRECT", "COT"]
    assert indexed["rescue", "direct_cot_format_or_length"]["trigger_reasons"] == ["answer_format", "length"]
    assert indexed["rescue", "direct_cot_format_or_length"]["total_tokens"] == 12 + 3 + 22 + 4
    assert indexed["harm", "direct_cot_format_or_length"]["path"] == ["DIRECT", "COT"]
    assert indexed["stop", "oracle_direct_cot_utility"]["path"] == ["DIRECT"]
    assert indexed["rescue", "oracle_direct_cot_utility"]["path"] == ["DIRECT", "COT"]

    summary = analysis.summarize(fixture, results, 0.02)
    complementarity = summary["direct_cot_complementarity"]
    assert complementarity == {
        "available_direct_wrong_cot_right": 1,
        "available_direct_right_cot_wrong": 2,
        "policy_rescue": 1,
        "policy_harm": 1,
    }
    assert summary["manipulation_gate"]["valid"] is False
    assert summary["development_decision"]["status"] == "invalid_manipulation"
    with pytest.raises(ValueError, match="Lambda"):
        analysis.evaluate(fixture, True)

    wordy = record("DIRECT", correct=False, parse_status="marker")
    wordy["trace"]["wordy"] = True
    assert analysis._direct_failure_reasons(wordy) == ["answer_format"]


def test_direct_cot_specific_cli_flags_are_isolated_from_collection(tmp_path):
    with pytest.raises(SystemExit):
        study.main([
            "--backend", "smoke", "--pilot", "--direct-cot-budget", "512",
            "--output", str(tmp_path / "bad-collection"),
        ])
    assert not (tmp_path / "bad-collection").exists()

    source = tmp_path / "source"
    collect_aligned_smoke(source)
    with pytest.raises(SystemExit):
        study.main([
            "--direct-cot-analysis", str(source), "--seed", "7",
            "--output", str(tmp_path / "bad-analysis"),
        ])
    assert not (tmp_path / "bad-analysis").exists()
