"""Recheck saved agent derivations and source selection; no inference or writes."""
import ast
from fractions import Fraction
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rational(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return Fraction(node.value)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -rational(node.operand)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "F" and not node.keywords and len(node.args) in (1, 2):
        args = [rational(v) for v in node.args]
        return args[0] if len(args) == 1 else args[0] / args[1]
    if isinstance(node, ast.BinOp):
        a, b = rational(node.left), rational(node.right)
        if isinstance(node.op, ast.Add): return a + b
        if isinstance(node.op, ast.Sub): return a - b
        if isinstance(node.op, ast.Mult): return a * b
        if isinstance(node.op, ast.Div): return a / b
        if isinstance(node.op, ast.Pow) and b.denominator == 1 and abs(b) <= 12: return a ** int(b)
    raise ValueError("Unsupported audit arithmetic")


def main():
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.prepare_gsm8k_development import build_items
    from experiments.research_study import normalized_text
    path = ROOT / "data/gsm8k_development_validation_candidate_v1/dataset.json"
    before = sha(path)
    dataset = json.loads(path.read_text())
    manifest = json.loads((path.parent / "manifest.json").read_text())
    assert before == manifest["dataset_sha256"]
    locks = json.loads((OUT / "derivation_lock.json").read_text())
    derivations = []
    for name, expected in sorted(locks.items()):
        assert sha(OUT / name) == expected
        derivations.extend(json.loads((OUT / name).read_text()))
    assert len(derivations) == len({r["id"] for r in derivations}) == 96
    items = {i["id"]: i for i in dataset["items"]}
    mismatches = []
    for row in derivations:
        item = items[row["id"]]
        assert hashlib.sha256(item["query"].encode()).hexdigest() == row["query_sha256"]
        value = rational(ast.parse(row["expression"], mode="eval").body)
        assert value == Fraction(row["independent_answer"])
        if value != Fraction(item["answer"]): mismatches.append(item["id"])
    assert set(mismatches) == {"gsm8k-dev-02343", "gsm8k-dev-00484", "gsm8k-dev-03823"}
    source = ROOT / "audit/gsm8k-source-20261004"
    provenance = json.loads((source / "manifest.json").read_text())
    for name, metadata in provenance["files"].items():
        assert sha(source / name) == metadata["sha256"]
    rows = [json.loads(v) for v in (source / "train.jsonl").read_text().splitlines()]
    old = json.loads((ROOT / "data/gsm8k_development_v1/dataset.json").read_text())
    excluded = {hashlib.sha256(normalized_text(i["query"]).encode()).hexdigest() for i in old["items"]}
    rebuilt, _, _ = build_items(rows, provenance["revision"], 96, 42, exclude_identities=excluded)
    assert rebuilt == dataset["items"] and sha(path) == before
    print("PASS: 96 rational derivations, 93 gold agreements, 3 disclosed disputes; source/ranking intact; no model calls.")


if __name__ == "__main__":
    main()
