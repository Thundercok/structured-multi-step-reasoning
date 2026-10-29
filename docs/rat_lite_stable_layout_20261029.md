# RAT Lite .23 — ổn định bố cục trong một lượt dùng

Người dùng chốt 10 mục ngày 2026-10-29. Đây là lượt sửa bố cục hiện hành;
[hợp nhất bốn mode](backlog/rat_lite_unified_interaction_20261029.md) đã được
đưa vào backlog, chưa triển khai. Không thêm animation.

## Đối chiếu 10 mục

1. **Nhận diện phiên.** Đọc danh sách tiến trình: QA20 PID7562 vẫn chạy từ
   `dist/rat-lite-20261029-observable/`. Không coi quan sát phiên này là đánh
   giá .22/.23. Menu phụ của bản mới lấy BUILD/PID từ runtime; plist bản đóng
   gói cũng lấy BUILD chung, bỏ nhãn .20 bị hard-code. Không đóng phiên cũ.
2. **Điểm neo Chuột.** Giữ Look ngồi ở optical height134; baseline chân cố
   định. Đặt thân bubble theo vùng bao chung 168×134 trong host176×176, đủ
   cho dáng lỗi rộng. Metadata miệng của từng pose chỉ điều khiển đuôi thoại.
3. **Một bubble.** Giữ nguyên instance SpeechBubble qua peek/processing/result/
   error, thay text/actions. Không tạo cửa sổ business hay đường dispatch mới.
4. **Giữ khung khi xử lý.** Trước khi gán snapshot busy, chụp kích thước đang
   hiển thị vào shared SpeechSurface. Giữ kích thước trong lúc xử lý, bỏ giữ
   khi hoàn tất. Nếu chưa có khung, dùng 380×96. Khung đọc được đo trước ở
   chiều rộng dự kiến, tránh dùng cách xuống dòng của chiều rộng cũ để resize.
5. **Mức rộng chung.** SpeechSurface sở hữu các mức220/380/580 logical px.
   Reader chọn theo chữ; Minimal bắt đầu mức380, chỉ tăng khi cần trong lượt
   hiện tại. Xóa chữ/Gửi không làm chiều rộng co lại. Lần gọi mới khi đang ẩn
   được chọn lại mức phù hợp. Màn hình hẹp vẫn được clamp.
6. **Giới hạn che màn hình.** Bubble cao tối đa min(300px,38% chiều cao vùng
   làm việc), vẫn giữ font16 và cỡ Chuột lớn. Nội dung tràn dùng reader cuộn
   sẵn có; giữ hành động mở workbench rõ ràng cho nội dung dài. Khi màn hình
   ép chiều rộng nhỏ hơn mức dự kiến, dòng thêm vẫn có thể cuộn tới.
7. **Phía/đuôi ổn định.** Cả hai corner surface dùng baseline/vùng bao chung.
   Ưu tiên giữ phía cũ và rewrap trước khi đổi phía; chỉ đổi khi không đủ vùng
   đọc tối thiểu. Giới hạn màn hình và fallback trên/dưới vẫn áp dụng.
8. **Trạng thái gắn Chuột.** Cố định nhãn112×24 ở giữa phía dưới host thay vì
   bám mép pose có thể đổi. Nền chờ nhẹ hơn, không viền; pending/busy/paused/
   hover/focus được nhấn mạnh. Không thêm status window riêng.
9. **Peek/reading.** Giữ timeout5s chỉ cho peek. Hover, kéo/cuộn, phần chữ đã
   chọn, keyboard focus và context menu đều tính là đang tương tác. Reading
   không hết giờ. Clipboard mới giữ nguyên task/scroll/selection và chỉ cập
   nhật pending qua contract hiện có. Copy/close/recall vẫn dùng controller.
10. **Hoàn thiện source trước đánh giá.** Không chạy test, smoke, chụp ảnh hoặc
    tour UI trong lượt này. Chỉ chuẩn bị package sau source; bản đang chạy chưa
    thay thế. Chỉ nghiệm thu khi người dùng yêu cầu rõ.

## Ranh giới bằng chứng

Các mục trên mô tả source, không phải 10 mục đã đạt nghiệm thu native. Chưa đo
độ mượt, số lần native resize/paint, contrast trên nền desktop, đa màn hình hay
luồng đọc thật của .23. Kết quả test cũ không xác nhận thay đổi mới.

Tái sử dụng MiniShell, SpeechSurface, SpeechBubble, LookSurface, CompanionStatus,
place_look/place_speech và bộ nhớ reader hiện có. Business contracts/dispatcher,
default LLM off không đổi. Main UI integration, M3, Stage0 vẫn còn gate riêng.
