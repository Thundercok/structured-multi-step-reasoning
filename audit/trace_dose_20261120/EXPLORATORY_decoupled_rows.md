# Exploratory (post-hoc, 2026-11-27): rival explanation for H3/H4

**Status:** exploratory, run after seeing H4 results. Not pre-registered. 0 GPU.
Script: `<artifact dir>/scratch/trace_structure.py` (paired comparison of the 229 self vs human training traces).

## Question

The paper explains H3/H4 as *off-policy trace-source mismatch*. Rival: human traces differ in **structure**, and
the structure itself teaches weaker step dependence.

## Result 1: structure is mostly matched (supports the paper)

| Feature (229 paired training rows) | self | human | paired p |
|---|---:|---:|---:|
| Calc lines per trace | 3.11 | 3.12 | 0.83 (Wilcoxon) |
| Calc uses an earlier result (`dep_rate`) | 0.827 | 0.840 | 0.31 |
| Dead-end intermediate results | 0.074 | 0.065 | 0.44 |
| Grounded operands | 0.843 | 0.845 | 0.42 |
| Plannable for intervention | 166 | 164 | 0.84 (McNemar) |

## Result 2: one real difference (a confound)

`answer_from_last_calc`: self **229/229**, human **221/229** (discordant 8/0, McNemar p = 0.0078).
In those 8 human rows the final answer is not produced by any Calc line (e.g. last `Calc: 9*6000=54000`, `Answer: 15`).
These rows directly demonstrate "the answer need not come from the written steps".

These rows scale with dose in H4:

| Human fraction | 0% | 25% | 50% | 75% | 100% |
|---|---:|---:|---:|---:|---:|
| Decoupled training rows | 0 | 1 | 3 | 3 | 8 |
| Pooled B1 `follows` | 89.4% | 85.9% | 82.9% | 83.8% | 80.1% |

The 50%→75% plateau coincides with the count staying at 3. **Five points, chosen after the fact: suggestive only.**

## What this means for claims

H3/H4 cannot separate (a) off-policy style mismatch from (b) a handful of explicit answer–step decoupling examples.
The Discussion's mechanism sentence ("aligns with off-policy distribution mismatch") exceeds the evidence until tested.

## Candidate falsification test (not run; needs the student's decision)

Drop the 8 questions from both sets (221 pairs), retrain self vs human (2 seeds), evaluate on a fresh split.
Gap survives → (b) is not the main driver. Gap collapses → (b) is.
