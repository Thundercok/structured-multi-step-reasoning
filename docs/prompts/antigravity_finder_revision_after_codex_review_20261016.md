# Antigravity — sửa finder/composer sau review độc lập

Đây là review phần hành vi ngoài thought bubble. Giữ bố cục thought bubble vừa
đính chính và phần code đúng; không bắt đầu tích hợp MLX hoặc thêm tính năng mới.
Đọc AGENTS.md và docs/project_scope.md. Giữ main, các thay đổi đồng thời và recovery;
không commit/push/pull/reset hoặc tạo branch.

Codex kiểm tra đúng source khớp SHA256 trong
`docs/evidence/rat_workbench_native/native_scene_session.json` của bản revision
thought bubble. Chưa thể nghiệm thu finder: có lỗi ngoài phạm vi 87 tests được
nêu trong log mới.

## Hai lỗi P1 — sửa trước

1. **Xóa hết truy vấn có thể làm app thoát.** Trong
   `rat/ui/omnibar.py:_on_composer_text_changed`, dòng 2163 của snapshot review
   đọc `current_snapshot.has_meaningful_content`, nhưng `WorkSceneSnapshot`
   không có thuộc tính đó. Khi finder bật, ở compact và chat còn rỗng, gõ rồi
   xóa ô nhập gây `AttributeError` trong Qt slot. Chạy cô lập đã exit 134.
   Sửa theo trạng thái/contract có thật, bảo toàn công việc cũ khi chỉ xóa draft;
   không dùng giá trị mặc định để che một lỗi hợp đồng chưa hiểu.
2. **Dán draft dài hơn 2.000 ký tự phát exception từ finder.** Slot gọi thẳng
   `SearchCoordinator.submit(q)`, API này từ chối chuỗi dài bằng
   `ValueError('invalid_finder_request')`. Finder là gợi ý phụ của composer;
   không được làm hỏng draft chat dài. Giữ nguyên draft, bỏ qua/ẩn hoặc báo
   trạng thái tìm kiếm phù hợp, vô hiệu kết quả cũ; đừng cắt nội dung chat để
   vượt validation. Không để exception thoát qua Qt callback.

## Các lỗi P2 — cần hoàn tất trước khi gọi finder dùng được

3. **Phím điều hướng chưa nối đủ.** Nhánh bảo toàn text editing trả `False`
   cho Down/Tab trước khi đến nhánh focus finder. Ngoài ra finder_box/row không
   được cài `OmnibarInputFilter`, nên khi focus danh sách, Down không đổi chọn.
   Test hiện tại chỉ gọi `navigate()` trực tiếp nên bỏ lọt lỗi. Nối event thật,
   giữ caret đa dòng và IME đúng; một dòng tại biên phải đi vào gợi ý, Up ở
   đầu trả về composer. Test cả focus trên row/button. Khi sửa shortcut, dùng
   đúng hit: nhánh Cmd+Enter hiện gọi `_reveal_current_in_finder()` của danh
   sách legacy thay vì path đang chọn trong finder; sửa luôn đường gọi này.
4. **Selection bị reset khi snapshot bổ sung tới.** `navigate()`/click chỉ
   đổi `FinderSuggestionsWidget.selected_resource_id`; `_finder_selected_id`
   của window không được cập nhật. Delivery lại truyền id cũ của hàng đầu.
   Có một owner rõ ràng cho selection; cập nhật từ cả phím và click, giữ đúng
   resource_id còn tồn tại khi nhận snapshot cùng query. Semantic hiện chưa
   nối provider thật; đây là lỗi hợp đồng progressive update, không phải kết
   luận đã chạy semantic trong UI. Tránh phá focus/scroll khi làm lại rows.
5. **Truy vấn đầu tiên bị quên khi catalog chưa sẵn sàng.** Gõ trước callback
   catalog_ready thì không submit. `_on_finder_catalog_ready()` tạo coordinator
   nhưng không gửi lại draft hiện tại; người dùng phải gõ thêm mới thấy kết
   quả. Sau init, xử lý draft còn hợp lệ một lần; không replay query đã xóa,
   đã submit/hủy hoặc còn trong IME preedit.
6. **Callback catalog muộn khởi tạo service sau shutdown.** Shutdown đã đặt
   `_shutting_down=True`, nhưng `_on_finder_catalog_ready()` không kiểm tra,
   vẫn tạo `SearchCoordinator` mới. Chặn callback sau đóng, xử lý init/close
   idempotent; không tạo worker mới sau cleanup. Không terminate thread.
7. **Nút thao tác finder bị cắt ngang.** Ảnh Cocoa mới vẫn cắt nút bên phải;
   probe với tên `so_tay_sinh_vien_2026.txt` và snippet bình thường xác nhận
   nút nằm ngoài viewport ở cả 620px và 420px. Hàng/label đang ép chiều rộng,
   trong khi horizontal scrollbar bị tắt. Cho phần text co/ellipsis hoặc
   reflow actions theo bố cục; giữ mọi hành động truy cập được, không chỉ Hỏi/Mở.
   Đối chiếu geometry/visibleRegion, không chỉ isVisible hoặc tăng chiều cao.

## Bằng chứng và regression cần chạy

Codex không sửa source sản phẩm; chỉ thêm probe/audit. Các fixture dùng file
tổng hợp và mock model/action; không scan thư mục cá nhân hay chạy inference.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  audit/rat_finder_codex_review_20261016/test_finder_integration_probes.py -q
```

Hiện **9 failed, 3 passed** (12 cases, gom thành 7 vấn đề ở trên). Hai probe
exception có `sys.excepthook` trong test để lưu lỗi thay vì để Qt abort. Probe
draft dài dùng coordinator thật; keyboard dùng `QTest.keyClick`; geometry dùng
helper kiểm tra viewport của suite hiện có. Không bỏ/xfail/nới assertion để
đếm xanh. Nếu đổi thiết kế điều hướng, giải thích và giữ kiểm chứng hành vi
tương đương bằng phím thật.

Ba case đã đúng: GUI bỏ snapshot stale, các nút Mở/Xem/Hiện trong Finder gửi
đúng path của row, nút Hỏi chọn nguồn và giữ draft mà chưa submit chat.

Bộ regression rộng hơn: **171 passed, 1 failed, 3 subtests passed** trong
45.95s. Failure là
`tests/test_rat_one_box_ui.py::test_result_opens_at_start_instead_of_skipping_form_fields`:
scrollbar 7, card.y() 8. Chạy riêng vẫn fail. Chưa xác định nguyên nhân do thay
đổi nào; đừng gọi toàn bộ UI xanh hoặc nới test tùy tiện. Cần giải thích/sửa
theo hợp đồng mở đầu kết quả và bảo đảm form field đầu tiên còn thấy được.

Chạy lại 8 suite UI + progressive search + active-detail probe của handoff gốc,
và `tests/test_selected_document_ui.py` để giữ luồng Hỏi. Lưu XML, source hashes,
ảnh finder có tất cả actions ở desktop/narrow. Không dùng thêm lượt benchmark
model hoặc thay research protocol cho revision UI này.

Audit: `audit/rat_finder_codex_review_20261016/` gồm snapshot source, manifests,
`regression.xml`, `scroll_recheck.xml`, `probes.xml` và review. Sửa hai P1 trước,
rồi nối các tương tác còn thiếu. Báo các kết quả thực tế, không chỉ số test tổng.
