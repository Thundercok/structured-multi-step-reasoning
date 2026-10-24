"""Independent verification of H1-H3 repairs on authored fixtures."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments import gsm8k_collector as c
from experiments import gsm8k_routing_baseline as r


def main():
    helper = runpy.run_path(str(ROOT / "tests/test_gsm8k_collector.py"))
    ds = helper["make_test_dataset"](2)
    identity = helper["make_test_identity"](ds, evidence="synthetic_staged_pilot_collection")
    settings = {"temperature": 0.0, "thinking": False}
    output = {}

    with tempfile.TemporaryDirectory(prefix="gsm8k-h1-h3-repair-") as temp:
        base = Path(temp)

        # H1: Verify that mismatched dispatch arguments are rejected with 0 dispatches and 0 journal writes
        cp = c.GSM8KCollectorCheckpoint(base / "dispatch", identity, ds, settings)
        runner = c.MockStagedRunner({("item_calibration_0", "DIRECT"): {"tokens": 1500}})
        rejected_h1 = False
        try:
            c.run_staged_collection(cp, runner, ds, token_budget=2048, master_seed=999)
        except ValueError as exc:
            if "differs from pinned identity" in str(exc):
                rejected_h1 = True
        calls_content = (cp.directory / "calls.jsonl").read_text(encoding="utf-8").strip()
        manifest_h1 = json.loads((cp.directory / "manifest.json").read_text(encoding="utf-8"))

        output["h1_dispatch_binding"] = {
            "mismatch_rejected_with_value_error": rejected_h1,
            "runner_dispatches": runner.generation_dispatches,
            "journal_events_written": len(calls_content.splitlines()) if calls_content else 0,
            "manifest_calls_started": manifest_h1["calls_started"],
        }
        assert rejected_h1
        assert runner.generation_dispatches == 0
        assert calls_content == ""
        assert manifest_h1["calls_started"] == 0
        cp.close()

        # H3: Verify that full collection cost reports all 6 calls across fitting and validation
        bank_path = base / "bank"
        cp = c.GSM8KCollectorCheckpoint(bank_path, identity, ds, settings)
        responses = {
            ("item_calibration_0", "DIRECT"): {"tokens": 100},
            ("item_calibration_0", "COT"): {"tokens": 150},
            ("item_calibration_0", "PAL"): {"tokens": 200},
            ("item_train_0", "DIRECT"): {"tokens": 300},
            ("item_train_0", "COT"): {"tokens": 350},
            ("item_train_0", "PAL"): {"tokens": 400},
        }
        c.run_staged_collection(cp, c.MockStagedRunner(responses=responses), ds)
        cp.close()

        seal = base / "seal"
        r.write_fitting_seal(bank_path, seal)
        r.write_validation_evaluation(seal, base / "val")
        summary = json.loads((base / "val" / "summary.json").read_text(encoding="utf-8"))
        actual = json.loads((bank_path / "summary.json").read_text(encoding="utf-8"))

        output["h3_collection_cost_reporting"] = {
            "full_collection_generation_calls": summary["full_collection"]["generation_calls"],
            "actual_calls_completed": actual["calls_completed"],
            "full_collection_generated_tokens": summary["full_collection"]["generated_tokens"],
            "actual_generated_tokens": actual["measured_generated_tokens"],
            "validation_only_calls": summary["validation_only_collection"]["generation_calls"],
            "validation_only_tokens": summary["validation_only_collection"]["generated_tokens"],
            "fitting_only_calls": summary["fitting_only_collection"]["generation_calls"],
            "fitting_only_tokens": summary["fitting_only_collection"]["generated_tokens"],
            "costs_differ": summary["fitting_only_collection"]["generated_tokens"] != summary["validation_only_collection"]["generated_tokens"],
        }
        assert summary["full_collection"]["generation_calls"] == actual["calls_completed"] == 6
        assert summary["full_collection"]["generated_tokens"] == actual["measured_generated_tokens"] == 1500
        assert summary["validation_only_collection"]["generation_calls"] == 3
        assert summary["validation_only_collection"]["generated_tokens"] == 450
        assert summary["fitting_only_collection"]["generation_calls"] == 3
        assert summary["fitting_only_collection"]["generated_tokens"] == 1050

        # H2: Verify that relabeling a staged bank with non-synthetic evidence or bad hashes fails closed
        manifest = json.loads((bank_path / "manifest.json").read_text())
        manifest["identity"]["evidence"] = "measured_development_pilot"
        manifest["identity"]["source_hashes"] = {"authored_unverified_source": "not-a-sha256"}
        (bank_path / "manifest.json").write_text(json.dumps(manifest) + "\n")

        rejected_h2 = False
        try:
            r.write_fitting_seal(bank_path, base / "measured_seal")
        except ValueError as exc:
            if "Measured staged collection is deferred" in str(exc):
                rejected_h2 = True

        output["h2_measured_gate_enforcement"] = {
            "non_synthetic_staged_evidence_rejected": rejected_h2,
            "measured_seal_written": (base / "measured_seal").exists(),
        }
        assert rejected_h2
        assert not (base / "measured_seal").exists()

    paths = [
        "experiments/gsm8k_collector.py",
        "experiments/gsm8k_routing_baseline.py",
        "experiments/research_study.py",
        "tests/test_gsm8k_collector.py",
    ]
    output.update(
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        new_model_calls=0,
        candidate_content_read=False,
        stage0_changed=False,
        all_checks_passed=True,
    )
    out_file = Path(__file__).parent / "verification.json"
    out_file.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
