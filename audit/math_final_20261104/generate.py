"""Generate one stage of the last run. Outputs are appended, so a stopped run resumes.

Run: python audit/math_final_20261104/generate.py {solution,independent,translated} DATA OUT_DIR [LIMIT]
Programs are generated only after the labels of the wrong solutions are frozen; see docs/research_plan.md.
"""
import json
import re
import sys
import time
from pathlib import Path

from structured_llm.evaluate import _EMPTY_THINK, model_path, read_jsonl
from structured_llm.gsm8k import chatml_prompt

MAX_TOKENS = 2048
SOLVE = ("Write every calculation explicitly, one per line, in plain English without markdown or LaTeX. "
         "End with exactly one line 'Answer: ' followed only by the final answer in simplest exact form, without units.")
_ALLOWED = ("You may import math, itertools and fractions. Do not use numpy, sympy or any other library. "
            "Return only code in one ```python``` block.")
INDEPENDENT = f"Write Python code to solve this problem and assign the final numeric answer to `result`. {_ALLOWED}"
TRANSLATED = ("Translate the solution below into Python code that follows the same steps and assign its final numeric "
              f"answer to `result`. {_ALLOWED}")
_ANSWER_LINE = re.compile(r"\n?^Answer:[^\n]*\s*\Z", re.M)


def without_answer(solution):
    """Drop the closing Answer line, so a program cannot simply copy it."""
    return _ANSWER_LINE.sub("", solution).rstrip()


def prompt_for(stage, item, solution):
    if stage == "solution":
        text = f"{item['question']}\n{SOLVE}"
    elif stage == "independent":
        text = f"{item['question']}\n{INDEPENDENT}"
    else:
        text = f"Problem:\n{item['question']}\n\nSolution:\n{without_answer(solution)}\n\n{TRANSLATED}"
    return chatml_prompt(text) + _EMPTY_THINK


def main(stage, data, out, limit=None):
    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    out.mkdir(parents=True, exist_ok=True)
    file = out / f"{stage}.jsonl"
    done = {record["id"] for record in read_jsonl(file)}
    solutions = {row["id"]: row["output"] for row in read_jsonl(out / "solution.jsonl")}
    model, tokenizer = load(model_path())
    sampler = make_sampler(temp=0.0)
    with file.open("a") as handle:
        for item in read_jsonl(data)[:limit]:
            if item["id"] in done:
                continue
            start = time.perf_counter()
            text = generate(model, tokenizer, prompt=prompt_for(stage, item, solutions.get(item["id"])),
                            max_tokens=MAX_TOKENS, sampler=sampler, verbose=False)
            tokens = len(tokenizer.encode(text))
            handle.write(json.dumps({"id": item["id"], "question": item["question"], "gold": item["answer"], "output": text,
                                     "tokens": tokens, "truncated": tokens >= MAX_TOKENS,
                                     "seconds": round(time.perf_counter() - start, 2)}, ensure_ascii=False) + "\n")
            handle.flush()


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else None)
