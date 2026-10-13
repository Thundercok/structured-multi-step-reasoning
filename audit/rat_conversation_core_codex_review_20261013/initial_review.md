# Review bàn giao core hội thoại RAT — 2026-10-13

**Verdict: Request changes. Chưa đề xuất duyệt Mốc 1 hoặc chuyển Mốc 2 UI.**

Core đã có các record ownership, history và provenance cần thiết. Tuy nhiên,
kiểm tra độc lập tái hiện lỗi reset/callback, hủy và projection lịch sử. Log
model thật cũng chưa hoàn thành hành vi trong ví dụ DSA. Review này chỉ thêm
audit/probes, không sửa source app, không chạy model mới hoặc kiểm tra native.

## Bằng chứng kiểm tra phần mềm

- Regression mở rộng: **161 passed in 6.96s**. Bao gồm suite 94 tests được báo
  trong bàn giao, interaction kernel, verification và VGC.
- 7 probes độc lập cho các ca thiếu trong regression: **7 failed in 0.26s**.
  Các failure dưới đây là lỗi hợp đồng được tái hiện, không phải timeout model.
- Source được chụp vào `reviewed_source/` trước lần kiểm tra cuối và hash trong
  `source_sha256.json`; source không đổi trong lần kiểm tra cuối.

Log: `regressions.txt`, `contract_probes.txt`. Probes ở `contract_probes.py`.

```bash
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest audit/rat_conversation_core_codex_review_20261013/contract_probes.py -q
```

## Lỗi cần sửa

### R1 — P1: callback có thể thay execution hoặc thay trạng thái đã kết thúc

Vị trí: [chat_session.py:227](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/chat_session.py:227),
[chat_session.py:243](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/chat_session.py:243),
[chat_session.py:272](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/chat_session.py:272).

`complete_turn` chỉ kiểm execution mismatch khi status khác `in_progress`, rồi
cho callback đổi `snap.execution_id`. Sau `clear()`, ID `turn-1` được dùng lại;
completion với execution cũ được nhận vào request mới. Completion lặp cũng
thêm cặp user/assistant lần nữa vào context. `fail_turn` có thể đổi lượt đã
hủy từ `cancelled` thành `failed` bằng callback muộn.

Ba probes đầu tái hiện các ca này. Cần cấp/bind execution trước khi chạy và
kiểm identity trước mọi commit; terminal transitions phải idempotent hoặc từ
chối hợp lệ. Cập nhật harness để truyền execution do `begin_turn` đã cấp vào
runtime, thay vì cho completion tự nhận một execution khác.

### R2 — P1: nhánh chọn kết quả bỏ qua hủy và ownership

Vị trí: [dispatcher.py:182](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/dispatcher.py:182).

Khi có hai artifact cùng loại và chưa chỉ định đích, `execute_operation` gọi
`_waiting` trực tiếp, không qua guard trong `_run` và không truyền turn/exec.
Execution đã hủy vẫn tạo `input_request`, đổi pending state và trả `needs_input`.
Trong execution hợp lệ, artifact/event hỏi lựa chọn vẫn mất owner identity.

Hai probes về ambiguity tái hiện lỗi. Preflight và context phải áp dụng cho
cả nhánh clarification/waiting, không chỉ nhánh chạy handler.

### R3 — P1: stop trong lúc handler chạy vẫn commit artifact

Vị trí: [assistant_runtime.py:441](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/assistant_runtime.py:441),
[assistant_runtime.py:931](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/assistant_runtime.py:931).

Dispatcher có guard đọc `context['should_cancel']` trước/sau handler, nhưng
`execute_tool` không đưa callback đó vào context. Trong probe, handler nhận
stop rồi trả kết quả; runtime trả `cancelled` ở vòng tiếp theo, nhưng artifact
`late result` đã vào store. Cần truyền guard và kiểm tra trước commit; giữ các
kết quả đã commit trước khi dừng. Probe chỉ kiểm commit trong core, không hứa
hoàn tác mọi hiệu ứng bên ngoài mà handler đã thực hiện.

### R4 — P2: lịch sử gửi model khác snapshot hiển thị của lượt cũ

Vị trí: [work_notes.py:774](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/work_notes.py:774).

`historical_context` duyệt revision từ cũ tới mới và giữ bản đầu mỗi owner.
Khi lượt 1 ghi 20, sửa tại chỗ thành 30, rồi lượt 2 đổi thành 40,
`notes_for_turn('turn-1')` là revision 2/text 30 nhưng historical context đưa
revision 1/text 20 cho model. Probe cuối tái hiện sự lệch này. Projection mặc
định phải khớp revision hiển thị của lượt cũ; nếu cung cấp nhiều revision thì
phải có reference rõ và đầy đủ, không âm thầm chỉ chọn bản đầu.

### R5 — P1 trong harness: bỏ mất phản hồi cuối của ngữ cảnh

Vị trí: [test_work_context.py:255](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/tests/test_work_context.py:255)
và bản runner được giữ ở `original_smoke_runner.py.txt`.

Fixture 6 lượt và script smoke dùng `history.messages_with_turn_ids()[:-1]`.
`begin_turn` chưa thêm request đang chạy vào context messages, nên slicing này
xóa assistant answer/status của lượt trước, không phải message của lượt mới.
Sau timeout, notice thất bại ở history bị bỏ; các turn references vẫn có status
failed, nhưng đường conversation chính thiếu message cần giữ.

`harness_context_probe.json` ghi hai đầu vào để đối chiếu. Lấy toàn bộ prior
messages; có thể lấy messages/references trước khi `begin_turn` để tránh nhầm.
Tách rõ logic loại pending turn reference với logic lấy conversation messages.

## Review smoke model đã có

Nguồn giữ nguyên: `audit/rat_conversation_core_20261013/dsa_core_smoke.json`.
Phân tích offline ở `smoke_review.json`; **0 lời gọi model mới**.

| Lượt | Quan sát |
| --- | --- |
| 1 | Có text giải thích; không có tool/event note. |
| 2 | Timeout khoảng 90.16s; không có kết quả hoặc note được ghi. |
| 3 | Lặp claim đã tìm được 8, không trả lời lý do `mid + 1`; thao tác tìm/ghi chưa có evidence. |
| 4 | Sai thuật toán: với mảng đã cho, mid=2, a[2]=6 bằng target nên phải dừng. Model lại hướng tìm phần lớn hơn 6. |
| 5 | Không quay lại được lý do `mid + 1`; lặp lỗi phần lớn hơn 6. |
| 6 | Callback cancel luôn true trước khi inference/tool bắt đầu. 0.15ms là early return, không phải đo hủy in-flight. |

Tổng latency các attempt khoảng 311.70s, 0 tool calls, 0 note events,
`final_active_notes=[]`. Nhận ra mảng/target trong prose không chứng minh đã
cập nhật note hoặc tham chiếu đúng kết quả. Nhận xét “nông/lặp” trong bàn giao
cần bổ sung lỗi thuật toán cụ thể, không đánh đồng `error=None` với câu trả lời đúng.

Token counters 0 ở timeout là số không nhận được từ request thất bại, không
chứng minh inference tiêu thụ 0 token. Runner không ghi đủ config/source hash
và model request để tái lập đầy đủ. Nó dùng `plan_tasks=False` mặc định, trong
khi native RAT bật `plan_tasks=True`; không dùng latency đó làm số đo native.

## Những phần có thể giữ

Core record độc lập Qt, version/event trả deep copies, nguồn quote ngắn hoặc
mơ hồ được kiểm tra và lịch sử user request thất bại được lưu riêng với successful
answers. Các phần này là nền tảng để sửa tiếp. Fixture được ghi nhãn đúng là
kiểm tra phần mềm, không phải kết quả AI/NCKH; Stage 0 không đổi.

## Bàn giao sửa

Checklist cụ thể ở
[handoff_antigravity.md](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_conversation_core_codex_review_20261013/handoff_antigravity.md).
Sửa core/harness trước, chạy lại các probes/regressions, rồi review transcript
model với context đúng trong một thư mục mới. Giữ log lỗi cũ. Chưa chuyển mốc UI
cho đến khi người dùng duyệt mốc core đã sửa.
