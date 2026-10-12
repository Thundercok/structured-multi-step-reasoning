# Preregistration: Decision Rule for PAL-v3 on Game-of-24 (Prompt AF1)

**Commit timestamp:** Prior to execution of PAL-v3.  
**Arm definition:**
- `PAL-v3` = PAL-v2 (same import allowlist: `itertools`, `math`, `fractions`, `functools`, `collections`; sandboxed without `open`, `exec`, `eval`, `sys`, `os`, `subprocess`; 512 token cap, greedy $T=0.0$, timeout 5.0s, output in `result`) plus an explicit prompt guideline:
  `"eval, exec, compile are unavailable; carry (value, expression-string) pairs and build expressions recursively"`.
- Evaluated on: `gen02_tune` Game-of-24 family only ($N=29$).

**Preregistered Decision Rule:**
- If PAL-v3 accuracy $\ge$ ToT point estimate ($17/29 \approx 58.6\%$) at mean total tokens $\le 0.5\times$ ToT mean total tokens ($0.5 \times 1446.8 = 723.4$ tokens):
  $\to$ Game-of-24 is declared **code-solvable**; ToT/SC/CoT claims on Game-of-24 are withdrawn, and the routing study must introduce task families where an executable program is not a free solution.
- Else:
  $\to$ ToT remains best on Game-of-24; PAL limits on symbolic expression search are documented.

No post-hoc reinterpretation of this threshold is permitted.
