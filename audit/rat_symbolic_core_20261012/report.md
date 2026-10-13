# RAT core: scoped verification and symbolic completion

2026-10-12, Asia/Saigon. Implemented in the existing assistant runtime,
capability registry and conversation work trace. No new feature window.

## Behavior

Operations can declare an `OperationVerifier`. Runtime snapshots observed
inputs/results with request-local evidence IDs and digests, checks execution
and final candidates, and feeds real check failures back to the model. New
capabilities use the same mechanism; a custom checker regression exercises
registration without a central action-name branch.

The first supported scope is arithmetic. Whole literal requests are bound to
the final result. Rational arithmetic is independently computed within syntax
and resource limits. Word-problem formalization remains unchecked; a result
matching a model-selected expression only has `calculation_answer_only` scope.
No number is extracted from arbitrary prose to manufacture a PASS.

Repair has a default limit of two rounds and shares max-step/token/cancel
limits. Rejected candidates, check reports, raw requests/completions and actual
inference usage are retained. No failed candidate becomes a completed answer
on budget exhaustion. UNKNOWN is retained outside supported scope.

For a uniquely computed arithmetic answer, the correction schema constrains
the model's answer string to that independently derived value. The model call
still occurs and its returned value is checked again. This is **symbolic result
constrained decoding**, not evidence that the neural model independently learned
to reason or corrected the calculation without help. A malformed envelope,
wrong value or unwanted tool call is a recorded failure.

UI uses `WorkTracePane` in the same chat turn for checks and revisions, plus
ordinary inline error/retry messages. No source/model private thought fields
are displayed. Gemini's iteration-2 note prototype remains a prototype; this
change does not implement its pending backend/history stages.

## Legacy integration

VGC arithmetic now adapts to the same checker: matching program output alone
cannot certify a different target or contradictory final claim. AST fallback
is rechecked and does not claim a deep model call. Deterministic helpers report
0 inference tokens and unknown calibrated confidence (`None`). Other legacy
MetaReasoner paths remain unmeasured and are not the supported research runner.

Document verification is limited to an entire exact excerpt in the supplied
text. It does not certify entity-value relations, semantic entailment, relevance
or source authenticity. Reranker labels this scope as “Trích đoạn khớp nguồn”.
The Alice=100/Bob=20 counterexample no longer verifies “Bob=100”.

## Validation

- `core_tests.txt`: **119 passed**. Includes independent calculation,
  wrong final value/expression, contradictory prose, bounded repair,
  budget/cancel, request isolation, checker failures, malformed envelopes,
  custom capability registration, legacy VGC and existing core regressions.
- `ui_tests.txt`: **53 passed**, Qt offscreen. Includes Gemini's note preview,
  existing chat/artifact/worker tests and check/repaired-result rendering in
  the same WorkTracePane without private raw reasoning.
- `git diff --check`: passed. No native window was launched in this turn.

The Gemini report's research count was not rerun or represented as new model
evidence. Harness, research verifier, fitting, default model configuration,
controller and Gemini's four prototype files match HEAD; hashes and scope are
recorded in `validation.json`. Research gates and DocAI separation are unchanged.
This turn did not commit, push, pull, reset or force Git.

## Real-model development smoke

All four iterations use `qwen2.5:1.5b`, an empty temporary database, no personal
indexing and the same exposed query `47 * 83`. Call timeout was bounded at 40s
for this development script. This was debugging of one repeated question, not
an unseen benchmark, paired baseline study or model-accuracy evaluation.

| Artifact | Result | Interpretation |
| --- | --- | --- |
| `live_smoke.json` | UNKNOWN; no answer returned | Unconstrained model repeats prose containing wrong result 3821. Whole-answer gate blocks it. |
| `live_smoke_v2.json` | FAIL; no answer returned | JSON format alone still produces 3821; numeric check rejects it. |
| `live_smoke_v3.json` | UNKNOWN; no answer returned | Improved feedback roles still leave wrong/invalid output; bounded guard stops. |
| `live_smoke_v4.json` | PASS; answer 3901 | Checker-derived unique enum constrains decoding and the final value passes rechecking. |

Final request latency: **47.826s**, of which measured model time **47.814s**;
verification time **5.478ms**. Token scope is reported prompt + completion:
**3,712 + 207 = 3,919**. No replay timing, synthetic token counts or embeddings
are included. Costs of the three failed debugging runs are separately retained
in `validation.json`, not excluded from the audit.

The default model remains weak in this example: free correction did not succeed,
and its initial plan copied instructions into the goal instead of producing a
useful plan. The check is bound to the actual user expression, not that model
plan. The current checker does not semantically validate plans. The result is
correct under symbolic constraints, but latency and broader planning quality
still need improvement; this is not an impressive speed result or an NCKH claim.

## Files and follow-on work

Implementation and boundaries: `docs/rat_verification.md`.
Source hashes, preserved paths, smoke summaries: `validation.json`.
Raw model calls, constraints, check events and usage: `live_smoke*.json`.

Next capability checkers should use this shared contract. Schedule constraints
need actual timezone/duration/source coverage; document semantics need more than
quote alignment. Learned-controller feature changes require separate reviewed
data/fitting. No additional capability, research experiment or model change was
introduced for those future steps in this implementation.

## Request identity follow-up

Review found that notebook generation is a cancellation epoch, so it cannot be
used as a unique verification request ID. Requests now receive UUIDs; an
additional regression verifies distinct evidence IDs for identical operations
in successive requests. Relevant runtime/note regressions: 76 passed, recorded
in `request_identity_regressions.txt`. The earlier live smoke is retained at its
original source hashes; no further inference was needed for this identity fix.
