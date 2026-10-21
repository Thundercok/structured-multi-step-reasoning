# Online policy execution in RAT — 2026-10-19

RAT uses CoT; CoT is implemented through RAT. This change connects an explicitly supplied fitted policy to a RAT engine instance. It does not enable the controller in the default desktop app or establish equivalence of the entire application and the research harness.

## Implemented

`reasoning/runtime.py` exposes `OnlineReasoningController(backend, policy, policy_source=...)`. Supply an `LLMBackend` implementation, an `OptimalStoppingPolicy` with fitted entry predictor, stopping thresholds and cost metadata, and an explicit source label. The controller performs no fitting, artifact deserialization, model loading or automatic campaign execution. The provenance label is caller-supplied, not an approval certificate.

The controller calls the fitted predictor on backend embeddings and shared complexity features. It runs PAL or REACT once, or calls the ladder COT → SELF_CONSISTENCY → TOT only as needed. After each nonterminal ladder result it uses `policy.should_escalate`, including fitted calibration. It never receives gold labels, calls the canned tuition/GPA/policy branches, or substitutes legacy responses for backend failures. It reports only observed answers, raw confidence and nonnegative integer generated-token counts.

Pass the controller to `MetaReasonerEngine(controller=controller)`, then call `solve(query)` in the application's existing worker execution context. Explicit controller mode bypasses legacy cache/intent branches and returns execution_mode=online_policy, strategy_path, policy_source and confidence_kind=backend_raw. Steps are execution summaries, not raw chain-of-thought. verification_status stays unverified; model confidence is not a proof. The global singleton remains unchanged and controller-free.

Latency is elapsed execution time including embedding, routing, backend calls and stopping in this invocation. With the synthetic test backend it measures only software execution. Generated-token counts sum all invoked strategies as reported by the backend; they exclude embedding cost/prompt tokens unless an explicit future accounting contract says otherwise. They are not full inference cost.

## Calibration fix

A genuinely fitted IsotonicCalibrator previously passed a zero-dimensional scalar array to sklearn's predict, while online should_escalate supplies a scalar. The fix reshapes the input for prediction and restores the input shape or returns one float. No fitted coefficients, threshold-fitting rule, prompts, model settings or split rules were changed. Tests verify scalar/array agreement and a calibrated stop that differs from raw-confidence escalation.

## Acceptance and limits

Synthetic fixtures fit actual EntryPredictor and OptimalStoppingPolicy objects, exercise all entry routes and stop/escalate behavior, compare the path and generated-token sum against the existing run_episode policy on identical observations, and test failure/invalid-observation propagation. These checks are software evidence only. No real model inference or accuracy campaign was run.

Default UI wiring remains deferred until a reviewed fitted policy bundle identifies compatible model/version, prompts, embeddings/features, confidence/calibrators, lambda, token semantics and disjoint train/calibration/test groups. There is no auto-loader for pickle/joblib. A free-text policy_source alone does not establish those contracts. The caller also owns per-call deadlines, total budget/cancellation and worker placement; this adapter is synchronous and must not be installed in the Qt main thread. Stage 0 and review gates remain unchanged.

The existing legacy meta_reasoner path still has canned policy/GPA examples; this change does not relabel them as measured policy execution. One Qt/VGC assertion fails in that legacy path and reproduces with unchanged HEAD; see audit/rat_online_reasoning_20261019/baseline_vgc.txt.
