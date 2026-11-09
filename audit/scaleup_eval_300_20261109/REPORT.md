# Scale-Up Empirical Evaluation Report (N=300)

> Generated automatically by `scripts/run_scaleup_eval_300.py`
> Date: 2026-11-09 16:57:35

---

## 1. Clean Accuracy & Paired McNemar Test ($N=300$)

| Model | Correct | Accuracy |
| :--- | :---: | :---: |
| **Enriched CF (Proposed)** | 251/300 | 83.67% |
| **Enriched Plain SFT (Baseline)** | 244/300 | 81.33% |

### Paired Contingency Table
* Both Correct ($n_{11}$): **224**
* CF Correct, Plain Wrong ($n_{01}$): **27**
* Plain Correct, CF Wrong ($n_{10}$): **20**
* Both Wrong ($n_{00}$): **29**
* Total Discordant Pairs ($D = n_{01} + n_{10}$): **47**
* **Exact McNemar Test**: Two-sided $p = \mathbf{0.38169}$, One-sided $p = \mathbf{0.19085}$

---

## 2. Causal Intervention Taxonomy ($N=167$ Shared Episodes)

| Metric | Enriched CF | Enriched Plain SFT |
| :--- | :---: | :---: |
| **Exact `follows`** | **136 (81.4%)** | 119 (71.3%) |
| **`follows_rounded`** | 19 (11.4%) | 25 (15.0%) |
| **Total Compliance** | **155 (92.8%)** | 144 (86.2%) |
| **`reverted`** | 3 (1.8%) | 5 (3.0%) |
| **`moved`** | 3 | 4 |
| **`other`** | 6 | 14 |

* **Exact Follows McNemar**: Discordant Pairs = **35** ($CF+=26, Plain+=9$), Two-sided $p = \mathbf{0.00599}$, One-sided $p = \mathbf{0.00299}$

---

## 3. Exhaustive Step Sweep & Positional Decay

### C. Exhaustive Step Sweep Benchmarks (N=238)
* **Discordant Pairs**: 28 (CF+=20, Plain+=8)
* **Exact McNemar p-value**: two-sided $p = 0.03570$, one-sided $p = 0.01785$

| Step $k$ | Total $n$ | Follows (+Rounded) | Reverted | Moved | Other |
| :---: | :---: | :---: | :---: | :---: | :---: |
| $k = 1$ | 111 | 104 (93.7%) | 5 (4.5%) | 1 | 1 |
| $k = 2$ | 75 | 72 (96.0%) | 1 (1.3%) | 0 | 2 |
| $k = 3$ | 33 | 32 (97.0%) | 1 (3.0%) | 0 | 0 |
| $k = 4$ | 13 | 13 (100.0%) | 0 (0.0%) | 0 | 0 |
| $k = 5$ | 6 | 5 (83.3%) | 1 (16.7%) | 0 | 0 |
