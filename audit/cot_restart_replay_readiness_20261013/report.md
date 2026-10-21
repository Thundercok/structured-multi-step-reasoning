# CoT restart legacy token audit

Exposed development; tokenizer only, no model calls or downloads. Stage 0 unchanged.

- Completions: 136 (including smoke calls).
- Literal token-count matches: 59/136.
- EOS-adjusted token-count matches: 122/136.
- Text roundtrips: 136/136.
- T5 EOS-aware gate: FAIL.

The EOS adjustment assumes the installed MLX-LM 0.31.3 convention. The historical
backend version was not recorded. Matching counts and text would still not prove
original token identity. No reconstructed sequence is stored as original IDs.

Legacy arms remain at their collected caps. M/D paired replay is unavailable until
every compared arm has an accepted token record. An ID-bearing addendum alone does
not make the historical A/F arms eligible. +/-8 sensitivity cannot repair a failed T5.

| Journal key | Finish | Recorded | Visible re-encode | EOS adjustment |
| --- | --- | ---: | ---: | ---: |
| restart_call / arith_0027_en_orig / prefix_call / 6499de9eecea1cfa / 1024 | stop | 110 | 110 | 1 |
| restart_call / arith_0027_en_orig / prefix_call / 86577199ed68ff2d / 1024 | stop | 78 | 78 | 1 |
| restart_call / arith_0027_en_orig / prefix_call / 03ed8b3413ca84d0 / 1024 | stop | 42 | 42 | 1 |
| restart_call / arith_0027_en_orig / prefix_call / 6499de9eecea1cfa / 2048 | stop | 110 | 110 | 1 |
| restart_call / arith_0027_en_orig / prefix_call / 86577199ed68ff2d / 2048 | stop | 78 | 78 | 1 |
| restart_call / arith_0027_en_orig / prefix_call / 03ed8b3413ca84d0 / 2048 | stop | 42 | 42 | 1 |
| restart_call / arith_0039_en_orig / prefix_call / 569f447c4fbd8af6 / 1024 | stop | 69 | 67 | 1 |
| restart_call / arith_0039_en_orig / prefix_call / 569f447c4fbd8af6 / 2048 | stop | 69 | 67 | 1 |
| restart_call / arith_0023_en_orig / prefix_call / 754620374b52e3e3 / 1024 | stop | 50 | 50 | 1 |
| restart_call / arith_0023_en_orig / prefix_call / 754620374b52e3e3 / 2048 | stop | 50 | 50 | 1 |
| restart_call / g24_0014_en_orig / prefix_call / c9147571b4374d2f / 1024 | length | 423 | 422 | 0 |
| restart_call / g24_0014_en_orig / prefix_call / d2214bf7824b2d59 / 1024 | length | 160 | 159 | 0 |
| restart_call / g24_0014_en_orig / prefix_call / c9147571b4374d2f / 2048 | stop | 1296 | 1294 | 1 |
| restart_call / g24_0014_en_orig / prefix_call / d2214bf7824b2d59 / 2048 | length | 1184 | 1183 | 0 |
