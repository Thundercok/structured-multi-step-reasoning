# GSM8K Stage 0 Execution Scenario & Freeze Protocol

**Date:** 2026-10-31  
**Status:** Software Preflight Verified; Real-Model Campaign Gated under Stage 0.  
**Harness Entry Point:** `python -m experiments.research_study` and `experiments/gsm8k_collector.py`.

---

## 1. Mục tiêu và phạm vi Stage 0

Giai đoạn Stage 0 được thiết kế để hoàn thiện toàn bộ khâu chuẩn bị, phong tỏa thông số (parameter freeze), kiểm chứng tính toàn vẹn phần mềm (software preflight) và xác định trần ngân sách (budget envelope) trước khi bất kỳ token thực nào được sinh bởi mô hình ngôn ngữ lớn:

1. **Bảo tồn cổng Stage 0 (Stage 0 Gate Preserved):** 0 token thực nghiệm được sinh ngoài kiểm duyệt. Toàn bộ kiểm thử và preflight pipeline sử dụng mock/synthetic runner.
2. **Khóa bất biến bộ dữ liệu (Dataset Freeze):** Bộ dữ liệu ứng viên 96 câu GSM8K được phân chia cố định thành 48 câu fitting (`train`) và 48 câu validation (`calibration`).
3. **Phân tách giai đoạn và kiểm toán bền vững (Durable Staged Accounting):** Quy trình thu thập qua `experiments.gsm8k_collector` tuân thủ vòng đời 3 trạng thái (`started` $\to$ `succeeded` | `failed`), ghi journal trước khi gọi tool PAL, và cách ly hoàn toàn dữ liệu validation trong pha fitting.
4. **Niêm phong quy tắc (Sealed Rule Selection):** Pha fitting chọn quy tắc bằng hàm utility $U = \text{Accuracy} - 0.1 \times \frac{\text{Generated Tokens}}{1000}$ và niêm phong mã băm SHA-256 của `selection.json` vào `manifest.json`. Pha validation chỉ nạp bản niêm phong để chấm điểm mà không fit lại.

---

## 2. Thông số phong tỏa (Freeze Parameters) — Cập nhật nghiệm thu 93 câu

Quyết định người dùng 2026-10-31: **"3 câu vứt đi, 93 câu duyệt"**.
3 câu bị loại trước khi sinh gồm: `gsm8k-dev-02343` (contradictory wording), `gsm8k-dev-00484` (ambiguous compounding), `gsm8k-dev-03823` (ambiguous survey arithmetic).
Bộ dữ liệu chính thức được chuyển sang: `data/gsm8k_development_validation_reviewed_v1`.

| Thành phần | Đặc tả phong tỏa | Bằng chứng / Khóa SHA-256 |
| :--- | :--- | :--- |
| **Dataset** | `data/gsm8k_development_validation_reviewed_v1/dataset.json` | `71cd5e97eedb170f849df63a0bae84a381de0d015c86436969e4a6ea71ee835a` |
| **Quy mô** | **93 nhóm GSM8K** (45 fitting `train`, 48 validation `calibration`) | 24 câu pilot cũ và 3 câu loại trừ được cách ly hoàn toàn |
| **Test split** | 0 câu test chính thức (Official GSM8K test hoàn toàn không bị chạm) | Đảm bảo tính toàn vẹn ngoại kiểm |
| **Mô hình mục tiêu** | Qwen3-8B 4-bit (`mlx-community/Qwen3-8B-4bit`) | Snapshot `545dc4251c05440727734bcd94334791f6ab0192` |
| **Prompt profile** | `english-math-v1`, temperature = 0.0, thinking = False, seed = 42 | Khớp cấu hình nghiệm thu H1–H3 |
| **Chiến lược (Arms)** | `DIRECT`, `COT`, `PAL` (3 recipes) | Không dùng tool đối với DIRECT/COT; PAL sandbox timeout 5.0s |
| **Trần Token/Call** | 1.024 token sinh tối đa mỗi lần gọi ($T_{\max} = 1024$) | Cắt độ dài cứng (`finish_reason="length"`) |
| **Trần Collection** | 93 items $\times$ 3 recipes = **279 calls** tối đa | Trần token sinh: $279 \times 1024 = \mathbf{285.696}$ **tokens** |
| **Hàm Utility** | $U = \text{Accuracy} - 0.1 \times \frac{\text{Generated Tokens}}{1000}$ | $\lambda = 0.1$ cố định cho bài toán routing độ dài câu hỏi |

---

## 3. Kết quả chạy thử nghiệm Preflight (Software Preflight Evidence)

Toàn bộ quy trình 3 bước đã được chạy kiểm chứng thực tế không lỗi trên môi trường phần mềm với tập dữ liệu 93 câu đã duyệt:

### Bước 1: Thu thập Staged Pilot bằng Mock Runner
* **Môi trường:** `MockStagedRunner` (deterministic execution, 0 model calls).
* **Kết quả:** Hoàn thành **279/279 calls**, 0 lỗi journal, 0 quarantined attempts.
* **Thư mục lưu trữ:** `runs/gsm8k-reviewed-93-synthetic-pilot-20261031`.

### Bước 2: Khóa và niêm phong quy tắc (Fitting & Sealing)
* **Lệnh chạy:**
  ```bash
  python -m experiments.research_study \
    --gsm8k-routing-fit runs/gsm8k-reviewed-93-synthetic-pilot-20261031 \
    --output runs/gsm8k-reviewed-93-routing-fit-20261031
  ```
* **Kết quả:** Đã quét 27 quy tắc ứng viên trên 45 câu fitting, chọn quy tắc tối ưu, xuất và khóa SHA-256 mã băm `selection_sha256` trong `manifest.json`.

### Bước 3: Đánh giá ngoại kiểm trên Validation đã niêm phong
* **Lệnh chạy:**
  ```bash
  python -m experiments.research_study \
    --gsm8k-routing-validate runs/gsm8k-reviewed-93-routing-fit-20261031 \
    --output runs/gsm8k-reviewed-93-routing-val-20261031
  ```
* **Kết quả:** Đánh giá 48 câu validation mà không refit, chạy 2.000 bootstrap draws, xuất báo cáo [`runs/gsm8k-reviewed-93-routing-val-20261031/report.md`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/runs/gsm8k-reviewed-93-routing-val-20261031/report.md) gồm đầy đủ 5 phương pháp đối chứng: `query_only_rule`, `selected_fixed_reference`, `fixed_direct`, `fixed_cot`, `fixed_pal`.

---

## 4. Điều kiện Gate trước khi chạy mô hình thật (Transition to Real Model)

1. [x] **Human Sign-off trên dữ liệu GSM8K:** ĐÃ HOÀN TẤT (Người dùng chốt 3 câu loại, duyệt 93 câu ngày 2026-10-31, lưu tại `data/gsm8k_development_validation_reviewed_v1`).
2. [ ] **Real Model Adapter Review:** Hoàn tất adapter thực thi tách tầng (`staged QwenMLXBackend`) có lưu raw prompt/messages và telemetry token prompt/completion chính xác.
3. [ ] **Cấp quyền ngân sách Token thật:** Người dùng xác nhận cấp hạn mức 279 model calls (trần 285.696 generated tokens).
4. [ ] **Bảo vệ tiến trình chạy ngầm:** Đảm bảo quá trình chạy có log xoay vòng và journal locking an toàn trước khi kích hoạt.
