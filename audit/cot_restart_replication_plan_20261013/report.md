# Second matched A/F/CONT draw: frozen development plan

Status: prepared. No real-model calls were made during preparation.
This plan copies verified first-draw prompts/IDs/caps and freezes new draw seeds.

- 12 exposed questions, 12 original groups, q=0.50.
- Draw index 1; base seed 42; seed = f(item, arm, call=1), independent of budget.
- All 36 seeds are distinct and disjoint from the first draw's seed set.
- At most 36 attempted calls; failed attempts consume their allowance.
- Completion ceiling: 72,996 sampled tokens including EOS.
- Prompt allowance: 14,125; combined ceiling: 87,121 tokens.
- Largest per-call prompt+completion allowance: 2,739 tokens.
- Refuse a new call after eight active hours; this is not a mid-call timeout.
- M: W=2048, same per-item caps and -8/0/+8 sensitivity. D: T*=2560, w=0/1.
- Model snapshot, sampling, prompt order, cache settings and generation source hashes are unchanged.

The first draw used approximately 32 minutes of active collection. That observation is
not a runtime guarantee or replay online-latency measurement. The exact token ceilings
above, rather than the first draw's observed completion length, bound the new run.

Freeze per-draw reporting and within-question averaging before paired group bootstrap
(2,000 samples, bootstrap seed 20261013). Two draws still contain 12 questions.
Do not apply a binary paired-table interval to fractional seed-averaged outcomes.
Sensitivity caps reuse each draw and remain descriptive. No fitted utility threshold
or formal superiority decision is introduced. D retains the historical base-count
EOS limitation. Stage 0 and publication review remain unchanged.

Plan SHA-256: `132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6`

| Item | Arm | First seed | New seed | Collected cap |
| --- | --- | ---: | ---: | ---: |
| arith_0027_en_orig | A | 571118698 | 3877319769 | 2415 |
| arith_0027_en_orig | F | 2058533090 | 574910181 | 2415 |
| arith_0027_en_orig | CONT | 3255916143 | 2459076420 | 2415 |
| arith_0039_en_orig | A | 1270983891 | 2065751461 | 2273 |
| arith_0039_en_orig | F | 4018069397 | 3087621275 | 2273 |
| arith_0039_en_orig | CONT | 3508648680 | 2700534107 | 2273 |
| arith_0023_en_orig | A | 3225049567 | 3801339378 | 2458 |
| arith_0023_en_orig | F | 3241412126 | 259578042 | 2458 |
| arith_0023_en_orig | CONT | 1986795888 | 4239445081 | 2458 |
| arith_0032_en_orig | A | 1300434272 | 2845257121 | 2376 |
| arith_0032_en_orig | F | 2473290153 | 1098753844 | 2376 |
| arith_0032_en_orig | CONT | 3255773980 | 1151856387 | 2376 |
| order_0012_en_orig | A | 2518905380 | 42997249 | 1973 |
| order_0012_en_orig | F | 2383683188 | 3252080043 | 1973 |
| order_0012_en_orig | CONT | 29674598 | 4221347406 | 1973 |
| order_0004_en_orig | A | 2004721328 | 3197470362 | 1822 |
| order_0004_en_orig | F | 1239523459 | 433200146 | 1822 |
| order_0004_en_orig | CONT | 455649004 | 1735041471 | 1822 |
| order_0006_en_orig | A | 2641392323 | 1133568190 | 1894 |
| order_0006_en_orig | F | 2829062713 | 3923539055 | 1894 |
| order_0006_en_orig | CONT | 2413364696 | 1305017233 | 1894 |
| order_0027_en_orig | A | 3498643699 | 780137728 | 1536 |
| order_0027_en_orig | F | 2495744574 | 1962602857 | 1536 |
| order_0027_en_orig | CONT | 700383253 | 3015695505 | 1536 |
| g24_0014_en_orig | A | 284252632 | 1727955083 | 1536 |
| g24_0014_en_orig | F | 1584148882 | 2812095567 | 1536 |
| g24_0014_en_orig | CONT | 2965107916 | 1870317795 | 1536 |
| g24_0028_en_orig | A | 1327054214 | 2846913276 | 2297 |
| g24_0028_en_orig | F | 2776142466 | 3150120670 | 2297 |
| g24_0028_en_orig | CONT | 1814638287 | 2863207726 | 2297 |
| g24_0023_en_orig | A | 2091000117 | 3583539301 | 1536 |
| g24_0023_en_orig | F | 4065309783 | 1201323190 | 1536 |
| g24_0023_en_orig | CONT | 2997787161 | 1261371566 | 1536 |
| g24_0018_en_orig | A | 3998555334 | 664138833 | 2216 |
| g24_0018_en_orig | F | 1598065515 | 1205288063 | 2216 |
| g24_0018_en_orig | CONT | 2644703470 | 104956769 | 2216 |
