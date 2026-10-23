# Review bản sửa bridge — 2026-10-23

**R2 đóng. R1 đạt parity khi dùng đúng cấu hình, nhưng chưa đóng binding của
approved profile.** Reviewer chạy độc lập 78 tests: **78 passed in 8.34s**,
không failure/error/skip. Chỉ đọc production, không sửa code của Anti, không
gọi model hoặc dùng candidate/held-out data.

## R1 — P1 còn mở: cấu hình đã duyệt vẫn bị thay khi chạy

Vị trí: `reasoning/runtime.py:164–174` và `reasoning/bundle.py:110–117`.

Phần đúng đã xác nhận: `l2_unit` xử lý vector `[3,4]` thành `[0.6,0.8]`, khớp
collector thật; cùng predictor cho route CoT. Đường legacy không có bundle
approved vẫn có thể dùng raw vectors như trước. Không yêu cầu đổi ngầm mọi
legacy policy thành unit normalization.

Nhưng validator mới chỉ kiểm `embedding_normalization` thuộc enum cho phép,
chưa bind nó với artifact đã review. Constructor lại ưu tiên tham số caller
hơn bundle sau khi bundle đã validate. Probe dùng cùng authored synthetic
predictor nhạy scale, một artifact JSON đầy đủ cost/performance/thresholds,
`embedding_normalization="l2_unit"`, và source/artifact SHA-256 đúng bytes:

| Trường hợp | Artifact | Bundle | Runtime thực dùng | Validation | Route |
| --- | --- | --- | --- | --- | --- |
| Positive control | l2_unit | l2_unit | l2_unit | valid, approved metadata | CoT |
| Caller truyền `embedding_normalization="none"` | l2_unit | l2_unit | none | valid, approved metadata | ReAct |
| Chỉ đổi metadata bundle | l2_unit | none | none | valid, approved metadata | ReAct |
| Bỏ khai báo bundle | l2_unit | None | None/raw | valid, approved metadata | ReAct |

Đây là **fixture mô phỏng approved metadata**, không phải reviewer phê duyệt
một policy thật. Không có model/data approval mới. Các ca chỉ đổi feature
preprocessing, không thay fitted parameters, artifact bytes hoặc câu hỏi.

**Sửa cần thiết trong cùng R1:**

1. Với approved profile, bind normalization với authoritative artifact và
   semantics khi fit. Xung đột/missing declaration phải fail closed, trừ một
   schema/version legacy có semantics rõ đã được review. Không tự coi metadata
   thiếu là raw-approved khi artifact khai unit.
2. Reject caller/policy/predictor hints mâu thuẫn với bundle đã duyệt trước khi
   embed/generate. Dev override có thể tồn tại trong đường explicit development;
   nó không được mang approval của bundle cũ sang cấu hình khác.
3. Thêm regression cho ba ca conflict/missing ở bảng trên, cùng positive unit
   và explicit legacy-raw controls. Các fixtures khai unit cần fit trên đúng
   unit features; không chỉ thêm field metadata cho policy fit trên raw data.

Không cần framework mới, campaign mới hoặc thêm budget. Giữ historical
artifacts nguyên trạng; lưu logs mới khi sửa source. `check_binding.py` tái hiện
bốn ca trên; `binding_probe.json/.txt` giữ kết quả và source hashes.

## R2 — CLOSED trong phạm vi fixture

Backend double đã whitelist embedding và từng answer/confidence/tokens.
Probe xác nhận `gold_in_fixture=false` và `correctness_in_fixture=false`.
Module online hiện có 28 tests, bao gồm input isolation và route parity.
Không suy model-quality evidence từ các fixture này.

## R3 — Nội dung chính đã chỉnh; cần trỏ log đúng phiên bản

Mapping đã phân biệt replay không tạo backend, feature schemas, calibration
mặc định, candidate selector, procedural scoring và nghìn token. Chưa xem đây
là native acceptance hoặc bằng chứng quality/latency.

`current_progress.json` báo parity suite 28 nhưng vẫn trỏ `parity_suite.xml/.txt`
cũ có **22** cases. XML mới `verification_20261023/post_repair_regression.xml`
có **57** cases: online 28 + mandatory research 29. Dẫn file mới/đúng breakdown,
giữ file cũ là historical. Tổng 112 là phép cộng của các suites đã liệt kê,
không phải reviewer đã chạy toàn bộ repo hoặc 112 fresh UI cases trên source
mới. UI55 là Anti-reported trong lượt này, reviewer không chạy lại UI.

Model/revision của campaign vẫn pending. Không dùng tên model ví dụ hoặc cổng
development lịch sử để suy quyền chạy model thật hiện tại. Không cần hỏi lại
người dùng về việc mô tả đúng vai trò auditor hậu kiểm.

## Tái lập và phạm vi

```bash
.venv/bin/python -m pytest tests/test_online_reasoning.py tests/test_policy_bundle.py tests/test_policy_calibration_binding.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
.venv/bin/python audit/rat_cot_quick_unification_20261022/research_bridge/codex_review/repair_check/check_binding.py
```

Raw fresh stdout/JUnit: `regression.txt/.xml`. `binding_probe.json` lưu
fingerprints ba source files, artifact đúng hash, gold-isolation facts và từng
effective route. Probe trả exit 0 khi tái hiện xong; các conflict cases được
chấp nhận trong JSON là findings, không phải ca kiểm approval đã đạt.

Giữ kết quả nhận bàn giao và kiểm này riêng. Không chạy lại script ghi vào
folder kết quả cũ để biến một counterexample lịch sử thành kết quả mới.
