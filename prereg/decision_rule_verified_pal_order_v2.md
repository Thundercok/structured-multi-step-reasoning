# Ordering certificate study: execution and statistics preregistration

Status: DRAFT; PENDING INDEPENDENT REVIEW AND EXECUTION FREEZE (2026-10-08).
This file is not a committed/frozen preregistration. Numeric settings below are
proposals, not accepted success criteria or a validated power design.
Development scope: 31 exposed items (8 train, 23 calibration; see
`audit/ordering_development_audit_20261008.md` for evidence corrections).
Test answers in `data/order_confirmatory_gapB_100.json` remain held-out and unsolved.
Historical `decision_rule_verified_pal_order.md` is preserved.

## Question and proposed fixed comparisons

Does checking a program's actual ranking certificate improve an exec-gated
cascade, and can either cascade preserve accuracy at a materially lower model
token count than always using three-candidate selection?

The implementation historically called `ToT` generates three complete solutions
and selects one; call it **candidate selection**, not tree search.

Collect four arms on the same items and seeds: answer-only PAL, certificate PAL,
candidate selection, and native thinking. Report all four fixed arms, historical
W-answer, W-certificate, Verified-certificate, and the query-only symbolic solver.

W-certificate and Verified-certificate MUST reuse the exact same certificate
PAL generation and execution payload, and the exact same fallback output.
Their sole intervention is exec gate versus certificate gate. Comparing
answer-only W to Verified-certificate also changes the prompt/output contract;
report it as a combined intervention, not an isolated verifier effect.

No entry router is fitted in this ordering extension. No test-selected lambda,
prompt, cap, verifier mode or policy is permitted.

## Gate and symbolic baseline

Parse the entire supported query; fail closed on any unsupported clause. Check
only the actual successful sandbox result, never a literal in generated code.
Require exactly the fields `order` and `answer`, the complete runner permutation,
all clue constraints, and alignment with the asked rank. Runtime failures,
length truncation, unsupported input and missing certificates escalate.

One feasible ranking does not establish an entailed answer on an ambiguous
question. The offline implementation therefore defaults to
`generic_with_uniqueness_check`, which uses an exact query-derived solver to
establish a unique asked occupant. Multiple rankings are allowed if they agree
at that rank. This mode is NOT a cheap witness-only verifier.

The exact same parser plus symbolic solver is a mandatory standalone baseline.
It receives query text only, abstains on unsupported/ambiguous/inconsistent
input, and has zero model tokens; report its CPU time separately. On the 31-item
development check, it solved 31/31 exposed items and matched their gold. Historical
timing figures lacked retained raw telemetry; report fresh CPU measurements,
not those figures. Acknowledge the strong baseline without extrapolating to test
or calling it an oracle. Verifier and solver share the same parser limits.

## Proposed execution settings — NOT FROZEN

- Model candidate: `mlx-community/Qwen3-8B-4bit`, revision
  `545dc4251c05440727734bcd94334791f6ab0192`.
- Generation seeds: 42, 43, 44; derived per-item/arm/call seeds are recorded.
- Non-native arms: native thinking disabled; PAL is greedy with a 512-token cap.
- Candidate selection: three 1,024-token candidates at temperature 0.7, then a
  greedy 64-token selector receiving all three full outputs.
- Native thinking: enabled, temperature 0.6, 1,024 generated-token cap INCLUDING
  both reasoning and final answer. This is a development proposal changed from
  3,136; neither the claimed hardware cause nor an adequate reasoning budget has
  been established from retained raw evidence. Pilot overrides stay development-only.
- Explicit `mx.clear_cache()` and `gc.collect()` after each model call.
- Every exact prompt is saved in the settings and every call's raw messages.

## Data and isolation

- Held-out test set: 100 items in `data/order_confirmatory_gapB_100.json`.
- Historical 31 `gen02_tune` ordering items remain exposed development:
  8 train, 23 calibration.
- Zero canonical fingerprint overlap confirmed against legacy tuning/main pools.
- Prospective test answers remain uninspected and unsolved until execution.

## Cost and inference

Count prompt AND completion tokens from every invoked model call, including all
candidate branches and selector prompts. Keep both components separately.
Model tokens are not FLOPs, energy or full inference cost. Collection runs every
arm; counterfactual selected-path cost is different from collection expenditure.
Replayed generation-time sums are not measured online end-to-end latency.
Report offline solver/verifier CPU time separately.

For a two-stage cascade, reconstruct cost with the conditional fallback mean:
`mean_cost = mean_initial_cost + escalation_rate × mean_fallback_cost_given_reject`.

## Proposed statistical decision rule — NOT IMPLEMENTED IN FULL / NOT FROZEN

Primary comparison: Verified-certificate minus fixed candidate selection, on
test only ($N = 100$). Average over the three observed seeds per question, then
give questions equal weight. Seeds are not additional independent questions.
Use 5,000 paired percentile cluster-bootstrap draws of `group_id`, preserving
all items and seeds, with bootstrap seed 20261008.

The decision gate requires BOTH:

1. Proposed lower endpoint of the 95% CI for accuracy difference is at least
   **−0.05** (−5 pp). This margin change from −2 pp has no validated power
   justification or independent acceptance; it must be decided before any test run.
2. Upper endpoint of the 95% CI for the mean-token ratio is at most **0.60**.

Boundary-safe criterion is a TODO, not an executable test specification. The
earlier draft's named alternatives were not implemented or reviewed. Specify a
paired non-inferiority procedure, its grouping/seed treatment, boundary behavior,
coverage and power assessment before freezing. The current software fails closed
on degenerate accuracy bootstraps; it must not substitute an unspecified test or
interpret an empirical `[0, 0]` as population non-inferiority confirmation.

Software gate calculations under these draft numbers are diagnostics only.
No 80% power claim follows from the former CI-width illustrations. Both the
accuracy rule and token-ratio rule require review before confirmatory execution.

Secondary diagnostic: paired Verified-certificate minus W-certificate, with
the same grouping/seeds. Report per-method accuracy/token intervals, escalation,
first-stage answer-based gate confusion, false-accept group counts, rescue and
harm versus both the initial stage and relevant baseline. Item × seed counts
must be labeled as such.

Failure or uncertainty at the gate means **no demonstrated target benefit**, not
proof that candidate selection is superior. Keep all baseline outcomes, including
symbolic domination and negative results. Publication requires independent review.
The existing Qwen/Meta-Reasoner Stage 0 gate remains unchanged.

## Development collector status

The supported entry point now has a development-only collector with an explicit
mock mode. Offline regression tests and synthetic artifacts validate persistence,
resume isolation and shared scoring; no real-model pilot from the repaired
collector has been reviewed. Mock cannot authenticate the model/runtime adapter,
validate token accounting on real generation or satisfy a campaign gate.
