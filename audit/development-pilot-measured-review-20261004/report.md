# Paired development pilot diagnostics

Evidence: **measured_development_pilot**

Exposed development data, one generation seed, two fixed strategies and two per-call caps. Human/publication review remains pending.
Synthetic inputs validate software only. Measured generated tokens exclude prefill/full inference cost; strategy duration excludes model loading and online controller scheduling.
DIRECT uses a Vietnamese suffix and CoT an English suffix. Strategy differences include prompt-language effects; matched caps do not establish instruction-only causality.
Questions/variants and groups are counted separately. No significance, superiority, calibrated difficulty or parameter freeze is inferred.

| Family | Cap/call | Strategy | Correct/items | Groups | Mean generated tokens | Mean prompt tokens | Parse failures | Length stops |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| all | 96 | DIRECT | 5/24 | 24 | 38.7 | 113.8 | 5 | 7 |
| all | 96 | COT | 5/24 | 24 | 90.3 | 95.8 | 12 | 19 |
| all | 1024 | DIRECT | 10/24 | 24 | 116.8 | 113.8 | 0 | 1 |
| all | 1024 | COT | 15/24 | 24 | 324.9 | 95.8 | 4 | 4 |
| arith | 96 | DIRECT | 2/8 | 8 | 80.1 | 131.9 | 5 | 6 |
| arith | 96 | COT | 3/8 | 8 | 82.5 | 113.9 | 5 | 5 |
| arith | 1024 | DIRECT | 6/8 | 8 | 247.1 | 131.9 | 0 | 1 |
| arith | 1024 | COT | 6/8 | 8 | 151.8 | 113.9 | 0 | 0 |
| g24 | 96 | DIRECT | 0/8 | 8 | 20.5 | 95.6 | 0 | 0 |
| g24 | 96 | COT | 1/8 | 8 | 92.9 | 77.6 | 7 | 7 |
| g24 | 1024 | DIRECT | 0/8 | 8 | 20.5 | 95.6 | 0 | 0 |
| g24 | 1024 | COT | 4/8 | 8 | 587.4 | 77.6 | 4 | 4 |
| order | 96 | DIRECT | 3/8 | 8 | 15.5 | 113.8 | 0 | 1 |
| order | 96 | COT | 1/8 | 8 | 95.6 | 95.8 | 0 | 7 |
| order | 1024 | DIRECT | 4/8 | 8 | 82.8 | 113.8 | 0 | 0 |
| order | 1024 | COT | 5/8 | 8 | 235.5 | 95.8 | 0 | 0 |

## Paired outcomes at the same cap

Became correct/incorrect describe switching from DIRECT to CoT on the same question.

| Family | Cap/call | Items | Both correct | Became correct | Became incorrect | Both incorrect | Mean token change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 96 | 24 | 3 | 2 | 2 | 17 | 51.6 |
| all | 1024 | 24 | 9 | 6 | 1 | 8 | 208.1 |
| arith | 96 | 8 | 2 | 1 | 0 | 5 | 2.4 |
| arith | 1024 | 8 | 6 | 0 | 0 | 2 | -95.4 |
| g24 | 96 | 8 | 0 | 1 | 0 | 7 | 72.4 |
| g24 | 1024 | 8 | 0 | 4 | 0 | 4 | 566.9 |
| order | 96 | 8 | 1 | 0 | 2 | 5 | 80.1 |
| order | 1024 | 8 | 3 | 2 | 1 | 2 | 152.8 |

## Increasing the cap within each strategy

| Family | Strategy | Items | Became correct | Became incorrect | Mean token change |
| --- | --- | ---: | ---: | ---: | ---: |
| all | DIRECT | 24 | 5 | 0 | 78.1 |
| all | COT | 24 | 10 | 0 | 234.5 |
| arith | DIRECT | 8 | 4 | 0 | 167.0 |
| arith | COT | 8 | 3 | 0 | 69.2 |
| g24 | DIRECT | 8 | 0 | 0 | 0.0 |
| g24 | COT | 8 | 3 | 0 | 494.5 |
| order | DIRECT | 8 | 1 | 0 | 67.2 |
| order | COT | 8 | 4 | 0 | 139.9 |
