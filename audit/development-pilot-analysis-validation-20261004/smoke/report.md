# Development-only research pilot

Evidence: **synthetic_pilot_smoke**

Fixed-strategy diagnostics on exposed development groups. No held-out evaluation or policy fitting.
Synthetic smoke traces validate software only; they provide no model-quality evidence.
Budgets cap each generation call; multi-call strategies can consume more total tokens. ReAct also retains its 200-token per-turn ceiling.
Timings are measured strategy-call duration (Python only for smoke), not online controller latency. Prompt counts are separate from generated-token costs.
Cells count questions and original groups separately. Variants and budget repetitions are not independent problems. No confidence intervals or superiority claims are inferred.

| Split | Family | Level | Strategy | Cap/call | Items/groups | Accuracy | Mean generated tokens | Parse failures | Length stops |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: |
| calibration | pal | 1 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 1 | COT | 1024 | 2/1 | 0.000 | 300.0 | 0 | 0 |
| calibration | pal | 1 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 1 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| calibration | pal | 2 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 2 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| calibration | pal | 2 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 2 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| calibration | pal | 3 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 3 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| calibration | pal | 3 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 3 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| calibration | pal | 4 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 4 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| calibration | pal | 4 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | pal | 4 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| calibration | plain | 1 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 1 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| calibration | plain | 1 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 1 | DIRECT | 1024 | 2/1 | 0.000 | 120.0 | 0 | 0 |
| calibration | plain | 2 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 2 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| calibration | plain | 2 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 2 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| calibration | plain | 3 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 3 | COT | 1024 | 2/1 | 0.000 | 300.0 | 0 | 0 |
| calibration | plain | 3 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 3 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| calibration | plain | 4 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 4 | COT | 1024 | 2/1 | 0.000 | 300.0 | 0 | 0 |
| calibration | plain | 4 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | plain | 4 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| calibration | react | 1 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 1 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| calibration | react | 1 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 1 | DIRECT | 1024 | 2/1 | 0.000 | 120.0 | 0 | 0 |
| calibration | react | 2 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 2 | COT | 1024 | 2/1 | 0.000 | 300.0 | 0 | 0 |
| calibration | react | 2 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 2 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| calibration | react | 3 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 3 | COT | 1024 | 2/1 | 0.000 | 300.0 | 0 | 0 |
| calibration | react | 3 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 3 | DIRECT | 1024 | 2/1 | 0.000 | 120.0 | 0 | 0 |
| calibration | react | 4 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 4 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| calibration | react | 4 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| calibration | react | 4 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| train | pal | 1 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 1 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| train | pal | 1 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 1 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| train | pal | 2 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 2 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| train | pal | 2 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 2 | DIRECT | 1024 | 2/1 | 0.000 | 120.0 | 0 | 0 |
| train | pal | 3 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 3 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| train | pal | 3 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 3 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| train | pal | 4 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 4 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| train | pal | 4 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | pal | 4 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| train | plain | 1 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 1 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| train | plain | 1 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 1 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| train | plain | 2 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 2 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| train | plain | 2 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 2 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| train | plain | 3 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 3 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| train | plain | 3 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 3 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| train | plain | 4 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 4 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| train | plain | 4 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | plain | 4 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| train | react | 1 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 1 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| train | react | 1 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 1 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| train | react | 2 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 2 | COT | 1024 | 2/1 | 0.500 | 300.0 | 0 | 0 |
| train | react | 2 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 2 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |
| train | react | 3 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 3 | COT | 1024 | 2/1 | 1.000 | 300.0 | 0 | 0 |
| train | react | 3 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 3 | DIRECT | 1024 | 2/1 | 0.500 | 120.0 | 0 | 0 |
| train | react | 4 | COT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 4 | COT | 1024 | 2/1 | 0.000 | 300.0 | 0 | 0 |
| train | react | 4 | DIRECT | 96 | 2/1 | 0.000 | 96.0 | 2 | 2 |
| train | react | 4 | DIRECT | 1024 | 2/1 | 1.000 | 120.0 | 0 | 0 |

Token scope: synthetic token units.
Human/source review and pilot configuration review remain pending. Parameters are not frozen. Stage 0 is unchanged.
