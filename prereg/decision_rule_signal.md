Confidence signals: COT, finished-only, repeated 5-fold CV x20, final 571-line trace. Committed before analysis.
Baseline = [family one-hot + level + completion_tokens]. A signal counts only if baseline+signal beats baseline by >= 0.05 CV AUROC
with paired-bootstrap 95% CI lower bound > 0, in arith AND order separately.
Else: no threshold fitting on that signal; use verifier- or agreement-based escalation.
