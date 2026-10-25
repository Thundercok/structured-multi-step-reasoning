"""Blind labelling for the P0 gold set. The auditor's verdict is NEVER shown to the labeller.

    python label_sheet.py export calls.jsonl --out sheet.csv  [--source-key K --answer-key K --query-key K --id-key K]
    # a human fills the `expected_gate` column with BLOCK | REGENERATE | ANNOTATE | PASS (see eval_gold.py for meaning)
    python label_sheet.py import sheet.csv calls.jsonl --out gold/real.jsonl [same keys]
    python eval_gold.py gold/real.jsonl

`origin` of imported rows is "llm_real" (only these rows count as recall evidence). Rows left blank are skipped and counted.
Split dev/test BY QUERY before tuning anything (see HANDOFF section 9): the `split` column is assigned by a hash of the query.
"""
import argparse
import csv
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from smoke_calls import dig, text_of
except ImportError:
    from scripts.smoke_calls import dig, text_of

LABELS = {"BLOCK", "REGENERATE", "ANNOTATE", "PASS"}
COLS = ["id", "split", "query", "answer", "source", "expected_gate", "note"]


def rows(a):
    for i, line in enumerate(open(a.calls, encoding="utf-8")):
        if line.strip():
            r = json.loads(line)
            q = text_of(dig(r, a.query_key)) if a.query_key else ""
            rid = str(dig(r, a.id_key)) if a.id_key and dig(r, a.id_key) is not None else f"r{i:05d}"
            yield rid, q, text_of(dig(r, a.answer_key)), text_of(dig(r, a.source_key)), r


def split_of(query):
    return "test" if int(hashlib.sha256(query.encode()).hexdigest(), 16) % 2 else "dev"


def export(a):
    n = 0
    with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        for rid, q, ans, src, _ in rows(a):
            if ans.strip() and src.strip():
                w.writerow({"id": rid, "split": split_of(q or rid), "query": q, "answer": ans, "source": src, "expected_gate": "", "note": ""})
                n += 1
    print(f"exported {n} rows to {a.out}; fill `expected_gate` BEFORE running the auditor")


def import_(a):
    lab = {r["id"]: r for r in csv.DictReader(open(a.sheet, encoding="utf-8-sig"))}
    out = skipped = 0
    with open(a.out, "w", encoding="utf-8") as f:
        for rid, q, ans, src, _ in rows(a):
            r = lab.get(rid)
            g = (r or {}).get("expected_gate", "").strip().upper()
            if g not in LABELS:
                skipped += 1
                continue
            f.write(json.dumps({"id": rid, "origin": "llm_real", "split": r["split"], "source": src, "answer": ans,
                                "query_condition": None, "query": q, "expected_gate": g, "tags": [],
                                "note": r.get("note", "")}, ensure_ascii=False) + "\n")
            out += 1
    print(f"wrote {out} labelled rows to {a.out}; skipped {skipped} unlabelled/invalid")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["export", "import"])
    ap.add_argument("first")
    ap.add_argument("second", nargs="?")
    ap.add_argument("--out", required=True)
    ap.add_argument("--source-key", default="source")
    ap.add_argument("--answer-key", default="answer")
    ap.add_argument("--query-key", default=None)
    ap.add_argument("--id-key", default=None)
    a = ap.parse_args()
    if a.cmd == "export":
        a.calls = a.first
        export(a)
    else:
        if not a.second:
            sys.exit("import needs: sheet.csv calls.jsonl")
        a.sheet, a.calls = a.first, a.second
        import_(a)
