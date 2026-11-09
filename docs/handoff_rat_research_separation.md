# HANDOFF: Tách RAT và Research Thành 2 Repository Độc Lập

> **Thời điểm**: 2026-11-09  
> **Mục tiêu**: Tách hoàn toàn RAT ra khỏi repository Research (`structured-multi-step-reasoning`), đưa RAT về vĩnh viễn tại repository `offline-tool-routing-agent` (sẽ đổi tên mới), đồng thời tái định vị RAT thành **Efficient Agent & Model Evaluation/Testing Harness** lấy cảm hứng từ bài báo **SoL-Pi (NVlabs / MIT)**.

---

## 1. Bối cảnh & Tầm nhìn cốt lõi

### 1.1. Hiện trạng vấn đề
- Repo hiện tại (`multi-step-structured-reasoning` / remote `structured-multi-step-reasoning`) đang bị **"nhiễm tạp"**:
  - Chứa cả code nghiên cứu NCKH (fine-tuning Qwen3-8B, can thiệp counterfactual, GSM8K trace verification).
  - Vừa chứa toàn bộ mã nguồn của RAT (resident desktop app, UI Persona 5, semantic search, local translation, PDF desk, astrology, timetable, v.v.).
  - Khiến repo nặng nề, bộ test bị loãng (99 test RAT lấn át 21 test nghiên cứu), mất tập trung vào mục tiêu bảo vệ NCKH.
- User đã chỉ định:
  - Repo https://github.com/Thundercok/offline-tool-routing-agent sẽ **vĩnh viễn đựng RAT**.
  - Muốn một **tên mới hay hơn, ngầu hơn** và **format lại toàn bộ repo** cho chuẩn chỉ.
  - RAT **không phải là simple agent/toy chatbot**, mà giải quyết bài toán lớn: **Evaluation / Testing Harness** cho mô hình và agent cục bộ.

### 1.2. Cảm hứng từ bài báo SoL-Pi (`NVlabs / NTU / MIT` - arXiv:2609.20519)
- **Tên bài báo**: *“SoL-Pi: Recursively Scaling Auto-Research Loops for Efficient Agent Harness”*.
- **Tử huyệt của Agent hiện nay**: Agent chạy chậm, ngốn token, tràn RAM/context không phải vì model yếu, mà vì **Harness (bộ khung điều phối) quá cồng kềnh**: nhét log thô, replay tool output khổng lồ, gọi tool vụn vặt và lặp lại ngữ cảnh vô ích.
- **4 cơ chế trụ cột của SoL-Pi cần đưa vào RAT Harness**:
  1. **Action Fusion**: Gộp các bước tuần tự (ví dụ: edit + validate, search + inspect) thành một lệnh để giảm số turn rỗng.
  2. **ObservationPack**: Đóng gói output dài (kết quả terminal, text PDF, dump file) thành reference handle gọn nhẹ thay vì nhồi raw text vào context.
  3. **Evidence-Preserving Reducer**: Nén log chẩn đoán nhưng giữ chặt bằng chứng suy luận/phản biện để phục vụ đánh giá tính trung thực (faithfulness).
  4. **Context Compaction**: Dọn dẹp context thông minh khi chạy tác vụ dài trên máy cá nhân (Apple Silicon / MLX / local SLMs).

---

## 2. Kết quả Rà soát Codebase (Audit)

### 2.1. Phân loại trong Repo hiện tại (`multi-step-structured-reasoning`)

| Thành phần | Thuộc về | Hành động | Chi tiết |
| :--- | :--- | :--- | :--- |
| `structured_llm/` | **Research** | **GIỮ LẠI** | Core nghiên cứu: format trace, GSM8K, LoRA training, counterfactual data, interventions |
| `adapters/` | **Research** | **GIỮ LẠI** | Trọng số LoRA checkpoints |
| `audit/` | **Research** | **GIỮ LẠI** | Báo cáo thực nghiệm, error anatomy, scaleup audit |
| `data/` | **Research** | **GIỮ LẠI** | Dataset train/val/dev/test GSM8K và counterfactual |
| `docs/` (trừ handoff RAT) | **Research** | **GIỮ LẠI** | Đề cương NCKH (`research_plan.md`, `nckh_defense_guide.md`, v.v.) |
| `scripts/run_scaleup_eval_300.py` | **Research** | **GIỮ LẠI** | Script chạy scale-up eval 300 mẫu |
| `tools/pipeline_status.py`, `visualize_dag.py` | **Research** | **GIỮ LẠI** | Công cụ theo dõi pipeline NCKH |
| `requirements.txt` | **Research** | **GIỮ LẠI** | Phụ thuộc thuần ML/Torch/Transformers/MLX |
| **21 test research** | **Research** | **GIỮ LẠI** | `test_structured_trace.py`, test prompt profiles, trace parser |
| | | | |
| `rat/` (toàn bộ) | **RAT** | **CHUYỂN SANG REPO 2** | UI, engine, os, crawler, astrology, timetable, cli.py, main.py, config.py |
| `document_intake/` | **RAT** | **CHUYỂN SANG REPO 2** | Module đọc PDF, OCR Tesseract, Apple Vision |
| `root main.py` | **RAT** | **CHUYỂN SANG REPO 2** | File entry point đang gọi `from rat.main import main` |
| `requirements-rat.txt` | **RAT** | **CHUYỂN SANG REPO 2** | PyQt6, ctranslate2, fastembed, pyobjc, pyswisseph... |
| `.rat/` | **RAT** | **CHUYỂN SANG REPO 2** | Folder ẩn chứa lock state và cache |
| `tools/` (10 files RAT) | **RAT** | **CHUYỂN SANG REPO 2** | `apple_translate.swift`, `build_rat_mini_hotkey.sh`, `desk_latency_baseline.json`, `measure_desk_latency.py`, `measure_language_retry.py`, `measure_search_quality.py`, `prepare_rat_*.py`, `rat_hotkey.c`, lock files |
| `work/` (ảnh UI cũ, audit UI) | **RAT** | **CHUYỂN SANG REPO 2** | Ảnh crop UI Persona 5, audit giao diện |
| `overnight_summary.log` | **RAT** | **CHUYỂN SANG REPO 2** | Log benchmark latency RAT cũ |
| **99 test files RAT** | **RAT** | **CHUYỂN SANG REPO 2** | Toàn bộ `test_rat*.py`, `test_quick*.py`, `test_desk*.py`, `test_progressive_search.py`, v.v. |

### 2.2. Hiện trạng repo đích (`offline-tool-routing-agent`)
- Đường dẫn local: `/Users/thundercock2/Documents/Github/offline-tool-routing-agent`
- Remote: `https://github.com/Thundercok/offline-tool-routing-agent.git`
- Đang chứa bản đổi tên dở dang từ đầu tháng 11 (`offline_agent/`, 17/52 test gãy). Bản này sẽ được dọn dẹp và thay thế bằng toàn bộ source RAT hoàn chỉnh từ main repo.

---

## 3. Các phương án đặt tên Repo (Repo Naming)

User muốn một cái tên hay hơn `offline-tool-routing-agent`, phản ánh đúng linh hồn vừa Persona 5 vừa là bộ khung đo đạc / thử lửa theo tinh thần SoL-Pi:

1. **Nhóm Thử lửa / Đấu trường (Chiến & Gắt)**:
   - **`rat-crucible`**: "Lò luyện kim" — nơi đưa model và agent vào nung thử để kiểm tra độ bền, tính trung thực và khả năng phục hồi lỗi.
   - **`rat-gauntlet`**: "Bãi chướng ngại vật" — chuỗi bài test đánh giá agent khi gặp môi trường ngặt nghèo về token/RAM.
2. **Nhóm Cơ khí / Đo đạc công suất**:
   - **`rat-dyno`**: Lấy cảm hứng từ bàn Dyno đo công suất động cơ xe — đo TTFT, tokens/s, RAM peak và context efficiency cục bộ trên macOS.
3. **Nhóm Persona 5 / Phong cách**:
   - **`velvet-harness`** hoặc **`velvet-room`**: Lấy từ Velvet Room trong Persona — nơi giam giữ, khảo cung, kiểm thử và tôi luyện Persona/Model.
4. **Nhóm Kỹ thuật chuẩn mực**:
   - **`rat-harness`**: Rõ ràng, trực diện, giữ vững thương hiệu RAT.

*(Ở chat mới, user và agent chỉ cần chốt 1 tên cuối cùng để tiến hành đổi tên remote GitHub).*

---

## 4. Kế hoạch triển khai từng bước (Action Roadmap)

### Giai đoạn 1: Chuẩn bị & Đồng bộ sang Repo RAT (`offline-tool-routing-agent` $\to$ Tên mới)
1. **Kiểm tra trạng thái git**:
   - Xác nhận cả 2 repo local đều clean trước khi sao chép.
2. **Chuyển các module RAT sang repo mới**:
   - Đưa `rat/`, `document_intake/`, `requirements-rat.txt` (đổi thành `requirements.txt`), 10 files tools đo đạc, và 99 file tests sang repo RAT.
   - Tổ chức lại cấu trúc thư mục chuẩn:
     ```text
     rat/
     ├── harness/             # Bộ điều phối & đo đạc SoL-Pi (ActionFusion, ObservationPack, Compaction)
     ├── engine/              # Engine tìm kiếm, routing, translation, local reader
     ├── kernel/              # Contracts, dispatcher, capabilities
     ├── os/                  # macOS hotkey, resident app, permissions
     ├── ui/                  # Persona 5 desk, Qt Quick surfaces
     tests/                   # 99 tests RAT đã được phân loại
     tools/                   # Scripts benchmark latency, model preparation
     requirements.txt
     README.md                # Format chuyên nghiệp, aesthetic Persona + Architecture SoL-Pi
     ```
3. **Chạy kiểm thử trên repo RAT**:
   - Thiết lập virtualenv, chạy `pytest tests/test_rat*.py` để bảo đảm không bị gãy import.

### Giai đoạn 2: Dọn dẹp triệt để Repo Research (`structured-multi-step-reasoning`)
1. **Xóa sạch các file RAT đã chuyển**:
   - Xóa `rat/`, `document_intake/`, `.rat/`, `requirements-rat.txt`, 10 file RAT trong `tools/`, các ảnh trong `work/`.
   - Xóa 99 file test RAT trong `tests/`, chỉ giữ lại 21 test thuộc về `structured_llm`.
2. **Cập nhật Entrypoint & Quy chuẩn**:
   - Dọn `main.py` ở root (hoặc đổi thành research cli).
   - Cập nhật `AGENTS.md` và `README.md` của Research repo: khẳng định repo này 100% là NCKH (Qwen3-8B fine-tuning & intervention study), độc lập hoàn toàn với RAT.
3. **Kiểm tra độ toàn vẹn của Research**:
   - Chạy `.venv/bin/python -m pytest tests/` $\to$ Đảm bảo 21 test research PASS 100% trong $<10$ giây.

### Giai đoạn 3: Tích hợp Triết lý SoL-Pi vào RAT Harness
1. Xây dựng module `rat.harness` triển khai 4 cơ chế:
   - `ActionFusion`: Giảm roundtrip khi agent thao tác file/terminal.
   - `ObservationPack`: Thu nhỏ đầu ra tìm kiếm ngữ nghĩa và đọc file thành object handle.
   - `EvidenceReducer`: Nén vết suy luận mà không làm mất căn cứ tính toán.
   - `LocalCompactor`: Giữ bộ nhớ context vừa vặn trong giới hạn bộ nhớ thống nhất (Unified Memory) của Apple Silicon.
2. Viết tài liệu `README.md` mới cho repo RAT với sơ đồ kiến trúc và bảng benchmark.

---

## 5. Danh sách 21 Test Research cần giữ lại tại Repo Research

1. `tests/test_audit_manifest.py`
2. `tests/test_benchmark_dataset.py`
3. `tests/test_canary_split.py`
4. `tests/test_counterfactual_generator.py`
5. `tests/test_dag_pipeline.py`
6. `tests/test_entry_eval_manifest.py`
7. `tests/test_eval_run_manifest.py`
8. `tests/test_gsm8k_direct_prompt.py`
9. `tests/test_gsm8k_format.py`
10. `tests/test_gsm8k_gold_leakage.py`
11. `tests/test_intervention_engine.py`
12. `tests/test_intervention_leakage.py`
13. `tests/test_intervention_manifest.py`
14. `tests/test_intervention_types.py`
15. `tests/test_legacy_trace_isolation.py`
16. `tests/test_lora_smoke_dataset.py`
17. `tests/test_no_cross_import.py` (cực kỳ quan trọng: đảm bảo research không import rat)
18. `tests/test_research_scoring.py`
19. `tests/test_scaleup_eval_manifest.py`
20. `tests/test_structured_trace.py`
21. `tests/test_unverifiable_fallback.py`

*(Tất cả 99 test còn lại trong `tests/` đều chuyển sang repo RAT).*

---

## 6. Lời dặn cho Agent ở phiên chat tiếp theo

Khi mở chat mới:
1. Hỏi người dùng để **chốt 1 tên duy nhất cho repo RAT** (ví dụ: `rat-crucible`, `rat-gauntlet`, `rat-dyno`, hay `velvet-harness`).
2. Thực hiện **Giai đoạn 1**: Sao chép toàn bộ code RAT + 99 test sang `/Users/thundercock2/Documents/Github/offline-tool-routing-agent`.
3. Thực hiện **Giai đoạn 2**: Dọn sạch RAT khỏi `multi-step-structured-reasoning`, chạy `pytest` xác nhận repo research sạch bóng và test pass 100%.
4. Tuân thủ nghiêm ngặt **Charter**: Giao tiếp ngắn gọn (bite-sized), không tường văn bản, giữ user trong vòng tư duy ở từng bước quyết định.
