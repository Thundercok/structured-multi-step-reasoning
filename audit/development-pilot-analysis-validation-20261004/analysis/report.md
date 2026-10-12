# Paired development pilot diagnostics

Evidence: **synthetic_pilot_smoke**

Exposed development data, one generation seed, two fixed strategies and two per-call caps. Human/publication review remains pending.
Synthetic inputs validate software only. Measured generated tokens exclude prefill/full inference cost; strategy duration excludes model loading and online controller scheduling.
DIRECT uses a Vietnamese suffix and CoT an English suffix. Strategy differences include prompt-language effects; matched caps do not establish instruction-only causality.
Questions/variants and groups are counted separately. No significance, superiority, calibrated difficulty or parameter freeze is inferred.

| Family | Cap/call | Strategy | Correct/items | Groups | Mean generated tokens | Mean prompt tokens | Parse failures | Length stops |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: |
| all | 96 | DIRECT | 0/48 | 24 | 96.0 | 1.0 | 48 | 48 |
| all | 96 | COT | 0/48 | 24 | 96.0 | 1.0 | 48 | 48 |
| all | 1024 | DIRECT | 29/48 | 24 | 120.0 | 1.0 | 0 | 0 |
| all | 1024 | COT | 28/48 | 24 | 300.0 | 1.0 | 0 | 0 |
| pal | 96 | DIRECT | 0/16 | 8 | 96.0 | 1.0 | 16 | 16 |
| pal | 96 | COT | 0/16 | 8 | 96.0 | 1.0 | 16 | 16 |
| pal | 1024 | DIRECT | 10/16 | 8 | 120.0 | 1.0 | 0 | 0 |
| pal | 1024 | COT | 12/16 | 8 | 300.0 | 1.0 | 0 | 0 |
| plain | 96 | DIRECT | 0/16 | 8 | 96.0 | 1.0 | 16 | 16 |
| plain | 96 | COT | 0/16 | 8 | 96.0 | 1.0 | 16 | 16 |
| plain | 1024 | DIRECT | 10/16 | 8 | 120.0 | 1.0 | 0 | 0 |
| plain | 1024 | COT | 8/16 | 8 | 300.0 | 1.0 | 0 | 0 |
| react | 96 | DIRECT | 0/16 | 8 | 96.0 | 1.0 | 16 | 16 |
| react | 96 | COT | 0/16 | 8 | 96.0 | 1.0 | 16 | 16 |
| react | 1024 | DIRECT | 9/16 | 8 | 120.0 | 1.0 | 0 | 0 |
| react | 1024 | COT | 8/16 | 8 | 300.0 | 1.0 | 0 | 0 |

## Paired outcomes at the same cap

Became correct/incorrect describe switching from DIRECT to CoT on the same question.

| Family | Cap/call | Items | Both correct | Became correct | Became incorrect | Both incorrect | Mean token change |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| all | 96 | 48 | 0 | 0 | 0 | 48 | 0.0 |
| all | 1024 | 48 | 18 | 10 | 11 | 9 | 180.0 |
| pal | 96 | 16 | 0 | 0 | 0 | 16 | 0.0 |
| pal | 1024 | 16 | 9 | 3 | 1 | 3 | 180.0 |
| plain | 96 | 16 | 0 | 0 | 0 | 16 | 0.0 |
| plain | 1024 | 16 | 5 | 3 | 5 | 3 | 180.0 |
| react | 96 | 16 | 0 | 0 | 0 | 16 | 0.0 |
| react | 1024 | 16 | 4 | 4 | 5 | 3 | 180.0 |

## Increasing the cap within each strategy

| Family | Strategy | Items | Became correct | Became incorrect | Mean token change |
| --- | --- | ---: | ---: | ---: | ---: |
| all | DIRECT | 48 | 29 | 0 | 24.0 |
| all | COT | 48 | 28 | 0 | 204.0 |
| pal | DIRECT | 16 | 10 | 0 | 24.0 |
| pal | COT | 16 | 12 | 0 | 204.0 |
| plain | DIRECT | 16 | 10 | 0 | 24.0 |
| plain | COT | 16 | 8 | 0 | 204.0 |
| react | DIRECT | 16 | 9 | 0 | 24.0 |
| react | COT | 16 | 8 | 0 | 204.0 |
