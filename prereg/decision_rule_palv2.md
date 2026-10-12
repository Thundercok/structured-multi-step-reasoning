PAL-v2 = PAL with an import allowlist (itertools, math, fractions, functools, collections) and a prompt that says so. Committed before results.
Run on gen02_tune: arith 40, order 31, g24 29 (original PAL results stay as recorded).
If PAL-v2 accuracy >= ToT on order AND on g24 (point estimates) at <= 0.5x ToT mean tokens: those families are code-solvable; ToT/SC/COT claims there are withdrawn, and the routing study must add families where a program is not a free solution.
Else: ToT stays best on the failing family; PAL limits documented.
Any other reading needs a new rule file.
