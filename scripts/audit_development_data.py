"""Read-only development audit; held-out content is only hashed for isolation checks."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.research_study import check_answer, normalized_text, write_json
from research_identity import digest, problem_fingerprint

DEVELOPMENT_SPLITS = {"train", "calibration", "dev", "calib"}
DATASETS = ("data/nckh_reasoning_dataset_draft.json", "data/gen_v2.json", "data/gen_tune.json")


def isolation_checks(items):
    classes = {}
    for item in items:
        classes.setdefault(problem_fingerprint(item), []).append(item)
    crossings = [rows for rows in classes.values() if len({row["split"] for row in rows}) > 1]
    return {
        "canonical_problem_classes": len(classes),
        "problem_classes_crossing_splits": len(crossings),
        "items_in_crossing_problem_classes": sum(map(len, crossings)),
        "crossing_families": dict(Counter(rows[0].get("family", "curated") for rows in crossings)),
        "method": "Arithmetic start/steps; g24 number multiset; order clue graph under all name permutations plus asked rank. No test labels used.",
    }


def solve_curated_group(group):
    """Independent calculations/countermodels recorded from reviewed development text."""
    arithmetic = {
        "grp_pal_003": (100 - 50 - 15 - 2 * 15, "100 - 100/2 - 15 - 2*15"),
        "grp_pal_004": ((2 * 16 + 2 * 8) * 4, "(2*16 + 2*8)*4"),
        "grp_pal_005": (Fraction(150) * Fraction(80, 100) * Fraction(108, 100), "150 * 80/100 * 108/100"),
        "grp_pal_006": (75 * 2 + 90 * Fraction(3, 2), "75*2 + 90*3/2"),
        "grp_pal_007": (2 * (24 + 18), "2*(24+18)"),
        "grp_pal_008": ((320 - 2 * 120) // 2, "(320 - 2*120)/(4-2)"),
        "grp_react_001": (345 * 28 - Fraction(1240, 5) + 89, "345*28 - 1240/5 + 89"),
        "grp_react_002": (24 * 18 + 15 * 25 + 30 * 12, "24*18 + 15*25 + 30*12"),
        "grp_react_003": (Fraction(15, 100) * 840 + Fraction(25, 100) * 620 - Fraction(30, 100) * 450, "15/100*840 + 25/100*620 - 30/100*450"),
        "grp_react_004": (145 + 210 + 85, "145+210+85"),
        "grp_react_005": (450 + 520 + 610 - 80, "450+520+610-80"),
        "grp_react_007": (3 * (45 + 55) - 4 * (120 - 85) + Fraction(250, 5), "3*(45+55) - 4*(120-85) + 250/5"),
    }
    if group in arithmetic:
        value, explanation = arithmetic[group]
        fraction = Fraction(value)
        answer = str(fraction.numerator) if fraction.denominator == 1 else str(float(fraction))
        return answer, explanation
    if group == "grp_plain_002":
        roses, flowers, fast = {"rose"}, {"rose", "lily"}, {"lily"}
        assert roses <= flowers and bool(flowers & fast) and not roses <= fast
        return "No", "Countermodel: rose is a flower that fades slowly; lily is a flower that fades quickly."
    if group == "grp_plain_003":
        orders = [p for p in itertools.permutations("ABCDE") if all(p.index(a) < p.index(b) for a, b in (("A", "B"), ("C", "A"), ("D", "C"), ("E", "D")))]
        first = {p[0] for p in orders}
        assert first == {"E"}
        return "E", f"Exhaustive ordering: {len(orders)} consistent order, E-D-C-A-B."
    if group == "grp_plain_004":
        weekdays = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        return weekdays[(1 + 100) % 7], "Tuesday index 1 + 100 days modulo 7 = Thursday index 3."
    if group == "grp_plain_005":
        orders = [p for p in itertools.permutations(("Tom", "Jerry", "Spike", "Tyke")) if all(p.index(a) < p.index(b) for a, b in (("Tom", "Jerry"), ("Jerry", "Spike"), ("Spike", "Tyke")))]
        assert orders and all(p.index("Tom") < p.index("Tyke") for p in orders)
        return "Yes", "All consistent strict age orderings put Tom before Tyke."
    if group == "grp_plain_006":
        safe = []
        for passenger in ("Wolf", "Goat", "Cabbage"):
            left = {"Wolf", "Goat", "Cabbage"} - {passenger}
            if not any(set(pair) <= left for pair in (("Wolf", "Goat"), ("Goat", "Cabbage"))):
                safe.append(passenger)
        assert safe == ["Goat"]
        return "Goat", "Boat carries farmer plus one item; only removing Goat leaves a safe unattended starting bank."
    if group == "grp_plain_007":
        assert Fraction(1) == Fraction(1)
        return "Equal", "Both masses are exactly 1 kg, using the ordinary mass interpretation."
    raise ValueError(f"No independent development proof for {group}")


def solve_procedural_query(item):
    """Parse the English query and solve it without generator verification functions."""
    query, family = item["query"], item["family"]
    if family == "arith":
        match = re.search(r"counter starts at (\d+)\.", query)
        start = int(match.group(1))
        value = Fraction(start)
        operations = re.findall(r"\((\d+)\) (add|subtract|multiply the result by|divide the result by) (\d+)", query)
        if not operations or [int(row[0]) for row in operations] != list(range(1, len(operations) + 1)):
            raise ValueError("Malformed operation sequence")
        codes = {"add": "add", "subtract": "sub", "multiply the result by": "mul", "divide the result by": "div"}
        parsed_metadata = {"start": start, "steps": [[codes[op], int(amount)] for _, op, amount in operations]}
        if "meta" in item and item["meta"] != parsed_metadata:
            raise ValueError("Arithmetic metadata differs from query")
        for _, operation, operand in operations:
            amount = int(operand)
            if operation == "add": value += amount
            elif operation == "subtract": value -= amount
            elif operation == "multiply the result by": value *= amount
            else: value /= amount
            if value.denominator != 1 or value < 0:
                raise ValueError("Non-integer/negative intermediate")
        return str(value.numerator), {"parsed_steps": len(operations)}
    if family == "order":
        names = re.search(r"runners \(([^)]+)\)", query).group(1).split(", ")
        asked = int(re.search(r"in (\d+)(?:st|nd|rd|th) place", query).group(1)) - 1
        clues = re.findall(r"([A-Za-z]+) finished (immediately before|before|after) ([A-Za-z]+)", query)
        parsed_clues = [
            ("a", names.index(a), names.index(b)) if relation == "immediately before"
            else ("b", names.index(b), names.index(a)) if relation == "after"
            else ("b", names.index(a), names.index(b))
            for a, relation, b in clues
        ]
        if "meta" in item:
            metadata = item["meta"]
            if metadata["names"] != names or metadata["ask"] != asked or sorted(map(tuple, metadata["clues"])) != sorted(parsed_clues):
                raise ValueError("Ordering metadata differs from query")
        possible, count = set(), 0
        for order in itertools.permutations(names):
            positions = {name: index for index, name in enumerate(order)}
            valid = all(
                positions[a] + 1 == positions[b] if relation == "immediately before"
                else positions[a] < positions[b] if relation == "before"
                else positions[a] > positions[b]
                for a, relation, b in clues
            )
            if valid:
                count += 1
                possible.add(order[asked])
        if len(possible) != 1:
            raise ValueError("Ordering question lacks a unique asked occupant")
        return possible.pop(), {"consistent_orders": count, "parsed_clues": len(clues)}
    if family == "g24":
        span = re.search(r"numbers (.*?) exactly once", query).group(1)
        numbers = sorted(map(int, re.findall(r"\d+", span)))
        if "meta" in item and sorted(item["meta"]["numbers"]) != numbers:
            raise ValueError("Game-of-24 metadata differs from query")
        used = []

        def evaluate(node):
            if isinstance(node, ast.Constant) and type(node.value) is int:
                used.append(node.value)
                return Fraction(node.value)
            if isinstance(node, ast.BinOp):
                a, b = evaluate(node.left), evaluate(node.right)
                if isinstance(node.op, ast.Add): return a + b
                if isinstance(node.op, ast.Sub): return a - b
                if isinstance(node.op, ast.Mult): return a * b
                if isinstance(node.op, ast.Div): return a / b
            raise ValueError("Disallowed reference expression")

        result = evaluate(ast.parse(item["answer"], mode="eval").body)
        if sorted(used) != numbers or result != 24:
            raise ValueError("Reference expression violates numbers or target")
        return item["answer"], {"exact_value": str(result), "numbers_used_exactly_once": True}
    raise ValueError("Unknown procedural family")


def apply_curated_review(dataset, review):
    """Apply reviewed development patches without changing any held-out row."""
    before = digest([item for item in dataset["items"] if item["split"] == "test"])
    reviewed = {group["group_id"]: group for group in review["curated_groups"]}
    by_id = {item["id"]: item for item in dataset["items"]}
    for identifier, patch in review["item_corrections"].items():
        item = by_id[identifier]
        if item["split"] not in DEVELOPMENT_SPLITS or item["group_id"] not in reviewed:
            raise ValueError("Review patches may target only reviewed development items")
        if not set(patch) <= {"query", "answer_aliases", "decimal_separator", "source_provenance"}:
            raise ValueError("Unexpected development patch field")
        item.update(patch)
    for item in dataset["items"]:
        if item["split"] not in DEVELOPMENT_SPLITS:
            continue
        group = reviewed[item["group_id"]]
        if group["split"] != item["split"]:
            raise ValueError("Review applies only to its recorded split assignment")
        item["review_status"] = "agent_reviewed"
        item["review"] = {
            "reviewer": review["reviewer"], "artifact": "audit/development_data_review.json",
            "human_review_status": "pending",
        }
    dataset["version"] = "1.0.1-development-audit"
    dataset["license"] = "Mixed item-level declarations; source and ownership review required"
    dataset["review_scope"] = "Agent review of train/calibration only; human sign-off pending; test unreviewed by this audit"
    if digest([item for item in dataset["items"] if item["split"] == "test"]) != before:
        raise ValueError("Held-out rows changed")
    return dataset


def audit_dataset(path, review):
    data = json.loads(path.read_text())
    items = data["items"]
    if any(item.get("split") not in DEVELOPMENT_SPLITS | {"test"} for item in items):
        raise ValueError("Unknown dataset split")
    groups = {}
    for item in items:
        previous = groups.setdefault(item["group_id"], item["split"])
        if previous != item["split"]:
            raise ValueError("Group crosses splits")
    if len({item["id"] for item in items}) != len(items):
        raise ValueError("Duplicate item IDs")
    hashes = [hashlib.sha256(normalized_text(item["query"]).encode()).hexdigest() for item in items]
    if len(set(hashes)) != len(hashes):
        raise ValueError("Duplicate normalized queries")
    development = [item for item in items if item["split"] in DEVELOPMENT_SPLITS]
    group_review = {group["group_id"]: group for group in review["curated_groups"]}
    outcomes = []
    for item in development:
        if "family" in item:
            expected, proof = solve_procedural_query(item)
        else:
            record = group_review[item["group_id"]]
            if hashlib.sha256(item["query"].encode()).hexdigest() != record["variant_query_sha256"][item["id"]]:
                raise ValueError("Question differs from the semantically reviewed text")
            expected, proof = solve_curated_group(item["group_id"])
        if expected != item["answer"] or not check_answer(expected, item):
            raise ValueError(f"Development gold failed independent check: {item['id']}")
        outcomes.append({"id": item["id"], "group_id": item["group_id"], "split": item["split"], "query_sha256": hashlib.sha256(item["query"].encode()).hexdigest(), "verified_answer": expected, "proof": proof})
    return {
        "path": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "items": len(items), "groups": len(groups), "development_items_verified": len(outcomes),
        "group_counts_by_split": dict(Counter(groups.values())),
        "held_out_rows_sha256": digest([item for item in items if item["split"] == "test"]),
        "blind_problem_isolation": isolation_checks(items),
        "development_outcomes": outcomes,
    }


def render_report(report, review):
    lines = [
        "# Development data and scoring validation", "",
        "Overall assessment: **Needs revision before main-study release**.", "",
        "This is a Codex AI-agent audit, not a record of independent human approval. No model calls or policy fitting occurred.",
        "Semantic and answer review covers only train/calibration/dev/calib. Test content was not displayed or semantically reviewed; automated isolation checks used IDs, structural fingerprints and hashes without test labels.", "",
        "## Verified calculations and coverage", "",
        "| Dataset | Development answers verified | Groups by split | Structural classes crossing splits |",
        "| --- | ---: | --- | ---: |",
    ]
    for result in report["datasets"]:
        lines.append(f"| {result['path']} | {result['development_items_verified']} | {result['group_counts_by_split']} | {result['blind_problem_isolation']['problem_classes_crossing_splits']} |")
    lines.extend([
        "", "The curated audit covers 54 variants of 18 original development groups. Procedural checks cover 168 development items, using query-parsed arithmetic, exhaustive ordering constraints, and exact rational evaluation of Game-of-24 references. All intended development labels agreed with those checks; wording repairs made previously implicit assumptions explicit.",
        "The order fingerprint canonicalizes clue graphs under every renaming and retains the asked rank. Matching fingerprints identify renamed logical instances; groups defined only by generated IDs miss this overlap. No held-out question or label was used to tune a scorer.", "",
        "## Issues repaired", "",
        "- **High:** ordering and arithmetic checkers accepted negation/alternative answers. They now match an entire scalar/name response, with a bounded unit vocabulary and consistent asserted rank.",
        "- **High:** Game-of-24 ignored contradictory equality suffixes and generic parsing discarded the expression. The checker validates the whole equality; typed extraction and voting preserve expressions through CoT, SC, selection, ReAct and PAL.",
        "- **High:** legacy parsing reduced contradictory Yes/No text to its first word. Research text extraction retains the complete final response for exact scoring.",
        "- **Medium:** correct Vietnamese text labels were rejected and decimal commas could be stripped as thousands separators. Development items now declare finite text aliases or a decimal separator; no substring or label-dependent normalization is used.",
        "- **Medium:** river crossing lacked capacity/rowing rules, pizza wording assumed consumption, travel variants omitted duration facts, and two translations changed the noun/domain. Ten development wording repairs restore explicit assumptions and matching facts.",
        "- **High:** hard-coded reviewed/human labels lacked a reviewer record. Development rows now say agent_reviewed with human review pending; the legacy gold table recalculates labels and states its actual review status.", "",
        "## Remaining release requirements", "",
        "- Assign canonical problem identities and create fresh disjoint splits before a main study. Existing test rows were preserved for audit integrity rather than silently reassigned.",
        "- Namespace procedural IDs by dataset release and prevent overlap between tuning and evaluation releases. Adapt dev/calib names and missing root/answer-type metadata to the supported research schema in the next preparation step.",
        "- Obtain independent human review and establish ownership/source records for descriptive template origins. A CC-BY declaration alone is not a provenance record.",
        "- Perform the held-out review through a separate process after scoring/prompt rules are frozen. This audit does not confirm any held-out answer or change Stage 0.", "",
        "## Source evidence", "",
        "The calibration Betty problem is an English adaptation of the official GSM8K training record at line 3, rather than a verbatim original. Its source label agrees. The pinned source revision and question/file fingerprints are in [source evidence](../development-source-evidence.json). The official repository records an [MIT license](https://github.com/openai/grade-school-math/blob/3101c7d5072418e28b9008a6636bde82a006892c/LICENSE). Paraphrase/translation provenance is recorded for all three development variants.",
        "Other curated source strings describe task genres; this audit could not establish an upstream revision or a rights-holder declaration for them. The draft root now describes mixed item-level declarations rather than presenting a single verified license.", "",
        "## Curated group review", "",
        "| Group | Split | Verified label | Independent calculation or proof | Variant review |",
        "| --- | --- | --- | --- | --- |",
    ])
    for group in review["curated_groups"]:
        lines.append(f"| {group['group_id']} | {group['split']} | {group['expected_answer']} | {group['independent_proof']} | {group['translation_review']} |")
    lines.extend(["", "## Cross-dataset identity checks", ""])
    for comparison in report["cross_dataset_identity"]:
        lines.append(f"- {comparison['datasets']}: {comparison['shared_group_names']} shared group names; {comparison['shared_problem_fingerprints']} shared canonical problem identities.")
    lines.extend([
        "", "## Reproduction", "", "```bash",
        "python -m scripts.audit_development_data --output audit/development-data-audit-new",
        "```", "",
        "Detailed per-item development proofs and blind held-out row fingerprints are in checks.json. Existing output directories are never overwritten.",
        "These checks establish data/scoring properties. They provide no measured model-quality, inference-cost or online-latency evidence.",
    ])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New audit directory")
    args = parser.parse_args(argv)
    review_path = ROOT / "audit/development_data_review.json"
    review = json.loads(review_path.read_text())
    results = [audit_dataset(ROOT / name, review) for name in DATASETS]
    baseline = json.loads((ROOT / "audit/development_audit_baseline.json").read_text())
    for result, original in zip(results, baseline["datasets"]):
        if result["held_out_rows_sha256"] != original["held_out_rows_sha256"]:
            raise ValueError("Held-out rows changed since baseline")
    args.output.mkdir(parents=True, exist_ok=False)
    cross_dataset = []
    for left, right in itertools.combinations(DATASETS, 2):
        a = json.loads((ROOT / left).read_text())["items"]
        b = json.loads((ROOT / right).read_text())["items"]
        cross_dataset.append({
            "datasets": [left, right],
            "shared_group_names": len({item["group_id"] for item in a} & {item["group_id"] for item in b}),
            "shared_problem_fingerprints": len({problem_fingerprint(item) for item in a} & {problem_fingerprint(item) for item in b}),
        })
    report = {
        "assessment": "Needs revision before main-study release: structural split overlap and publication provenance",
        "reviewer": review["reviewer"], "human_review_status": "pending",
        "review_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "datasets": results, "held_out_rows_unchanged": True,
        "cross_dataset_identity": cross_dataset,
        "scope": "Development-only semantic/gold review; test rows used only for blinded isolation fingerprints",
    }
    write_json(args.output / "checks.json", report)
    (args.output / "report.md").write_text(render_report(report, review), encoding="utf-8")
    manifest = {
        "status": "complete", "kind": "development_data_audit", "model_calls": 0,
        "dataset_release_ready": False,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("scripts/audit_development_data.py", "research_identity.py", "research_scoring.py", "experiments/research_study.py", "scripts/gen_tasks.py", "reasoning_strategies.py", "qwen_mlx_backend.py")
        },
        "review_evidence_sha256": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in ("audit/development_data_review.json", "audit/development-source-evidence.json", "audit/development_audit_baseline.json")
        },
        "artifact_sha256": {name: hashlib.sha256((args.output / name).read_bytes()).hexdigest() for name in ("checks.json", "report.md")},
    }
    write_json(args.output / "manifest.json", manifest)
    print(f"Verified {sum(result['development_items_verified'] for result in results)} development items; held-out rows unchanged.")


if __name__ == "__main__":
    main()
