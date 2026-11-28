# Paper Storyline — Structured Reasoning Trace Source and Step Dependence

> **Status:** working synthesis, not a frozen manuscript claim  
> **Prepared:** 2026-11-28  
> **Purpose:** reconcile the current experiment record into one defensible paper narrative before external review.  
> **Primary evidence:** `audit/trace_dose_20261120/RESULTS.md`, `audit/trace_dose_20261120/HANDOFF.md`, `docs/trace_dose_prereg.md`, and `docs/trace_dose_prereg_amendment_20261123.md`.

---

## 1. Recommended paper identity

### Working title

**Trace-Source Composition and Step Dependence in Mathematical Reasoning SFT: A Dose-Response Study with Qwen3-8B**

Alternative, more conservative title:

**A Controlled Study of Trace-Source Composition and Counterfactual Step Dependence in Qwen3-8B**

### One-sentence summary

In a controlled, small-scale study of Qwen3-8B, increasing the proportion of human-written reasoning traces in a fixed-size supervised fine-tuning dataset was associated with a lower rate of following counterfactually perturbed intermediate calculations, although the five-level pattern was not strictly monotonic and the result is limited to one model, one task family, and two training seeds.

### Scope

- Model: Qwen3-8B-4bit using MLX on Apple Silicon.
- Task family: grade-school mathematical word problems.
- Training data: 229 aligned questions, with five nested trace-source mixtures (0%, 25%, 50%, 75%, 100% human-written traces).
- Evaluation: 500 GSM-Plus holdout questions, with no question overlap with the earlier H3 evaluation.
- Intervention: perturb an intermediate `Calc` result and observe whether the continuation follows the perturbed value.
- Main construct: **operational counterfactual step dependence**, not direct access to the model's internal reasoning process.

This paper is not a claim about all language models, all reasoning tasks, or human-written reasoning traces in general.

---

## 2. The primary research question

**RQ1 — Trace-source composition:**  
For a fixed set of training questions and a fixed SFT recipe, how is the proportion of human-written versus self-generated structured reasoning traces associated with a model's dependence on intermediate calculation steps, as measured by counterfactual intervention?

This is the paper's single primary question.

### Supporting questions

- **RQ2 — Robustness across mixture levels:** Does the endpoint difference between 0% and 100% human-written traces extend across intermediate mixture ratios, or does the pattern look more like a threshold/step effect?
- **RQ3 — Performance trade-offs:** How do answer accuracy, output-format validity, truncation, and intervention eligibility vary across the five mixture levels?

RQ2 and RQ3 support interpretation of RQ1. They should not become separate novelty claims.

---

## 3. Hypothesis and conclusion

### Registered hypothesis

The registered H4 question was whether increasing the human-written trace fraction would reduce counterfactual step-following, and whether the five-level pattern would justify the stronger word **"monotonically"**.

The primary analysis was amended on 2026-11-23, before `analyze` was run. The amendment moved the primary test to the adapter level to avoid treating thousands of intervention rows as independent when there were only ten trained adapters. It also defined the primary outcome as B1: `follows` among planned interventions with a known expected value (`expected != None`).

The amendment and its rationale must be disclosed in the paper. Do not present the amended analysis as if it were the original preregistered test.

### Result supported by the current evidence

The adapter-level OLS test across ten adapters (five mixture ratios × two seeds) found a negative association between human-trace fraction and B1 step-following:

- Slope: **−0.6489**
- SE: **0.1206**
- t(7): **−5.380**
- p: **0.00103**

The five-level mean logits for B1 were:

| Human-written trace fraction | 0% | 25% | 50% | 75% | 100% |
|---|---:|---:|---:|---:|---:|
| Mean logit B1 | 2.120 | 1.795 | 1.571 | 1.639 | 1.386 |
| Approx. B1 rate | 89.4% | 85.9% | 82.9% | 83.8% | 80.1% |

The 75% level is slightly higher than the 50% level. Therefore:

- **Supported:** higher human-trace fraction is associated with lower B1 step-following in this experiment.
- **Not supported:** a strictly monotonic decrease at every intermediate level.
- **Required wording:** "dose-dependent erosion" or "a negative dose-response trend", with the non-monotonic 50%–75% segment stated explicitly.
- **Do not write:** "monotonically erodes" or "monotonic dose-response."

### Endpoint comparisons on the new evaluation questions

The H4 report also gives paired comparisons of the 0% and 100% adapters on their common eligible questions:

- Seed 0: 88.4% vs 74.1%, difference +14.3 percentage points, 95% CI [8.0, 20.5], McNemar p = 1.94e-5.
- Seed 1: 90.1% vs 78.3%, difference +11.8 percentage points, 95% CI [6.1, 17.6], McNemar p = 1.21e-4.

These are paired comparisons of those specific adapters, not independent replications across newly trained endpoint adapters. The 0% and 100% adapters are reused from H3.

---

## 4. What the result does and does not mean

### Defensible interpretation

The experiment provides evidence that, under this particular Qwen3-8B SFT setup, trace-source composition is associated with how often the model's continuation follows an externally perturbed intermediate calculation. A larger human-written fraction corresponds to a lower observed B1 rate across the ten adapters.

This is evidence about the model's **observable response to a particular intervention protocol**. It does not reveal hidden internal cognition and should not be equated with a complete measure of reasoning faithfulness.

### Claims to avoid

Do not claim that:

1. Human-written traces universally make language models less faithful.
2. Self-generated traces are generally superior to human-written traces.
3. The effect is strictly monotonic.
4. The experiment establishes a mechanism explaining *why* the effect occurs.
5. The effect generalizes beyond Qwen3-8B, GSM-Plus-style numerical substitution, the chosen trace format, or this training recipe.
6. This study shows that trace-source mismatch outweighs counterfactual augmentation. H4 varies trace-source mixture; it does not factorially isolate or compare the contribution of counterfactual augmentation.
7. The intervention directly measures the model's internal reasoning state.

### Important competing interpretation

As the human-trace fraction increases, answer accuracy also declines and truncation rises. Across the two seeds:

- At 0% human traces, accuracy is 82.2% and 80.6%; truncation is 10 and 9 cases.
- At 100% human traces, accuracy is 73.4% and 70.6%; truncation is 35 and 50 cases.
- Format validity is in a comparatively similar range across cells (314–341 valid outputs out of 500).

This pattern matters. The lower B1 rate could be related to changes in model competence, generation length, truncation, or the composition of eligible interventions—not solely a change in reliance on reasoning steps. The paper must report these outcomes alongside B1 and avoid a causal-mechanistic explanation that the current design cannot isolate.

---

## 5. Experimental design and analysis that must be described

### Training design

- Five nested training mixtures: 0%, 25%, 50%, 75%, and 100% human-written traces.
- 229 training questions, with row order held fixed across mixture levels.
- Two training seeds (0 and 1).
- Same SFT recipe and 200 training iterations.
- Ten adapters in total.
- The 0% and 100% adapters are reused from H3; the three intermediate ratios are newly trained for H4.

### Evaluation design

- First 500 questions of `data/gsm_plus_v1/holdout_819.jsonl`.
- The 500 questions do not overlap with the 500 questions used in H3.
- All ten adapters were evaluated and intervened on.
- The intervention perturbs an intermediate `Calc` value and classifies the continuation (e.g. `follows`, `reverted`, `other`, `no_answer`).

### Primary outcome and test

- Primary outcome: B1, `follows` among planned interventions with `expected != None`.
- Primary unit for the dose-response test: adapter, not individual intervention row.
- Transform: `logit((f + 0.5)/(n + 1))`.
- OLS predictors: human-trace fraction and seed.
- Primary test: two-sided t-test of the human-fraction coefficient, 7 degrees of freedom, alpha = 0.05.
- Report per-cell denominators and intervention eligibility/flagged-trace rates.

### Sensitivity and descriptive analyses

- Common-intersection analysis on the 59 questions eligible in all ten cells: slope −0.6774, SE 0.1559, t(7) = −4.344, p = 0.00338.
- Original metric including flagged traces: slope −0.6591, p = 0.00074 (secondary).
- Paired McNemar comparisons between the exact adapter pairs, clearly labelled as such.
- Accuracy, format validity, truncation, and intervention taxonomy by cell.
- GLMM analyses and nonlinearity tests are descriptive only under the amendment; their p-values may be anti-conservative because they do not model adapter-level variation adequately.

### Preregistration transparency

The paper must clearly disclose:

1. The original preregistration and the 2026-11-23 amendment.
2. Why the primary test changed (pseudo-replication risk with only ten adapters).
3. Why B1 was selected and that eligibility depends on each adapter's own generated trace.
4. That H3 endpoint adapters were reused, so H4 is independent of H3 in evaluation questions but not in adapter weights.
5. Which analyses were primary, secondary, and descriptive.

---

## 6. Main limitations

1. **Only one base model:** Qwen3-8B-4bit.
2. **Only two training seeds:** insufficient to characterize training-run variability precisely.
3. **Only ten adapters:** the primary regression has ten observations and seven residual degrees of freedom.
4. **Reused endpoint adapters:** 0% and 100% cells are the H3 adapters, so the H4 dose-response is not ten wholly independent training runs.
5. **Small training set:** 229 questions, with nested mixtures.
6. **Single task family and evaluation distribution:** GSM8K-derived training and GSM-Plus numerical-substitution evaluation.
7. **Selection/eligibility:** both intervention planning and B1 eligibility depend on the model's own output. The B1 denominator varies across cells; flagged traces must be reported rather than hidden.
8. **Accuracy and truncation trade-off:** higher human-trace fractions are accompanied by lower accuracy and more truncation in the current results.
9. **Operational construct:** following a perturbed `Calc` value is not equivalent to full faithfulness or access to internal reasoning.
10. **No factorial test of counterfactual augmentation:** the paper cannot claim a relative effect between trace source and counterfactual augmentation from H4 alone.

---

## 7. Related work and novelty positioning

The existing survey in `docs/related_work_survey_20261114.md` concludes that the broad phenomena "counterfactual training improves step-following" and "ordinary fine-tuning can reduce CoT faithfulness" are already present in prior work. The current paper should not claim either phenomenon as a new discovery.

The narrower contribution to investigate is a **controlled trace-source mixture / dose-response study** using nested training sets, two seeds, a held-out GSM-Plus evaluation, and an adapter-level primary analysis.

This is a candidate empirical contribution, not yet a verified novelty claim. Before submission:

- Read the closest papers in full, especially LIFT, Lobo et al., CASE, and any work specifically comparing self-generated and human-written traces.
- Search ACL Anthology, OpenReview, arXiv, and recent proceedings for trace-source mixture or source-composition ablations.
- Compare not just the headline question but also model, training setup, intervention, data, and statistical unit.
- State the difference from prior work narrowly and cite evidence for it.

Do not write "no prior work has studied this" based only on the current partial survey.

---

## 8. Manuscript structure (4-page short-paper target)

1. **Introduction:** why observable dependence on intermediate reasoning steps matters; precise research question and scope.
2. **Related Work:** CoT faithfulness, counterfactual interventions, trace-source composition and SFT.
3. **Method:** structured `Step/Calc` format, trace-source mixtures, training setup, intervention, outcome taxonomy.
4. **Experimental Setup:** data, splits, seeds, preregistration and amendment, adapter-level test.
5. **Results:** primary dose-response result first; then endpoint paired comparisons; then accuracy/format/truncation and eligibility.
6. **Discussion:** what the intervention supports, competing explanations, implications for trace construction.
7. **Limitations and Conclusion:** concise, explicit scope limits.

A short paper should not include the old independent-vs-translated PAL error-detection thread as a second central story. That is a different research question and would dilute this paper.

---

## 9. Pre-submission audit checklist

### Evidence and statistics

- [ ] Recompute every table directly from the committed raw `results.json` and intervention files.
- [ ] Verify all reported denominators and confirm the 59-item common intersection.
- [ ] Report confidence intervals for the primary slope and/or fitted contrast; do not rely on p-values alone.
- [ ] Add a clear plot of all ten adapter-level observations, not only five averaged points.
- [ ] Show accuracy, truncation, format validity, flagged-trace rate, and B1 eligibility together.
- [ ] Check whether the B1 trend remains interpretable after transparently stratifying or describing truncation and eligibility. Do not invent a post-hoc causal adjustment.
- [ ] Include seed-specific curves and avoid implying that two seeds establish broad reproducibility.

### Research framing

- [ ] Replace "monotonically" with "dose-dependent erosion" or a similarly qualified description.
- [ ] Remove "outweighing counterfactual augmentation" unless a suitable factorial comparison is added.
- [ ] Distinguish counterfactual step-following from internal reasoning faithfulness.
- [ ] Clearly state the H4 amendment and endpoint-adapter reuse.
- [ ] Update `README.md`, `docs/research_plan.md`, and `docs/paper/outline_20261116.md` so they tell the same current story.
- [ ] Ensure the obsolete PAL error-detection figures are not presented as the main contribution.

### External review

- [ ] Ask at least one NLP/LLM researcher to challenge novelty and positioning.
- [ ] Ask at least one methods/statistics reviewer to challenge the adapter-level inference and eligibility selection.
- [ ] Ask a peer to reproduce one result table from raw artifacts.
- [ ] Record feedback and disposition; do not silently change the primary analysis after seeing reviewer comments.

---

## 10. Current decision

**Recommended paper story:** a small, preregistered, controlled dose-response study of trace-source composition and counterfactual step dependence in Qwen3-8B.

**Current strongest result:** a negative adapter-level association between human-written trace fraction and B1 step-following (slope −0.6489, p = 0.00103), with the strict monotonicity claim explicitly rejected.

**Current biggest threat to the paper:** interpretation. Accuracy falls and truncation rises with the human-trace fraction; B1 eligibility is output-dependent; and only ten adapters are available, with the endpoint adapters reused from H3.

**Next action:** do a CPU-free evidence audit and reconcile the public-facing project documents before running more experiments or contacting potential collaborators with a paper claim.
