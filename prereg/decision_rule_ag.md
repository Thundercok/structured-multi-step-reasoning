Sweep AG. Committed before results. Same model/protocol as run13 (pinned snapshot, enable_thinking=False).
PAL-v4 = PAL-v2 prompt (no eval warning) with builtin `eval` replaced by an AST-based arithmetic evaluator (digits, + - * / ( ), Fractions). exec, compile, open, os, subprocess, sys, __import__ stay blocked; allowlisted imports as v2. Run on all 100 gen02_tune items.
R1 (g24): code-solvable iff PAL-v4 >= 17/29 AND mean total tokens <= 723. Else ToT stays best on g24.
R2 (order, wording): on the 31 gapB items run PAL-v4 and ToT. Code-solvable under unambiguous wording iff PAL-v4 acc >= ToT acc (points) AND tokens <= 0.5x ToT. Else ToT keeps its edge.
R3 (cascade W, exploratory on tune, re-tested on a fresh set later): stage 1 = PAL-v4; escalate to ToT iff exec status != ok, result empty/None, or finish=length. Report acc, mean tokens (both stages), escalation rate, vs always-ToT / always-PAL-v4 / oracle(PAL-v4, ToT), per family.
Anything else goes under UNSPECIFIED.
