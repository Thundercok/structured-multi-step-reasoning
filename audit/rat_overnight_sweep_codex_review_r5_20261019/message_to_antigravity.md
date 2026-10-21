# Repair follow-up sau independent review r5

Đọc `audit/rat_overnight_sweep_codex_review_r5_20261019/review.md` và các raw
artifacts trước khi sửa. Review độc lập xác nhận 309/309 pass, gồm toàn bộ 7
probe r4, nhưng 10 probe mới có 4 fail / 6 pass. D1/D2 mới đóng được các ca cũ;
còn ba finding P2 trong hai file vừa sửa:

1. **E1 / parser**: `Answer: 2 + 2 = 4; 1 / 4 = 1/4` và phiên bản bắt đầu bằng
   `Therefore` đều thành `4`. `_clean_cand` lấy scalar trung gian trước khi kiểm
   RHS cuối. Ca marker là regression mới, có snapshot before/after. Chọn kết
   luận cuối rồi giữ toàn bộ giá trị/phân thức; không quay lại scalar trước.
2. **E2 / provenance legacy**: classifier gọi record fake r3 là real vì có
   timing và prompt_tokens=2031. Fake backend cũng có các metrics này. Phiên
   `legacy_fake_history_halt` chứng minh end-to-end: guard không dispatch mà
   summary ghi một historical real-model record. Dùng nguồn đã xác minh hoặc
   unknown; không coi timing/token count là chứng cứ inference. Unknown vẫn
   tiêu thụ budget attempts.
3. **E3 / current-run count**: copy phiên fake mới (đã có backend/session tag),
   chạy lại cap 1 thì guard halt 0 requests nhưng summary vẫn fake_calls=1 và
   `offline_fake_backend_completed_1_calls`. Đếm current run bằng current run;
   tách lịch sử thành trường riêng và không mượn warm metrics phiên trước.

Đây là phần hoàn thiện các hợp đồng D1/D2 đã yêu cầu, không thêm UI feature hay
đổi nghiên cứu. Không sửa typed scoring, gold datasets hoặc frozen evaluation
để khớp output sai. Không tự tăng budget; 12 real calls đã dùng xong. Giữ ledger
gốc và các review artifacts nguyên vẹn; sửa source trên main, giữ unrelated
changes, không commit/branch/push/pull/reset.

Đã có các ca input, command, log và ledger trong review r5. Khi sửa, tạo folder
repair mới, chạy fresh fake cap 1, rồi tạo bản copy ledger đó để kiểm exhausted
fake history; thêm replay riêng trên bản copy real history và legacy fake history.
Không chạy runner vào folder review cũ.

Chạy lại probe:

```bash
QT_QPA_PLATFORM=offscreen \
RAT_REVIEW_R5_OUTPUT_DIR=/absolute/path/to/new_repair_output \
.venv/bin/python -m pytest \
  audit/rat_overnight_sweep_codex_review_r5_20261019/test_provenance_and_conclusion.py -q
```

`new_repair_output` phải có `fake_session/`, `fake_history_halt/` và raw log
`fake_history_halt.txt`. Classifier probe cô lập đúng function hiện tại bằng
AST để không load model; nếu thay kiến trúc classifier, điều chỉnh cách gọi
mechanically hoặc thay bằng kiểm output end-to-end tương đương, giữ assertions
về provenance. Explicit backend controls vẫn phải pass.

Giữ 309 tests cũ, 70 parser/backend/scoring cases và 29 NCKH bắt buộc. 29 là
subset trong 309. Nếu môi trường skip 2 native bfloat16 cases, báo đúng pass/skip.
Đừng ghi đè ảnh/geometry của review r4 khi chạy lại hosted UI test; dùng cơ chế
redirect output như `run_consolidated.py`. Không gọi model thật cho các tests này.

Handoff mới cần snapshot source trước/sau, diff, command + env, raw logs/JUnit,
ledger byte comparisons và scope native chưa đo. Không khẳng định full active
suite/model quality/native UX đã đạt từ bộ software tests. Giữ Stage 0 và các
native acceptance cases chưa chạy đúng trạng thái; không cần xin thêm budget
để sửa và kiểm ba lỗi offline này.
