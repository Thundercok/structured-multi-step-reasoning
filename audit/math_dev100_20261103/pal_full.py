"""Rescore the saved base_pal programs with the full interpreter, so gate 3b measures the model, not the reader."""
import collections
import json
import signal
import sys
from pathlib import Path

from structured_llm.math_check import same_answer
from structured_llm.pal import refusal, run_program

HERE = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent


class Timeout(Exception):
    pass


def alarm(*_):
    raise Timeout


signal.signal(signal.SIGALRM, alarm)
rows, reasons = [], collections.Counter()
for line in (HERE / "base_pal.jsonl").open():
    row = json.loads(line)
    signal.alarm(30)
    try:
        value = run_program(row["output"], full=True)
        reason = refusal(row["output"]) if value is None else None
    except Timeout:
        value, reason = None, "timeout"
    finally:
        signal.alarm(0)
    correct = value is not None and same_answer(repr(value), row["gold"])
    reasons[reason or "ran"] += 1
    rows.append({"id": row["id"], "gold": row["gold"], "value": value, "correct": correct, "refused": reason,
                 "truncated": row["truncated"]})

unknown = sum(row["value"] is None for row in rows)
summary = {
    "n": len(rows), "ran": len(rows) - unknown, "correct": sum(row["correct"] for row in rows), "no_value": unknown,
    "correct_if_every_no_value_were_right": sum(row["correct"] for row in rows) + unknown,
    "reasons": reasons.most_common(),
}
(HERE / "pal_full.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False) + "\n")
print(json.dumps(summary, indent=1))
for row in rows:
    if row["value"] is not None and not row["correct"]:
        print(row["id"], "gold", row["gold"], "value", row["value"])
