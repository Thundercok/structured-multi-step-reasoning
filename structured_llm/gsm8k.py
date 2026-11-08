"""Convert GSM8K train solutions into structured traces and split them.

Run: python -m structured_llm.gsm8k

The official GSM8K test file is never read. The 120 questions already used for
development are excluded. Splits are assigned by hash rank before any filtering,
so the held-out sets do not depend on labels or on whether conversion succeeds.
"""

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path

from .trace import Step, calc_is_correct, check, render

SOURCE = Path("data/gsm8k_source/train.jsonl")
SOURCE_SHA256 = "17f347dc51477c50d4efb83959dbb7c56297aba886e5544ee2aaed3024813465"
USED_FOR_DEVELOPMENT = (
    "data/gsm8k_development_v1/dataset.json",
    "data/gsm8k_development_validation_candidate_v1/dataset.json",
)
OUTPUT = Path("data/structured_gsm8k_v1")
SEED = "structured-gsm8k-v1"
N_VALID, N_DEV = 100, 100

_ANNOTATION = re.compile(r"<<(.*?)>>")
_FINAL = re.compile(r"####\s*(.+)")


def normalize(question):
    return " ".join(question.lower().split())


def rank_key(question):
    return hashlib.sha256(f"{SEED}:{normalize(question)}".encode()).hexdigest()


def gold_answer(solution):
    return _FINAL.search(solution)[1].strip().replace(",", "").replace("$", "")


def enrich_step1_prose(prose):
    """Enrich Step 1 prose with explicit 'Calculate the ...' quantity specification."""
    p = prose.strip()

    # 1. Already starts with "Calculate the" or "Calculate"
    if re.match(r"^Calculate\s+the\b", p, re.I):
        return p
    if re.match(r"^Calculate\b", p, re.I):
        return ("Calculate the " + p[9:].lstrip(": ")).strip()

    # 2. "First/To begin/Initially (find|calculate|determine|compute) (the) <target>"
    m = re.match(r"^(?:First|To begin|Initially|First of all),?\s*(?:find|calculate|determine|compute)\s+(?:the\s+)?(.*)$", p, re.I)
    if m:
        target = m.group(1).strip().lstrip(": ")
        return f"Calculate the {target}"

    # 3. "(Find|Determine|Compute) (the) <target>"
    m = re.match(r"^(?:Find|Determine|Compute)\s+(?:the\s+)?(.*)$", p, re.I)
    if m:
        target = m.group(1).strip().lstrip(": ")
        return f"Calculate the {target}"

    # 4. "The <target> (is|was|are|were|=) <rest>" (PRIORITY OVER costs verb)
    m = re.match(r"^The\s+(.+?)\s+\b(is|was|are|were|=)\b\s+(.*)$", p, re.I)
    if m and len(m.group(1).split()) <= 15:
        target = m.group(1).strip().rstrip(": ")
        rest = m.group(3).strip().lstrip(": ")
        return f"Calculate the {target}: {rest}"

    # 5. "The <target> costs <rest>" (e.g. "The popcorn costs 8 - 3 = $5")
    m_cost = re.match(r"^The\s+(.+?)\s+\bcosts?\b\s+(.*)$", p, re.I)
    if m_cost and len(m_cost.group(1).split()) <= 6:
        item = m_cost.group(1).strip().rstrip(": ")
        rest = m_cost.group(2).strip().lstrip(": ")
        return f"Calculate the cost of the {item}: {rest}"

    # 6. "The <something> ..." fallback
    if re.match(r"^The\s+", p, re.I):
        return "Calculate the " + p[4:].strip()

    # 7. "There are/were/is/was <N> <unit> ..."
    m = re.match(r"^There (?:are|were|is|was)\s+(.*?)(?:because|\.|$)", p, re.I)
    if m:
        clause = m.group(1).strip()
        m_u = re.search(r"=\s*\$?\d[\d,]*(?:\.\d+)?\s+([a-zA-Z\s\x27-]+?)(?:\s+in\b|\s+on\b|\s+at\b|\s+for\b|\s+left\b|\s+total\b|\.|$)", clause)
        if m_u:
            unit = m_u.group(1).strip()
            unit = re.sub(r"\s+(?:are|is|was|were|in|of|for|on|at|to|the|a|an|that|with)$", "", unit).strip()
            words = unit.split()
            if 1 <= len(words) <= 4 and not any(w in words for w in ["because", "since", "so", "and", "then", "which"]):
                return f"Calculate the number of {unit}: {p}"
        return f"Calculate the number: {p}"

    # 8. Time
    for t in ["hours", "days", "weeks", "minutes", "months", "years"]:
        if re.search(rf"\b{t}\b", p.lower()):
            return f"Calculate the total {t}: {p}"

    # 9. Money: contains $ or cost/price/spent/paid/earned
    if "$" in p or any(w in p.lower() for w in ["cost", "price", "fee"]):
        return f"Calculate the cost: {p}"
    if any(w in p.lower() for w in ["earned", "makes", "earns"]):
        return f"Calculate the earnings: {p}"
    if any(w in p.lower() for w in ["paid", "spent", "spends"]):
        return f"Calculate the amount spent: {p}"

    # 10. Look for unit after number/equation: "800*.2=160 words"
    m_u = re.search(r"=\s*\$?(\d[\d,]*(?:\.\d+)?)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)\b", p)
    if m_u:
        unit = m_u.group(2).lower().strip()
        unit = re.sub(r"\s+(?:are|is|was|were|in|of|for|on|at|to|the|a|an|that|with)$", "", unit).strip()
        words = unit.split()
        if not any(w in ["because", "since", "so", "and", "then", "which", "more", "less", "times", "marks", "each"] for w in words):
            return f"Calculate the number of {unit}: {p}"

    # 11. General fallback
    return f"Calculate the value: {p}"


def convert(row, enrich_step1=False):
    """Return (trace text, None), or (None, reason) if the solution doesn't qualify."""
    steps = []
    for line in row["answer"].split("\n"):
        if line.startswith("####"):
            continue
        calcs = []
        for annotation in _ANNOTATION.findall(line):
            expr, _, result = annotation.rpartition("=")
            calcs.append((expr.strip(), result.strip()))
        prose = " ".join(_ANNOTATION.sub("", line).split())
        if prose:
            steps.append(Step(prose, calcs))
        elif calcs:
            return None, "calc_without_prose"
    if not any(step.calcs for step in steps):
        return None, "no_annotations"
    if not all(calc_is_correct(*calc) for step in steps for calc in step.calcs):
        return None, "wrong_or_unparsable_annotation"
    if enrich_step1 and steps:
        steps[0].text = enrich_step1_prose(steps[0].text)
    text = render(steps, gold_answer(row["answer"]))
    if check(text, row["question"])["errors"]:
        return None, "fails_own_grammar"
    return text, None


def chatml_prompt(user):
    """Qwen3 chat template with thinking enabled, so the trace is its thinking."""
    return f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"


def training_row(row, trace):
    return {"text": f"{chatml_prompt(row['question'])}{trace}<|im_end|>"}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mean(values):
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else None


def used_questions():
    used = set()
    for path in USED_FOR_DEVELOPMENT:
        used |= {normalize(item["query"]) for item in json.loads(Path(path).read_text())["items"]}
    return used


def load_splits(source=SOURCE):
    """Return (train, valid, dev) source rows, with all excluded questions removed."""
    raw = Path(source).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise SystemExit(f"{source} does not match the pinned SHA-256")
    rows = [json.loads(line) for line in raw.decode().splitlines()]

    used = used_questions()
    pool = sorted((row for row in rows if normalize(row["question"]) not in used),
                  key=lambda row: rank_key(row["question"]))
    excluded = len(rows) - len(pool)
    if excluded != len(used):
        raise SystemExit(f"excluded {excluded} rows for {len(used)} development questions")

    return pool[N_VALID + N_DEV:], pool[:N_VALID], pool[N_VALID:N_VALID + N_DEV]


def build(source=SOURCE, output=OUTPUT, enrich_step1=False):
    train, valid, dev = load_splits(source)
    rows = len(train) + len(valid) + len(dev)

    dropped = collections.Counter()
    def converted(split):
        kept = []
        for row in split:
            trace, reason = convert(row, enrich_step1=enrich_step1)
            if trace is None:
                dropped[reason] += 1
            else:
                kept.append((row, trace))
        return kept

    train_kept, valid_kept = converted(train), converted(valid)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    hashes = {
        "train.jsonl": write_jsonl(output / "train.jsonl", [training_row(*pair) for pair in train_kept]),
        "valid.jsonl": write_jsonl(output / "valid.jsonl", [training_row(*pair) for pair in valid_kept]),
        "dev.jsonl": write_jsonl(output / "dev.jsonl", [
            {"id": rank_key(row["question"])[:16], "question": row["question"],
             "answer": gold_answer(row["answer"])} for row in dev]),
    }

    # What a perfect gold trace scores: the ceiling for the soft metrics.
    gold = [check(trace, row["question"], gold_answer(row["answer"])) for row, trace in train_kept]
    manifest = {
        "source_sha256": SOURCE_SHA256,
        "source_rows": rows + len(used_questions()),
        "excluded_development_questions": len(used_questions()),
        "official_test_read": False,
        "seed": SEED,
        "enrich_step1": enrich_step1,
        "split_rows": {"train": len(train), "valid": len(valid), "dev": len(dev)},
        "converted_rows": {"train": len(train_kept), "valid": len(valid_kept)},
        "dropped": dict(dropped),
        "gold_ceiling": {
            "calc_accuracy": _mean(item["calc_accuracy"] for item in gold),
            "grounded_rate": _mean(item["grounded_rate"] for item in gold),
            "answer_from_last_calc": _mean(float(item["answer_from_last_calc"]) for item in gold),
            "correct": _mean(float(item["correct"]) for item in gold),
        },
        "sha256": hashes,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output", default=None)
    parser.add_argument("--enrich", action="store_true", help="Enrich Step 1 prose with 'Calculate the ...'")
    args = parser.parse_args()
    out = args.output
    if out is None:
        out = Path("data/structured_gsm8k_enriched_v1") if args.enrich else OUTPUT
    print(json.dumps(build(args.source, out, enrich_step1=args.enrich), indent=2))
