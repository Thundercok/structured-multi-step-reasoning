Đọc review mới tại `audit/rat_overnight_sweep_codex_review_r4_20261019/review.md`.
Đã xác minh độc lập 302/302 bằng fake session mới. Startup, answer navigation,
unique budget counting và same-directory copy labels đã pass; giữ các fixes đó.
Không làm lại full sweep hoặc native model smoke để tăng số tests.

Còn hai phần của C1/C2 cần sửa software/offline:

1. **D1 — fallback fraction value:** `Therefore x = 3/4` đang thành `4`,
   `x = 3.25/4` thành `3`. Marker đã sửa nhưng fallback vẫn gọi
   extract_conclusion_number/extract_number theo đường riêng. Dùng cùng quy tắc
   bảo toàn conclusion ở cả hai đường; không lấy prefix/tử/mẫu từ rational hoặc
   expression. Kiểm có/không Answer marker, conclusion cues, signed/decimal
   numerators, units và integer controls. Giữ placeholder fix. Không nới typed
   research scoring, gold labels hay frozen evidence.
2. **D2 — historical classification:** copy ledger thật 12 calls và chạy
   --fake-backend --max-budget 12 chỉ để guard halt vẫn phát ra fake_calls=12.
   Không có request mới nào. Không được gán type backend của record lịch sử bằng
   args.fake_backend của process hiện tại. Lưu/request-link backend kind, model,
   session ID; tách current-run counts với historical totals. Legacy records
   cần provenance xác nhận hoặc unknown/reject incompatible mode. Guard halt
   phải ghi 0 new calls và giữ historical evidence; không trộn RSS/load mới
   với old generation samples, không gọi old real samples là warm fake samples.
   Có thể fail-closed khi ledger/mode không tương thích, kèm summary rõ lý do.

Test mới: `audit/rat_overnight_sweep_codex_review_r4_20261019/test_final_edges.py`
có 7 cases, hiện 3 fail / 4 pass. Giữ assertions/value semantics, không sửa data
captured của reviewer. Tạo output mới cho cả hai nhánh:
- `fake_session/`: --fake-backend --max-budget 1, một fake request.
- `locked_ledger_replay/`: bản copy byte-identical của ledger 12 real calls,
  --fake-backend --max-budget 12, phải không dispatch thêm request, summary
  không được ghi 12 fake calls. Nếu reject mismatch, báo rõ status thay vì
  claim hoàn tất fake requests.

Khi chạy tests trên evidence mới, đặt `RAT_REVIEW_R4_OUTPUT_DIR` trỏ tới thư mục
cha chứa hai folder đó; không ghi đè review r4. Để chạy old 13 artifact probes,
đặt RAT_REVIEW_FAKE_OUTPUT_DIR vào fresh one-request fake_session như các vòng
trước. Giữ old fail logs và real ledger nguyên byte.

Tiếp tục chỉ bằng fake backend/text fixtures: **0 real model generation mới**,
không load model thật để kiểm guard. Ngân sách 12 calls cũ đã dùng hết. Giữ main,
dirty work/recovery/audit, không push/pull/reset/force/branch.

Chạy affected parser/backend/scoring tests và mandatory research checks theo
AGENTS khi đổi parser. Không cộng skip thành pass; ghi interpreter/env. Một
consolidated regression cuối khi source đã ổn, không cần full 132-file rerun.
Native GUI scope vẫn not-run/blocked; không dùng 302 software passes để thay
cho native hoặc model-quality acceptance.

Báo cáo source trước/sau, delta, logs/XML, current-vs-history counters và từng
finding; chỉ đóng hai finding khi cả fallback và historical-mode replay đúng.
