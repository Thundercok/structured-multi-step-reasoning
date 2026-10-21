"""Export an outcome-blind human review packet; never collect model outputs."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from research_identity import canonical_problem_id, digest  # noqa: E402

RELEASE = ROOT / "data/procedural_research_v1"
KNOWN_EXPOSED = (
    "data/procedural_research_v1/tuning.json",
    "audit/cot_restart_pilot_qwen35_20261009/dataset.json",
    "audit/order_certificate_pilot_dev2_real_20261008/dataset.json",
    "audit/order_certificate_pilot_dev8_contract_v2_real_20261008/dataset.json",
)
OUTPUTS = ("README.md", "review_packet.md", "candidate_frame.json", "manifest.json")
# Compared with release source e6129d4: adds gap/offset clue support while
# preserving legacy three-field clue identities; every retained ID is rechecked.
REVIEWED_IDENTITY_SHA = "5e22ba902cbb2d9f033b149570d252497fe15fb46dae5bcc7d736447204debb0"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def quote(value):
    return "\n".join("> " + line for line in str(value).splitlines())


def prepare(output):
    output = Path(output).resolve()
    if any((output / name).exists() for name in OUTPUTS):
        raise ValueError("Use a new output directory; never overwrite a review packet")
    release_manifest = load(RELEASE / "manifest.json")
    for name, expected in release_manifest["artifact_sha256"].items():
        if sha(RELEASE / name) != expected:
            raise ValueError(f"Candidate artifact hash mismatch: {name}")
    original_identity_sha = release_manifest["source_sha256"]["research_identity.py"]
    current_identity_sha = sha(ROOT / "research_identity.py")
    if current_identity_sha not in (original_identity_sha, REVIEWED_IDENTITY_SHA):
        raise ValueError("Canonical identity implementation changed; review before exporting")
    for source in release_manifest["inputs"].values():
        if sha(ROOT / source["path"]) != source["sha256"]:
            raise ValueError("Original dataset hash mismatch")

    main = load(RELEASE / "main.json")
    legacy = {row["id"]: row for row in load(ROOT / "data/gen_v2.json")["items"]}
    split_groups = defaultdict(set)
    for row in main["items"]:
        if canonical_problem_id(row) != row["group_id"]:
            raise ValueError("Candidate canonical identity mismatch")
        split_groups[row["split"]].add(row["group_id"])
        provenance = row["source_provenance"]
        original = legacy[provenance["original_id"]]
        if digest(original) != provenance["original_row_sha256"]:
            raise ValueError("Original row provenance mismatch")
        if any(row[key] != value for key, value in original.items()
               if key not in ("id", "group_id", "split")):
            raise ValueError("Candidate changed original content")
    for left, right in (("train", "calibration"), ("train", "test"), ("calibration", "test")):
        if split_groups[left] & split_groups[right]:
            raise ValueError("Canonical groups cross splits")

    candidates = sorted((r for r in main["items"] if r["split"] == "test"),
                        key=lambda r: (r["family"], r["group_id"], r["id"]))
    candidate_groups = {r["group_id"] for r in candidates}
    overlap_checks = []
    for relative in KNOWN_EXPOSED:
        rows = load(ROOT / relative)["items"]
        observed = {canonical_problem_id(r) for r in rows}
        overlap = sorted(candidate_groups & observed)
        overlap_checks.append({"dataset": relative, "sha256": sha(ROOT / relative),
                               "groups": len(observed), "overlap_groups": overlap})
        if overlap:
            raise ValueError(f"Candidate overlaps a checked exposed pool: {relative}")
    groups = defaultdict(list)
    for row in candidates:
        groups[row["group_id"]].append(row)
    frame = {
        "role": "candidate_review_only", "publication_ready": False,
        "execution_authorized": False, "power_justified": False,
        "human_review_status": "pending", "prior_exposure_status": "unverified_beyond_listed_pools",
        "proposed_representative_rule": "lexicographically smallest item ID per canonical group; no outcomes used",
        "items": len(candidates), "groups": len(groups),
        "families": dict(sorted(Counter(r["family"] for r in candidates).items())),
        "group_frame": [{"group_id": group,
                         "proposed_representative_id": min(r["id"] for r in rows),
                         "variant_ids": sorted(r["id"] for r in rows),
                         "review_status": "pending"}
                        for group, rows in sorted(groups.items())],
    }
    packet = ["# Gói duyệt câu ứng viên CoT restart", "",
              "Dành cho reviewer đáp án/nguồn độc lập; chưa có model output mới.",
              "Đây là bản xuất nguyên văn, chưa phải chứng nhận gold đúng hoặc dữ liệu chưa từng lộ.",
              "Tạo bản sao để ghi review; ghi người duyệt, ngày, quyết định và lý do cho từng câu.", ""]
    for index, row in enumerate(candidates, 1):
        source = row["source_provenance"]
        packet.extend([
            f"## {index}. {row['id']}", "",
            f"- Nhóm: `{row['group_id']}`; họ: `{row['family']}`; mức generator: `{row['level']}`.",
            f"- Nguồn: `{source['path']}` / `{source['original_id']}`; split gốc: `{source['original_split']}`.",
            f"- SHA-256 query: `{hashlib.sha256(row['query'].encode()).hexdigest()}`.",
            f"- SHA-256 gold: `{hashlib.sha256(str(row['answer']).encode()).hexdigest()}`.", "",
            "**Câu hỏi gốc**", "", quote(row["query"]), "",
            "**Gold gốc cần kiểm độc lập**", "", quote(row["answer"]), "",
            "- [ ] Câu hỏi rõ, đủ dữ kiện; tự giải và kiểm lại gold.",
            "- [ ] Nguồn/quyền sử dụng có bằng chứng (có thể dẫn một hồ sơ chung).",
            "- [ ] Kiểm tra lịch sử lộ/chạy trước ngoài các pool đã đối chiếu.",
            "- Reviewer / ngày:", "- Quyết định: pending / pass / exclude / needs-correction.",
            "- Lập luận, nguồn và ghi chú:", "",
        ])
    readme = f"""# Việc làm ngay: duyệt dữ liệu cho đợt CoT restart mới

Đã xuất **{len(candidates)} câu ứng viên / {len(groups)} nhóm**, chưa có câu nào
được gói này chứng nhận đã qua human review; model calls mới = 0.

1. Gửi bản sao [gói câu hỏi và gold](review_packet.md) cho reviewer độc lập để
   ghi lập luận, nguồn, lịch sử sử dụng và quyết định từng câu; giữ nguyên bản xuất này.
2. Đối chiếu hồ sơ review với [frame nhóm](candidate_frame.json), ghi mọi sửa/loại
   trước khi xem model output; nếu sửa nội dung thì tạo release mới cùng hash mới.
3. Dùng frame đã duyệt để chốt protocol và power cho F−CONT, F−O, rồi mới freeze
   nguồn/code/luật quyết định và chuẩn bị ngân sách chạy cụ thể.

**Đã kiểm bằng CPU:** hash bundle gốc, nguyên trạng query/gold/metadata so với
nguồn, identity chuẩn, nhóm không qua split, và trùng canonical với tuning pool,
pilot CoT restart 12 câu, hai pilot ordering 2/8 câu; các đối chiếu này có 0 nhóm trùng.
Đây là kiểm trùng có phạm vi, chưa xác minh toàn bộ lịch sử chạy hoặc pretraining.
Mã identity hiện có thêm hỗ trợ clue gap so với bản tạo bundle; đã đối chiếu
diff và tính lại identity trên toàn bộ 179 câu, giữ đúng group ID đã lưu.
Nội dung câu/gold được xuất bằng chương trình; chưa được agent duyệt ngữ nghĩa
trong bước này. Mức generator không phải độ khó thực nghiệm đã được kiểm chứng.

**Thiết kế đề xuất:** giữ q yêu cầu = 0,50; một draw chính mỗi câu cho F và CONT,
O là đáp án base mới dùng chung; A là ablation phụ. Mỗi nhóm tối đa một câu trong
phân tích chính, đại diện đề xuất chọn bằng item ID trước mọi kết quả. Mọi base
mới phải lưu prompt/completion IDs và EOS ngay từ đầu. Không dùng lại số token
base lịch sử chưa xác minh. Báo riêng prompt, completion và toàn đường suy luận;
latency triển khai cần đo online riêng.

**Phần còn phải làm trước chạy thật:** runner hiện tại khóa đúng 12 câu lịch sử
(`experiments/cot_restart_matched.py`); cần adapter thu base và arm cho frame mới,
được kiểm bằng mock qua entry point `python -m experiments.research_study`.
Cần chốt cap/cost scope, δ_prac (và λ nếu dùng utility), n/power và code quyết định;
{len(groups)} nhóm ở đây là lượng ứng viên hiện có, không phải cỡ mẫu đã chứng minh đủ power.
Chọn m=1 cho thống kê chính; các mở rộng cluster/betting giữ ở nhánh phương pháp
synthetic. Đây là đề xuất, chưa là preregistration hoặc phê duyệt inference.

Gói này không thay đổi split, dữ liệu nguồn, runner, kế hoạch đã hash hoặc Stage 0.
Để tái lập sang thư mục mới:

```bash
python3.12 audit/cot_restart_fresh_data_review_20261016/prepare_review.py --output /tmp/cot_restart_review_copy
```
"""
    output.mkdir(parents=True, exist_ok=True)
    (output / "README.md").write_text(readme, encoding="utf-8")
    (output / "review_packet.md").write_text("\n".join(packet), encoding="utf-8")
    write_json(output / "candidate_frame.json", frame)
    input_paths = [RELEASE / "manifest.json", RELEASE / "main.json", RELEASE / "tuning.json",
                   ROOT / "data/gen_v2.json", ROOT / "data/gen_tune.json",
                   ROOT / "research_identity.py", Path(__file__).resolve()]
    input_paths.extend(ROOT / p for p in KNOWN_EXPOSED)
    write_json(output / "manifest.json", {
        "status": "prepared_pending_independent_review", "evidence": "CPU-only structural export",
        "date_local": "2026-10-16", "timezone": "Asia/Ho_Chi_Minh",
        "model_calls": 0, "semantic_gold_review_performed": False,
        "test_query_or_gold_printed_to_agent": False, "execution_authorized": False,
        "stage_0_changed": False, "candidate_items": len(candidates), "candidate_groups": len(groups),
        "human_approved_by_this_packet": 0, "overlap_checks": overlap_checks,
        "identity_compatibility": {
            "release_source_sha256": original_identity_sha,
            "current_source_sha256": current_identity_sha,
            "exact_source_match": original_identity_sha == current_identity_sha,
            "review": "Compared e6129d4 with current: gap/offset support added; legacy three-field identities preserved",
            "all_main_item_canonical_ids_recomputed_and_equal": True,
            "main_items_checked": len(main["items"]),
        },
        "inputs_sha256": {str(p.relative_to(ROOT)): sha(p) for p in dict.fromkeys(input_paths)},
        "artifact_sha256": {name: sha(output / name) for name in OUTPUTS if name != "manifest.json"},
    })
    return {"items": len(candidates), "groups": len(groups), "family_counts": frame["families"],
            "human_approved": 0, "checked_pool_overlaps": 0, "model_calls": 0,
            "output": str(output)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output), ensure_ascii=False))
