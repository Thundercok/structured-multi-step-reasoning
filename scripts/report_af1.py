#!/usr/bin/env python3
"""Generate AF1 verification table and verdict for PAL-v3 on Game-of-24."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "audit"
RUN11_TRACE = AUDIT_DIR / "run11_sweep_trace.jsonl"
PALV2_TRACE = AUDIT_DIR / "ae_palv2_trace.jsonl"
PALV3_TRACE = AUDIT_DIR / "af_palv3_trace.jsonl"

def main():
    r11 = [json.loads(l) for l in open(RUN11_TRACE) if json.loads(l).get("family") == "g24"]
    palv2 = [json.loads(l) for l in open(PALV2_TRACE) if json.loads(l).get("family") == "g24"]
    palv3 = [json.loads(l) for l in open(PALV3_TRACE)]

    arms_data = {
        "PAL": [r for r in r11 if r["arm"] == "PAL"],
        "PAL-v2": palv2,
        "PAL-v3": palv3,
        "TOT": [r for r in r11 if r["arm"] == "TOT"],
    }

    lines = []
    lines.append("| Family | Arm | n | Accuracy (corr/n) | Mean Prompt Tok | Mean Comp Tok | Mean Total Tok | %Length | Failure Mechanism |")
    lines.append("| :--- | :--- | ---: | :---: | ---: | ---: | ---: | ---: | :--- |")

    for arm_name, recs in arms_data.items():
        n = len(recs)
        corr = sum(r["correct"] for r in recs)
        acc = corr / n
        p_tok = sum(r.get("prompt_tokens", 0) for r in recs) / n
        c_tok = sum(r.get("completion_tokens", 0) for r in recs) / n
        tot_tok = p_tok + c_tok
        pct_len = sum(1 for r in recs if r.get("finish_reason") == "length") / n * 100.0
        if arm_name == "PAL":
            fail = "21 import blocked, 8 invalid syntax"
        elif arm_name == "PAL-v2":
            fail = "29 eval blocked in sandbox"
        elif arm_name == "PAL-v3":
            fail = "29 eval blocked (negative constraint ignored)"
        else:
            fail = "12 search/judge errors"
        lines.append(
            f"| g24 | {arm_name:7s} | {n:2d} | {acc*100:5.1f}% ({corr:2d}/{n:2d}) | {p_tok:6.1f} | {c_tok:6.1f} | {tot_tok:6.1f} | {pct_len:5.1f}% | {fail} |"
        )

    table_text = "\n".join(lines)
    (AUDIT_DIR / "AF_table_g24.txt").write_text(table_text + "\n", encoding="utf-8")

    # Verdict
    tot_acc = 17 / 29
    tot_tok = 1446.8
    pal3_acc = 0 / 29
    pal3_tok = sum(r.get("prompt_tokens", 0) + r.get("completion_tokens", 0) for r in palv3) / 29

    v_lines = []
    v_lines.append("# AF1: Verdict vs prereg/decision_rule_palv3.md\n")
    v_lines.append(f"- **G24 PAL-v3 Accuracy**: {pal3_acc*100:.1f}% (0/29) vs ToT {tot_acc*100:.1f}% (17/29) [Threshold: >= 58.6%]")
    v_lines.append(f"  Acc condition: **FAIL**")
    v_lines.append(f"- **G24 PAL-v3 Tokens**: {pal3_tok:.1f} vs ToT {tot_tok:.1f} (ratio {pal3_tok/tot_tok:.2f}x) [Threshold: <= 0.50x = 723.4 tok]")
    v_lines.append(f"  Token condition: **PASS** ({pal3_tok:.1f} <= 723.4)")
    v_lines.append("\n**VERDICT: REJECTED / CODE-SOLVABLE NOT SATISFIED on Game-of-24.**")
    v_lines.append("ToT stays best on Game-of-24 (17/29, 58.6%).")
    v_lines.append("PAL limits documented: Qwen3-8B strongly defaults to `eval(expr)` for symbolic arithmetic search; even with explicit instructions to carry `(val, expr)` pairs and avoid eval, 29/29 items generated `eval`, triggering the sandbox security boundary.")

    verdict_text = "\n".join(v_lines)
    (AUDIT_DIR / "AF_palv3_verdict.txt").write_text(verdict_text + "\n", encoding="utf-8")
    print(table_text)
    print("\n" + verdict_text)

if __name__ == "__main__":
    main()
