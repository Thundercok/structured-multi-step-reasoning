# Dev Split Gold Standard Verification (12 Groups / 36 Items)

Bảng tra cứu gold label chuẩn của 12 nhóm thuộc tập development (`split: 'train'`).
Mọi câu hỏi và đáp án gold được tạo và kiểm định bằng phương pháp tất định (deterministic solver / human logic), không dựa vào sinh tự do từ LLM.

| group_id | câu hỏi (en_orig) | gold | cách sinh gold (human/solver/LLM) | 3 variant id |
| --- | --- | --- | --- | --- |
| `grp_pal_004` | Albert buys 2 large pizzas and 2 small pizzas per week for 4 weeks. A large pizza has 16 slices and a small pizza has 8 slices. In 4 weeks, how many slices of pizza does Albert eat in total? | **192** | solver (closed-form arithmetic: (2*16 + 2*8)*4 = 192) | `pal_004_en_orig`, `pal_004_en_para`, `pal_004_vi_trans` |
| `grp_pal_005` | A store offers a 20% discount on a $150 jacket. Sales tax is 8% applied to the discounted price. What is the final total price in dollars? | **129.6** | solver (closed-form percentage: 150 * 0.8 * 1.08 = 129.6) | `pal_005_en_orig`, `pal_005_en_para`, `pal_005_vi_trans` |
| `grp_pal_007` | If a rectangle has length 24 cm and width 18 cm, what is its perimeter in cm? | **84** | solver (closed-form geometry: 2*(24 + 18) = 84) | `pal_007_en_orig`, `pal_007_en_para`, `pal_007_vi_trans` |
| `grp_pal_008` | A farmer has 120 chickens and cows in total. Together they have 320 legs. How many cows are on the farm? | **40** | solver (closed-form algebra: c+w=120, 2c+4w=320 -> w=40) | `pal_008_en_orig`, `pal_008_en_para`, `pal_008_vi_trans` |
| `grp_react_002` | A warehouse receives 24 crates of 18 boxes, 15 crates of 25 boxes, and 30 crates of 12 boxes. How many boxes in total were received? | **1167** | solver (exact chained sum: 24*18 + 15*25 + 30*12 = 1167) | `react_002_en_orig`, `react_002_en_para`, `react_002_vi_trans` |
| `grp_react_003` | Evaluate: 15% of 840 plus 25% of 620 minus 30% of 450. | **146** | solver (exact percentage evaluation: 0.15*840 + 0.25*620 - 0.30*450 = 146) | `react_003_en_orig`, `react_003_en_para`, `react_003_vi_trans` |
| `grp_react_004` | A trip has 3 segments: 145 km in 2 hours, 210 km in 3 hours, and 85 km in 1 hour. What is the total distance in km? | **440** | solver (exact distance summation: 145 + 210 + 85 = 440) | `react_004_en_orig`, `react_004_en_para`, `react_004_vi_trans` |
| `grp_react_007` | Evaluate: 3 * (45 + 55) - 4 * (120 - 85) + 250 / 5. | **210** | solver (arithmetic order of operations: 3*100 - 4*35 + 50 = 210) | `react_007_en_orig`, `react_007_en_para`, `react_007_vi_trans` |
| `grp_plain_002` | All roses are flowers. Some flowers fade quickly. Can we conclude with certainty that all roses fade quickly? Answer Yes or No. | **No** | human (syllogistic deductive logic: existential quantifier non-entailment -> No) | `plain_002_en_orig`, `plain_002_en_para`, `plain_002_vi_trans` |
| `grp_plain_003` | Five runners (A, B, C, D, E) finished a race. A finished before B but behind C. D finished before C but behind E. Who finished first? | **E** | human/solver (topological sort: E > D > C > A > B -> E) | `plain_003_en_orig`, `plain_003_en_para`, `plain_003_vi_trans` |
| `grp_plain_004` | If today is Tuesday, what day of the week will it be in exactly 100 days? | **Thursday** | solver (modulo calendar arithmetic: (Tuesday + 100 mod 7) = Thursday) | `plain_004_en_orig`, `plain_004_en_para`, `plain_004_vi_trans` |
| `grp_plain_005` | Tom is older than Jerry. Jerry is older than Spike. Tyke is younger than Spike. Is Tom older than Tyke? Answer Yes or No. | **Yes** | human (transitive relation deduction: Tom > Jerry > Spike > Tyke -> Yes) | `plain_005_en_orig`, `plain_005_en_para`, `plain_005_vi_trans` |
