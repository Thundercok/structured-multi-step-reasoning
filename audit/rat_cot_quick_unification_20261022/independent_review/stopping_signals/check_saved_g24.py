"""Inspect public answers in eight exposed development outputs; no collection."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from scripts.verifiers import verify_g24_rationale

OUT = Path(__file__).resolve().parent
RUN = ROOT / "audit/development-pilot-measured-20261004-runtimefix"
RECORDS_SHA256 = "1b1a79624c8b605627c6cb002fc473b62389f3da7700c39415772d62e7b4a3f0"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((RUN / "manifest.json").read_text())
    assert manifest["evidence"] == "measured_development_pilot"
    expected = manifest["artifact_sha256"]
    assert expected["records.json"] == RECORDS_SHA256
    assert all(sha(RUN / name) == digest for name, digest in expected.items())
    sources = {p: sha(ROOT / p) for p in ("scripts/verifiers.py", "scripts/gen_tasks.py")}
    dataset = json.loads((RUN / "dataset.json").read_text())
    assert {item["split"] for item in dataset["items"]} <= {"train", "calibration"}
    # Golds/solutions are not passed into the checker; retain only declared inputs.
    numbers = {item["id"]: list(item["meta"]["numbers"])
               for item in dataset["items"] if item["family"] == "g24"}
    rows = [r for r in json.loads((RUN / "records.json").read_text())
            if r["family"] == "g24" and r["strategy"] == "COT" and r["token_budget"] == 1024]
    assert len(rows) == len({r["group_id"] for r in rows}) == 8
    observed = []
    for row in rows:
        # Use the stored parsed PUBLIC answer, never a raw/private rationale.
        result = verify_g24_rationale("Answer: " + row["answer"], {"numbers": numbers[row["id"]]})
        observed.append({"id": row["id"], "group_id": row["group_id"],
                         "checker_status": result.status.value, "reason": result.reason,
                         "stored_correct": row["correct"],
                         "length_stop": any(g["finish_reason"] == "length" for g in row["trace"]["generations"])})
    assert all(sha(RUN / name) == digest for name, digest in expected.items())
    assert sources == {p: sha(ROOT / p) for p in sources}
    output = {
        "kind": "retrospective_public_answer_coverage", "new_model_calls": 0,
        "groups": 8, "seed": manifest["seed"], "cap_per_call": 1024,
        "run": str(RUN.relative_to(ROOT)), "run_manifest_sha256": sha(RUN / "manifest.json"),
        "input_artifact_sha256": expected, "source_sha256": sources,
        "script_sha256": sha(Path(__file__)), "historical_inputs_unchanged": True,
        "statuses": dict(Counter(r["checker_status"] for r in observed)),
        "status_by_stored_correctness": dict(Counter(f"{r['checker_status']}|correct={r['stored_correct']}" for r in observed)),
        "items": observed, "human_review_status": "pending", "publication_ready": False,
        "important_limit": "Checker and original procedural scorer share check24; their agreement is not independent accuracy/precision validation.",
        "input_scope": "Stored parsed public expression + four declared numbers. Prefix Answer: is an adapter, not a raw-output format test.",
    }
    (OUT / "saved_g24_coverage.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: output[key] for key in ("groups", "statuses", "status_by_stored_correctness", "new_model_calls")}, indent=2))


if __name__ == "__main__":
    main()
