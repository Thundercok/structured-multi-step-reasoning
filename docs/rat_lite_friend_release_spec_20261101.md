# RAT Lite — bản phát hành cho người dùng cuối, spec chốt

Cập nhật: 2026-11-01, Asia/Ho_Chi_Minh. Trạng thái: spec đã chốt theo quyết định
người dùng, chưa triển khai. Thay cho các phần mâu thuẫn trong
[rat_mini_spec.md](rat_mini_spec.md) và [rat_lite_20261030_overhaul.md](rat_lite_20261030_overhaul.md).

## 1. Người dùng và mục tiêu

- Người dùng cuối: sinh viên không rành công nghệ, tải app về và dùng ngay.
- Máy: Mac chip M (arm64), macOS 14 trở lên. Mac Intel ngoài phạm vi trừ khi
  người dùng yêu cầu bản x86_64.
- Tiêu chí: không có bước nào khiến người dùng phải đoán. Cho phép đúng một bước
  hệ thống khi mở lần đầu (mục 6) và quyền Trợ năng là tùy chọn.

## 2. Hai việc duy nhất

| Việc | Cách dùng | Cách chạy |
| --- | --- | --- |
| Tìm file hoặc app không nhớ tên | Gõ gần đúng vào ô nhập | Spotlight + catalog app, xếp hạng có gập dấu tiếng Việt |
| Dịch đoạn đang đọc (paper PDF, web, ảnh) | Bôi đen rồi bấm phím tắt, hoặc chụp ảnh vào clipboard rồi bấm phím tắt, hoặc dán/thả | Dịch Anh ↔ Việt trên máy (CTranslate2/OPUS-MT đóng kèm) |

Không có trong Lite: LLM, API key, dịch qua mạng, chọn dịch vụ dịch, dịch cả trang
PDF (thuộc bản full), sắp xếp thư mục, "Giải thích", sửa yêu cầu đã gửi, panel
ngữ cảnh. Code các phần này giữ trong lõi cho bản full; Lite không đăng ký tool
và không hiển thị UI của chúng.

## 3. Lite vẫn đại diện cho bản full

- Cùng luồng tầng 0 của RAT: yêu cầu → chọn tool → thực thi → kiểm chứng → dừng →
  kết quả có bằng chứng. 0 lần gọi LLM. Bản full cắm thêm tầng 1+ (vòng Agent)
  vào cùng contracts, dispatcher và verifier.
- Quá trình hiện bằng một dòng trace ngắn dưới kết quả, ví dụ
  "Tìm trong Spotlight · đã kiểm tra file tồn tại" hoặc
  "Dịch trên máy · Anh → Việt · ghép 4 dòng bị ngắt". Không hiển thị raw reasoning.
- UI không phụ thuộc tool: mỗi tool trả về một loại thẻ (danh sách kết quả, thẻ
  bản dịch). Thêm tool ở bản full là thêm loại thẻ, không thêm nút rải rác.

## 4. Màn hình: ba trạng thái

1. **Trống:** ô nhập, hai gợi ý "Tìm file hoặc app" và "Dịch đoạn đã chép", tên
   phím tắt. Lần đầu có thêm một dòng chào ngắn, không có màn setup riêng.
2. **Kết quả:**
   - Danh sách: app và file chung một danh sách, app đứng trước khi tên khớp.
     Enter mở, ⌘C copy đường dẫn, ⌘R hiện trong Finder.
   - Thẻ dịch: bản dịch, nút Sao chép, đoạn gốc thu gọn và sửa được tại chỗ
     (sửa xong tự dịch lại). Không có màn OCR/ảnh/nguồn riêng.
3. **Cài đặt (một trang):** phím tắt, chiều dịch mặc định, bật Trợ năng (tùy chọn),
   xuất chẩn đoán (đặt cuối trang).

## 5. Chất lượng dịch cho paper

- Làm sạch chữ chép từ PDF trước khi dịch: ghép dòng bị ngắt giữa câu, nối từ bị
  gạch nối cuối dòng, đổi ligature (ﬁ, ﬂ) về chữ thường, bỏ khoảng trắng thừa.
- Danh sách thuật ngữ học thuật giữ tiếng Anh trong ngoặc, ví dụ
  "bộ điều khiển (controller)". Danh sách đóng kèm, không tải về.
- Đo tham chiếu 2026-11-01 trên máy dev: ~1 giây cho một đoạn ~110 từ, ~5,5 giây
  cho ~570 từ. Chưa đo trên máy người dùng cuối.
- Apple Translate là phương án so sánh sau, khi có gói ngôn ngữ; không phải mặc định
  vì cần người dùng tự tải gói trong Cài đặt hệ thống.

## 6. Quyền và phân phối (miễn phí, không Developer account)

- Đóng gói `.dmg` có sẵn lối tắt Applications để kéo thả. Bỏ file `.command`
  (file tải về cũng bị Gatekeeper chặn).
- Kèm một trang hướng dẫn có hình cho đúng một lần mở lần đầu:
  Cài đặt → Quyền riêng tư & Bảo mật → "Vẫn mở".
- Ký bằng chứng chỉ code-signing tự tạo, cố định giữa các bản build, để quyền
  Trợ năng không mất khi cập nhật. Người dùng tự tạo chứng chỉ một lần trong
  Keychain Access theo hướng dẫn; build script nhận tên qua `RAT_CODESIGN_IDENTITY`.
- Không cần quyền cho: tìm file/app (Spotlight), phím tắt (`RegisterEventHotKey`),
  dịch từ clipboard, dịch ảnh chụp bằng ⌃⌘⇧4.
- Trợ năng chỉ cần để bôi đen rồi bấm phím tắt mà không ⌘C. App mời cấp quyền khi
  người dùng thử lần đầu, tự nhận ra khi đã cấp, không bắt buộc từ đầu.

## 7. Nghiệm thu trước khi gửi

Kiểm tra trên một tài khoản macOS mới (người dùng tự tạo), cài từ `.dmg` như
người dùng cuối:

- [ ] Mở lần đầu chỉ gặp bước "Vẫn mở" đã có trong hướng dẫn.
- [ ] Không có hộp thoại quyền nào hiện ra khi chưa dùng tới chức năng cần quyền.
- [ ] Tìm được app và file khi gõ thiếu dấu, sai một chữ.
- [ ] Bôi đen một đoạn trong paper mở bằng Preview → ⌘C → phím tắt → có bản dịch
      đọc trôi, không có dòng bị ngắt giữa câu.
- [ ] ⌃⌘⇧4 chụp một đoạn → phím tắt → có bản dịch.
- [ ] Cập nhật lên bản build mới: quyền Trợ năng vẫn hoạt động.
- [ ] Mọi thông báo lỗi bằng tiếng Việt thường, có một hành động gợi ý.

## 8. Các bước triển khai (mỗi bước một commit)

1. Rút tool và UI ngoài phạm vi khỏi profile Lite.
2. Gom `MiniDesk.qml` về ba trạng thái và hệ thẻ theo loại kết quả.
3. Thêm app vào danh sách tìm kiếm.
4. Làm sạch chữ PDF và danh sách thuật ngữ, có test.
5. Luồng clipboard và ảnh chụp không cần quyền; mời Trợ năng khi cần.
6. Đóng gói `.dmg`, ký chứng chỉ cố định, trang hướng dẫn có hình.
7. Đi qua UI thật, chụp từng trạng thái, chạy checklist mục 7.
