# Offline stopping: evidence review, 2026-10-25

**Not publication-ready. No new inference. Stage 0 unchanged.**

Read-only diagnostics: `python -m audit.rat_agentic_integrity_20261025.stopping_review.check_source`.
The script retains trace/dataset SHA-256 in `source_diagnostic.json`.

Findings from the current loader/report, not a new quality experiment:

1. The source is exposed historical development: 100 SC rows, 100 groups, five candidates each (40 arithmetic, 31 ordering, 29 Game24). Thirty permutations reuse these same outputs; they do not add independent questions or model draws. Existing research protocol already identifies Run 11 as development, with scoring/token limitations.
2. Candidate cost is **imputed** as `max(1, completion_tokens // 5)` for every candidate of a question. Per-candidate generated-token counts are absent. Thus fixed-k=3's 40% proxy reduction follows directly from the equal-share cost assumption. It is not measured online token or full inference savings; prompt, cache, timing and collection cost are not represented.
3. Correctness uses exact string equality against gold. Comparing all 500 saved candidates against the existing procedural checker on their matching `gen02_tune` item finds **74 disagreements**. Example: `g24_0000_en_orig` candidate `8 / (13 - 12) * 3` is a valid alternative to the gold expression but literal equality rejects it. This diagnostic does not itself validate dataset labels or license/review status.
4. Before this review, the README generator hard-coded headline conclusions and numeric values, including seed=42 and 100 questions. This exporter has now been corrected to emit actual configuration, cost/scoring metadata and explicit limitations; the historical table is preserved. Equal point estimates or a CI crossing zero do not establish equivalence/noninferiority. No such margin/design has been validated here.
5. The gold-dependent oracle uses correctness unavailable at deployment. Its result is a descriptive upper bound under this replay setup, not a deployable controller or an achievable savings estimate.

Use the implementation as software infrastructure and these numbers as historical diagnostics only. Before a publishable comparison: freeze reviewed inputs/splits and valid scorer/canonicalization; collect actual per-call prompt/completion counts and failure status; fit/select rules only on development/calibration; evaluate held-out groups with fixed baselines and paired uncertainty; state replay cost scope separately from online latency. Do not use this review to authorize a new research campaign.
