"""
scripts/build_nckh_dataset.py — Build curated multi-step reasoning dataset for NCKH.

Features:
1. Strict schema compliance with experiments.research_study.validate_dataset:
   - Root: name, version, source, license, items.
   - Items: id, group_id, split, query, answer, answer_type, tolerance, source, license, category, review_status.
2. Group-level integrity:
   - Paraphrases and Vietnamese translations are strictly co-located within the SAME group_id.
   - Group-level train / calibration / test splitting ensures zero data leakage across splits.
3. Locked test split for unbiased evaluation.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
import random
import sys
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.research_study import validate_dataset


RAW_GROUPS = [
    # --------------------------------------------------------------------------
    # PAL Category (Program-Aided Language / Arithmetic / Multi-step Math)
    # --------------------------------------------------------------------------
    {
        "group_id": "grp_pal_001",
        "category": "pal",
        "source": "GSM8K (Cobbe et al.)",
        "license": "MIT",
        "answer": "72",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_001_en_orig", "Natalia sold clips to 48 of her friends in April, and then she sold half as many clips in May. How many clips did Natalia sell altogether in April and May?"),
            ("pal_001_en_para", "In April, Natalia provided clips to 48 friends. The following month in May, she sold only half that amount. What was the combined total of clips Natalia sold over April and May?"),
            ("pal_001_vi_trans", "Trong tháng 4, Natalia đã bán kẹp giấy cho 48 người bạn. Sang tháng 5, cô ấy bán được số kẹp bằng một nửa tháng 4. Hỏi tổng cộng cả hai tháng Natalia bán được bao nhiêu kẹp giấy?"),
        ],
    },
    {
        "group_id": "grp_pal_002",
        "category": "pal",
        "source": "GSM8K (Cobbe et al.)",
        "license": "MIT",
        "answer": "10",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_002_en_orig", "Weng earns $12 an hour for babysitting. Yesterday, she just did 50 minutes of babysitting. How much did she earn in dollars?"),
            ("pal_002_en_para", "Weng is paid a babysitting wage of $12 per hour. If she looked after children for 50 minutes yesterday, what was her dollar earnings?"),
            ("pal_002_vi_trans", "Weng kiếm được 12 đô la mỗi giờ nhờ trông trẻ. Hôm qua, cô ấy trông trẻ trong 50 phút. Hỏi cô ấy kiếm được bao nhiêu đô la?"),
        ],
    },
    {
        "group_id": "grp_pal_003",
        "category": "pal",
        "source": "GSM8K (Cobbe et al.)",
        "license": "MIT",
        "answer": "5",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_003_en_orig", "Betty is saving money for a new wallet which costs $100. Betty has only half of the money she needs. Her parents give her $15, and her grandparents give her twice as much as her parents. How much more money does Betty need to buy the wallet?"),
            ("pal_003_en_para", "A wallet costs $100. Betty currently has 50% of the cost. She receives $15 from her parents and double that amount from her grandparents. How many more dollars does she need to purchase the wallet?"),
            ("pal_003_vi_trans", "Betty đang tiết kiệm tiền để mua một chiếc ví có giá 100 đô la. Hiện cô ấy mới có một nửa số tiền cần thiết. Bố mẹ cho cô ấy 15 đô la, còn ông bà cho cô ấy gấp đôi số tiền bố mẹ cho. Hỏi Betty còn thiếu bao nhiêu đô la nữa mới đủ mua chiếc ví?"),
        ],
    },
    {
        "group_id": "grp_pal_004",
        "category": "pal",
        "source": "Curated Arithmetic",
        "license": "CC-BY-4.0",
        "answer": "192",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_004_en_orig", "Albert buys 2 large pizzas and 2 small pizzas per week for 4 weeks. A large pizza has 16 slices and a small pizza has 8 slices. In 4 weeks, how many slices of pizza does Albert eat in total?"),
            ("pal_004_en_para", "Every week across a 4-week period, Albert gets 2 large pizzas (16 slices each) and 2 small pizzas (8 slices each). Calculate the total number of slices he has after 4 weeks."),
            ("pal_004_vi_trans", "Albert mua 2 chiếc bánh pizza lớn và 2 chiếc pizza nhỏ mỗi tuần trong vòng 4 tuần. Một chiếc pizza lớn có 16 miếng và pizza nhỏ có 8 miếng. Trong 4 tuần, tổng cộng Albert đã ăn bao nhiêu miếng pizza?"),
        ],
    },
    {
        "group_id": "grp_pal_005",
        "category": "pal",
        "source": "Curated Arithmetic",
        "license": "CC-BY-4.0",
        "answer": "129.6",
        "answer_type": "number",
        "tolerance": "0.01",
        "review_status": "reviewed",
        "variants": [
            ("pal_005_en_orig", "A store offers a 20% discount on a $150 jacket. Sales tax is 8% applied to the discounted price. What is the final total price in dollars?"),
            ("pal_005_en_para", "A jacket marked at $150 is discounted by 20 percent. Then an 8 percent sales tax is added to this reduced price. What is the final checkout cost?"),
            ("pal_005_vi_trans", "Một cửa hàng giảm giá 20% cho một chiếc áo khoác có giá 150 đô la. Thuế bán hàng 8% được tính trên giá đã giảm. Hỏi giá thanh toán cuối cùng là bao nhiêu đô la?"),
        ],
    },
    {
        "group_id": "grp_pal_006",
        "category": "pal",
        "source": "Curated Physics/Math",
        "license": "CC-BY-4.0",
        "answer": "285",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_006_en_orig", "A train travels at 75 km/h for 2 hours, and then 90 km/h for 1.5 hours. What is the total distance traveled in kilometers?"),
            ("pal_006_en_para", "A train runs for 2 hours at an average speed of 75 km/h, followed by 1.5 hours at 90 km/h. How many kilometers did the train cover in total?"),
            ("pal_006_vi_trans", "Một đoàn tàu di chuyển với vận tốc 75 km/h trong 2 giờ, sau đó chạy với vận tốc 90 km/h trong 1,5 giờ. Hỏi tổng quãng đường đoàn tàu đã đi được là bao nhiêu kilômét?"),
        ],
    },
    {
        "group_id": "grp_pal_007",
        "category": "pal",
        "source": "Classic Geometry",
        "license": "CC-BY-4.0",
        "answer": "84",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_007_en_orig", "If a rectangle has length 24 cm and width 18 cm, what is its perimeter in cm?"),
            ("pal_007_en_para", "Compute the perimeter in centimeters of a rectangular shape measuring 24 cm in length by 18 cm in width."),
            ("pal_007_vi_trans", "Một hình chữ nhật có chiều dài 24 cm và chiều rộng 18 cm. Hỏi chu vi của hình chữ nhật đó là bao nhiêu cm?"),
        ],
    },
    {
        "group_id": "grp_pal_008",
        "category": "pal",
        "source": "Classic Algebra Puzzle",
        "license": "CC-BY-4.0",
        "answer": "40",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("pal_008_en_orig", "A farmer has 120 chickens and cows in total. Together they have 320 legs. How many cows are on the farm?"),
            ("pal_008_en_para", "There are 120 animals consisting of chickens and cows on a farm. The total leg count is 320. Find the number of cows."),
            ("pal_008_vi_trans", "Một người nông dân có tổng cộng 120 con gà và bò. Đếm tất cả có 320 cái chân. Hỏi trong trang trại có bao nhiêu con bò?"),
        ],
    },

    # --------------------------------------------------------------------------
    # REACT Category (Chained Arithmetic & Explicit Intermediate Verification)
    # --------------------------------------------------------------------------
    {
        "group_id": "grp_react_001",
        "category": "react",
        "source": "Chained Arithmetic",
        "license": "CC-BY-4.0",
        "answer": "9501",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_001_en_orig", "Calculate the arithmetic expression: (345 * 28) - (1240 / 5) + 89. Give the exact final number."),
            ("react_001_en_para", "What is the exact numerical result of evaluating (345 * 28) minus (1240 / 5) plus 89?"),
            ("react_001_vi_trans", "Tính giá trị của biểu thức: (345 * 28) - (1240 / 5) + 89. Hãy cho biết con số chính xác cuối cùng."),
        ],
    },
    {
        "group_id": "grp_react_002",
        "category": "react",
        "source": "Chained Arithmetic",
        "license": "CC-BY-4.0",
        "answer": "1167",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_002_en_orig", "A warehouse receives 24 crates of 18 boxes, 15 crates of 25 boxes, and 30 crates of 12 boxes. How many boxes in total were received?"),
            ("react_002_en_para", "A delivery to a warehouse brings 24 crates holding 18 boxes each, 15 crates holding 25 boxes each, and 30 crates holding 12 boxes each. What is the total box count?"),
            ("react_002_vi_trans", "Một nhà kho nhận được 24 kiện hàng (mỗi kiện 18 hộp), 15 kiện hàng (mỗi kiện 25 hộp), và 30 kiện hàng (mỗi kiện 12 hộp). Hỏi tổng cộng nhà kho đã nhận được bao nhiêu hộp?"),
        ],
    },
    {
        "group_id": "grp_react_003",
        "category": "react",
        "source": "Percentage Chaining",
        "license": "CC-BY-4.0",
        "answer": "146",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_003_en_orig", "Evaluate: 15% of 840 plus 25% of 620 minus 30% of 450."),
            ("react_003_en_para", "Find the value of: 0.15 * 840 + 0.25 * 620 - 0.30 * 450."),
            ("react_003_vi_trans", "Tính giá trị của biểu thức: 15% của 840 cộng với 25% của 620 trừ đi 30% của 450."),
        ],
    },
    {
        "group_id": "grp_react_004",
        "category": "react",
        "source": "Multi-segment Travel",
        "license": "CC-BY-4.0",
        "answer": "440",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_004_en_orig", "A trip has 3 segments: 145 km in 2 hours, 210 km in 3 hours, and 85 km in 1 hour. What is the total distance in km?"),
            ("react_004_en_para", "A journey is split into three legs: 145 km, 210 km, and 85 km. Calculate the cumulative distance of the entire trip in kilometers."),
            ("react_004_vi_trans", "Một chuyến đi gồm 3 chặng: chặng một dài 145 km, chặng hai dài 210 km, và chặng ba dài 85 km. Hỏi tổng quãng đường đã đi là bao nhiêu km?"),
        ],
    },
    {
        "group_id": "grp_react_005",
        "category": "react",
        "source": "Inventory Arithmetic",
        "license": "CC-BY-4.0",
        "answer": "1500",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_005_en_orig", "A factory produces 450 units on Monday, 520 on Tuesday, and 610 on Wednesday. If 80 defective units are discarded, how many good units remain?"),
            ("react_005_en_para", "Output at a manufacturing plant is 450 items on Monday, 520 on Tuesday, and 610 on Wednesday. After removing 80 faulty items, how many acceptable units are left?"),
            ("react_005_vi_trans", "Một nhà máy sản xuất 450 sản phẩm vào thứ Hai, 520 vào thứ Ba, và 610 vào thứ Tư. Nếu loại bỏ 80 sản phẩm bị lỗi, hỏi còn lại bao nhiêu sản phẩm đạt chuẩn?"),
        ],
    },
    {
        "group_id": "grp_react_006",
        "category": "react",
        "source": "Finance Calculation",
        "license": "CC-BY-4.0",
        "answer": "2265",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_006_en_orig", "An investor buys 50 shares at $24 each, 30 shares at $35 each, and pays a flat fee of $15. What is the total investment in dollars?"),
            ("react_006_en_para", "Calculate the total outlay in dollars for purchasing 50 shares at $24 per share plus 30 shares at $35 per share with an added $15 transaction commission."),
            ("react_006_vi_trans", "Một nhà đầu tư mua 50 cổ phiếu giá 24 đô la/cổ phiếu, 30 cổ phiếu giá 35 đô la/cổ phiếu, và trả thêm một khoản phí cố định là 15 đô la. Hỏi tổng số tiền đầu tư là bao nhiêu đô la?"),
        ],
    },
    {
        "group_id": "grp_react_007",
        "category": "react",
        "source": "Compound Arithmetic",
        "license": "CC-BY-4.0",
        "answer": "210",
        "answer_type": "number",
        "tolerance": "0",
        "review_status": "reviewed",
        "variants": [
            ("react_007_en_orig", "Evaluate: 3 * (45 + 55) - 4 * (120 - 85) + 250 / 5."),
            ("react_007_en_para", "Compute the mathematical value of: 3*(45+55) - 4*(120-85) + 250/5."),
            ("react_007_vi_trans", "Tính giá trị biểu thức: 3 * (45 + 55) - 4 * (120 - 85) + 250 / 5."),
        ],
    },

    # --------------------------------------------------------------------------
    # PLAIN Category (Transitive Logic, Deduction, Commonsense Reasoning)
    # --------------------------------------------------------------------------
    {
        "group_id": "grp_plain_001",
        "category": "plain",
        "source": "Transitive Logic",
        "license": "CC-BY-4.0",
        "answer": "Charlie",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_001_en_orig", "Alice is taller than Bob. Charlie is shorter than Bob. David is taller than Alice. Who is the shortest person among them?"),
            ("plain_001_en_para", "Between four individuals: Alice exceeds Bob in height, Charlie is not as tall as Bob, and David surpasses Alice. Which individual has the least height?"),
            ("plain_001_vi_trans", "Alice cao hơn Bob. Charlie thấp hơn Bob. David cao hơn Alice. Hỏi trong số họ ai là người thấp nhất?"),
        ],
    },
    {
        "group_id": "grp_plain_002",
        "category": "plain",
        "source": "Syllogistic Logic",
        "license": "CC-BY-4.0",
        "answer": "No",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_002_en_orig", "All roses are flowers. Some flowers fade quickly. Can we conclude with certainty that all roses fade quickly? Answer Yes or No."),
            ("plain_002_en_para", "Given that every rose belongs to the set of flowers, and a subset of flowers wither fast, does it logically follow that every rose must wither fast? Respond with Yes or No."),
            ("plain_002_vi_trans", "Mọi bông hoa hồng đều là hoa. Một số loài hoa mau tàn. Chúng ta có thể kết luận chắc chắn rằng mọi bông hoa hồng đều mau tàn hay không? Trả lời Yes hoặc No."),
        ],
    },
    {
        "group_id": "grp_plain_003",
        "category": "plain",
        "source": "Ordering Puzzle",
        "license": "CC-BY-4.0",
        "answer": "E",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_003_en_orig", "Five runners (A, B, C, D, E) finished a race. A finished before B but behind C. D finished before C but behind E. Who finished first?"),
            ("plain_003_en_para", "In a race of five competitors A, B, C, D, E: A beat B but trailed C; D beat C but trailed E. Who took first place?"),
            ("plain_003_vi_trans", "Năm vận động viên (A, B, C, D, E) hoàn thành một cuộc đua. A về trước B nhưng sau C. D về trước C nhưng sau E. Hỏi ai là người về đích đầu tiên?"),
        ],
    },
    {
        "group_id": "grp_plain_004",
        "category": "plain",
        "source": "Modular Arithmetic / Calendar",
        "license": "CC-BY-4.0",
        "answer": "Thursday",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_004_en_orig", "If today is Tuesday, what day of the week will it be in exactly 100 days?"),
            ("plain_004_en_para", "Assuming today is a Tuesday, which day of the week will occur 100 days from now?"),
            ("plain_004_vi_trans", "Nếu hôm nay là thứ Ba, thì đúng 100 ngày nữa sẽ là thứ mấy trong tuần?"),
        ],
    },
    {
        "group_id": "grp_plain_005",
        "category": "plain",
        "source": "Transitive Ordering",
        "license": "CC-BY-4.0",
        "answer": "Yes",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_005_en_orig", "Tom is older than Jerry. Jerry is older than Spike. Tyke is younger than Spike. Is Tom older than Tyke? Answer Yes or No."),
            ("plain_005_en_para", "Tom exceeds Jerry in age; Jerry exceeds Spike; Tyke is younger than Spike. Is Tom strictly older than Tyke? Respond Yes or No."),
            ("plain_005_vi_trans", "Tom lớn tuổi hơn Jerry. Jerry lớn tuổi hơn Spike. Tyke nhỏ tuổi hơn Spike. Hỏi Tom có lớn tuổi hơn Tyke không? Trả lời Yes hoặc No."),
        ],
    },
    {
        "group_id": "grp_plain_006",
        "category": "plain",
        "source": "Classic River Crossing Riddle",
        "license": "CC-BY-4.0",
        "answer": "Goat",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_006_en_orig", "A farmer needs to cross a river with a wolf, a goat, and a cabbage. If left alone, the wolf eats the goat, and the goat eats the cabbage. Which item must the farmer take across first?"),
            ("plain_006_en_para", "To transport a wolf, a goat, and a cabbage across a river safely without the wolf devouring the goat or the goat devouring the cabbage when unsupervised, which one must be moved first?"),
            ("plain_006_vi_trans", "Một bác nông dân cần chở một con sói, một con dê và một bắp cải qua sông. Nếu để ở cùng nhau mà không có người, sói sẽ ăn thịt dê, và dê sẽ ăn bắp cải. Hỏi bác nông dân phải chở thứ gì qua sông đầu tiên?"),
        ],
    },
    {
        "group_id": "grp_plain_007",
        "category": "plain",
        "source": "Commonsense Physics",
        "license": "CC-BY-4.0",
        "answer": "Equal",
        "answer_type": "text",
        "review_status": "reviewed",
        "variants": [
            ("plain_007_en_orig", "Which is heavier: 1 kilogram of steel or 1 kilogram of feathers? Answer Steel, Feathers, or Equal."),
            ("plain_007_en_para", "Between one kilogram of steel and one kilogram of bird feathers, which mass is greater? Answer Steel, Feathers, or Equal."),
            ("plain_007_vi_trans", "Vật nào nặng hơn: 1 kilôgam sắt hay 1 kilôgam lông vũ? Trả lời Steel, Feathers, hoặc Equal."),
        ],
    },
]


def split_groups_stratified(groups: List[Dict[str, Any]], seed: int = 42) -> Dict[str, str]:
    """
    Split groups into train (50%), calibration (25%), test (25%) stratified by category.
    Guarantees no group crosses splits.
    """
    rng = random.Random(seed)
    by_category: Dict[str, List[str]] = {}
    for g in groups:
        by_category.setdefault(g["category"], []).append(g["group_id"])

    group_to_split: Dict[str, str] = {}

    for cat, g_ids in by_category.items():
        shuffled = list(g_ids)
        rng.shuffle(shuffled)
        n = len(shuffled)
        n_train = max(1, int(round(n * 0.50)))
        n_calib = max(1, int(round(n * 0.25)))
        n_test = n - n_train - n_calib
        if n_test < 1:
            n_test = 1
            n_train -= 1

        train_ids = shuffled[:n_train]
        calib_ids = shuffled[n_train:n_train + n_calib]
        test_ids = shuffled[n_train + n_calib:]

        for gid in train_ids:
            group_to_split[gid] = "train"
        for gid in calib_ids:
            group_to_split[gid] = "calibration"
        for gid in test_ids:
            group_to_split[gid] = "test"

    return group_to_split


def build_dataset(seed: int = 42) -> Dict[str, Any]:
    """Construct a draft; schema validity does not establish human review."""
    group_to_split = split_groups_stratified(RAW_GROUPS, seed=seed)

    items: List[Dict[str, Any]] = []

    for group in RAW_GROUPS:
        gid = group["group_id"]
        split = group_to_split[gid]

        for item_id, query_text in group["variants"]:
            item = {
                "id": item_id,
                "group_id": gid,
                "split": split,
                "query": query_text,
                "answer": group["answer"],
                "answer_type": group["answer_type"],
                "source": group["source"],
                "license": group["license"],
                "category": group["category"],
                "review_status": group["review_status"],
            }
            if group.get("tolerance"):
                item["tolerance"] = group["tolerance"]
            items.append(item)

    dataset = {
        "name": "nckh-multistep-reasoning-v1",
        "version": "1.0.0",
        "source": "Curated benchmark with paraphrases & Vietnamese translations",
        "license": "CC-BY-4.0",
        "items": items,
    }

    review_path = ROOT / "audit" / "development_data_review.json"
    if seed == 42 and review_path.exists():
        from scripts.audit_development_data import apply_curated_review
        dataset = apply_curated_review(dataset, json.loads(review_path.read_text()))
    elif seed != 42:
        for item in items:
            item["review_status"] = "unreviewed"

    # Validate against strict research study criteria
    validate_dataset(dataset)
    return dataset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/nckh_reasoning_dataset_draft.json", help="Output path")
    parser.add_argument("--seed", type=int, default=42, help="Stratified split seed")
    args = parser.parse_args()

    dataset = build_dataset(seed=args.seed)

    out_path = Path(args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(dataset, indent=2, ensure_ascii=False))

    items = dataset["items"]
    by_split = {}
    for it in items:
        by_split[it["split"]] = by_split.get(it["split"], 0) + 1

    print(f"Dataset successfully built and validated: {out_path}")
    print(f"Total items: {len(items)} across {len(RAW_GROUPS)} groups")
    print(f"Distribution by split: {by_split}")
    print("Group IDs remain disjoint across splits; semantic duplicates and human review require separate evidence.")


if __name__ == "__main__":
    main()
