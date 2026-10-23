# Thu gọn bộ test — đợt 1, 2026-10-23

Đã sửa 3 file, giảm ròng 101 dòng trong test/CI (104 dòng bỏ, 3 dòng thêm).
Bỏ 3 hàm test, tương ứng 5 ca sau parametrization; không gỡ file test.

- Gỡ job Watch Bot đã lỗi thời khỏi CI; giữ nguyên job nghiên cứu.
- Gỡ 2 hàm engine trùng trong `tests/test_dsa_multi_turn_flow.py`; giữ bản tương ứng trong `tests/test_quick_unified_flow.py`. Backend doubles có cùng embed/run; bản Widgets chỉ thêm thuộc tính cancel_check_fn không được dùng ở hai ca này. Hai hàm bị gỡ chỉ dùng engine, không dùng UI fixture nhận vào.
- Gỡ class TestAppsGridPolishContracts: một test dò chuỗi kích thước, màu và tên QML. Việc dò source không kiểm tra được focus, cuộn hay mở app. Đợt này chấp nhận bỏ guard về source này; chưa tuyên bố có ca hành vi thay thế cho mọi hạng mục nó liệt kê.

## Kiểm chứng

Lệnh trong `pytest.log`: 70 passed in 10.74s, gồm nhóm nghiên cứu bắt buộc, selected PDF, selected document QA và collector local-file smoke. Các suite này không phải các module GUI vừa sửa.

AST parsing và git diff --check đạt cho các file sửa. Không chạy được nguyên suite Qt do lỗi native import neon đã ghi ở báo cáo triage.

Bản file trước sửa cùng SHA256 nằm trong `before/` và `manifest.json`; phục hồi không phụ thuộc commit.

## Phần tiếp theo

- Test chức năng đọc/mở file thành công phải đi qua file có bytes thật và code đọc thật. Chỉ gán SelectedPDF hoặc kết quả tool vào trạng thái không chứng minh chức năng đọc.
- Giữ đường dẫn không tồn tại cho ca báo lỗi; giữ dữ liệu giả cho unit test hợp đồng và trình bày khi được ghi đúng phạm vi.
- Chưa gỡ các suite nghiên cứu, các ca cancellation/timeout/stale callback, hoặc các thay đổi test đang có của công việc khác.
- CI vẫn chỉ bao phủ nhóm nghiên cứu hiện có. Bỏ job Watch Bot không có nghĩa đã bổ sung coverage runtime.
