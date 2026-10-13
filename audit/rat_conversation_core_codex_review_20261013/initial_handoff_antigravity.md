# Antigravity: sửa bàn giao Mốc 1 trước khi chuyển UI

Đọc AGENTS.md và `audit/rat_conversation_core_codex_review_20261013/review.md`.
Giữ các thay đổi sẵn có; chưa triển khai Mốc 2 UI. DSA tiếp tục chỉ là ví dụ
kiểm tra core hội thoại chung.

## Các việc cần sửa

1. Bind execution được cấp từ `ConversationHistory.begin_turn` trước khi chạy;
   truyền nó vào `AssistantRuntime.run`. Mọi complete/fail/cancel kiểm đúng
   execution/conversation. Callback cũ sau clear không được ghi vào turn mới;
   completion lặp không thêm context, callback muộn không đổi terminal status.
   Không nới guard để accommodate harness dùng execution khác.
2. Nhánh ambiguous-target của dispatcher cũng kiểm cancel và giữ turn/exec
   trong input_request/artifact/event. Operation đã hủy không tạo pending input.
3. Truyền `should_cancel` từ runtime vào dispatcher; chặn commit kết quả phát
   sinh sau stop trong handler, giữ kết quả đã nhận trước stop. Kiểm cả nhánh
   trả InputRequest và artifact.
4. Historical note projection gửi model khớp snapshot/revision của lượt cũ
   đang hiển thị. Bao phủ ca ghi 20 → sửa cùng lượt thành 30 → lượt sau đổi 40.
5. Sửa fixture và smoke runner: prior messages không có pending turn mới,
   nên bỏ slicing `messages_with_turn_ids()[:-1]`. Collect prior context trước
   begin_turn hoặc truyền đầy đủ messages, và giữ execution ID nhất quán.

## Kiểm tra và bằng chứng

7 probes ở `audit/rat_conversation_core_codex_review_20261013/contract_probes.py`
đang fail trên source đã review. Dùng chúng làm regression; có thể đưa các ca
vào tests phù hợp nhưng giữ log failure cũ và source snapshot audit nguyên vẹn.
Lưu kết quả sửa vào thư mục audit mới, không ghi đè report/probe log của review.

```bash
python -m pytest audit/rat_conversation_core_codex_review_20261013/contract_probes.py -q
python -m pytest tests/test_work_context.py tests/test_rat_chat_session.py tests/test_assistant_runtime.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_interaction_kernel.py tests/test_interaction_kernel_regressions.py tests/test_rat_verification.py tests/test_vgc_verification.py -q
```

Đưa runner tái lập được vào repo, nhận output directory mới, ghi model/config,
source hashes và model inputs/outputs. Khi chạy smoke lại, ghi `plan_tasks` và
profile đang dùng. Giữ timeout/token-unknown đúng sự thật. Cancel ngay trước
inference không được báo là latency hủy in-flight.

Đối chiếu nội dung DSA với reference: tìm 6 trong [2,4,6,8,10] dừng ở mid=2.
Log cũ có 0 tool calls/0 note events; không báo đã ghi/sửa notes hoặc hoàn
thành 6 lượt chỉ vì model trả text. Không hardcode lời giải DSA để cứu output
model. Báo cả lỗi nội dung, tool selection và latency còn lại.

Bàn giao lại core đã sửa cùng diff, kết quả test và raw artifacts để người dùng
duyệt. Tương tác Chuột chỉ trang trí và notes inline là phạm vi mốc UI sau đó;
không trộn các thay đổi UI vào lượt sửa core này.
