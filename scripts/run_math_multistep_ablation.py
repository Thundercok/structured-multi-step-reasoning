"""Full Pipeline: MATH Multi-Step Ablation (Training + Evaluation + Comparative Diagnostics)

Tests Hypothesis 1 from docs/ablation_math_multistep_spec.md:
Does removing 1-step examples from the training corpus resolve the Flat-Trace Bottleneck,
or is flat sequential reasoning inherently limited on competition mathematics?
"""

from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ADAPTER = ROOT / "adapters/math_lora_multistep_1000_s0"
DATA_DIR = ROOT / "data/math_source/structured_math_multistep_v1"
DEV_DATA = ROOT / "data/math_source/structured_math_v1/dev.jsonl"
OUT_DIR = ROOT / "audit/lora_math_multistep_20261109"
EVAL_DIR = OUT_DIR / "eval"
REPORT_MD = OUT_DIR / "REPORT.md"
BASELINE_FILE = ROOT / "audit/lora_math_20261107/eval/tuned.jsonl"


def run_training():
    print("=" * 70)
    print("PHASE 1: TRAINING ADAPTER (1,000 ITERS, MULTI-STEP DATA)")
    print("=" * 70)
    safetensors = ADAPTER / "adapters.safetensors"
    if safetensors.is_file():
        print(f"[Train] Found existing adapter at {safetensors}, skipping training.")
        return

    cmd = [
        "zsh",
        str(ROOT / "structured_llm/train.sh"),
        str(ADAPTER),
        "1000",
        str(DATA_DIR),
        "512",
        "0",
    ]
    print(f"[Train] Executing: {' '.join(cmd)}")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        raise RuntimeError(f"Training failed with exit code {res.returncode}")
    print(f"[Train] Completed in {(time.time() - t0) / 60:.1f} minutes.")


def run_evaluation():
    print("\n" + "=" * 70)
    print("PHASE 2: EVALUATION ON 100 MATH DEV PROBLEMS")
    print("=" * 70)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    tuned_file = EVAL_DIR / "tuned.jsonl"

    existing = [json.loads(l) for l in tuned_file.read_text().splitlines()] if tuned_file.is_file() else []
    if len(existing) == 100:
        print(f"[Eval] Found complete evaluation at {tuned_file} (100 items), skipping.")
        return existing

    cmd = [
        str(ROOT / ".venv/bin/python"),
        "-u",
        "-m",
        "structured_llm.evaluate",
        "--adapter",
        str(ADAPTER),
        "--data",
        str(DEV_DATA),
        "--out",
        str(EVAL_DIR),
        "--max-tokens",
        "1024",
    ]
    print(f"[Eval] Executing: {' '.join(cmd)}")
    t0 = time.time()
    res = subprocess.run(cmd, cwd=str(ROOT))
    if res.returncode != 0:
        raise RuntimeError(f"Evaluation failed with exit code {res.returncode}")
    print(f"[Eval] Completed in {(time.time() - t0) / 60:.1f} minutes.")
    return [json.loads(l) for l in tuned_file.read_text().splitlines()]


def analyze_records(records):
    non_truncated = [r for r in records if not r.get("truncated", False)]
    truncated = [r for r in records if r.get("truncated", False)]

    # Repetition loops check
    rep_loop_n = 0
    step_counts = Counter()
    for r in truncated:
        out = r.get("output", "")
        lines = [line.strip() for line in out.splitlines() if line.strip()]
        has_line_rep = any(c >= 5 for c in Counter(lines).values()) if lines else False
        has_slice_rep = len(out) >= 150 and out[:-150].count(out[-150:-90]) >= 3
        if has_slice_rep or has_line_rep:
            rep_loop_n += 1

        start = out.find("<think>")
        end = out.find("</think>")
        think_text = out[start:end] if (start != -1 and end != -1) else out[start:] if start != -1 else out
        steps = [l for l in think_text.splitlines() if l.strip().startswith("Step ")]
        step_counts[len(steps)] += 1

    return {
        "n": len(records),
        "correct": sum(bool(r.get("check", {}).get("correct")) for r in records),
        "format_valid": sum(bool(r.get("check", {}).get("format_valid")) for r in records),
        "non_truncated": {
            "n": len(non_truncated),
            "correct": sum(bool(r.get("check", {}).get("correct")) for r in non_truncated),
            "accuracy": round(sum(bool(r.get("check", {}).get("correct")) for r in non_truncated) / len(non_truncated) * 100, 2) if non_truncated else 0,
        },
        "truncated": {
            "n": len(truncated),
            "repetition_loops": rep_loop_n,
            "monologue_1step": step_counts[1],
            "step_distribution": dict(sorted(step_counts.items())),
        },
    }


def generate_comparative_report(ablation_recs):
    print("\n" + "=" * 70)
    print("PHASE 3: COMPARATIVE SCIENTIFIC ANALYSIS")
    print("=" * 70)
    baseline_recs = [json.loads(l) for l in BASELINE_FILE.read_text().splitlines() if l.strip()]

    base_stats = analyze_records(baseline_recs)
    ab_stats = analyze_records(ablation_recs)

    # Paired McNemar on Correct
    base_map = {r["id"]: bool(r["check"]["correct"]) for r in baseline_recs}
    ab_map = {r["id"]: bool(r["check"]["correct"]) for r in ablation_recs}
    common = sorted(set(base_map.keys()) & set(ab_map.keys()))

    n11, n01, n10, n00 = 0, 0, 0, 0
    for q in common:
        b = base_map[q]
        a = ab_map[q]
        if a and b:
            n11 += 1
        elif a and not b:
            n01 += 1  # Ablation only
        elif not a and b:
            n10 += 1  # Baseline only
        else:
            n00 += 1
    d_corr = n01 + n10
    p_corr = stats.binomtest(min(n01, n10), d_corr, 0.5).pvalue if d_corr > 0 else 1.0

    # Paired McNemar on Completion (Not Truncated)
    base_trunc = {r["id"]: bool(r.get("truncated", False)) for r in baseline_recs}
    ab_trunc = {r["id"]: bool(r.get("truncated", False)) for r in ablation_recs}
    t_n11, t_n01, t_n10, t_n00 = 0, 0, 0, 0
    for q in common:
        b_comp = not base_trunc[q]
        a_comp = not ab_trunc[q]
        if a_comp and b_comp:
            t_n11 += 1
        elif a_comp and not b_comp:
            t_n01 += 1  # Ablation completed, Baseline truncated
        elif not a_comp and b_comp:
            t_n10 += 1  # Baseline completed, Ablation truncated
        else:
            t_n00 += 1
    d_trunc = t_n01 + t_n10
    p_trunc = stats.binomtest(min(t_n01, t_n10), d_trunc, 0.5).pvalue if d_trunc > 0 else 1.0

    # Evaluate Disconfirmation Criteria from docs/ablation_math_multistep_spec.md
    # H1: 1-step monologue truncation drops from 29/45 (or 36/45) to < 10.
    # Disconfirmation: stays > 20.
    mono_count = ab_stats["truncated"]["monologue_1step"]
    if mono_count < 10:
        verdict = "**XÁC NHẬN GIẢ THUYẾT ($H_1$ CONFIRMED)**: Loại bỏ dữ liệu 1-Step đã giải quyết triệt để hiện tượng Step 1 độc thoại kéo dài, hạ số ca xuống < 10."
    elif mono_count > 20:
        verdict = "**BÁC BỎ GIẢ THUYẾT ($H_1$ DISCONFIRMED)**: Dù đã loại bỏ 100% mẫu 1-Step trong huấn luyện, mô hình vẫn biến `Step 1` thành độc thoại kéo dài (> 20 ca). Điều này chứng minh Flat-Trace Bottleneck là **giới hạn cấu trúc cố hữu của biểu diễn trace phẳng**, không phải lỗi lọc dữ liệu."
    else:
        verdict = "**KẾT QUẢ TRUNG GIAN (PARTIAL)**: Hiện tượng độc thoại giảm một phần (10 - 20 ca) nhưng chưa triệt để."

    report = f"""# Báo cáo Thử nghiệm Ablation: MATH Multi-Step vs. Baseline ($N=100$)

> Đề cương tiền đăng ký: `docs/ablation_math_multistep_spec.md`
> Thời gian tạo: {time.strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. Bảng Đo Lường Thực Nghiệm So Sánh

| Chỉ số | Baseline Control (`math_lora_1000_s0`) | Treatment Ablation (`math_lora_multistep_1000_s0`) | Độ lệch ($\Delta$) |
| :--- | :---: | :---: | :---: |
| **Tập huấn luyện (Train Size)** | 725 (65.2% 1-Step) | **252 (100% $\\ge 2$ Steps)** | -473 (-65.2%) |
| **Độ chính xác tổng thể** | {base_stats['correct']}/100 ({base_stats['correct']}%) | **{ab_stats['correct']}/100 ({ab_stats['correct']}%)** | {ab_stats['correct'] - base_stats['correct']:+d}% |
| **Đúng cú pháp (`format_valid`)** | {base_stats['format_valid']}/100 ({base_stats['format_valid']}%) | **{ab_stats['format_valid']}/100 ({ab_stats['format_valid']}%)** | {ab_stats['format_valid'] - base_stats['format_valid']:+d}% |
| **Số câu hoàn thành (Non-truncated)** | {base_stats['non_truncated']['n']}/100 | **{ab_stats['non_truncated']['n']}/100** | {ab_stats['non_truncated']['n'] - base_stats['non_truncated']['n']:+d} |
| **Độ chính xác trên chuỗi hoàn thành** | {base_stats['non_truncated']['correct']}/{base_stats['non_truncated']['n']} ({base_stats['non_truncated']['accuracy']}%) | **{ab_stats['non_truncated']['correct']}/{ab_stats['non_truncated']['n']} ({ab_stats['non_truncated']['accuracy']}%)** | {ab_stats['non_truncated']['accuracy'] - base_stats['non_truncated']['accuracy']:+.2f}% |
| **Số câu bị cắt cụt (Truncated)** | {base_stats['truncated']['n']}/100 | **{ab_stats['truncated']['n']}/100** | {ab_stats['truncated']['n'] - base_stats['truncated']['n']:+d} |
| **Cắt cụt do 1-Step độc thoại kéo dài** | **{base_stats['truncated']['monologue_1step']}/{base_stats['truncated']['n']}** | **{ab_stats['truncated']['monologue_1step']}/{ab_stats['truncated']['n']}** | {ab_stats['truncated']['monologue_1step'] - base_stats['truncated']['monologue_1step']:+d} |
| **Vòng lặp tham lam (Repetition Loops)** | {base_stats['truncated']['repetition_loops']}/{base_stats['truncated']['n']} | **{ab_stats['truncated']['repetition_loops']}/{ab_stats['truncated']['n']}** | {ab_stats['truncated']['repetition_loops'] - base_stats['truncated']['repetition_loops']:+d} |

---

## 2. Kiểm Định Thống Kê Ghép Cặp (Paired McNemar Tests)

### A. Độ chính xác lời giải (Accuracy)
* Cả 2 cùng đúng ($n_{{11}}$): **{n11}** | Cả 2 cùng sai ($n_{{00}}$): **{n00}**
* Ablation đúng, Baseline sai ($n_{{01}}$): **{n01}**
* Baseline đúng, Ablation sai ($n_{{10}}$): **{n10}**
* Discordant Pairs ($D = n_{{01}} + n_{{10}}$): **{d_corr}**
* **Exact McNemar $p$-value**: $p = \\mathbf{{{p_corr:.5f}}}$

### B. Khả năng hoàn thành chuỗi (Non-truncation Completion)
* Cả 2 cùng hoàn thành ($n_{{11}}$): **{t_n11}** | Cả 2 cùng bị cắt cụt ($n_{{00}}$): **{t_n00}**
* Ablation hoàn thành, Baseline cắt cụt ($n_{{01}}$): **{t_n01}**
* Baseline hoàn thành, Ablation cắt cụt ($n_{{10}}$): **{t_n10}**
* Discordant Pairs ($D = t_{{01}} + t_{{10}}$): **{d_trunc}**
* **Exact McNemar $p$-value**: $p = \\mathbf{{{p_trunc:.5f}}}$

---

## 3. Kết Luận Khoa Học & Phán Quyết Tiêu Chí Bác Bỏ

{verdict}

### Phân phối số bước trong các chuỗi bị cắt cụt:
* **Baseline**: `{base_stats['truncated']['step_distribution']}`
* **Ablation**: `{ab_stats['truncated']['step_distribution']}`
"""
    REPORT_MD.write_text(report)
    print(f"\n[Report] Saved comparative report to {REPORT_MD}")
    print(report)


def main():
    t_start = time.time()
    print("=== STARTING MATH MULTI-STEP ABLATION PIPELINE ===")
    run_training()
    records = run_evaluation()
    generate_comparative_report(records)
    print(f"\n=== PIPELINE FINISHED IN {(time.time() - t_start) / 60:.1f} MINUTES ===")


if __name__ == "__main__":
    main()
