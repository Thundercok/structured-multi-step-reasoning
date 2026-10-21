# Antigravity: phần còn lại sau review Mốc 1

Đọc AGENTS.md và `audit/rat_conversation_core_codex_review_20261013/review.md`.
Source hiện tại đã sửa R1–R4; 7 probes và 168 regression tests đều qua ở snapshot
được review. Giữ các sửa đó, không làm lại theo `initial_handoff_antigravity.md`.
Người review không sửa source app hoặc chạy model mới.

## Cần làm tiếp

1. Sửa các callsite fixture DSA dùng `messages_with_turn_ids()[:-1]`. Pending
   turn mới chưa có trong messages; slicing đang bỏ assistant answer/status
   cuối. Lấy đầy đủ prior messages, hoặc collect trước khi `begin_turn`.
2. Đưa smoke runner tái lập được vào repo, nhận output directory mới. Truyền
   `execution_id=snapshot.execution_id` vào runtime và giữ prior context đúng.
   Tách việc lấy prior turn references khỏi việc lấy messages.
3. Ghi model/config (đặc biệt `plan_tasks`), source hashes, raw model requests
   và responses. Log cũ dùng default `plan_tasks=False`; native đang True.
4. Chạy lại development smoke sau khi sửa harness vào thư mục mới. Giữ log
   timeout/sai cũ; ghi token unknown khi request timeout, không quy đổi thành
   inference cost 0. Cancel trước khi chạy không gọi là thử cancel in-flight.
5. Review nội dung và hành động thực: log cũ có 0 tool calls/0 note events;
   tìm 6 phải dừng ở mid=2, trong khi output cũ sai. Không báo hoàn thành 6 lượt
   chỉ vì model trả text. Không hardcode lời giải DSA để cứu output model.

## Kiểm tra

```bash
python -m pytest audit/rat_conversation_core_codex_review_20261013/contract_probes.py -q
python -m pytest tests/test_work_context.py tests/test_rat_chat_session.py tests/test_assistant_runtime.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_interaction_kernel.py tests/test_interaction_kernel_regressions.py tests/test_rat_verification.py tests/test_vgc_verification.py tests/test_rat_conversation_lifecycle.py -q
```

Giữ audit review, các snapshot và log failure đầu nguyên vẹn. Lưu validation
sau sửa ở thư mục mới. Bàn giao lại diff, test log và raw smoke với cả pass/fail
để người dùng duyệt. Source UI đang có thay đổi nhưng wiring/native chưa được
review trong lượt này; không coi headless tests là nghiệm thu UI. Notes inline
và Chuột chỉ trang trí tiếp tục là phạm vi đã chọn.
