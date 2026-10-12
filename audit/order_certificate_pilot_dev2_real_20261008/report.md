# Ordering certificate development pilot

Evidence: measured_development_pilot. Decision: development_diagnostics_only.

Synthetic fixtures are not measured model quality. This is not a confirmatory test.

| Method | Questions | Item × seed rows | Accuracy | Mean prompt | Mean completion | Mean total tokens | Escalation |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixed_pal_answer | 2 | 2 | 0.500 | 94.5 | 230.0 | 324.5 | 0.000 |
| fixed_pal_certificate | 2 | 2 | 1.000 | 113.5 | 232.0 | 345.5 | 0.000 |
| fixed_candidate_selection | 2 | 2 | 0.500 | 1934.0 | 1561.0 | 3495.0 | 0.000 |
| fixed_thinking_native | 2 | 2 | 0.000 | 89.5 | 1024.0 | 1113.5 | 0.000 |
| w_answer | 2 | 2 | 0.500 | 94.5 | 230.0 | 324.5 | 0.000 |
| w_certificate | 2 | 2 | 1.000 | 113.5 | 232.0 | 345.5 | 0.000 |
| verified_certificate | 2 | 2 | 0.500 | 1142.5 | 1069.5 | 2212.0 | 0.500 |
| symbolic_solver | 2 | 2 | 1.000 | 0.0 | 0.0 | 0.0 | 0.000 |

Verified / fixed candidate mean-token ratio (all invoked stages): 0.633.
Gate confusion by FIRST-STAGE answer correctness (item × seed counts): {'true_accept': 1, 'false_accept': 0, 'true_reject': 0, 'false_reject': 1}.
Rescue / harm versus initial PAL answer: 0 / 1.

A correct answer with an invalid witness is not an incorrect-answer false accept.
Fallback costs count even when the fallback is wrong or truncated.
Replayed generation-time sums, offline verifier time and symbolic CPU-path time are separate; not measured online latency.
The generic verifier includes exact uniqueness solving. The standalone solver is a query-only baseline, not an oracle.
Model-token counts are not FLOPs, energy or full inference cost. Synthetic counts are placeholders.
The Python execution helper is NOT a security boundary. Real runs need a controlled environment.
No preregistration pass, superiority or publication claim follows from this development report.
