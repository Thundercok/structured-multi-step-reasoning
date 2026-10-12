import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
DATA_PATH = os.path.join(ROOT, "data", "nckh_reasoning_dataset_draft.json")
OUTPUT_PATH = os.path.join(ROOT, "audit", "dev_golds.md")

def main():
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    dev_groups = {}
    for item in data["items"]:
        if item.get("split") == "train":
            dev_groups.setdefault(item["group_id"], []).append(item)

    from scripts.audit_development_data import solve_curated_group
    for gid, items in dev_groups.items():
        expected, _ = solve_curated_group(gid)
        if any(item["answer"] != expected for item in items):
            raise ValueError(f"Development gold differs from independent calculation: {gid}")

    lines = [
        "# Dev Split Gold Standard Verification (12 Groups / 36 Items)",
        "",
        "Bảng tra cứu gold label chuẩn của 12 nhóm thuộc tập development (`split: 'train'`).",
        "Labels được kiểm tra lại bằng tính toán/lập luận độc lập trong `scripts/audit_development_data.py`.",
        "Đây là kiểm tra của AI agent; chưa có hồ sơ người duyệt. Xem `audit/development_data_review.json` và báo cáo development audit.",
        "",
        "| group_id | câu hỏi (en_orig) | gold | kiểm tra độc lập của agent | 3 variant id |",
        "| --- | --- | --- | --- | --- |",
    ]

    for gid, items in dev_groups.items():
        orig = next(it for it in items if it["id"].endswith("_en_orig"))
        variant_ids = ", ".join(f"`{it['id']}`" for it in items)
        query = orig["query"].replace("|", "\\|")
        gold = orig["answer"]
        _, method = solve_curated_group(gid)
        lines.append(f"| `{gid}` | {query} | **{gold}** | {method} | {variant_ids} |")

    lines.append("")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated {OUTPUT_PATH} for {len(dev_groups)} dev groups.")

if __name__ == "__main__":
    main()
