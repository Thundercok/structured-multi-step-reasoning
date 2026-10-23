# RAT — backend cancel, prompt cache và code preview · 2026-10-23

Đã kiểm bằng nhập/bấm desktop và Ollama local qwen2.5:1.5b, digest giữ nguyên như lần trước. Không inject đáp án hoặc dùng backend giả. Đây là assistant-lane smoke, không phải nghiệm thu policy/research, không đổi Stage 0.

## Thay đổi source

- Kết nối HTTP riêng cho request có cancellation callback. Watcher shutdown đúng socket khi Dừng hoặc hết deadline; không unload model hoặc hủy request khác. Callback đi qua actor, planner và selected-document Ollama. Backend khác giữ capability contract hiện có.
- Chuẩn hóa timeout thành `timeout`, giữ error_detail và usage unknown khi backend không trả số đo. Đáp án công khai rỗng có mã lỗi riêng và thông báo rõ; không tự tạo nội dung hoặc retry che lỗi. Chưa tái hiện empty response sau sửa nên chưa xác nhận hết nguyên nhân upstream.
- Code Python thuần có định nghĩa hợp lệ được nhận dạng bằng AST, chỉ parse, không thực thi trong renderer. Full giữ khoảng trắng; min hiện tối đa ba dòng monospace cho code có hoặc không có Markdown. Copy vẫn giữ raw answer.
- Đặt historical context trước yêu cầu hiện hành. Chuyển timestamp/member sang host data frame, kèm system rule xác định vai trò metadata; không dùng text này để cấp quyền hiệu ứng. Render-only xác nhận Ollama trước đó ghép timestamp vào trước tools, gây mất cache dù source đã đặt system message riêng.

## Bằng chứng trực tiếp

| Kiểm | Kết quả |
| --- | --- |
| Dừng trong desktop | Server ghi `cancel task` và trở về idle; request trả cancelled, không xuất đáp án muộn. |
| Code không Markdown | Min giữ 3 dòng, full giữ thụt dòng; kiểm bằng đáp án mới sinh, không replay. |
| Sao chép | Bấm Copy rồi paste trong composer xác nhận raw code còn thụt dòng. |
| Đóng khi đang chạy | Lần riêng với observer sửa thoát 0, source hash không đổi, request thật cancelled. |
| Prompt cache | Cùng câu hỏi code: 33,288 ms trước → 9,351 ms sau; cached prompt 679 → 3.343 tokens, prefill 26,200 → 3,270 ms. Đây là quan sát hai lượt không seed, không phải benchmark tổng quát; lượt đầu sau sửa vẫn 33,700 ms. |
| Static checks | py_compile và git diff --check đạt; không chạy lại fixture UI để gọi là live acceptance. |

## Chưa đạt

Model vẫn trả sai index đơn giản (9 trong [2,4,7,9,13] trả 2 thay vì 3) và không sửa yêu cầu tìm index đầu tiên dù đã nêu phản ví dụ. Hàm thường đạt 8 ca, nhưng các lượt sửa vẫn trả 1 cho [2,2,2], target=2 khi cần 0. UI vẫn ghi chưa xác minh. Không tuyên bố sửa prompt đã giải quyết chất lượng hoặc mọi timeout/empty response.

Lần đóng đầu crash ở observer gọi grabWindow trên cửa sổ đã ẩn (stack chính nằm ở meth_QQuickWindow_grabWindow); chỉ sửa script chụp ảnh, không sửa production để che lỗi. Bản crash và các lần không đạt được giữ nguyên. Một lượt thao tác paste sau Copy vô tình gửi raw code, được ghi rõ trong transcript; không dùng nó làm evidence cho prompt giải thích dự định.

## Artifacts

- [Hội thoại sau sửa, gồm lỗi thật](../work/rat_context_live_20261023/conversation-review.md)
- [Acceptance phân biệt UI và chất lượng](../work/rat_context_live_20261023/acceptance-review.json)
- [Các hàm thật và kiểm ca nhỏ](../work/rat_context_live_20261023/observed-code-check.json)
- [Min code](../work/rat_context_live_20261023/live-turn-turn-2-min.png), [full code không Markdown](../work/rat_context_live_20261023/live-turn-turn-4-full.png)
- [Trước sửa ngữ cảnh](../work/rat_backend_live_preview_20261023/conversation-review.md)
- [Timeout/cancel và bug renderer ban đầu](../work/rat_backend_live_20261023/conversation-review.md)
- [Đóng cửa sổ sau sửa observer](../work/rat_close_live_20261023/source-manifest.json)

Mỗi thư mục có model-calls.json (request, public response, phases và usage-known), conversation.json, screenshots, source hashes và script. Không lưu private thinking. Số token không được trả khi hủy/timeout là unknown, không phải chi phí bằng 0. Render-only không sinh token; cấu hình này được đối chiếu với [Ollama v0.34.3 routes](https://github.com/ollama/ollama/blob/v0.34.3/server/routes.go).

Không build/deploy app cài sẵn, commit hoặc push. Giữ nguyên thay đổi nghiên cứu của chat khác. Daemon test local được dừng sau kiểm.
