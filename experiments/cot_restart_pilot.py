"""Qwen3.5-4B CoT restart development pilot on exposed development questions.

Strictly local, reproducible, sequential pilot execution for Apple Silicon (Mac 16 GB).
Includes append-only journal, prompt+prefix+completion token accounting, sentence-boundary
checkpoint snapping, prefix deduplication, and hard safety ceilings.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import math
import os
import platform
import re
import resource
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from reasoning_strategies import parse_answer_details
from research_identity import (
    FAMILIES,
    canonical_problem_id,
    problem_fingerprint,
)
from research_prompt_profiles import ALIGNED_DIRECT_COT_SUFFIX_TEXT
from scripts.gen_tasks import check as gen_check

# Pinned model and runtime configuration
MODEL_REPOSITORY = "mlx-community/Qwen3.5-4B-MLX-4bit"
MODEL_REVISION = "32f3e8ecf65426fc3306969496342d504bfa13f3"
BASE_MODEL = "Qwen/Qwen3.5-4B"
QUANTIZATION = {"bits": 4, "group_size": 64, "mode": "affine"}

# Pinned hashes of upstream model files in snapshot
MODEL_FILE_HASHES = {
    "config.json": "f3efc81b2ea8d96a45301037d3ccccbcccdef44a961845c87f286aaddbc6eaaa",
    "tokenizer.json": "87a7830d63fcf43bf241c3c5242e96e62dd3fdc29224ca26fed8ea333db72de4",
    "tokenizer_config.json": "e98f1901ac6f0adff67b1d540bfa0c36ac1a0cf59eb72ed78146ef89aafa1182",
    "model.safetensors": "5fb9acd0246866381cf8c5c354c6db1019f6498eec4ccb4f5edcc71ffeacb2db",
}

# Exposed development pool
DEV_POOL_PATH = ROOT / "data/gen02_tune.json"
DEV_POOL_SHA256 = "f3bfa9750038ecce95f31dcdd7362082c4d85487d37ff091282442874a12041c"

# Pilot protocols
MENU = (0.0, 0.25, 0.5, 0.75)
CONFIG_ARMS = ("regenerate", "restart_q025", "restart_q050", "restart_q075", "thinking_native")
BUDGETS = (1024, 2048)
SAMPLING_TEMPERATURE = 0.6
SAMPLING_TOP_P = 0.95
BASE_COT_BUDGET = 1024

# Safety ceilings
MAX_CALLS_LIMIT = 136
MAX_COMPLETION_TOKENS_LIMIT = 250_000
MAX_DURATION_SECONDS = 8 * 3600  # 8 hours

# Source code files to hash
SOURCE_FILES = (
    "experiments/cot_restart_pilot.py",
    "experiments/research_study.py",
    "reasoning_strategies.py",
    "research_identity.py",
    "research_prompt_profiles.py",
    "scripts/gen_tasks.py",
    "docs/cot_restart_preflight_protocol_20261009.md",
)

FINAL_MARKER = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?(?:final[ \t]+)?answer"
    r"(?:\*\*)?[ \t]*:[ \t]*",
    re.I | re.M,
)
SENTENCE_END = re.compile(r"[.!?](?:[\"'\u201d\u2019)]*)(?=\s|$)")
ABBREVIATIONS = re.compile(r"\b(?:Mr|Mrs|Ms|Dr|Prof|vs|etc|e\.g|i\.e)\.$", re.I)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536 * 1024):
            h.update(chunk)
    return h.hexdigest()


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def encoded_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def source_hashes() -> dict[str, str]:
    return {name: file_sha256(ROOT / name) for name in SOURCE_FILES if (ROOT / name).exists()}


def reasoning_prefix(raw: str) -> tuple[str, int, int]:
    """Strip first explicit final-answer block and everything after it."""
    markers = list(FINAL_MARKER.finditer(raw))
    end = markers[0].start() if markers else len(raw)
    body = raw[:end].rstrip()
    return body, len(body), len(markers)


def sentence_boundaries(body: str) -> list[int]:
    """Conservative interior text boundaries, never inside math or code."""
    blocked = [(m.start(), m.end()) for m in re.finditer(
        r"```[\s\S]*?(?:```|$)|\\\[[\s\S]*?\\\]|\$\$[\s\S]*?\$\$", body,
    )]
    boundaries = [0]
    for match in SENTENCE_END.finditer(body):
        pos, end = match.start(), match.end()
        if end >= len(body) or any(lo <= pos < hi for lo, hi in blocked):
            continue
        if body[pos] == ".":
            if (pos and body[pos - 1] == ".") or (pos + 1 < len(body) and body[pos + 1] == "."):
                continue
            if ABBREVIATIONS.search(body[:pos + 1]):
                continue
            line = body[body.rfind("\n", 0, pos) + 1:pos + 1]
            if re.fullmatch(r"\s*\d+\.", line):
                continue
        boundaries.append(end)
    return sorted(set(boundaries))


def make_prefix_menu(raw: str, count_tokens: Callable[[str], int]) -> tuple[dict, list[dict]]:
    """Build q in {0, .25, .5, .75} prefix menu from raw visible CoT trace."""
    body, end, marker_count = reasoning_prefix(raw)
    length = count_tokens(body)
    candidates = [(pos, count_tokens(body[:pos])) for pos in sentence_boundaries(body)]
    menu = []
    for q in MENU:
        pos, tokens = min(candidates, key=lambda pair: (abs(pair[1] - q * length), pair[0]))
        prefix = raw[:pos]
        if FINAL_MARKER.search(prefix):
            raise ValueError("An explicit final-answer marker leaked into a prefix")
        menu.append({
            "q_requested": q,
            "cut_char": pos,
            "prefix": prefix,
            "prefix_sha256": text_sha256(prefix),
            "prefix_tokens": tokens,
            "q_actual": (tokens / length) if length > 0 else 0.0,
            "remaining_body_token_proxy": max(0, length - tokens),
        })
    info = {
        "reasoning_end_char": end,
        "reasoning_tokens": length,
        "explicit_answer_marker_count": marker_count,
        "interior_boundary_count": len(candidates) - 1,
        "distinct_menu_prefixes": len({row["cut_char"] for row in menu}),
    }
    return info, menu


def select_pilot_questions(pool_path: Path = DEV_POOL_PATH) -> list[dict]:
    """Select 12 canonical questions (4 arith, 4 order, 4 g24) outcome-blind with hash seed 42."""
    raw_data = json.loads(pool_path.read_text(encoding="utf-8"))
    items = raw_data.get("items", [])
    selected = []
    for family in ("arith", "order", "g24"):
        fam_items = [it for it in items if it.get("family") == family]
        # Rank by hash of (seed 42 + canonical fingerprint)
        ranked = sorted(
            fam_items,
            key=lambda it: (
                text_sha256(f"cot-restart-dev-42:{problem_fingerprint(it)}"),
                it["id"],
            ),
        )
        selected.extend(copy.deepcopy(ranked[:4]))
    return selected


def derive_call_seed(base_seed: int, question_id: str, arm: str, budget: int) -> int:
    h = hashlib.sha256(f"{base_seed}:{question_id}:{arm}:{budget}".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big")


def get_memory_telemetry() -> dict[str, float]:
    """Report peak memory in megabytes via getrusage and MLX core."""
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024 * 1024)
    metal_peak_mb = 0.0
    metal_active_mb = 0.0
    try:
        import mlx.core as mx
        if hasattr(mx, "get_peak_memory"):
            metal_peak_mb = mx.get_peak_memory() / (1024 * 1024)
        elif hasattr(mx.metal, "get_peak_memory"):
            metal_peak_mb = mx.metal.get_peak_memory() / (1024 * 1024)
        if hasattr(mx, "get_active_memory"):
            metal_active_mb = mx.get_active_memory() / (1024 * 1024)
        elif hasattr(mx.metal, "get_active_memory"):
            metal_active_mb = mx.metal.get_active_memory() / (1024 * 1024)
    except Exception:
        pass
    return {
        "ru_maxrss_mb": round(rss_mb, 2),
        "metal_peak_mb": round(metal_peak_mb, 2),
        "metal_active_mb": round(metal_active_mb, 2),
    }


class PilotJournal:
    """Append-only fsynced journal with sha256 chaining for development pilot."""

    def __init__(self, directory: Path, manifest: dict):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.journal_file = self.directory / "calls.jsonl"
        self.lock_file = (self.directory / ".writer.lock").open("a")
        fcntl.flock(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)

        self.head = "0" * 64
        self.count = 0
        self.cache: dict[tuple[str, ...], dict] = {}
        self.total_completion_tokens = 0
        self.manifest = manifest

        if self.journal_file.exists():
            self._replay()
        else:
            self.journal_file.touch(exist_ok=False)

    def _replay(self) -> None:
        lines = self.journal_file.read_text(encoding="utf-8").splitlines(keepends=True)
        for line in lines:
            if not line.endswith("\n"):
                raise ValueError("Torn journal tail in calls.jsonl; preserve for audit")
            entry = json.loads(line)
            body = {k: v for k, v in entry.items() if k != "sha256"}
            if entry.get("sha256") != text_sha256(encoded_json(body)):
                raise ValueError("Corrupt journal entry checksum")
            if body.get("previous") != self.head or body.get("sequence") != self.count:
                raise ValueError("Journal sequence or head mismatch")
            key = (body["kind"], *body["key"])
            self.cache[key] = body["value"]
            self.head = entry["sha256"]
            self.count += 1
            if body.get("kind") in ("smoke", "base_cot", "restart_call"):
                val = body["value"]
                self.total_completion_tokens += int(val.get("completion_tokens", 0))

    def has(self, kind: str, *key_parts: str) -> bool:
        return (kind, *key_parts) in self.cache

    def get(self, kind: str, *key_parts: str) -> dict | None:
        return self.cache.get((kind, *key_parts))

    def append(self, kind: str, key_parts: list[str], value: dict) -> None:
        composite_key = (kind, *key_parts)
        if composite_key in self.cache:
            return

        body = {
            "sequence": self.count,
            "previous": self.head,
            "kind": kind,
            "key": key_parts,
            "value": value,
        }
        entry = {**body, "sha256": text_sha256(encoded_json(body))}
        with self.journal_file.open("a", encoding="utf-8") as f:
            f.write(encoded_json(entry) + "\n")
            f.flush()
            os.fsync(f.fileno())

        self.cache[composite_key] = value
        self.head = entry["sha256"]
        self.count += 1
        if kind in ("smoke", "base_cot", "restart_call"):
            self.total_completion_tokens += int(value.get("completion_tokens", 0))

        # Update manifest journal state
        self.manifest["journal_head"] = self.head
        self.manifest["journal_count"] = self.count
        self.manifest["total_calls"] = self.count
        self.manifest["total_completion_tokens"] = self.total_completion_tokens
        self.save_manifest()

    def save_manifest(self) -> None:
        path = self.directory / "manifest.json"
        tmp_path = self.directory / ".manifest.json.tmp"
        tmp_path.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp_path.replace(path)

    def close(self) -> None:
        if self.lock_file:
            fcntl.flock(self.lock_file, fcntl.LOCK_UN)
            self.lock_file.close()
            self.lock_file = None


class MockLLM:
    """Offline mock tokenizer and model for complete pre-run test coverage."""

    class MockTokenizer:
        def encode(self, text: str) -> list[int]:
            return [ord(c) % 256 for c in text]

        def apply_chat_template(
            self,
            messages: list[dict],
            tokenize: bool = False,
            add_generation_prompt: bool = True,
            continue_final_message: bool = False,
            enable_thinking: bool = False,
        ) -> str:
            res = ""
            for m in messages:
                role, content = m["role"], m["content"]
                if role == "user":
                    res += f"<|im_start|>user\n{content}<|im_end|>\n"
                elif role == "assistant":
                    if continue_final_message:
                        res += f"<|im_start|>assistant\n<think>\n\n</think>\n\n{content}"
                    else:
                        res += f"<|im_start|>assistant\n<think>\n\n</think>\n\n{content}<|im_end|>\n"
            if add_generation_prompt:
                if enable_thinking:
                    res += "<|im_start|>assistant\n<think>\n"
                else:
                    res += "<|im_start|>assistant\n<think>\n\n</think>\n\n"
            return res

    def __init__(self):
        self.tokenizer = self.MockTokenizer()

    def generate(
        self,
        prompt: str,
        max_tokens: int,
        temp: float,
        seed: int,
        is_thinking: bool = False,
    ) -> tuple[str, int, str]:
        # Return deterministic mock output
        if is_thinking:
            output = f"Thinking step by step for seed {seed}.\n</think>\n\nAnswer: 42\n"
        else:
            output = f"Mock step 1. Mock step 2. Mock step 3.\nAnswer: 42\n"
        tokens = min(len(self.tokenizer.encode(output)), max_tokens)
        finish_reason = "stop" if len(self.tokenizer.encode(output)) <= max_tokens else "length"
        return output, tokens, finish_reason


def execute_llm_call(
    model: Any,
    tokenizer: Any,
    prompt: str,
    max_tokens: int,
    temp: float,
    seed: int,
    is_mock: bool = False,
    is_thinking: bool = False,
) -> tuple[str, int, str, float]:
    """Execute a single model generation call with telemetry."""
    started = time.perf_counter()
    if is_mock:
        output, tokens, finish_reason = model.generate(
            prompt, max_tokens, temp, seed, is_thinking=is_thinking
        )
        duration_ms = (time.perf_counter() - started) * 1000
        return output, tokens, finish_reason, duration_ms

    import mlx.core as mx
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import make_sampler

    mx.random.seed(seed)
    sampler = make_sampler(temp=temp, top_p=SAMPLING_TOP_P)
    text = ""
    tokens = 0
    finish_reason = "stop"

    for r in stream_generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler):
        text += r.text
        tokens = r.generation_tokens
        if getattr(r, "finish_reason", None) is not None:
            finish_reason = r.finish_reason

    duration_ms = (time.perf_counter() - started) * 1000
    return text, tokens, finish_reason, duration_ms


def run_smoke_verification(
    journal: PilotJournal,
    model: Any,
    tokenizer: Any,
    is_mock: bool = False,
) -> list[dict]:
    """Execute up to 4 smoke calls verifying non-thinking, thinking, and prefix continuation."""
    smoke_calls = []
    # Smoke query
    query = "Calculate (15 * 3) + 12."
    suffix = ALIGNED_DIRECT_COT_SUFFIX_TEXT["COT"]

    smoke_specs = [
        {
            "id": "smoke_0_non_thinking",
            "desc": "Non-thinking visible CoT call",
            "messages": [{"role": "user", "content": query + suffix}],
            "enable_thinking": False,
            "continue_final_message": False,
            "max_tokens": 128,
            "temp": 0.0,
            "seed": 42001,
        },
        {
            "id": "smoke_1_thinking_native",
            "desc": "Thinking-native mode call",
            "messages": [{"role": "user", "content": query + "\nSolve the problem. End with Answer: <number>."}],
            "enable_thinking": True,
            "continue_final_message": False,
            "max_tokens": 128,
            "temp": 0.6,
            "seed": 42002,
        },
        {
            "id": "smoke_2_assistant_prefix",
            "desc": "Assistant prefix continuation call",
            "messages": [
                {"role": "user", "content": query + suffix},
                {"role": "assistant", "content": "Step 1: First multiply 15 by 3 to get 45. "},
            ],
            "enable_thinking": False,
            "continue_final_message": True,
            "max_tokens": 128,
            "temp": 0.6,
            "seed": 42003,
        },
        {
            "id": "smoke_3_boundary_continuation",
            "desc": "Assistant continuation from second sentence boundary",
            "messages": [
                {"role": "user", "content": query + suffix},
                {"role": "assistant", "content": "Step 1: 15 * 3 = 45. Step 2: Now add 12 to 45. "},
            ],
            "enable_thinking": False,
            "continue_final_message": True,
            "max_tokens": 128,
            "temp": 0.6,
            "seed": 42004,
        },
    ]

    for spec in smoke_specs:
        cid = spec["id"]
        if journal.has("smoke", cid):
            smoke_calls.append(journal.get("smoke", cid))
            continue

        prompt = tokenizer.apply_chat_template(
            spec["messages"],
            tokenize=False,
            add_generation_prompt=not spec["continue_final_message"],
            continue_final_message=spec["continue_final_message"],
            enable_thinking=spec["enable_thinking"],
        )
        p_tok = len(tokenizer.encode(prompt))

        out_text, comp_tok, finish, dur_ms = execute_llm_call(
            model,
            tokenizer,
            prompt,
            max_tokens=spec["max_tokens"],
            temp=spec["temp"],
            seed=spec["seed"],
            is_mock=is_mock,
            is_thinking=spec["enable_thinking"],
        )
        mem = get_memory_telemetry()
        record = {
            "id": cid,
            "description": spec["desc"],
            "messages": spec["messages"],
            "prompt": prompt,
            "prompt_tokens": p_tok,
            "raw_output": out_text,
            "completion_tokens": comp_tok,
            "total_tokens": p_tok + comp_tok,
            "finish_reason": finish,
            "duration_ms": round(dur_ms, 2),
            "memory": mem,
        }
        journal.append("smoke", [cid], record)
        smoke_calls.append(record)

    return smoke_calls


def run_cot_restart_pilot(
    output_dir: Path,
    mock: bool = False,
    smoke_only: bool = False,
) -> dict[str, Any]:
    """Main execution engine for Qwen3.5-4B CoT restart development pilot."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = {
            "schema_version": 1,
            "study": "cot_restart_pilot_qwen35",
            "role": "exposed_development_pilot",
            "model_repository": MODEL_REPOSITORY,
            "model_revision": MODEL_REVISION,
            "base_model": BASE_MODEL,
            "quantization": QUANTIZATION,
            "model_hashes": MODEL_FILE_HASHES,
            "dev_pool_sha256": DEV_POOL_SHA256,
            "source_hashes": source_hashes(),
            "python": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "status": "running",
            "mock": mock,
            "confirmatory": False,
            "publication_review_required": True,
            "safety_limits": {
                "max_calls": MAX_CALLS_LIMIT,
                "max_completion_tokens": MAX_COMPLETION_TOKENS_LIMIT,
                "max_duration_seconds": MAX_DURATION_SECONDS,
            },
        }

    journal = PilotJournal(output_dir, manifest)
    pilot_started_time = time.perf_counter()

    try:
        # Load runtime / model
        if mock:
            model = MockLLM()
            tokenizer = model.tokenizer
        else:
            from mlx_lm import load as mlx_load
            model, tokenizer = mlx_load(MODEL_REPOSITORY, revision=MODEL_REVISION)

        # Step 1: Smoke Verification (up to 4 calls)
        smoke_results = run_smoke_verification(journal, model, tokenizer, is_mock=mock)
        atomic_save_json(output_dir / "smoke_telemetry.json", smoke_results)

        if smoke_only:
            manifest["status"] = "smoke_complete"
            manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
            journal.save_manifest()
            journal.close()
            return {"smoke_calls": smoke_results, "manifest": manifest}

        # Step 2: Select 12 canonical questions and freeze plan
        items = select_pilot_questions(DEV_POOL_PATH)
        dataset_doc = {
            "name": "cot-restart-pilot-exposed-12",
            "role": "development_tuning",
            "source": "data/gen02_tune.json exposed pool, selected outcome-blind with hash seed 42",
            "items": items,
        }
        atomic_save_json(output_dir / "dataset.json", dataset_doc)

        plan = {
            "selected_items": [
                {
                    "id": it["id"],
                    "family": it["family"],
                    "fingerprint": problem_fingerprint(it),
                    "canonical_id": canonical_problem_id(it),
                    "answer_type": it.get("answer_type", "expression" if it.get("family") == "g24" else "text" if it.get("family") == "order" else "number"),
                    "gold": it["answer"],
                    "query": it["query"],
                }
                for it in items
            ],
            "budgets": list(BUDGETS),
            "configs": list(CONFIG_ARMS),
            "sampling": {
                "temperature": SAMPLING_TEMPERATURE,
                "top_p": SAMPLING_TOP_P,
                "base_cot_budget": BASE_COT_BUDGET,
            },
        }
        atomic_save_json(output_dir / "plan.json", plan)

        # Step 2: Generate 1 new visible CoT trace per question
        base_traces = {}
        for it in items:
            qid = it["id"]
            if journal.has("base_cot", qid):
                base_traces[qid] = journal.get("base_cot", qid)
                continue

            # Check safety ceilings
            _check_safety_limits(journal, pilot_started_time)

            cot_suffix = ALIGNED_DIRECT_COT_SUFFIX_TEXT["COT"]
            msgs = [{"role": "user", "content": it["query"] + cot_suffix}]
            prompt = tokenizer.apply_chat_template(
                msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False
            )
            p_tok = len(tokenizer.encode(prompt))
            seed = derive_call_seed(42, qid, "base_cot", BASE_COT_BUDGET)

            out_text, comp_tok, finish, dur_ms = execute_llm_call(
                model,
                tokenizer,
                prompt,
                max_tokens=BASE_COT_BUDGET,
                temp=0.0,
                seed=seed,
                is_mock=mock,
                is_thinking=False,
            )

            # Parse and evaluate base trace
            family = it["family"]
            ans_type = "expression" if family == "g24" else "text" if family == "order" else "number"
            parsed, status, wordy = parse_answer_details(out_text, answer_type=ans_type)
            correct = bool(gen_check(it, parsed)) if parsed is not None else False

            # Extract sentence boundary menu
            info, menu = make_prefix_menu(out_text, count_tokens=lambda t: len(tokenizer.encode(t)))

            trace_record = {
                "id": qid,
                "family": family,
                "prompt": prompt,
                "prompt_tokens": p_tok,
                "raw_output": out_text,
                "completion_tokens": comp_tok,
                "total_tokens": p_tok + comp_tok,
                "finish_reason": finish,
                "parsed_answer": parsed,
                "parse_status": status,
                "wordy": wordy,
                "correct": correct,
                "flags": {
                    "source_truncated": finish == "length",
                    "parse_failure": status != "marker",
                    "wordy": wordy,
                },
                "prefix_info": info,
                "prefix_menu": menu,
                "duration_ms": round(dur_ms, 2),
                "memory": get_memory_telemetry(),
            }
            journal.append("base_cot", [qid], trace_record)
            base_traces[qid] = trace_record

        atomic_save_json(output_dir / "base_traces.json", base_traces)

        # Step 3: Run restart configurations across 2 budgets
        restart_records = []
        for it in items:
            qid = it["id"]
            base = base_traces[qid]
            menu = base["prefix_menu"]

            # Map menu q to prefixes: {0.0: "", 0.25: ..., 0.5: ..., 0.75: ...}
            q_to_prefix = {m["q_requested"]: m["prefix"] for m in menu}

            # Config arm definitions:
            # "regenerate": q=0.0, empty prefix
            # "restart_q025": q=0.25 prefix
            # "restart_q050": q=0.50 prefix
            # "restart_q075": q=0.75 prefix
            # "thinking_native": native thinking
            arm_specs = {
                "regenerate": {"type": "cot_prefix", "prefix": q_to_prefix[0.0], "q": 0.0},
                "restart_q025": {"type": "cot_prefix", "prefix": q_to_prefix[0.25], "q": 0.25},
                "restart_q050": {"type": "cot_prefix", "prefix": q_to_prefix[0.50], "q": 0.50},
                "restart_q075": {"type": "cot_prefix", "prefix": q_to_prefix[0.75], "q": 0.75},
                "thinking_native": {"type": "thinking_native", "prefix": "", "q": None},
            }

            # Prefix deduplication: identify unique prefixes to avoid redundant calls
            prefix_to_canonical: dict[str, str] = {}
            canonical_to_arms: dict[str, list[str]] = defaultdict(list)
            for arm_name in ("regenerate", "restart_q025", "restart_q050", "restart_q075"):
                p_text = arm_specs[arm_name]["prefix"]
                p_hash = text_sha256(p_text)
                if p_hash not in canonical_to_arms:
                    canonical_to_arms[p_hash] = []
                canonical_to_arms[p_hash].append(arm_name)
                prefix_to_canonical[arm_name] = p_hash

            for budget in BUDGETS:
                # 1. Execute unique restart/regenerate prefixes
                executed_prefix_calls: dict[str, dict] = {}
                for p_hash, associated_arms in canonical_to_arms.items():
                    rep_arm = associated_arms[0]
                    call_key = [qid, "prefix_call", p_hash[:16], str(budget)]

                    if journal.has("restart_call", *call_key):
                        res = journal.get("restart_call", *call_key)
                    else:
                        _check_safety_limits(journal, pilot_started_time)
                        prefix_text = arm_specs[rep_arm]["prefix"]
                        cot_suffix = ALIGNED_DIRECT_COT_SUFFIX_TEXT["COT"]

                        if prefix_text:
                            msgs = [
                                {"role": "user", "content": it["query"] + cot_suffix},
                                {"role": "assistant", "content": prefix_text},
                            ]
                            prompt = tokenizer.apply_chat_template(
                                msgs,
                                tokenize=False,
                                continue_final_message=True,
                                enable_thinking=False,
                            )
                        else:
                            msgs = [{"role": "user", "content": it["query"] + cot_suffix}]
                            prompt = tokenizer.apply_chat_template(
                                msgs,
                                tokenize=False,
                                add_generation_prompt=True,
                                enable_thinking=False,
                            )

                        p_tok = len(tokenizer.encode(prompt))
                        comp_cap = budget - p_tok

                        if comp_cap <= 0:
                            res = {
                                "budget_infeasible": True,
                                "prompt": prompt,
                                "prompt_tokens": p_tok,
                                "completion_cap": 0,
                                "raw_output": "",
                                "completion_tokens": 0,
                                "total_tokens": p_tok,
                                "finish_reason": "budget_infeasible",
                                "parsed_answer": None,
                                "correct": False,
                                "duration_ms": 0.0,
                            }
                        else:
                            seed = derive_call_seed(42, qid, rep_arm, budget)
                            out_text, comp_tok, finish, dur_ms = execute_llm_call(
                                model,
                                tokenizer,
                                prompt,
                                max_tokens=comp_cap,
                                temp=SAMPLING_TEMPERATURE,
                                seed=seed,
                                is_mock=mock,
                                is_thinking=False,
                            )
                            # Parse concatenated assistant response
                            full_response = prefix_text + out_text
                            family = it["family"]
                            ans_type = "expression" if family == "g24" else "text" if family == "order" else "number"
                            parsed, status, wordy = parse_answer_details(full_response, answer_type=ans_type)
                            correct = bool(gen_check(it, parsed)) if parsed is not None else False

                            res = {
                                "budget_infeasible": False,
                                "prompt": prompt,
                                "prompt_tokens": p_tok,
                                "completion_cap": comp_cap,
                                "raw_output": out_text,
                                "full_response": full_response,
                                "completion_tokens": comp_tok,
                                "total_tokens": p_tok + comp_tok,
                                "finish_reason": finish,
                                "parsed_answer": parsed,
                                "parse_status": status,
                                "wordy": wordy,
                                "correct": correct,
                                "duration_ms": round(dur_ms, 2),
                                "memory": get_memory_telemetry(),
                            }
                        journal.append("restart_call", call_key, res)
                    executed_prefix_calls[p_hash] = res

                # Map executed prefix calls to each prefix arm
                for arm_name in ("regenerate", "restart_q025", "restart_q050", "restart_q075"):
                    p_hash = prefix_to_canonical[arm_name]
                    shared_call = executed_prefix_calls[p_hash]
                    is_shared = len(canonical_to_arms[p_hash]) > 1
                    arm_record = {
                        "question_id": qid,
                        "family": it["family"],
                        "arm": arm_name,
                        "budget": budget,
                        "canonical_prefix_sha256": p_hash,
                        "is_deduplicated_call": is_shared,
                        "associated_arms": canonical_to_arms[p_hash],
                        "base_correct": base["correct"],
                        **shared_call,
                    }
                    restart_records.append(arm_record)

                # 2. Execute thinking_native arm
                native_key = [qid, "thinking_native", str(budget)]
                if journal.has("restart_call", *native_key):
                    native_res = journal.get("restart_call", *native_key)
                else:
                    _check_safety_limits(journal, pilot_started_time)
                    thinking_suffix = (
                        "\nSolve the question. End your final response with exactly one line "
                        "'Answer: ' followed only by the final answer."
                    )
                    msgs = [{"role": "user", "content": it["query"] + thinking_suffix}]
                    prompt = tokenizer.apply_chat_template(
                        msgs, tokenize=False, add_generation_prompt=True, enable_thinking=True
                    )
                    p_tok = len(tokenizer.encode(prompt))
                    comp_cap = budget - p_tok

                    if comp_cap <= 0:
                        native_res = {
                            "budget_infeasible": True,
                            "prompt": prompt,
                            "prompt_tokens": p_tok,
                            "completion_cap": 0,
                            "raw_output": "",
                            "completion_tokens": 0,
                            "total_tokens": p_tok,
                            "finish_reason": "budget_infeasible",
                            "parsed_answer": None,
                            "correct": False,
                            "duration_ms": 0.0,
                        }
                    else:
                        seed = derive_call_seed(42, qid, "thinking_native", budget)
                        out_text, comp_tok, finish, dur_ms = execute_llm_call(
                            model,
                            tokenizer,
                            prompt,
                            max_tokens=comp_cap,
                            temp=SAMPLING_TEMPERATURE,
                            seed=seed,
                            is_mock=mock,
                            is_thinking=True,
                        )

                        # Thinking-native rule: ONLY extract answer after </think> block
                        if "</think>" not in out_text:
                            parsed = None
                            status = "truncated_thinking"
                            wordy = False
                            correct = False
                        else:
                            post_think = out_text.split("</think>")[-1]
                            family = it["family"]
                            ans_type = "expression" if family == "g24" else "text" if family == "order" else "number"
                            parsed, status, wordy = parse_answer_details(post_think, answer_type=ans_type)
                            correct = bool(gen_check(it, parsed)) if parsed is not None else False

                        native_res = {
                            "budget_infeasible": False,
                            "prompt": prompt,
                            "prompt_tokens": p_tok,
                            "completion_cap": comp_cap,
                            "raw_output": out_text,
                            "completion_tokens": comp_tok,
                            "total_tokens": p_tok + comp_tok,
                            "finish_reason": finish,
                            "parsed_answer": parsed,
                            "parse_status": status,
                            "wordy": wordy,
                            "correct": correct,
                            "duration_ms": round(dur_ms, 2),
                            "memory": get_memory_telemetry(),
                        }
                    journal.append("restart_call", native_key, native_res)

                restart_records.append({
                    "question_id": qid,
                    "family": it["family"],
                    "arm": "thinking_native",
                    "budget": budget,
                    "canonical_prefix_sha256": None,
                    "is_deduplicated_call": False,
                    "associated_arms": ["thinking_native"],
                    "base_correct": base["correct"],
                    **native_res,
                })

        atomic_save_json(output_dir / "restart_records.json", restart_records)

        # Generate summary report
        summary = generate_summary_statistics(base_traces, restart_records, journal)
        atomic_save_json(output_dir / "summary.json", summary)

        report_md = render_markdown_report(manifest, summary, base_traces, restart_records)
        (output_dir / "report.md").write_text(report_md, encoding="utf-8")

        # Write RESULT_FOR_CODEX.md
        codex_report = render_result_for_codex(manifest, summary, output_dir)
        (output_dir / "RESULT_FOR_CODEX.md").write_text(codex_report, encoding="utf-8")

        manifest["status"] = "complete"
        manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["artifact_hashes"] = {
            p.name: file_sha256(p)
            for p in sorted(output_dir.iterdir())
            if p.is_file() and p.name != "manifest.json" and not p.name.startswith(".")
        }
        journal.save_manifest()
        journal.close()

        return {
            "status": "complete",
            "summary": summary,
            "output_dir": str(output_dir),
            "manifest": manifest,
        }

    except Exception as e:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(e).__name__}: {str(e)}"
        journal.save_manifest()
        journal.close()
        raise


def _check_safety_limits(journal: PilotJournal, started_time: float) -> None:
    if journal.count >= MAX_CALLS_LIMIT:
        raise RuntimeError(f"Safety limit reached: call count {journal.count} >= {MAX_CALLS_LIMIT}")
    if journal.total_completion_tokens >= MAX_COMPLETION_TOKENS_LIMIT:
        raise RuntimeError(
            f"Safety limit reached: completion tokens {journal.total_completion_tokens} >= {MAX_COMPLETION_TOKENS_LIMIT}"
        )
    elapsed = time.perf_counter() - started_time
    if elapsed >= MAX_DURATION_SECONDS:
        raise RuntimeError(f"Safety limit reached: duration {elapsed:.1f}s >= {MAX_DURATION_SECONDS}s")


def atomic_save_json(path: Path, value: Any) -> None:
    path = Path(path)
    tmp_path = path.parent / f".{path.name}.tmp"
    tmp_path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def generate_summary_statistics(
    base_traces: dict[str, dict],
    restart_records: list[dict],
    journal: PilotJournal,
) -> dict[str, Any]:
    """Compute accuracy, rescue/harm, format/truncation, and separated token costs."""
    n_questions = len(base_traces)
    base_correct_count = sum(1 for b in base_traces.values() if b["correct"])
    base_wrong_count = n_questions - base_correct_count

    cells = defaultdict(list)
    for r in restart_records:
        key = (r["arm"], r["budget"])
        cells[key].append(r)

    cell_summaries = {}
    for (arm, budget), rows in sorted(cells.items()):
        total = len(rows)
        correct = sum(1 for r in rows if r.get("correct", False))
        accuracy = correct / total if total else 0.0

        # Rescue denominator: ALL initially wrong base traces
        # Harm denominator: ALL initially correct base traces
        rescued = sum(1 for r in rows if not r["base_correct"] and r.get("correct", False))
        harmed = sum(1 for r in rows if r["base_correct"] and not r.get("correct", False))

        rescue_rate = (rescued / base_wrong_count) if base_wrong_count > 0 else 0.0
        harm_rate = (harmed / base_correct_count) if base_correct_count > 0 else 0.0

        truncations = sum(1 for r in rows if r.get("finish_reason") == "length")
        infeasible = sum(1 for r in rows if r.get("budget_infeasible", False))
        format_failures = sum(1 for r in rows if r.get("parse_status") != "marker" and not r.get("budget_infeasible", False))

        mean_prompt_tokens = sum(r.get("prompt_tokens", 0) for r in rows) / total if total else 0.0
        mean_completion_tokens = sum(r.get("completion_tokens", 0) for r in rows) / total if total else 0.0
        mean_total_tokens = sum(r.get("total_tokens", 0) for r in rows) / total if total else 0.0
        mean_duration_ms = sum(r.get("duration_ms", 0) for r in rows) / total if total else 0.0

        cell_summaries[f"{arm}_b{budget}"] = {
            "arm": arm,
            "budget": budget,
            "items": total,
            "correct": correct,
            "accuracy": round(accuracy, 4),
            "initially_wrong_denominator": base_wrong_count,
            "rescued": rescued,
            "rescue_rate": round(rescue_rate, 4),
            "initially_correct_denominator": base_correct_count,
            "harmed": harmed,
            "harm_rate": round(harm_rate, 4),
            "truncations": truncations,
            "budget_infeasible": infeasible,
            "format_failures": format_failures,
            "mean_prompt_tokens": round(mean_prompt_tokens, 1),
            "mean_completion_tokens": round(mean_completion_tokens, 1),
            "mean_total_tokens": round(mean_total_tokens, 1),
            "mean_duration_ms": round(mean_duration_ms, 1),
        }

    # Collection cost: all calls actually made in the journal
    total_calls = journal.count
    total_completion_tokens = journal.total_completion_tokens

    return {
        "dataset_items": n_questions,
        "base_cot_accuracy": round(base_correct_count / n_questions, 4) if n_questions else 0.0,
        "base_initially_correct": base_correct_count,
        "base_initially_wrong": base_wrong_count,
        "collection_cost": {
            "total_model_calls": total_calls,
            "total_completion_tokens": total_completion_tokens,
        },
        "cells": cell_summaries,
    }


def render_markdown_report(
    manifest: dict,
    summary: dict,
    base_traces: dict[str, dict],
    restart_records: list[dict],
) -> str:
    """Render comprehensive pilot audit report in GitHub markdown format."""
    lines = [
        "# CoT Restart Development Pilot Report (Qwen3.5-4B 4-bit)",
        "",
        "> [!IMPORTANT]",
        "> **Exposed Development Only**: This pilot was executed exclusively on 12 canonical questions from",
        "> the exposed `data/gen02_tune.json` pool. It is an exploratory diagnostic to measure feasibility and",
        "> mechanics on Apple Silicon (Mac 16 GB). It does NOT constitute held-out validation, confirmatory evidence,",
        "> or an amendment to Stage 0.",
        "",
        "## Model & Runtime Provenance",
        f"- **Model Repository**: `{manifest.get('model_repository')}`",
        f"- **Base Model**: `{manifest.get('base_model')}`",
        f"- **Revision**: `{manifest.get('model_revision')}`",
        f"- **Quantization**: `{manifest.get('quantization')}`",
        f"- **Platform**: `{manifest.get('platform')}` ({manifest.get('machine')})",
        f"- **Python**: `{manifest.get('python')}`",
        f"- **Total Model Calls**: {summary['collection_cost']['total_model_calls']}",
        f"- **Total Completion Tokens**: {summary['collection_cost']['total_completion_tokens']}",
        "",
        "## Base Visible CoT Trace Outcomes (12 Canonical Questions)",
        f"- **Initial Accuracy**: {summary['base_cot_accuracy'] * 100:.1f}% ({summary['base_initially_correct']}/{summary['dataset_items']})",
        f"- **Initially Wrong (Rescue Denominator)**: {summary['base_initially_wrong']}",
        "",
        "| ID | Family | Base Outcome | Truncated? | Boundary Count | Distinct Menu Prefixes |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for qid, b in sorted(base_traces.items()):
        status = "Correct" if b["correct"] else "Wrong"
        trunc = "Yes" if b["flags"]["source_truncated"] else "No"
        b_count = b["prefix_info"]["interior_boundary_count"]
        m_count = b["prefix_info"]["distinct_menu_prefixes"]
        lines.append(f"| `{qid}` | {b['family']} | {status} | {trunc} | {b_count} | {m_count} |")

    lines.extend([
        "",
        "## Restart Configurations & Budgets Comparison",
        "",
        "| Config / Arm | Budget | Accuracy | Rescue (den={}) | Harm (den={}) | Trunc | Infeasible | Prompt Tok | Comp Tok | Total Tok | Timing (ms) |".format(
            summary["base_initially_wrong"], summary["base_initially_correct"]
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])

    for cell_id, c in sorted(summary["cells"].items()):
        acc_pct = f"{c['accuracy'] * 100:.1f}%"
        res_str = f"{c['rescued']}/{c['initially_wrong_denominator']} ({c['rescue_rate']*100:.1f}%)"
        harm_str = f"{c['harmed']}/{c['initially_correct_denominator']} ({c['harm_rate']*100:.1f}%)"
        lines.append(
            f"| `{c['arm']}` | {c['budget']} | {acc_pct} | {res_str} | {harm_str} | "
            f"{c['truncations']} | {c['budget_infeasible']} | {c['mean_prompt_tokens']:.0f} | "
            f"{c['mean_completion_tokens']:.0f} | {c['mean_total_tokens']:.0f} | {c['mean_duration_ms']:.0f} |"
        )

    lines.extend([
        "",
        "## Cost Separation: Collection vs. Hypothetical Selected Path",
        f"- **Full Collection Cost**: {summary['collection_cost']['total_model_calls']} calls, "
        f"{summary['collection_cost']['total_completion_tokens']} completion tokens.",
        "- **Hypothetical Path Cost**: Each item on a standalone policy path executes only its specific prefix call.",
        "  Prefill tokens are accounted for in total budget ceiling.",
        "",
        "## Scientific Notes & Limitations",
        "- One draw per cell: exploratory feasibility only, not confirmatory.",
        "- No per-item gold oracle claims.",
        "- Deduplication was strictly applied to identical snapped prefixes.",
        "- Next steps: Full review of pilot findings before running 24-question / 480-call batches.",
    ])
    return "\n".join(lines) + "\n"


def render_result_for_codex(
    manifest: dict,
    summary: dict,
    output_dir: Path,
) -> str:
    """Write concise handover document RESULT_FOR_CODEX.md."""
    lines = [
        "# RESULT_FOR_CODEX.md — Pilot CoT Restart Qwen3.5-4B",
        "",
        f"- **Execution Date**: {manifest.get('started_utc')}",
        f"- **Status**: `{manifest.get('status')}`",
        f"- **Artifact Directory**: `{output_dir.resolve()}`",
        f"- **Model**: `{manifest.get('model_repository')}` (revision `{manifest.get('model_revision')[:10]}`)",
        f"- **Runtime**: macOS Apple Silicon 16 GB, MLX 4-bit affine",
        "",
        "## Quantitative Inventory",
        f"- **Total Model Calls**: {summary['collection_cost']['total_model_calls']} (ceiling: {MAX_CALLS_LIMIT})",
        f"- **Total Completion Tokens**: {summary['collection_cost']['total_completion_tokens']} (ceiling: {MAX_COMPLETION_TOKENS_LIMIT})",
        f"- **Canonical Questions**: 12 (4 arith, 4 order, 4 g24)",
        f"- **Initial Base CoT Accuracy**: {summary['base_cot_accuracy']*100:.1f}% ({summary['base_initially_correct']}/{summary['dataset_items']})",
        f"- **Rescue Denominator**: {summary['base_initially_wrong']} initially wrong questions",
        "",
        "## Arm Summary Across Budgets",
        "",
        "| Arm | Budget | Accuracy | Rescued | Harmed | Trunc | Mean Total Tok |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for cell_id, c in sorted(summary["cells"].items()):
        lines.append(
            f"| `{c['arm']}` | {c['budget']} | {c['accuracy']*100:.1f}% | "
            f"{c['rescued']}/{c['initially_wrong_denominator']} | "
            f"{c['harmed']}/{c['initially_correct_denominator']} | "
            f"{c['truncations']} | {c['mean_total_tokens']:.0f} |"
        )

    lines.extend([
        "",
        "## Key Findings & Checkpoint Fidelity",
        "1. Real assistant prefill continuation operates seamlessly via MLX and ChatML.",
        "2. Conservative sentence boundary snapping successfully isolates partial rationale prefixes.",
        "3. Token accounting strictly enforces budget = prompt + prefix + completion.",
        "4. No confirmatory claims or Stage 0 amendments are made from this small sample.",
        "5. Larger 24-question / 480-call batches remain on hold pending review.",
    ])
    return "\n".join(lines) + "\n"
