# Adapter repair rerun — 2026-10-24

**Not accepted yet: offline verification aborts in this workspace.** Directory
name denotes the intended acceptance review, not a passing verdict.

Source inspection confirms implementation of supplied seed dispatch, prompt
ID capture from `_chat`, staged missing-message rejection and subprocess
checker import isolation. Runtime verification remains incomplete:

- Copied repair `verification.py` into this separate directory and executed
  it: **exit 134**, native nanobind abort while importing `mlx.core`:
  `refusing to add duplicate key "cpu" to enumeration "mlx.core.DeviceType"`.
- Exact ten-file suite from the handoff: **exit 134**, not 185 passes.
  [Captured output](regression.txt) shows abort in `_chat` at the `mlx.core`
  import during `test_parity_direct_fallback_no_marker`.
- Mocked-backend/checker pair: **46 passed, 2 skipped in 3.39s**, exit 0.
  [Captured output](combined.txt). This is not 48 passed.

No weights or candidate data were loaded and no model generation/embedding
was invoked. The newly exercised parity path **does attempt actual MLX native
imports**, so it does not establish the promised MLX-import-free fixture
environment. Do not equate importing MLX with model inference; neither should
be hidden in reporting. Bridge, measured staged gate and Stage 0 unchanged.

## Required next correction

Make parity fixtures and the standalone verification script consistently inject
the numerical/seed/sampler boundary used by real legacy `_chat`, not just
`stream_generate`. Tests may exercise real legacy Python control flow without
initializing the MLX native extension. Verify the promise in a fresh subprocess
whose import hook rejects `mlx`/`mlx_lm`; avoid deleting/reimporting a loaded
native extension or masking a failed native import with a success claim.

Retain the supplied seed/token-ID/trace assertions and measured-evidence gate.
Rerun the exact ten-file command and probe only after correcting the fixture
boundary. Report skipped cases explicitly. No additional production defect is
inferred solely from the native abort; its root cause beyond the observed
import failure is not established by this review.

Earlier source request-changes report:
`audit/gsm8k_staged_adapter_review_20261024/README.md`. This follow-up records
the newer fixes and reproducibility blocker without overwriting that evidence
or the repair author's reported results. Do not open candidate/inference to
work around the test failure.
