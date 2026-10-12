# Quyết định Cổng Thực nghiệm Stage 0 (Stage 0 Gate Decision)

**Ngày thực hiện:** 2026-10-03  
**Quyết định:** **PASS** (Đủ điều kiện kích hoạt pilot mô hình thực tế trên tập development)

---

## 1. Bằng chứng kiểm thử & Xác thực

1. **Bộ test bắt buộc của đề tài NCKH:**
   ```bash
   python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
   ```
   * **Kết quả:** 22/22 tests PASS (100%).
   * Toàn bộ test suite dự án: 217/217 tests PASS.

2. **Benchmark Stage 0 (`scripts/benchmark_stage0.py`):**
   * **Trạng thái:** `complete` (Chạy độc lập trên snapshot 12.648 tài liệu / 35.045 chunks).
   * **Tính toàn vẹn cơ sở dữ liệu:** Hash trước và sau thực thi khớp nhau 100%:
     `5c04ac7592a646cca3d6fe353558f4ceb121fb997e7b8bd2d1002e8cd335cc00`
   * **Giám sát tài nguyên & LLM call:**
     * LLM / SLM calls: 0 (Kiểm tra nghiêm ngặt không phát sinh chi phí inference ngoài ý muốn).
     * Peak RSS: BM25 (110.6 MB), Lexical (117.3 MB), Vector (1048.7 MB), Hybrid (1075.0 MB).

3. **Audit Độ lệch Embedding (`scripts/audit_embedding_drift.py`):**
   * Mẫu ngẫu nhiên có seed cố định: 300 chunks liên kết hợp lệ.
   * Số lượng so sánh thành công: 300/300 (0 vector hỏng/invalid).
   * **289/300 chunks (96.33%)** có độ tương đồng Cosine tuyệt đối = 1.00000000.
   * **11 chunks** có Cosine < 0.99 thuộc về các chunk ID thời kỳ đầu (trước khi bản vá embedder fail-closed được kích hoạt). Không ảnh hưởng tới pipeline nghiên cứu mới.

---

## 2. Kết luận mở cổng

* Cổng Stage 0 chính thức **ĐẠT (PASS)**.
* Cho phép tiến hành bước tiếp theo: Chạy pilot mô hình thật trên dataset development riêng để đo lường token sinh, parser, confidence và tài nguyên hệ thống trước khi khóa cấu hình thực nghiệm chính.
