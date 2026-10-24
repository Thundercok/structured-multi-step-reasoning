# Native seed failure propagation — 2026-10-24

Removed the broad exception suppression in `QwenMLXBackend.set_seed`'s
non-injected branch. Missing MLX or a failed `mx.random.seed` now propagates
before NumPy seeding and before staged generation dispatch. No successful
generation or applied-seed result is manufactured after a failed seed call.
The injected offline path is unchanged.

Three authored tests in `tests/test_qwen_seed_failure.py` check missing import,
native-setter exception with zero generation dispatches, and successful seeding
of both MLX and NumPy. The native module is a temporary in-memory stub in these
tests; no actual MLX extension/model load is needed.

```bash
.venv/bin/python -m pytest tests/test_qwen_seed_failure.py tests/test_qwen_staged_parity.py tests/test_gsm8k_collector.py tests/test_gsm8k_routing_baseline.py tests/test_checker_dry_run.py tests/test_research_pilot.py tests/test_gsm8k_development.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py -q
```

Observed **189 passed in 12.70s**, exit 0; mandatory research checks included.
[Verification and source fingerprints](verification.json). `git diff --check`
for changed implementation/new tests passed. Existing uncommitted backend/UI
changes were preserved; only the seed exception block was edited here.

This resolves the seed-failure readiness issue named in the preceding offline
adapter acceptance. It does not verify native hardware RNG behavior or model
quality, enable measured staged ingestion, or authorize candidate access.
Candidate 48/48 unopened, inference/embedding calls 0, bridge/Stage 0 unchanged.
Historical hashes remain intact; new source requires a fresh execution freeze
before any real collection. Other data/provenance/custody review remains pending.
