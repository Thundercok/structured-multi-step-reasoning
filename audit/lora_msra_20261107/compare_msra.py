"""Compare MSRA Stage 1 Cold-Start SFT vs Stage 2 SimPO on 100 dev problems.

Run from repo root:
    PYTHONPATH=. .venv/bin/python audit/lora_msra_20261107/compare_msra.py
"""

import json
from pathlib import Path
from structured_llm.analyze import exact_mcnemar

DIR = Path(__file__).parent
STAGE1_JSON = DIR / "eval_dev100.json"
STAGE2_JSON = DIR / "eval_simpo_dev100.json"
COMP_JSON = DIR / "comparison.json"
REPORT_MD = DIR / "REPORT.md"


def load_eval(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_ci(ci):
    if not ci or len(ci) != 2:
        return "N/A"
    return f"{ci[0]:.1f}–{ci[1]:.1f}%"


def main():
    s1 = load_eval(STAGE1_JSON)
    s2 = load_eval(STAGE2_JSON)

    out = {"stage1_coldstart": s1, "stage2_simpo": s2}
    if s1 and s2 and "items" in s1 and "items" in s2:
        map1 = {r["problem_id"]: r for r in s1["items"]}
        map2 = {r["problem_id"]: r for r in s2["items"]}
        shared = set(map1.keys()) & set(map2.keys())
        only_s2 = sum(bool(map2[k]["correct"]) and not bool(map1[k]["correct"]) for k in shared)
        only_s1 = sum(bool(map1[k]["correct"]) and not bool(map2[k]["correct"]) for k in shared)
        out["paired_comparison"] = {
            "shared_n": len(shared),
            "only_simpo_correct": only_s2,
            "only_coldstart_correct": only_s1,
            "mcnemar_p": exact_mcnemar(only_s2, only_s1),
            "helper_rate_delta": round(s2["helper_call_rate"] - s1["helper_call_rate"], 2),
            "mean_cost_delta": round(s2["mean_cost_per_problem"] - s1["mean_cost_per_problem"], 3),
        }

    COMP_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Báo cáo Thực nghiệm MSRA: Stage 1 (Cold-Start DAG SFT) vs. Stage 2 (SimPO)",
        "",
        "| Giai đoạn / Adapter | Đúng (`Accuracy`) | KTC Wilson 95% | Đúng XML (`xml_valid`) | Hợp lệ DAG (`dag_valid`) | Tỷ lệ gọi công cụ (`helper_call_rate`) | Chi phí TB (`mean_cost`) | Số bước TB |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    for label, data in [
        ("Stage 1: `msra_coldstart_2000_s0`", s1),
        ("**Stage 2: `msra_simpo_1000_s0`**", s2),
    ]:
        if not data:
            continue
        lines.append(
            f"| {label} | {data['accuracy']:.1f}% | {fmt_ci(data.get('accuracy_wilson_95'))} | "
            f"{data['xml_valid_rate']:.1f}% ({fmt_ci(data.get('xml_valid_wilson_95'))}) | "
            f"{data['dag_valid_rate']:.1f}% | {data['helper_call_rate']:.1f}% | "
            f"{data['mean_cost_per_problem']:.3f} | {data['mean_steps']:.2f} |"
        )

    if "paired_comparison" in out:
        pc = out["paired_comparison"]
        lines.extend([
            "",
            "## Kiểm định Ghép cặp (Stage 2 SimPO vs. Stage 1 Cold-Start)",
            f"- **McNemar chính xác hai phía:** `p = {pc['mcnemar_p']:.4f}` (chỉ SimPO đúng: {pc['only_simpo_correct']}, chỉ Cold-Start đúng: {pc['only_coldstart_correct']})",
            f"- **Độ lệch tỷ lệ gọi trợ giúp (`helper_call_rate`):** `{pc['helper_rate_delta']:+.2f}%`",
            f"- **Độ lệch chi phí trung bình (`mean_cost`):** `{pc['mean_cost_delta']:+.3f}`",
        ])
    else:
        lines.extend([
            "",
            "*Ghi chú: Đang chờ tiến trình huấn luyện và đánh giá Stage 1 / Stage 2 hoàn tất để cập nhật bảng đối sánh đầy đủ.*",
        ])

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {COMP_JSON} and {REPORT_MD}")


if __name__ == "__main__":
    main()
