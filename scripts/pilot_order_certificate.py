"""Development-only ordering pilot; mock never imports MLX or loads a model.

Completed generations/executions are journaled before the next call. Old
unlabelled directories, changed profiles, mixed evidence and corruption are
rejected. This is not a confirmatory collector or a security sandbox.
"""

from __future__ import annotations

import argparse
import copy
import gc
import importlib.metadata
import json
import math
import platform
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.order_certificate_study import (
    ARMS, METHODS, PROMPTS, SETTINGS, _selected_answer, evaluate, file_hash, validate_records,
    format_selector_candidates,
)
from experiments.order_pilot_checkpoint import PilotCheckpoint, atomic_json, atomic_text, digest
from reasoning_strategies import extract_code, run_python_sandboxed
from scripts.verified_pal_order import solve_order_query
from experiments.research_study import seed_for

# Deliberately lazy: importing this module or running --mock cannot import MLX.
load = stream_generate = make_sampler = mx = None


def _load_runtime():
    global load, stream_generate, make_sampler, mx
    try:
        from mlx_lm import load as mlx_load, stream_generate as mlx_stream
        from mlx_lm.sample_utils import make_sampler as mlx_sampler
        import mlx.core as mlx_core
    except ImportError as error:
        raise RuntimeError("MLX unavailable; use --mock for offline validation") from error
    load, stream_generate, make_sampler, mx = mlx_load, mlx_stream, mlx_sampler, mlx_core


def run_call(model, tokenizer, messages, *, max_tokens, temperature, enable_thinking, seed):
    if stream_generate is None or mx is None:
        raise RuntimeError("Real runtime must be explicitly loaded before generation")
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=enable_thinking,
    )
    mx.random.seed(seed)
    sampler = make_sampler(temperature)
    started = time.perf_counter()
    output, last = "", None
    try:
        for response in stream_generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler):
            output += response.text
            last = response
        wall_ms = (time.perf_counter() - started) * 1000.0
    finally:
        mx.clear_cache()
        gc.collect()
    # Require backend counters, including the final stream response. Chunk
    # counts/re-encoding rendered text are not interchangeable with model tokens.
    generated = getattr(last, "generation_tokens", None)
    prompt_count = getattr(last, "prompt_tokens", None)
    termination = getattr(last, "finish_reason", None)
    if (type(generated) is not int or not 0 <= generated <= max_tokens
            or type(prompt_count) is not int or prompt_count < 1
            or termination not in ("stop", "stop_answer", "length")):
        raise RuntimeError("Backend lacks complete final token/termination telemetry; preserve run for review")
    return {
        "messages": messages, "rendered_prompt": prompt, "output": output,
        "prompt_tokens": prompt_count, "completion_tokens": generated, "max_tokens": max_tokens,
        "finish_reason": termination, "wall_ms": wall_ms, "seed": seed,
        "enable_thinking": enable_thinking, "temperature": temperature,
    }


def _spec(item, seed, arm, index, settings, candidate_outputs=()):
    selector = arm == "candidate_selection" and index == 3
    suffix = PROMPTS["selector"] if selector else PROMPTS["candidate"] if arm == "candidate_selection" else PROMPTS[arm]
    content = item["query"] + "\n" + suffix
    if selector:
        content += "\n" + format_selector_candidates(candidate_outputs)
    cap = settings["selector_max_tokens"] if selector else settings["candidate_max_tokens"] if arm == "candidate_selection" else settings["thinking_max_tokens"] if arm == "thinking_native" else settings["pal_max_tokens"]
    temperature = settings["thinking_temperature"] if arm == "thinking_native" else settings["candidate_temperature"] if arm == "candidate_selection" and not selector else 0.0
    return {
        "messages": [{"role": "user", "content": content}], "max_tokens": cap,
        "temperature": temperature, "enable_thinking": arm == "thinking_native",
        "seed": seed_for(seed, item["id"], f"{arm}:{index}"),
    }


def _validate_generation(generation, spec, evidence):
    if not isinstance(generation, dict) or generation.get("evidence") != evidence:
        raise ValueError("Generation has missing or mixed evidence")
    if any(generation.get(key) != value or type(generation.get(key)) is not type(value) for key, value in spec.items()):
        raise ValueError("Cached generation differs from its call profile")
    if not isinstance(generation.get("output"), str) or generation.get("finish_reason") not in ("stop", "stop_answer", "length"):
        raise ValueError("Missing raw output or termination")
    for key in ("prompt_tokens", "completion_tokens"):
        if type(generation.get(key)) is not int or generation[key] < (0 if key == "completion_tokens" else 1):
            raise ValueError("Invalid per-call token telemetry")
    if generation["completion_tokens"] > spec["max_tokens"]:
        raise ValueError("Completion exceeds its cap")
    if type(generation.get("wall_ms")) not in (int, float) or not math.isfinite(generation["wall_ms"]) or generation["wall_ms"] < 0:
        raise ValueError("Invalid per-call time")


def _mock_text(item, arm, index):
    if arm == "pal_answer":
        return "import itertools\nresult = " + repr(item["answer"])
    if arm == "pal_certificate":
        solved = solve_order_query(item["query"])
        certificate = {"order": list(solved.order or ()), "answer": item["answer"]}
        return "import itertools\nresult = " + repr(certificate)
    if arm == "candidate_selection" and index == 3:
        return "Best: 0"
    answer = "Reasoning fixture.\nAnswer: " + item["answer"]
    return "<think>Fixture reasoning.</think>\n" + answer if arm == "thinking_native" else answer


def collect_single_item(model, tokenizer, item, seed, settings=SETTINGS, mock=False,
                        verbose=True, checkpoint=None):
    evidence = "synthetic_smoke" if mock else "measured_development_pilot"
    records = []
    for arm in ARMS:
        generations = []
        for index in range(4 if arm == "candidate_selection" else 1):
            spec = _spec(item, seed, arm, index, settings, [row["output"] for row in generations])
            key = (item["id"], seed, arm, index)
            generation = checkpoint.get("generation", key) if checkpoint else None
            if generation is None:
                if mock:
                    text = _mock_text(item, arm, index)
                    generation = {
                        **spec, "output": text, "prompt_tokens": len(spec["messages"][0]["content"].split()),
                        "completion_tokens": len(text.split()), "finish_reason": "stop", "wall_ms": 0.0,
                    }
                else:
                    generation = run_call(model, tokenizer, **spec)
                generation = {**generation, "evidence": evidence}
                _validate_generation(generation, spec, evidence)
                if checkpoint:
                    checkpoint.save("generation", key, generation)
            else:
                _validate_generation(generation, spec, evidence)
            generations.append(generation)

        execution = None
        if arm.startswith("pal"):
            key = (item["id"], seed, arm, 0)
            saved_execution = checkpoint.get("execution", key) if checkpoint else None
            if saved_execution is not None:
                if saved_execution.get("generation_sha256") != digest(generations[0]):
                    raise ValueError("Execution refers to a different generation")
                execution = saved_execution["result"]
            else:
                started = time.perf_counter()
                if generations[0]["finish_reason"] == "length":
                    ok, output = False, "generation_length"
                else:
                    ok, output = run_python_sandboxed(extract_code(generations[0]["output"]), allowed_imports=("itertools",))
                execution = {
                    "ok": ok, "output": output, "finish_reason": generations[0]["finish_reason"],
                    "wall_ms": (time.perf_counter() - started) * 1000.0,
                }
                if checkpoint:
                    checkpoint.save("execution", key, {"generation_sha256": digest(generations[0]), "result": execution})
        record = {
            "id": item["id"], "group_id": item["group_id"], "split": item["split"], "seed": seed,
            "arm": arm, "evidence": evidence, "answer": "", "execution": execution,
            "generations": generations,
        }
        record["answer"] = _selected_answer(record)[0] if execution is None or execution["ok"] else ""
        if not isinstance(record["answer"], str):
            record["answer"] = ""
        if checkpoint:
            checkpoint.save("record", (item["id"], seed, arm), record)
        records.append(record)
        if verbose:
            print(f"    {arm}: completed ({evidence})", flush=True)
    return records


def _source_hashes():
    names = (
        "scripts/pilot_order_certificate.py", "experiments/order_pilot_checkpoint.py",
        "experiments/order_certificate_study.py", "experiments/research_study.py",
        "scripts/verified_pal_order.py", "scripts/gen_tasks.py", "research_identity.py",
        "reasoning_strategies.py",
    )
    return {name: file_hash(ROOT / name) for name in names}


def _runtime_identity(mock):
    value = {"python": sys.version, "platform": platform.platform()}
    if not mock:
        for name in ("mlx", "mlx-lm"):
            try:
                value[name] = importlib.metadata.version(name)
            except importlib.metadata.PackageNotFoundError:
                value[name] = "unavailable"
    return value


def _preflight(checkpoint, dataset, settings):
    allowed = set()
    pending = 0
    for item in dataset["items"]:
        for seed in settings["generation_seeds"]:
            for arm in ARMS:
                outputs = []
                keys = []
                for index in range(4 if arm == "candidate_selection" else 1):
                    key = (item["id"], seed, arm, index)
                    allowed.add(("generation", *key))
                    keys.append(("generation", *key))
                    generation = checkpoint.get("generation", key)
                    if generation is None:
                        pending += 1
                    else:
                        if arm == "candidate_selection" and index == 3 and len(outputs) != 3:
                            raise ValueError("Selector checkpoint lacks candidate inputs")
                        _validate_generation(generation, _spec(item, seed, arm, index, settings, outputs),
                                             checkpoint.identity["evidence"])
                        outputs.append(generation["output"])
                if arm.startswith("pal"):
                    execution_key = ("execution", item["id"], seed, arm, 0)
                    allowed.add(execution_key)
                    if execution_key in checkpoint.cache and keys[0] not in checkpoint.cache:
                        raise ValueError("Execution checkpoint lacks its generation")
                    execution = checkpoint.cache.get(execution_key)
                    if execution is not None:
                        if not isinstance(execution, dict):
                            raise ValueError("Invalid cached execution")
                        generation = checkpoint.cache[keys[0]]
                        result = execution.get("result")
                        if (execution.get("generation_sha256") != digest(generation)
                                or not isinstance(result, dict) or type(result.get("ok")) is not bool
                                or not isinstance(result.get("output"), str)
                                or result.get("finish_reason") != generation["finish_reason"]):
                            raise ValueError("Invalid cached execution or generation link")
                    keys.append(execution_key)
                record_key = ("record", item["id"], seed, arm)
                allowed.add(record_key)
                if record_key in checkpoint.cache and not all(key in checkpoint.cache for key in keys):
                    raise ValueError("Completed arm checkpoint lacks a call or execution")
    if not set(checkpoint.cache) <= allowed:
        raise ValueError("Checkpoint contains unknown items, seeds, arms or call indices")
    completed = [value for key, value in checkpoint.cache.items() if key[0] == "record"]
    validate_records(dataset, completed, evidence=checkpoint.identity["evidence"], settings=settings,
                     development_pilot=True, allow_incomplete=True)
    for record in completed:
        prefix = (record["id"], record["seed"], record["arm"])
        if any(generation != checkpoint.get("generation", (*prefix, index))
               for index, generation in enumerate(record["generations"])):
            raise ValueError("Completed arm differs from its journaled calls")
        if record["execution"] is not None and record["execution"] != checkpoint.get("execution", (*prefix, 0))["result"]:
            raise ValueError("Completed arm differs from its journaled execution")
    return pending


def run_pilot(*, num_items=8, seeds=None, output_dir=None, thinking_max_tokens=None,
              mock=False, verbose=True):
    if output_dir is None:
        raise ValueError("A new or compatible checkpoint output directory is required")
    if type(num_items) is not int or num_items < 1:
        raise ValueError("num_items must be a positive integer")
    settings = copy.deepcopy(SETTINGS)
    settings["generation_seeds"] = [42] if seeds is None else seeds
    if thinking_max_tokens is not None:
        settings["thinking_max_tokens"] = thinking_max_tokens
    # Select only exposed train content; the source file is hashable but no test
    # outcome is evaluated, solved, displayed or used for profile decisions.
    full = json.loads((ROOT / "data/order_certificate_candidate_v1/dataset.json").read_text())
    train = [row for row in full["items"] if row["split"] == "train"]
    if num_items > len(train):
        raise ValueError("Requested more train items than available")
    dataset = {**copy.deepcopy(full), "items": copy.deepcopy(train[:num_items]),
               "name": f"ordering-pilot-train-{num_items}", "role": "development_tuning",
               "evidence": "synthetic_smoke" if mock else "measured_development_pilot"}
    evidence = dataset["evidence"]
    # Validate profile and schema before creating outputs/loading any runtime.
    validate_records(dataset, [], evidence=evidence, settings=settings,
                     development_pilot=True, allow_incomplete=True)
    identity = {
        "schema_version": 1, "mock": mock, "evidence": evidence,
        "settings_sha256": digest(settings), "dataset_sha256": digest(dataset),
        "source_sha256": _source_hashes(), "runtime": _runtime_identity(mock),
    }
    checkpoint = PilotCheckpoint(output_dir, identity, dataset, settings)
    model = tokenizer = None
    try:
        pending = _preflight(checkpoint, dataset, settings)
        print(f"Ordering development pilot: {evidence}; {num_items} questions; pending calls={pending}")
        if checkpoint.was_complete:
            records = json.loads((checkpoint.directory / "records.json").read_text())
            validate_records(dataset, records, evidence=evidence, settings=settings, development_pilot=True)
            report = {
                "evidence": evidence, "decision": "development_diagnostics_only",
                "summary": json.loads((checkpoint.directory / "summary.json").read_text()),
                "eval_rows": json.loads((checkpoint.directory / "eval_rows.json").read_text()),
                "generation_seeds": settings["generation_seeds"], "publication_review_required": True,
            }
            return dataset, records, settings, report
        if not mock and pending:
            _load_runtime()
            model, tokenizer = load(settings["model_repository"], revision=settings["model_revision"])
        records = []
        for item in dataset["items"]:
            for seed in settings["generation_seeds"]:
                records.extend(collect_single_item(model, tokenizer, item, seed, settings,
                                                   mock=mock, verbose=verbose, checkpoint=checkpoint))
        summary_report = generate_pilot_report(dataset, records, settings)
        atomic_json(checkpoint.directory / "summary.json", summary_report["summary"])
        atomic_json(checkpoint.directory / "eval_rows.json", summary_report["eval_rows"])
        atomic_text(checkpoint.directory / "report.md", render_pilot_markdown(summary_report))
        checkpoint.snapshot()
        checkpoint.complete()
        return dataset, records, settings, summary_report
    except BaseException as error:
        if not checkpoint.was_complete:
            checkpoint.status("interrupted", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        checkpoint.close()


def generate_pilot_report(dataset, records, settings):
    evidence = dataset.get("evidence")
    validate_records(dataset, records, evidence=evidence, settings=settings, development_pilot=True)
    rows = evaluate(dataset, records, settings=settings)
    summary = {}
    for method in METHODS:
        group = [row for row in rows if row["method"] == method]
        n = len(group)
        metric = {
            "count": n, "questions": len({row["id"] for row in group}),
            "correct_count": sum(row["correct"] for row in group),
            "accuracy": sum(row["correct"] for row in group) / n,
            "mean_prompt_tokens": sum(row["prompt_tokens"] for row in group) / n,
            "mean_completion_tokens": sum(row["completion_tokens"] for row in group) / n,
            "mean_tokens": sum(row["tokens"] for row in group) / n,
            "mean_replayed_strategy_ms": sum(row["replayed_strategy_ms"] for row in group) / n,
            "mean_offline_verifier_ms": sum(row["offline_verifier_ms"] for row in group) / n,
            "mean_offline_solver_ms": sum(row["offline_solver_ms"] for row in group) / n,
            "escalation_rate": sum(row["escalated"] for row in group) / n,
        }
        if method.startswith("w_") or method == "verified_certificate":
            rejected = [row for row in group if row["escalated"]]
            initial = sum(row["initial_tokens"] for row in group) / n
            conditional = sum(row["fallback_tokens"] for row in rejected) / len(rejected) if rejected else 0.0
            metric.update(
                rescue_from_initial=sum(not row["initial_correct"] and row["correct"] for row in group),
                harm_from_initial=sum(row["initial_correct"] and not row["correct"] for row in group),
                cost_identity={"mean_initial_tokens": initial, "mean_fallback_tokens_given_reject": conditional,
                               "reconstructed_mean_tokens": initial + metric["escalation_rate"] * conditional},
            )
        if method == "verified_certificate":
            metric["gate_confusion_by_answer"] = {
                "true_accept": sum(row["certificate_accepted"] and row["initial_correct"] for row in group),
                "false_accept": sum(row["certificate_accepted"] and not row["initial_correct"] for row in group),
                "true_reject": sum(not row["certificate_accepted"] and not row["initial_correct"] for row in group),
                "false_reject": sum(not row["certificate_accepted"] and row["initial_correct"] for row in group),
            }
        summary[method] = metric
    return {
        "evidence": evidence, "decision": "development_diagnostics_only", "summary": summary,
        "eval_rows": rows, "generation_seeds": settings["generation_seeds"],
        "publication_review_required": True,
    }


def render_pilot_markdown(report):
    summary = report["summary"]
    lines = [
        "# Ordering certificate development pilot", "",
        f"Evidence: {report['evidence']}. Decision: development_diagnostics_only.", "",
        f"Prompt/parser profile: {SETTINGS['prompt_profile']} / {SETTINGS['selector_parser_profile']}.", "",
        "Synthetic fixtures are not measured model quality. This is not a confirmatory test.", "",
        "| Method | Questions | Item × seed rows | Accuracy | Mean prompt | Mean completion | Mean total tokens | Escalation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for method, metric in summary.items():
        lines.append(f"| {method} | {metric['questions']} | {metric['count']} | {metric['accuracy']:.3f} | {metric['mean_prompt_tokens']:.1f} | {metric['mean_completion_tokens']:.1f} | {metric['mean_tokens']:.1f} | {metric['escalation_rate']:.3f} |")
    verified = summary["verified_certificate"]
    ratio = verified["mean_tokens"] / summary["fixed_candidate_selection"]["mean_tokens"]
    lines.extend([
        "", f"Verified / fixed candidate mean-token ratio (all invoked stages): {ratio:.3f}.",
        "Gate confusion by FIRST-STAGE answer correctness (item × seed counts): " + str(verified["gate_confusion_by_answer"]) + ".",
        f"Rescue / harm versus initial PAL answer: {verified['rescue_from_initial']} / {verified['harm_from_initial']}.",
        "", "A correct answer with an invalid witness is not an incorrect-answer false accept.",
        "Fallback costs count even when the fallback is wrong or truncated.",
        "Replayed generation-time sums, offline verifier time and symbolic CPU-path time are separate; not measured online latency.",
        "The generic verifier includes exact uniqueness solving. The standalone solver is a query-only baseline, not an oracle.",
        "Model-token counts are not FLOPs, energy or full inference cost. Synthetic counts are placeholders.",
        "The Python execution helper is NOT a security boundary. Real runs need a controlled environment.",
        "No preregistration pass, superiority or publication claim follows from this development report.",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Development-only ordering certificate pilot")
    parser.add_argument("--items", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--thinking-tokens", type=int, default=SETTINGS["thinking_max_tokens"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mock", action="store_true", help="Synthetic software validation; never import/load MLX")
    args = parser.parse_args()
    run_pilot(num_items=args.items, seeds=[args.seed], output_dir=args.output,
              thinking_max_tokens=args.thinking_tokens, mock=args.mock)
