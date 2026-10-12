# Ordering certificate development pilot

Evidence: synthetic_smoke. Decision: development_diagnostics_only.

Prompt/parser profile: order-contract-v2 / single-zero-based-index-v2.

Synthetic fixtures are not measured model quality. This is not a confirmatory test.

| Method | Questions | Item × seed rows | Accuracy | Mean prompt | Mean completion | Mean total tokens | Escalation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_pal_answer | 2 | 2 | 1.000 | 73.5 | 5.0 | 78.5 | 0.000 |
| fixed_pal_certificate | 2 | 2 | 1.000 | 72.5 | 12.0 | 84.5 | 0.000 |
| fixed_candidate_selection | 2 | 2 | 1.000 | 295.0 | 14.0 | 309.0 | 0.000 |
| fixed_thinking_native | 2 | 2 | 1.000 | 58.5 | 6.0 | 64.5 | 0.000 |
| w_answer | 2 | 2 | 1.000 | 73.5 | 5.0 | 78.5 | 0.000 |
| w_certificate | 2 | 2 | 1.000 | 72.5 | 12.0 | 84.5 | 0.000 |
| verified_certificate | 2 | 2 | 1.000 | 72.5 | 12.0 | 84.5 | 0.000 |
| symbolic_solver | 2 | 2 | 1.000 | 0.0 | 0.0 | 0.0 | 0.000 |

Verified / fixed candidate mean-token ratio (all invoked stages): 0.273.
Gate confusion by FIRST-STAGE answer correctness (item × seed counts): {'true_accept': 2, 'false_accept': 0, 'true_reject': 0, 'false_reject': 0}.
Rescue / harm versus initial PAL answer: 0 / 0.

A correct answer with an invalid witness is not an incorrect-answer false accept.
Fallback costs count even when the fallback is wrong or truncated.
Replayed generation-time sums, offline verifier time and symbolic CPU-path time are separate; not measured online latency.
The generic verifier includes exact uniqueness solving. The standalone solver is a query-only baseline, not an oracle.
Model-token counts are not FLOPs, energy or full inference cost. Synthetic counts are placeholders.
The Python execution helper is NOT a security boundary. Real runs need a controlled environment.
No preregistration pass, superiority or publication claim follows from this development report.
