# Handoff: Trace-Source Dose Response (`trace_dose_20261120`)

**Updated:** 2026-11-23 16:25 +07
**Preregistration commit (pushed before mixing/training/eval):** `c437df01` on `main`
**Target Venues (Dual-Track):**
- **NCKH** (Primary student research defense/paper: `docs/paper/nckh_structured_reasoning.tex`)
- **EACL 2027 Student Research Workshop (SRW)** — Direct submission deadline: **2026-12-15**
  - **Format:** Official ACL template; **Short Paper locked (4 pages content, 5p camera-ready)**; references/appendices/limitations unlimited.
  - **Anonymity:** ARR double-blind anonymity policy (no author names, affiliations, or identifying links in submitted PDF; non-anonymous preprints allowed under ARR).
  - **Current Action:** `s0_r100` resumed in background at 16:10 +07; Seed 1 (`s1_r0..100`) remains.

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
- **Primary test (H4, `audit/trace_dose_20261120/analyze.py`):**
  - 1D random-intercept logistic GLMM (21-point Gauss–Hermite quadrature):
    `logit P(follows_ij = 1 | u_i) = beta_0 + beta_human * x_ij + beta_seed * s_ij + sigma * u_i`
  - Two-sided LRT (1 df) at $\alpha = 0.05$.
  - Secondary diagnostics already coded & unit-tested (`tests/test_trace_dose_stats.py`, 394/394 pytest passing): 3-df nonlinearity LRT (linear vs 5-level categorical), common-intersection GLMM (all 10 cells), per-seed GLMMs, fresh H3 McNemar (`0% vs 100%`, `25% vs 75%`), and full `format_valid` / `accuracy` / `taxonomy` table (to address the reviewer objection *"self didn't learn anything"*).

## 3. Current Status (as of 2026-11-23 08:18 +07)

- **Training:** 10/10 adapters `OK`.
- **Eval + Interventions:**
  - `s0_r0`: `500/500`, `245/245` (DONE)
  - `s0_r25`: `500/500`, `246/246` (DONE)
  - `s0_r50`: `500/500`, `253/253` (DONE)
  - `s0_r75`: `500/500`, `218/224` (running now, ~2 min left → then `s0_r100` starts)
  - `s0_r100` + `s1_r0..100`: pending (~3.4h per cell on idle M1).
- **Do NOT peek** at `follows` outcomes on partial cells before all 10 finish.

## 4. Operational Commands & Machine Constraints

- **Check progress anytime:**
  ```bash
  ./audit/trace_dose_20261120/run_phase.sh status
  ```
- **Resume safely if stopped/restarted** (replace cell list with only incomplete cells so it doesn't waste 10s reloading completed cells; keep Metal buffer limits + auto-retry because 16 GB M1 occasionally throws transient `kIOGPUCommandBufferCallbackErrorOutOfMemory` after ~180–200 generations):
  ```bash
  caffeinate -i zsh -c '
    export MLX_MAX_OPS_PER_BUFFER=10 MLX_MAX_MB_PER_BUFFER=512
    for cell in "0 100" "1 0" "1 25" "1 50" "1 75" "1 100"; do
      s=${cell% *}; r=${cell#* }; tries=0
      until ./audit/trace_dose_20261120/run_phase.sh eval $s $r; do
        tries=$((tries + 1)); [[ $tries -ge 20 ]] && exit 1; sleep 5
      done
    done
    ./audit/trace_dose_20261120/run_phase.sh analyze
  '
  ```
- **User habit:** User frequently pauses/closes laptop for class or plays League of Legends on this M1 16 GB. Always kill MLX before gaming; both `evaluate` and `intervene` flush every item to `.jsonl` so stopping loses at most ~1 item (~20s).

## 5. Next Steps for This Evening / After Completion

1. **First:** Run `./audit/trace_dose_20261120/run_phase.sh status` and check whether `results.json` exists or if Seed 1 still needs resuming.
2. **While machine runs (CPU-free human work):**
   - Pull ~5–10 discordant pairs from H3 (`audit/trace_source_20261117` — NOT from `trace_dose_20261120`!) where `self` follows and `human` does not, and read them together with the user to diagnose the mechanism qualitatively.
   - Run a proper Gate-2 literature survey on *"self-generated vs human-written CoT traces × faithfulness / counterfactual step dependence"* (beyond Gekhman 2024 & SDFT 2024).
3. **Once all 10 cells finish:**
   - Run `./audit/trace_dose_20261120/run_phase.sh analyze` (if not already auto-run) **without modifying `analyze.py`**.
   - Write `audit/trace_dose_20261120/RESULTS.md` strictly following the preregistered reading rule (including nonlinearity check and `format_valid`/`accuracy` defense against *"self didn't learn anything"*).
   - Update `docs/research_plan.md` and `docs/paper/outline_20261116.md` with the user in the loop.
4. **Collaboration style:** Keep replies short, bite-sized, one step at a time (AI Research Partner Charter in `AGENTS.md`). Do not commit/push unless asked.
