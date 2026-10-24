# Build .10 — review ảnh mới nhất

2026-10-24. Đọc trực tiếp ảnh của `29-turn3-seamless-reader`, không điều khiển
Antigravity, không chạy model hoặc sửa product code trong lượt review này.

## Findings

1. **P1 — Header tràn ngang, mất control.**
   `screenshots/r02-14-page-full.png` và `r01-03-page-full.png`: cụm điều hướng,
   input trang, nút đọc, tìm, mở ngoài, tên file, Chép và thu gọn cùng một hàng.
   Nút Chép đi ra ngoài mép phải ảnh; thu gọn không còn thấy trong khung.
   RowLayout header trong PDFDesk.qml cần ngân sách chiều rộng theo chính tờ
   kết quả, không theo toàn window. Thu nhỏ chữ tên file chưa giải quyết được
   tổng minimum widths của các control.

2. **P2 — Hướng dẫn chọn text xuất hiện trong mode ảnh.**
   Cùng ảnh có “Bôi chọn đoạn cần lấy, rồi chép trích dẫn” nhưng mode đang là
   Trang gốc (ảnh). Không được hướng dẫn một thao tác chưa được hỗ trợ bởi
   control đang hiển thị. Chỉ hiện hướng dẫn phù hợp với mode/hành vi thật.

3. **Phạm vi thiết kế đã lệch quyết định mới.**
   Build này vẫn là Seamless PDF Reader: full-page preview, lật trang, Trang
   gốc/Văn bản. Người dùng đã chuyển reader đầy đủ vào backlog và chọn luồng
   hỏi thông tin → trang nguồn → cap đúng đoạn. Giữ code/recovery nhưng không
   tiếp tục coi toolbar reader này là main flow cần hoàn thiện ở Turn 3.

4. **Mật độ thông tin/điều khiển thừa.**
   Số trang lặp ở header, tiêu đề, chip và footer. Trang gốc bị scale nhỏ trong
   tờ hẹp khiến phần chữ cần tìm không đọc được ngay; người dùng phải tự đi
   tìm trên toàn trang. `r01-06-search-full.png` có ảnh vùng khớp phù hợp hơn,
   nhưng nhãn “Trang PDF 10 · 10” lặp thông tin và chưa trả lời nội dung cần tìm.

## Giới hạn QA đang có

Run 29: calls=[], closed=true, QML warnings=[]. Capture guard ở runner chỉ
kiểm view height/preferred height và paper_top khi expanded, không kiểm right
edge/child bounds. Vì vậy clear_frame=true trong manifest không chứng minh
header không bị cắt. Không sửa raw flags hay xóa ảnh lỗi.

Next small iteration: dừng thêm chức năng reader; bảo đảm header/control nằm
trọn trong tờ ở 520/700px, giữ ảnh lỗi trước/sau. Sau đó chỉ làm nguồn trang
và đoạn cắt theo `rat_information_evidence_design_20261024.md`. Không chữa
overflow bằng cách ép window rộng/lớn hơn quy tắc production. Chưa cần model
để kiểm các thay đổi layout này.

## Follow-up — bàn giao sửa header

Đã đọc source mới và hai ảnh được bàn giao trong
`~/.gemini/antigravity/brain/c521fb94-cdbc-4b76-8354-89e731c844c7/`:

- `turn3_fixed_520px.png`: 1040×590, RGBA, một màu duy nhất (0,0,0,0).
- `turn3_fixed_700px.png`: 1400×1140, RGBA, một màu duy nhất (0,0,0,0).

Hai ảnh hoàn toàn trong suốt, không chứa UI; view_image hiển thị nền đen.
Không dùng chúng để xác nhận “sau sửa đạt 100%”. Giữ nguyên ảnh làm bằng chứng
lỗi capture, không tô nền hoặc retouch để biến chúng thành ảnh nghiệm thu.

Chạy lại đúng `test_header_controls_bounds_and_mode_instructions`: 1 passed
in 3.32s. Probe tạm thêm điều kiện copy_right <= fold_left tại 520/700px:
1 passed in 3.75s. Không tái hiện overlap trong trạng thái test này; số liệu
trong báo cáo không thay thế kết quả probe. Chưa chạy lại toàn bộ 68 tests.

Code đã chuyển breakpoint sang resultPaper.width, giới hạn label/control,
ẩn reader controls phụ ở tờ hẹp và chỉ hướng dẫn bôi chọn trong text mode.
Có tiến triển phần hình học; chưa chốt visual acceptance khi ảnh vẫn rỗng.

Next duy nhất: sửa/kiểm cơ chế capture, đợi frame thực vẽ và kiểm ảnh có nội
dung trước khi bàn giao. Chụp lại 520/700px với PDF thật có provenance/hash,
nhìn trực tiếp ảnh, báo đúng software/component hay desktop acceptance.
Không thêm reader hoặc chuyển sang UX nguồn trước khi đóng lỗi ảnh trống.
Review chỉ đọc/test; không điều khiển Antigravity, không gọi model, không sửa
product source.

## Follow-up — ảnh software renderer đã có nội dung

Mở lại hai PNG bàn giao 520/700px: hiện đã có UI, cả Chép và Thu gọn nằm
trọn trong header; không thấy chồng/cắt hai nút ở các trạng thái này. Đóng
lỗi ảnh rỗng cho hai capture mới và chấp nhận sửa layout header trong phạm
vi ảnh. Chưa xác minh nguyên nhân Metal/cache; backend software là điều kiện
capture được báo cáo, không chứng minh backend mặc định đã ổn.

UX vẫn thiên về reader: số trang xuất hiện nhiều lần, toàn trang chiếm gần
hết tờ và nội dung cần tìm bị đẩy xuống/che bởi composer. Bước nhỏ tiếp theo
là thu gọn metadata nguồn theo rat_information_evidence_design_20261024.md;
chưa phát triển reader hay crop mới trong cùng lượt.

Run 31 là scenario phần mềm, chưa đủ nghiệm thu hội thoại thật: manifest có
calls=[] và answer_excerpt được gán trực tiếp trong
scripts/run_rat_quick_ui_session.py (câu BEST-Route/VRP), rồi gọi
openAnswerSource(0). Không dùng câu đó làm bằng chứng câu trả lời của model
hoặc nội dung bài báo. Ảnh vẫn hữu ích kiểm bố cục; lượt kiểm 0 model nên dùng
luồng PDF/search thật thay vì gán câu trả lời mẫu.

## Review Build .11 — metadata nguồn

Đã mở ảnh turn3_metadata_after_520px.png và turn3_metadata_after_700px.png
trong artifact directory bàn giao. Tiêu đề Nguồn · Trang 1/25 và tên tệp phụ
gọn hơn, footer bỏ số trang, Copy/Thu gọn vẫn hiện trọn. Chấp nhận phần trình
bày metadata trong hai ảnh. Toàn trang vẫn chiếm vùng chính; ở 700px abstract
tiếp tục đi xuống vùng fade trên composer. Chưa đạt UX tra thông tin/đoạn nguồn.

scripts/verify_rat_metadata_ui.py dùng PDF/search thật và không gán câu trả
lời mẫu, có tiến bộ so với run 31. Tuy nhiên script gọi controller trực tiếp,
setProperty cho draft/min/full và grabWindow: đây là kiểm thử tích hợp/render,
chưa phải thao tác người dùng qua desktop. Sửa cách mô tả "qua UI" và "bảo
toàn tuyệt đối" trong bàn giao; không suy rộng từ các trạng thái đã thử.

Chạy test_source_metadata_title_and_composer_footer_presentation cùng
tests/test_quick_unified_flow.py bằng software backend: 12 passed, 2 failed
in 7.64s (chạy ngoài sandbox sau khi Qt import abort trong sandbox).
Metadata test pass; hai test unified fail ở expanded=False thay vì True và
copyCitation bị ẩn. Chưa xác định regression hay kỳ vọng test cũ; không quy
lỗi cho diff metadata. Bộ 69 test được báo cáo không gồm unified flow; không
coi đó là toàn bộ quick acceptance. Không chạy model hoặc sửa product source.

## Review Build .12 — Đoạn khớp

Đã đọc bàn giao, controller/QML, verify_turn4_matched_excerpt.py và mở ảnh
matched 520/700px. Thông tin nguồn thật và keyword highlight đã lên trước
toàn trang: đúng hướng. 520px vẫn cắt tiêu đề từ khóa và phần cuối excerpt
nằm dưới vùng fade; xuống dòng cứng từ PDF tạo nhiều dòng ngắn ở cả 700px.

Hai điểm cần sửa trước khi chốt hành vi Copy:

- copyReady là yêu cầu mang dữ liệu, chưa phải xác nhận clipboard: controller
  emit rồi QML hiện Đã chép. Production có connect tới clipboard.setText,
  nhưng script/test matched mới chỉ connect tới list, không nối clipboard.
  Vì vậy ảnh Đã chép không chứng minh OS clipboard đã cập nhật. Cần đọc lại
  clipboard trước báo thành công và kiểm clipboard thật trong nghiệm thu.
- requestCopy đọc selectedText của matchedExcerptText/pageText mà không ràng
  buộc chế độ/visibility; persistentSelection giữ vùng chọn khi đổi mode.
  Cần chỉ lấy vùng chọn từ chế độ đang hiển thị, tránh chép vùng chọn ẩn.

verify_turn4 vẫn setProperty draft/expanded, controller.search/readPage và
ép chiều cao tối thiểu 720 trước click hit. Đây là test tích hợp/render,
chưa thay thế thao tác desktop với kích thước production. Không gọi model.

Chạy test matched mới cùng unified flow: matched pass (dấu .), sau đó process
segfault exit 139 tại fixture quick_env của unified. Không kết luận pass toàn
bộ khi ghép; cần ghi nhận crash và phân biệt kết quả chạy từng file.
Chạy riêng tests/test_quick_unified_flow.py: 13 passed in 6.41s, xác nhận hai
ca sửa kỳ vọng min/full đã qua trong lần chạy riêng này.

## Review Build .13 — bỏ switcher

Mở ảnh work/turn4_evidence/turn4_matched_excerpt_520px.png và bản 700px:
switcher đã bỏ, từ khóa hiện đầy đủ, nguồn/chép đoạn rõ hơn. Source QML chỉ
lấy vùng chọn matched đang visible; clipboard ghi rồi đọc lại, QML nhận
copyConfirmed thay vì copyReady. Chạy riêng tests/test_quick_pdf.py bằng
software backend: 11 passed in 7.25s. Không gọi model hoặc sửa product source.

Vẫn còn cụm lật/nhập số trang trên header dù luồng chính chỉ đọc đoạn khớp;
chuyển sang trang không có hit đưa người dùng vào fallback rỗng. 700px còn
hai hành động mở PDF gốc: icon trên header và nút có nhãn cạnh metadata.
Next nhỏ: ở luồng nguồn từ search, chỉ giữ Quay lại kết quả, Chép đoạn, Thu
gọn trên header và một Mở PDF gốc cạnh metadata; không biến điều hướng này
thành next/prev reader. Chưa thêm tính năng mới.

Giới hạn nghiệm thu vẫn còn: script setProperty/call controller/QTest; phần
mở PDF ngoài thay _open_url bằng lambda trả True, chỉ kiểm yêu cầu mở và giữ
draft, chưa chứng minh app ngoài thực sự mở. openOriginal chỉ gửi file URL,
chưa nhảy tới trang. Không gọi đây là thao tác desktop thật hoặc mở đúng
trang đã xác nhận. Nguyên nhân crash khi ghép Qt suite chưa được chứng minh;
không kết luận chắc là xung đột luồng nền chỉ từ việc chạy riêng pass.
