"""Gold-set evaluator.

    python scripts/eval_gold.py gold/seed.jsonl [--strict] [--show-ok]

JSONL row: {id, origin, source, answer, query_condition|null, expected_gate, tags, note, known_gap?}
`expected_gate` is the label a human assigns BEFORE running the auditor:
    BLOCK       answer contradicts the source
    REGENERATE  answer is right only for some programme but does not say which
    ANNOTATE    answer cannot be verified (programme unknown to KB) or is right only given the query
    PASS        nothing to flag
`known_gap` (string) marks a documented limitation: reported separately and never fails --strict.
`origin == "synthetic"` rows are NOT recall evidence; only real LLM answers labelled by a human are.
"""
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

try:
    from contradiction_auditor import audit_text, build_index, gate
except ImportError:
    from rat.engine.contradiction_auditor import audit_text, build_index, gate

CLASSES = ["BLOCK", "REGENERATE", "ANNOTATE", "PASS"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main(path, strict=False, show_ok=False):
    rows = load(path)
    cm = collections.Counter()
    bad, gaps, origins = [], [], collections.Counter(r.get("origin", "?") for r in rows)
    for r in rows:
        fs = audit_text(r["answer"], build_index(r["source"]), r.get("query_condition"))
        got, exp = gate(fs), r["expected_gate"]
        gap = r.get("known_gap")
        if not gap:
            cm[(exp, got)] += 1
        if got != exp:
            (gaps if gap else bad).append((r, got, fs))
        elif show_ok:
            print(f"ok   {r['id']:5} {exp}")
    n = sum(cm.values())
    print(f"rows={len(rows)} origins={dict(origins)} scored={n} known_gap={len(gaps)}")
    print("\nconfusion (rows = expected, cols = got), known_gap excluded")
    print(f"{'':12}" + "".join(f"{c:>12}" for c in CLASSES))
    for e in CLASSES:
        print(f"{e:12}" + "".join(f"{cm[(e, g)]:>12}" for g in CLASSES))
    print("\nper class  (precision = of the rows we labelled X, how many were X; recall = of true X, how many we caught)")
    for c in CLASSES:
        tp = cm[(c, c)]
        pred = sum(cm[(e, c)] for e in CLASSES)
        true = sum(cm[(c, g)] for g in CLASSES)
        p = f"{tp}/{pred}" if pred else "-"
        r_ = f"{tp}/{true}" if true else "-"
        print(f"  {c:11} precision {p:>7}   recall {r_:>7}")
    unsafe = [x for x in bad if x[0]["expected_gate"] == "BLOCK" and x[1] == "PASS"]
    fblock = [x for x in bad if x[1] == "BLOCK" and x[0]["expected_gate"] != "BLOCK"]
    print(f"\nmissed contradictions (expected BLOCK, got PASS): {len(unsafe)}   false blocks (got BLOCK, expected other): {len(fblock)}")

    def dump(title, items):
        if not items:
            return
        print(f"\n{title}")
        for r, got, fs in items:
            print(f"  {r['id']:5} expected={r['expected_gate']:10} got={got:10} [{','.join(r.get('tags', []))}] {r.get('note', '')}")
            if r.get("known_gap"):
                print(f"        known_gap: {r['known_gap']}")
            for f in fs:
                print(f"        {f.result.verdict.name:18} {(f.result.reason or '-')[:28]:28} {f.text[:60]!r}")
            if not fs:
                print("        (no findings)")

    dump("MISMATCHES", bad)
    dump("KNOWN GAPS (not scored)", gaps)
    if strict and bad:
        sys.exit(1)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "gold/seed.jsonl", "--strict" in sys.argv, "--show-ok" in sys.argv)
