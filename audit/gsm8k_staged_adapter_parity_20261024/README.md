# GSM8K Decoupled Staged Adapter & Offline Parity Dossier — 2026-10-24

**Verdict: Step 1 (Real Staged Adapter) and Step 2 (Offline Parity) implemented and verified.**
All tests executed purely offline using deterministic injected fixtures without loading MLX weights or connecting to Hugging Face. Zero model/embedding calls made, 0 VND expended, candidate GSM8K 48/48 content remains strictly unread, research bridge closed, and Stage 0 Gate unchanged.

---

## 1. Summary of Implemented Changes

| Component | Target File | Key Enhancements | Verification Status |
| :--- | :--- | :--- | :--- |
| **Dataclass Enhancement** | `experiments/gsm8k_collector.py` | Added `raw_prompt: Optional[str]`, `messages: Optional[List[Dict[str, str]]]`, and `generation_trace: Optional[Dict[str, Any]]` to `StagedExecutionResult`. Enhanced `validate_staged_generation_result` with type validation. | Verified in `test_collector_stores_actual_messages_and_not_bare_query` and unit tests. |
| **Collector Trace Fidelity** | `experiments/gsm8k_collector.py` | Eliminated bare-query message reconstruction (`[{"role": "user", "content": item["query"]}]`). Now records actual `messages` containing exact strategy suffixes (`MATH_EN_SUFFIXES`), rendered `raw_prompt` (chat template), and diagnostics (`parse_status`, `wordy`). | Verified in `test_collector_stores_actual_messages_and_not_bare_query` (asserts message matches suffix and differs from bare query). |
| **Real Staged Adapter** | `qwen_mlx_backend.py` | Implemented `QwenMLXStagedRunner(backend)`: decouples generation stage (`run_generation`) from sandboxed Python tool execution (`run_tool`). Preserves exact prompt suffix (`_suffix`), chat template application, answer format configuration from query metadata only (no gold), stop condition, and confidence calculations. Made MLX operations lazy to enable clean offline imports. | Verified in `tests/test_qwen_staged_parity.py` across DIRECT, COT, and PAL arms. |
| **Offline Parity Suite** | `tests/test_qwen_staged_parity.py` | Authoring 9 rigorous tests comparing legacy monolithic path (`backend.run`) vs. decoupled staged path (`run_generation` -> journal -> `run_tool` -> `_build_record_from_evidence`) with injected fixtures. Covers DIRECT marker/fallback, COT multi-step, PAL tool success, runtime error fallback (ZeroDivisionError with 0.3 confidence penalty), timeout fallback (5.0s with 0.3 penalty), and length truncation boundaries. | **9 passed in 1.72s**. |
| **Gate Lock Verification** | `experiments/gsm8k_routing_baseline.py` | Reaffirmed and verified that staged manifests with non-synthetic evidence (e.g. `measured_staged_collection`) remain strictly rejected as deferred before sealing. | Verified in `test_staged_measured_evidence_remains_locked`. |

---

## 2. Technical Architecture & Decoupling

### A. Dataclass and Trace Storage
In `experiments/gsm8k_collector.py`:
- `StagedExecutionResult` now explicitly carries the full conversation structure and model prompt:
  ```python
  @dataclass
  class StagedExecutionResult:
      text: str
      confidence: float
      generated_tokens: int
      prompt_tokens: int
      finish_reason: str
      elapsed_ms: float
      raw_prompt: Optional[str] = None
      messages: Optional[List[Dict[str, str]]] = None
      generation_trace: Optional[Dict[str, Any]] = None
  ```
- In `_build_record_from_evidence`:
  The assembled record trace extracts `gen_val.get("messages")`, `raw_prompt`, and `generation_trace`. The resulting record trace accurately reflects the actual input messages passed to the tokenizer (including the exact strategy suffix specified in `MATH_EN_SUFFIXES`), preventing historical loss of prompt provenance.

### B. QwenMLXStagedRunner
In `qwen_mlx_backend.py`:
- `QwenMLXStagedRunner` implements `StagedRunnerInterface`:
  1. `run_generation(item, strategy, max_tokens, seed)`:
     - Configures format metadata from `item` (`answer_type`, `decimal_separator`); never sees `item["answer"]`.
     - Resolves strategy action (`A.DIRECT`, `A.COT`, `A.PAL`) and retrieves exact suffix via `self.backend._suffix(action)`.
     - Formats `messages = [{"role": "user", "content": item["query"] + suffix}]`.
     - Renders chat template via `self.backend.tokenizer.apply_chat_template` and records `raw_prompt` and `p_tok`.
     - Calls `self.backend._chat(messages, temp=0.0, max_tokens=max_tokens)` without running tools.
     - Parses generated text for diagnostics (`parse_status`, `wordy`).
     - Maps finish reasons (`completed`/`stop_answer`/`stop` -> `"stop"`, `length` -> `"length"`).
     - Returns validated `StagedExecutionResult`.
  2. `run_tool(code, timeout_seconds=5.0)`:
     - Invokes `run_python_sandboxed(code, timeout=timeout_seconds)` in isolated execution.
     - Returns `ToolExecutionResult(ok=ok, output=result, duration_ms=tool_ms)`.

### C. Lazy MLX Imports
- Made `load`, `stream_generate`, and `make_sampler` in `qwen_mlx_backend.py` lazy wrapper functions.
- Importing `qwen_mlx_backend` no longer eagerly imports `mlx` or `mlx_lm` at module level, allowing offline tests and checker import guards (`test_no_forbidden_imports`) to run in the same test runner without `sys.modules` contamination.

---

## 3. Verification & Evidence

### Full Regression Suite
Command:
```bash
.venv/bin/python -m pytest tests/test_qwen_staged_parity.py tests/test_gsm8k_collector.py tests/test_gsm8k_routing_baseline.py tests/test_checker_dry_run.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py -v
```
Output: **179 passed in 6.19s**, exit 0 (recorded in `regression.txt`).

### Standalone Parity Probes (`verification.py` -> `verification.json`)
```json
{
  "direct_parity": {
    "legacy_answer": "105",
    "staged_parsed_answer": "105",
    "confidence_matched": true,
    "tokens_matched": true,
    "suffix_preserved_in_messages": true,
    "parity_exact": true
  },
  "pal_success_parity": {
    "legacy_answer": "105",
    "staged_tool_output": "105",
    "confidence_matched": true,
    "parity_exact": true
  },
  "pal_error_fallback_parity": {
    "legacy_answer": "105",
    "legacy_confidence_penalized": 0.27,
    "tool_failed": true,
    "parity_exact": true
  },
  "collector_trace_fidelity": {
    "records_assembled": 3,
    "stored_message_matches_suffix": true,
    "bare_query_prevented": true,
    "raw_prompt_persisted": true
  },
  "measured_staged_gate_locked": {
    "deferred_rejection_active": true
  },
  "all_checks_passed": true
}
```

---

## 4. Inviolable Boundaries Maintained

1. **Model Budget**: 0 real model calls, 0 embedding calls, 0 VND expended.
2. **Data Blinding**: Candidate GSM8K 48/48 data remains strictly unread, unopened, and unparsed.
3. **Gate Status**: Staged measured evidence gate remains strictly locked and deferred (`ALLOWED_STAGED_EVIDENCE`).
4. **Research Bridge & Stage 0**: Stage 0 Gate remains active and unpassed; research bridge remains closed.
5. **Git Hygiene**: Working tree files preserved; no git commit, push, or reset executed.
