# Development-only research pilot

Evidence: **measured_development_pilot**

Fixed-strategy diagnostics on exposed development groups. No held-out evaluation or policy fitting.
Synthetic smoke traces validate software only; they provide no model-quality evidence.
Budgets cap each generation call; multi-call strategies can consume more total tokens. ReAct also retains its 200-token per-turn ceiling.
Timings are measured strategy-call duration (Python only for smoke), not online controller latency. Prompt counts are separate from generated-token costs.
Cells count questions and original groups separately. Variants and budget repetitions are not independent problems. No confidence intervals or superiority claims are inferred.

| Split | Family | Level | Strategy | Cap/call | Items/groups | Accuracy | Mean generated tokens | Parse failures | Length stops |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| calibration | gsm8k | unspecified | COT | 1024 | 12/12 | 0.833 | 95.3 | 0 | 0 |
| calibration | gsm8k | unspecified | DIRECT | 1024 | 12/12 | 0.833 | 93.2 | 0 | 0 |
| calibration | gsm8k | unspecified | PAL | 1024 | 12/12 | 0.833 | 86.4 | 0 | 0 |
| train | gsm8k | unspecified | COT | 1024 | 11/11 | 0.818 | 98.5 | 0 | 0 |
| train | gsm8k | unspecified | DIRECT | 1024 | 11/11 | 0.909 | 93.6 | 0 | 0 |
| train | gsm8k | unspecified | PAL | 1024 | 11/11 | 1.000 | 87.7 | 0 | 0 |

Token scope: generated tokens summed over all calls; prompt tokens recorded separately.
Human/source review and pilot configuration review remain pending. Parameters are not frozen. Stage 0 is unchanged.
