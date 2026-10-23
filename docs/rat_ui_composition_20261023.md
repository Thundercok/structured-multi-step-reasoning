# RAT Quick — hierarchy/composition, min mode trước

2026-10-23, Asia/Ho_Chi_Minh. Người dùng duyệt một lượt chỉnh hierarchy,
thông tin tài liệu, nhịp đọc và kết nối paper/composer; đồng thời nhắc người dùng
chủ yếu dùng min mode. Đây là chỉnh source Quick hiện tại, không redesign.

## Kết quả

- Min mode là trạng thái thu còn composer/mascot/notice, không đồng nghĩa cửa
  sổ hẹp. Kiểm cả thu/mở và độ rộng 520/700 px, hai theme.
- Header `Câu trả lời` là tiêu đề chính. Câu hỏi gốc thành dòng ngữ cảnh nhỏ,
  elide khi dài, có tooltip và bấm để mở/thu toàn văn. Trạng thái thực thi ở
  ngay dưới, vẫn wrap và đọc được; không thay nội dung trạng thái runtime.
- Nguồn thành dòng `N tham chiếu` mở/thu, nằm sau câu trả lời và trước nhật ký.
  Trạng thái xác minh vẫn hiện khi nguồn thu; không suy ra xác minh từ PDF.
  Nguồn lấy từ metadata theo lượt như trước, chỉ mở trang có vị trí hợp lệ.
- Một chip tài liệu trong composer thay chip cũ + hàng tài liệu đang chọn
  trong answer + menu/số trang lặp ở footer. Bấm tên/chevron mở thao tác PDF;
  nút bỏ đính kèm riêng vẫn còn. Dùng được khi min và full, tên dài elide,
  tên đầy đủ qua tooltip/menu. Thao tác chọn PDF khác vẫn ở footer.
- Paragraph, heading, list và code có khoảng cách rõ hơn. Vẫn là renderer
  nhỏ, inert/escaped; copy toàn văn giữ raw answer. Theme tối dùng đúng HTML
  tối đã có trong snapshot.
- Cạnh phải paper khớp composer. Giữ mascot, paper lệch phía sau, palette,
  vị trí composer và cách cửa sổ nở lên trên.
- Giữ rich HTML qua một property string ổn định: cập nhật snapshot chỉ để
  thu/mở không parse lại document làm mất bôi chọn. Draft, nguồn đang mở,
  câu hỏi đang mở và vị trí cuộn giữ sau thu/mở.
- Native review phát hiện menu PDF không nhận Escape khi ở min; thêm focus
  cho popup. Đã kiểm lại Escape trên cửa sổ native và qua QTest.

Không đổi controller/routing/model/research trong lượt này. Hành vi tự mở
answer khi runtime hoàn tất hiện có vẫn giữ. AI suggestion card vẫn bị bỏ.
Không rebuild bundle hay thay bản app cài sẵn; không commit/push.

## Validation và artifacts

Lần validation cuối: **82 passed in 24.38s** trên presentation/source, PDF,
Finder, unified flow, Apps contracts, chat session và conversation lifecycle.
Checks mới kiểm min/full qua chuột, PDF menu + Escape trong min, mở đúng trang
2, copy raw answer, bôi chọn/draft/cuộn, câu hỏi và tên PDF dài, hai độ rộng
và hai theme. Kiểm regression geometry Finder/Apps vẫn đạt.

`work/rat_ui_composition_20261023/` chứa snapshot trước lượt này, formatter
trước, scripts, logs/hash và captures. `final-tests.json` ghi hash trước/sau;
`capture-final.json` nối ảnh cuối với đúng source đã test. Gallery gồm 64 ảnh
composition trước/sau và 80 ảnh regression, không QML warning. Nội dung là
fixture tự soạn; PDF thật được tạo từ fixture, không đọc tài liệu cá nhân,
không gọi model hay indexer. Không dùng tests/ảnh để khẳng định model tốt hơn.

QML cuối: `a800fb53b56c47fd08fb06f69a05c2d8f67ec20c925c7b1ac696c51f3777a157`.
Baseline đầu lượt: `2f0b4f60f1370f0098a5a85541c6f414b0d891511fb758a98722b46ae18963ac`.
Baseline được chụp từ checkout thực tế khi bắt đầu lượt, không ghi đè ảnh cũ.

Đã xem source native ở 520 px: mở/thu nguồn, min/full, menu PDF trong min,
Escape và đọc đúng trang 2; fixture đã đóng. Chưa nghiệm thu đầy đủ IME,
đa màn hình, accessibility hoặc motion; Qt native có log IMK/keymapper.

## Các lần thử chưa đạt

- Test mới phát hiện mất selection khi snapshot đổi mode; đã ổn định rich
  text property, test bôi chọn sau thu/mở đạt.
- Có một run rộng thất bại geometry (tọa độ control âm) khi đồng thời chạy
  native fixture/CUA. Logs giữ ở `focus-review-failed.*`. Run độc lập sau khi
  đóng native fixture đạt 82 tests với cùng source hash; chưa kết luận chắc
  nguyên nhân của mọi lỗi geometry. Final test và capture chạy tuần tự.
- Qt trong sandbox vẫn lỗi CPU NEON; Qt checks/render/native dùng đường
  require_escalated được duyệt. Không dùng đường bỏ qua bộ duyệt.
