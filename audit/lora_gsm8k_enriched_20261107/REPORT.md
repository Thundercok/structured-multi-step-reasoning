# Báo cáo Thực nghiệm Huấn luyện LoRA Giàu Ngữ nghĩa (Enriched GSM8K)

> **Thời gian kết xuất:** report_generator.py tự động tạo  
> **Đối tượng so sánh:** Qwen3-8B Base Prefill vs. LoRA Cũ (2026-11-05) vs. LoRA Enriched (2026-11-07)

---

## 1. Bảng So sánh Hiệu năng trên 100 câu Dev (Dev100)

| Chế độ / Adapter | Đúng (Accuracy) | KTC Wilson 95% | Đúng định dạng (Format Valid) | KTC Wilson 95% | McNemar vs Base Prefill (p) | Token TB |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| Base Prefill (Mốc gốc) | 93/100 (93.0%) | 86.3–96.6% | 61/100 (61.0%) | 51.2–70.0% | N/A | 144.2 |
| Cũ Thường (2026-11-05) | 87/100 (87.0%) | 79.0–92.2% | 87/100 (87.0%) | 79.0–92.2% | p = 0.1460 | 157.2 |
| Cũ Phản thực (2026-11-05) | 83/100 (83.0%) | 74.5–89.1% | 95/100 (95.0%) | 88.8–97.8% | p = 0.0129 | 149.6 |
| **Mới Thường Enriched (2026-11-07)** | 82/100 (82.0%) | 73.3–88.3% | 95/100 (95.0%) | 88.8–97.8% | p = 0.0127 | 155.6 |
| **Mới Thường Enriched + Tool (`tuned_tool`)** | 82/100 (82.0%) | 73.3–88.3% | 95/100 (95.0%) | 88.8–97.8% | p = 0.0127 | 154.1 |
| **Mới Phản thực Enriched (2026-11-07)** | 87/100 (87.0%) | 79.0–92.2% | 95/100 (95.0%) | 88.8–97.8% | p = 0.1094 | 160.1 |
| **Mới Phản thực Enriched + Tool (`tuned_tool`)** | 87/100 (87.0%) | 79.0–92.2% | 97/100 (97.0%) | 91.5–99.0% | p = 0.1094 | 159.3 |

---

## 2. Kiểm định Giả thuyết Nghiên cứu Cốt lõi

### Cổng 0: Độ tuân thủ định dạng tự nhiên (Zero-Prefill Format Validity)
* **Bản thường Enriched:** 95/100 (KTC: 88.8–97.8%)
* **Bản phản thực Enriched:** 95/100 (KTC: 88.8–97.8%)
* **Kết luận Cổng 0:** ĐẠT (>= 90%)

## 3. Phân tích Chi tiết 19 Câu Từng Thất bại (19 Union Target Questions)
* **Bối cảnh tập 19 câu:** Là hợp (union) các câu trên Dev-100 mà `base_prefill` giải đúng nhưng adapter cũ sai:
  - `old_plain`: 10/19 đúng (9 câu sai, 15/19 format_valid).
  - `old_cf`: 7/19 đúng (12 câu sai, 18/19 format_valid).
  - `old_cf + runtime prefill`: phục hồi được **15/19** câu.
* **Kết quả Bản thường Enriched (`gsm8k_enriched_2000_s0`):**
  - Đạt **13/19 (68.4%)** đúng zero-prefill, đúng định dạng **18/19**.
  - Phục hồi **6/9 (66.7%)** câu từng sai của `old_plain`.
  - Phục hồi **8/12 (66.7%)** câu từng sai của `old_cf`.
* **Phân bố trên 81 câu còn lại trên Dev-100:**
  - `enriched_plain` đúng **69/81** câu (so với 77/81 của `old_plain`), dẫn đến tổng thể Dev-100 đạt **82/100**.
  - Tỷ lệ đúng định dạng (`format_valid`) toàn bộ đạt **95/100** [88.8–97.8%], giúp SFT thuần vượt qua Cổng 0 mà không cần dữ liệu phản thực.
* **Kết quả Bản phản thực Enriched (`gsm8k_cf_enriched_2000_s0`):**
  - Đạt **15/19 (78.9%)** đúng zero-prefill, đúng định dạng **18/19**.
  - Phục hồi **7/9 (77.8%)** câu từng sai của `old_plain`.
  - Phục hồi **10/12 (83.3%)** câu từng sai của `old_cf`.

### So sánh Đối đầu Trực tiếp (Enriched CF vs. Old CF):
* Số câu chỉ bản mới đúng: **11**
* Số câu chỉ bản cũ đúng: **7**
* Số câu chỉ bản mới đúng định dạng: **5**
* Số câu chỉ bản cũ đúng định dạng: **5**

## 4. Phân tích Can thiệp Phản thực (Causal Faithfulness)
### Kết quả Can thiệp trên `enriched_plain`:
```json
{
  "tuned": {
    "eligible": {
      "n": 73,
      "follows": 55,
      "follows_rounded": 12,
      "reverted": 2,
      "other": 3,
      "moved": 1,
      "no_answer": 0
    },
    "eligibility_rate": 0.73,
    "skipped": {
      "invalid_format": 5,
      "no_result_used_later": 6,
      "too_few_calcs": 3,
      "ambiguous_propagation": 11,
      "answer_needs_comparison": 2
    },
    "rq1": {
      "moved|clean": {
        "n": 70,
        "wrong": 9
      },
      "moved|flagged": {
        "n": 1,
        "wrong": 1
      },
      "unmoved|clean": {
        "n": 2,
        "wrong": 0
      }
    },
    "correct_only": {
      "n": 63,
      "follows": 49,
      "follows_rounded": 12,
      "reverted": 2,
      "other": 0,
      "moved": 0,
      "no_answer": 0
    },
    "shared": {
      "n": 73,
      "follows": 55,
      "follows_rounded": 12,
      "reverted": 2,
      "other": 3,
      "moved": 1,
      "no_answer": 0
    },
    "shared_correct_only": {
      "n": 63,
      "follows": 49,
      "follows_rounded": 12,
      "reverted": 2,
      "other": 0,
      "moved": 0,
      "no_answer": 0
    }
  }
}
```
### Kết quả Can thiệp trên `enriched_cf`:
```json
{
  "tuned": {
    "eligible": {
      "n": 66,
      "follows": 55,
      "follows_rounded": 6,
      "reverted": 2,
      "other": 2,
      "moved": 1,
      "no_answer": 0
    },
    "eligibility_rate": 0.66,
    "skipped": {
      "ambiguous_propagation": 11,
      "no_result_used_later": 10,
      "invalid_format": 5,
      "too_few_calcs": 5,
      "answer_needs_comparison": 3
    },
    "rq1": {
      "moved|clean": {
        "n": 63,
        "wrong": 5
      },
      "moved|flagged": {
        "n": 1,
        "wrong": 0
      },
      "unmoved|clean": {
        "n": 1,
        "wrong": 0
      },
      "unmoved|flagged": {
        "n": 1,
        "wrong": 0
      }
    },
    "correct_only": {
      "n": 61,
      "follows": 52,
      "follows_rounded": 6,
      "reverted": 2,
      "other": 0,
      "moved": 1,
      "no_answer": 0
    },
    "shared": {
      "n": 66,
      "follows": 55,
      "follows_rounded": 6,
      "reverted": 2,
      "other": 2,
      "moved": 1,
      "no_answer": 0
    },
    "shared_correct_only": {
      "n": 61,
      "follows": 52,
      "follows_rounded": 6,
      "reverted": 2,
      "other": 0,
      "moved": 1,
      "no_answer": 0
    }
  }
}
```
