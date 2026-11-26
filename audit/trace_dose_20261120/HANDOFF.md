# Handoff: Trace-Source Dose Response (`trace_dose_20261120`)

**Updated:** 2026-11-27 00:12 +07
**Preregistration commit (pushed before mixing/training/eval):** `c437df01` on `main` (amendment in effect: `d4dbcd80`, `docs/trace_dose_prereg_amendment_20261123.md`)
**Target Venues (Dual-Track):**
- **NCKH** (Primary student research defense/paper: `docs/paper/nckh_structured_reasoning.tex`)
- **EACL 2027 Student Research Workshop (SRW)** — Direct submission deadline: **2026-12-15** (AoE safe; Notification: **2027-01-05**, Camera-ready: **2027-01-19**)
  - **OpenReview:** `https://openreview.net/group?id=eacl.org/EACL/2027/SRW`
  - **Format:** Official ACL template; **Short Paper locked (4 pages content, 5p camera-ready)**; references/appendices/limitations unlimited.
  - **Anonymity:** ARR double-blind anonymity policy (no author names, affiliations, or identifying links in submitted PDF; non-anonymous preprints allowed under ARR).
  - **Hardware Constraint:** Seed 1 MUST stay on Apple Silicon MLX (`mlx-community/Qwen3-8B-4bit`) — do NOT move to Colab CUDA (quantization confounder vs Seed 0).

## 1. Strategic Context (Why We Pivoted Here)

- The only preregistered **and** replicated effect in this repo is **H3 (`self > human` trace source)** on GSM-Plus:
  - Seed 0 (`audit/trace_source_20261117`): +8.6 pp, McNemar $p = 0.023$
  - Seed 1 (`audit/trace_source_seed1_20261119`): +9.7 pp, McNemar $p = 0.007$
- In contrast, `CF > Plain` (H1) did **not** replicate on GSM-Plus holdout (+1.4 pp, $p = 0.51$), and 7 exploratory mechanism probes (Nov 18–20) were null/mixed. Steering vector draft (`docs/steer_vector_prereg.md`) is parked in `docs/research_plan.md` Backlog.
- **User-approved target thesis (Option B, `docs/paper/outline_20261116.md`):**
  > *Degradation of step dependence under reasoning SFT is driven by trace-source mismatch: increasing the fraction of human-written traces monotonically erodes reliance on intermediate steps, outweighing the effect of counterfactual augmentation.*
- **Strict fallback rule:** If H4 is not significant OR the 5-point curve is a binary step/threshold instead of gradual erosion, drop *"monotonically"* and fall back to Option A / honest threshold framing.

## 2. Experimental Design (Locked in `docs/trace_dose_prereg.md`)

- **5 strictly nested mixing ratios** on the exact same 229 questions & row order (`mix_seed = 20261120`, `structured_llm/trace_mix.py`):
  - `0 / 25 / 50 / 75 / 100%` human traces = `0 / 57 / 114 / 172 / 229` human rows.
  - `audit/trace_dose_20261120/check.json`: 0 errors, 0 off-format, 0 rows > 512 tokens, mean lengths 209.4–210.2 tokens across all 5 sets.
- **10 adapters (5 ratios × 2 seeds: 0 and 1):**
  - `0%` = existing `adapters/trace_self_200_s{0,1}`
  - `100%` = existing `adapters/trace_human_200_s{0,1}`
  - `25/50/75%` = newly trained `adapters/trace_mix{25,50,75}_200_s{0,1}` (all 6 trained & saved on 2026-11-20).
- **Clean held-out evaluation set:** First 500 questions of `data/gsm_plus_v1/holdout_819.jsonl` (sha256 `d079e99a...`, 0 overlap with H3's 500 questions, never evaluated on any `trace_*` adapter).
- **Primary test (H4) — AMENDED 2026-11-23, before analysis** (`docs/trace_dose_prereg_amendment_20261123.md`, commits `5acf368`, `d2404e6`, `d4dbcd8`):
  - **Why:** the registered question-only GLMM LRT treats ~5,000 rows as independent although there are only 10 training runs. In simulation (`audit/trace_dose_20261120/amendment_20261123/`) it rejects 0.11 / 0.26 / 0.43 under the null when each adapter has its own logit offset τ = 0.1 / 0.2 / 0.3.
  - **Primary now:** `adapter_level_test` in `analyze.py` — one logit per (seed, ratio) adapter, OLS on human fraction + seed, two-sided t-test, 7 df, α = 0.05 (size 0.03–0.04 in the same simulation).
  - **Primary metric (B1, chosen by the student):** `follows` among planned interventions whose `expected` is known. Flagged original traces (`expected = None`: wrong `Calc`, or answer not from the last `Calc`) cannot reach `follows`; their rate is reported per cell as a trace-quality metric.
  - **Secondary / descriptive:** same test on the original metric; same test on items eligible in all 10 cells; the original GLMM LRT, 3-df nonlinearity LRT, common-intersection and per-seed GLMMs (descriptive only — their p-values may be too small); fresh McNemar (`0% vs 100%`, `25% vs 75%`); `format_valid` / `accuracy` / `taxonomy` table.
  - **Known limit:** the 0% and 100% adapters are the H3 adapters, so H4 is independent of H3 in questions, not in adapters.

## 3. Current Status (as of 2026-11-27)

- **Training:** 10/10 adapters `OK`.
- **Eval + Interventions:** **10/10 DONE** (Seed 0 + Seed 1 all `500/500`, all interventions complete).
- **Analysis & Report:** `results.json` generated (2026-11-25) and `RESULTS.md` written (2026-11-27).
  - **Primary H4 (adapter-level OLS, B1):** `b_human = -0.6489`, `t(7) = -5.380`, **`p = 0.00103`** (supported).
  - **Monotonicity rule:** B1 5-level mean logits `2.120 / 1.795 / 1.571 / 1.639 / 1.386` (flat/slight bump at 50%→75%) → **drop "monotonically"**, frame as **dose-dependent erosion**.
  - **Reviewer defense:** `format_valid` comparable (314–341/500), `accuracy` drops from ~81.4% (0%) to ~72.0% (100%) with `truncated` rising from 9–10 to 35–50.
- **Nothing running in background.**

## 4. Operational Commands & Machine Constraints

- **Check progress anytime:**
  ```bash
  ./audit/trace_dose_20261120/run_phase.sh status
  ```
- **Resume Seed 1 safely** (keep Metal buffer limits + auto-retry because 16 GB M1 occasionally throws transient `kIOGPUCommandBufferCallbackErrorOutOfMemory` after ~180–200 generations):
  ```bash
  caffeinate -i zsh -c '
    export MLX_MAX_OPS_PER_BUFFER=10 MLX_MAX_MB_PER_BUFFER=512
    for cell in "1 0" "1 25" "1 50" "1 75" "1 100"; do
      s=${cell% *}; r=${cell#* }; tries=0
      until ./audit/trace_dose_20261120/run_phase.sh eval $s $r; do
        tries=$((tries + 1)); [[ $tries -ge 20 ]] && exit 1; sleep 5
      done
    done
    ./audit/trace_dose_20261120/run_phase.sh analyze
  '
  ```
- **User habit:** User frequently pauses/closes laptop for class or plays League of Legends on this M1 16 GB. Always kill MLX before gaming; both `evaluate` and `intervene` flush every item to `.jsonl` so stopping loses at most ~1 item (~20s).

## 5. Next Steps (18 days to EACL 2027 SRW deadline 2026-12-15)

1. **Completed:**
   - All 10 cells evaluated & intervened (`s0_r0..100`, `s1_r0..100`).
   - `results.json` computed without modifying `analyze.py`.
   - `audit/trace_dose_20261120/RESULTS.md` written strictly following prereg + amendment.
   - Qualitative inspection of H3 discordant pairs (`audit/trace_source_20261117/MECHANISM_NOTES.md`).
2. **Immediate next moves (CPU-free, toward EACL 2027 SRW 4-page Short Paper):**
   - Run Gate-2 literature survey on *"self-generated vs human-written CoT traces × faithfulness / counterfactual step dependence"*.
   - Update `docs/research_plan.md` & `docs/paper/outline_20261116.md` with the H4 outcome (dose-dependent erosion, dropping "monotonically").
   - Draft the 4-page ACL Short Paper (anonymous ARR format) + dose-response figure for EACL 2027 SRW.
3. **Collaboration style:** Keep replies short, bite-sized, one step at a time (AI Research Partner Charter in `AGENTS.md`). Do not commit/push unless asked.
