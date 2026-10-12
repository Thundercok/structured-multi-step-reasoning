# Ordering certificate development pilot

Evidence: measured_development_pilot. Decision: development_diagnostics_only.

Prompt/parser profile: order-contract-v2 / single-zero-based-index-v2.

Synthetic fixtures are not measured model quality. This is not a confirmatory test.

| Method | Questions | Item × seed rows | Accuracy | Mean prompt | Mean completion | Mean total tokens | Escalation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_pal_answer | 8 | 8 | 0.500 | 124.4 | 142.0 | 266.4 | 0.000 |
| fixed_pal_certificate | 8 | 8 | 0.500 | 126.4 | 284.2 | 410.6 | 0.000 |
| fixed_candidate_selection | 8 | 8 | 0.375 | 2860.1 | 2365.5 | 5225.6 | 0.000 |
| fixed_thinking_native | 8 | 8 | 0.000 | 102.4 | 2048.0 | 2150.4 | 0.000 |
| w_answer | 8 | 8 | 0.500 | 542.4 | 493.0 | 1035.4 | 0.125 |
| w_certificate | 8 | 8 | 0.500 | 546.4 | 639.5 | 1185.9 | 0.125 |
| verified_certificate | 8 | 8 | 0.500 | 1885.4 | 1741.2 | 3626.6 | 0.625 |
| symbolic_solver | 8 | 8 | 1.000 | 0.0 | 0.0 | 0.0 | 0.000 |

Verified / fixed candidate mean-token ratio (all invoked stages): 0.694.
Gate confusion by FIRST-STAGE answer correctness (item × seed counts): {'true_accept': 3, 'false_accept': 0, 'true_reject': 4, 'false_reject': 1}.
Rescue / harm versus initial PAL answer: 0 / 0.

A correct answer with an invalid witness is not an incorrect-answer false accept.
Fallback costs count even when the fallback is wrong or truncated.
Replayed generation-time sums, offline verifier time and symbolic CPU-path time are separate; not measured online latency.
The generic verifier includes exact uniqueness solving. The standalone solver is a query-only baseline, not an oracle.
Model-token counts are not FLOPs, energy or full inference cost. Synthetic counts are placeholders.
The Python execution helper is NOT a security boundary. Real runs need a controlled environment.
No preregistration pass, superiority or publication claim follows from this development report.
