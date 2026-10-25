> **Evidence correction, 2026-10-25:** Historical exposed-development replay only. Candidate token costs are equal-share imputations, not observed per-candidate costs. The loader uses literal-string scoring; a diagnostic finds 74/500 disagreements with the existing procedural checker. Headline claims below are not accepted research conclusions. See `../rat_agentic_integrity_20261025/stopping_review/README.md`. Raw results remain preserved; Stage 0 unchanged.

# Báo cáo Thực nghiệm Offline Stopping Rules & Phân tích Đánh đổi Pareto

- **Tập dữ liệu nguồn:** `audit/run11_sweep_trace.jsonl` (100 câu hỏi, cánh Self-Consistency)
- **Số lượt hoán vị ngẫu nhiên ($R$):** 30
- **Phương pháp tái lập:** Paired Bootstrap CI 95% ($B=2.000$ draws), seed ngẫu nhiên 42
- **Biểu đồ Pareto:** Lưu tại `stopping_pareto_curve.png`

## Bảng Kết quả Chi tiết

| Họ (Family) | Quy tắc Dừng (Rule) | Accuracy (95% CI) | Tokens (95% CI) | Δ Acc vs k=5 | Δ Tokens vs k=5 | Tiết kiệm (%) | Pareto? |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :---: |
| Oracle | Oracle (Omniscient) | 0.4517 [0.3587, 0.5453] | 430.8 [371.8, 492.1] | +0.0197 [+0.0080, +0.0337] | -1545.5 [-1749.7, -1347.6] | 78.2% | Không |
| Fixed-k | Fixed-k=1 | 0.4223 [0.3347, 0.5143] | 395.2 [344.0, 446.2] | -0.0097 [-0.0350, +0.0130] | -1581.0 [-1784.8, -1376.1] | 80.0% | **CÓ** |
| Fixed-k | Fixed-k=2 | 0.4223 [0.3347, 0.5143] | 790.5 [688.1, 892.4] | -0.0097 [-0.0350, +0.0130] | -1185.8 [-1338.6, -1032.1] | 60.0% | Không |
| Fixed-k | Fixed-k=3 | 0.4320 [0.3413, 0.5250] | 1185.8 [1032.1, 1338.6] | +0.0000 [-0.0163, +0.0150] | -790.5 [-892.4, -688.1] | 40.0% | **CÓ** |
| Fixed-k | Fixed-k=4 | 0.4327 [0.3407, 0.5273] | 1581.0 [1376.1, 1784.8] | +0.0007 [-0.0100, +0.0103] | -395.2 [-446.2, -344.0] | 20.0% | **CÓ** |
| Fixed-k | Fixed-k=5 | 0.4320 [0.3370, 0.5263] | 1976.2 [1720.1, 2231.0] | +0.0000 [+0.0000, +0.0000] | +0.0 [+0.0, +0.0] | 0.0% | Không |
| Margin | Margin-m=1 | 0.4223 [0.3347, 0.5143] | 395.2 [344.0, 446.2] | -0.0097 [-0.0350, +0.0130] | -1581.0 [-1784.8, -1376.1] | 80.0% | Không |
| Margin | Margin-m=2 | 0.4310 [0.3363, 0.5263] | 1624.4 [1352.7, 1898.6] | -0.0010 [-0.0030, +0.0000] | -351.9 [-416.6, -290.0] | 17.8% | Không |
| Margin | Margin-m=3 | 0.4320 [0.3370, 0.5263] | 1820.0 [1548.1, 2092.2] | +0.0000 [+0.0000, +0.0000] | -156.2 [-197.2, -119.3] | 7.9% | Không |
| Beta-Top2 | Beta-Top2 (θ=0.70) | 0.4223 [0.3347, 0.5143] | 395.2 [344.0, 446.2] | -0.0097 [-0.0350, +0.0130] | -1581.0 [-1784.8, -1376.1] | 80.0% | Không |
| Beta-Top2 | Beta-Top2 (θ=0.80) | 0.4310 [0.3363, 0.5263] | 1624.4 [1352.7, 1898.6] | -0.0010 [-0.0030, +0.0000] | -351.9 [-416.6, -290.0] | 17.8% | Không |
| Beta-Top2 | Beta-Top2 (θ=0.85) | 0.4310 [0.3363, 0.5263] | 1649.3 [1374.9, 1925.0] | -0.0010 [-0.0030, +0.0000] | -326.9 [-386.2, -270.9] | 16.5% | Không |
| Beta-Top2 | Beta-Top2 (θ=0.90) | 0.4320 [0.3370, 0.5263] | 1820.0 [1548.1, 2092.2] | +0.0000 [+0.0000, +0.0000] | -156.2 [-197.2, -119.3] | 7.9% | Không |
| Beta-Top2 | Beta-Top2 (θ=0.95) | 0.4320 [0.3370, 0.5263] | 1909.8 [1645.3, 2173.3] | +0.0000 [+0.0000, +0.0000] | -66.5 [-86.9, -48.0] | 3.4% | Không |
| Beta-Rest | Beta-Rest (θ=0.70) | 0.4223 [0.3347, 0.5143] | 395.2 [344.0, 446.2] | -0.0097 [-0.0350, +0.0130] | -1581.0 [-1784.8, -1376.1] | 80.0% | Không |
| Beta-Rest | Beta-Rest (θ=0.80) | 0.4310 [0.3363, 0.5263] | 1624.4 [1352.7, 1898.6] | -0.0010 [-0.0030, +0.0000] | -351.9 [-416.6, -290.0] | 17.8% | Không |
| Beta-Rest | Beta-Rest (θ=0.85) | 0.4310 [0.3363, 0.5263] | 1649.3 [1374.9, 1925.0] | -0.0010 [-0.0030, +0.0000] | -326.9 [-386.2, -270.9] | 16.5% | Không |
| Beta-Rest | Beta-Rest (θ=0.90) | 0.4320 [0.3370, 0.5263] | 1820.0 [1548.1, 2092.2] | +0.0000 [+0.0000, +0.0000] | -156.2 [-197.2, -119.3] | 7.9% | Không |
| Beta-Rest | Beta-Rest (θ=0.95) | 0.4320 [0.3370, 0.5263] | 1909.8 [1645.3, 2173.3] | +0.0000 [+0.0000, +0.0000] | -66.5 [-86.9, -48.0] | 3.4% | Không |
| ESC-Window | ESC-Window (w=2) | 0.4287 [0.3350, 0.5240] | 1558.7 [1294.3, 1829.1] | -0.0033 [-0.0093, +0.0007] | -417.6 [-487.0, -352.0] | 21.1% | Không |
| ESC-Window | ESC-Window (w=3) | 0.4320 [0.3370, 0.5263] | 1807.5 [1535.7, 2078.9] | +0.0000 [+0.0000, +0.0000] | -168.8 [-211.6, -130.1] | 8.5% | Không |

## Nhận định Khoa học Cốt lõi

1. **Ngưỡng tiệm cận độ chính xác:** `Fixed-k=3` đạt độ chính xác tương đương `Fixed-k=5` (0.4320) nhưng tiết kiệm **40.0%** chi phí token (1.185.8 tokens vs 1.976.2 tokens).
2. **Cơ chế dừng thích ứng Adaptive-Consistency (Beta-Top2 / Margin):**
   - Ở ngưỡng $\theta=0.80$ hoặc $m=2$, phương pháp đạt độ chính xác 0.4310 (chỉ kém 0.001 so với k=5) trong khi tiết kiệm được **17.8%** token.
   - Ở ngưỡng $\theta=0.90$ hoặc $m=3$, phương pháp đạt độ chính xác ngang bằng k=5 (0.4320) và tiết kiệm **7.9%** token.
3. **ESC Window ($w=2$):** Đạt độ chính xác 0.4287 và tiết kiệm **21.1%** token so với k=5.
4. **Oracle (Trần lý thuyết):** Dừng tại k sớm nhất khi đa số phiếu đã đúng đạt độ chính xác 0.4517 ở mức chi phí chỉ 430.8 tokens (tiết kiệm **78.2%** token), cho thấy tiềm năng tối ưu hóa rất lớn nếu có bộ phân định chân lý tốt.