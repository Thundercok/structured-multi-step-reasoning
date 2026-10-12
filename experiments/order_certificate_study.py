"""Offline preparation and paired replay for the ordering certificate study."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import platform
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from experiments.research_study import ROOT, check_answer, git_value, seed_for, validate_dataset, write_json
from research_identity import IDENTITY_VERSION, canonical_problem_id
from scripts.gen_tasks import render_order
from scripts.verified_pal_order import (
    OrderVerificationStatus, extract_order_certificate, parse_order_query, solve_order_query,
    verify_order_execution,
)

ARMS = ("pal_answer", "pal_certificate", "candidate_selection", "thinking_native")
METHODS = (
    "fixed_pal_answer", "fixed_pal_certificate", "fixed_candidate_selection",
    "fixed_thinking_native", "w_answer", "w_certificate", "verified_certificate",
    "symbolic_solver",
)
SOURCE_FILES = (
    "experiments/order_certificate_study.py", "experiments/research_study.py",
    "scripts/verified_pal_order.py", "scripts/gen_tasks.py", "research_identity.py",
)
PROMPTS = {
    "pal_answer": "Write Python using itertools if needed. Assign exactly one bare runner name string to result. Do not include a rank, label, explanation, or print statement. Return only Python code.",
    "pal_certificate": 'Write Python using itertools if needed. Assign a dict to result with exactly "order" (all runners in rank order) and "answer" (the requested runner). Return only Python code.',
    "candidate": "Write concise reasoning steps. End with exactly one line Answer: followed by the requested runner.",
    "selector": "The responses below are explicitly labelled Candidate 0, Candidate 1, and Candidate 2 (zero-based indices). Choose one complete candidate that correctly answers the question. Return exactly one line: Best: 0, Best: 1, or Best: 2. Return the candidate index, not a runner name or rank.",
    "thinking_native": "Solve the question. End your final response with Answer: followed by the requested runner.",
}
SETTINGS = {
    "schema_version": 1,
    "prompt_profile": "order-contract-v2",
    "selector_parser_profile": "single-zero-based-index-v2",
    "generation_seeds": [42, 43, 44],
    "pal_max_tokens": 512,
    "candidate_max_tokens": 1024,
    "candidate_branches": 3,
    "candidate_temperature": 0.7,
    "selector_max_tokens": 64,
    "thinking_max_tokens": 1024,
    "thinking_temperature": 0.6,
    "verifier_mode": "generic_with_uniqueness_check",
    "bootstrap_repetitions": 5000,
    "bootstrap_seed": 20261008,
    "accuracy_margin": -0.05,
    "max_token_ratio": 0.60,
    "model_repository": "mlx-community/Qwen3-8B-4bit",
    "model_revision": "545dc4251c05440727734bcd94334791f6ab0192",
    "prompts": PROMPTS,
}


def format_selector_candidates(outputs):
    """One shared, numbered contract for collector, fixtures and validation."""
    if not isinstance(outputs, (list, tuple)) or len(outputs) != 3 or any(not isinstance(text, str) for text in outputs):
        raise ValueError("Selector requires exactly three raw candidate strings")
    return "\n\n".join(f"Candidate {index}:\n{text}\nEnd Candidate {index}" for index, text in enumerate(outputs))


def parse_selector_index(text):
    """Accept only a single whole index response, never search prose for digits.

    Best: X is requested; Answer: X and Candidate X are narrow format aliases.
    They use the SAME explicit zero-based mapping, not a one-based heuristic.
    Completion/truncation is checked separately by the attempt scorer.
    """
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"\s*(?:(?:Best|Answer)\s*:\s*|Candidate\s+)([0-2])\s*", text, re.I)
    return int(match[1]) if match else None


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    return {name: file_hash(ROOT / name) for name in SOURCE_FILES}


def _save(directory, artifacts, manifest):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {
        **manifest, "status": "running", "source_sha256": source_hashes(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_value("rev-parse", "HEAD"), "git_status": git_value("status", "--porcelain"),
        "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
        "model_calls": False, "publication_review_required": True,
    }
    write_json(directory / "manifest.json", manifest)
    try:
        for name, value in artifacts.items():
            if name.endswith(".md"):
                (directory / name).write_text(value, encoding="utf-8")
            else:
                write_json(directory / name, value)
        manifest["artifact_sha256"] = {name: file_hash(directory / name) for name in artifacts}
        manifest["status"] = "complete"
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(directory / "manifest.json", manifest)
    except BaseException as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        write_json(directory / "manifest.json", manifest)
        raise


def prepare_dataset(raw_path, output):
    """Adapt the frozen candidate without solving or reviewing its test gold."""
    if Path(output).exists():
        raise FileExistsError(f"Output already exists: {output}")
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    tuning_path = ROOT / "data/gen02_tune.json"
    tune = json.loads(tuning_path.read_text(encoding="utf-8"))
    test_rows = raw.get("items", [])
    if len(test_rows) != 100 or any(row.get("family") != "order" for row in test_rows):
        raise ValueError("Preparation requires the 100-item ordering candidate")
    if any(row.get("split") != "confirmatory" for row in test_rows):
        raise ValueError("Candidate items must have the original confirmatory label")
    rows = []
    for original in [row for row in tune["items"] if row["family"] == "order"] + test_rows:
        row = copy.deepcopy(original)
        prospective = original["split"] == "confirmatory"
        row["split"] = "test" if prospective else "train" if original["split"] == "dev" else "calibration"
        row.update(answer_type="text", problem_id=canonical_problem_id(row))
        row["group_id"] = row["problem_id"]
        row["source_provenance"] = {"original_id": original["id"], "original_split": original["split"]}
        rows.append(row)
    dataset = {
        "name": "ordering-certificate-candidate-v1", "version": "1.0.0-candidate",
        "role": "main_study", "identity_version": IDENTITY_VERSION,
        "source": "Frozen 100-item candidate plus exposed gen02_tune development; see manifest hashes",
        "license": "Project procedural generator; ownership/license confirmation pending",
        "human_review_status": "pending", "unique_asked_rank_review_status": "pending",
        "publication_ready": False, "items": rows,
    }
    validate_dataset(dataset)
    # Label-free isolation audit, including reserved inputs. No answer is solved,
    # compared or displayed for any prospective test item.
    excluded_sources = (
        "data/gen02_tune.json", "data/gen02_tune_gapB.json", "data/gen02_v2.json",
        "data/gen02_v2b.json", "data/gen_tune.json", "data/gen_v2.json",
        "data/procedural_research_v1/main.json", "data/procedural_research_v1/tuning.json",
    )
    candidates = {row["problem_id"] for row in rows if row["split"] == "test"}
    isolation = []
    for name in excluded_sources:
        path = ROOT / name
        if not path.exists():
            continue
        others = json.loads(path.read_text(encoding="utf-8"))["items"]
        identities = {canonical_problem_id(row) for row in others if row.get("family") == "order"}
        overlap = len(candidates & identities)
        isolation.append({"path": name, "sha256": file_hash(path), "canonical_overlap": overlap})
        if overlap:
            raise ValueError(f"Prospective ordering candidate overlaps {name}")
    plan = {
        **SETTINGS, "status": "pending_review_and_execution_freeze",
        "measured_collection_enabled": False,
        "primary_split": "test", "policies_fitted": False,
        "required_before_collection": [
            "Human generator, query-parser and unique-asked-rank review",
            "Model content and upstream revision provenance",
            "Power/sample-size addendum and frozen selection of verifier mode",
            "Native-thinking generation/termination smoke on development only",
            "Stage 0 requirements reviewed; this preparation does not pass Stage 0",
        ],
    }
    _save(output, {
        "dataset.json": dataset, "plan.json": plan, "isolation.json": isolation,
        "report.md": (
            "# Ordering candidate preparation\n\n"
            "Candidate only; review and execution freeze are pending. No model calls.\n\n"
            f"Items by split: {dict(Counter(row['split'] for row in rows))}.\n\n"
            "Prospective test rows are copied unchanged except schema/identity fields. "
            "Test answers were not solved or semantically reviewed. Historical test "
            "labels in gen02_tune are treated as exposed development.\n"
        ),
    }, {"mode": "order_candidate_preparation", "evidence": "schema_and_isolation_only",
        "input_sha256": {str(Path(raw_path)): file_hash(raw_path), str(tuning_path): file_hash(tuning_path)}})


def smoke_dataset():
    rows = []
    for n in (3, 4, 5):
        names = ["Alice", "Bob", "Carol", "Dave", "Erin"][:n]
        for ask in range(n):
            meta = {"names": names, "clues": [["b", i, i + 1] for i in range(n - 1)], "ask": ask}
            row = {"id": f"synthetic-order-{n}-{ask}", "family": "order", "checker": "order",
                   "level": n - 2, "meta": meta, "query": render_order(meta), "answer": names[ask],
                   "answer_type": "text", "split": ("train", "calibration", "test")[len(rows) % 3]}
            row["problem_id"] = row["group_id"] = canonical_problem_id(row)
            rows.append(row)
    return {"name": "synthetic-order-certificate-smoke", "version": "1", "role": "main_study",
            "identity_version": IDENTITY_VERSION, "source": "Project-authored synthetic fixtures",
            "license": "Project-authored test fixture", "human_review_status": "synthetic_fixture",
            "items": rows}


def _smoke_records(dataset):
    records = []
    for seed in SETTINGS["generation_seeds"]:
        for index, item in enumerate(dataset["items"]):
            solved = solve_order_query(item["query"])
            witness = list(solved.order)
            wrong = next(name for name in witness if name != item["answer"])
            good = index % 4 == 0
            certificate = {"order": witness if good else list(reversed(witness)),
                           "answer": item["answer"] if good else wrong}
            for arm in ARMS:
                generated = []
                count = 4 if arm == "candidate_selection" else 1
                for call in range(count):
                    selector = arm == "candidate_selection" and call == 3
                    suffix = PROMPTS["selector"] if selector else PROMPTS["candidate"] if arm == "candidate_selection" else PROMPTS[arm]
                    messages = [{"role": "user", "content": item["query"] + "\n" + suffix}]
                    if selector:
                        messages[0]["content"] += "\n" + format_selector_candidates([row["output"] for row in generated])
                    text = "Best: 0" if selector else f"Answer: {item['answer']}" if arm in ("candidate_selection", "thinking_native") else "result = " + repr(certificate if arm == "pal_certificate" else item["answer"])
                    cap = SETTINGS["selector_max_tokens"] if selector else SETTINGS["candidate_max_tokens"] if arm == "candidate_selection" else SETTINGS["thinking_max_tokens"] if arm == "thinking_native" else SETTINGS["pal_max_tokens"]
                    generated.append({
                        "messages": messages, "output": text,
                        "prompt_tokens": len(messages[0]["content"].split()),
                        "completion_tokens": 8 if selector else 80 if arm.startswith("pal") else 120,
                        "max_tokens": cap, "finish_reason": "stop", "wall_ms": 0.0,
                        "seed": seed_for(seed, item["id"], f"{arm}:{call}"),
                        "enable_thinking": arm == "thinking_native",
                        "temperature": SETTINGS["thinking_temperature"] if arm == "thinking_native" else SETTINGS["candidate_temperature"] if arm == "candidate_selection" and not selector else 0.0,
                    })
                execution = None
                if arm.startswith("pal"):
                    execution = {"ok": index % 4 != 2,
                                 "output": json.dumps(certificate) if arm == "pal_certificate" else item["answer"] if good else wrong,
                                 "finish_reason": "stop"}
                answer = item["answer"] if arm in ("candidate_selection", "thinking_native") else certificate["answer"] if arm == "pal_certificate" else execution["output"]
                records.append({"id": item["id"], "group_id": item["group_id"], "split": item["split"],
                                "seed": seed, "arm": arm, "answer": answer, "execution": execution,
                                "generations": generated})
    return records


PATTERNS = (
    r"Answer:[ \t]*([A-Za-z]+)",
    r"\*\*Answer:[ \t]*([A-Za-z]+)\*\*",
    r"\*\*Answer:\*\*[ \t]*([A-Za-z]+)",
)


def _final_answer(text, runners=None):
    """Bounded draft aliases on a terminal answer block, never a gold-name search.

    Whole plain/bold/bold-label Answer lines, optional Markdown heading prefix.
    Repeated adjacent answers must agree; unknown names and extra prose fail.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    answers = []
    for line in reversed(text.rstrip().splitlines()):
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"^#{1,6}[ \t]+", "", line)
        match = next((match for pattern in PATTERNS if (match := re.fullmatch(pattern, line))), None)
        if match is None:
            break
        if runners is not None and match[1] not in runners:
            return ""
        answers.append(match[1])
    return answers[0] if answers and len(set(answers)) == 1 else ""


def _extract_runners_from_attempt(attempt):
    if "runners" in attempt:
        return tuple(attempt["runners"])
    if "query" in attempt:
        ir = parse_order_query(attempt["query"])
        if ir is not None:
            return ir.runners
    generations = attempt.get("generations")
    if generations and isinstance(generations, list):
        messages = generations[0].get("messages")
        if messages and isinstance(messages, list) and messages[0].get("content"):
            ir = parse_order_query(messages[0]["content"])
            if ir is not None:
                return ir.runners
    return None


def _selected_answer(attempt, runners=None):
    if runners is None:
        runners = _extract_runners_from_attempt(attempt)
    generations = attempt["generations"]
    if attempt["arm"] == "candidate_selection":
        if len(generations) != 4:
            return "", False
        selector_call = generations[3]
        selector_idx = parse_selector_index(selector_call["output"])
        if selector_idx is None or selector_call.get("finish_reason") not in ("stop", "stop_answer"):
            return "", False
        admissible = {}
        for branch, call in enumerate(generations[:3]):
            if call.get("finish_reason") not in ("stop", "stop_answer"):
                continue
            ans = _final_answer(call["output"], runners)
            if ans:
                admissible[branch] = ans
        if selector_idx in admissible:
            return admissible[selector_idx], True
        if len(admissible) == 1:
            only = next(iter(admissible))
            return admissible[only], True
        return "", False
    if attempt["arm"] == "thinking_native":
        call = generations[0]
        if call.get("finish_reason") not in ("stop", "stop_answer"):
            return "", False
        ans = _final_answer(call["output"], runners)
        return ans, bool(ans)
    execution = attempt["execution"]
    if not execution:
        return "", False
    certificate = extract_order_certificate(execution["output"]) if attempt["arm"] == "pal_certificate" else None
    answer = certificate.get("answer", "") if certificate else "" if attempt["arm"] == "pal_certificate" else execution["output"]
    return answer, bool(execution["ok"] and generations[0]["finish_reason"] != "length")


def validate_records(dataset, records, *, evidence, settings, development_pilot=False, allow_incomplete=False):
    if allow_incomplete and not development_pilot:
        raise ValueError("Incomplete matrices are allowed only for development preparation")
    if development_pilot:
        if dataset.get("role") != "development_tuning" or any(row.get("split") == "test" for row in dataset.get("items", [])):
            raise ValueError("Ordering pilot requires development-only data")
        profile = dict(settings)
        seeds = profile.pop("generation_seeds", None)
        cap = profile.pop("thinking_max_tokens", None)
        reference = {key: value for key, value in SETTINGS.items() if key not in ("generation_seeds", "thinking_max_tokens")}
        if profile != reference or not isinstance(seeds, list) or not seeds or any(type(seed) is not int or not 0 <= seed < 2**32 for seed in seeds) or len(set(seeds)) != len(seeds) or type(cap) is not int or not 1 <= cap <= 3136:
            raise ValueError("Invalid development pilot profile")
    elif settings != SETTINGS:
        raise ValueError("Recorded settings differ from this study implementation")
    items = {row["id"]: row for row in validate_dataset(dataset, require_all_splits=not development_pilot)}
    labels = ("synthetic_smoke", "measured_development_pilot") if development_pilot else ("synthetic_smoke", "measured_order_certificate")
    if evidence not in labels:
        raise ValueError("Unsupported evidence label")
    seen = set()
    for row in records:
        if not isinstance(row, dict) or row.get("id") not in items or row.get("arm") not in ARMS:
            raise ValueError("Unknown item or arm")
        if development_pilot and row.get("evidence") != evidence:
            raise ValueError("Attempt evidence differs from the pilot mode")
        item = items[row["id"]]
        if row.get("group_id") != item["group_id"] or row.get("split") != item["split"]:
            raise ValueError("Attempt identity differs from the dataset")
        key = (row["id"], row.get("seed"), row["arm"])
        if type(row.get("seed")) is not int or row["seed"] not in settings["generation_seeds"] or key in seen:
            raise ValueError("Duplicate or invalid attempt seed")
        seen.add(key)
        generations = row.get("generations")
        expected_calls = 4 if row["arm"] == "candidate_selection" else 1
        if not isinstance(generations, list) or len(generations) != expected_calls:
            raise ValueError("Missing model-call telemetry (including selector)")
        for call, generation in enumerate(generations):
            if not isinstance(generation, dict):
                raise ValueError("Model-call telemetry must be an object")
            if development_pilot and generation.get("evidence") != evidence:
                raise ValueError("Generation evidence differs from the pilot mode")
            for field in ("prompt_tokens", "completion_tokens", "max_tokens"):
                minimum = 0 if field == "completion_tokens" else 1
                if type(generation.get(field)) is not int or generation[field] < minimum:
                    raise ValueError("Each call requires valid prompt/completion/cap counts")
            if generation["completion_tokens"] > generation["max_tokens"]:
                raise ValueError("Generation exceeded its recorded cap")
            selector = row["arm"] == "candidate_selection" and call == 3
            cap = settings["selector_max_tokens"] if selector else settings["candidate_max_tokens"] if row["arm"] == "candidate_selection" else settings["thinking_max_tokens"] if row["arm"] == "thinking_native" else settings["pal_max_tokens"]
            temp = settings["thinking_temperature"] if row["arm"] == "thinking_native" else settings["candidate_temperature"] if row["arm"] == "candidate_selection" and not selector else 0.0
            if generation["max_tokens"] != cap or generation.get("temperature") != temp:
                raise ValueError("Per-call budget or decoding setting mismatch")
            if not isinstance(generation.get("output"), str) or not isinstance(generation.get("messages"), list) or not generation["messages"]:
                raise ValueError("Each call requires complete prompt messages and raw output")
            suffix = PROMPTS["selector"] if selector else PROMPTS["candidate"] if row["arm"] == "candidate_selection" else PROMPTS[row["arm"]]
            expected_prompt = item["query"] + "\n" + suffix
            if selector:
                expected_prompt += "\n" + format_selector_candidates([part["output"] for part in generations[:3]])
            if generation["messages"] != [{"role": "user", "content": expected_prompt}]:
                raise ValueError("Prompt differs from the frozen profile or lacks selector candidates")
            if generation.get("seed") != seed_for(row["seed"], row["id"], f"{row['arm']}:{call}"):
                raise ValueError("Per-call generation seed mismatch")
            if generation.get("enable_thinking") is not (row["arm"] == "thinking_native"):
                raise ValueError("Native-thinking flag mismatch")
            if generation.get("finish_reason") not in ("stop", "stop_answer", "length"):
                raise ValueError("Missing termination reason")
            if type(generation.get("wall_ms")) not in (int, float) or not math.isfinite(generation["wall_ms"]) or generation["wall_ms"] < 0:
                raise ValueError("Invalid recorded generation time")
        if not isinstance(row.get("answer"), str):
            raise ValueError("Attempt answer must be a string")
        if row["arm"].startswith("pal"):
            execution = row.get("execution")
            if not isinstance(execution, dict) or type(execution.get("ok")) is not bool or not isinstance(execution.get("output"), str):
                raise ValueError("PAL requires the actual execution result")
            if execution.get("finish_reason") != generations[-1]["finish_reason"]:
                raise ValueError("Execution and generation termination disagree")
            if execution["ok"]:
                extracted = _selected_answer(row)[0]
                if extracted != row["answer"]:
                    raise ValueError("PAL answer differs from its actual execution payload")
        elif _selected_answer(row)[0] != row["answer"]:
            raise ValueError("Answer does not reproduce from the raw selected output")
    expected = {(identifier, seed, arm) for identifier in items for seed in settings["generation_seeds"] for arm in ARMS}
    if seen != expected and not allow_incomplete:
        raise ValueError("Study requires the complete item/seed/arm factorial")
    return items


def _cost(attempt):
    return sum(call["prompt_tokens"] + call["completion_tokens"] for call in attempt["generations"])


def _exec_accept(attempt):
    result = attempt["execution"]
    return result["ok"] is True and result["output"].strip() not in ("", "None") and result["finish_reason"] != "length"


def evaluate(dataset, records, *, settings=SETTINGS):
    items = {row["id"]: row for row in dataset["items"]}
    paired = {(row["id"], row["seed"], row["arm"]): row for row in records}
    results = []
    symbolic = {}
    for item in dataset["items"]:
        started = time.perf_counter()
        solved = solve_order_query(item["query"])
        symbolic[item["id"]] = (solved, (time.perf_counter() - started) * 1000)
    for identifier in sorted(items):
        item = items[identifier]
        for seed in settings["generation_seeds"]:
            attempts = {arm: paired[(identifier, seed, arm)] for arm in ARMS}
            certificate = attempts["pal_certificate"]
            started = time.perf_counter()
            verified = verify_order_execution(item["query"], certificate["execution"])
            check_ms = (time.perf_counter() - started) * 1000
            paths = {f"fixed_{arm}": [arm] for arm in ARMS}
            paths.update({
                "w_answer": ["pal_answer"] + ([] if _exec_accept(attempts["pal_answer"]) else ["candidate_selection"]),
                "w_certificate": ["pal_certificate"] + ([] if _exec_accept(certificate) else ["candidate_selection"]),
                "verified_certificate": ["pal_certificate"] + ([] if verified.status == OrderVerificationStatus.VALID else ["candidate_selection"]),
                "symbolic_solver": [],
            })
            for method, path in paths.items():
                selected = attempts[path[-1]] if path else None
                answer = selected["answer"] if selected else symbolic[identifier][0].answer or ""
                valid_completion = selected is None or _selected_answer(selected)[1]
                invoked = [attempts[arm] for arm in path]
                row = {
                    "method": method, "id": identifier, "group_id": item["group_id"], "split": item["split"],
                    "seed": seed, "path": path, "answer": answer,
                    "correct": bool(valid_completion and check_answer(answer, item)),
                    "tokens": sum(_cost(attempt) for attempt in invoked),
                    "prompt_tokens": sum(call["prompt_tokens"] for attempt in invoked for call in attempt["generations"]),
                    "completion_tokens": sum(call["completion_tokens"] for attempt in invoked for call in attempt["generations"]),
                    "replayed_strategy_ms": sum(call["wall_ms"] for attempt in invoked for call in attempt["generations"]),
                    "offline_verifier_ms": check_ms if method == "verified_certificate" else 0.0,
                    "offline_solver_ms": symbolic[identifier][1] if method == "symbolic_solver" else 0.0,
                    "escalated": len(path) > 1, "verification_status": verified.status.value if method == "verified_certificate" else None,
                    "symbolic_status": symbolic[identifier][0].status if not path else None,
                    "certificate_accepted": method == "verified_certificate" and len(path) == 1,
                    "initial_correct": bool(_selected_answer(attempts[path[0]])[1] and check_answer(attempts[path[0]]["answer"], item)) if path else None,
                    "initial_tokens": _cost(attempts[path[0]]) if path else 0,
                    "fallback_tokens": _cost(attempts[path[-1]]) if len(path) > 1 else 0,
                }
                results.append(row)
    return results


def summarize(results, *, evidence):
    test = [row for row in results if row["split"] == "test"]
    if not test:
        raise ValueError("No evaluation test fixture")
    by_method = {method: [row for row in test if row["method"] == method] for method in METHODS}
    metrics = {}
    for method, rows in by_method.items():
        metrics[method] = {
            "questions": len({row["id"] for row in rows}), "groups": len({row["group_id"] for row in rows}),
            "generations_per_question": len(SETTINGS["generation_seeds"]),
            "accuracy": float(np.mean([row["correct"] for row in rows])),
            "mean_tokens": float(np.mean([row["tokens"] for row in rows])),
            "escalation_rate": float(np.mean([row["escalated"] for row in rows])),
            "false_accepts": sum(row["certificate_accepted"] and not row["correct"] for row in rows),
            "false_accept_groups": len({row["group_id"] for row in rows if row["certificate_accepted"] and not row["correct"]}),
            "mean_replayed_strategy_ms": float(np.mean([row["replayed_strategy_ms"] for row in rows])),
            "mean_offline_verifier_ms": float(np.mean([row["offline_verifier_ms"] for row in rows])),
            "mean_offline_solver_ms": float(np.mean([row["offline_solver_ms"] for row in rows])),
        }
        grouped = defaultdict(list)
        for row in rows:
            grouped[row["group_id"]].append([float(row["correct"]), row["tokens"]])
        sums = np.array([np.sum(group, axis=0) for group in grouped.values()])
        counts = np.array([len(group) for group in grouped.values()])
        draws = np.random.default_rng(SETTINGS["bootstrap_seed"]).integers(
            0, len(grouped), size=(SETTINGS["bootstrap_repetitions"], len(grouped)),
        )
        sampled = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)[:, None]
        metrics[method]["accuracy_ci95"] = np.quantile(sampled[:, 0], [0.025, 0.975]).tolist() if len(grouped) > 1 else None
        metrics[method]["mean_tokens_ci95"] = np.quantile(sampled[:, 1], [0.025, 0.975]).tolist() if len(grouped) > 1 else None
        if method.startswith("w_") or method == "verified_certificate":
            escalated = [row for row in rows if row["escalated"]]
            c1 = float(np.mean([row["initial_tokens"] for row in rows]))
            conditional = float(np.mean([row["fallback_tokens"] for row in escalated])) if escalated else 0.0
            metrics[method]["cost_identity"] = {
                "mean_initial_tokens": c1, "mean_fallback_tokens_given_reject": conditional,
                "reconstructed_mean_tokens": c1 + metrics[method]["escalation_rate"] * conditional,
            }
            metrics[method]["rescue_from_initial"] = sum(not row["initial_correct"] and row["correct"] for row in rows)
            metrics[method]["harm_from_initial"] = sum(row["initial_correct"] and not row["correct"] for row in rows)
        if method == "verified_certificate":
            metrics[method]["gate_confusion_by_answer"] = {
                "true_accept": sum(row["certificate_accepted"] and row["initial_correct"] for row in rows),
                "false_accept": sum(row["certificate_accepted"] and not row["initial_correct"] for row in rows),
                "true_reject": sum(not row["certificate_accepted"] and not row["initial_correct"] for row in rows),
                "false_reject": sum(not row["certificate_accepted"] and row["initial_correct"] for row in rows),
            }
    verification = by_method["verified_certificate"]

    def paired_comparison(baseline_method):
        baseline = {(row["id"], row["seed"]): row for row in by_method[baseline_method]}
        groups = defaultdict(list)
        for row in verification:
            base = baseline[(row["id"], row["seed"])]
            groups[row["group_id"]].append([float(row["correct"]) - float(base["correct"]), row["tokens"], base["tokens"]])
        values = list(groups.values())
        sums = np.array([np.sum(group, axis=0) for group in values])
        counts = np.array([len(group) for group in values])
        rng = np.random.default_rng(SETTINGS["bootstrap_seed"])
        draws = rng.integers(0, len(values), size=(SETTINGS["bootstrap_repetitions"], len(values)))
        accuracy_delta = sums[draws, 0].sum(axis=1) / counts[draws].sum(axis=1)
        ratio = sums[draws, 1].sum(axis=1) / sums[draws, 2].sum(axis=1)
        accuracy_ci = np.quantile(accuracy_delta, [0.025, 0.975]).tolist()
        ratio_ci = np.quantile(ratio, [0.025, 0.975]).tolist()
        degenerate = bool(np.all(accuracy_delta == accuracy_delta[0]))
        # An empirical [0, 0] interval with no discordance cannot establish the
        # absence of rare population harms. Fail closed pending statistical review.
        eligible = len(groups) > 1 and not degenerate
        passes = eligible and accuracy_ci[0] >= SETTINGS["accuracy_margin"] and ratio_ci[1] <= SETTINGS["max_token_ratio"]
        if len(groups) < 2:
            accuracy_ci, ratio_ci = None, None
        return {
            "baseline": baseline_method,
            "accuracy_delta": metrics["verified_certificate"]["accuracy"] - metrics[baseline_method]["accuracy"],
            "accuracy_delta_ci95": accuracy_ci,
            "token_ratio": metrics["verified_certificate"]["mean_tokens"] / metrics[baseline_method]["mean_tokens"],
            "token_ratio_ci95": ratio_ci,
            "accuracy_bootstrap_degenerate": degenerate,
            "statistical_gate_pass": bool(passes),
            "rescue": sum(row["correct"] and not baseline[(row["id"], row["seed"])]["correct"] for row in verification),
            "harm": sum(not row["correct"] and baseline[(row["id"], row["seed"])]["correct"] for row in verification),
        }

    primary = paired_comparison("fixed_candidate_selection")
    return {
        "evidence": evidence, "methods": metrics,
        "paired_verified_minus_candidate": primary,
        "paired_verified_minus_w_certificate": paired_comparison("w_certificate"),
        "statistical_gate_pass": primary["statistical_gate_pass"],
        "decision": "synthetic_validation_only" if evidence == "synthetic_smoke" else "pending_independent_review",
        "bootstrap_unit": "group_id, retaining every item and generation seed",
        "token_scope": "sum of all model-call prompt and completion counts; not FLOPs/energy/full inference cost",
    }


def report(summary):
    lines = ["# Ordering certificate study", "", f"Evidence: {summary['evidence']}. Decision: {summary['decision']}.", "",
             "| Method | Questions | Accuracy | Mean tokens | Escalation |",
             "| --- | ---: | ---: | ---: | ---: |"]
    for method, value in summary["methods"].items():
        lines.append(f"| {method} | {value['questions']} | {value['accuracy']:.3f} | {value['mean_tokens']:.1f} | {value['escalation_rate']:.3f} |")
    lines.extend(["", "## Paired comparisons", ""])
    for key in ("paired_verified_minus_candidate", "paired_verified_minus_w_certificate"):
        value = summary[key]
        lines.append(f"Verified minus {value['baseline']}: accuracy delta {value['accuracy_delta']:.3f}, CI95 {value['accuracy_delta_ci95']}; token ratio {value['token_ratio']:.3f}, CI95 {value['token_ratio_ci95']}.")
    lines.extend(["", "Gate confusion by first-stage answer correctness (item × seed counts): " + str(summary["methods"]["verified_certificate"]["gate_confusion_by_answer"]) + ".", ""])
    lines.extend(["", "W-certificate and Verified-certificate share identical PAL output and fallback attempts.",
                  "Symbolic solving has zero model tokens; CPU timings are reported separately.",
                  "Generic certificate verification includes an exact uniqueness check. Its CPU cost is explicit.",
                  "Synthetic token counts validate accounting only. Saved strategy-time sums are replayed, not online latency.",
                  "Intervals resample groups, preserving all seeds. A CI containing zero does not prove noninferiority.",
                  "Degenerate accuracy bootstraps cannot pass the gate without a reviewed boundary-safe statistical addendum.",
                  "Measured execution remains pending review, sample-size justification and Stage 0 requirements."])
    return "\n".join(lines) + "\n"


def run_smoke(output):
    if Path(output).exists():
        raise FileExistsError(f"Output already exists: {output}")
    dataset = smoke_dataset()
    records = _smoke_records(dataset)
    validate_records(dataset, records, evidence="synthetic_smoke", settings=SETTINGS)
    results = evaluate(dataset, records)
    summary = summarize(results, evidence="synthetic_smoke")
    _save(output, {"dataset.json": dataset, "records.json": records, "settings.json": SETTINGS,
                   "results.json": results, "summary.json": summary, "report.md": report(summary)},
          {"mode": "order_certificate_study", "evidence": "synthetic_smoke", "model_calls": False})


def replay(source, output):
    if Path(output).exists():
        raise FileExistsError(f"Output already exists: {output}")
    source = Path(source)
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest.get("status") != "complete" or manifest.get("mode") != "order_certificate_study":
        raise ValueError("Requires a complete ordering certificate run")
    if manifest.get("evidence") != "synthetic_smoke":
        raise ValueError("Measured ingestion requires the reviewed execution addendum; currently only smoke replay is enabled")
    if manifest.get("source_sha256") != source_hashes():
        raise ValueError("Semantic source hashes changed")
    hashes = manifest.get("artifact_sha256", {})
    if not {"dataset.json", "records.json", "settings.json"} <= hashes.keys():
        raise ValueError("Missing hashed source artifacts")
    for name, expected in hashes.items():
        if Path(name).name != name or name == "manifest.json" or file_hash(source / name) != expected:
            raise ValueError(f"Source artifact changed: {name}")
    dataset = json.loads((source / "dataset.json").read_text())
    records = json.loads((source / "records.json").read_text())
    settings = json.loads((source / "settings.json").read_text())
    validate_records(dataset, records, evidence=manifest["evidence"], settings=settings)
    results = evaluate(dataset, records)
    summary = summarize(results, evidence=manifest["evidence"])
    _save(output, {"results.json": results, "summary.json": summary, "report.md": report(summary)},
          {"mode": "order_certificate_analysis", "evidence": manifest["evidence"],
           "source_manifest_sha256": file_hash(source / "manifest.json"), "model_calls": False})
