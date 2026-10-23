# RAT follow-up — 2026-10-24

Tiếp tục lỗi model không sửa code theo yêu cầu mới. Toàn bộ hội thoại nhập/bấm desktop, backend/model local thật. Không inject đáp án, không chạy lại canned UI fixtures. Đây là assistant-lane development smoke; Stage 0 và research campaigns không đổi.

## Source đã sửa

- `AssistantRuntime._native_messages`: bỏ bản lặp của user_query/assistant_summary trong compact context chỉ khi có cặp user/assistant trùng nguyên văn trong 12 history messages đang gửi. Giữ các lượt không còn trong history, ID, trạng thái, artifact/source refs và canonical snapshot. Marker content_in_chat_history cho biết nơi nội dung còn nằm. Payload live xác nhận marker xuất hiện và bản lặp biến mất.
- Thêm hướng dẫn chung: đáp án cũ có thể sai; yêu cầu chỉnh sửa phải áp dụng ràng buộc mới. Đây không phải verifier và không tự chứng nhận chất lượng.
- `rat.ui.quick_app`: thêm tùy chọn chạy rõ ràng `--local-assistant-model` và `--discover-tools`. Không đổi model/catalog mặc định hoặc config cá nhân; từ chối dùng flags để ghi đè runtime do host inject.

Cách chạy profile đã kiểm:

```bash
.venv/bin/python -m rat.ui.quick_app --local-assistant-model qwen3:4b-instruct --discover-tools
```

CLI startup/close được kiểm riêng, exit 0, không thêm model call. Hai lượt model của profile dùng cùng engine/QML/controller và cấu hình qua composition observer có ghi raw artifacts. CLI flags được thêm sau lượt model; manifest ghi rõ source delta này.

## Kết quả thật

| Cấu hình | Quan sát |
| --- | --- |
| 1.5B + discovery, trước sửa dedup | Hàm thường đạt 8 ca; yêu cầu tìm index đầu tiên vẫn sai. |
| 1.5B + catalog mặc định, sau dedup | Payload đã bỏ trùng đúng; yêu cầu sửa vẫn sai. Không tuyên bố prompt fix đã giải quyết chất lượng. |
| Qwen3 4B Instruct + 22 schemas | Timeout khoảng 95,4 giây khi prefill; token usage unknown. |
| Qwen3 4B Instruct + discovery | Hai phản hồi thật, khoảng 48,8 và 33,3 giây. Hàm ban đầu và hàm sửa đều đạt 8/8 ca tương ứng; bản sửa lưu result và tiếp tục tìm bên trái, [2,2,2], target=2 trả 0. |

Model digest 4B: `0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`; 1.5B giữ model đã cài từ lượt trước. Không tải model. Discovery là cơ chế sẵn có: chỉ đổi schemas/prompt trong các profile có bật; các operation khác vẫn cần discovery receipt hợp lệ. Lượt này chưa kiểm lại workflow PDF hoặc operation discovery, nên chưa đủ căn cứ bật discovery mặc định.

Chỉ có hai lượt trong một hội thoại cho profile đạt, không seed, khác model/settings và trạng thái cache. Không suy ra model 4B luôn đúng, không coi 8 ca là accuracy nghiên cứu hoặc verifier trong app. UI vẫn ghi chưa xác minh. Thời gian trên là wall time của các request thực, không phải replay hoặc benchmark tổng quát; bản 4B có đánh đổi latency rõ ràng.

## Evidence và giới hạn

- [Hội thoại profile đạt](../work/rat_followup_4b_discovery_live_20261024/conversation-review.md)
- [Raw calls/settings/source guards và tổng hợp](../work/rat_followup_4b_discovery_live_20261024/run-review.json)
- [Kiểm hàm thực tế, gồm các ca FAIL](../work/rat_followup_4b_discovery_live_20261024/observed-function-check.json)
- [Full mode của hàm sửa](../work/rat_followup_4b_discovery_live_20261024/live-turn-turn-2-full.png)
- [Source delta sau live và CLI startup](../work/rat_followup_4b_discovery_live_20261024/final-source-review.json)

Mỗi run có prompts, public responses, lỗi, screenshots, model-call metadata và script. Private thinking không được lưu. py_compile, CLI --help, startup/close native và git diff --check đạt. Không dùng chúng làm bằng chứng chất lượng. Không commit/push, không đổi harness hoặc thay đổi nghiên cứu của chat khác. Daemon test được dừng sau kiểm.
