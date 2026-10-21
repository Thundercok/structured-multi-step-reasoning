# Handoff: Sửa Review và Hoàn tất Gom Cấu trúc Canonical `reasoning/` Hệ RAT–CoT

## 1. Mục tiêu và Bối cảnh Thực hiện

- **Định hướng hệ thống**: RAT sử dụng CoT, CoT được thể hiện qua RAT. Không đối xử như hai dự án độc lập.
- **Ranh giới module ngoài và trạng thái working tree**:
  - Watch bot & EVRP: Đã gỡ sạch; archive và bundle trong `scratch/` và `.migration-backups/` được bảo toàn nguyên vẹn.
  - Spider: Upstream ở `Thundercok/tdtu-timetable-compiler` (commit `e21fcef`); adapter Python trong RAT giữ trạng thái tắt mặc định (`enable_web=False`).
  - DocAI: Đã được xác nhận gỡ bỏ (`modules/docai/` đã xóa, export phục hồi đã kiểm chứng ở `audit/docai_removal_20261017/` và `audit/docai_standalone_prepare_20261017/manifest.json`). Không khôi phục.
  - `document_intake/`: Giữ ở thư mục gốc làm hạ tầng PDF/OCR dùng chung. Khi DocAI tách repo, cấp dưới dạng dependency/wheel, không nhân bản mã OCR.
  - `qwen_backend.py`: Đã gỡ bỏ, không còn trong working tree.

---

## 2. Các Điểm Đã Sửa Sau Review Codex (`review.md`)

### P1 — Cập nhật Source Provenance Hashing (`experiments/research_study.py`)
- `source_hashes()` tại dòng 344 đã được mở rộng để hash đồng thời:
  - 5 tệp canonical: `reasoning/__init__.py`, `reasoning/entry_predictor.py`, `reasoning/optimal_stopping.py`, `reasoning/reasoning_env.py`, `reasoning/reasoning_strategies.py`.
  - 4 tệp shims tương thích tại thư mục gốc: `entry_predictor.py`, `optimal_stopping.py`, `reasoning_env.py`, `reasoning_strategies.py`.
  - Cùng các tệp hạ tầng nghiên cứu khác (tổng cộng 17 files).
- **Kiểm thử Fingerprint**: Đã chạy test xác minh độc lập: sửa đổi 1 byte trong canonical `reasoning/reasoning_strategies.py` làm thay đổi trực tiếp giá trị SHA256 tương ứng trong manifest, bảo đảm tính trung thực của bằng chứng nghiên cứu.

### P1 — Đính chính Hiện trạng Tích hợp `meta_reasoner.py`
- AST analysis xác nhận: `rat/engine/meta_reasoner.py` lines 21-22 chỉ import `EntryPredictor` và `EntryChoice`, **hoàn toàn chưa khởi tạo, huấn luyện (fit), hay gọi dự đoán (choose/score)**.
- `MetaReasoner.__init__` (lines 83-85): tạo `self.policy = OptimalStoppingPolicy(lam=0.02)` rồi gán cứng `self.policy.tau = [0.671, 0.688]`. Comment "Pre-fitted" không có bằng chứng run artifact được kiểm duyệt kèm theo.
- Nhánh policy (lines 335-347): dùng độ tự tin cố định `conf_initial = 0.58`, so trực tiếp `self.policy.tau[0]`, sinh chuỗi text mô phỏng "Đồng thuận (5/5)". Tại đây **không gọi `should_escalate` và không chạy lấy mẫu 5 lần**.
- Đã ghi nhận trung thực đây là lát cắt heuristic/simulation phục vụ demo giao diện RAT; việc nối đầy đủ `EntryPredictor` và stopping thật vào `MetaReasoner` thuộc core backlog, không can thiệp thuật toán trong refactor cấu trúc.

### P2 — Đính chính Phân tích Harness `research_study.py`
- `research_study.fit_policies()` (lines 251-257): fit `OptimalStoppingPolicy` trên split `calibration` và fit `EntryPredictor` trên split `train` qua `entry_training_data()`.
- Entry point này **không gọi `collect_entry_training_data` và không khởi tạo Gym episode loop `ReasoningEnv`**; việc đánh giá trên split `test` được thực hiện qua hàm `evaluate_records()` replay lại các attempts đã log tĩnh.
- `OptimalStoppingPolicy.fit()` có tham số mặc định `n_bootstraps=0`; research study entry point không bật bootstrap CI khi fit policy.

### P2 — Cơ chế Shims: Module Identity, Private Helpers, và Monkeypatching
- Không dùng wildcard `from reasoning.* import *` vì wildcard bỏ sót các helper private (`_eval_arith`) và tạo ra 2 module objects tách rời, làm gãy monkeypatching và `isinstance` checks.
- Sử dụng pattern `sys.modules` aliasing có lưu tên shim trước khi cập nhật globals:
  ```python
  import sys
  from reasoning import <module_name> as _canonical

  _shim_name = __name__
  globals().update({k: getattr(_canonical, k) for k in dir(_canonical)})
  sys.modules[_shim_name] = _canonical
  ```
- Kết quả: `sys.modules[shim] is sys.modules[canonical]` trả về `True` cho cả 4 module; `unittest.mock.patch` qua tên shim cập nhật trực tiếp vào module canonical.
- Package initializer `reasoning/__init__.py` được thiết kế cực nhẹ (chỉ khai báo `__all__`), không eager-import `sklearn`, `gymnasium`, `mlx` hay `PyQt`.

### P2 — Mẫu số Đếm và Tác động Vật lý Trung thực
- Đã loại bỏ `modules/docai/` và `qwen_backend.py` khỏi danh sách consumers và denominators.
- Thống kê working tree hiện tại (loại trừ `audit/`, `scratch/`, `work/`, `.venv/`): **782 product files** (365 python files).
- Số dòng code vật lý:
  - Baseline trước gom: 4 files, 1,035 dòng (885 non-blank).
  - Canonical `reasoning/`: 5 files, 1,056 dòng (891 non-blank).
  - Root shims: 4 files, 52 dòng (40 non-blank).
  - **Tác động thuần**: $+73$ dòng tổng ($+46$ dòng non-blank), $+2,267$ bytes do việc duy trì song song package canonical và shims tương thích. Không tuyên bố delta vật lý bằng 0.
  - **Logic thuật toán**: Giữ nguyên $100\%$, 0 thay đổi model/prompt/policy.

---

## 3. Bản đồ Consumers Working Tree Hiện hành (`import_map.json`)

| Module Lõi | Tổng Consumers | RAT Desktop | Research Harness | Tests | Scripts | Nội bộ `reasoning/` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `entry_predictor` | **6** | 1 (`meta_reasoner.py` - stub import) | 3 | 1 | 0 | 1 |
| `optimal_stopping` | **7** | 1 (`meta_reasoner.py` - fixed tau) | 3 | 2 | 0 | 1 |
| `reasoning_env` | **19** | 1 (`meta_reasoner.py`) | 6 | 7 | 2 | 2 |
| `reasoning_strategies` | **29** | 5 | 6 | 7 | 10 | 0 |

---

## 4. Kết quả Kiểm thử (`tests.log`)

Toàn bộ 4 test suites liên quan đều pass $100\%$:
1. **Research Study & Optimal Stopping / Predictor (theo `AGENTS.md`)**:
   - `tests/test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py` -> **29 passed in 9.12s**.
2. **Core Reasoning Environment & Strategies**:
   - `test_reasoning_env.py`, `test_reasoning_strategies.py`, `tests/test_research_scoring.py` -> **53 passed in 7.19s**.
3. **Qwen MLX Mocked Backend**:
   - `test_qwen_mlx_backend_mocked.py` -> **26 passed in 1.90s** (chạy unsandboxed do Metal shader compilation của macOS).
4. **RAT Runtime & Work Context**:
   - `tests/test_spider_adapter.py`, `tests/test_assistant_runtime.py`, `tests/test_work_context.py` -> **93 passed in 23.54s**.
5. **Shim Identity & Import Isolation**:
   - Cả 4 shims khớp tuyệt đối `sys.modules` canonical objects.
   - Fresh import `reasoning` và `reasoning.reasoning_strategies` không nạp bất kỳ thư viện nặng nào (`sklearn`, `gymnasium`, `PyQt`, `mlx` = `[]`).

---

## 5. Danh mục Artifacts và Tệp Bàn giao

1. [`docs/rat_cot_structural_consolidation_20261017.md`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/docs/rat_cot_structural_consolidation_20261017.md)
2. [`audit/rat_cot_structural_consolidation_20261017/import_map.json`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_structural_consolidation_20261017/import_map.json)
3. [`audit/rat_cot_structural_consolidation_20261017/contract_comparison.json`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_structural_consolidation_20261017/contract_comparison.json)
4. [`audit/rat_cot_structural_consolidation_20261017/footprint.json`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_structural_consolidation_20261017/footprint.json)
5. [`audit/rat_cot_structural_consolidation_20261017/tests.log`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_cot_structural_consolidation_20261017/tests.log)
6. Canonical Package:
   - [`reasoning/__init__.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/__init__.py)
   - [`reasoning/entry_predictor.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/entry_predictor.py)
   - [`reasoning/optimal_stopping.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/optimal_stopping.py)
   - [`reasoning/reasoning_env.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/reasoning_env.py)
   - [`reasoning/reasoning_strategies.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning/reasoning_strategies.py)
7. Root Compatibility Shims:
   - [`entry_predictor.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/entry_predictor.py)
   - [`optimal_stopping.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/optimal_stopping.py)
   - [`reasoning_env.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning_env.py)
   - [`reasoning_strategies.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/reasoning_strategies.py)
8. Updated Research Study:
   - [`experiments/research_study.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/experiments/research_study.py) (dòng 344 `source_hashes()`).
