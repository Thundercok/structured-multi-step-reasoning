# Development-only research pilot

Evidence: **measured_development_pilot**

Fixed-strategy diagnostics on exposed development groups. No held-out evaluation or policy fitting.
Synthetic smoke traces validate software only; they provide no model-quality evidence.
Budgets cap each generation call; multi-call strategies can consume more total tokens. ReAct also retains its 200-token per-turn ceiling.
Timings are measured strategy-call duration (Python only for smoke), not online controller latency. Prompt counts are separate from generated-token costs.
Cells count questions and original groups separately. Variants and budget repetitions are not independent problems. No confidence intervals or superiority claims are inferred.

| Split | Family | Level | Strategy | Cap/call | Items/groups | Accuracy | Mean generated tokens | Parse failures | Length stops |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| calibration | arith | 1 | COT | 96 | 1/1 | 1.000 | 39.0 | 0 | 0 |
| calibration | arith | 1 | COT | 1024 | 1/1 | 1.000 | 39.0 | 0 | 0 |
| calibration | arith | 1 | DIRECT | 96 | 1/1 | 1.000 | 58.0 | 0 | 0 |
| calibration | arith | 1 | DIRECT | 1024 | 1/1 | 1.000 | 58.0 | 0 | 0 |
| calibration | arith | 2 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | arith | 2 | COT | 1024 | 1/1 | 1.000 | 100.0 | 0 | 0 |
| calibration | arith | 2 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | arith | 2 | DIRECT | 1024 | 1/1 | 1.000 | 114.0 | 0 | 0 |
| calibration | arith | 3 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | arith | 3 | COT | 1024 | 1/1 | 1.000 | 155.0 | 0 | 0 |
| calibration | arith | 3 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | arith | 3 | DIRECT | 1024 | 1/1 | 1.000 | 179.0 | 0 | 0 |
| calibration | arith | 4 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | arith | 4 | COT | 1024 | 1/1 | 0.000 | 318.0 | 0 | 0 |
| calibration | arith | 4 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| calibration | arith | 4 | DIRECT | 1024 | 1/1 | 0.000 | 1024.0 | 0 | 1 |
| calibration | g24 | 1 | COT | 96 | 1/1 | 1.000 | 71.0 | 0 | 0 |
| calibration | g24 | 1 | COT | 1024 | 1/1 | 1.000 | 71.0 | 0 | 0 |
| calibration | g24 | 1 | DIRECT | 96 | 1/1 | 0.000 | 18.0 | 0 | 0 |
| calibration | g24 | 1 | DIRECT | 1024 | 1/1 | 0.000 | 18.0 | 0 | 0 |
| calibration | g24 | 2 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | g24 | 2 | COT | 1024 | 1/1 | 0.000 | 1024.0 | 1 | 1 |
| calibration | g24 | 2 | DIRECT | 96 | 1/1 | 0.000 | 23.0 | 0 | 0 |
| calibration | g24 | 2 | DIRECT | 1024 | 1/1 | 0.000 | 23.0 | 0 | 0 |
| calibration | g24 | 3 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | g24 | 3 | COT | 1024 | 1/1 | 0.000 | 1024.0 | 1 | 1 |
| calibration | g24 | 3 | DIRECT | 96 | 1/1 | 0.000 | 17.0 | 0 | 0 |
| calibration | g24 | 3 | DIRECT | 1024 | 1/1 | 0.000 | 17.0 | 0 | 0 |
| calibration | g24 | 4 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| calibration | g24 | 4 | COT | 1024 | 1/1 | 0.000 | 1024.0 | 1 | 1 |
| calibration | g24 | 4 | DIRECT | 96 | 1/1 | 0.000 | 28.0 | 0 | 0 |
| calibration | g24 | 4 | DIRECT | 1024 | 1/1 | 0.000 | 28.0 | 0 | 0 |
| calibration | order | 1 | COT | 96 | 1/1 | 1.000 | 93.0 | 0 | 0 |
| calibration | order | 1 | COT | 1024 | 1/1 | 1.000 | 93.0 | 0 | 0 |
| calibration | order | 1 | DIRECT | 96 | 1/1 | 1.000 | 4.0 | 0 | 0 |
| calibration | order | 1 | DIRECT | 1024 | 1/1 | 1.000 | 4.0 | 0 | 0 |
| calibration | order | 2 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| calibration | order | 2 | COT | 1024 | 1/1 | 1.000 | 210.0 | 0 | 0 |
| calibration | order | 2 | DIRECT | 96 | 1/1 | 1.000 | 4.0 | 0 | 0 |
| calibration | order | 2 | DIRECT | 1024 | 1/1 | 1.000 | 4.0 | 0 | 0 |
| calibration | order | 3 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| calibration | order | 3 | COT | 1024 | 1/1 | 1.000 | 273.0 | 0 | 0 |
| calibration | order | 3 | DIRECT | 96 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| calibration | order | 3 | DIRECT | 1024 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| calibration | order | 4 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| calibration | order | 4 | COT | 1024 | 1/1 | 0.000 | 300.0 | 0 | 0 |
| calibration | order | 4 | DIRECT | 96 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| calibration | order | 4 | DIRECT | 1024 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| train | arith | 1 | COT | 96 | 1/1 | 1.000 | 52.0 | 0 | 0 |
| train | arith | 1 | COT | 1024 | 1/1 | 1.000 | 52.0 | 0 | 0 |
| train | arith | 1 | DIRECT | 96 | 1/1 | 1.000 | 7.0 | 0 | 0 |
| train | arith | 1 | DIRECT | 1024 | 1/1 | 1.000 | 7.0 | 0 | 0 |
| train | arith | 2 | COT | 96 | 1/1 | 1.000 | 89.0 | 0 | 0 |
| train | arith | 2 | COT | 1024 | 1/1 | 1.000 | 89.0 | 0 | 0 |
| train | arith | 2 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | arith | 2 | DIRECT | 1024 | 1/1 | 1.000 | 104.0 | 0 | 0 |
| train | arith | 3 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | arith | 3 | COT | 1024 | 1/1 | 1.000 | 172.0 | 0 | 0 |
| train | arith | 3 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | arith | 3 | DIRECT | 1024 | 1/1 | 1.000 | 155.0 | 0 | 0 |
| train | arith | 4 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | arith | 4 | COT | 1024 | 1/1 | 0.000 | 289.0 | 0 | 0 |
| train | arith | 4 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | arith | 4 | DIRECT | 1024 | 1/1 | 0.000 | 336.0 | 0 | 0 |
| train | g24 | 1 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | g24 | 1 | COT | 1024 | 1/1 | 1.000 | 288.0 | 0 | 0 |
| train | g24 | 1 | DIRECT | 96 | 1/1 | 0.000 | 19.0 | 0 | 0 |
| train | g24 | 1 | DIRECT | 1024 | 1/1 | 0.000 | 19.0 | 0 | 0 |
| train | g24 | 2 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | g24 | 2 | COT | 1024 | 1/1 | 0.000 | 1024.0 | 1 | 1 |
| train | g24 | 2 | DIRECT | 96 | 1/1 | 0.000 | 22.0 | 0 | 0 |
| train | g24 | 2 | DIRECT | 1024 | 1/1 | 0.000 | 22.0 | 0 | 0 |
| train | g24 | 3 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | g24 | 3 | COT | 1024 | 1/1 | 1.000 | 126.0 | 0 | 0 |
| train | g24 | 3 | DIRECT | 96 | 1/1 | 0.000 | 20.0 | 0 | 0 |
| train | g24 | 3 | DIRECT | 1024 | 1/1 | 0.000 | 20.0 | 0 | 0 |
| train | g24 | 4 | COT | 96 | 1/1 | 0.000 | 96.0 | 1 | 1 |
| train | g24 | 4 | COT | 1024 | 1/1 | 1.000 | 118.0 | 0 | 0 |
| train | g24 | 4 | DIRECT | 96 | 1/1 | 0.000 | 17.0 | 0 | 0 |
| train | g24 | 4 | DIRECT | 1024 | 1/1 | 0.000 | 17.0 | 0 | 0 |
| train | order | 1 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| train | order | 1 | COT | 1024 | 1/1 | 1.000 | 110.0 | 0 | 0 |
| train | order | 1 | DIRECT | 96 | 1/1 | 1.000 | 4.0 | 0 | 0 |
| train | order | 1 | DIRECT | 1024 | 1/1 | 1.000 | 4.0 | 0 | 0 |
| train | order | 2 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| train | order | 2 | COT | 1024 | 1/1 | 1.000 | 177.0 | 0 | 0 |
| train | order | 2 | DIRECT | 96 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| train | order | 2 | DIRECT | 1024 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| train | order | 3 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| train | order | 3 | COT | 1024 | 1/1 | 0.000 | 248.0 | 0 | 0 |
| train | order | 3 | DIRECT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| train | order | 3 | DIRECT | 1024 | 1/1 | 1.000 | 634.0 | 0 | 0 |
| train | order | 4 | COT | 96 | 1/1 | 0.000 | 96.0 | 0 | 1 |
| train | order | 4 | COT | 1024 | 1/1 | 0.000 | 473.0 | 0 | 0 |
| train | order | 4 | DIRECT | 96 | 1/1 | 0.000 | 4.0 | 0 | 0 |
| train | order | 4 | DIRECT | 1024 | 1/1 | 0.000 | 4.0 | 0 | 0 |

Token scope: generated tokens summed over all calls; prompt tokens recorded separately.
Human/source review and pilot configuration review remain pending. Parameters are not frozen. Stage 0 is unchanged.
