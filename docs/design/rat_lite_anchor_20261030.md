# RAT Lite — cùng một cụm quanh Chuột

Chốt 2026-10-30: Chuột nổi; bấm để mở một ô nhập bên cạnh, không chọn mode. Kết quả nằm phía trên ô trong cùng cụm. Chuột giữ tỷ lệ và anchor khi nội dung thay đổi. Bảng setup có thể lớn, riêng; việc nhập tay không phụ thuộc quyền Trợ năng.

Phác thảo bố cục (không theo tỷ lệ):

```
Chờ:                 🐭
Nhập:   [ Tìm file hoặc dịch…   ↑  ⋯ ]  🐭
Dịch:   [ Bản dịch có thể chọn        ]
        [ Hỏi tiếp…             ↑  ⋯ ]  🐭
File:   [ Tên file · đường dẫn        ]
        [ Tên file · đường dẫn        ]
        [ Mở file     Mở rộng          ]
        [ Hỏi tiếp…             ↑  ⋯ ]  🐭
Lỗi:    [ Lỗi cụ thể · cách khôi phục  ]
        [ Hỏi tiếp…             ↑  ⋯ ]  🐭
```

Chọn phía giấy theo vùng trống, giữ Chuột trên màn hình hiện tại; chiều cao gọn có giới hạn và có cuộn; Mở rộng chỉ thay projection của cùng task. Lỗi, kết quả và tiến trình phải lấy từ service. Đây là bản thiết kế bố cục, không phải ảnh app hay bằng chứng nghiệm thu. Quyền Trợ năng chỉ cần cho capture selection. Không khôi phục Workbench như quyết định đã nghiệm thu, không giả model loop.
