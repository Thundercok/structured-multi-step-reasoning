"""Migrate immutable legacy inputs into isolated, grouped research candidates.

No model calls, result inspection, question rewriting or held-out gold review.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path

from experiments.research_study import validate_dataset
from research_identity import IDENTITY_VERSION, canonical_problem_id, digest

ROOT = Path(__file__).resolve().parents[1]
LEGACY_SPLITS = {"dev", "calib", "test"}
REVIEW_DIRECTORY = ROOT / "audit/development-data-20261003-final"


def _groups(dataset):
    items = dataset["items"]
    if digest(items) != dataset["meta"]["sha256_items"]:
        raise ValueError("Legacy dataset item hash does not match its manifest")
    if len({row["id"] for row in items}) != len(items):
        raise ValueError("Legacy input contains duplicate IDs")
    groups = defaultdict(list)
    for row in items:
        if row["split"] not in LEGACY_SPLITS:
            raise ValueError("Unknown legacy split")
        groups[canonical_problem_id(row)].append(row)
    return groups


def _assign_development(groups, seed, role):
    strata = defaultdict(list)
    for problem_id, rows in groups.items():
        # A multi-level variant class remains one indivisible group.
        stratum = (rows[0]["family"], tuple(sorted({row["level"] for row in rows})))
        strata[stratum].append(problem_id)
    assignments = {}
    for stratum, identifiers in sorted(strata.items()):
        ordered = sorted(identifiers, key=lambda identifier: digest([seed, role, stratum, identifier]))
        n_train = (len(ordered) + 1) // 3
        if len(ordered) >= 2:
            n_train = max(1, min(len(ordered) - 1, n_train))
        for index, identifier in enumerate(ordered):
            assignments[identifier] = "train" if index < n_train else "calibration"
    return assignments


def _adapt(groups, assignments, name, role, original_meta, source, reviews):
    items = []
    for problem_id, rows in sorted(groups.items()):
        for original in sorted(rows, key=lambda row: row["id"]):
            row = copy.deepcopy(original)
            provenance = {
                **source, "original_id": original["id"],
                "original_group_id": original["group_id"], "original_split": original["split"],
                "original_row_sha256": digest(original),
            }
            proof = reviews.get(original["id"])
            if proof:
                if original["split"] == "test" or proof["query_sha256"] != hashlib.sha256(original["query"].encode()).hexdigest() or proof["verified_answer"] != original["answer"]:
                    raise ValueError("Development review no longer matches its original item")
            row.update({
                "id": f"{name}/{original['id']}", "group_id": problem_id, "problem_id": problem_id,
                "split": assignments[problem_id],
                "answer_type": "number" if original["family"] == "arith" else "text",
                "language": "en", "source_provenance": provenance,
                "review_status": "agent_reviewed" if proof else "unreviewed",
                "review": {
                    "human_review_status": "pending",
                    "artifact": source.get("development_review_artifact") if proof else None,
                    "scope": "Original development question and gold" if proof else "No semantic/gold review claimed",
                },
            })
            items.append(row)
    return {
        "name": name, "version": "1.0.0-candidate", "role": role,
        "source": "Immutable procedural gen_tasks.py 0.1 input; see source_provenance and legacy_meta",
        "license": "Project procedural generator; rights-holder/license confirmation pending",
        "identity_version": IDENTITY_VERSION, "legacy_meta": copy.deepcopy(original_meta),
        "publication_ready": False, "human_review_status": "pending",
        "test_exposure_status": "Original test retained where eligible; prior external exposure unverified" if role == "main_study" else "Entire legacy tuning pool treated as exposed development",
        "items": sorted(items, key=lambda row: row["id"]),
    }


def counts(dataset):
    items = dataset["items"]
    strata = sorted({(row["family"], row["level"]) for row in items})
    return {
        "items": len(items), "canonical_groups": len({row["group_id"] for row in items}),
        "items_by_split": dict(sorted(Counter(row["split"] for row in items).items())),
        "groups_by_split": {split: len({row["group_id"] for row in items if row["split"] == split}) for split in sorted({row["split"] for row in items})},
        "reviewed_items": sum(row["review_status"] == "agent_reviewed" for row in items),
        "strata": [{
            "family": family, "level": level,
            "items_by_split": dict(sorted(Counter(row["split"] for row in items if (row["family"], row["level"]) == (family, level)).items())),
            "groups_by_split": {split: len({row["group_id"] for row in items if (row["family"], row["level"]) == (family, level) and row["split"] == split}) for split in ("train", "calibration", "test")},
        } for family, level in strata],
    }


def build_release(main_input, tuning_input, *, split_seed=42, sources=None, reviews=None):
    """Regroup development only; never promote any development group to test."""
    sources = sources or {"main": {}, "tuning": {}}
    reviews = reviews or {"main": {}, "tuning": {}}
    main_groups, tune_groups = _groups(main_input), _groups(tuning_input)
    excluded = []
    eligible = {}
    for problem_id, rows in main_groups.items():
        if problem_id in tune_groups:
            excluded.extend({"original_id": row["id"], "original_split": row["split"], "problem_id": problem_id, "reason": "Canonical problem belongs to exposed tuning pool"} for row in rows)
        else:
            eligible[problem_id] = rows
    held = {key: rows for key, rows in eligible.items() if {row["split"] for row in rows} == {"test"}}
    development = {key: rows for key, rows in eligible.items() if key not in held}
    assignments = _assign_development(development, split_seed, "main_study")
    assignments.update({key: "test" for key in held})
    main = _adapt(eligible, assignments, "procedural-main-v1", "main_study", main_input["meta"], sources["main"], reviews["main"])
    tune = _adapt(tune_groups, _assign_development(tune_groups, split_seed, "development_tuning"), "procedural-tuning-v1", "development_tuning", tuning_input["meta"], sources["tuning"], reviews["tuning"])
    validate_dataset(main)
    validate_dataset(tune, require_all_splits=False)
    shared = {row["problem_id"] for row in main["items"]} & {row["problem_id"] for row in tune["items"]}
    if shared:
        raise ValueError("Tuning/evaluation canonical identities overlap")
    promotions = [row["id"] for row in main["items"] if row["split"] == "test" and row["source_provenance"]["original_split"] != "test"]
    if promotions:
        raise ValueError("Development content was promoted into test")
    # Retained question/label/metadata bytes must agree with the source row.
    for output, original in ((main, main_input), (tune, tuning_input)):
        by_id = {row["id"]: row for row in original["items"]}
        for row in output["items"]:
            old = by_id[row["source_provenance"]["original_id"]]
            if any(row[key] != value for key, value in old.items() if key not in ("id", "group_id", "split")):
                raise ValueError("Migration changed original question/label content")
    checks = {
        "kind": "procedural_dataset_migration", "split_seed": split_seed,
        "split_algorithm": "SHA256 rank of seed/role/family/level-set/canonical-ID; nearest one-third of development groups to train, remainder calibration; eligible original test groups retained",
        "identity_version": IDENTITY_VERSION,
        "main": counts(main), "tuning": counts(tune),
        "cross_release_problem_overlap": len(shared),
        "cross_release_item_id_overlap": len({row["id"] for row in main["items"]} & {row["id"] for row in tune["items"]}),
        "excluded_main_items": sorted(excluded, key=lambda row: row["original_id"]),
        "development_promoted_to_test": len(promotions),
        "original_content_preserved": True, "model_calls": 0,
        "publication_ready": False,
        "demoted_original_test_items": sum(row["split"] != "test" and row["source_provenance"]["original_split"] == "test" for row in main["items"]),
    }
    return main, tune, checks


def _load(path):
    data = json.loads(path.read_text())
    return data, {"path": str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _review_records(source):
    path = REVIEW_DIRECTORY / "checks.json"
    manifest = json.loads((REVIEW_DIRECTORY / "manifest.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["artifact_sha256"]["checks.json"]:
        raise ValueError("Development review artifact hash mismatch")
    for dataset in json.loads(path.read_text())["datasets"]:
        if dataset["sha256"] == source["sha256"]:
            source.update({"development_review_artifact": str(path.relative_to(ROOT)), "development_review_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            return {row["id"]: row for row in dataset["development_outcomes"]}
    return {}


def render_report(checks):
    lines = [
        "# Procedural research dataset candidate", "",
        "Structural/schema validation complete. Human and source/license review pending; no model-quality claim. Stage 0 unchanged.", "",
        "| Release | Items | Canonical groups | Train items | Calibration items | Test items |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ("main", "tuning"):
        count = checks[name]
        splits = count["items_by_split"]
        lines.append(f"| {name} | {count['items']} | {count['canonical_groups']} | {splits.get('train', 0)} | {splits.get('calibration', 0)} | {splits.get('test', 0)} |")
    lines.extend([
        "", f"Split seed: {checks['split_seed']}. {checks['split_algorithm']}.", "",
        "Canonical identities use arithmetic start/ordered operations, the Game-of-24 number multiset, and ordering clue graphs under all runner renamings plus the asked rank. This does not prove absence of every semantic equivalence, template shortcut or pretraining overlap.", "",
        f"Excluded {len(checks['excluded_main_items'])} main-source items belonging to the exposed tuning pool, regardless of model outcome. Cross-release canonical/ID overlaps: zero. Original inputs and retained question/label/metadata content are unchanged; no development content is promoted into test.", "",
        "main.json uses the supported train/calibration/test schema. tuning.json contains exposed development only; the study entry point rejects it as a held-out study input. Original tuning test labels are not presented as held-out evaluation.", "",
        "Agent review provenance is carried only for unchanged, previously audited development items. Original test labels were not semantically reviewed by this migration. Independent human review, ownership/license confirmation and prior test-exposure review remain necessary before freezing a publication dataset.", "",
        "Family/level counts describe generator bands, not measured difficulty or calibrated accuracy. Variants sharing a canonical group are dependent; group counts are reported separately. This is a small candidate release, without a power/precision justification.", "",
        "## Family and level coverage", "",
        "| Release | Family | Level | Train | Calibration | Test |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ])
    for name in ("main", "tuning"):
        for stratum in checks[name]["strata"]:
            splits = stratum["items_by_split"]
            lines.append(f"| {name} | {stratum['family']} | {stratum['level']} | {splits.get('train', 0)} | {splits.get('calibration', 0)} | {splits.get('test', 0)} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main-input", type=Path, default=ROOT / "data/gen_v2.json")
    parser.add_argument("--tuning-input", type=Path, default=ROOT / "data/gen_tune.json")
    parser.add_argument("--split-seed", type=int, default=42)
    parser.add_argument("--output", type=Path, required=True, help="New release directory; never overwritten")
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    main_input, main_source = _load(args.main_input.resolve())
    tuning_input, tuning_source = _load(args.tuning_input.resolve())
    sources = {"main": main_source, "tuning": tuning_source}
    reviews = {role: _review_records(source) for role, source in sources.items()}
    main_data, tuning_data, checks = build_release(main_input, tuning_input, split_seed=args.split_seed, sources=sources, reviews=reviews)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, value in (("main.json", main_data), ("tuning.json", tuning_data), ("checks.json", checks)):
        (args.output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "report.md").write_text(render_report(checks), encoding="utf-8")
    source_names = ("scripts/build_procedural_research_data.py", "research_identity.py", "experiments/research_study.py", "scripts/gen_tasks.py")
    manifest = {
        "status": "complete", "kind": "procedural_dataset_candidate", "identity_version": IDENTITY_VERSION,
        "split_seed": args.split_seed, "inputs": sources,
        "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_names},
        "artifact_sha256": {name: hashlib.sha256((args.output / name).read_bytes()).hexdigest() for name in ("main.json", "tuning.json", "checks.json", "report.md")},
        "publication_ready": False, "model_calls": 0, "stage0_changed": False,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({role: {key: checks[role][key] for key in ("items", "canonical_groups", "items_by_split", "groups_by_split")} for role in ("main", "tuning")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
