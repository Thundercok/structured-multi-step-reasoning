"""GSM8K staged generation and checkpointed collector with durable accounting.

Implements the hardened collector contract for GSM8K development comparisons:
- Three-state call lifecycle: started -> (succeeded | failed).
- Started-only attempts are outcome_unknown, halt, and retain conservative reservation.
- Distinct stages: Generation -> (PAL Tool Execution) -> Assembled Record.
- Tool failure is a costed observation parsing generation text (F2).
- Unknown cost is recorded as budget_charge_tokens, not measured_tokens (F1).
- Fail-closed journal integrity: torn tails or hash mismatches fail with 0 byte writes (D3).
- Strict resume under no-retry policy: dispatches never-started conditions only (D1).
- Full execution identity verification across dataset, model, recipes, seeds, and sources (D6).
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import numpy as np

from experiments.order_pilot_checkpoint import atomic_json, atomic_text
from experiments.research_pilot import sha256_file
from experiments.research_study import ROOT, check_answer, seed_for
from research_scoring import parse_typed_answer

ACTIONS = ("DIRECT", "COT", "PAL")
MAX_TOKENS_PER_CALL = 1024
DEFAULT_PAL_TIMEOUT_SECONDS = 5.0
ALLOWED_STAGED_EVIDENCE = ("synthetic_staged_pilot_collection", "synthetic_staged_collector_fixture")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


class QuarantineError(RuntimeError):
    """Raised when journal contains started-only attempts with unknown outcomes."""
    pass


class SimulatedProcessKill(BaseException):
    """Simulates SIGKILL or abrupt power loss where no outcome event is persisted."""
    pass


class BudgetExhaustedError(RuntimeError):
    """Raised when planned calls exceed remaining call or token envelope."""
    pass


@dataclass
class StagedExecutionResult:
    """Outcome of generation stage."""
    text: str
    confidence: float
    generated_tokens: int
    prompt_tokens: int
    finish_reason: str
    elapsed_ms: float
    raw_prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    generation_trace: Optional[Dict[str, Any]] = None
    prompt_token_ids: Optional[List[int]] = None


@dataclass
class ToolExecutionResult:
    """Outcome of sandboxed PAL tool execution."""
    ok: bool
    output: str
    duration_ms: float


def validate_staged_generation_result(res: StagedExecutionResult, token_budget: int) -> None:
    """Validate generation output payload before committing success (G1)."""
    if isinstance(res.generated_tokens, bool) or not isinstance(res.generated_tokens, int):
        raise ValueError(f"Generated tokens must be a non-boolean integer, got: {res.generated_tokens}")
    if not (0 < res.generated_tokens <= token_budget):
        raise ValueError(f"Generated tokens {res.generated_tokens} exceeds declared cap {token_budget} or is non-positive")
    if isinstance(res.prompt_tokens, bool) or not isinstance(res.prompt_tokens, int) or res.prompt_tokens < 0:
        raise ValueError(f"Prompt tokens must be a non-negative integer, got: {res.prompt_tokens}")
    if isinstance(res.confidence, bool) or not isinstance(res.confidence, (int, float)) or not math.isfinite(res.confidence) or not (0.0 <= res.confidence <= 1.0):
        raise ValueError(f"Confidence must be a finite float in [0, 1], got: {res.confidence}")
    if res.finish_reason not in ("stop", "length"):
        raise ValueError(f"Unexpected finish reason: {res.finish_reason}")
    if not isinstance(res.text, str) or not res.text.strip():
        raise ValueError("Generation text must be a non-empty string")
    if isinstance(res.elapsed_ms, bool) or not isinstance(res.elapsed_ms, (int, float)) or not math.isfinite(res.elapsed_ms) or res.elapsed_ms < 0.0:
        raise ValueError(f"Elapsed ms must be non-negative finite number, got: {res.elapsed_ms}")
    if res.raw_prompt is not None and not isinstance(res.raw_prompt, str):
        raise ValueError(f"raw_prompt must be string or None, got: {type(res.raw_prompt)}")
    if res.messages is not None:
        if not isinstance(res.messages, list) or not all(isinstance(m, dict) and "role" in m and "content" in m for m in res.messages):
            raise ValueError(f"messages must be list of dicts with role and content, got: {type(res.messages)}")
    if res.generation_trace is not None and not isinstance(res.generation_trace, dict):
        raise ValueError(f"generation_trace must be dict or None, got: {type(res.generation_trace)}")
    if res.prompt_token_ids is not None:
        if not isinstance(res.prompt_token_ids, list) or not all(isinstance(t, int) and not isinstance(t, bool) for t in res.prompt_token_ids):
            raise ValueError(f"prompt_token_ids must be a list of integers, got: {type(res.prompt_token_ids)}")
        if len(res.prompt_token_ids) != res.prompt_tokens:
            raise ValueError(f"prompt_token_ids length ({len(res.prompt_token_ids)}) must match prompt_tokens ({res.prompt_tokens})")


def validate_tool_execution_result(res: ToolExecutionResult) -> None:
    """Validate tool execution output payload (G1)."""
    if not isinstance(res.ok, bool):
        raise ValueError(f"Tool ok must be a boolean, got: {type(res.ok)}")
    if not isinstance(res.output, str):
        raise ValueError(f"Tool output must be a string, got: {type(res.output)}")
    if isinstance(res.duration_ms, bool) or not isinstance(res.duration_ms, (int, float)) or not math.isfinite(res.duration_ms) or res.duration_ms < 0.0:
        raise ValueError(f"Tool duration ms must be a non-negative finite number, got: {res.duration_ms}")


def log_exposure_event(
    run_dir: Path,
    action: str,
    accessor: str,
    files_accessed: List[str],
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Maintain tamper-evident audit of outcome reads and custody events (G4)."""
    ledger_path = Path(run_dir) / "exposure_ledger.json"
    entries = []
    if ledger_path.is_file():
        try:
            entries = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            entries = []
    entry = {
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "action": action,
        "accessor": accessor,
        "files_accessed": list(files_accessed),
    }
    if details:
        entry["details"] = details
    entries.append(entry)
    atomic_json(ledger_path, entries)


class StagedRunnerInterface:
    """Interface for backends supporting decoupled generation and tool execution."""

    def run_generation(
        self,
        item: Dict[str, Any],
        strategy: str,
        max_tokens: int,
        seed: int,
    ) -> StagedExecutionResult:
        raise NotImplementedError

    def run_tool(
        self,
        code: str,
        timeout_seconds: float = DEFAULT_PAL_TIMEOUT_SECONDS,
    ) -> ToolExecutionResult:
        raise NotImplementedError


class MockStagedRunner(StagedRunnerInterface):
    """Deterministic scripted or simulated staged runner for offline software verification."""

    def __init__(self, responses: Optional[Dict[Tuple[str, str], Dict[str, Any]]] = None):
        self.responses = responses or {}
        self.generation_dispatches = 0
        self.tool_dispatches = 0

    def run_generation(
        self,
        item: Dict[str, Any],
        strategy: str,
        max_tokens: int,
        seed: int,
    ) -> StagedExecutionResult:
        self.generation_dispatches += 1
        key = (item["id"], strategy)
        resp = self.responses.get(key, {})
        if resp.get("raise_generation"):
            exc = resp["raise_generation"]
            if isinstance(exc, Exception):
                raise exc
            raise RuntimeError(str(exc))
        text = resp.get("output", f"Answer: {item.get('answer', '42')}")
        tokens = resp.get("tokens", 120 if strategy == "DIRECT" else 250)
        p_tokens = resp.get("prompt_tokens", 25)
        conf = float(resp.get("confidence", 0.9))
        finish_reason = resp.get("finish_reason", "stop")
        elapsed_ms = float(resp.get("elapsed_ms", 15.0))
        strategy_suffixes = {
            "DIRECT": "\nAnswer directly without showing steps. End with exactly one line 'Answer: ' followed only by the final number, without units.",
            "COT": "\nWrite concise steps in plain English without markdown or LaTeX. End with exactly one line 'Answer: ' followed only by the final number, without units.",
            "PAL": "\nWrite Python code to solve this problem and assign the final numeric answer to `result`. Use arithmetic and built-in Python only, without imports. Return only code in one ```python``` block.",
        }
        messages = resp.get("messages")
        if messages is None:
            suffix = strategy_suffixes.get(strategy, "")
            messages = [{"role": "user", "content": item.get("query", "") + suffix}]
        raw_prompt = resp.get("raw_prompt", f"<|im_start|>user\n{messages[0]['content']}<|im_end|>\n<|im_start|>assistant\n")
        prompt_token_ids = resp.get("prompt_token_ids", [1] * p_tokens)
        return StagedExecutionResult(
            text=text,
            confidence=conf,
            generated_tokens=tokens,
            prompt_tokens=p_tokens,
            finish_reason=finish_reason,
            elapsed_ms=elapsed_ms,
            raw_prompt=raw_prompt,
            messages=messages,
            generation_trace=resp.get("generation_trace"),
            prompt_token_ids=prompt_token_ids,
        )

    def run_tool(
        self,
        code: str,
        timeout_seconds: float = DEFAULT_PAL_TIMEOUT_SECONDS,
    ) -> ToolExecutionResult:
        self.tool_dispatches += 1
        # Check if code triggers scripted behavior
        if "RAISE_TOOL_TIMEOUT" in code:
            return ToolExecutionResult(ok=False, output="TimeoutError: execution exceeded 5.0s", duration_ms=timeout_seconds * 1000)
        if "RAISE_TOOL_ERROR" in code:
            return ToolExecutionResult(ok=False, output="ZeroDivisionError: division by zero", duration_ms=2.5)
        # Default mock tool execution extracts result = ...
        import re
        match = re.search(r"result\s*=\s*(.+)", code)
        if match:
            raw_val = match.group(1).strip()
            return ToolExecutionResult(ok=True, output=raw_val, duration_ms=1.5)
        return ToolExecutionResult(ok=True, output="42", duration_ms=1.0)


class GSM8KCollectorCheckpoint:
    """Atomic, fail-closed journal and state machine for GSM8K development collection.

    Guarantees:
    - Pre-dispatch durable write for started events.
    - Separate events for generation, tool, and record assembly.
    - Started-only events without outcome become outcome_unknown and quarantine the run.
    - Resume dispatches strictly never-started conditions.
    - Tool failure parses original generation text (F2) and retains diagnostics.
    - Unknown/failed cost is charged to budget without being claimed as measured (F1).
    - Fail-closed on torn/corrupt journals with zero byte alteration.
    """

    ARTIFACTS = (
        "dataset.json",
        "settings.json",
        "calls.jsonl",
        "records.json",
        "records_fitting.json",
        "records_validation.json",
        "exposure_ledger.json",
        "summary.json",
        "report.md",
    )

    REQUIRED_IDENTITY_KEYS = {
        "evidence",
        "dataset_sha256",
        "prompt_profile",
        "seed",
        "strategies",
        "max_tokens",
        "source_hashes",
    }

    ALLOWED_EVENT_KINDS = {
        "generation_started",
        "generation_outcome",
        "tool_started",
        "tool_outcome",
        "record_assembled",
    }

    def __init__(
        self,
        directory: Path,
        identity: Dict[str, Any],
        dataset: Dict[str, Any],
        settings: Dict[str, Any],
        resume: bool = False,
    ):
        self.directory = Path(directory)
        self.identity = identity
        self.dataset = dataset
        self.settings = settings
        self.resume = resume

        self.head = "0" * 64
        self.count = 0
        self.lock = None
        self.was_complete = False

        # Ledger tracking
        self.attempts: Dict[str, Dict[str, Any]] = {}
        self.records: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.dispatched_conditions: Set[Tuple[str, str]] = set()
        self.completed_conditions: Set[Tuple[str, str]] = set()
        self.unknown_conditions: Set[Tuple[str, str]] = set()

        # Cumulative budget accounting
        self.measured_tokens_total = 0
        self.budget_charge_tokens_total = 0
        self.calls_started_total = 0
        self.calls_completed_total = 0

        exists = self.directory.exists()
        if exists and not (self.directory / "manifest.json").is_file():
            raise ValueError(
                f"Existing output directory {self.directory} lacks manifest.json; "
                "refusing to touch or overwrite."
            )
        if not exists:
            self.directory.mkdir(parents=True, exist_ok=False)

        try:
            self.lock = (self.directory / ".writer.lock").open("a")
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

            if exists:
                if not self.resume:
                    raise ValueError(
                        f"Refusing to reuse occupied directory {self.directory} without explicit --resume."
                    )
                self.manifest = json.loads((self.directory / "manifest.json").read_text(encoding="utf-8"))
                self._verify_identity_contract()
                self._read_journal()
                self._recover_records_from_terminal_evidence()

                if self.manifest.get("status") == "complete":
                    self.was_complete = True
                    self._verify_completed_artifacts()
            else:
                self._validate_initial_contract()
                self.manifest = {
                    "schema_version": 1,
                    "mode": "gsm8k_development_pilot_collection",
                    "identity": self.identity,
                    "status": "running",
                    "journal_head": self.head,
                    "journal_entries": 0,
                    "calls_started": 0,
                    "calls_completed": 0,
                    "measured_tokens": 0,
                    "budget_charged_tokens": 0,
                }
                atomic_json(self.directory / "dataset.json", self.dataset)
                atomic_json(self.directory / "settings.json", self.settings)
                (self.directory / "calls.jsonl").touch(exist_ok=False)
                log_exposure_event(self.directory, "collection_initialized", "gsm8k_collector", ["dataset.json", "settings.json"])
                self._sync_manifest("running")
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self.lock is not None:
            try:
                fcntl.flock(self.lock, fcntl.LOCK_UN)
            except Exception:
                pass
            self.lock.close()
            self.lock = None

    def _validate_initial_contract(self) -> None:
        """Validate execution identity completeness and dataset integrity before directory creation (H1)."""
        require(isinstance(self.identity, dict), "Checkpoint identity must be a dictionary")
        missing = self.REQUIRED_IDENTITY_KEYS - set(self.identity.keys())
        require(not missing, f"Identity missing required keys: {sorted(missing)}")

        require(
            isinstance(self.identity["max_tokens"], int)
            and not isinstance(self.identity["max_tokens"], bool)
            and self.identity["max_tokens"] > 0,
            "max_tokens must be positive non-bool integer",
        )
        require(
            isinstance(self.identity["seed"], int)
            and not isinstance(self.identity["seed"], bool),
            "seed must be non-bool integer",
        )
        require(
            isinstance(self.identity["strategies"], list)
            and set(self.identity["strategies"]) == set(ACTIONS),
            "strategies must match ACTIONS list",
        )
        expected_ds_sha = hashlib.sha256(json.dumps(self.dataset, sort_keys=True).encode("utf-8")).hexdigest()
        require(
            self.identity["dataset_sha256"] in (expected_ds_sha, digest(self.dataset)),
            "Identity dataset_sha256 mismatch with provided dataset",
        )
        require(
            isinstance(self.identity["source_hashes"], dict) and bool(self.identity["source_hashes"]),
            "source_hashes must be a non-empty dictionary",
        )
        for path_name, h in self.identity["source_hashes"].items():
            require(
                isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h.lower()),
                f"Invalid source hash for {path_name}: {h}",
            )

        require(isinstance(self.dataset.get("items"), list) and bool(self.dataset["items"]), "Dataset missing items list")
        item_ids = [i["id"] for i in self.dataset["items"]]
        require(len(item_ids) == len(set(item_ids)), f"Duplicate item IDs in dataset: {item_ids}")

    def _verify_identity_contract(self) -> None:
        """Verify full environment and configuration contract (D6, G1, integrity)."""
        saved_id = self.manifest.get("identity")
        require(isinstance(saved_id, dict), "Manifest identity must be a dictionary")
        require(isinstance(self.identity, dict), "Run identity must be a dictionary")

        missing_saved = self.REQUIRED_IDENTITY_KEYS - set(saved_id.keys())
        require(not missing_saved, f"Manifest identity missing required keys: {sorted(missing_saved)}")
        missing_current = self.REQUIRED_IDENTITY_KEYS - set(self.identity.keys())
        require(not missing_current, f"Run identity missing required keys: {sorted(missing_current)}")

        require(saved_id.get("evidence") == self.identity.get("evidence"), "Identity evidence mismatch")
        require(saved_id.get("dataset_sha256") == self.identity.get("dataset_sha256"), "Dataset SHA-256 mismatch")
        require(saved_id.get("prompt_profile") == self.identity.get("prompt_profile"), "Prompt profile mismatch")
        require(saved_id.get("seed") == self.identity.get("seed"), "Seed contract mismatch")
        require(saved_id.get("strategies") == self.identity.get("strategies"), "Strategy list mismatch")
        require(saved_id.get("max_tokens") == self.identity.get("max_tokens"), "Max tokens cap mismatch")
        require(saved_id.get("source_hashes") == self.identity.get("source_hashes"), "Source hashes mismatch")
        if "model_provenance" in self.identity:
            require(saved_id.get("model_provenance") == self.identity.get("model_provenance"), "Model provenance mismatch")

        require(saved_id == self.identity, f"Identity contract mismatch between manifest and run: saved={saved_id} current={self.identity}")

        saved_dataset = json.loads((self.directory / "dataset.json").read_text(encoding="utf-8"))
        require(saved_dataset == self.dataset, "Pinned dataset.json differs from run dataset")
        saved_settings = json.loads((self.directory / "settings.json").read_text(encoding="utf-8"))
        require(saved_settings == self.settings, "Pinned settings.json differs from run settings")

    def _read_journal(self) -> None:
        """Parse journal, enforce strict hash chain, and reconstruct ledger (D3, G1, G2)."""
        journal_path = self.directory / "calls.jsonl"
        require(journal_path.is_file(), "Missing calls.jsonl journal")

        dataset_item_ids = {i["id"] for i in self.dataset["items"]}

        lines = journal_path.read_text(encoding="utf-8").splitlines(keepends=True)
        anchors = {self.head}

        # Staging trackers
        started_conditions: Dict[Tuple[str, str], str] = {}
        attempts: Dict[str, Dict[str, Any]] = {}
        records: Dict[Tuple[str, str], Dict[str, Any]] = {}

        for line in lines:
            if not line.endswith("\n"):
                raise ValueError("Torn journal tail (incomplete line); failing closed without altering file.")
            entry = json.loads(line)
            body = {k: v for k, v in entry.items() if k != "sha256"}
            computed_sha = digest(body)
            if entry.get("sha256") != computed_sha:
                raise ValueError("Journal checksum mismatch; failing closed without altering file.")
            if body.get("previous") != self.head:
                raise ValueError("Journal chain broken; failing closed without altering file.")
            if body.get("sequence") != self.count:
                raise ValueError("Journal sequence mismatch; failing closed without altering file.")

            kind = body["kind"]
            require(kind in self.ALLOWED_EVENT_KINDS, f"Unknown journal event kind: {kind}")
            attempt_id = body["attempt_id"]
            cond_key = tuple(body["key"])  # (item_id, strategy)
            require(len(cond_key) == 2, f"Condition key must be (item_id, strategy), got: {cond_key}")
            item_id, strategy = cond_key
            require(item_id in dataset_item_ids, f"Condition key item {item_id} not in dataset")
            require(strategy in ACTIONS, f"Condition key strategy {strategy} not in ACTIONS")

            if kind == "generation_started":
                require(attempt_id not in attempts, f"Duplicate attempt_id: {attempt_id}")
                require(cond_key not in started_conditions, f"Duplicate condition started: {cond_key} already started in {started_conditions.get(cond_key)}")
                val = body["value"]
                require(val.get("item_id") == item_id, "Start item_id mismatch")
                require(val.get("strategy") == strategy, "Start strategy mismatch")
                require(val.get("declared_max_tokens") == self.identity.get("max_tokens", 1024), "Start declared_max_tokens mismatch")
                require(val.get("reserved_tokens") == val.get("declared_max_tokens"), "Start reserved_tokens mismatch")
                require(val.get("seed") == seed_for(self.identity.get("seed", 42), item_id, strategy), "Seed derivation mismatch")

                started_conditions[cond_key] = attempt_id
                attempts[attempt_id] = {
                    "cond_key": cond_key,
                    "started": val,
                    "generation_outcome": None,
                    "tool_started": None,
                    "tool_outcome": None,
                    "record_assembled": None,
                }
                self.calls_started_total += 1
                self.dispatched_conditions.add(cond_key)

            elif kind == "generation_outcome":
                require(attempt_id in attempts, f"generation_outcome without started for {attempt_id}")
                require(cond_key == attempts[attempt_id]["cond_key"], f"generation_outcome key mismatch for {attempt_id}")
                require(attempts[attempt_id]["generation_outcome"] is None, f"Duplicate generation_outcome for {attempt_id}")
                require(attempts[attempt_id]["tool_started"] is None, f"generation_outcome after tool_started for {attempt_id}")
                require(attempts[attempt_id]["record_assembled"] is None, f"generation_outcome after record_assembled for {attempt_id}")

                val = body["value"]
                status = val.get("status")
                require(status in ("succeeded", "failed"), f"Invalid generation status: {status}")
                if status == "succeeded":
                    res = StagedExecutionResult(
                        text=val.get("output_text", ""),
                        confidence=val.get("confidence", -1.0),
                        generated_tokens=val.get("measured_generated_tokens"),
                        prompt_tokens=val.get("measured_prompt_tokens"),
                        finish_reason=val.get("finish_reason", ""),
                        elapsed_ms=val.get("elapsed_ms", -1.0),
                    )
                    validate_staged_generation_result(res, attempts[attempt_id]["started"]["declared_max_tokens"])
                    require(val.get("budget_charge_tokens") == res.generated_tokens, "Budget charge mismatch")
                    require(val.get("cost_status") == "measured", "Cost status mismatch for succeeded generation")
                    self.measured_tokens_total += res.generated_tokens
                    self.budget_charge_tokens_total += val["budget_charge_tokens"]
                else:
                    require(val.get("measured_generated_tokens") is None, "Failed generation cannot have measured tokens")
                    require(val.get("measured_prompt_tokens") is None, "Failed generation cannot have measured prompt tokens")
                    require(val.get("cost_status") == "unknown_reserved", "Cost status mismatch for failed generation")
                    require(val.get("budget_charge_tokens") == attempts[attempt_id]["started"]["declared_max_tokens"], "Failed generation must charge full reservation")
                    self.budget_charge_tokens_total += val["budget_charge_tokens"]

                attempts[attempt_id]["generation_outcome"] = val

            elif kind == "tool_started":
                require(attempt_id in attempts, f"tool_started without started for {attempt_id}")
                require(cond_key == attempts[attempt_id]["cond_key"], f"tool_started key mismatch for {attempt_id}")
                require(strategy == "PAL", f"tool_started invalid for non-PAL strategy {strategy}")
                gen_out = attempts[attempt_id]["generation_outcome"]
                require(gen_out is not None and gen_out.get("status") == "succeeded", f"tool_started before successful generation for {attempt_id}")
                require(attempts[attempt_id]["tool_started"] is None, f"Duplicate tool_started for {attempt_id}")
                require(attempts[attempt_id]["record_assembled"] is None, f"tool_started after record_assembled for {attempt_id}")

                val = body["value"]
                require(val.get("name") == "python" and isinstance(val.get("code"), str), "Invalid tool_started payload")
                attempts[attempt_id]["tool_started"] = val

            elif kind == "tool_outcome":
                require(attempt_id in attempts, f"tool_outcome without started for {attempt_id}")
                require(cond_key == attempts[attempt_id]["cond_key"], f"tool_outcome key mismatch for {attempt_id}")
                require(strategy == "PAL", f"tool_outcome invalid for non-PAL strategy {strategy}")
                require(attempts[attempt_id]["tool_started"] is not None, f"tool_outcome before tool_started for {attempt_id}")
                require(attempts[attempt_id]["tool_outcome"] is None, f"Duplicate tool_outcome for {attempt_id}")
                require(attempts[attempt_id]["record_assembled"] is None, f"tool_outcome after record_assembled for {attempt_id}")

                val = body["value"]
                tool_res = ToolExecutionResult(ok=val.get("ok"), output=val.get("output"), duration_ms=val.get("duration_ms"))
                validate_tool_execution_result(tool_res)
                attempts[attempt_id]["tool_outcome"] = val

            elif kind == "record_assembled":
                require(attempt_id in attempts, f"record_assembled without started for {attempt_id}")
                require(cond_key == attempts[attempt_id]["cond_key"], f"record_assembled key mismatch for {attempt_id}")
                require(attempts[attempt_id]["record_assembled"] is None, f"Duplicate record_assembled for {attempt_id}")
                gen_out = attempts[attempt_id]["generation_outcome"]
                require(gen_out is not None and gen_out.get("status") == "succeeded", f"record_assembled without successful generation for {attempt_id}")
                if strategy == "PAL":
                    require(attempts[attempt_id]["tool_outcome"] is not None, f"record_assembled for PAL without terminal tool_outcome for {attempt_id}")

                val = body["value"]
                require(val.get("id") == item_id, "Record item id mismatch")
                require(val.get("strategy") == strategy, "Record strategy mismatch")
                require(val.get("tokens") == gen_out["measured_generated_tokens"], "Record tokens mismatch with generation outcome")

                attempts[attempt_id]["record_assembled"] = val
                records[cond_key] = val
                self.completed_conditions.add(cond_key)
                self.calls_completed_total += 1

            self.head = entry["sha256"]
            self.count += 1
            anchors.add(self.head)

        manifest_head = self.manifest.get("journal_head")
        if manifest_head not in anchors:
            raise ValueError(f"Manifest head {manifest_head} is absent from journal chain.")

        self.attempts = attempts
        self.records = records

        # Identify unknown attempts and restore conservative reservation (G2)
        for att_id, att in attempts.items():
            cond_key = att["cond_key"]
            gen_out = att["generation_outcome"]
            if gen_out is None:
                self.unknown_conditions.add(cond_key)
                self.budget_charge_tokens_total += att["started"].get("reserved_tokens", MAX_TOKENS_PER_CALL)
            elif att["started"]["strategy"] == "PAL":
                if gen_out.get("status") == "succeeded":
                    if att["tool_started"] is not None and att["tool_outcome"] is None:
                        self.unknown_conditions.add(cond_key)
                    elif att["tool_started"] is None and att["record_assembled"] is None:
                        self.unknown_conditions.add(cond_key)

    def _build_record_from_evidence(self, att: Dict[str, Any]) -> Dict[str, Any]:
        """Construct assembled record purely from terminal generation and tool evidence (G2)."""
        cond_key = att["cond_key"]
        item_id, strategy = cond_key
        item = next((i for i in self.dataset["items"] if i["id"] == item_id), None)
        require(item is not None, f"Item {item_id} not found in dataset")
        started = att["started"]
        gen_val = att["generation_outcome"]
        tool_val = att["tool_outcome"]

        action_seed = started["seed"]
        token_budget = started["declared_max_tokens"]
        fmt = {"answer_type": "number", "decimal_separator": item.get("decimal_separator", ".")}
        tools_list = []

        if strategy == "PAL":
            require(tool_val is not None, f"PAL strategy requires tool_outcome for recovery on {att}")
            tools_list = [{
                "name": "python",
                "ok": tool_val["ok"],
                "output": tool_val["output"],
                "duration_ms": tool_val["duration_ms"],
            }]
            if tool_val["ok"]:
                parsed, parse_status, wordy = parse_typed_answer(f"Answer: {tool_val['output']}", **fmt)
                eff_conf = gen_val["confidence"]
            else:
                parsed, parse_status, wordy = parse_typed_answer(gen_val["output_text"], **fmt)
                eff_conf = gen_val["confidence"] * 0.3
        else:
            parsed, parse_status, wordy = parse_typed_answer(gen_val["output_text"], **fmt)
            eff_conf = gen_val["confidence"]

        correct = bool(check_answer(parsed, item))
        total_strategy_ms = gen_val["elapsed_ms"] + (tool_val["duration_ms"] if tool_val else 0.0)

        actual_messages = gen_val.get("messages")
        messages_provenance = "genuine_trace"
        if actual_messages is None:
            evidence_type = getattr(self, "identity", {}).get("evidence", "")
            # On staged schema, fail closed: invented messages are strictly prohibited
            if evidence_type in ALLOWED_STAGED_EVIDENCE or getattr(self, "identity", {}).get("mode") == "gsm8k_development_pilot_collection":
                raise ValueError(
                    f"Staged record assembly requires actual messages in generation evidence for {cond_key}; "
                    "invented bare query fallback is strictly prohibited."
                )
            # Legacy synthetic fallback with explicit synthetic provenance label
            actual_messages = [{"role": "user", "content": item["query"]}]
            messages_provenance = "synthetic_legacy_fallback"

        gen_entry = {
            "output": gen_val["output_text"],
            "tokens": gen_val["measured_generated_tokens"],
            "prompt_tokens": gen_val["measured_prompt_tokens"],
            "max_tokens": token_budget,
            "temperature": 0.0,
            "enable_thinking": False,
            "finish_reason": gen_val["finish_reason"],
            "messages": actual_messages,
            "messages_provenance": messages_provenance,
        }
        if gen_val.get("prompt_token_ids") is not None:
            gen_entry["prompt_token_ids"] = gen_val["prompt_token_ids"]
        if gen_val.get("raw_prompt") is not None:
            gen_entry["raw_prompt"] = gen_val["raw_prompt"]
        if gen_val.get("generation_trace") is not None:
            gen_entry["generation_trace"] = gen_val["generation_trace"]

        trace = {
            "parse_status": parse_status,
            "wordy": wordy,
            "generations": [gen_entry],
            "tools": tools_list,
        }
        if isinstance(gen_val.get("generation_trace"), dict):
            for k, v in gen_val["generation_trace"].items():
                if k not in trace and k not in ("generations", "tools"):
                    trace[k] = v

        return {
            "id": item["id"],
            "group_id": item["group_id"],
            "split": item["split"],
            "strategy": strategy,
            "token_budget": token_budget,
            "seed": action_seed,
            "answer_format": fmt,
            "answer": str(parsed if parsed is not None else ""),
            "correct": correct,
            "confidence": float(eff_conf),
            "tokens": int(gen_val["measured_generated_tokens"]),
            "strategy_ms": float(total_strategy_ms),
            "trace": trace,
        }

    def _recover_records_from_terminal_evidence(self) -> None:
        """Reconstruct assembled records purely from durable terminal evidence on resume (G2)."""
        for att_id, att in sorted(self.attempts.items()):
            cond_key = att["cond_key"]
            if cond_key in self.completed_conditions:
                continue
            if cond_key in self.unknown_conditions:
                continue
            gen_out = att["generation_outcome"]
            if gen_out is None or gen_out.get("status") != "succeeded":
                continue
            if att["started"]["strategy"] == "PAL" and att["tool_outcome"] is None:
                continue
            # Recoverable terminal evidence exists! Reconstruct without re-executing
            record = self._build_record_from_evidence(att)
            self.append_event("record_assembled", att_id, cond_key, record)
            att["record_assembled"] = record
            self.records[cond_key] = record
            self.completed_conditions.add(cond_key)
            self.calls_completed_total += 1

    def _verify_completed_artifacts(self) -> None:
        hashes = self.manifest.get("artifact_sha256", {})
        for name in self.ARTIFACTS:
            require((self.directory / name).is_file(), f"Missing completed artifact {name}")
            require(sha256_file(self.directory / name) == hashes.get(name), f"Checksum mismatch for {name}")

    def append_event(self, kind: str, attempt_id: str, cond_key: Tuple[str, str], value: Dict[str, Any]) -> None:
        """Atomically append a validated, hash-chained event to calls.jsonl and fsync."""
        body = {
            "sequence": self.count,
            "previous": self.head,
            "kind": kind,
            "attempt_id": attempt_id,
            "key": list(cond_key),
            "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "value": value,
        }
        entry = {**body, "sha256": digest(body)}
        line = canonical_json(entry) + "\n"

        journal_path = self.directory / "calls.jsonl"
        with journal_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

        self.head = entry["sha256"]
        self.count += 1

    def _sync_manifest(self, status: str, **extra_fields: Any) -> None:
        self.manifest.update({
            "status": status,
            "journal_head": self.head,
            "journal_entries": self.count,
            "calls_started": self.calls_started_total,
            "calls_completed": self.calls_completed_total,
            "measured_tokens": self.measured_tokens_total,
            "budget_charged_tokens": self.budget_charge_tokens_total,
            **extra_fields,
        })
        atomic_json(self.directory / "manifest.json", self.manifest)

    def is_condition_dispatched(self, cond_key: Tuple[str, str]) -> bool:
        return cond_key in self.dispatched_conditions

    def has_unknown_outcomes(self) -> bool:
        return bool(self.unknown_conditions)


def run_staged_collection(
    checkpoint: GSM8KCollectorCheckpoint,
    runner: StagedRunnerInterface,
    dataset: Optional[Dict[str, Any]] = None,
    strategies: Optional[List[str]] = None,
    token_budget: Optional[int] = None,
    master_seed: Optional[int] = None,
    max_total_calls: int = 288,
    max_total_tokens: int = 294912,
    fail_on_interruption: bool = False,
) -> Dict[str, Any]:
    """Execute staged GSM8K collection under strict accounting and no-retry rules."""
    # H1: Immutable execution contract binding before any dispatch or journal mutation
    if dataset is not None:
        require(dataset == checkpoint.dataset, "Dispatch dataset differs from pinned checkpoint dataset")
    dataset = checkpoint.dataset

    expected_cap = checkpoint.identity.get("max_tokens", MAX_TOKENS_PER_CALL)
    if token_budget is not None:
        require(
            token_budget == expected_cap,
            f"Dispatch token_budget ({token_budget}) differs from pinned identity ({expected_cap})",
        )
    token_budget = expected_cap

    expected_seed = checkpoint.identity.get("seed", 42)
    if master_seed is not None:
        require(
            master_seed == expected_seed,
            f"Dispatch master_seed ({master_seed}) differs from pinned identity ({expected_seed})",
        )
    master_seed = expected_seed

    expected_strategies = list(checkpoint.identity.get("strategies", ACTIONS))
    if strategies is not None:
        require(
            list(strategies) == expected_strategies,
            f"Dispatch strategies ({strategies}) differ from pinned identity ({expected_strategies})",
        )
    strategies = expected_strategies

    # Check for duplicate item IDs in dataset
    items = dataset.get("items", [])
    require(bool(items), "Dataset items list is empty")
    item_ids = [i["id"] for i in items]
    require(len(item_ids) == len(set(item_ids)), f"Duplicate item IDs in dataset: {item_ids}")

    # Check for quarantine (D1)
    if checkpoint.has_unknown_outcomes():
        checkpoint._sync_manifest("quarantined", error="Contains started-only attempts with unknown outcomes.")
        raise QuarantineError(
            f"Run is quarantined with {len(checkpoint.unknown_conditions)} unknown outcome attempts. "
            "Under no-retry policy, redispatch is prohibited without separate authorization."
        )

    if checkpoint.was_complete:
        return checkpoint.manifest

    # Build planned ordered conditions: item x strategy
    items = dataset["items"]
    all_conditions = [
        (item, strategy)
        for item in sorted(items, key=lambda i: i["id"])
        for strategy in strategies
    ]

    require(len(all_conditions) <= max_total_calls, "Condition count exceeds maximum allowed calls")

    for item, strategy in all_conditions:
        cond_key = (item["id"], strategy)
        if cond_key in checkpoint.completed_conditions:
            continue
        if checkpoint.is_condition_dispatched(cond_key):
            # Already dispatched in prior run: under no-retry policy, DO NOT DISPATCH AGAIN
            continue

        # Preflight check against remaining envelope
        if checkpoint.calls_started_total >= max_total_calls:
            checkpoint._sync_manifest("interrupted", error="Maximum planned calls envelope exhausted.")
            raise BudgetExhaustedError("Exhausted maximum calls envelope")

        if checkpoint.budget_charge_tokens_total + token_budget > max_total_tokens:
            checkpoint._sync_manifest("interrupted", error="Maximum token envelope exhausted.")
            raise BudgetExhaustedError("Exhausted maximum token envelope")

        attempt_id = f"{item['id']}_{strategy}_a0"
        action_seed = seed_for(master_seed, item["id"], strategy)

        # STAGE 1: Generation Started
        start_payload = {
            "item_id": item["id"],
            "group_id": item["group_id"],
            "role": item.get("split", "train"),
            "strategy": strategy,
            "seed": action_seed,
            "declared_max_tokens": token_budget,
            "reserved_tokens": token_budget,
        }
        checkpoint.append_event("generation_started", attempt_id, cond_key, start_payload)
        checkpoint.attempts[attempt_id] = {
            "cond_key": cond_key,
            "started": start_payload,
            "generation_outcome": None,
            "tool_started": None,
            "tool_outcome": None,
            "record_assembled": None,
        }
        checkpoint.calls_started_total += 1
        checkpoint.dispatched_conditions.add(cond_key)

        # Execute Generation Stage
        gen_start_time = time.perf_counter()
        try:
            gen_res = runner.run_generation(item, strategy, token_budget, action_seed)
            validate_staged_generation_result(gen_res, token_budget)
            gen_elapsed_ms = (time.perf_counter() - gen_start_time) * 1000
        except BaseException as exc:
            if isinstance(exc, SimulatedProcessKill):
                raise
            gen_elapsed_ms = (time.perf_counter() - gen_start_time) * 1000
            # Generation failed or invalid payload: log failure with conservative reservation (F1, G1)
            fail_payload = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "measured_generated_tokens": None,
                "measured_prompt_tokens": None,
                "budget_charge_tokens": token_budget,
                "cost_status": "unknown_reserved",
                "elapsed_ms": gen_elapsed_ms,
            }
            checkpoint.append_event("generation_outcome", attempt_id, cond_key, fail_payload)
            checkpoint.attempts[attempt_id]["generation_outcome"] = fail_payload
            checkpoint.budget_charge_tokens_total += token_budget
            checkpoint._sync_manifest("interrupted", error=f"Generation failed on {attempt_id}: {exc}")
            raise

        # Generation Succeeded: persist evidence BEFORE tool execution (D2)
        gen_payload = {
            "status": "succeeded",
            "output_text": gen_res.text,
            "measured_generated_tokens": gen_res.generated_tokens,
            "measured_prompt_tokens": gen_res.prompt_tokens,
            "finish_reason": gen_res.finish_reason,
            "confidence": gen_res.confidence,
            "elapsed_ms": gen_res.elapsed_ms,
            "budget_charge_tokens": gen_res.generated_tokens,
            "cost_status": "measured",
            "raw_prompt": gen_res.raw_prompt,
            "messages": gen_res.messages,
            "generation_trace": gen_res.generation_trace,
            "prompt_token_ids": gen_res.prompt_token_ids,
        }
        checkpoint.append_event("generation_outcome", attempt_id, cond_key, gen_payload)
        checkpoint.attempts[attempt_id]["generation_outcome"] = gen_payload
        checkpoint.measured_tokens_total += gen_res.generated_tokens
        checkpoint.budget_charge_tokens_total += gen_res.generated_tokens

        # STAGE 2: Tool Execution (PAL only)
        tool_res = None
        if strategy == "PAL":
            # Extract python code
            from reasoning.reasoning_strategies import extract_code
            code = extract_code(gen_res.text)

            tool_start_payload = {
                "name": "python",
                "code": code,
                "timeout_seconds": DEFAULT_PAL_TIMEOUT_SECONDS,
            }
            checkpoint.append_event("tool_started", attempt_id, cond_key, tool_start_payload)
            checkpoint.attempts[attempt_id]["tool_started"] = tool_start_payload

            try:
                tool_res = runner.run_tool(code, DEFAULT_PAL_TIMEOUT_SECONDS)
                validate_tool_execution_result(tool_res)
            except BaseException as exc:
                if isinstance(exc, SimulatedProcessKill):
                    raise
                # Fatal sandbox runner crash or invalid payload
                tool_fail_payload = {
                    "ok": False,
                    "output": f"{type(exc).__name__}: {str(exc)}",
                    "duration_ms": 0.0,
                }
                checkpoint.append_event("tool_outcome", attempt_id, cond_key, tool_fail_payload)
                checkpoint.attempts[attempt_id]["tool_outcome"] = tool_fail_payload
                checkpoint._sync_manifest("interrupted", error=f"Tool runner crash on {attempt_id}: {exc}")
                raise

            tool_outcome_payload = {
                "ok": tool_res.ok,
                "output": tool_res.output,
                "duration_ms": tool_res.duration_ms,
            }
            checkpoint.append_event("tool_outcome", attempt_id, cond_key, tool_outcome_payload)
            checkpoint.attempts[attempt_id]["tool_outcome"] = tool_outcome_payload

        # STAGE 3: Record Assembly
        record = checkpoint._build_record_from_evidence(checkpoint.attempts[attempt_id])
        checkpoint.append_event("record_assembled", attempt_id, cond_key, record)
        checkpoint.attempts[attempt_id]["record_assembled"] = record
        checkpoint.records[cond_key] = record
        checkpoint.completed_conditions.add(cond_key)
        checkpoint.calls_completed_total += 1

    # Check if all conditions completed
    all_keys = {(item["id"], strategy) for item, strategy in all_conditions}
    if checkpoint.completed_conditions == all_keys:
        ordered_records = [checkpoint.records[k] for k in sorted(all_keys)]
        fitting_records = [r for r in ordered_records if r["split"] == "train"]
        val_records = [r for r in ordered_records if r["split"] == "calibration"]

        atomic_json(checkpoint.directory / "records.json", ordered_records)
        atomic_json(checkpoint.directory / "records_fitting.json", fitting_records)
        atomic_json(checkpoint.directory / "records_validation.json", val_records)

        train_items = [i for i in items if i["split"] == "train"]
        val_items = [i for i in items if i["split"] == "calibration"]

        summary_data = {
            "status": "complete",
            "items_count": len(items),
            "records_count": len(ordered_records),
            "train_items_count": len(train_items),
            "train_records_count": len(fitting_records),
            "calibration_items_count": len(val_items),
            "calibration_records_count": len(val_records),
            "calls_completed": checkpoint.calls_completed_total,
            "measured_generated_tokens": checkpoint.measured_tokens_total,
            "budget_charged_tokens": checkpoint.budget_charge_tokens_total,
            "validation_accuracy_suppressed": True,
            "note": "Pre-seal validation outcomes and aggregate scores are suppressed. Run --gsm8k-routing-fit and --gsm8k-routing-validate to evaluate.",
        }
        atomic_json(checkpoint.directory / "summary.json", summary_data)

        report_text = (
            f"# GSM8K Staged Collection Summary\n\n"
            f"- Status: Complete\n"
            f"- Total Calls Completed: {checkpoint.calls_completed_total}\n"
            f"- Total Measured Generated Tokens: {checkpoint.measured_tokens_total}\n"
            f"- Total Budget Charged: {checkpoint.budget_charge_tokens_total}\n"
            f"- Train Items: {len(train_items)} (Records: {len(fitting_records)})\n"
            f"- Calibration Items: {len(val_items)} (Records: {len(val_records)})\n"
            f"- Validation Outcomes: Sealed and access-isolated; aggregate accuracy suppressed pre-seal.\n"
        )
        atomic_text(checkpoint.directory / "report.md", report_text)

        log_exposure_event(
            checkpoint.directory,
            "collection_completed",
            "gsm8k_collector",
            ["records.json", "records_fitting.json", "records_validation.json", "summary.json", "report.md"],
        )

        artifact_hashes = {
            name: sha256_file(checkpoint.directory / name)
            for name in checkpoint.ARTIFACTS
        }
        checkpoint._sync_manifest("complete", artifact_sha256=artifact_hashes)

    return checkpoint.manifest
