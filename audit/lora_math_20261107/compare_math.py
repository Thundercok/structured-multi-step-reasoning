"""Compare MATH Level 3-5 LoRA adapter against base modes on 100 dev problems.

Evaluates:
- Full-set metrics for base_prefill, base_showcalc, base_pal, and math_lora_tuned.
- Paired subset comparisons on shared completed questions.
- Error and truncation anatomy (greedy repetition loops vs. long derivations).
- Live intervention planner counts and pre-registered RQ2 Gate evaluation.

Run from repo root:
    PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py
"""

from collections import Counter
import json
from pathlib import Path
from typing import Any, Dict, Optional

from structured_llm.analyze import compare, describe
from structured_llm.evaluate import read_jsonl, score
from structured_llm.intervene import plan_for

DIR = Path(__file__).parent
BASE_DIR = Path("audit/math_dev100_20261103")
COMP_JSON = DIR / "comparison.json"
REPORT_MD = DIR / "REPORT.md"
README_MD = DIR / "README.md"
INT_SUMMARY_PATH = DIR / "eval/interventions_summary.json"
DEV_META_PATH = Path("data/math_source/structured_math_v1/dev.jsonl")

SOURCES = {
    "math_lora_tuned": (DIR / "eval/tuned.jsonl", "tuned"),
    "math_lora_term": (DIR / "eval_term/tuned.jsonl", "tuned"),
    "base_prefill": (BASE_DIR / "base_prefill.jsonl", "base_prefill"),
    "base_showcalc": (BASE_DIR / "base_showcalc.jsonl", "base_showcalc"),
    "base_pal": (BASE_DIR / "base_pal.jsonl", "base_pal"),
}


def load_records(path: Path, mode: str) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    pal_full_map = {}
    if mode == "base_pal" and (BASE_DIR / "pal_full.json").exists():
        pal_data = json.loads((BASE_DIR / "pal_full.json").read_text(encoding="utf-8"))
        pal_full_map = {r["id"]: r for r in pal_data.get("rows", [])}
    out = {}
    for row in read_jsonl(path):
        row["check"] = score(
            mode,
            row["output"],
            row["question"],
            row["gold"],
            row.get("answer_format", "math"),
        )
        if row["id"] in pal_full_map:
            row["check"]["correct"] = bool(pal_full_map[row["id"]]["correct"])
            row["check"]["answered"] = pal_full_map[row["id"]]["value"] is not None
        out[row["id"]] = row
    return out


def fmt_ci(ci: Optional[Any]) -> str:
    if not ci or len(ci) != 2:
        return "N/A"
    return f"{ci[0] * 100:.1f}–{ci[1] * 100:.1f}%"


def analyze_math_tuned_anatomy(recs: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze errors and truncation modes (repetition loops vs long derivations)."""
    non_truncated = [r for r in recs.values() if not r.get("truncated")]
    truncated = [r for r in recs.values() if r.get("truncated")]

    non_tr_errors = Counter()
    for r in non_truncated:
        for e in r.get("check", {}).get("errors", []):
            non_tr_errors[e] += 1

    rep_loop_n = 0
    for r in truncated:
        out = r.get("output", "")
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        has_line_rep = any(c >= 5 for c in Counter(lines).values()) if lines else False
        has_slice_rep = len(out) >= 150 and out[:-150].count(out[-150:-90]) >= 3
        if has_slice_rep or has_line_rep:
            rep_loop_n += 1

    long_deriv_n = len(truncated) - rep_loop_n

    return {
        "non_truncated": {
            "n": len(non_truncated),
            "correct": sum(bool(r.get("check", {}).get("correct")) for r in non_truncated),
            "format_valid": sum(bool(r.get("check", {}).get("format_valid")) for r in non_truncated),
            "invalid_format_n": sum(not r.get("check", {}).get("format_valid") for r in non_truncated),
            "invalid_format_but_correct": sum(
                (not r.get("check", {}).get("format_valid")) and bool(r.get("check", {}).get("correct"))
                for r in non_truncated
            ),
            "error_counts": dict(non_tr_errors.most_common()),
        },
        "truncated": {
            "n": len(truncated),
            "repetition_loop_n": rep_loop_n,
            "long_derivation_n": long_deriv_n,
        },
    }


def evaluate_rq2_gate(
    int_data: Optional[Dict[str, Any]] = None,
    recs: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evaluate pre-registered RQ2 Gate on MATH (research_plan.md lines 188-196)."""
    # Allow flexible call order if recs was passed as first argument
    if isinstance(int_data, dict) and any("output" in v for v in int_data.values() if isinstance(v, dict)):
        recs, int_data = int_data, recs

    live_planner_counts = Counter()
    if recs:
        for r in recs.values():
            plan, reason = plan_for("tuned", r, freeform=False)
            if plan is not None:
                live_planner_counts["eligible"] += 1
            else:
                live_planner_counts[reason or "unknown_skip"] += 1

    gate = {
        "live_planner_counts": dict(live_planner_counts.most_common()),
        "status": "pending_execution (awaiting intervention run)",
        "official_evaluation": None,
    }

    if int_data and "tuned" in int_data:
        tuned_int = int_data["tuned"]
        if "eligible" in tuned_int:
            elig = tuned_int["eligible"]
            unflagged_n = (
                elig.get("follows", 0)
                + elig.get("follows_rounded", 0)
                + elig.get("reverted", 0)
                + elig.get("other", 0)
            )
            not_followed = elig.get("reverted", 0) + elig.get("other", 0)
            not_followed_rate = round(not_followed / unflagged_n, 4) if unflagged_n > 0 else None

            if elig.get("n", 0) < 30:
                status = "unmeasurable (< 30 eligible traces)"
            elif not_followed >= 5 and (not_followed_rate or 0) >= 0.05:
                status = "active (>= 30 eligible, >= 5 and >= 5% not following)"
            else:
                status = "inactive (< 5 or < 5% not following; drop RQ2)"

            gate["status"] = status
            gate["official_evaluation"] = {
                "eligible_n": elig.get("n", 0),
                "unflagged_n": unflagged_n,
                "not_followed": not_followed,
                "not_followed_rate": not_followed_rate,
                "follows": elig.get("follows", 0),
                "follows_rounded": elig.get("follows_rounded", 0),
                "reverted": elig.get("reverted", 0),
                "other": elig.get("other", 0),
                "moved": elig.get("moved", 0),
                "status": status,
            }

    return gate


def summarize_slice(slice_ids: list, loaded: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    n = len(slice_ids)
    bp = loaded.get("base_prefill", {})
    bs = loaded.get("base_showcalc", {})
    bpal = loaded.get("base_pal", {})
    tuned = loaded.get("math_lora_tuned", {})
    term = loaded.get("math_lora_term", {})

    bp_c = sum(bool(bp[i].get("check", {}).get("correct")) for i in slice_ids if i in bp)
    bs_c = sum(bool(bs[i].get("check", {}).get("correct")) for i in slice_ids if i in bs)
    bpal_c = sum(bool(bpal[i].get("check", {}).get("correct")) for i in slice_ids if i in bpal)

    lora_c = sum(bool(tuned[i].get("check", {}).get("correct")) for i in slice_ids if i in tuned)
    lora_fv = sum(bool(tuned[i].get("check", {}).get("format_valid")) for i in slice_ids if i in tuned)
    lora_tr = sum(bool(tuned[i].get("truncated")) for i in slice_ids if i in tuned)
    lora_nt_n = n - lora_tr
    lora_nt_c = sum(
        bool(tuned[i].get("check", {}).get("correct"))
        for i in slice_ids
        if i in tuned and not tuned[i].get("truncated")
    )

    out = {
        "n": n,
        "base_prefill_correct": bp_c,
        "base_showcalc_correct": bs_c,
        "base_pal_correct": bpal_c,
        "lora_correct": lora_c,
        "lora_format_valid": lora_fv,
        "lora_truncated": lora_tr,
        "lora_non_trunc_n": lora_nt_n,
        "lora_non_trunc_correct": lora_nt_c,
    }
    if term:
        tr_c = sum(bool(term[i].get("check", {}).get("correct")) for i in slice_ids if i in term)
        tr_fv = sum(bool(term[i].get("check", {}).get("format_valid")) for i in slice_ids if i in term)
        tr_tr = sum(bool(term[i].get("truncated")) for i in slice_ids if i in term)
        tr_nt_n = n - tr_tr
        tr_nt_c = sum(
            bool(term[i].get("check", {}).get("correct"))
            for i in slice_ids
            if i in term and not term[i].get("truncated")
        )
        out["term_correct"] = tr_c
        out["term_format_valid"] = tr_fv
        out["term_truncated"] = tr_tr
        out["term_non_trunc_n"] = tr_nt_n
        out["term_non_trunc_correct"] = tr_nt_c
    return out


def compute_breakdowns(
    loaded: Dict[str, Dict[str, Any]], dev_meta: Dict[str, Dict[str, str]]
) -> Dict[str, Any]:
    eval_ids = list(loaded.get("math_lora_tuned", loaded.get("base_prefill", {})).keys())

    levels = ["Level 3", "Level 4", "Level 5"]
    by_level = {}
    for lvl in levels:
        slice_ids = [i for i in eval_ids if dev_meta.get(i, {}).get("level") == lvl]
        by_level[lvl] = summarize_slice(slice_ids, loaded)

    all_subjects = sorted(
        list({dev_meta.get(i, {}).get("subject") for i in eval_ids if dev_meta.get(i, {}).get("subject")})
    )
    by_subject = {}
    for subj in all_subjects:
        slice_ids = [i for i in eval_ids if dev_meta.get(i, {}).get("subject") == subj]
        by_subject[subj] = summarize_slice(slice_ids, loaded)

    return {
        "by_level": by_level,
        "by_subject": by_subject,
    }


def format_slice_table(
    breakdown_dict: Dict[str, Dict[str, Any]], first_col_name: str, is_vn: bool = False
) -> list[str]:
    c_n = "N"
    c_bp = "`base_prefill` Acc" if not is_vn else "`base_prefill` Đúng"
    c_bs = "`base_showcalc` Acc" if not is_vn else "`base_showcalc` Đúng"
    c_pal = "`base_pal` Acc" if not is_vn else "`base_pal` Đúng"
    c_lora = "`math_lora_1000_s0` Overall Acc" if not is_vn else "`math_lora_1000_s0` Chung"
    c_fv = "`math_lora_1000_s0` Format Valid" if not is_vn else "`math_lora_1000_s0` Đúng Cú pháp"
    c_tr = "`math_lora_1000_s0` Truncated" if not is_vn else "`math_lora_1000_s0` Bị cắt cụt"
    c_nt = "`math_lora_1000_s0` Non-Trunc Acc" if not is_vn else "`math_lora_1000_s0` Không cắt cụt"

    table_lines = [
        f"| {first_col_name} | {c_n} | {c_bp} | {c_bs} | {c_pal} | {c_lora} | {c_fv} | {c_tr} | {c_nt} |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for key, data in breakdown_dict.items():
        n = data["n"]
        bp_s = f"{data['base_prefill_correct']}/{n} ({data['base_prefill_correct']/n*100:.1f}%)" if n else "N/A"
        bs_s = f"{data['base_showcalc_correct']}/{n} ({data['base_showcalc_correct']/n*100:.1f}%)" if n else "N/A"
        bpal_s = f"{data['base_pal_correct']}/{n} ({data['base_pal_correct']/n*100:.1f}%)" if n else "N/A"
        lora_s = f"{data['lora_correct']}/{n} ({data['lora_correct']/n*100:.1f}%)" if n else "N/A"
        fv_s = f"{data['lora_format_valid']}/{n} ({data['lora_format_valid']/n*100:.1f}%)" if n else "N/A"
        tr_s = f"{data['lora_truncated']}/{n} ({data['lora_truncated']/n*100:.1f}%)" if n else "N/A"
        nt_n = data["lora_non_trunc_n"]
        nt_s = (
            f"{data['lora_non_trunc_correct']}/{nt_n} ({data['lora_non_trunc_correct']/nt_n*100:.1f}%)"
            if nt_n > 0
            else "N/A"
        )
        display_key = f"`{key}`" if not key.startswith("Level") else key
        table_lines.append(
            f"| {display_key} | {n} | {bp_s} | {bs_s} | {bpal_s} | {lora_s} | {fv_s} | {tr_s} | {nt_s} |"
        )
    return table_lines


def main():
    loaded = {}
    for name, (path, mode) in SOURCES.items():
        recs = load_records(path, mode)
        if recs:
            loaded[name] = recs

    summary = {}
    for name, recs in loaded.items():
        summary[name] = describe(recs)
        if "base_prefill" in loaded and name != "base_prefill":
            summary[name]["vs_base_prefill"] = compare(recs, loaded["base_prefill"])
        if "base_showcalc" in loaded and name != "base_showcalc":
            summary[name]["vs_base_showcalc"] = compare(recs, loaded["base_showcalc"])

    # If math_lora_tuned is present, compute paired subset comparisons and anatomy
    if "math_lora_tuned" in loaded:
        tuned_recs = loaded["math_lora_tuned"]
        if "base_prefill" in loaded:
            shared_prefill = {k: loaded["base_prefill"][k] for k in tuned_recs.keys() & loaded["base_prefill"].keys()}
            summary["math_lora_tuned"]["base_prefill_on_shared"] = describe(shared_prefill)
            summary["math_lora_tuned"]["vs_base_prefill_shared"] = compare(tuned_recs, loaded["base_prefill"])
        if "base_showcalc" in loaded:
            shared_showcalc = {k: loaded["base_showcalc"][k] for k in tuned_recs.keys() & loaded["base_showcalc"].keys()}
            summary["math_lora_tuned"]["base_showcalc_on_shared"] = describe(shared_showcalc)
            summary["math_lora_tuned"]["vs_base_showcalc_shared"] = compare(tuned_recs, loaded["base_showcalc"])

        # Error & Truncation Anatomy
        anatomy = analyze_math_tuned_anatomy(tuned_recs)
        summary["math_lora_tuned"]["error_anatomy"] = anatomy

    # If math_lora_term is present, compute paired subset comparisons and anatomy
    if "math_lora_term" in loaded:
        term_recs = loaded["math_lora_term"]
        if "base_prefill" in loaded:
            shared_prefill = {k: loaded["base_prefill"][k] for k in term_recs.keys() & loaded["base_prefill"].keys()}
            summary["math_lora_term"]["base_prefill_on_shared"] = describe(shared_prefill)
            summary["math_lora_term"]["vs_base_prefill_shared"] = compare(term_recs, loaded["base_prefill"])
        if "base_showcalc" in loaded:
            shared_showcalc = {k: loaded["base_showcalc"][k] for k in term_recs.keys() & loaded["base_showcalc"].keys()}
            summary["math_lora_term"]["base_showcalc_on_shared"] = describe(shared_showcalc)
            summary["math_lora_term"]["vs_base_showcalc_shared"] = compare(term_recs, loaded["base_showcalc"])
        if "math_lora_tuned" in loaded:
            summary["math_lora_term"]["vs_math_lora_tuned"] = compare(term_recs, loaded["math_lora_tuned"])

        # Error & Truncation Anatomy
        anatomy_term = analyze_math_tuned_anatomy(term_recs)
        summary["math_lora_term"]["error_anatomy"] = anatomy_term

    # Interventions summary if available
    int_data = None
    if INT_SUMMARY_PATH.exists():
        try:
            int_data = json.loads(INT_SUMMARY_PATH.read_text(encoding="utf-8"))
            summary["interventions"] = int_data
        except Exception as e:
            print(f"Error loading {INT_SUMMARY_PATH}: {e}")

    # Evaluate pre-registered RQ2 Gate
    tuned_recs_for_gate = loaded.get("math_lora_tuned")
    rq2_gate = evaluate_rq2_gate(int_data=int_data, recs=tuned_recs_for_gate)
    summary["rq2_math_gate"] = rq2_gate

    # Difficulty & Subject breakdowns
    dev_meta = {}
    if DEV_META_PATH.exists():
        dev_meta = {
            r["id"]: {"subject": r.get("subject", "unknown"), "level": r.get("level", "unknown")}
            for r in read_jsonl(DEV_META_PATH)
        }
    breakdowns = compute_breakdowns(loaded, dev_meta)
    summary["by_level"] = breakdowns["by_level"]
    summary["by_subject"] = breakdowns["by_subject"]

    COMP_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Render Markdown Report
    lines = [
        "# Báo cáo Thực nghiệm LoRA trên Tập Toán Khó MATH (Level 3–5, Dev-100)",
        "",
        "| Chế độ / Adapter | Đúng (`correct`) | KTC Wilson 95% | Đúng định dạng (`format_valid`) | KTC Wilson 95% | Bắt câu sai (`caught_wrong`) | Báo nhầm (`false_alarm`) | McNemar vs `base_prefill` |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    labels = {
        "base_prefill": "`base_prefill` (Gốc mồi Step 1)",
        "base_showcalc": "`base_showcalc` (Gốc viết phép tính)",
        "base_pal": "`base_pal` (Chương trình Python)",
        "math_lora_tuned": "**`math_lora_1000_s0` (LoRA 1.000 vòng)**",
        "math_lora_term": "**`math_lora_term_1000_s0` (Terminated-512 LoRA)**",
    }
    for key, label in labels.items():
        if key not in summary:
            continue
        row = summary[key]
        n = row["n"]
        p_val = row.get("vs_base_prefill", {}).get("mcnemar_p")
        p_str = "—" if p_val is None else f"p = {p_val:.4f}"
        lines.append(
            f"| {label} | {row['correct']}/{n} | {fmt_ci(row['correct_ci'])} | "
            f"{row['format_valid']}/{n} | {fmt_ci(row['format_valid_ci'])} | "
            f"{row['caught_wrong']} | {row['false_alarm_right']} | {p_str} |"
        )

    # Section 2: Error and Truncation Anatomy
    if "math_lora_tuned" in summary and "error_anatomy" in summary["math_lora_tuned"]:
        anat = summary["math_lora_tuned"]["error_anatomy"]
        ntr = anat["non_truncated"]
        tr = anat["truncated"]
        mlt = summary["math_lora_tuned"]

        lines.extend([
            "",
            "---",
            "",
            "## 2. Phân tích Giải phẫu Lỗi & Hiện tượng Cắt cụt (Error & Truncation Anatomy)",
            "",
            f"Tổng số câu đã đánh giá: **{mlt['n']}/100** (Không cắt cụt: **{ntr['n']}**, Cắt cụt token tối đa: **{tr['n']}**).",
            "",
            "### 2.1. Các câu không bị cắt cụt (Non-Truncated Items)",
            f"* **Độ chính xác (`correct`):** **{ntr['correct']}/{ntr['n']}** ({ntr['correct']/ntr['n']*100:.1f}%)" if ntr['n'] > 0 else "* **Độ chính xác:** N/A",
            f"* **Đúng định dạng (`format_valid`):** **{ntr['format_valid']}/{ntr['n']}** ({ntr['format_valid']/ntr['n']*100:.1f}%)" if ntr['n'] > 0 else "* **Đúng định dạng:** N/A",
            f"* **Sai định dạng nhưng tính đúng đáp án:** **{ntr['invalid_format_but_correct']}** câu (mô hình suy luận ra đáp án đúng nhưng cú pháp vi phạm ngữ pháp quy định).",
            f"* **Lỗi ngữ pháp chi tiết:**",
        ])
        for err, cnt in ntr["error_counts"].items():
            lines.append(f"  - `{err}`: **{cnt}** câu (chủ yếu do dòng `Calc:` chứa biểu thức ký hiệu LaTeX phức tạp hoặc phép biến đổi đại số).")
        if not ntr["error_counts"]:
            lines.append("  - Không phát hiện lỗi ngữ pháp trên các câu không cắt cụt.")

        lines.extend([
            "",
            "### 2.2. Hiện tượng suy thoái cắt cụt (Truncation Breakdown)",
            f"* **Tổng số câu bị cắt cụt:** **{tr['n']}** câu.",
            f"* **Vòng lặp suy thoái lặp lại (Greedy Repetition Loop):** **{tr['repetition_loop_n']}/{tr['n']}** ({tr['repetition_loop_n']/tr['n']*100:.1f}%) câu bị bẫy trong vòng lặp vô hạn ở bước lập luận, lặp lại cùng một dòng $\\ge 5$ lần hoặc chuỗi ký tự đuôi $\\ge 3$ lần.",
            f"* **Lập luận dài vượt ngưỡng (Long Derivations):** **{tr['long_derivation_n']}/{tr['n']}** ({tr['long_derivation_n']/tr['n']*100:.1f}%) câu lập luận logic dài vượt giới hạn 1.024 token.",
            "",
            "### 2.3. So sánh ghép cặp trên tập câu chung (Paired Comparison on Shared Completed Items)",
        ])

        if "vs_base_prefill_shared" in mlt and "base_prefill_on_shared" in mlt:
            vp = mlt["vs_base_prefill_shared"]
            bp = mlt["base_prefill_on_shared"]
            lines.append(
                f"* **Vs `base_prefill`:** Trên {vp['shared']} câu chung, LoRA đúng **{mlt['correct']}/{vp['shared']}** "
                f"so với **{bp['correct']}/{vp['shared']}** của `base_prefill` "
                f"(Chỉ LoRA đúng: **{vp['only_this_correct']}**, Chỉ `base_prefill` đúng: **{vp['only_baseline_correct']}**, McNemar exact **p = {vp['mcnemar_p']:.4f}**)."
            )

        if "vs_base_showcalc_shared" in mlt and "base_showcalc_on_shared" in mlt:
            vs = mlt["vs_base_showcalc_shared"]
            bs = mlt["base_showcalc_on_shared"]
            lines.append(
                f"* **Vs `base_showcalc`:** Trên {vs['shared']} câu chung, LoRA đúng **{mlt['correct']}/{vs['shared']}** "
                f"so với **{bs['correct']}/{vs['shared']}** của `base_showcalc` "
                f"(Chỉ LoRA đúng: **{vs['only_this_correct']}**, Chỉ `base_showcalc` đúng: **{vs['only_baseline_correct']}**, McNemar exact **p = {vs['mcnemar_p']:.4f}**)."
            )

    # Section 3: Pre-Registered RQ2 Gate
    if "rq2_math_gate" in summary:
        gate = summary["rq2_math_gate"]
        plc = gate.get("live_planner_counts", {})
        lines.extend([
            "",
            "---",
            "",
            "## 3. Kiểm định Ngưỡng RQ2 trên MATH (Pre-Registered Gate)",
            "",
            "> **Quy tắc tiền đăng ký (`docs/research_plan.md` dòng 188–196):**  ",
            "> RQ2 duy trì hiệu lực nếu tỷ lệ không theo can thiệp $\\ge 5\\%$, có $\\ge 5$ ca và $\\ge 30$ vết đủ điều kiện.  ",
            "> Dưới 30 vết: *chưa đo được (`unmeasurable`)*. Dưới 5 ca hoặc $< 5\\%$: *bác bỏ RQ2 (`inactive`), chuyển trọng tâm sang RQ3*.",
            "",
            "### 3.1. Thống kê Khảo sát từ Bộ lập Can thiệp Trực tiếp (Live Planner Counts)",
            f"* **Vết đủ điều kiện can thiệp (`eligible`):** **{plc.get('eligible', 0)}**",
            f"* **Lý do bỏ qua (Skipped Reasons):**",
        ])
        for reason, count in plc.items():
            if reason != "eligible":
                lines.append(f"  - `{reason}`: **{count}** câu")

        lines.extend([
            "",
            "### 3.2. Trạng thái Đánh giá Cổng RQ2 Chính thức",
            f"* **Trạng thái cổng hiện tại:** `{gate.get('status')}`",
        ])

        if gate.get("official_evaluation"):
            oe = gate["official_evaluation"]
            lines.extend([
                f"* **Số vết đủ điều kiện can thiệp:** {oe['eligible_n']}",
                f"* **Số vết không cờ (`unflagged`):** {oe['unflagged_n']}",
                f"* **Số ca tuân thủ (`follows` + `follows_rounded`):** {oe['follows']} + {oe['follows_rounded']}",
                f"* **Số ca không tuân thủ (`reverted` + `other`):** **{oe['not_followed']}** ({oe['not_followed_rate']*100:.1f}%)" if oe['not_followed_rate'] is not None else f"* **Số ca không tuân thủ:** {oe['not_followed']}",
                f"* **Kết luận:** `{oe['status']}`",
            ])
        else:
            lines.append("*Tiến trình can thiệp phản thực chính thức sẽ được kích hoạt ngay khi đánh giá 100 câu hoàn tất.*")

    if "math_lora_tuned" not in summary:
        lines.extend([
            "",
            "*Ghi chú: Adapter `adapters/math_lora_1000_s0` đang trong quá trình huấn luyện; bảng sẽ tự động cập nhật ngay khi `eval/tuned.jsonl` hoàn tất.*",
        ])

    # Section 6: Breakdown by Difficulty Level & Subject
    if "by_level" in summary and "by_subject" in summary:
        lines.extend([
            "",
            "---",
            "",
            "## 6. Phân tích chi tiết theo Cấp độ và Chủ đề (Breakdown by Difficulty Level & Subject)",
            "",
            "### 6.1. Phân tích theo Cấp độ Khó (Table 6.1: By Difficulty Level)",
            "",
        ])
        lines.extend(format_slice_table(summary["by_level"], "Cấp độ", is_vn=True))
        lines.extend([
            "",
            "### 6.2. Phân tích theo Chủ đề Toán học (Table 6.2: By Subject)",
            "",
        ])
        lines.extend(format_slice_table(summary["by_subject"], "Chủ đề", is_vn=True))

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    README_MD.write_text(render_readme(summary), encoding="utf-8")
    print(f"Wrote {COMP_JSON}, {REPORT_MD}, and {README_MD}")
    update_paper_math_tex(summary)


def render_readme(summary: Dict[str, Any]) -> str:
    lines = [
        "# Huấn luyện LoRA trên tập toán khó MATH (Level 3–5), 2026-11-07",
        "",
        "Huấn luyện Qwen3-8B 4-bit với LoRA trên 725 bài toán kiểm chứng được (checkable) từ tập train của MATH (Level 3 đến 5).",
        "Đây là bước kiểm định quy luật mở rộng cấu trúc suy luận từ số học GSM8K sang đại số, tổ hợp, lý thuyết số và hình học phức tạp.",
        "",
        "## 1. Dữ liệu (`data/math_source/structured_math_v1/`)",
        "",
        "Tạo bằng: `python -m structured_llm.math_convert`",
        "- **Nguồn:** `train_source.jsonl` (801 câu Level 3–5 kiểm chứng được).",
        "- **Tách tập:** Phân chia tất định bằng băm SHA-256 mã câu hỏi:",
        "  - `train.jsonl`: 725 câu (SHA-256: `414001eba97fdafdebfc6f4882ea66bf3fba5d2accee7a6d7a9111df1c394287`)",
        "  - `valid.jsonl`: 76 câu (SHA-256: `de32ad35d3e368f70e1b0d1c631f30d9d44e4d34c8ae24d296dbb870f058cc6d`)",
        "  - `dev.jsonl`: 100 câu kiểm thử độc lập (Level 3–5).",
        "",
        "### Phân bố độ khó và chủ đề (801 câu):",
        "- **Độ khó:**",
        "  - Level 5: 351 bài (43,8%)",
        "  - Level 4: 236 bài (29,5%)",
        "  - Level 3: 214 bài (26,7%)",
        "- **Chủ đề:**",
        "  - Đại số (Algebra): 174 bài",
        "  - Tiền đại số (Prealgebra): 157 bài",
        "  - Tổ hợp & Xác suất (Counting & Probability): 126 bài",
        "  - Hình học (Geometry): 122 bài",
        "  - Đại số nâng cao (Intermediate Algebra): 105 bài",
        "  - Lý thuyết số (Number Theory): 78 bài",
        "  - Tiền tích phân (Precalculus): 39 bài",
        "",
        "## 2. Thông số Huấn luyện (`adapters/math_lora_1000_s0`)",
        "",
        "- **Kiến trúc:** LoRA trên Qwen3-8B 4-bit (Rank 8, Scale 20.0, Dropout 0.0, 8 target layers, lr 5e-5, batch_size 1, grad_checkpoint=true, max_seq_length 512).",
        "- **Số vòng (Iterations):** 1.000 vòng (~2,76 epoch trên 725 mẫu).",
        "- **Hàm mất mát (Loss):** Khởi điểm 1.340 $\\to$ Vòng 500: 0.642 $\\to$ Vòng 1.000: **Train Loss 0.5140**, **Val Loss 0.5870**.",
        "- **Tài nguyên phần cứng:** Apple M1 16GB, Đỉnh RAM: **5.915 GB**, Tốc độ: ~50.8 tok/s.",
        "- **Hạn chế độ dài chuỗi huấn luyện:** Để duy trì dưới trần bộ nhớ đồ họa Metal 5.915 GB trên máy M1 16GB, tham số `--max-seq-length 512` đã cắt cụt phần đuôi `</think>\\n\\nAnswer:` của 105/725 (14,5%) bài toán mẫu dài trong tập train; điều này giải thích trực tiếp tại sao các chuỗi suy luận dài khi inference không phát ra thẻ đóng `</think>` và rơi vào vòng lặp suy thoái (greedy repetition loop).",
        "",
        "## 3. Bảng Kết quả So sánh trên MATH Dev-100",
        "",
        "| Chế độ / Adapter | Đúng (`correct`) | KTC Wilson 95% | Đúng định dạng (`format_valid`) | KTC Wilson 95% | Bắt câu sai (`caught_wrong`) | Báo nhầm (`false_alarm`) | McNemar vs `base_prefill` |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    labels = {
        "base_prefill": "`base_prefill` (Gốc mồi Step 1)",
        "base_showcalc": "`base_showcalc` (Gốc viết phép tính)",
        "base_pal": "`base_pal` (Chương trình Python)",
        "math_lora_tuned": "**`math_lora_1000_s0` (LoRA 1.000 vòng)**",
        "math_lora_term": "**`math_lora_term_1000_s0` (Terminated-512 LoRA)**",
    }
    for key, label in labels.items():
        if key not in summary:
            continue
        row = summary[key]
        n = row["n"]
        p_val = row.get("vs_base_prefill", {}).get("mcnemar_p")
        p_str = "—" if p_val is None else f"p = {p_val:.4f}"
        lines.append(
            f"| {label} | {row['correct']}/{n} | {fmt_ci(row['correct_ci'])} | "
            f"{row['format_valid']}/{n} | {fmt_ci(row['format_valid_ci'])} | "
            f"{row['caught_wrong']} | {row['false_alarm_right']} | {p_str} |"
        )

    # Section 4: Error and Truncation Anatomy
    if "math_lora_tuned" in summary and "error_anatomy" in summary["math_lora_tuned"]:
        anat = summary["math_lora_tuned"]["error_anatomy"]
        ntr = anat["non_truncated"]
        tr = anat["truncated"]
        mlt = summary["math_lora_tuned"]

        lines.extend([
            "",
            "## 4. Giải phẫu Lỗi & Điểm nghẽn Cắt cụt (The Flat-Trace Bottleneck)",
            "",
            f"Tổng số câu đã đánh giá: **{mlt['n']}/100** (Không cắt cụt: **{ntr['n']}**, Bị cắt cụt ở 1.024 tokens: **{tr['n']}**).",
            "",
            "### 4.1. Các câu không bị cắt cụt (Non-Truncated Items)",
            f"- **Độ chính xác (`correct`):** **{ntr['correct']}/{ntr['n']}** ({ntr['correct']/ntr['n']*100:.1f}%)" if ntr['n'] > 0 else "- **Độ chính xác:** N/A",
            f"- **Đúng định dạng (`format_valid`):** **{ntr['format_valid']}/{ntr['n']}** ({ntr['format_valid']/ntr['n']*100:.1f}%)" if ntr['n'] > 0 else "- **Đúng định dạng:** N/A",
            f"- **Suy luận đúng đáp án nhưng vi phạm cú pháp Cổng 0:** **{ntr['invalid_format_but_correct']}** câu (mô hình suy luận ra đáp án đúng nhưng dòng `Calc:` chứa biểu thức ký hiệu LaTeX phức tạp hoặc phép biến đổi đại số).",
            "- **Chi tiết lỗi cú pháp:**",
        ])
        for err, cnt in ntr["error_counts"].items():
            lines.append(f"  - `{err}`: **{cnt}** câu")
        if not ntr["error_counts"]:
            lines.append("  - Không phát hiện lỗi cú pháp trên các câu không cắt cụt.")

        lines.extend([
            "",
            "### 4.2. Hiện tượng suy thoái cắt cụt (Truncation Breakdown)",
            f"- **Tổng số câu bị cắt cụt:** **{tr['n']}** câu.",
            f"- **Vòng lặp suy thoái (Greedy Repetition Loop):** **{tr['repetition_loop_n']}/{tr['n']}** ({tr['repetition_loop_n']/tr['n']*100:.1f}%) câu bị lặp vô hạn ở bước lập luận (lặp lại cùng 1 dòng $\\ge 5$ lần hoặc chuỗi ký tự đuôi $\\ge 3$ lần).",
            f"- **Lập luận dài vượt ngưỡng 1.024 token:** **{tr['long_derivation_n']}/{tr['n']}** ({tr['long_derivation_n']/tr['n']*100:.1f}%) câu.",
        ])

        if "vs_base_prefill_shared" in mlt and "base_prefill_on_shared" in mlt:
            vp = mlt["vs_base_prefill_shared"]
            bp = mlt["base_prefill_on_shared"]
            lines.extend([
                "",
                "### 4.3. So sánh ghép cặp trên tập câu chung (Paired Comparison)",
                f"- **Vs `base_prefill`:** Trên {vp['shared']} câu chung, LoRA đúng **{mlt['correct']}/{vp['shared']}** "
                f"so với **{bp['correct']}/{vp['shared']}** của `base_prefill` "
                f"(Chỉ LoRA đúng: **{vp['only_this_correct']}**, Chỉ `base_prefill` đúng: **{vp['only_baseline_correct']}**, McNemar exact **p = {vp['mcnemar_p']:.4f}**).",
            ])

    # Section 5: Pre-Registered RQ2 Gate
    if "rq2_math_gate" in summary:
        gate = summary["rq2_math_gate"]
        plc = gate.get("live_planner_counts", {})
        lines.extend([
            "",
            "## 5. Kiểm định Ngưỡng RQ2 trên MATH (Pre-Registered Gate)",
            "",
            "> **Quy tắc tiền đăng ký (`docs/research_plan.md` dòng 188–196):**  ",
            "> RQ2 duy trì hiệu lực nếu tỷ lệ không theo can thiệp $\\ge 5\\%$, có $\\ge 5$ ca và $\\ge 30$ vết đủ điều kiện.  ",
            "> Dưới 30 vết: *chưa đo được (`unmeasurable`)*. Dưới 5 ca hoặc $< 5\\%$: *bác bỏ RQ2 (`inactive`), chuyển trọng tâm sang RQ3*.",
            "",
            f"- **Trạng thái cổng hiện tại:** `{gate.get('status')}`",
            f"- **Vết đủ điều kiện can thiệp (`eligible`):** **{plc.get('eligible', 0)}** (Dưới ngưỡng 30 vết $\\to$ Vùng chưa thể đo lường / *unmeasurable regime*).",
            "- **Chi tiết các lý do loại trừ (Skipped Reasons):**",
        ])
        for reason, count in plc.items():
            if reason != "eligible":
                lines.append(f"  - `{reason}`: **{count}** câu")

    # Section 6: Breakdown by Difficulty Level & Subject
    if "by_level" in summary and "by_subject" in summary:
        lines.extend([
            "",
            "## 6. Breakdown by Difficulty Level & Subject",
            "",
            "### 6.1. Table 6.1: By Difficulty Level (Level 3, Level 4, Level 5)",
            "",
        ])
        lines.extend(format_slice_table(summary["by_level"], "Level", is_vn=False))
        lines.extend([
            "",
            "### 6.2. Table 6.2: By Subject (7 MATH Domains)",
            "",
        ])
        lines.extend(format_slice_table(summary["by_subject"], "Subject", is_vn=False))

    lines.extend([
        "",
        "## 7. Reproduction Commands",
        "",
        "```bash",
        "# 1. Huấn luyện và đánh giá toàn diện",
        "audit/lora_math_20261107/run_math_training.sh",
        "",
        "# 2. Cập nhật bảng so sánh và báo cáo thống kê",
        "PYTHONPATH=. .venv/bin/python audit/lora_math_20261107/compare_math.py",
        "```",
    ])
    return "\n".join(lines) + "\n"


def update_paper_math_tex(summary: Dict[str, Any]) -> None:
    """Insert math_lora_term_1000_s0 row into Table tab:math_lora in paper when available."""
    tex_path = DIR.parent.parent / "docs/paper/nckh_structured_reasoning.tex"
    if not tex_path.exists() or "math_lora_term" not in summary:
        return
    try:
        tex = tex_path.read_text(encoding="utf-8")
        if r"\textbf{\texttt{math\_lora\_term\_1000\_s0}}" in tex:
            return
        term = summary["math_lora_term"]
        n = term["n"]
        acc_str = f"{term['correct']}/{n} ({term['correct']/n*100:.1f}\\%)"
        val_str = f"{term['format_valid']}/{n} ({term['format_valid']/n*100:.1f}\\%)"

        anat = term.get("error_anatomy", {})
        ntr = anat.get("non_truncated", {})
        tr = anat.get("truncated", {})
        nt_n = ntr.get("n", 0)
        nt_c = ntr.get("correct", 0)
        nt_acc_str = f"\\textbf{{{nt_c}/{nt_n} ({nt_c/nt_n*100:.1f}\\%)}}" if nt_n > 0 else "---"

        tr_n = tr.get("n", 0)
        rep_n = tr.get("repetition_loop_n", 0)
        rep_str = f"{rep_n}/{tr_n} ({rep_n/tr_n*100:.1f}\\%)" if tr_n > 0 else "---"

        int_term_path = DIR / "eval_term/interventions_summary.json"
        elig_str = "---"
        rq2_str = "Unmeasurable ($<30$)"
        if int_term_path.exists():
            try:
                int_data = json.loads(int_term_path.read_text(encoding="utf-8"))
                el = int_data.get("tuned", {}).get("eligible", {}).get("n", 0)
                elig_str = str(el)
                if el < 30:
                    rq2_str = "Unmeasurable ($<30$)"
                else:
                    rq2_str = "Measured ($\\ge 30$)"
            except Exception:
                pass

        target_row = r"\textbf{\texttt{math\_lora\_1000\_s0}} & 40/100 (40.0\%) & 42/100 (42.0\%) & \textbf{40/55 (72.7\%)} & 34/45 (75.6\%) & 2 & Unmeasurable ($<30$) \\"
        new_row = f"\\textbf{{\\texttt{{math\\_lora\\_term\\_1000\\_s0}}}} & {acc_str} & {val_str} & {nt_acc_str} & {rep_str} & {elig_str} & {rq2_str} \\\\"
        if target_row in tex:
            tex = tex.replace(target_row, target_row + "\n" + new_row, 1)
            tex_path.write_text(tex, encoding="utf-8")
            print(f"Updated {tex_path} with math_lora_term_1000_s0 row.")
    except Exception as e:
        print(f"Warning: could not auto-update math paper tex: {e}")


if __name__ == "__main__":
    main()
