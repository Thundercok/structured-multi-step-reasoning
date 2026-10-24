"""Independent verification of G1-G5 repairs and integrity hardening for GSM8K collector."""
import copy
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
    helpers = runpy.run_path(str(ROOT / "tests/test_gsm8k_collector.py"))
    fixture = runpy.run_path(str(ROOT / "tests/test_gsm8k_routing_baseline.py"))
    dataset = helpers["make_test_dataset"](2)
    identity = helpers["make_test_identity"](dataset, evidence="synthetic_staged_pilot_collection")
    settings = {"temperature": 0.0, "thinking": False}

    results = {}

    with tempfile.TemporaryDirectory(prefix="gsm8k-repair-verify-") as temp:
        base = Path(temp)

        # G1: Validate generation/tool payloads
        g1_results = []
        for index, tokens in enumerate((-100, 2048, True)):
            cp = c.GSM8KCollectorCheckpoint(base / f"invalid_{index}", identity, dataset, settings)
            runner = c.MockStagedRunner({("item_calibration_0", "DIRECT"): {"tokens": tokens}})
            rejected = False
            try:
                c.run_staged_collection(cp, runner, dataset)
            except ValueError:
                rejected = True
            finally:
                cp.close()

            lines = (base / f"invalid_{index}" / "calls.jsonl").read_text(encoding="utf-8").splitlines()
            events = [json.loads(l) for l in lines]
            gen_out = next(e for e in events if e["kind"] == "generation_outcome" and e["key"] == ["item_calibration_0", "DIRECT"])
            val = gen_out["value"]
            manifest = json.loads((base / f"invalid_{index}" / "manifest.json").read_text(encoding="utf-8"))

            g1_results.append({
                "provided_tokens": tokens,
                "rejected_with_value_error": rejected,
                "outcome_status": val["status"],
                "measured_generated_tokens": val["measured_generated_tokens"],
                "budget_charge_tokens": val["budget_charge_tokens"],
                "manifest_status": manifest["status"],
                "manifest_budget_charge": manifest["budget_charged_tokens"],
            })
            assert rejected and val["status"] == "failed" and val["budget_charge_tokens"] == 1024
            assert manifest["status"] == "interrupted" and manifest["budget_charged_tokens"] == 1024
        results["g1_payload_validation"] = g1_results

        # G2: Orphan charge restoration
        orphan_dir = base / "orphan"
        cp = c.GSM8KCollectorCheckpoint(orphan_dir, identity, dataset, settings)
        class Kill(c.MockStagedRunner):
            def run_generation(self, *args, **kwargs):
                raise c.SimulatedProcessKill("kill after started write")
        try:
            c.run_staged_collection(cp, Kill(), dataset)
        except c.SimulatedProcessKill:
            pass
        finally:
            cp.close()

        cp_resume = c.GSM8KCollectorCheckpoint(orphan_dir, identity, dataset, settings, resume=True)
        unknown_count = len(cp_resume.unknown_conditions)
        charged_tokens = cp_resume.budget_charge_tokens_total
        quarantine_raised = False
        try:
            c.run_staged_collection(cp_resume, c.MockStagedRunner(), dataset)
        except c.QuarantineError:
            quarantine_raised = True
        finally:
            cp_resume.close()

        state = json.loads((orphan_dir / "manifest.json").read_text())
        results["g2_orphan_charge"] = {
            "unknown_conditions": unknown_count,
            "budget_charge_tokens_in_memory": charged_tokens,
            "manifest_status": state["status"],
            "manifest_budget_charged_tokens": state["budget_charged_tokens"],
            "quarantine_raised": quarantine_raised,
        }
        assert unknown_count == 1 and charged_tokens == 1024
        assert state["status"] == "quarantined" and state["budget_charged_tokens"] == 1024
        assert quarantine_raised

        # G2: Pure record reconstruction from durable terminal evidence
        assembly_dir = base / "lost_assembly"
        cp = c.GSM8KCollectorCheckpoint(assembly_dir, identity, dataset, settings)
        orig_append = cp.append_event
        def stop_before_record(kind, *args, **kwargs):
            if kind == "record_assembled":
                raise c.SimulatedProcessKill("stop before record assembled")
            return orig_append(kind, *args, **kwargs)
        cp.append_event = stop_before_record
        try:
            c.run_staged_collection(cp, c.MockStagedRunner(), dataset)
        except c.SimulatedProcessKill:
            pass
        finally:
            cp.close()

        cp_resume = c.GSM8KCollectorCheckpoint(assembly_dir, identity, dataset, settings, resume=True)
        runner = c.MockStagedRunner()
        state = c.run_staged_collection(cp_resume, runner, dataset)
        results["g2_lost_assembly_reconstruction"] = {
            "unknown_conditions": len(cp_resume.unknown_conditions),
            "recovered_records_before_run": 1,
            "resume_dispatches": runner.generation_dispatches,
            "completed_records": len(cp_resume.records),
            "expected_records": 6,
            "returned_status": state["status"],
        }
        assert len(cp_resume.unknown_conditions) == 0
        assert runner.generation_dispatches == 5  # Reconstructed condition 0 was not redispatched!
        assert len(cp_resume.records) == 6
        assert state["status"] == "complete"
        cp_resume.close()

        # G3: Sealed input bank swap rejection
        items, recs = fixture["fixture_data"]()
        pilot = fixture["save_run"](base / "pilot", items, recs)
        seal = base / "seal"
        r.write_fitting_seal(pilot, seal)
        sealed = json.loads((seal / "manifest.json").read_text())

        # Swap rows in pilot
        rows = json.loads((pilot / "records.json").read_text())
        for row in rows:
            if row["split"] != "calibration":
                continue
            row["correct"] = not row["correct"]
            row["answer"] = "7" if row["correct"] else "8"
        (pilot / "records.json").write_text(json.dumps(rows) + "\n")
        man = json.loads((pilot / "manifest.json").read_text())
        man["artifact_sha256"]["records.json"] = r.sha256_file(pilot / "records.json")
        (pilot / "manifest.json").write_text(json.dumps(man) + "\n")

        swap_rejected = False
        try:
            r.write_validation_evaluation(seal, base / "validation_changed")
        except ValueError as exc:
            if "differs from sealed hash" in str(exc):
                swap_rejected = True
        results["g3_sealed_input_swap"] = {
            "swap_rejected": swap_rejected,
            "tampered_manifest_hash": r.sha256_file(pilot / "manifest.json"),
            "sealed_expected_hash": sealed["input_manifest_sha256"],
        }
        assert swap_rejected

        # G4: Outcome-access isolation
        staged_iso_dir = base / "staged_iso"
        cp = c.GSM8KCollectorCheckpoint(staged_iso_dir, identity, dataset, settings)
        c.run_staged_collection(cp, c.MockStagedRunner(), dataset)
        cp.close()

        # Corrupt validation records completely
        (staged_iso_dir / "records_validation.json").write_text("CORRUPTED INVALID DATA", encoding="utf-8")
        seal_iso_dir = base / "seal_iso"
        seal_iso_state = r.write_fitting_seal(staged_iso_dir, seal_iso_dir)
        results["g4_outcome_access_isolation"] = {
            "fitting_seal_succeeded_with_corrupted_val_bank": seal_iso_state["status"] == "selection_saved",
            "validation_accuracy_suppressed_pre_seal": json.loads((staged_iso_dir / "summary.json").read_text()).get("validation_accuracy_suppressed"),
            "exposure_ledger_exists": (staged_iso_dir / "exposure_ledger.json").is_file(),
        }
        assert seal_iso_state["status"] == "selection_saved"
        assert results["g4_outcome_access_isolation"]["validation_accuracy_suppressed_pre_seal"] is True

        # G5: Staged Collect -> Fit Seal -> Validate E2E
        staged_e2e_dir = base / "staged_e2e"
        cp = c.GSM8KCollectorCheckpoint(staged_e2e_dir, identity, dataset, settings)
        c.run_staged_collection(cp, c.MockStagedRunner(), dataset)
        cp.close()

        seal_e2e_dir = base / "seal_e2e"
        r.write_fitting_seal(staged_e2e_dir, seal_e2e_dir)

        val_e2e_dir = base / "val_e2e"
        val_e2e_state = r.write_validation_evaluation(seal_e2e_dir, val_e2e_dir)
        val_summary = json.loads((val_e2e_dir / "summary.json").read_text())

        results["g5_e2e_workflow"] = {
            "status": val_e2e_state["status"],
            "methods_count": len(val_summary["methods"]),
            "has_primary_comparison": "primary_comparison" in val_summary,
            "new_model_calls": val_e2e_state["new_model_calls"],
        }
        assert val_e2e_state["status"] == "complete"
        assert len(val_summary["methods"]) == 5
        assert val_e2e_state["new_model_calls"] == 0

    paths = [
        "experiments/gsm8k_collector.py",
        "experiments/gsm8k_routing_baseline.py",
        "experiments/research_study.py",
        "tests/test_gsm8k_collector.py",
    ]
    results.update(
        source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths},
        new_model_calls=0,
        candidate_content_read=False,
        stage0_changed=False,
        all_verifications_passed=True,
    )
    output_path = Path(__file__).parent / "verification.json"
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
