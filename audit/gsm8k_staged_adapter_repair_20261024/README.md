# GSM8K Staged Adapter Repair Dossier — 2026-10-24 (Updated)

**Verdict: Runtime exit 134 / nanobind native abort resolved; numerical/seed/sampler boundary injected into legacy `_chat` and verified MLX-import-free under strict subprocess import guards.**
All tests executed purely offline using synthetic deterministic fixtures. Zero model weights loaded, zero embedding calls made, 0 VND expended, candidate GSM8K 48/48 content strictly unopened/unread, research bridge closed, and Stage 0 Gate unchanged and unpassed.

---

## 1. Resolution of Runtime Native Abort (Exit 134)

### Root Cause
When `_chat` was invoked on the parity path:
1. `_chat` unconditionally called `import mlx.core as mx` at the start of generation (even though `mx` was only referenced in optional logprobs unpacking).
2. `_chat` called `sampler = make_sampler(temp=temp)` without an injectable sampler hook, triggering `from mlx_lm.sample_utils import make_sampler`, which eagerly initializes `mlx.core`.
3. In environments where `mlx.core` was previously registered or where nanobind extensions reload across tests, nanobind aborted with SIGABRT (exit 134):
   `refusing to add duplicate key "cpu" to enumeration "mlx.core.DeviceType"`.
4. Tests monkeypatched only `stream_generate`, failing to isolate the numerical/sampler/seed boundary.

### Architectural Repair & Boundary Injection
In [`qwen_mlx_backend.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/qwen_mlx_backend.py):
- **Injectable Sampler Factory**: Added `sampler_factory: Optional[Callable[..., Any]] = None` to `QwenMLXBackend`. In `_chat`:
  ```python
  if getattr(self, "sampler_factory", None) is not None:
      sampler = self.sampler_factory(temp=temp)
  else:
      sampler = make_sampler(temp=temp)
  ```
  Offline testing injects `sampler_factory=lambda temp=0.0: None`, bypassing `mlx_lm.sample_utils` entirely.
- **Injectable Seed Setter**: Added `seed_setter: Optional[Callable[[int], None]] = None` to `QwenMLXBackend`. In `set_seed(seed)`:
  ```python
  if getattr(self, "seed_setter", None) is not None:
      self.seed_setter(seed)
  else:
      try:
          import mlx.core as mx
          mx.random.seed(seed)
      except Exception:
          pass
  np.random.seed(seed % (2**32))
  ```
  Offline execution routes through the injected setter and NumPy, avoiding `mlx.core.random.seed`.
- **Injectable Numerical Converter**: Added `array_converter: Optional[Callable[[Any], np.ndarray]] = None` to `QwenMLXBackend`. In `_chat`:
  ```python
  if getattr(r, "logprobs", None) is not None:
      if getattr(self, "array_converter", None) is not None:
          lp_arr = self.array_converter(r.logprobs)
      else:
          try:
              import mlx.core as mx
              lp_arr = np.asarray(mx.array(r.logprobs, dtype=mx.float32), dtype=np.float32)
          except Exception:
              lp_arr = np.asarray(r.logprobs, dtype=np.float32)
  ```
- **Removed Unconditional Import**: Removed `import mlx.core as mx` from line 427 of `_chat`.
- **Offline Backend Factory**: In [`tests/test_qwen_staged_parity.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/tests/test_qwen_staged_parity.py#L79-L95), `make_offline_backend` configures:
  ```python
  backend = QwenMLXBackend(
      model=FakeModel(),
      tokenizer=tokenizer or FakeTokenizer(),
      prompt_profile="english-math-v1",
      seed_setter=seed_setter or (lambda s: None),
      sampler_factory=sampler_factory or (lambda temp=0.0: None),
      array_converter=array_converter or (lambda x: np.asarray(x, dtype=np.float32)),
  )
  ```

---

## 2. Summary of Contracts vs. Review Findings

| Finding | Priority | Target Contract & Repair | Verification Evidence |
| :--- | :---: | :--- | :--- |
| **1. Apply Generation Seed** | **[P2]** | `QwenMLXStagedRunner` applies `seed` at the generation boundary before dispatch via `seed_setter` (or backend's `set_seed`). Validates non-boolean integer, delegates `seed` into `_chat(seed=seed)`, and records `applied_seed` inside `generation_trace`. | Verified in `test_staged_runner_applies_seed_before_dispatch`, `verification.json` (`finding_1_seed`: 42 and 999 verified, bool/str rejected). |
| **2. Persist Prompt Actually Consumed** | **[P2]** | Eliminated redundant double template rendering. `_chat` captures `prompt_token_ids` (`list[int]`), `raw_prompt` (decoded view), `prompt_tokens`, and `messages` directly from the single invocation's generation trace. Supports tokenizers returning raw token IDs (`TokenIdTokenizer`), preserving dispatched token IDs exactly without loss. | Verified in `test_staged_runner_captures_token_ids_from_tokenizer`, `verification.json` (`finding_2_prompt_and_token_ids`: dispatched IDs match recorded IDs `[101, 2054, 2003, 102]`). |
| **3. Restrict Invented Messages** | **[P2]** | `_build_record_from_evidence` strictly fails closed with `ValueError` on staged collection schemas if `messages` is `None` (prohibiting bare-query invention). For legacy synthetic schemas, missing messages are explicitly tagged `messages_provenance = "synthetic_legacy_fallback"`. Genuine traces receive `messages_provenance = "genuine_trace"`. Verified both in initial collection and on journal recovery after crash. | Verified in `test_collector_fails_closed_when_messages_missing_on_staged_schema`, `test_collector_labels_legacy_fallback_explicitly`, `test_interrupted_resumed_reconstruction_fails_closed_if_messages_missing_in_journal`, `test_interrupted_resumed_reconstruction_recovers_genuine_messages`, and `verification.json`. |
| **4. Zero-MLX Subprocess Verification** | **[P1]** | Added [`test_parity_and_adapter_run_under_strict_forbidden_mlx_imports`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/tests/test_qwen_staged_parity.py#L716-L790) and `verify_mlx_import_free_subprocess()`. Executes legacy `_chat` and staged runner in a fresh subprocess whose import hook raises `AssertionError` if any `mlx` or `mlx_lm` package is imported. | Subprocess exit code 0 (`STAGED_PARITY_ZERO_MLX_SUBPROCESS_OK`), `zero_mlx_imports_verified: true`. |
| **5. Checker Subprocess Isolation** | **[P1]** | In `tests/test_checker_dry_run.py`, isolated `test_no_forbidden_imports` inside a clean subprocess with guarded `builtins.__import__` interceptor. Prevents false positive test failures caused by pytest's shared `sys.modules` when mock suites run alongside checker tests. | Subprocess exit code 0 (`CHECKER_IMPORT_ISOLATION_OK`), combined suite passes cleanly. |
| **6. Gate Lock Remains Enforced** | **[Gate]** | Reaffirmed and verified that `write_fitting_seal` strictly rejects staged manifests with non-synthetic evidence (e.g. `measured_staged_collection`) as deferred before sealing. | Verified in `test_staged_measured_evidence_remains_locked` and `verification.json` (`measured_staged_evidence_gate`). |

---

## 3. Test & Verification Evidence

### Standalone Verification (`verification.py`)
Run command:
```bash
.venv/bin/python audit/gsm8k_staged_adapter_repair_20261024/verification.py
```
Output recorded in [`verification.json`](verification.json):
```json
{
  "finding_1_seed": {
    "seed_setter_called_with_exact_seed": true,
    "seed_42_verified": true,
    "seed_999_verified": true,
    "bool_seed_rejected": true,
    "str_seed_rejected": true,
    "generation_trace_records_applied_seed": true
  },
  "finding_2_prompt_and_token_ids": {
    "prompt_token_ids": [101, 2054, 2003, 102],
    "dispatched_ids_match_recorded": true,
    "prompt_tokens_matches_length": true,
    "raw_prompt_decoded_view": true,
    "messages_preserves_suffix": true
  },
  "finding_3_messages_contract": {
    "staged_missing_messages_fails_closed": true,
    "legacy_missing_messages_provenance": "synthetic_legacy_fallback",
    "genuine_trace_provenance": "genuine_trace"
  },
  "checker_subprocess_isolation": {
    "subprocess_exit_code": 0,
    "stdout": "CHECKER_IMPORT_ISOLATION_OK",
    "forbidden_imports_blocked": true
  },
  "adapter_mlx_import_free_subprocess": {
    "subprocess_exit_code": 0,
    "stdout": "STAGED_PARITY_ZERO_MLX_SUBPROCESS_OK",
    "zero_mlx_imports_verified": true
  },
  "measured_staged_evidence_gate": {
    "measured_staged_collection_rejected": true
  }
}
```

### 10-File Regression Suite
Run command:
```bash
.venv/bin/python -m pytest tests/test_qwen_staged_parity.py tests/test_gsm8k_collector.py tests/test_gsm8k_routing_baseline.py tests/test_checker_dry_run.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py -v
```
Result: **186 passed in 13.98s**, exit code 0 (recorded in [`regression.txt`](regression.txt)).

### Mocked Backend + Checker Dry Run Suite
Run command:
```bash
.venv/bin/python -m pytest test_qwen_mlx_backend_mocked.py tests/test_checker_dry_run.py -v
```
- **Total collected items**: 48 items (26 in `test_qwen_mlx_backend_mocked.py`, 22 in `tests/test_checker_dry_run.py`).
- **Accounting of results**:
  - In environments without native MLX bfloat16 hardware/bindings: **46 passed, 2 skipped in 3.39s**, exit code 0 (tests `test_bfloat16_logprobs_produce_finite_confidence` and `test_bfloat16_hidden_states_export_float32_embedding` intentionally skip via `pytest.skip("Requires native MLX bfloat16 arrays")`).
  - In environments with native MLX bfloat16 support: **48 passed in 3.14s**, exit code 0.
- Both outcomes have 0 failures, 0 errors, exit code 0 (recorded in [`combined.txt`](combined.txt) and [`regression.txt`](regression.txt)).

---

## 4. SHA-256 Source Fingerprints

| Source File | SHA-256 Fingerprint |
| :--- | :--- |
| `qwen_mlx_backend.py` | `1f3ad3e654ff0ab88e103033f78877691321fc8d782131185957eed5ce7f9a5c` |
| `experiments/gsm8k_collector.py` | `5994cb1d5c555645b06385a023632a2fbb80d221fe01dacaa7af39fcf2e738ff` |
| `experiments/gsm8k_routing_baseline.py` | `9c855b31b29cc34e55a803dc75c9e9fdea40fefa27864dc522544c2545012760` |
| `tests/test_checker_dry_run.py` | `31293740f6f8e4a7a82b2279717c81c1a888ed466bd4cd35752908f9f12404b0` |
| `tests/test_qwen_staged_parity.py` | `0ff7fbe9cd76400309f6aa82872f3091e4c9e8a6ab6f800190bcc5fb4b8fadd8` |
