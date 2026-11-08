"""Secondary, exploratory cuts of signal B on the 200 new problems. None of these were fixed before the run."""
import json
import re
from pathlib import Path

from structured_llm.analyze import wilson
from structured_llm.evaluate import score
from structured_llm.math_check import final_answer, same_answer

HERE = Path(__file__).parent
pal = {row["id"]: row for row in json.load((HERE / "pal_full.json").open())["rows"]}
rows = [json.loads(line) for line in (HERE / "base_showcalc.jsonl").open()]
data = []
for row in rows:
    value = pal[row["id"]]["value"]
    found = final_answer("<think>\n\n</think>\n\n" + row["output"])
    data.append({
        "id": row["id"],
        "right": score("base_showcalc", row["output"], row["question"], row["gold"], "latex")["correct"],
        "state": "no_value" if value is None else ("agree" if same_answer(found, repr(value)) else "differ"),
        "numeric": bool(re.fullmatch(r"-?[\d,]+(?:\.\d+)?", row["gold"].strip())),
        "truncated": row["truncated"],
    })


def rate(hit, pool):
    pool = list(pool)
    count = sum(hit(item) for item in pool)
    return {"count": f"{count}/{len(pool)}", "ci": wilson(count, len(pool)) if pool else None}


wrong = [d for d in data if not d["right"]]
right = [d for d in data if d["right"]]
differ = lambda d: d["state"] == "differ"
out = {
    "states": {s: {"right": sum(d["state"] == s for d in right), "wrong": sum(d["state"] == s for d in wrong)}
               for s in ("agree", "differ", "no_value")},
    "right_when_agree": rate(lambda d: d["right"], (d for d in data if d["state"] == "agree")),
    "right_overall": rate(lambda d: d["right"], data),
    "share_agree": rate(lambda d: d["state"] == "agree", data),
    "numeric_gold": {"caught": rate(differ, (d for d in wrong if d["numeric"])),
                     "false_alarm": rate(differ, (d for d in right if d["numeric"]))},
    "symbolic_gold": {"caught": rate(differ, (d for d in wrong if not d["numeric"])),
                      "false_alarm": rate(differ, (d for d in right if not d["numeric"]))},
    "not_truncated": {"caught": rate(differ, (d for d in wrong if not d["truncated"])),
                      "false_alarm": rate(differ, (d for d in right if not d["truncated"]))},
    "truncated_flag_alone": {"caught": rate(lambda d: d["truncated"], wrong), "false_alarm": rate(lambda d: d["truncated"], right)},
    "flag_differ_or_no_value": {"caught": rate(lambda d: d["state"] != "agree", wrong),
                                "false_alarm": rate(lambda d: d["state"] != "agree", right)},
}
# Read by hand after scoring. The frozen scorer stays as it is; this shows how much these cases move signal B.
SCORER_MISSES = ("8670a0", "291ac8", "0a3182")  # 72 for 72 degrees, 105 for 105 degrees, 3.175 for 11*sqrt(3)/6.
PROMPT_ARTEFACTS = ("3227cd", "ca68c0", "3ac26b", "0d2baa", "33783f")  # 2304 for 2304*pi, 910 for 9/10 and the like.
fixed = [{**d, "right": d["right"] or d["id"].startswith(SCORER_MISSES + PROMPT_ARTEFACTS)} for d in data]
out["if_read_cases_counted_right"] = {
    "correct": sum(d["right"] for d in fixed),
    "caught": rate(differ, (d for d in fixed if not d["right"])),
    "false_alarm": rate(differ, (d for d in fixed if d["right"])),
}
(HERE / "secondary.json").write_text(json.dumps(out, indent=1) + "\n")
print(json.dumps(out))
