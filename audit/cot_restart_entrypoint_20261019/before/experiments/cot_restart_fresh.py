"""Offline adapter for fresh CoT restart frames; real inference is disabled.

This is software preparation, not a new research collection entry point.
Historical sources/plans stay byte-for-byte intact. A future reviewed campaign
must integrate through experiments.research_study and freeze its own sources.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path

from experiments.cot_restart_pilot import (
    ALIGNED_DIRECT_COT_SUFFIX_TEXT, MockLLM, execute_llm_call,
    make_prefix_menu, reasoning_prefix,
)
from experiments.cot_restart_replay import (
    CAP_SWEEP_SEED_POLICY, derive_cap_sweep_seed, encode_prompt, score_replay,
)
from experiments.order_pilot_checkpoint import atomic_json, encoded
from experiments.research_study import validate_dataset

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = "synthetic_fresh_restart_smoke"
SOURCE_FILES = (
    "experiments/cot_restart_fresh.py", "experiments/cot_restart_pilot.py",
    "experiments/cot_restart_replay.py", "experiments/order_pilot_checkpoint.py",
    "experiments/research_study.py", "research_identity.py",
    "research_prompt_profiles.py", "reasoning_strategies.py", "scripts/gen_tasks.py",
)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class MockSettings:
    # Required caps are software-test inputs, never inferred from gold/results.
    base_cap: int
    completion_cap: int
    base_seed: int = 42
    q_star: float = .5
    include_a: bool = False

    def __post_init__(self):
        if any(type(v) is not int or v < 1 for v in (self.base_cap, self.completion_cap)):
            raise ValueError("Mock completion caps must be positive integers")
        if type(self.base_seed) is not int or self.base_seed < 0:
            raise ValueError("base_seed must be a nonnegative integer")
        if self.q_star != .5 or type(self.include_a) is not bool:
            raise ValueError("This adapter keeps q=0.50 and a boolean A-ablation option")


def select_frame(dataset, split):
    """One outcome-blind representative per group; retain canonical split checks."""
    validate_dataset(dataset, require_all_splits=False)
    if split not in ("train", "calibration", "test"):
        raise ValueError("Unknown frame split")
    groups = defaultdict(list)
    for item in dataset["items"]:
        if item["split"] == split:
            groups[item["group_id"]].append(item)
    if not groups:
        raise ValueError("Selected split contains no groups")
    representatives = [min(rows, key=lambda r: r["id"]) for _, rows in sorted(groups.items())]
    if any(item.get("family") not in ("arith", "order", "g24") for item in representatives):
        raise ValueError("Fresh adapter requires a supported procedural family")
    return representatives


def build_request(item, tokenizer, settings, arm, base=None):
    """Only query/base text affect prompts; gold/correctness never affect calls."""
    prefix, actual = "", 0.0
    if arm in ("F", "CONT"):
        if base is None or base["question_id"] != item["id"] or base["arm"] != "O":
            raise ValueError("F/CONT require this question's newly collected O record")
        body = reasoning_prefix(base["raw_output"])[0]
        if arm == "CONT":
            prefix, actual = body, 1.0
        else:
            _, menu = make_prefix_menu(base["raw_output"], lambda t: len(tokenizer.encode(t, add_special_tokens=False)))
            choice = next(m for m in menu if m["q_requested"] == settings.q_star)
            prefix, actual = choice["prefix"], choice["q_actual"]
    elif arm not in ("O", "A") or (arm == "A" and not settings.include_a):
        raise ValueError("Unsupported arm")
    messages = [{"role": "user", "content": item["query"] + ALIGNED_DIRECT_COT_SUFFIX_TEXT["COT"]}]
    if prefix:
        messages.append({"role": "assistant", "content": prefix})
    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, enable_thinking=False,
        continue_final_message=bool(prefix), add_generation_prompt=not bool(prefix),
    )
    ids = encode_prompt(tokenizer, prompt)
    return {
        "question_id": item["id"], "group_id": item["group_id"], "family": item["family"],
        "arm": arm, "prompt": prompt, "prompt_token_ids": ids, "prompt_tokens": len(ids),
        "prefix_text": prefix, "q_requested": settings.q_star if arm == "F" else float(arm == "CONT"),
        "q_actual": actual, "prefix_collapsed_to_empty": arm in ("F", "CONT") and not prefix,
        "completion_cap": settings.base_cap if arm == "O" else settings.completion_cap,
        "temperature": 0.0 if arm == "O" else .6,
        "seed": derive_cap_sweep_seed(settings.base_seed, item["id"], arm),
        "seed_policy": CAP_SWEEP_SEED_POLICY,
        "base_generation_sha256": digest({key: base[key] for key in (
            "prompt_token_ids", "completion_token_ids", "raw_output", "seed",
            "completion_cap", "decoding_config", "finish_reason",
        )}) if arm != "O" and base is not None else None,
    }


class _Journal:
    """Fsynced attempts, strict resume, and no automatic retry of uncertain calls."""

    def __init__(self, output, identity, dataset, settings):
        self.output, self.identity = Path(output), identity
        self.head, self.count, self.started, self.completed = "0" * 64, 0, {}, {}
        self.lock, self.manifest = None, None
        exists = self.output.exists()
        if exists and not (self.output / "manifest.json").is_file():
            raise ValueError("Existing output lacks a manifest; use a new directory")
        if not exists:
            self.output.mkdir(parents=True)
        try:
            self.lock = (self.output / ".writer.lock").open("a")
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if exists:
                self.manifest = json.loads((self.output / "manifest.json").read_text())
                if self.manifest.get("identity") != identity:
                    raise ValueError("Resume dataset/settings/source identity mismatch")
                if self.manifest.get("evidence") != EVIDENCE or self.manifest.get("real_model_calls") != 0:
                    raise ValueError("Invalid synthetic manifest evidence")
                for name, value in (("dataset.json", dataset), ("settings.json", settings)):
                    if json.loads((self.output / name).read_text()) != value:
                        raise ValueError(f"Pinned {name} changed")
                anchors = {self.head}
                for line in (self.output / "calls.jsonl").read_text().splitlines(keepends=True):
                    if not line.endswith("\n"):
                        raise ValueError("Torn journal tail; preserve for review")
                    entry = json.loads(line)
                    body = {k: v for k, v in entry.items() if k != "sha256"}
                    if entry["sha256"] != digest(body) or body["previous"] != self.head or body["sequence"] != self.count:
                        raise ValueError("Journal checksum/chain mismatch")
                    key = tuple(body["key"])
                    if body["kind"] == "call_started":
                        if key in self.started:
                            raise ValueError("Duplicate call attempt")
                        self.started[key] = body["value"]
                    elif body["kind"] == "call_completed":
                        if key not in self.started or key in self.completed:
                            raise ValueError("Unpaired or duplicate completed call")
                        if body["value"]["request_sha256"] != self.started[key]["request_sha256"]:
                            raise ValueError("Completed call differs from started request")
                        self.completed[key] = body["value"]
                    else:
                        raise ValueError("Unknown journal kind")
                    self.head, self.count = entry["sha256"], self.count + 1
                    anchors.add(self.head)
                if self.manifest.get("journal_head") not in anchors:
                    raise ValueError("Manifest head absent from journal")
                if self.manifest.get("status") == "complete":
                    hashes = self.manifest.get("artifact_sha256", {})
                    if set(hashes) != {"dataset.json", "settings.json", "calls.jsonl", "records.json", "paths.json"}:
                        raise ValueError("Missing completed artifact hashes")
                    if self.manifest.get("journal_head") != self.head or self.manifest.get("journal_entries") != self.count:
                        raise ValueError("Completed manifest differs from journal")
                    for name, expected in hashes.items():
                        if file_digest(self.output / name) != expected:
                            raise ValueError(f"Completed artifact changed: {name}")
                if set(self.started) != set(self.completed):
                    raise ValueError("Unfinished attempt: no automatic retry; preserve output and review budget")
            else:
                self.manifest = {
                    "identity": identity, "status": "running", "evidence": EVIDENCE,
                    "real_model_calls": 0, "confirmatory": False, "stage_0_changed": False,
                    "decision_states_enabled": False, "journal_head": self.head,
                }
                atomic_json(self.output / "dataset.json", dataset)
                atomic_json(self.output / "settings.json", settings)
                (self.output / "calls.jsonl").touch(exist_ok=False)
                self.save()
        except BaseException:
            self.close()
            raise

    def save(self, **extra):
        self.manifest.update(
            journal_head=self.head, journal_entries=self.count,
            attempted_mock_calls=len(self.started), completed_mock_calls=len(self.completed),
            cost_status="known_synthetic_tokens" if set(self.started) == set(self.completed) else "unknown_incurred",
            **extra,
        )
        atomic_json(self.output / "manifest.json", self.manifest)

    def append(self, kind, key, value):
        body = {"kind": kind, "key": list(key), "value": value, "sequence": self.count, "previous": self.head}
        entry = {**body, "sha256": digest(body)}
        with (self.output / "calls.jsonl").open("a") as handle:
            handle.write(encoded(entry) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.head, self.count = entry["sha256"], self.count + 1
        (self.started if kind == "call_started" else self.completed)[tuple(key)] = value
        self.save()

    def close(self):
        if self.lock is not None:
            self.lock.close()
            self.lock = None


def _paths(records):
    by_item = defaultdict(dict)
    for record in records:
        by_item[record["question_id"]][record["arm"]] = record
    result = []
    for item, arms in sorted(by_item.items()):
        base = arms["O"]
        for arm, record in arms.items():
            calls = [base] if arm == "O" else [base, record]
            prompt = sum(r["prompt_tokens"] for r in calls)
            completion = sum(r["completion_tokens"] for r in calls)
            result.append({
                "question_id": item, "group_id": record["group_id"], "arm": arm,
                "correct": record["correct"], "parsed_answer": record["parsed_answer"],
                "path_call_arms": [r["arm"] for r in calls], "path_prompt_tokens": prompt,
                "path_completion_tokens_including_eos": completion, "path_total_tokens": prompt + completion,
                "cost_scope": "synthetic token counts, base once plus selected arm; excludes inference overhead",
                "evidence": EVIDENCE,
            })
    return result


def run_mock(dataset, output, settings, *, split="train", model=None):
    """Exercise the complete adapter only on explicitly synthetic questions.

    No approval argument can enable real inference. New study data stay behind
    the existing review/freeze process and the supported research entry point.
    """
    if dataset.get("evidence") != "synthetic_smoke" or dataset.get("role") != "synthetic_software_validation":
        raise ValueError("Mock adapter accepts explicitly synthetic fixtures only; real candidate data remain uncollected")
    if not isinstance(settings, MockSettings):
        raise ValueError("MockSettings required")
    if model is not None and not isinstance(model, MockLLM):
        raise ValueError("Only the offline MockLLM backend is supported")
    items = select_frame(dataset, split)
    config = {**asdict(settings), "split": split, "mock": True,
              "arms": ["O", "F", "CONT"] + (["A"] if settings.include_a else []),
              "max_attempted_mock_calls": len(items) * (4 if settings.include_a else 3),
              "completion_budget_scope": "same fixed new-completion cap for F/CONT/A; not registered M/D",
              "base_sampling": "greedy", "continuation_sampling": "temperature=0.6, top_p=0.95"}
    model = model or MockLLM()
    identity = {"dataset_sha256": digest(dataset), "settings_sha256": digest(config),
                "source_sha256": {p: file_digest(ROOT / p) for p in SOURCE_FILES},
                "mock_eos_at": model.eos_at, "evidence": EVIDENCE, "schema_version": 1}
    journal = _Journal(output, identity, dataset, config)
    try:
        if journal.manifest["status"] == "complete":
            return journal.manifest
        records = []
        for item in items:
            base = None
            for arm in config["arms"]:
                request = build_request(item, model.tokenizer, settings, arm, base)
                key = (item["id"], arm)
                if key in journal.completed:
                    record = journal.completed[key]
                    if record["request_sha256"] != digest(request):
                        raise ValueError("Cached call differs from reconstructed request")
                else:
                    if len(journal.started) >= config["max_attempted_mock_calls"]:
                        raise RuntimeError("Mock call ceiling reached")
                    journal.append("call_started", key, {
                        "request_sha256": digest(request), "prompt_tokens": request["prompt_tokens"],
                        "reserved_completion_cap": request["completion_cap"],
                    })
                    captured = {}
                    _, _, _, duration = execute_llm_call(
                        model, model.tokenizer, request["prompt"], request["completion_cap"],
                        request["temperature"], request["seed"], is_mock=True, capture=captured,
                    )
                    record = {**request, **captured, "duration_ms": duration, "evidence": EVIDENCE,
                              "request_sha256": digest(request),
                              "total_tokens": captured["prompt_tokens"] + captured["completion_tokens"]}
                    scored = score_replay(record, model.tokenizer, record["completion_cap"], item,
                                          prefix_text=request["prefix_text"])
                    for field in ("full_response", "parsed_answer", "parse_status", "wordy", "correct"):
                        record[field] = scored[field]
                    journal.append("call_completed", key, record)
                records.append(record)
                if arm == "O":
                    base = record
        atomic_json(Path(output) / "records.json", records)
        atomic_json(Path(output) / "paths.json", _paths(records))
        journal.manifest.pop("error", None)
        journal.save(
            status="complete", real_model_calls=0, original_groups=len(items),
            total_synthetic_prompt_tokens=sum(r["prompt_tokens"] for r in records),
            total_synthetic_completion_tokens_including_eos=sum(r["completion_tokens"] for r in records),
            total_synthetic_collection_tokens=sum(r["total_tokens"] for r in records),
            artifact_sha256={n: file_digest(Path(output) / n) for n in (
                "dataset.json", "settings.json", "calls.jsonl", "records.json", "paths.json")},
        )
        return journal.manifest
    except BaseException as error:
        journal.save(status="interrupted", error=str(error))
        raise
    finally:
        journal.close()


def synthetic_dataset():
    """Three authored software fixtures; no candidate/held-out content is read."""
    from research_identity import canonical_problem_id
    from scripts import gen_tasks

    specs = [
        ("arith", {"start": 40, "steps": [["add", 2]]}, "42"),
        ("order", {"names": ["Arin", "Beryl"], "clues": [["b", 0, 1]], "ask": 0}, "Arin"),
        ("g24", {"numbers": [1, 2, 3, 4]}, "(1+3)*(2+4)"),
    ]
    items = []
    for family, meta, answer in specs:
        row = {"id": f"synthetic-fresh-{family}", "family": family, "checker": family,
               "meta": meta, "answer": answer, "split": "train", "level": 0,
               "answer_type": "number" if family == "arith" else "text",
               "query": getattr(gen_tasks, f"render_{family}")(meta)}
        row["group_id"] = row["problem_id"] = canonical_problem_id(row)
        items.append(row)
    return {"name": "fresh-restart-software-fixture", "version": "1",
            "source": "Three authored synthetic software fixtures; no study-pool inputs",
            "license": "Project software-test fixtures", "identity_version": "procedural-v1",
            "role": "synthetic_software_validation", "evidence": "synthetic_smoke", "items": items}
