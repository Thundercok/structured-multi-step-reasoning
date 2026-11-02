import json
import re
import sys

ROOT = "/Users/thundercock2/Documents/Github/multi-step-structured-reasoning"
sys.path.insert(0, ROOT)
from structured_llm.trace import calc_is_correct

records = json.load(open(f"{ROOT}/runs/gsm8k-qwen3-8b-staged-pilot-reviewed93-20261031/records.json"))
EQ = re.compile(r"([\d.,]+(?:\s*[-+*/x×÷]\s*[\d.,]+)+)\s*=\s*\$?\s*(-?[\d.,]*\d)")


def arithmetic_errors(text):
    bad = []
    for expr, result in EQ.findall(text.replace("\\times", "*").replace("\\div", "/").replace("\\", "")):
        clean = expr.replace(",", "").replace("x", "*").replace("×", "*").replace("÷", "/")
        if not calc_is_correct(clean, result.replace(",", "")):
            bad.append(f"{expr}={result}")
    return bad


def auroc(wrong_scores, right_scores):
    pairs = [(w < r) + 0.5 * (w == r) for w in wrong_scores for r in right_scores]
    return sum(pairs) / len(pairs) if pairs else None


by_item = {}
for record in records:
    by_item.setdefault(record["id"], {})[record["strategy"]] = record

for strategy in ("DIRECT", "COT", "PAL"):
    rows = [r for r in records if r["strategy"] == strategy]
    wrong = [r for r in rows if not r["correct"]]
    right = [r for r in rows if r["correct"]]
    print(strategy, "correct", len(right), "/", len(rows), "mean tokens",
          round(sum(r["tokens"] for r in rows) / len(rows), 1),
          "logprob AUROC", None if not wrong else round(auroc(
              [r["confidence"] for r in wrong], [r["confidence"] for r in right]), 3))

cot = [r for r in records if r["strategy"] == "COT"]
wrong = [r for r in cot if not r["correct"]]
right = [r for r in cot if r["correct"]]
output = lambda r: r["trace"]["generations"][0]["output"]
flag_wrong = sum(bool(arithmetic_errors(output(r))) for r in wrong)
flag_right = sum(bool(arithmetic_errors(output(r))) for r in right)
print(f"\nCoT arithmetic check: flags {flag_wrong}/{len(wrong)} wrong, {flag_right}/{len(right)} right")


def same(a, b):
    try:
        return abs(float(str(a).replace(",", "")) - float(str(b).replace(",", ""))) < 1e-6
    except (TypeError, ValueError):
        return False


disagree_wrong = sum(not same(r["answer"], by_item[r["id"]]["PAL"]["answer"]) for r in wrong)
disagree_right = sum(not same(r["answer"], by_item[r["id"]]["PAL"]["answer"]) for r in right)
print(f"CoT vs PAL disagreement: flags {disagree_wrong}/{len(wrong)} wrong, {disagree_right}/{len(right)} right")

print("\n--- every wrong CoT output")
dataset = json.load(open(f"{ROOT}/runs/gsm8k-qwen3-8b-staged-pilot-reviewed93-20261031/dataset.json"))
items = dataset["items"] if isinstance(dataset, dict) else dataset
gold = {item["id"]: item for item in items}
for r in wrong:
    print(f"\n[{r['id']}] gold={gold[r['id']]['answer']} cot={r['answer']} pal={by_item[r['id']]['PAL']['answer']} "
          f"conf={r['confidence']:.3f} tokens={r['tokens']} arith={arithmetic_errors(output(r))}")
    print("Q:", gold[r["id"]]["query"][:420])
    print("A:", output(r)[:520].replace("\n", " | "))
