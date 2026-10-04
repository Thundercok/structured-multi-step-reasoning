6-arm run: gen02_tune (100 items), Qwen3-8B-4bit. Committed before results.
Per arm: acc, mean (prompt+completion) tokens. best-single = highest acc (tie: cheaper).
oracle = cheapest correct arm per item. gap = oracle acc - best-single acc, 95% cluster-bootstrap CI by group_id.
GO to fit/calibration only if gap >= 10pp and CI lower bound >= 5pp. Else fix arms/knobs; no threshold fitting.
Report per family; no pooled claim if families disagree.
