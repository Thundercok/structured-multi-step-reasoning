Sweep P: gen02_tune, Qwen3-8B-4bit, DIRECT-v2 + COT, T=0. Committed before results were read.
Health (all): parsed-empty <= 2%; arith/order %length <= 5%.
arith, order PASS: >=2 levels with COT in [30%,85%], and COT(top level) < COT(lowest level).
g24 (COT only): report only; PASS if %length <= 30% and >=2 levels in [20%,85%].
Pre-decided fixes: arith >=85% at every level -> raise steps/digits; order >=85% everywhere -> new knob, not more runners;
g24 %length > 30% -> do not raise the cap, use g24 only for SC/ToT/PAL comparisons.
Any other change needs a new tag and a new rule file.
