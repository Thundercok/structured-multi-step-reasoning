# Review core hội thoại RAT — kết quả cuối lượt 2026-10-13

**Verdict: lifecycle đã sửa các lỗi tái hiện; cần sửa harness và cập nhật bằng
chứng hội thoại trước khi chốt bàn giao hoặc coi luồng model/native đã đạt.**

Source được sửa tiếp trong lúc review. Review giữ hai snapshot và log riêng;
người review không sửa source app, không gọi model mới hoặc kiểm tra native.

## Kết quả hiện tại

| Bản được kiểm tra | Regression | Probes độc lập |
| --- | --- | --- |
| Snapshot bàn giao đầu | 161 passed, 6.96s | 7 failed, 0.26s |
| Snapshot sau thay đổi trong lượt review | 168 passed, 6.85s | 7 passed, 0.30s |

Không cộng hai suite thành một số test duy nhất: suite 168 đã có thêm 7 ca
lifecycle tương ứng với probes. Đây là kiểm tra phần mềm, không đo chất lượng AI.
Source snapshot sau thay đổi không đổi trong lần kiểm tra cuối.

## Lỗi lifecycle đã được sửa

- R1: completion/failure kiểm execution đúng trước commit; duplicate completion
  không thêm context; callback muộn không đổi lượt đã hủy thành failed; reset
  chặn callback của conversation cũ.
- R2: nhánh ambiguous target kiểm cancel và truyền ownership vào input/event.
- R3: runtime truyền `should_cancel` tới dispatcher, nên probe stop trong handler
  không commit artifact được tạo sau stop.
- R4: historical notes chọn revision cuối của owner cũ, khớp `notes_for_turn`.

Snapshot lỗi và mô tả chi tiết được giữ ở `initial_review.md`,
`reviewed_source/`, `contract_probes.txt`. Thay đổi tương ứng ở
`source_changes_during_review.diff`; source sau sửa ở `source_after_changes/`.
Các `.py.txt` là snapshot đọc, tránh pytest tự collect bản sao các test.

## R5 còn lại — P1: fixture/smoke cắt mất phản hồi cuối

Fixture DSA trong
[test_work_context.py:255](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/tests/test_work_context.py:255)
vẫn dùng `history.messages_with_turn_ids()[:-1]` sau `begin_turn`.
`begin_turn` chưa thêm request đang chạy vào context messages. Vì vậy slicing
xóa assistant answer/status của lượt trước. API đúng đang trả đầy đủ messages;
caller cần giữ chúng. `harness_context_probe.json` tái hiện sự khác biệt này.

Script smoke cũ mắc cùng lỗi và không truyền execution ID được cấp từ
`begin_turn` vào runtime. Snapshot script ở `original_smoke_runner.py.txt`.
Sau khi guard execution đã nghiêm, runner đó cần sửa cả identity và context
trước khi dùng lại. Không cần nới guard của core để giữ runner cũ chạy được.

## Smoke model cũ chưa chứng minh luồng đã đạt

Raw artifact được giữ nguyên và chụp thêm vào `original_dsa_core_smoke.json`.
Đánh giá offline ở `smoke_review.json`; **0 lời gọi model mới của người review**.
Đây là evidence development của source trước sửa, không xác nhận hành vi source mới.

- Có 0 tool calls, 0 note events, và `final_active_notes=[]`. Chưa có evidence
  model thực sự ghi/sửa notes dù có yêu cầu rõ.
- Lượt 2 timeout khoảng 90s. Các lượt trả text khác mất khoảng 51–62s; tổng
  client wall time các attempt khoảng 311.70s.
- Lượt 3 không giải thích `mid + 1`, lặp claim đã tìm được 8.
- Lượt 4 sai thuật toán: tìm 6 trong [2,4,6,8,10] phải dừng tại mid=2/a[2]=6,
  nhưng output hướng sang phần lớn hơn 6. Lượt 5 lặp lỗi đó và không quay lại
  được lời giải thích được yêu cầu. Đây là lỗi nội dung, vượt nhận xét “nông/lặp”.
- Lượt 6 bị cancel trước khi inference/tool bắt đầu. 0.15ms là early return,
  không chứng minh latency hoặc lifecycle của cancel in-flight.
- Token counters 0 ở timeout không chứng minh inference tiêu thụ 0 token.
- Runner dùng `plan_tasks=False` mặc định; native RAT dùng `plan_tasks=True`.
  Không dùng timing của runner đó như số đo native.

Cần một runner trong repo nhận output directory mới, lưu config/source/model
identity và raw model requests/responses. Sửa context rồi chạy development smoke
mới, giữ cả lỗi và kết quả cũ. Đánh giá đúng nghĩa của câu trả lời và quyết định
gọi operation riêng với status `completed` hoặc `error=None`.

## Phạm vi review và bàn giao

Review này chỉ xác nhận các ca lifecycle đã tái hiện trong snapshot được pin.
Source UI cũng đã thay đổi trong lúc review; wiring/native chưa được review
trong lượt này. Không coi headless tests là nghiệm thu UI hoặc năng lực DSA.
Không đổi research pipeline/default model/Stage 0.

Checklist còn lại ở
[handoff_antigravity.md](/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/rat_conversation_core_codex_review_20261013/handoff_antigravity.md).
Ưu tiên sửa R5 và bổ sung bằng chứng đúng trước khi trình duyệt kết quả hội thoại
hoặc mốc native UI tiếp theo.
