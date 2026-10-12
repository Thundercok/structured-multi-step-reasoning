"""Build a review packet and verify local model content without inference."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

from experiments.research_pilot import select_groups, sha256_file
from experiments.research_study import ROOT, check_answer, source_hashes, write_json
from scripts.audit_development_data import solve_procedural_query


def solve_24(numbers):
    """Find an expression using subset dynamic programming and exact fractions."""
    if len(numbers) != 4 or any(type(number) is not int or number <= 0 for number in numbers):
        raise ValueError("Expected four positive integer operands")
    values = {1 << i: {Fraction(number): str(number)} for i, number in enumerate(numbers)}
    for mask in range(1, 1 << len(numbers)):
        if mask in values:
            continue
        results = {}
        left = (mask - 1) & mask
        while left:
            right = mask ^ left
            if right and left < right:
                for a, expression_a in values[left].items():
                    for b, expression_b in values[right].items():
                        possibilities = [(a + b, f"({expression_a}+{expression_b})"),
                            (a * b, f"({expression_a}*{expression_b})"),
                            (a - b, f"({expression_a}-{expression_b})"),
                            (b - a, f"({expression_b}-{expression_a})")]
                        if b:
                            possibilities.append((a / b, f"({expression_a}/{expression_b})"))
                        if a:
                            possibilities.append((b / a, f"({expression_b}/{expression_a})"))
                        for value, expression in possibilities:
                            results.setdefault(value, expression)
            left = (left - 1) & mask
        values[mask] = results
    expression = values[(1 << len(numbers)) - 1].get(Fraction(24))
    if expression is None:
        raise ValueError("Question has no exact solution for 24")
    return expression


def verify_item(item):
    # The existing query parser separately validates the supplied reference.
    answer, proof = solve_procedural_query(item)
    if item["family"] == "g24":
        span = re.search(r"numbers (.*?) exactly once", item["query"]).group(1)
        numbers = list(map(int, re.findall(r"\d+", span)))
        answer = solve_24(numbers)
        proof = {**proof, "independent_method": "subset dynamic programming with exact fractions",
                 "independent_expression": answer, "operands_from_query": numbers}
    else:
        proof["independent_method"] = "query-derived exact arithmetic" if item["family"] == "arith" else "query-derived exhaustive ordering"
    if not check_answer(answer, item):
        raise ValueError(f"Gold disagrees with independent solution: {item['id']}")
    return {"id": item["id"], "group_id": item["group_id"], "split": item["split"],
            "family": item["family"], "level": item["level"], "query": item["query"],
            "reference_answer": item["answer"], "independent_answer": answer,
            "query_sha256": hashlib.sha256(item["query"].encode()).hexdigest(),
            "source_provenance": item["source_provenance"], "proof": proof,
            "automated_verification": "pass", "human_review_status": "pending"}


def verify_model(directory, metadata):
    """Verify SHA-256 for LFS content and Git blob hashes for ordinary files."""
    directory = directory.resolve()
    if metadata.get("id") != "mlx-community/Qwen3-8B-4bit":
        raise ValueError("Expected the reviewed Qwen3-8B-4bit repository metadata")
    rows = []
    for expected in metadata["siblings"]:
        name = expected["rfilename"]
        if name == ".gitattributes":
            continue  # Repository attribute metadata is not a runtime model file.
        if Path(name).name != name or not (directory / name).is_file():
            raise ValueError(f"Missing or unsafe model file: {name}")
        path = directory / name
        if path.stat().st_size != expected["size"]:
            raise ValueError(f"Upstream size differs for {name}")
        sha256 = sha256_file(path)
        if "lfs" in expected:
            observed = sha256
            upstream = expected["lfs"]["sha256"]
            method = "sha256"
        else:
            content = path.read_bytes()
            observed = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            upstream = expected["blobId"]
            method = "git_blob_sha1"
        if observed != upstream:
            raise ValueError(f"Upstream content differs for {name}")
        rows.append({"name": name, "bytes": path.stat().st_size, "sha256": sha256,
                     "upstream_hash_method": method, "upstream_hash": upstream, "match": True})
    if not any(row["name"].endswith(".safetensors") for row in rows):
        raise ValueError("Upstream metadata lacks model weights")
    return {"repository": metadata["id"], "revision": metadata["sha"],
            "local_directory": str(directory), "local_content_matches_upstream_revision": True,
            "model_loaded": False, "license_declared_by_model_card": metadata.get("cardData", {}).get("license"),
            "files": rows}


def render_review(rows, model, max_tokens):
    lines = ["# Selected development pilot review", "",
        f"{len(rows)} questions / {len({row['group_id'] for row in rows})} canonical groups; automated exact checks pass.",
        "Human/source ownership sign-off remains pending. These are exposed development questions; no held-out gold was inspected.",
        "Model content matches the pinned upstream revision; this preparation made no model call.",
        f"Proposed collection: DIRECT and CoT, caps 96 and 1,024 per call, seed 42; {len(rows) * 4} conditions and at most {max_tokens:,} generated tokens.",
        "Current DIRECT prompt is Vietnamese and CoT prompt is English. Matched caps alone do not isolate instruction from prompt-language effects.", "",
        "## Human review record", "", "Reviewer: pending", "Date: pending", "",
        "Confirm wording/answers/groups below; record procedural generator ownership or permission and any requested corrections.",
        "The repository has no top-level license for this generator. Git history supports origin tracking, not a rights-holder assertion.", ""]
    for index, row in enumerate(rows, 1):
        lines.extend([f"## {index}. {row['id']}", "", f"Split/family/level: {row['split']} / {row['family']} / {row['level']}", "",
            row["query"], "", f"Reference: `{row['reference_answer']}`", f"Independent solution: `{row['independent_answer']}`", "",
            f"Proof: {json.dumps(row['proof'], ensure_ascii=False)}", "", "Human decision: pending", ""])
    lines.extend(["## Model provenance", "", f"Repository: {model['repository']}", f"Revision: `{model['revision']}`", "",
        f"[Pinned model card](https://huggingface.co/{model['repository']}/blob/{model['revision']}/README.md)",
        "All runtime model/tokenizer files are matched to upstream hashes; weights use SHA-256, ordinary files Git blob SHA-1.", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/procedural_research_v1/tuning.json")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--upstream-metadata", type=Path, required=True, help="Directory containing saved Hugging Face API/model license responses")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--groups-per-stratum", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    if args.groups_per_stratum <= 0:
        parser.error("Groups per stratum must be positive")
    dataset, selection = select_groups(json.loads(args.dataset.read_text()), args.seed, args.groups_per_stratum)
    rows = [verify_item(item) for item in dataset["items"]]
    metadata_path = args.upstream_metadata / "model_info.json"
    metadata = json.loads(metadata_path.read_text())
    model = verify_model(args.model, metadata)
    base = json.loads((args.upstream_metadata / "base_model_info.json").read_text())
    model["upstream_metadata_url"] = f"https://huggingface.co/api/models/{model['repository']}/revision/{model['revision']}?blobs=true"
    model["base_model_license_url"] = f"https://huggingface.co/Qwen/Qwen3-8B/resolve/{base['sha']}/LICENSE"
    max_tokens = len(rows) * 2 * (96 + 1024)
    generator_history = subprocess.check_output(["git", "log", "--follow", "--format=%H %cs %s", "--", "scripts/gen_tasks.py"], cwd=ROOT, text=True).splitlines()
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in (("selected_dataset.json", dataset), ("selection.json", selection),
                       ("gold_verification.json", rows), ("model_provenance.json", model)):
        write_json(args.output / name, data)
    for name in ("model_info.json", "base_model_info.json", "base_model_LICENSE"):
        shutil.copyfile(args.upstream_metadata / name, args.output / name)
    (args.output / "review.md").write_text(render_review(rows, model, max_tokens), encoding="utf-8")
    manifest = {
        "kind": "development_pilot_preflight", "status": "complete",
        "recorded_utc": datetime.now(timezone.utc).isoformat(), "source_sha256": source_hashes(),
        "preparation_script_sha256": sha256_file(Path(__file__)),
        "input_dataset_sha256": sha256_file(args.dataset), "seed": args.seed,
        "selected_items": len(rows), "selected_groups": len(selection["selected_group_ids"]),
        "selected_strata": len(selection["strata"]), "planned_conditions": len(rows) * 4,
        "maximum_generated_tokens": max_tokens, "generator_git_history": generator_history,
        "procedural_ownership_confirmation": "pending", "human_review_status": "pending",
        "publication_ready": False, "model_calls": 0, "policy_fitted": False,
        "stage0_decision_sha256": sha256_file(ROOT / "docs/stage0_gate_decision.md"),
        "stage0_changed": False,
        "artifact_sha256": {path.name: sha256_file(path) for path in sorted(args.output.iterdir()) if path.is_file()},
    }
    write_json(args.output / "manifest.json", manifest)
    print(json.dumps({key: manifest[key] for key in ("selected_items", "selected_groups", "planned_conditions", "maximum_generated_tokens", "model_calls")}))


if __name__ == "__main__":
    main()
