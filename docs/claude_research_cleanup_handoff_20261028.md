# Handoff cho Claude — research cleanup, 2026-10-28

## Cập nhật mới nhất: kiểm thử được user cho phép và đã chạy

User đã nói “go” rồi “go on” để chạy focused batch. **62 passed trong 55.47s**: research study, optimal stopping, entry predictor, Qwen staged parity, matched restart và reasoning conversation. Năm matched tests dùng fixture khôi phục đều pass; conversation module collect/chạy thành công trên Qt Quick. Sandbox attempt abort khi import native Qt; retry ngoài sandbox với Qt offscreen pass. Xem `audit/research_repairs_20261028/README.md`, raw logs, JUnit XML và manifest.

Các câu “chưa chạy” bên dưới ghi lại trạng thái ở lượt sửa source trước batch này; cập nhật này là trạng thái mới nhất. Bốn script path workflows chỉ được đọc source, không chạy đầy đủ. Chưa có real-model run/live UI acceptance, không thay Stage 0. Không suy ra quyền chạy suite thêm hoặc push từ batch vừa được cho phép.

## Đọc trước khi làm

- Checkout: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
- Branch hiện tại: `main`. Dùng `main`; không tạo branch mới.
- Đọc `AGENTS.md`, `docs/project_scope.md`; đọc `docs/research_plan.md` và `docs/research_protocol.md` trước khi sửa hành vi nghiên cứu/model.
- RAT và CoT là cùng một hệ. Giữ nguyên Stage 0; không suy diễn tool registration thành Agent/model đã chạy thật.
- Không tự chạy test, smoke, UI acceptance, screenshot hoặc model inference. User đã yêu cầu chỉ kiểm thử khi có yêu cầu rõ. Handoff này không cấp quyền kiểm thử.
- Không push/pull/reset/force trừ khi user yêu cầu trong chính tin nhắn hiện tại. Các lệnh push ở chat trước đã hoàn tất, không phải quyền push tiếp.
- Không chạm `.migration-backups/`, `work/`, `dist/`. Giữ các sửa đổi không liên quan.

## Đã commit và push

`644ec756` — `Consolidate main: remove historical artifacts and migrate reasoning imports`.

Đã push thành công tới `https://github.com/Thundercok/structured-multi-step-reasoning.git`, branch `main` (remote chuyển từ `d4513c55` sang `644ec756`). Đây là remote thực tế đã dùng; hướng dẫn cũ gọi repo canonical là `nesy-docai`, không tự đổi remote dựa trên tên đó.

User đã xem cảnh báo về việc mất audit/evidence và sau đó yêu cầu “scorched earth”, commit/push nhanh. Commit này bao gồm 5.881 file bị xóa đã stage sẵn: audit, artifacts, scratch, prototype và 5 compatibility wrappers ở root. Bản đã commit trước khi xóa vẫn nằm trong Git history. Không tự khôi phục toàn bộ cleanup; user chỉ chấp thuận khôi phục fixture cần cho retained tests trong bước tiếp theo.

Commit cũng giữ các thay đổi source của user:

1. `reasoning/entry_predictor.py`: scaler theo block, PCA mặc định 32/whiten, CV cho L2 của LogisticRegression/Ridge, fit thay thế state thay vì append.
2. `qwen_mlx_backend.py`: flatten logprob shape, full-vocabulary Shannon entropy và coverage/normalization telemetry. Công thức confidence không chủ đích thay đổi.
3. Import chuyển sang `reasoning.*`, cập nhật nhiều source-fingerprint paths.
4. Handoff Mini Look và các tài liệu liên quan có mặt trong commit; không coi commit là bằng chứng live acceptance.

## Đã làm sau push — chưa commit

Chỉ các thay đổi dưới đây thuộc lượt repair của chat này:

- `scripts/agreement.py`: hash current source tại `reasoning/reasoning_strategies.py`.
- `scripts/review_tuning_sweep.py`: current-source fingerprint dùng canonical path. Cố ý GIỮ `reasoning_strategies.py` trong `legacy_implementation()`: hàm đó đọc file tại pinned Git commit `76d311b`, nên root path là đúng cho lịch sử.
- `scripts/mutation_check.py`: mutant đọc implementation trong `reasoning/reasoning_strategies.py`.
- `scripts/generate_real_mutants.py`: đọc canonical implementation và tạo patch headers cho canonical path.
- Khôi phục 10 file nguyên byte từ `644ec756^` vào `audit/cot_restart_pilot_qwen35_20261009/`: `RESULT_FOR_CODEX.md`, `base_traces.json`, `calls.jsonl`, `dataset.json`, `manifest.json`, `plan.json`, `report.md`, `restart_records.json`, `smoke_telemetry.json`, `summary.json`. Không khôi phục `.writer.lock` cũ.

Các fixture được khôi phục vì `tests/test_cot_restart_matched.py` dùng historical dataset/base traces và `verify_historical_run()` kiểm tra các file mà manifest dẫn chiếu. Không sửa nội dung hoặc hash trong manifest lịch sử. Files vừa khôi phục đang untracked; phải add explicit paths nếu user yêu cầu commit.

Không chạy tests/smoke sau repair. Chưa xác nhận năm lỗi fixture đã hết.

## Sửa source tiếp theo — user chấp thuận sau handoff, chưa chạy kiểm chứng

1. **PCA fold sizing**: source hiện tạo actual CV splits riêng cho classifier/cost head, giới hạn PCA theo training fold nhỏ nhất (và trừ một chiều do centering). Không whitening với training set chỉ có một hàng; reject input rỗng. Regression tests cho minority=2, cv_folds>N và single-row đã viết trong `test_entry_predictor.py`, chưa chạy. Chưa claim fit thành công trong runtime.
2. **Strict telemetry**: `QwenMLXBackend.__init__` nhận `strict_telemetry=False`. Các production MLX constructor trong `experiments/research_study.py`, `experiments/research_pilot.py`, `experiments/pilot_real_model.py`, `pipeline.py`, `scripts/run_smoke_b_lite.py` và backend CLI bật `True`. Default vẫn giữ tương thích cho injected doubles; trace ghi flag. Strict check nằm trong try/finally để generation trace ghi `failed` khi telemetry bị từ chối. Regression tests viết tại `tests/test_qwen_staged_parity.py`, chưa chạy, chưa gọi model thật.
3. **Missing test-module import**: `tests/test_reasoning_conversation.py` chuyển fixture từ widget `tests/test_flow_interaction.py` đã retired sang existing Qt Quick fixture `tests/test_quick_unified_flow.py`. Vẫn giữ multi-turn/history, execution identity, synthetic provenance, draft/navigation và no-fallback assertions trên `QuickPDFController`/QML. Không khôi phục retired widget implementation. Chưa chạy collection hoặc UI tests; chưa xác nhận lỗi collection đã hết.

## Các vấn đề còn lại

4. **Frozen source hashes**: manifest cũ hash root `reasoning_strategies.py`; kiểm chứng bằng source ở Git revision gốc, không thay hash/path lịch sử bằng file mới để ép pass. `direct_cot_analysis.py` cần xử lý theo provenance này nếu được giao tiếp.
5. Còn branch lịch sử chưa hợp nhất (bao gồm `rat-ui` có ba commit không nằm trên main). Chat này chỉ chuyển working checkout về main và commit hiện trạng; không merge/delete branch cũ. Không claim “mọi branch đã được hợp nhất”.

## Kết quả kiểm chứng: phân biệt nguồn

User chuyển handoff rằng họ đã chạy:

```bash
python -m experiments.research_study --backend smoke --seed 42 --lam 0.02 --output runs/smoke-42
```

Và báo smoke pass, 158+ test pass, 5 failures do thiếu historical fixtures, 1 collection error. Đây là thông tin user cung cấp, không phải lệnh chat này đã chạy. Không bảo đảm suite hiện tại vì có nhiều thay đổi đồng thời sau đó.

User cũng báo synthetic d=4096,N=120 có held-out accuracy khoảng 0.51 → 0.60–0.70 và confidence parity 12 chữ số. Không có artifact review của các claim đó trong chat này; không trình bày thành real-model quality hay kết quả confirmatory. Không tự chạy lại.

## Working tree đang có công việc Mini từ nguồn khác

Tại lúc handoff, nhiều sửa đổi Mini/UI/docs/tests và assets mới xuất hiện đồng thời. Chúng không thuộc lượt repair bốn scripts + historical fixtures trên. Chạy `git status --short` và đọc diff hiện tại trước khi stage; không dùng `git add -A` hay `commit -a`.

Các handoff Mini cần đọc nếu làm phần đó: `docs/rat_mini_look_handoff_20261028.md`, `docs/rat_mini_speech_handoff_20261028.md`, `docs/rat_mini_look_clipboard_20261028.md` (hai file sau đang untracked lúc quan sát). Không suy ra chúng đã được kiểm chứng chỉ vì tồn tại.

Bảy backup files vẫn untracked: `experiments/research_study.py.bak`, `experiments/research_study.py.bak2`, `pipeline.py.bak`, `qwen_mlx_backend.py.bak`, `qwen_mlx_backend.py.pre-task2`, `research_scoring.py.bak`, `test_qwen_mlx_backend_mocked.py.bak`. Không tự add hoặc xóa.

## Bước tiếp theo đề xuất

Đọc trạng thái hiện tại rồi báo user phần repair còn local. Source repairs đã hoàn tất nhưng chưa chạy kiểm chứng. Chỉ chạy kiểm thử khi user cấp quyền rõ; lúc được phép, chọn một batch gồm `tests/test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`, `tests/test_qwen_staged_parity.py`, `tests/test_cot_restart_matched.py`, `tests/test_reasoning_conversation.py` và lưu kết quả thật. Chỉ retry phần fail/changed cần thiết. Không tự push hoặc mở rộng sang Mini UI dựa trên handoff này.
