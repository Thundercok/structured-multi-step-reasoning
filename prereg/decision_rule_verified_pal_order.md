# Preregistration: Verified-PAL for Ordering Reasoning

**Protocol**: Frozen prior to execution on held-out / confirmatory splits.  
**Domain**: Logic Ordering tasks (runners, sequential order, distance gap clues, gapB wording).

## 1. Strategies & Baselines

1. **Always-ToT**:
   - 3 candidate branches at $T=0.7$, followed by a zero-temperature model selector.
2. **Always-PAL-v2**:
   - Python code generation with allowlisted standard modules (`itertools`, `collections`).
   - Sandbox execution with keyword safety filtering (`open`, `exec`, `os`, `sys`, `subprocess` blocked).
   - Only checks runtime success (`exec ok`); accepts whatever `result` is returned.
3. **Policy W (Exec-Gated Cascade)**:
   - Stage 1: PAL-v2.
   - Escalation trigger: `exec status != ok`, output empty/None, or finish reason == length.
   - If escalated: Execute ToT; final answer from ToT. Total cost = Stage 1 tokens + Stage 2 tokens.
4. **Verified-PAL (Certificate-Gated Cascade)**:
   - Stage 1: PAL-v2 with Certificate Contract.
     Model outputs a witness certificate containing full ranking and final answer:
     ```json
     {"order": ["Alice", "Bob", "Carol", "Dave", "Erin"], "answer": "Carol"}
     ```
   - Stage 1 Gate: **Query-Derived Certificate Verifier** (Fail-Closed).
     Parses the raw problem text (no access to `meta` or gold answers) into a Constraint IR:
     - Runners set $\{R_1, \dots, R_n\}$
     - Clues: `before`, `after`, `immediately before/after`, `gap(k)`
     - Asked target position (e.g. 1st, 2nd, ..., n-th)
     Checks:
     1. **Permutation validity**: `order` contains each runner exactly once, length equals $n$.
     2. **Clue satisfaction**: All parsed constraints hold on `order`.
     3. **Answer alignment**: `answer` matches runner at asked position (`order[asked_rank - 1]`).
   - Verifier Output States:
     - `VALID`: Permutation valid, all clues hold, answer aligns $\implies$ ACCEPT answer, terminate.
     - `INVALID`: Clue violated, malformed permutation, or answer mismatch $\implies$ ESCALATE to ToT.
     - `UNVERIFIABLE`: Query parser failure, missing certificate, or unparseable JSON $\implies$ ESCALATE to ToT.
   - Final Answer: Stage 1 answer if `VALID`, else ToT answer.
   - Cost: Stage 1 tokens if `VALID`; Stage 1 tokens + Stage 2 tokens if escalated.
5. **Thinking-Native (Reference Baseline)**:
   - Native reasoning mode under matched fixed compute budget. Standalone baseline; not part of cascade.

## 2. Decision Rules & Primary Gate

**Primary Gate for Verified-PAL Success**:
$$\text{Acc}(\text{Verified-PAL}) \ge \text{Acc}(\text{Always-ToT}) - 2.0\text{ pp} \quad \text{AND} \quad \text{Cost}(\text{Verified-PAL}) \le 0.60 \times \text{Cost}(\text{Always-ToT})$$
evaluated with 95% cluster-bootstrap confidence interval.

If the gate is not satisfied, report the outcome as a negative result and retain ToT as the superior standalone strategy.

## 3. Required Diagnostic Metrics

For all evaluations, the report must include:
1. Full tokens (Prompt + Completion), counting all executed stages.
2. Overall Accuracy and 95% Cluster-Bootstrap CI (clustered by `group_id`).
3. Escalation rate $e = N_{\text{escalated}} / N$.
4. Verifier confusion matrix:
   - True Accepts (correct witness validated)
   - False Accepts (leakage: incorrect answer passed verifier)
   - True Rejects (incorrect witness caught and escalated)
   - False Rejects (unnecessary escalation of a correct answer)
5. Net Rescue vs. Harm:
   - Rescued: PAL wrong $\to$ Verifier rejects $\to$ ToT correct
   - Harmed: PAL correct $\to$ Verifier rejects $\to$ ToT wrong
