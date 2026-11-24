# Qualitative & Taxonomy Inspection: `self` vs `human` (H3, Seeds 0 & 1)

**Sources inspected (2026-11-23):**
- `audit/trace_source_20261117/eval_{self,human}/tuned_interventions.jsonl` (Seed 0, 140 common items)
- `audit/trace_source_seed1_20261119/eval_{self,human}/tuned_interventions.jsonl` (Seed 1, 144 common items)

## 1. Robustness to Rounding/Approximation
Counting `broad_follows = {follows, follows_rounded, follows_approximate}` on common items still shows a clear advantage for `self`:
- **Seed 0:** `self` 132/140 (**94.3%**) vs `human` 120/140 (**85.7%**) — discordant pairs: **14 vs 2**
- **Seed 1:** `self` 137/144 (**95.1%**) vs `human` 128/144 (**88.9%**) — discordant pairs: **12 vs 3**

## 2. Three Drivers of the `human` Deficit
1. **Higher Reversion (`reverted`):**
   - Seed 0: `human` 13/209 (**6.2%**) vs `self` 7/227 (**3.1%**)
   - Seed 1: `human` 11/220 (**5.0%**) vs `self` 5/223 (**2.2%**)
   - Includes both **true reversion** (ignoring the edited `Calc` and recomputing from the problem text: `5813fb09ba0a0abd`, `12c10ca1619289e3`) and **rounding artifacts** (following the edited number to `.14` or `.5`, then rounding back to the original integer: `1744aa1b18785c05`, `40d08d216578338a`).
2. **Generation Collapse / Token-Limit Loops (`no_answer`):**
   - Seed 0: `human` **7/209** (~3.3%) vs `self` **1/227** (~0.4%)
   - Seed 1: `human` **7/220** (~3.2%) vs `self` **0/223** (0.0%)
   - Example: `242bde961e2d3931` (`human` enters a repetition loop until `max_tokens`).
3. **Measurement Artifact (`expected=None` $\to$ `moved`):**
   - Seed 0: `human` 17/209 (**8.1%**) vs `self` 4/227 (**1.8%**)
   - Seed 1: `human` 12/220 (**5.5%**) vs `self` 4/223 (**1.8%**)
   - When `human`'s original trace lacks a clean downstream `Calc` dependency graph, `expected` is `None`, making `follows` unachievable even when the continuation actually uses the edited value (e.g., `0ae35915a207a5ad`, where `human` computes `61` from `72` but is labeled `moved`).

## 3. Paper Note (EACL 2027 SRW 4-Page Short Paper & NCKH)
- **Analysis:** `self` improves step dependence mainly by reducing true reversion and preventing generation collapse (`no_answer`).
- **Limitations:** Disclose the `expected=None` and integer-rounding measurement artifacts transparently; verify whether the same pattern appears in `trace_dose_20261120` once all 10 cells finish.
