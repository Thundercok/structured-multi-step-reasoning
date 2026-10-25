from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import Counter
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from contradiction_auditor import audit_answer, build_index, infer_query_condition, V
except ImportError:
    from rat.engine.contradiction_auditor import audit_answer, build_index, infer_query_condition, V


def dig(d: Any, key: str | None) -> Any:
    if not key or d is None:
        return None
    curr = d
    for part in key.split("."):
        if isinstance(curr, dict):
            curr = curr.get(part)
        elif isinstance(curr, (list, tuple)) and part.isdigit():
            idx = int(part)
            curr = curr[idx] if 0 <= idx < len(curr) else None
        else:
            return None
    return curr


def text_of(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("text") or v.get("content") or v.get("snippet") or v.get("excerpt") or json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "\n".join(text_of(x) for x in v if x)
    return str(v)


def run_smoke(calls_path: str, source_key: str, answer_key: str, query_key: str | None = None, id_key: str | None = None):
    gate_counts = Counter()
    total_calls = 0
    total_quant_checked = 0
    total_satisfied = 0
    total_conflict = 0
    total_unverified = 0
    total_unparsed = 0
    total_sentences = 0
    total_sentences_no_num = 0
    blocks = []

    with open(calls_path, encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue

            src = text_of(dig(row, source_key))
            ans = text_of(dig(row, answer_key))
            q = text_of(dig(row, query_key)) if query_key else ""
            cid = str(dig(row, id_key)) if id_key and dig(row, id_key) is not None else f"call_{idx:04d}"

            if not src.strip() or not ans.strip():
                continue

            total_calls += 1
            kb = build_index(src)
            q_cond = infer_query_condition(q) if q else None
            rep = audit_answer(ans, kb, q_cond)

            gate_counts[rep.gate] += 1
            s = rep.summary
            total_quant_checked += s["quantitative_checked"]
            total_satisfied += s["satisfied"]
            total_conflict += s["conflict"]
            total_unverified += s["unverified"]
            total_unparsed += s["unparsed"]
            total_sentences += s["sentences"]
            total_sentences_no_num += s["sentences_without_numbers"]

            if rep.gate == "BLOCK":
                confl_findings = [f for f in rep.findings if f.result.verdict == V.GROUNDING_CONFLICT]
                blocks.append((cid, q, ans, confl_findings, kb))

    print(f"\n=== SMOKE CALLS REPORT: {calls_path} ===")
    print(f"Total calls audited: {total_calls}")
    print(f"Gates distribution: {dict(gate_counts)}")
    print(f"Quantitative claims checked: {total_quant_checked}")
    print(f"  - Satisfied:  {total_satisfied}")
    print(f"  - Conflicts:  {total_conflict}")
    print(f"  - Unverified: {total_unverified}")
    print(f"Unparsed atoms: {total_unparsed}")
    print(f"Sentences: {total_sentences} (without numbers: {total_sentences_no_num})")
    coverage_pct = (total_quant_checked / max(1, total_quant_checked + total_unparsed)) * 100.0
    print(f"Quantitative Coverage: {coverage_pct:.2f}%\n")

    if blocks:
        print(f"--- BLOCKS ENCOUNTERED ({len(blocks)}) ---")
        for cid, q, ans, findings, kb in blocks:
            print(f"\n[ID: {cid}]")
            if q:
                print(f"  Query:  {q}")
            print(f"  Answer: {ans[:200]!r}")
            for f in findings:
                print(f"  Finding: {f.text} -> {f.result.reason}")
                if f.tup:
                    k = (f.tup.metric, f.tup.unit)
                    cand = kb.get(k, [])
                    print(f"    Source candidates for {k}:")
                    for c in cand:
                        print(f"      - {c.text} (op={c.op}, val={c.value}, cond={c.condition})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Audit each answer against its own source")
    ap.add_argument("calls", help="Path to calls.jsonl")
    ap.add_argument("--source-key", default="source", help="Field path for source text")
    ap.add_argument("--answer-key", default="answer", help="Field path for answer text")
    ap.add_argument("--query-key", default=None, help="Field path for query")
    ap.add_argument("--id-key", default=None, help="Field path for call ID")
    args = ap.parse_args()

    run_smoke(args.calls, args.source_key, args.answer_key, args.query_key, args.id_key)
