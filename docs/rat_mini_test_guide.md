# RAT Mini — hướng dẫn sử dụng và trạng thái kiểm chứng

**Ứng viên hiện hành M5.7:** gom UI thu gọn, correction/retry, nguồn dùng chung
và ổn định hóa. Gói dự kiến `dist/mini-m57/RAT Mini.app`. Screenshot thật được
người dùng yêu cầu riêng; chưa nghiệm thu máy người nhận hoặc tích hợp main.
Trạng thái actual: `audit/rat_mini_m57_20261027/status.json`.

**Source hiện hành M5.6-dev:** thêm editor OCR + xem OCR gốc + tool lưu phần
người dùng sửa thành artifact mới + retry riêng bước dịch. Chưa build/test M5.6.
Các mục M5.5/M5.4 bên dưới là mốc trước; ZIP M5.4 chưa có UI sửa OCR.

Source đã tiến tới **M5.5-dev**: hợp đồng ImageInput headless, workflow OCR→dịch
dùng chung và provenance xuyên artifact. Chưa build/test M5.5; app/ZIP M5.4 bên
dưới không chứa thay đổi M5.5. Chi tiết:
[image translation ingress](contracts/image_translation_ingress.md).

**Hiện hành M5.4:** screenshot do macOS tạo bằng ⌘⇧4, thả file ảnh vào RAT
để tự OCR/dịch. Có highlight “Thả ảnh để dịch”; nhận từng ảnh, kiểm tra dung
lượng/định dạng/kích thước trước decode. Copy file ảnh từ Finder rồi paste cũng
gắn draft để dịch bằng Enter. Không đăng ký global hotkey, không yêu cầu quyền
chụp màn hình cho luồng import. Xem [backlog](backlog/rat_mini_global_capture.md).
M5.4 chưa chạy test/UI acceptance; không dùng kết quả M5.2/M5.3 làm bằng chứng.

M5.3 thay adapter hotkey bằng native Carbon helper có event loop riêng, đóng
gói tại `dist/mini-m53-native-hotkey/RAT Mini.app`. Chưa xác nhận shortcut vật
lý của M5.3. M5.2 đã chụp và OCR thật qua menu sau khi cấp quyền, nhưng shortcut
vật lý vẫn thất bại; kết quả OCR tiếng Việt `same_language` không được tính là
kiểm chứng dịch Anh→Việt. Xem `audit/rat_mini_hotkey_20261026/final_status.json`.

M4 bỏ các nút mode của M3: một ô nhập gửi yêu cầu vào router headless dùng chung.
Yêu cầu rõ được lập kế hoạch một action; yêu cầu mơ hồ dùng InputRequest và
giữ nội dung gốc khi người dùng trả lời. Mini là vertical slice của RAT chính,
xem [quyết định hiện hành](rat_mini_vertical_slice.md).

M5 nối ⌥⇧D với chụp vùng → OCR → dịch; tự phân loại text/tệp/ảnh khi paste,
và căn lại chuột. Theo yêu cầu người dùng, không chạy kiểm thử cho các thay đổi
này. Build M5 được đặt riêng tại `dist/mini-m5/`, giữ nguyên app M4 cũ.

Mục tiêu bản này: Spotlight và dịch đoạn văn bản trong UI giấy Qt Quick của RAT.
Mini dùng chung QuietButton, DeskIcon, KeycapBadge và FinderResultsView với RAT
chính; MiniQuickController nối các thao tác vào MiniSession. Không nạp controller
PDF hay QtWidgets. Bản M2 được giữ phục hồi trong audit/rat_mini_m3_20261026/.
Vector DB, embedding và Swift Translation không được nạp trong runtime Mini.

## Khởi động

Mở bản app cần kiểm chứng (M5.4: `dist/mini-m54-drop-image/RAT Mini.app`),
hoặc từ thư mục gốc repo:

```bash
source .venv/bin/activate
python mini_app.py
```

Chỉ chạy một bản trong cùng thư mục cấu hình. Bản đóng gói ARM được ký ad-hoc;
chưa notarize và chưa kiểm thử trực tiếp trên máy macOS 14 của người nhận.

## Thao tác

- Gõ `tìm báo cáo hôm qua` hoặc tên như `test.pdf`, rồi Enter hoặc bấm nút gửi. Tìm trong
  Documents, Desktop, Downloads. Chọn kết quả bằng ↑↓, Enter mở file bằng macOS;
  nhấp đúp cũng mở được. File chưa được Spotlight index có thể không xuất hiện.
- ⌘⇧4 lưu screenshot, kéo file ảnh vào RAT để OCR/dịch qua cùng capability.
- Gõ/paste đoạn văn rồi Enter; router dùng nội dung, nguồn nhập và ngữ cảnh.
  Có thể chỉ rõ `dịch: Hello world`; chỉ hỏi lại khi chưa rõ. Shift+Enter xuống dòng.
- Cmd+V ảnh pixel gắn draft vào ô nhập; Enter để OCR/dịch. Copy tệp từ Finder
  giữ nghĩa tìm tên tệp, không tự đọc cả tài liệu.
- Copy đoạn văn bản rồi chọn **⋯ → Dịch Clipboard**. Đoạn này được gửi đến dịch vụ dịch online.
- Esc ẩn cửa sổ; biểu tượng kính lúp của RAT ở menu bar cho phép hiện lại và mở cấu hình.
- **Thu gọn/Kết quả** gấp hoặc mở giấy kết quả; nút **⋯** mở cài đặt QML.

## Bằng chứng và giới hạn

`audit/rat_mini_m4_20261026/live/` dành cho bằng chứng của M4. Bằng chứng M3 tại
`audit/rat_mini_m3_20261026/live/`; bằng chứng lịch sử
M2 vẫn nằm tại `audit/rat_mini_m2_20261026/live/`. Các JSON lưu request, response,
artifact, verification. PDF kiểm thử có nguồn và SHA256 tại
`artifacts/rat_mini_m1_20261026/pdf-provenance.json`.

Google GTX đang trả HTTP 429 trong phiên kiểm thử; bản dịch thành công thực tế
dùng MyMemory dự phòng, có ghi provider trên UI. HTTPS vẫn kiểm tra chứng chỉ
bằng certifi; không dùng `verify=False`.

Cả thao tác trực tiếp và UI đều đi qua capability contract, dispatcher và
AgentExecutionService. Runtime chỉ đăng ký Finder và Translation. Nhánh Agent
cloud đã nối runtime nhưng chưa kiểm thử với model thật vì phiên này không có
API key; các thao tác trực tiếp đã chạy backend thật và không cần gọi LLM.
Verifier kiểm tra file/quyền đọc/identity và độ phủ văn bản dịch, không xác nhận
chất lượng ngữ nghĩa của bản dịch. Không thay đổi hoặc vượt Stage 0 nghiên cứu.
