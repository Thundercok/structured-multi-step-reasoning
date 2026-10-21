# Hợp nhất Cấu trúc trong Hệ RAT–CoT — 2026-10-17

## 1. Định hướng cốt lõi và Ranh giới hệ thống

Theo quyết định đã chốt tại `AGENTS.md` và `docs/project_scope.md`:
> **RAT SỬ DỤNG CoT; CoT ĐƯỢC THỂ HIỆN BẰNG RAT.**
> RAT là implementation chính của CoT. Phương pháp, runtime, harness và hạ tầng là các vai trò trong cùng một hệ; không tách rời thành hai dự án độc lập.

- **Watch bot & EVRP**: Đã gỡ bỏ sạch khỏi working tree; các bản archive và git bundle được bảo toàn nguyên vẹn trong `.migration-backups/` và `scratch/`. Tuyệt đối không khôi phục hoặc import lại vào RAT–CoT.
- **Spider**: Mã nguồn upstream đã chuyển sang `Thundercok/tdtu-timetable-compiler` tại commit `e21fcef`. Adapter Python tùy chọn trong `rat/crawler/spider_adapter.py` tiếp tục được giữ lại ở trạng thái **tắt mặc định** (`enable_web=False` trong `rat/work_context/registry.py`).
- **DocAI**: Đã được xác nhận gỡ bỏ (`modules/docai/` đã xóa, export phục hồi đã kiểm chứng ở `audit/docai_removal_20261017/` và `audit/docai_standalone_prepare_20261017/manifest.json`). Không khôi phục.
- **Hạ tầng OCR dùng chung (`document_intake/`)**: Được giữ ở thư mục gốc repo. Khi tách DocAI sang repo riêng sau này, DocAI phải tiêu thụ `document_intake` dưới dạng package wheel/dependency độc lập, không sao chép thêm một bản OCR mới vào nội bộ DocAI.
- **`qwen_backend.py`**: Đã gỡ bỏ khỏi working tree, không còn là consumer.

---

## 2. Bản đồ Imports và Hiện trạng 4 Module Reasoning Lõi

Bốn module reasoning cốt lõi đã được chuyển vào package canonical `reasoning/` và giữ 4 file shims tương thích tại thư mục gốc (`./`):
1. `entry_predictor.py` -> shim trỏ `reasoning.entry_predictor` (13 dòng)
2. `optimal_stopping.py` -> shim trỏ `reasoning.optimal_stopping` (13 dòng)
3. `reasoning_env.py` -> shim trỏ `reasoning.reasoning_env` (13 dòng)
4. `reasoning_strategies.py` -> shim trỏ `reasoning.reasoning_strategies` (13 dòng)

Bản canonical trong `reasoning/`:
1. `reasoning/__init__.py` (11 dòng, 6 non-blank, 259 bytes - lightweight, không import sklearn/Gym/Qt)
2. `reasoning/entry_predictor.py` (101 dòng, 78 non-blank, 4,772 bytes)
3. `reasoning/optimal_stopping.py` (289 dòng, 245 non-blank, 12,756 bytes)
4. `reasoning/reasoning_env.py` (185 dòng, 157 non-blank, 7,752 bytes)
5. `reasoning/reasoning_strategies.py` (470 dòng, 411 non-blank, 18,308 bytes)

### Thống kê Consumers qua Rà soát Tự động trên Working Tree Hiện hành

| Module Lõi | Tổng Consumer Files | RAT Desktop (`rat/`) | Research Harness (`experiments/`, `pipeline.py`) | Tests (`test_*.py`, `tests/`) | Scripts (`scripts/`) | Reasoning Nội bộ |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `entry_predictor` | **6** | 1 (`rat/engine/meta_reasoner.py`)* | 3 (`research_study.py`, `benchmark_reasoning.py`, `pipeline.py`) | 1 (`test_entry_predictor.py`) | 0 | 1 (`reasoning/optimal_stopping.py`) |
| `optimal_stopping` | **7** | 1 (`rat/engine/meta_reasoner.py`) | 3 (`research_study.py`, `benchmark_reasoning.py`, `pipeline.py`) | 2 (`test_optimal_stopping.py`, `test_entry_predictor.py`) | 0 | 1 (`reasoning/entry_predictor.py`) |
| `reasoning_env` | **19** | 1 (`rat/engine/meta_reasoner.py`) | 6 (`research_study.py`, `research_aggregate.py`, `research_pilot.py`, `pilot_real_model.py`, `benchmark_reasoning.py`, `pipeline.py`) | 7 (`test_reasoning_env.py`, `test_entry_predictor.py`, `test_optimal_stopping.py`, `test_agent.py`, `test_qwen_mlx_backend_mocked.py`, `tests/test_benchmark_reasoning.py`, `tests/test_harness_regressions.py`) | 2 (`scripts/run_smoke_b_lite.py`, `scripts/summarize_math_baselines.py`) | 2 (`reasoning/entry_predictor.py`, `reasoning/optimal_stopping.py`) |
| `reasoning_strategies` | **29** | 5 (`meta_reasoner.py`, `vgc.py`, `main.py`, `omnibar.py`, `spotlight_window.py`) | 6 (`research_study.py`, `pipeline.py`, `research_scoring.py`, `direct_cot_analysis.py`, `cot_restart_pilot.py`, `cot_restart_replay.py`, `benchmark_reasoning.py`) | 7 (`test_reasoning_strategies.py`, `test_research_scoring.py`, `test_qwen_mlx_backend_mocked.py`, `tests/test_harness_regressions.py`, `tests/test_cot_restart_pilot.py`, `tests/test_cot_restart_replay.py`, `tests/test_sweep_and_oracle.py`) | 10 (các scripts sweep, report, agreement) | 0 |

*\* Lưu ý: AST check xác nhận `meta_reasoner.py` chỉ import `EntryPredictor` và `EntryChoice`, chưa khởi tạo hoặc gọi.*

---

## 3. Đối chiếu Hợp đồng: Headless Harness vs Desktop RAT

Nguyên tắc bắt buộc: **Không suy ra tương đương hành vi từ việc dùng chung tên lớp hay imports.**

### A. Dual Entry Predictor (`entry_predictor.py`)
- **Thuật toán dùng chung**: RTR-style predictor kết hợp hồi quy chi phí (Ridge) và xác suất đúng (LogisticRegression) cho 3 candidate (`LADDER`, `REACT`, `PAL`).
- **Harness Headless (`experiments/research_study.py`)**:
  - `fit_policies()` fit predictor trên split `train` bằng `entry_training_data(train, policy, use_ladder)`.
  - Đánh giá trên split `test` qua replay offline records; dự đoán điểm $S = \text{acc} - \lambda \cdot \text{cost}$.
- **Desktop RAT (`rat/engine/meta_reasoner.py`) — Hiện trạng thực tế**:
  - AST check xác nhận `meta_reasoner.py` lines 21-22 chỉ import `EntryPredictor` và `EntryChoice`, **không hề khởi tạo (instantiate), huấn luyện (fit), hay gọi dự đoán (choose/score)**.
  - Phân loại query của desktop hiện phụ thuộc hoàn toàn vào các bộ lọc regex / keyword tĩnh (`is_reasoning_query`, `_solve_with_pal`, `_solve_policy_with_ladder`).
  - **Khoảng trống tích hợp**: Việc nối `EntryPredictor` thật vào runtime `MetaReasoner` là nhiệm vụ backlog cốt lõi, không tự ý sửa đổi thuật toán trong đợt structural refactor này.

### B. Optimal Stopping Policy (`optimal_stopping.py`)
- **Thuật toán dùng chung**: Quy hoạch động lùi (backward induction) tối ưu ngưỡng $\tau_0$ (CoT) và $\tau_1$ (SC) qua hàm `fit_threshold`. Hỗ trợ hiệu chuẩn Platt / Isotonic. `fit()` có mặc định `n_bootstraps=0`.
- **Harness Headless (`experiments/research_study.py`) — Hiện trạng thực tế**:
  - `fit_policies()` fit stopping trên split `calibration` (không bật bootstrap, `n_bootstraps=0`).
  - Đánh giá test qua `evaluate_records()`, replay offline các attempts đã log; **không khởi tạo Gym episode loop `ReasoningEnv` hay rollout LLM online** trong entry point này.
- **Desktop RAT (`rat/engine/meta_reasoner.py`) — Hiện trạng thực tế**:
  - `MetaReasoner.__init__` khởi tạo `self.policy = OptimalStoppingPolicy(lam=self.lam)` rồi gán cứng ngưỡng: `self.policy.tau = [0.671, 0.688]`. Chú thích "Pre-fitted" không đi kèm run artifact được kiểm duyệt chứng minh nguồn gốc hai số này.
  - Trong `_solve_policy_with_ladder` (lines 335-347): `conf_initial` được gán cứng cố định `0.58` và so trực tiếp với `self.policy.tau[0]`. Chuỗi kết quả "Đồng thuận (5/5)" là text mô phỏng được sinh cố định, **không gọi `self.policy.should_escalate` hay chạy lấy mẫu 5 lần thật sự**.
  - **Khoảng trống tích hợp**: Đây là lát cắt heuristic / simulation phục vụ demo giao diện RAT, chưa phải tích hợp runtime đầy đủ của CoT ladder. Giữ nguyên ranh giới, không sửa đổi logic thuật toán trong refactor cấu trúc.

### C. Môi trường & Chiến lược (`reasoning_env.py` & `reasoning_strategies.py`)
- **Harness Headless**:
  - Định nghĩa Gym `ReasoningEnv` đầy đủ (dùng cho các sweep / pilot rollout cần tương tác Gym).
  - Đánh giá đáp án hàng loạt với gold labels, chuẩn hóa format qua `normalize_answer` và `parse_answer_details`.
- **Desktop RAT**:
  - Chỉ tiêu thụ enum `ReasoningAction (A)`, chuỗi `LADDER` và đặc trưng `complexity_features`.
  - Không khởi tạo Gym step loop trong luồng UI để triệt tiêu overhead tương tác.
  - Sử dụng `safe_calculate` và `run_python_sandboxed` cho tính toán an toàn và sandbox Python trong `vgc.py` và `meta_reasoner.py`.
  - Định dạng đầu ra thành `MetaReasoningResult` hiển thị trên `PreviewPanel` và `Omnibar`.

---

## 4. Kiến trúc Gom Package và Cơ chế Compatibility Shims

### Cấu trúc Thư mục Triển khai

```text
multi-step-structured-reasoning/
├── reasoning/                             # Package canonical cho thuật toán reasoning lõi
│   ├── __init__.py                        # Lightweight exports (__all__), không eager-load ML/Qt
│   ├── entry_predictor.py                 # EntryChoice, EntryTrainingData, EntryPredictor
│   ├── optimal_stopping.py                # OptimalStoppingPolicy, CalibrationData, calibrators
│   ├── reasoning_env.py                   # ReasoningAction, ReasoningEnv, complexity_features
│   └── reasoning_strategies.py            # Parsers, safe_calculate, run_python_sandboxed
├── entry_predictor.py                     # Compatibility shim (sys.modules aliased)
├── optimal_stopping.py                    # Compatibility shim (sys.modules aliased)
├── reasoning_env.py                       # Compatibility shim (sys.modules aliased)
├── reasoning_strategies.py                # Compatibility shim (sys.modules aliased)
├── experiments/                           # Headless research adapters
│   └── research_study.py                  # source_hashes() cập nhật 17 files
└── rat/                                   # Desktop application adapters
    ├── engine/meta_reasoner.py
    └── ui/
```

### Cơ chế Shims: Đảm bảo Module Identity và Monkeypatching

Tránh sử dụng `from reasoning.X import *` vì wildcard làm mất private symbols (`_eval_arith`) và tạo ra hai module instance độc lập, khiến monkeypatching hoặc isinstance checks bị phân mảnh.

Mỗi shim tại thư mục gốc sử dụng pattern:
```python
import sys
from reasoning import <module_name> as _canonical

_shim_name = __name__
globals().update({k: getattr(_canonical, k) for k in dir(_canonical)})
sys.modules[_shim_name] = _canonical
```
- `_shim_name = __name__` được lưu trước khi `globals().update` thực thi (tránh việc `__name__` bị ghi đè bởi canonical module name).
- `sys.modules[_shim_name] = _canonical` bảo đảm `sys.modules['module_name'] is sys.modules['reasoning.module_name']`.
- Monkeypatching qua shim name (ví dụ `unittest.mock.patch('optimal_stopping.OptimalStoppingPolicy')`) cập nhật trực tiếp canonical module.

### Cập nhật `source_hashes()`

Trong `experiments/research_study.py:344`, `source_hashes()` được cập nhật để hash cả 5 file trong `reasoning/` lẫn 4 root shims (tổng cộng 17 files). Đã kiểm thử xác minh: thay đổi 1 byte trong mã nguồn canonical `reasoning/reasoning_strategies.py` làm thay đổi trực tiếp fingerprint SHA256 trong manifest nghiên cứu.

---

## 5. Số đo Footprint và Tác động Vật lý

Theo `audit/rat_cot_structural_consolidation_20261017/footprint.json` (snapshot ngày 17/10):
- **Baseline trước hợp nhất**: 4 file gốc, 1,035 dòng (885 non-blank), 43,152 bytes.
- **Canonical `reasoning/`**: 5 files, 1,056 dòng (905 non-blank), 43,870 bytes.
- **Root shims**: 4 files, 52 dòng (40 non-blank), 1,832 bytes.
- **Tác động vật lý thực tế của move ngày 17/10**: Thêm 5 files, tăng thuần $+73$ dòng tổng ($+60$ dòng non-blank), $+2,550$ bytes do việc duy trì song song package canonical và shims tương thích. Không hứa hẹn delta LOC $= 0$ sai sự thật.
- **Phân định với trạng thái checkout ngày 20/10**: Delta thuần hiện tại là $+104$ dòng tổng ($+86$ dòng non-blank), $+4,193$ bytes so với baseline. Khoảng chênh lệch này là do các bản sửa lỗi sau consolidation (gồm logic parser trong `reasoning_strategies.py` và shape handling trong `IsotonicCalibrator.predict`), không thuộc về riêng việc di chuyển package ngày 17/10.
- **Logic thuật toán**: Tại thời điểm snapshot 17/10, 0 dòng thuật toán/model/prompt/policy bị sửa đổi.

---

## 6. Kết quả Kiểm thử Toàn diện

> [!NOTE]
> File `audit/rat_cot_structural_consolidation_20261017/tests.log` là bản tóm tắt thủ công (manual summary transcript) ghi nhận các kết quả pass trong phiên làm việc ngày 17/10. Bằng chứng kiểm thử thô (raw evidence) độc lập với đầy đủ commands, môi trường, exit codes và JUnit XML được lưu trữ tại `audit/rat_cot_structural_consolidation_review_r2_20261020/`.

1. **Research Study & Stopping / Predictor (AGENTS harness)**:
   - *Lệnh*: `.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q`
   - *Raw evidence*: `audit/rat_cot_structural_consolidation_review_r2_20261020/research.txt` & `research.xml`
   - *Kết quả*: **29 passed** (exit code 0).
2. **Core Reasoning Environment & Strategies**:
   - *Lệnh*: `.venv/bin/python -m pytest test_reasoning_env.py test_reasoning_strategies.py tests/test_research_scoring.py -q`
   - *Raw evidence*: `audit/rat_cot_structural_consolidation_review_r2_20261020/core.txt` & `core.xml`
   - *Kết quả*: **53 passed** (exit code 0).
3. **Qwen MLX Mocked Backend**:
   - *Lệnh*: `.venv/bin/python -m pytest test_qwen_mlx_backend_mocked.py -q`
   - *Raw evidence*: `audit/rat_cot_structural_consolidation_review_r2_20261020/backend.txt` & `backend.xml`
   - *Kết quả*: **24 passed, 2 skipped** (exit code 0; 2 skip do yêu cầu native MLX bfloat16 trên Apple Silicon).
4. **RAT Runtime & Work Context**:
   - *Lệnh*: `.venv/bin/python -m pytest tests/test_spider_adapter.py tests/test_assistant_runtime.py tests/test_work_context.py -q`
   - *Raw evidence*: `audit/rat_cot_structural_consolidation_review_r2_20261020/runtime.txt` & `runtime.xml`
   - *Kết quả*: **93 passed** (exit code 0).
5. **Package Contract Probes Bổ sung (2026-10-20)**:
   - *Lệnh*: `.venv/bin/python -m pytest audit/rat_cot_structural_consolidation_review_r2_20261020/test_package_contracts.py -q`
   - *Raw evidence*: `audit/rat_cot_structural_consolidation_review_r2_20261020/package_contracts.txt` & `package_contracts.xml`
   - *Kết quả*: **5 passed** (exit code 0; kiểm chứng canonical import identity, shim monkeypatching, pickle serialization, và lightweight import isolation).
6. **Shim Identity & Isolation**:
   - `assert sys.modules[shim] is sys.modules[canonical]` pass cho cả 4 modules.
   - `import reasoning` không kéo thêm `sklearn`, `gymnasium`, `mlx` hay `PyQt`.
