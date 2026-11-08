"""Translate each saved base_showcalc solution into a program. Outputs are appended, so a stopped run resumes.

Run: python audit/math_translate_20261104/translate.py SOURCE_RUN OUT_DIR [LIMIT]
"""
import json
import re
import sys
import time
from pathlib import Path

from mlx_lm import generate, load
from mlx_lm.sample_utils import make_sampler

from structured_llm.evaluate import _EMPTY_THINK, model_path, read_jsonl
from structured_llm.gsm8k import chatml_prompt

MAX_TOKENS = 2048
TRANSLATE = ("Translate the solution below into Python code that follows the same steps and assign its final numeric "
             "answer to `result`. Use arithmetic and built-in Python only, without imports. "
             "Return only code in one ```python``` block.")
_ANSWER_LINE = re.compile(r"\n?^Answer:[^\n]*\s*\Z", re.M)


def without_answer(solution):
    """Drop the closing Answer line, so a program cannot simply copy it."""
    return _ANSWER_LINE.sub("", solution).rstrip()


def prompt_for(question, solution):
    return chatml_prompt(f"Problem:\n{question}\n\nSolution:\n{without_answer(solution)}\n\n{TRANSLATE}") + _EMPTY_THINK


def main(source, out, limit=None):
    out.mkdir(parents=True, exist_ok=True)
    file = out / "translated.jsonl"
    done = {record["id"] for record in read_jsonl(file)}
    model, tokenizer = load(model_path())
    sampler = make_sampler(temp=0.0)
    with file.open("a") as handle:
        for row in read_jsonl(source / "base_showcalc.jsonl")[:limit]:
            if row["id"] in done:
                continue
            start = time.perf_counter()
            text = generate(model, tokenizer, prompt=prompt_for(row["question"], row["output"]),
                            max_tokens=MAX_TOKENS, sampler=sampler, verbose=False)
            tokens = len(tokenizer.encode(text))
            handle.write(json.dumps({"id": row["id"], "output": text, "tokens": tokens, "truncated": tokens >= MAX_TOKENS,
                                     "seconds": round(time.perf_counter() - start, 2)}, ensure_ascii=False) + "\n")
            handle.flush()


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else None)
