# Ordering certificate study

Evidence: synthetic_smoke. Decision: synthetic_validation_only.

| Method | Questions | Accuracy | Mean tokens | Escalation |
| --- | ---: | ---: | ---: | ---: |
| fixed_pal_answer | 4 | 0.250 | 127.2 | 0.000 |
| fixed_pal_certificate | 4 | 0.250 | 139.2 | 0.000 |
| fixed_candidate_selection | 4 | 1.000 | 557.0 | 0.000 |
| fixed_thinking_native | 4 | 1.000 | 165.2 | 0.000 |
| w_answer | 4 | 0.500 | 260.2 | 0.250 |
| w_certificate | 4 | 0.500 | 272.2 | 0.250 |
| verified_certificate | 4 | 1.000 | 553.2 | 0.750 |
| symbolic_solver | 4 | 1.000 | 0.0 | 0.000 |

## Paired comparisons

Verified minus fixed_candidate_selection: accuracy delta 0.000, CI95 [0.0, 0.0]; token ratio 0.993, CI95 [0.4933862433862434, 1.25].
Verified minus w_certificate: accuracy delta 0.500, CI95 [0.0, 1.0]; token ratio 2.032, CI95 [1.0, 5.0].

Gate confusion by first-stage answer correctness (item × seed counts): {'true_accept': 3, 'false_accept': 0, 'true_reject': 9, 'false_reject': 0}.


W-certificate and Verified-certificate share identical PAL output and fallback attempts.
Symbolic solving has zero model tokens; CPU timings are reported separately.
Generic certificate verification includes an exact uniqueness check. Its CPU cost is explicit.
Synthetic token counts validate accounting only. Saved strategy-time sums are replayed, not online latency.
Intervals resample groups, preserving all seeds. A CI containing zero does not prove noninferiority.
Degenerate accuracy bootstraps cannot pass the gate without a reviewed boundary-safe statistical addendum.
Measured execution remains pending review, sample-size justification and Stage 0 requirements.
