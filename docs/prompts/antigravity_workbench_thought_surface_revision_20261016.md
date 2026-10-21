# Antigravity — sửa cách hiểu thought bubble của Workbench

Đây là đính chính trực tiếp từ người dùng ngày 2026-10-16; ưu tiên hơn mô tả
polish cũ của Codex. Codex đã hiểu sai và hướng dẫn làm một bubble nhỏ chứa
`...`; bản triển khai theo hướng dẫn đó chưa đúng ý thiết kế.

## Ý cần thể hiện

**Toàn bộ khung Workbench phía trên chính là bong bóng suy nghĩ của Chuột.
Ba chấm tròn nối đầu Chuột với khung đó; khung được nới ra để chứa công việc.**

Sơ đồ quan hệ, không phải tọa độ hay tỷ lệ bắt buộc:

```text
       ╭───────────────────────────────────╮
       │ Workbench: tìm kiếm, nguồn,       │
       │ kết quả, xem chi tiết…            │
       ╰───────────────────────────────────╯
             ◯
           ○
         ·
       Chuột       lời thoại hiện có
                   composer duy nhất
```

## Revision cụ thể

1. Thay oval ellipsis nhỏ vừa thêm trong `rat/ui/workbench.py` bằng đường nối
   ba chấm từ gần đầu Chuột tới khung Workbench. Đặt ở cấp layout phù hợp để
   đường nối đi được tới khung; không gò toàn bộ hình vào vùng paint của mascot.
2. Chỉnh hình dáng khung Workbench cho đọc được như một thought bubble lớn,
   mềm và thống nhất với style hiện tại. Giữ các widget nguồn/kết quả/detail
   và finder bên trong, không tạo bản sao renderer hay một panel suy nghĩ mới.
3. Nới vùng làm việc để nội dung có chỗ hiển thị. Mở/thu theo nội dung trong
   giới hạn màn hình; khi hết chỗ thì scroll bên trong. Giữ composer bên dưới
   luôn truy cập được. Không kéo giãn cửa sổ vượt màn hình hoặc giật layout
   theo từng ký tự/kết quả. Không coi ảnh finder đang cắt gần hết hàng đầu là
   trạng thái hoàn chỉnh.
4. Bubble và đường nối là bố cục của Workbench, không bị ràng buộc chỉ vào
   `thinking/working/searching`. Sau done/error/cancel giữ lại công việc/kết quả
   đã có; trạng thái chuyển động dừng. Không thu khung đang có kết quả về dấu
   ba chấm chỉ vì model ngừng chạy. Không thêm nội dung suy nghĩ nội tâm.
5. Giữ mức tăng Chuột vừa phải như đã yêu cầu, nhưng kiểm tra toàn hình thật:
   tai/đuôi/chân phải đủ chỗ. Căn ba chấm theo vị trí đầu/khung khi resize,
   không dựa vào tọa độ cố định chỉ đúng ở một kích thước.
6. Kiểm tra light/dark, 420px, compact/expanded. Không che mặt Chuột, speech,
   composer hay nội dung. Đường nối không nhận focus/click. Reduced motion
   dùng chuyển trạng thái trực tiếp; không tạo animation idle/polling.

Giữ phần finder đang có và luồng một composer, Enter/chat/Hỏi tệp; không đổi
backend, routing, CoT controller hay thêm dependency. Đọc AGENTS.md và
docs/project_scope.md; giữ main và thay đổi đồng thời, không commit/push/pull/reset.

## Bàn giao để review

Ảnh toàn cảnh desktop + narrow + dark, thấy rõ Chuột → ba chấm → toàn bộ
Workbench. Có cặp compact/mở rộng và đang làm/xong hoặc hủy với nội dung còn
xem được. Ghi source hashes và cách capture, phân biệt fixture với live model.
Regression tập trung vào geometry/visibleRegion, composer và renderer identity;
chạy lại các suite liên quan trong handoff gốc. Tests xanh không thay thế việc
đối chiếu bố cục với ý người dùng đã đính chính ở trên.
