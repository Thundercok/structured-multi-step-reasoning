# Agreement reanalysis — EXPLORATORY

Review status: software/statistic correction; publication and prereg interpretation pending.

- EXPLORATORY reanalysis of exposed gen02_tune; its legacy test label does not make this a confirmatory test.
- Point estimates and paired cluster intervals both use mean-repeat OOF AUROC. Intervals condition on fixed predictions; folds/models are not refitted in bootstrap.
- Four signals per evaluable family have unadjusted intervals. An individual diagnostic threshold is not a global preregistration pass or evidence of VGC superiority.
- Historical prereg requires arith AND order, but its final verdict mentions order alone. This conflict remains review-pending; arith's single-class target is not evaluable.
- All gate signals predict PAL-v2 parsed-answer correctness. The plurality signal is an auxiliary predictor, not a separate plurality-correctness target.
- g24 agreement is validity-assisted: check24 maps different valid expressions to one key using question numbers. It is not pure answer identity or verifier-free agreement.
- Four-arm n_agree consumes historical PAL, CoT, candidate-selection and SC outputs (nominal collector configuration: 1+1+4+5 calls); no free or cheap online gate is established.
- Legacy candidate selection (labelled ToT) retains only one branch's prompt-token count; other branch and selector inputs are missing. All invoked arm fields are summed, but full per-call cost cannot be recovered.
- Parsed answers are retrospectively rescored. Candidate-selection and selected-SC termination cannot be fully reconstructed; this is not a corrected fresh model measurement.
- Replay G1/G2 use only PAL/CoT pair agreement, not four-arm n_agree. Their failure does not rule out every agreement policy or establish a verifier as the only solution.
- Agree-and-wrong lists demonstrate shared incorrect parsed answers; causal explanations require independent review.
- No new generation, GPU, model loading, prospective-test evaluation or Stage 0 change occurs.

## Gate diagnostics

| Family | Signal predicting PAL correctness | Mean repeat baseline AUROC | Mean repeat signal AUROC | Δ AUROC | Paired 95% CI, SAME statistic | Unadjusted diagnostic threshold |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **arith (N=40)** | Baseline | N/A | N/A | N/A | N/A | N/A (Single-class PAL target (40 positive, 0 negative)) |
| arith | + agree(PAL,COT) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (40 positive, 0 negative)) |
| arith | + agree(PAL,TOT) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (40 positive, 0 negative)) |
| arith | + n_agree (PAL) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (40 positive, 0 negative)) |
| arith | + n_agree (plurality) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (40 positive, 0 negative)) |
| order | + agree(PAL,COT) | 0.7175 | 0.7805 | +0.0630 | [-0.0629, +0.1928] | NOT MET |
| order | + agree(PAL,TOT) | 0.7175 | 0.8370 | +0.1195 | [-0.0253, +0.2758] | NOT MET |
| order | + n_agree (PAL) | 0.7175 | 0.8582 | +0.1407 | [+0.0221, +0.2775] | MET (exploratory only) |
| order | + n_agree (plurality) | 0.7175 | 0.7905 | +0.0730 | [-0.0235, +0.1855] | NOT MET |
| **g24 (N=29)** | Baseline | N/A | N/A | N/A | N/A | N/A (Single-class PAL target (0 positive, 29 negative)) |
| g24 | + agree(PAL,COT) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (0 positive, 29 negative)) |
| g24 | + agree(PAL,TOT) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (0 positive, 29 negative)) |
| g24 | + n_agree (PAL) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (0 positive, 29 negative)) |
| g24 | + n_agree (plurality) | N/A | N/A | N/A | N/A | NOT EVALUABLE (Single-class PAL target (0 positive, 29 negative)) |
| pooled | + agree(PAL,COT) | 0.9767 | 0.9807 | +0.0040 | [-0.0109, +0.0202] | NOT MET |
| pooled | + agree(PAL,TOT) | 0.9767 | 0.9870 | +0.0104 | [-0.0047, +0.0311] | NOT MET |
| pooled | + n_agree (PAL) | 0.9767 | 0.9899 | +0.0132 | [+0.0014, +0.0320] | NOT MET |
| pooled | + n_agree (plurality) | 0.9767 | 0.9836 | +0.0070 | [-0.0026, +0.0200] | NOT MET |

## Conditional precision

| Family | Signal | Agreed Items / Total | Correct When Agreed | P(Correct \| Agree) |
| :--- | :--- | :---: | :---: | :---: |
| arith | agree(PAL-v2,COT) | 30/40 (75.0%) | 30/30 | 100.0% |
| arith | agree(PAL-v2,ToT) | 30/40 (75.0%) | 30/30 | 100.0% |
| arith | pal_agree>=2 | 30/40 (75.0%) | 30/30 | 100.0% |
| arith | pal_agree>=3 | 30/40 (75.0%) | 30/30 | 100.0% |
| arith | pal_agree==4 | 30/40 (75.0%) | 30/30 | 100.0% |
| arith | plurality_agree>=2 | 37/40 (92.5%) | 30/37 | 81.1% |
| arith | plurality_agree>=3 | 33/40 (82.5%) | 30/33 | 90.9% |
| arith | plurality_agree==4 | 30/40 (75.0%) | 30/30 | 100.0% |
| order | agree(PAL-v2,COT) | 14/31 (45.2%) | 13/14 | 92.9% |
| order | agree(PAL-v2,ToT) | 17/31 (54.8%) | 16/17 | 94.1% |
| order | pal_agree>=2 | 18/31 (58.1%) | 17/18 | 94.4% |
| order | pal_agree>=3 | 16/31 (51.6%) | 15/16 | 93.8% |
| order | pal_agree==4 | 9/31 (29.0%) | 9/9 | 100.0% |
| order | plurality_agree>=2 | 22/31 (71.0%) | 18/22 | 81.8% |
| order | plurality_agree>=3 | 18/31 (58.1%) | 15/18 | 83.3% |
| order | plurality_agree==4 | 9/31 (29.0%) | 9/9 | 100.0% |
| g24 | agree(PAL-v2,COT) | 0/29 (0.0%) | 0/0 | N/A (no agreements) |
| g24 | agree(PAL-v2,ToT) | 0/29 (0.0%) | 0/0 | N/A (no agreements) |
| g24 | pal_agree>=2 | 0/29 (0.0%) | 0/0 | N/A (no agreements) |
| g24 | pal_agree>=3 | 0/29 (0.0%) | 0/0 | N/A (no agreements) |
| g24 | pal_agree==4 | 0/29 (0.0%) | 0/0 | N/A (no agreements) |
| g24 | plurality_agree>=2 | 17/29 (58.6%) | 16/17 | 94.1% |
| g24 | plurality_agree>=3 | 12/29 (41.4%) | 12/12 | 100.0% |
| g24 | plurality_agree==4 | 0/29 (0.0%) | 0/0 | N/A (no agreements) |
| pooled | agree(PAL-v2,COT) | 44/100 (44.0%) | 43/44 | 97.7% |
| pooled | agree(PAL-v2,ToT) | 47/100 (47.0%) | 46/47 | 97.9% |
| pooled | pal_agree>=2 | 48/100 (48.0%) | 47/48 | 97.9% |
| pooled | pal_agree>=3 | 46/100 (46.0%) | 45/46 | 97.8% |
| pooled | pal_agree==4 | 39/100 (39.0%) | 39/39 | 100.0% |
| pooled | plurality_agree>=2 | 76/100 (76.0%) | 64/76 | 84.2% |
| pooled | plurality_agree>=3 | 63/100 (63.0%) | 57/63 | 90.5% |
| pooled | plurality_agree==4 | 39/100 (39.0%) | 39/39 | 100.0% |

## Shared incorrect answers (not causal diagnoses)

| Item ID | Family | Level | Signal | Accepted Answer | Gold Answer | Arms (PAL-v2 / COT / candidate selection / SC) | Observation, NOT causal diagnosis |
| :--- | :--- | :---: | :--- | :---: | :---: | :--- | :--- |
| `arith_0026_en_orig` | arith | 4 | plurality_agree>=2 | **25767632** | **25842332** | PAL: 25842332, COT: 25767632, ToT: 25767632, SC: 25767632 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0028_en_orig` | arith | 4 | plurality_agree>=2 | **114176565** | **113731565** | PAL: 113731565, COT: 114176565, ToT: 114176565, SC: 114176565 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0031_en_orig` | arith | 4 | plurality_agree>=2 | **920440658069354** | **917720389173354** | PAL: 917720389173354, COT: 920440658069354, ToT: 920440658070354, SC: 920440658069354 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0032_en_orig` | arith | 5 | plurality_agree>=2 | **49518909** | **49835709** | PAL: 49835709, COT: 49518909, ToT: 49569464.666..., SC: 49518909 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0034_en_orig` | arith | 5 | plurality_agree>=2 | **96472785662** | **96376801762** | PAL: 96376801762, COT: 96472785662, ToT: 96472785662, SC: 96431624762 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0036_en_orig` | arith | 5 | plurality_agree>=2 | **686316062652668** | **687726209109668** | PAL: 687726209109668, COT: 686316062652668, ToT: 687316061772668, SC: 686316062652668 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0039_en_orig` | arith | 5 | plurality_agree>=2 | **2812328** | **2822328** | PAL: 2822328, COT: 2812328, ToT: 2812328, SC: 2812328 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0026_en_orig` | arith | 4 | plurality_agree>=3 | **25767632** | **25842332** | PAL: 25842332, COT: 25767632, ToT: 25767632, SC: 25767632 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0028_en_orig` | arith | 4 | plurality_agree>=3 | **114176565** | **113731565** | PAL: 113731565, COT: 114176565, ToT: 114176565, SC: 114176565 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `arith_0039_en_orig` | arith | 5 | plurality_agree>=3 | **2812328** | **2822328** | PAL: 2822328, COT: 2812328, ToT: 2812328, SC: 2812328 | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0010_en_orig` | order | 2 | agree(PAL-v2,COT) | **alice** | **grace** | PAL: alice, COT: alice, ToT: alice, SC: bob | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0010_en_orig` | order | 2 | agree(PAL-v2,ToT) | **alice** | **grace** | PAL: alice, COT: alice, ToT: alice, SC: bob | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0010_en_orig` | order | 2 | pal_agree>=2 | **alice** | **grace** | PAL: alice, COT: alice, ToT: alice, SC: bob | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0010_en_orig` | order | 2 | pal_agree>=3 | **alice** | **grace** | PAL: alice, COT: alice, ToT: alice, SC: bob | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0008_en_orig` | order | 2 | plurality_agree>=2 | **carol** | **dave** | PAL: grace, COT: carol, ToT: carol, SC: carol | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0009_en_orig` | order | 2 | plurality_agree>=2 | **dave** | **grace** | PAL: grace, COT: dave, ToT: bob, SC: dave | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0010_en_orig` | order | 2 | plurality_agree>=2 | **alice** | **grace** | PAL: alice, COT: alice, ToT: alice, SC: bob | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0019_en_orig` | order | 3 | plurality_agree>=2 | **alice** | **heidi** | PAL: break, COT: alice, ToT: alice, SC: alice | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0008_en_orig` | order | 2 | plurality_agree>=3 | **carol** | **dave** | PAL: grace, COT: carol, ToT: carol, SC: carol | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0010_en_orig` | order | 2 | plurality_agree>=3 | **alice** | **grace** | PAL: alice, COT: alice, ToT: alice, SC: bob | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `order_0019_en_orig` | order | 3 | plurality_agree>=3 | **alice** | **heidi** | PAL: break, COT: alice, ToT: alice, SC: alice | Shared incorrect parsed answer; underlying cause not independently reviewed |
| `g24_0031_en_orig` | g24 | 4 | plurality_agree>=2 | **(11+1)*(3-1)** | **__VALID_24__** | PAL: break, COT: 20., ToT: (11+1)*(3-1), SC: (11+1)*(3-1) | Shared incorrect parsed answer; underlying cause not independently reviewed |

## Retrospective policy replay — legacy token proxy

| Family | Policy | Retrospective accuracy (corr/n) | 95% Cluster CI (Acc) | Mean LEGACY token proxy | 95% Cluster CI (Proxy) | Escalation Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| arith | always-PAL-v2 | 100.0% (40/40) | [100.0%, 100.0%] | 229.2 | [207.8, 249.2] | 0.0% (0/40) |
| arith | always-ToT | 75.0% (30/40) | [60.0%, 87.5%] | 688.5 | [571.4, 820.7] | 0.0% (0/40) |
| arith | W (exec fail -> ToT) | 100.0% (40/40) | [100.0%, 100.0%] | 229.2 | [209.0, 249.4] | 0.0% (0/40) |
| arith | G1 (PAL+COT agree -> PAL, else ToT) | 75.0% (30/40) | [62.4%, 87.5%] | 824.0 | [633.2, 1037.7] | 25.0% (10/40) |
| arith | G2 (PAL -> if fail ToT else COT agree) | 75.0% (30/40) | [62.5%, 87.5%] | 824.0 | [624.2, 1029.8] | 25.0% (10/40) |
| order | always-PAL-v2 | 64.5% (20/31) | [48.4%, 80.6%] | 474.3 | [440.6, 508.8] | 0.0% (0/31) |
| order | always-ToT | 67.7% (21/31) | [51.6%, 83.9%] | 1894.0 | [1639.9, 2146.7] | 0.0% (0/31) |
| order | W (exec fail -> ToT) | 74.2% (23/31) | [58.1%, 90.3%] | 916.0 | [598.5, 1285.4] | 19.4% (6/31) |
| order | G1 (PAL+COT agree -> PAL, else ToT) | 71.0% (22/31) | [54.8%, 87.1%] | 2406.1 | [1896.4, 2943.7] | 54.8% (17/31) |
| order | G2 (PAL -> if fail ToT else COT agree) | 71.0% (22/31) | [54.8%, 87.1%] | 2228.5 | [1761.3, 2721.4] | 54.8% (17/31) |
| g24 | always-PAL-v2 | 0.0% (0/29) | [0.0%, 0.0%] | 474.8 | [432.4, 517.7] | 0.0% (0/29) |
| g24 | always-ToT | 58.6% (17/29) | [41.4%, 75.9%] | 1446.8 | [1210.2, 1692.4] | 0.0% (0/29) |
| g24 | W (exec fail -> ToT) | 58.6% (17/29) | [41.4%, 75.9%] | 1921.6 | [1685.8, 2166.4] | 100.0% (29/29) |
| g24 | G1 (PAL+COT agree -> PAL, else ToT) | 58.6% (17/29) | [41.4%, 75.9%] | 2549.4 | [2182.4, 2921.3] | 100.0% (29/29) |
| g24 | G2 (PAL -> if fail ToT else COT agree) | 58.6% (17/29) | [41.4%, 75.9%] | 1921.6 | [1669.7, 2170.8] | 100.0% (29/29) |
| pooled | always-PAL-v2 | 60.0% (60/100) | [50.0%, 69.0%] | 376.4 | [347.4, 406.5] | 0.0% (0/100) |
| pooled | always-ToT | 68.0% (68/100) | [59.0%, 77.0%] | 1282.1 | [1132.9, 1425.4] | 0.0% (0/100) |
| pooled | W (exec fail -> ToT) | 80.0% (80/100) | [72.0%, 88.0%] | 932.9 | [758.9, 1120.8] | 35.0% (35/100) |
| pooled | G1 (PAL+COT agree -> PAL, else ToT) | 69.0% (69/100) | [60.0%, 78.0%] | 1814.8 | [1549.0, 2085.2] | 56.0% (56/100) |
| pooled | G2 (PAL -> if fail ToT else COT agree) | 69.0% (69/100) | [60.0%, 78.0%] | 1577.7 | [1351.9, 1790.3] | 56.0% (56/100) |

