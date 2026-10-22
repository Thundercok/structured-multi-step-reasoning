# Fresh CoT Restart Data Review Checklist & Protocol Freeze Profile (Candidate 71/70)

**Date**: 2026-10-20  
**Status**: PENDING INDEPENDENT HUMAN REVIEW (Execution Unauthorized, Stage 0 Gate In Force)  
**Target Candidate Packet**: `audit/cot_restart_fresh_data_review_20261016/`  
**Candidate Items**: 71 items  
**Candidate Canonical Groups**: 70 groups  

---

## 1. Provenance, Licensing & Independence Index

| Source Collection | Candidate Items | Candidate Groups | License / Origin | Known Exposure Checks |
|---|---|---|---|---|
| `data/procedural_research_v1/main.json` (split: `test`) | 71 | 70 | TDTU Academic & Procedural Reasoning Benchmarks (Internal Student Research) | Verified zero overlap against tuning pool (91 groups), pilot 12-call (12 groups), order dev2 (2 groups), and order dev8 (8 groups). |

### Strict Pre-condition Audit Verification
- `data/procedural_research_v1/manifest.json`: SHA256 `d585eddb175d292568230c1cf8e7f6b7aba3bb23345c6b49f2584447d86c5289` (Verified).
- `data/procedural_research_v1/main.json`: SHA256 `fa5d09d9a1074de0e65ae544ff977b6c2751a1a36c60fd721d51234a9b2b3ddc` (Verified).
- `data/procedural_research_v1/tuning.json`: SHA256 `069ca68a4d34d40a3c2f559dffadaa255e73e1e9719e8e488f171a091e002d95` (Verified).
- `data/gen_v2.json`: SHA256 `c6af7d21994d537da1a4b94dbe8c954e2cf2b66dce1d3732e485688cac522d6b` (Verified).
- `research_identity.py`: SHA256 `5e22ba902cbb2d9f033b149570d252497fe15fb46dae5bcc7d736447204debb0` (Verified).
- Candidate test items across all 3 splits (`train`, `calibration`, `test`) have **zero cross-split group leakage** (`split_groups['train'] & split_groups['test'] == empty`, `split_groups['calibration'] & split_groups['test'] == empty`).

---

## 2. Human Reviewer Action Checklist

This checklist is provided for independent human review before authorizing any real collection run.
*Notice: Agent inspection or automated schema checks cannot replace independent human adjudication.*

### Item-by-Item Review Criteria:
1. **Ownership & Legal Authority**:
   - [ ] Confirm question content does not infringe copyright or expose private personal student records.
2. **Gold Truth Rationale**:
   - [ ] Verify derivation and correctness of ground truth value.
   - [ ] Confirm typed format metadata (`number`, `text`, `expression`) and decimal separator (`.` or `,`) match the gold answer without ambiguity.
3. **Canonical Grouping & Variant Validity**:
   - [ ] Confirm items sharing a `group_id` are genuine lexical/numerical variants of the same problem template.
   - [ ] Enforce the representative selection rule: *lexicographically smallest item ID per group*, determined prior to running models.
4. **Prior Corpus Exposure Assessment**:
   - [ ] Check whether question phrasing matches common public GSM8K / SVAMP / MATH questions that may have leaked into base LLM pre-training data.
   - [ ] Note: Structural checks verify zero overlap with local pilot pools; they do NOT certify complete absence of pretraining contamination in proprietary model weights.
5. **Disposition Adjudication**:
   - [ ] Record explicit human decision per item/group: `ACCEPT`, `REJECT`, or `MODIFY`.
   - [ ] If any modifications are made, export a new versioned release with re-hashed manifest; never modify in-place.

---

## 3. Protocol Freeze & Statistical Power Profile

### A. Candidate Pool vs Statistical Power
- The **70 candidate groups** represent the currently available pool of clean, unexposed items.
- **70 groups is NOT a sample size proven to have adequate statistical power** for subtle effects.
- **Power Sensitivity Analysis** (Reproducible artifact: `power_sensitivity.json`, computed via `scripts/calculate_power_sensitivity.py`):
  - Model: Asymptotic McNemar paired test of proportions (two-sided $\alpha = 0.05$).
  - Primary baseline assumption: Discordant pair rate $p_{disc} = p_{10} + p_{01} = 0.30$ (with sensitivity bounds $p_{disc} \in [0.20, 0.40]$).
  - For candidate pool $N=70$:
    - Minimum Detectable Effect (MDE) for 80% power ($1 - \beta = 0.80$): $\text{MDE} \approx 0.183$ (at $p_{disc}=0.30$) and $\text{MDE} \approx 0.150$ (at $p_{disc}=0.20$).
    - Power to detect $\Delta = 0.10$: only $\approx 33.3\%$ ($N = 236$ required for 80% power in this approximation).
    - Power to detect $\Delta = 0.05$: only $\approx 10.9\%$ ($N = 942$ required for 80% power in this approximation).
  - **Conclusion & Boundary Rule**: $N=70$ is powered only to detect large effects ($\Delta \ge 0.15 - 0.18$). Smaller margins will result in indeterminate / inconclusive hypothesis tests. Researchers must not treat failure to reject as proof of equivalence. These numbers are planning proposals, not a formal preregistered execution freeze.

### B. Separation of Experimental Studies & Arms
To avoid confounding and budget confusion, two distinct empirical investigations in the RAT–CoT research program are strictly decoupled:

1. **Study 1: Fresh-Restart Manipulation (Prefix Continuity vs. Fresh KV Cache)**:
   - Evaluates prefix interventions executed with clean per-call KV cache under `docs/cot_restart_fresh_adapter_20261016.md` and `experiments/cot_restart_fresh.py`.
   - **Arms** (strictly 1 LLM request per arm per item; each call runs with independent, fresh per-call KV cache):
     - $O$: Original generation / baseline prompt with greedy decoding (`temperature=0.0`), no prefix.
     - $F$: Continuation from partial reasoning prefix of $O$ at $q^* = 0.50$ (`temperature=0.6`, fresh per-call cache).
     - $CONT$: Continuation reasoning from full reasoning prefix of $O$ at $q = 1.0$ (`temperature=0.6`, fresh per-call cache).
     - $A$: Alternate generation without prefix using identical user CoT prompt (`temperature=0.6`, fresh per-call cache).
   - **Dispatched Attempt Cap**: Exactly $70 \text{ groups} \times 1 \text{ rep} \times 4 \text{ arms} = 280$ single-call generation requests.

2. **Study 2: Online Routing Ladder Study (Meta-Controller Escalation)**:
   - Evaluates adaptive multi-call routing: EntryPredictor $\to$ OptimalStoppingPolicy (COT $\to$ SC $\to$ ToT).
   - **Multi-call Subcall Structure**:
     - Direct / COT: 1 call.
     - SC-5: up to 5 calls.
     - ToT-4: up to 4 calls.
     - Worst-case per query: up to 10 subcalls.
   - **Dispatched Attempt Cap**: Requires independent budgeting ($70 \times 10 = 700$ maximum requests if unstopped).
   - Decoupled from the 280-call Fresh-Restart budget.

### C. Execution Settings & Provenance
- Fixed random seeds: 42 (calibration), 1001 (sample draws).
- Per-turn token ceiling: 64 tokens (smoke baseline; study ceiling pending preregistration).
- Requested rate: $q = 0.50$.
- Attempt count per group: $m = 1$ primary draw.
- **Token Semantics & Latency**:
  - Prompt tokens, generated tokens, and total token sums recorded separately in append-only ledger.
  - Generated tokens measure model output length; they do NOT measure full cloud/hardware inference costs or real online user-perceived latency.
