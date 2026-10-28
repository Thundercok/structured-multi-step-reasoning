# Research repair verification — 2026-10-28

User explicitly authorized this focused batch. Result: **62 passed in 55.47s**.

```bash
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_qwen_staged_parity.py tests/test_cot_restart_matched.py tests/test_reasoning_conversation.py -q
```

The sandbox attempt aborted during native Qt Quick import before tests ran; its raw log is retained. The retry outside the sandbox completed successfully with offscreen Qt. `pytest.log` and `pytest.xml` retain the actual passing result.

The batch covers the required research regressions, PCA minority-class/small-fold and single-row cases, strict telemetry rejection and normalized batched logprobs, the five matched tests using restored historical artifacts, and conversation contracts plus the migrated Qt Quick multi-turn test.

The four script path changes received source review only; their full workflows were not executed. Real MLX entry-point configuration was edited but not exercised against a real model. These are software checks using synthetic doubles and historical inputs, not new model-quality evidence or live UI acceptance. Stage 0 remains unchanged. Manifest source hashes were captured after the run.
