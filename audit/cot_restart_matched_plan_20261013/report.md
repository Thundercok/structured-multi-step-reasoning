# Proposed A/F/CONT development batch

Prepared with a tokenizer only; real generation remains pending explicit budget approval.

- Same 12 exposed-development questions; F fixed by the user at q=0.50.
- 36 attempted calls, one fresh draw per item/arm; no new base calls.
- Completion ceiling: 72,996 sampled tokens including EOS.
- Second-prompt tokens: 14,125; total ceiling: 87,121.
- Largest per-call prompt+completion allowance: 2,739 tokens.
- Refuse new calls after 8 hours of active collection; failed attempts consume the 36-call allowance.
- M uses W=2048, per-item L_i and offsets -8/0/+8; every required cap is collected.
- D uses proposed T*=2560 for w=0 and w=1. The w=1 feasibility floor is 2359.

A flat 2,056-token collection limit cannot cover all w=1 deployment cells at a common T.
Instead, each call collects only the maximum completion required by M+8, D(w=0) and D(w=1).
This changes the collection allowance, while primary M remains at W=2,048.

Legacy base counts remain a labeled cost component with unverified EOS convention.
D is conditional on those logged counts, not a fully audited inference-cost measurement.
No lambda/practical threshold or GO/NO-GO decision is fitted or enabled in this 12-item diagnostic.
No learned locator, held-out claim, deployment efficiency claim or Stage 0 change.

| Item | Arm | Prompt | Collected cap | M | D w=0 | D w=1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| arith_0027_en_orig | A | 166 | 2415 | 1748 | 2415 | 2083 |
| arith_0027_en_orig | F | 233 | 2415 | 1748 | 2415 | 2016 |
| arith_0027_en_orig | CONT | 300 | 2415 | 1748 | 2415 | 1949 |
| arith_0039_en_orig | A | 191 | 2273 | 1582 | 2273 | 1891 |
| arith_0039_en_orig | F | 338 | 2273 | 1582 | 2273 | 1744 |
| arith_0039_en_orig | CONT | 466 | 2273 | 1582 | 2273 | 1616 |
| arith_0023_en_orig | A | 140 | 2458 | 1816 | 2458 | 2178 |
| arith_0023_en_orig | F | 192 | 2458 | 1816 | 2458 | 2126 |
| arith_0023_en_orig | CONT | 232 | 2458 | 1816 | 2458 | 2086 |
| arith_0032_en_orig | A | 187 | 2376 | 1690 | 2376 | 2002 |
| arith_0032_en_orig | F | 273 | 2376 | 1690 | 2376 | 1916 |
| arith_0032_en_orig | CONT | 358 | 2376 | 1690 | 2376 | 1831 |
| order_0012_en_orig | A | 116 | 1973 | 1350 | 1973 | 1741 |
| order_0012_en_orig | F | 411 | 1973 | 1350 | 1973 | 1446 |
| order_0012_en_orig | CONT | 698 | 1973 | 1350 | 1973 | 1159 |
| order_0004_en_orig | A | 127 | 1822 | 1188 | 1822 | 1568 |
| order_0004_en_orig | F | 491 | 1822 | 1188 | 1822 | 1204 |
| order_0004_en_orig | CONT | 860 | 1822 | 1188 | 1822 | 835 |
| order_0006_en_orig | A | 107 | 1894 | 1281 | 1894 | 1680 |
| order_0006_en_orig | F | 420 | 1894 | 1281 | 1894 | 1367 |
| order_0006_en_orig | CONT | 767 | 1894 | 1281 | 1894 | 1020 |
| order_0027_en_orig | A | 155 | 1536 | 869 | 1536 | 1226 |
| order_0027_en_orig | F | 673 | 1536 | 869 | 1536 | 708 |
| order_0027_en_orig | CONT | 1179 | 1536 | 869 | 1536 | 202 |
| g24_0014_en_orig | A | 93 | 1536 | 931 | 1536 | 1350 |
| g24_0014_en_orig | F | 601 | 1536 | 931 | 1536 | 842 |
| g24_0014_en_orig | CONT | 1117 | 1536 | 931 | 1536 | 326 |
| g24_0028_en_orig | A | 95 | 2297 | 1709 | 2297 | 2107 |
| g24_0028_en_orig | F | 209 | 2297 | 1709 | 2297 | 1993 |
| g24_0028_en_orig | CONT | 339 | 2297 | 1709 | 2297 | 1863 |
| g24_0023_en_orig | A | 94 | 1536 | 930 | 1536 | 1348 |
| g24_0023_en_orig | F | 599 | 1536 | 930 | 1536 | 843 |
| g24_0023_en_orig | CONT | 1118 | 1536 | 930 | 1536 | 324 |
| g24_0018_en_orig | A | 95 | 2216 | 1626 | 2216 | 2026 |
| g24_0018_en_orig | F | 263 | 2216 | 1626 | 2216 | 1858 |
| g24_0018_en_orig | CONT | 422 | 2216 | 1626 | 2216 | 1699 |
