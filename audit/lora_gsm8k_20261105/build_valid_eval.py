"""Turn the 99 training-format valid rows into the id/question/answer rows evaluate.py reads.

Run from the repo root: PYTHONPATH=. .venv/bin/python audit/lora_gsm8k_20261105/build_valid_eval.py
Ids follow dev.jsonl: the first 16 hex digits of rank_key(question).
"""

import hashlib
import json
from pathlib import Path

from structured_llm.gsm8k import rank_key
from structured_llm.trace import parse

SOURCE = Path("data/structured_gsm8k_v1/valid.jsonl")
OUT = Path("data/structured_gsm8k_v1/valid_eval.jsonl")

rows = []
for line in SOURCE.read_text().splitlines():
    text = json.loads(line)["text"]
    question = text.split("<|im_start|>user\n", 1)[1].split("<|im_end|>", 1)[0]
    trace = text.split("<|im_start|>assistant\n", 1)[1].removesuffix("<|im_end|>")
    answer = parse(trace).answer
    assert answer is not None, question
    rows.append({"id": rank_key(question)[:16], "question": question, "answer": answer})
assert len({row["id"] for row in rows}) == len(rows) == 99
OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
print(OUT, len(rows), hashlib.sha256(OUT.read_bytes()).hexdigest())
