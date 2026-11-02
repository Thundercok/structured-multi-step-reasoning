"""Compare the fine-tuned model with the base model on a held-out split.

Run: python -m structured_llm.evaluate --adapter adapters/smoke --limit 20 --out audit/run

tuned            adapter, plain question
tuned_tool       as tuned, but the runtime computes each Calc result
base_instructed  no adapter, format and one example in the prompt: what asking gets without training
base_tool        as base_instructed, but the runtime computes each Calc result
base_showcalc    no adapter, thinking off, told to write every calculation in plain text
base_native      no adapter, plain question, the model's own free-form thinking
base_pal         no adapter, thinking off, writes a program that is then interpreted

Raw outputs are appended as they finish, so a stopped run resumes where it left off.
"""

import argparse
import hashlib
import json
import platform
import re
import time
from pathlib import Path

from .counterfactual import fmt
from .gsm8k import OUTPUT, chatml_prompt
from .pal import run_program
from .trace import check, evaluate_expr

MODEL_ID = "mlx-community/Qwen3-8B-4bit"
MODEL_REVISION = "545dc4251c05440727734bcd94334791f6ab0192"
MODES = ("tuned", "tuned_tool", "base_instructed", "base_tool", "base_showcalc", "base_native", "base_pal")
ADAPTER_MODES = ("tuned", "tuned_tool")
TOOL_MODES = ("tuned_tool", "base_tool")
_OPEN_CALC = re.compile(r"(?:^|\n)Calc: ([^=\n]+)=$")

INSTRUCTION = """Solve the problem. Think inside <think></think> in exactly this format, then give the final number.

Question: Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?
<think>
Step 1: Natalia sold 48/2 = 24 clips in May.
Calc: 48/2=24
Step 2: Natalia sold 48+24 = 72 clips altogether in April and May.
Calc: 48+24=72
</think>

Answer: 72

Question: """
SHOW_CALCULATIONS = ("Write every calculation explicitly, one per line, in plain English without markdown or LaTeX. "
                     "End with exactly one line 'Answer: ' followed only by the final number, without units.")
WRITE_PROGRAM = ("Write Python code to solve this problem and assign the final numeric answer to `result`. "
                 "Use arithmetic and built-in Python only, without imports. Return only code in one ```python``` block.")
_EMPTY_THINK = "<think>\n\n</think>\n\n"


def prompt_for(mode, question):
    if mode in ("base_instructed", "base_tool"):
        return chatml_prompt(INSTRUCTION + question)
    if mode == "base_showcalc":
        return chatml_prompt(f"{question}\n{SHOW_CALCULATIONS}") + _EMPTY_THINK
    if mode == "base_pal":
        return chatml_prompt(f"{question}\n{WRITE_PROGRAM}") + _EMPTY_THINK
    return chatml_prompt(question)


def score(mode, output, question, gold):
    """Thinking-off modes get their empty think block back so one scorer reads every mode."""
    if mode == "base_pal":
        value = run_program(output)
        text = _EMPTY_THINK if value is None else f"{_EMPTY_THINK}Answer: {value}"
    elif mode == "base_showcalc":
        text = _EMPTY_THINK + output
    else:
        text = output
    return check(text, question, gold)


def tool_result(text):
    """If text stops at "Calc: 48/2=", return what the runtime should write next, else None."""
    match = _OPEN_CALC.search(text)
    if not match:
        return None
    value = evaluate_expr(match[1])
    return None if value is None else fmt(value) + "\n"


def generate_text(mode, model, tokenizer, prompt, max_tokens, sampler):
    """Return (text, tool calls). In tool modes the runtime writes each Calc result.

    Each tool call restarts generation without a prompt cache, so seconds overstate the
    cost of tool modes; compare them on generated tokens.
    """
    from mlx_lm import generate, stream_generate

    if mode not in TOOL_MODES:
        return generate(model, tokenizer, prompt=prompt, max_tokens=max_tokens, sampler=sampler, verbose=False), 0
    text, generated, calls = "", 0, 0
    while generated < max_tokens:
        inserted = None
        for response in stream_generate(model, tokenizer, prompt + text, max_tokens=max_tokens - generated,
                                        sampler=sampler):
            generated += 1
            text += response.text
            inserted = tool_result(text)
            if inserted:
                break
        if not inserted:
            break
        text += inserted
        calls += 1
    return text, calls


def adapter_sha256(adapter):
    return hashlib.sha256((Path(adapter) / "adapters.safetensors").read_bytes()).hexdigest()


def model_path():
    from huggingface_hub import snapshot_download

    return snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_files_only=True)


def read_jsonl(path):
    path = Path(path)
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def is_flagged(result):
    """What a checker would raise on an output, without knowing the right answer."""
    return (not result["format_valid"] or result["calc_accuracy"] != 1.0
            or not result["answer_from_last_calc"])


def detection(records):
    wrong = [record for record in records if not record["check"]["correct"]]
    right = [record for record in records if record["check"]["correct"]]
    return {
        "wrong": len(wrong),
        "flagged_wrong": sum(is_flagged(record["check"]) for record in wrong),
        "right": len(right),
        "flagged_right": sum(is_flagged(record["check"]) for record in right),
    }


def summarize(records):
    def mean(key):
        values = [record["check"][key] for record in records if record["check"][key] is not None]
        return round(sum(values) / len(values), 3) if values else None

    return {
        "n": len(records),
        "correct": sum(bool(record["check"]["correct"]) for record in records),
        "answered": sum(record["check"]["answered"] for record in records),
        "format_valid": sum(record["check"]["format_valid"] for record in records),
        "calc_accuracy": mean("calc_accuracy"),
        "grounded_rate": mean("grounded_rate"),
        "mean_tokens": round(sum(record["tokens"] for record in records) / max(len(records), 1), 1),
        "mean_seconds": round(sum(record["seconds"] for record in records) / max(len(records), 1), 2),
        "truncated": sum(record["truncated"] for record in records),
        "detection": detection(records),
    }


def run(adapter, limit, out, modes, max_tokens, data):
    from mlx_lm import load
    from mlx_lm.sample_utils import make_sampler

    if set(modes) & set(ADAPTER_MODES) and not adapter:
        raise SystemExit("tuned modes need --adapter")
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    data = Path(data)
    items = read_jsonl(data)[:limit]
    (out / "manifest.json").write_text(json.dumps({
        "model": MODEL_ID,
        "revision": MODEL_REVISION,
        "adapter": str(adapter) if adapter else None,
        "adapter_sha256": adapter_sha256(adapter) if adapter else None,
        "data": str(data),
        "data_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        "limit": limit,
        "max_tokens": max_tokens,
        "temperature": 0.0,
        "machine": platform.platform(),
    }, indent=2) + "\n")

    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    sampler = make_sampler(temp=0.0)
    path, loaded = model_path(), None
    for mode in modes:
        wanted = adapter if mode in ADAPTER_MODES else None
        if loaded is None or loaded[0] != wanted:
            loaded = (wanted, *load(path, adapter_path=str(wanted) if wanted else None))
        _, model, tokenizer = loaded

        file = out / f"{mode}.jsonl"
        records = read_jsonl(file)
        done = {record["id"] for record in records}
        with file.open("a") as handle:
            for item in items:
                if item["id"] in done:
                    continue
                start = time.perf_counter()
                text, tool_calls = generate_text(mode, model, tokenizer, prompt_for(mode, item["question"]),
                                                 max_tokens, sampler)
                tokens = len(tokenizer.encode(text))
                record = {
                    "id": item["id"], "question": item["question"], "gold": item["answer"], "output": text,
                    "tokens": tokens, "truncated": tokens >= max_tokens, "tool_calls": tool_calls,
                    "seconds": round(time.perf_counter() - start, 2),
                    "check": score(mode, text, item["question"], item["answer"]),
                }
                records.append(record)
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
        summary[mode] = summarize(records)
        print(mode, json.dumps(summary[mode]), flush=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--out", required=True)
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--data", default=OUTPUT / "dev.jsonl")
    args = parser.parse_args()
    run(args.adapter, args.limit, args.out, args.modes, args.max_tokens, args.data)
