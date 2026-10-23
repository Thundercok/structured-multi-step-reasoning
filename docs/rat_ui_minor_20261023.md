# RAT Quick — minor polish, 2026-10-23

Tiếp tục UI Quick hiện tại theo phạm vi minor changes trong
`rat_cot_end_to_end_next_20261022.md`. Đã đọc báo cáo polish/execution flow
2026-10-21, PDF/ADR-005 và bàn giao hợp nhất hiện hành trước khi sửa.

Chỉ sửa `rat/ui/quick/PDFDesk.qml`:

- Hàng Finder chưa chọn dùng nền giấy hiện có, giảm các mảng xanh cạnh nhau;
  hàng chọn giữ nền, viền và thanh đánh dấu hiện có.
- Căn trái nội dung hàng cố định 10 px, tránh chữ dịch khi đổi selection.
- Badge App dùng cùng kiểu nhãn phụ PDF/Tệp; gợi ý Enter dùng nền nhạt.
- Bỏ đường giả nổi dưới keycap, giữ nhãn và thao tác.
- Rút gọn phụ đề AI thành “Gửi câu hỏi này cho trợ lý”, giới hạn trong cột.
- Dãy phím tắt Finder tự xuống dòng khi hẹp thay vì bị cắt mép phải.

Giữ Chuột, lớp giấy, composer, palette, kích thước cửa sổ và hợp đồng thao tác.
Dãy phím tắt có thể tăng chiều cao nội dung ở cửa sổ hẹp theo cơ chế fit sẵn có.
Không đổi backend, reasoning, research harness hoặc launcher/packaged app.

## Kiểm tra

`QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software QT_QUICK_CONTROLS_STYLE=Basic .venv/bin/python -m pytest tests/test_quick_pdf.py tests/test_quick_finder_flow.py tests/test_quick_unified_flow.py -q`

Kết quả sau sửa cuối: **28 passed in 25.75s**.
`git diff --check -- rat/ui/quick/PDFDesk.qml` đạt.

`work/rat_ui_minor_20261023/render_comparison.py` render 12 ảnh từ source trước
và sau, cùng fixture Finder/AI ở 700 px sáng, 520 px sáng/tối: không QML warning.
`comparison.png` ghép trước/sau 520 px; `comparison.json` ghi danh sách ảnh.
Bản trước lấy từ HEAD khi UI file chưa có thay đổi riêng. Script capture showcase
cũ cũng đã chạy, nhưng thư mục `after/` là mốc trước sửa xuống dòng cuối;
ảnh `after-finder-*.png` ở thư mục gốc mới là mốc cuối của gói này.

Đây là fixture/offscreen, không phải native macOS acceptance hay bằng chứng chất
lượng model. Không gọi model thật trong kiểm tra. Qt phải chạy ngoài sandbox
vì sandbox nhận diện thiếu NEON. Có thông báo font alias từ môi trường Qt;
không ghi nhận QML warning. Các thay đổi từ chat khác được giữ nguyên.

## Gói đồng nhất sau khi người dùng duyệt minor fixes

Người dùng yêu cầu triển tiếp và đồng nhất UI. Dùng skill `design-system` để
đối chiếu cách hiển thị đang có; triển khai trong cùng `PDFDesk.qml`.

| Vai trò chung | Thành phần dùng chung |
| --- | --- |
| `selectedSurface`, `selectedEdge` | Finder, gợi ý AI, Apps, chip tài liệu |
| `utilitySurface` | Thanh thao tác Finder/Apps, Apps empty state |
| `hoverSurface` | Nút chữ, nút icon, ô Apps |
| `keySurface`, `keyEdge` | Các phím tắt hiển thị |
| `cardRadius` / `controlRadius` | Thẻ nội dung / nút và thanh thao tác |

- Giữ palette giấy/sage; giảm các biến thể màu gần giống nhau.
- Nút chữ và icon có trạng thái hover/nhấn/disabled nhất quán; nút chính giữ
  màu accent, nút phụ dùng nền nhẹ. Vòng focus hiện có vẫn giữ.
- Keycap chính dùng cùng accent với các thao tác chính khác.
- Tiêu đề các phần live dùng 16 px Medium; body, metadata và composer giữ cỡ cũ.
- Bôi chọn trong editor dùng cùng màu với answer/PDF.
- Apps dùng cùng cách xuống dòng phím tắt như Finder. Tên app giữ vùng riêng,
  đường dẫn phụ nhường chỗ trước; ở cửa sổ hẹp, thẻ có thể cao thêm một dòng.

Kiểm tra cuối: cùng ba bộ Qt ở trên và
`tests/test_turn3_apps_grid_and_auditor_hardening.py`: **40 passed in 24.92s**.
Đây gồm kiểm tra hành trình UI và các hợp đồng/controller sẵn có; không phải
40 kiểm tra thẩm mỹ hoặc native acceptance.

`work/rat_ui_consistency_20261023/` giữ source trước lượt đồng nhất, script,
`comparison.json`, 40 ảnh trước/sau của Finder, AI, Apps, answer, PDF ở
520/700 px sáng/tối và `surfaces.png` để so các phần cạnh nhau. Apps dùng icon
placeholder trong fixture này; không thay icon native của sản phẩm. Không QML
warning; vẫn có thông báo font alias của môi trường Qt. Đã xem trực tiếp ảnh
Apps hẹp/rộng, PDF và answer. Không gọi model hay mở ứng dụng ngoài.

Hash SHA-256 của QML được kiểm tra:
`d4d3f7aeb1912162c01f5e8b7ca41fa45e7a284215a4e88f7cdbe6c7aedfc9e0`.
`git diff --check -- rat/ui/quick/PDFDesk.qml` đạt. Không đổi runtime/research,
không rebuild bundle hoặc thay bản app đã cài; phần source đã được cập nhật.

## Gói hoàn thiện bố cục và selector — đã triển khai theo kế hoạch được duyệt

Người dùng chấp thuận `rat_ui_minor_next_20261023.md` và yêu cầu sửa selector
cùng lượt. Thay đổi tiếp trong cùng `PDFDesk.qml`:

- Header/nội dung và phần cuối giấy gọn hơn: phần bù chiều cao live 96 → 80 px,
  khoảng đầu vùng đọc 58 → 48 px, nhịp nội dung 13 → 10 px. Dòng nhật ký nhẹ
  hơn, bỏ separator và hàng trống không có thao tác tìm tiếp.
- Apps giữ một tiêu đề/số lượng; bỏ nhãn và hướng dẫn lặp. Copy ở header trở
  thành nút phụ; nút gửi trong composer vẫn là thao tác chính.
- Finder dành hàng riêng cho tên tệp, tối đa hai dòng; metadata là text nhẹ.
  Bỏ badge và gợi ý Enter/Hỏi lặp; icon thao tác nằm hàng metadata, có chỗ dự
  trữ để việc đổi selection không làm nội dung dịch ngang hoặc đổi chiều cao.
- Selector Finder/Apps dùng nền nhẹ và viền bo liên tục. Bỏ vạch dọc Finder,
  thanh ngang Apps chạm mép góc, viền ô chưa chọn và đổi font weight theo chọn.
- Toolbar bớt khung nền, rút nhãn ở chiều rộng nhỏ. Cả Finder/Apps vẫn giữ đủ
  lệnh; bản 520 px với dữ liệu đã thử không còn hàng phím tắt rơi lẻ.
- Giữ geometry/anchor composer, artwork và kích thước Chuột, lớp giấy lệch,
  draft/selection, runtime và launcher. Thẻ kết quả co theo nội dung ít chrome
  hơn; không chuyển vị trí composer trong cùng cửa sổ.

Kiểm tra sau sửa source cuối: **40 passed in 32.75s** với bốn bộ Qt/hợp đồng
đã nêu ở mục trên. `git diff --check -- rat/ui/quick/PDFDesk.qml` đạt.
SHA-256 source: `f4bbb45f81f91dc64c52c006bbd504168aa99038ce2e7d1e2e0c7bffd2f749a1`.

`work/rat_ui_finish_20261023/` giữ source trước lượt này, script/ảnh trước/sau,
icon native Apps, tên tệp dài tiếng Việt, Apps lọc/rỗng, answer ngắn/dài, PDF,
idle ở 520/700 px sáng/tối. `review.png` ghép Finder trước/sau và Apps sau.
Dữ liệu tự soạn; không gọi model thật. Screenshot không chứng minh chất lượng
suy luận hay hiệu năng.

### Kiểm native có giới hạn

Đã mở đúng source QML trong cửa sổ Python/Qt native 520 px, xem selector và tên
hai dòng; qua CUA thực hiện Down trong Finder, vào Apps, xóa bộ lọc, focus ô
nhập và Right (Calculator → Safari), rồi Escape. Accessibility xác nhận draft
`Bản nháp UI` khôi phục. Đã đóng fixture. Không mở app ngoài hay model.

Lần native đầu có fixture catalog thiếu alias, gây `min() iterable argument is
empty` khi gõ; đây là dữ liệu test tự dựng. Đã sửa alias và cấu hình DB tạm
riêng trong script native, chạy lại hành trình nêu trên. Không sửa resolver.
Native Qt có thông báo font alias/Cocoa keymapper/IMK trong quá trình dùng CUA;
không gọi đây là acceptance IME hoàn chỉnh. Một lần đọc AX timeout, lần ảnh AX
và screenshot không đồng thời được lấy lại bằng screenshot mới trước khi đánh
giá hình ảnh. Chưa kiểm nhiều màn hình, IME toàn diện, bundle hay app đã cài.

Render cuối hoàn tất **80 captures, không QML warning**; script còn xác nhận
filename thông thường không truncated, vị trí/kích thước tên giữ nguyên khi
chuyển selection và hai toolbar chỉ một hàng ở 520 px trong hai theme.
Lần bổ sung assertion đầu tìm QObject không thấy visual delegate; đã sửa script
đi qua `childItems()` và chạy lại thành công, không thay source sản phẩm.

## Lượt tiếp: toolbar nhẹ, chữ phụ và chatbar

Theo yêu cầu “tiếp theo là gì? implement và tiếp tục”, tiếp tục trên cùng UI:

- `KeycapBadge` trở thành Button: tên thao tác đứng trước, shortcut là text phụ,
  bỏ ô keycap viền riêng. Nút chính dùng nền chọn nhẹ; hover, pressed, focus và
  disabled rõ. Qt accessibility nhận diện là button; có thể focus và Space.
- Header chuyển sang chữ thường; Finder một nhóm không lặp nhãn nhóm. Mixed
  Finder vẫn giữ heading nhóm để phân biệt tệp/ứng dụng.
- Placeholder ngắn vừa 520 px; footer dùng “Kéo thả PDF”, bỏ nhãn offline tĩnh
  trong UI chung. Nút Apps giữ tên “Ứng dụng” và nền active khi ở mục Apps.
- Menu PDF giữ thao tác cũ với nhãn “Tài liệu”; tên PDF đầy đủ vẫn ở chip,
  nội dung/popup và accessible name. Nút hỗ trợ elide để tên dài không kéo footer.
- Thẻ hỏi AI bỏ vạch nhấn và khung icon phụ, dùng lời gợi ý ngắn.

Không đổi artwork/size Chuột, palette, lớp giấy, vị trí composer hoặc backend.

Kiểm tra cuối: **41 passed in 31.37s** với bốn bộ đã nêu. Kiểm tra mới trong
`tests/test_quick_finder_flow.py` focus nút mở app rồi dùng Space, xác nhận đúng
URL fixture và draft phục hồi; opener ghi nhận tại chỗ, không launch app thật.
Bộ 40 tests ban đầu cũng đạt trước khi thêm test này.

`work/rat_ui_readability_20261023/` giữ baseline trước lượt, 80 ảnh 10 trạng
thái × 2 widths × 2 themes × trước/sau, native icons Apps, script và hash.
Không QML warning; assertions tên không truncated, selection không làm đổi
hình học tên và toolbar hẹp một hàng đều đạt. Đã xem ảnh Finder, Apps, idle,
PDF dark và AI; đã mở đúng source native bằng DB/catalog fixture để xem lại
Finder. AX xác nhận các action button mới và accessible names. Lần đóng bằng
shortcut CUA báo foreground thay đổi; đã bind lại đúng fixture và đóng bằng
nút ×, không tác động cửa sổ khác. Có thông báo font alias từ Qt như các lượt
trước. Chưa kiểm IME toàn diện, nhiều màn hình hoặc đóng gói.

SHA-256 QML cuối:
`4124e8a5196ac48031f3e4c1b5bbfca1a6c5adb34858968f78f1295c63cefae5`.
`git diff --check` cho QML và file test đạt. Bản app đã cài chưa rebuild.

## Bỏ thẻ gợi ý AI theo phản hồi người dùng

Đã xóa toàn bộ `smartAiCard` khỏi QML, không thay bằng thẻ khác. Giữ đường
Enter/nút gửi → `search()` → `submit()` hiện có khi không chọn tệp PDF; khi
đang chọn PDF vẫn tìm nội dung PDF theo hợp đồng cũ. Không đổi routing/model.
Đã đổi tên/caption cảnh capture tương lai thành `03b_composer_question.png`;
không sửa/xóa ảnh lịch sử đã lưu.

Kiểm tra liên quan: `tests/test_quick_unified_flow.py` và
`tests/test_quick_finder_flow.py`: **23 passed in 25.70s**. Script trong
`work/rat_ui_no_ai_card_20261023/` render 16 ảnh Finder có/không kết quả ở
520/700 px sáng/tối, không QML warning; geometry/toolbar assertions đạt.
Đã xem ảnh no-results 520 px sau sửa. Không gọi model thật, chưa rebuild app.
SHA-256 QML:
`637ffda9e652f9377d8c0438c7bc328909bbf41015e851861f70d6c281e8b045`.

## Ưu tiên tiếp theo — đề xuất sau khi bỏ thẻ

Chỉnh surface câu trả lời/nguồn trong chính tờ giấy hiện tại:

1. Phân cấp câu trả lời dài, đoạn, danh sách và code; giữ copy toàn văn và
   selection, không biến nội dung chưa verify thành kết luận đã kiểm chứng.
2. Nút `openPdfCitation` hiện chỉ dựa vào `fileName` rồi gọi
   `jumpToPdfPage(1)`. Cần tách nghĩa “mở tài liệu đang chọn” với nguồn trích
   dẫn có source/page thật. Chỉ định vị trang khi public evidence có page ref
   hợp lệ; không gọi selected PDF là nguồn đã chứng minh cho câu trả lời.
3. Dùng public execution state cho working/completed/cancelled/error; giữ
   loading nhẹ, không tạo tiến trình hoặc thao tác giả. Kiểm draft, cuộn,
   nguồn và copy trên cùng bộ nội dung dài/ngắn.

Đây là kế hoạch tiếp theo, chưa triển khai ba mục trong lượt bỏ thẻ. Phạm vi
vẫn minor changes; giữ Chuột, lớp giấy, composer, palette và runtime chung.

Sau khi xem ảnh no-results, đã ẩn toàn bộ container Finder khi không có hits
để bỏ implicit height còn giữ từ danh sách trước. Không thêm nội dung gợi ý.
Ảnh cuối 520 px cho thấy giấy co về thông báo ngắn, nhật ký và composer.
Kiểm tra lại: **23 passed in 24.29s**, 16 captures không QML warning.
Hash source cuối lượt bỏ thẻ:
`7542341ea0785e501f599732ff4dd65b78cb78bdd359bb194eacb6024df76de6`.

## Câu trả lời, tham chiếu và icon — source cuối đã kiểm tra

Người dùng yêu cầu thực hiện gói câu trả lời/nguồn và sửa icon; sau đó yêu cầu
tiếp tục vì chưa thấy thay đổi đủ rõ. Đã hoàn thiện trong cùng UI Quick:

- `DeskIcon.qml`: một lưới SVG 24, stroke 1.7, bo đầu nét, màu theo theme;
  dùng cho tệp/PDF, xem nhanh/Finder, gửi/dừng, chép/check, đóng/thu, mũi tên,
  dropdown và tăng/giảm trang. Không dùng chữ nhỏ trong SVG PDF hoặc glyph font
  làm icon thao tác. Icon app vẫn qua native provider. Component là file local
  trong thư mục Quick đã được `rat.spec` thu thập; chưa build bundle.
- `answer_presentation.py`: formatter giới hạn cho đoạn, heading, chữ đậm,
  inline code, danh sách và fenced code. Khoảng dòng/đoạn rõ hơn; code có nền
  riêng sáng/tối. Raw HTML, link và ảnh trong nội dung không trở thành resource
  hoặc hành động tự động. Đây không phải renderer Markdown/LaTeX đầy đủ.
  Copy toàn văn giữ nguyên câu trả lời gốc; bôi chọn dùng nội dung hiển thị.
- Bỏ nghĩa “PDF đang chọn = nguồn trích dẫn”. `Mở tài liệu` mở picker, không
  tự đọc trang 1. Tham chiếu lấy từ public `AgentResponse.sources`, lưu trên
  `TurnSnapshot.source_refs` và đi theo lượt đang hiển thị, kể cả lookback.
- `Đọc trang N` chỉ bật khi ref có số trang nguyên hợp lệ và path khớp PDF
  đang chọn; thiếu trang không suy ra trang 1. PDF khác/chưa chọn và nguồn
  ngoài PDF hiện chỉ hiện metadata, không có resolver mở mọi loại nguồn.
  Việc mở trang không chứng minh ref hoặc câu trả lời đúng; kiểm stat stamp
  hiện có không phải cơ chế xác minh durable revision của mọi nguồn.
- `answer_verification_status` lưu theo lượt, mặc định UNKNOWN; UI chỉ báo
  PASS/FAIL theo trạng thái runtime thực sự trả về, không suy từ đính kèm PDF
  hoặc heuristic auditor pass. Status metadata bớt nổi; source/answer có thể
  đọc và copy trong cùng desk.
- Các kết quả timeout/quota/unresolved được ghi vào lịch sử với trạng thái
  failed hợp lệ, cancelled vẫn là cancelled. Trước đó bridge truyền các tên
  mà `fail_turn` không nhận rồi bắt exception, có thể để snapshot in_progress.
  Đây là sửa hợp đồng ghi trạng thái, không đổi routing/stopping hoặc quota.

### Validation và source identity

Lần cuối `validate_final.py`: **77 passed in 18.78s**. Gồm presentation/source,
PDF, Finder, unified flow, Apps contracts, chat session và conversation lifecycle.
Kiểm tra mới bao gồm không tạo HTML resource/link, copy raw answer, ref thiếu/
sai trang, mở đúng trang 2, nguồn theo lượt cũ, callback stale và trạng thái
incomplete. Test theme tối kiểm màu code trên document thực; test footer kiểm
menu tài liệu không kéo rộng. Test unified đọc plain text từ rich document
thay vì so HTML serialization với raw answer; cancel dùng nút QML thật.

`work/rat_ui_answers_icons_20261023/final-tests.json` ghi lệnh, return code và
hash trước/sau cho QML, icon, bridge, history, formatter và tests. Source giữ
nguyên trong run. `capture-final.json` xác nhận ảnh cuối dùng đúng các hash đó.
QML cuối: `283520cbdd93b414e6125e1b2fd0405695fb5de14e1e7bf8524bf4783dbe36e8`.
`git diff --check` cho các file đã sửa đạt.

Artifacts trong cùng thư mục: 80 captures ở 520/700 px sáng/tối, bảng icon,
`answer-sources-light.png`, `answer-sources-dark.png`, `source-page-two.png`,
`review-final.png`, script và raw stdout/stderr cuối. Gallery không QML warning;
Qt có thông báo font alias trong môi trường. Nội dung/PDF là fixture tự soạn,
không gọi model thật, không đo chất lượng model/latency/chi phí inference.

Đã mở source native với PDF fixture, xem định dạng/icon và dùng CUA bấm
`Đọc trang 2`; AX xác nhận trang 2 cùng đúng nội dung tự soạn. Đã đóng fixture.
Native review diễn ra trước chỉnh bố trí footer cuối; bố trí/theme source cuối
đã kiểm Qt offscreen và geometry assertions, chưa nghiệm thu đầy đủ IME,
accessibility, nhiều màn hình, motion hoặc packaged app.

### Các lần thử không được tính là pass

- Ban đầu component Image dùng implicitHeight read-only: smoke bắt lỗi, đã
  chuyển sang width/height và kiểm lại. Test cỡ chữ cũng được sửa để đọc pixel
  size của font CSS thay vì point size.
- Một run ghép đầu SIGSEGV ở Qt khi bắt đầu module PDF sau module mới. Fixture
  mới nay giữ QApplication sống xuyên module; các run riêng và hai run ghép
  sau đều pass. Không kết luận đã xác định chắc nguyên nhân mọi crash native.
- Các assertion cũ so raw text/biểu tượng stop font được chuyển sang kiểm nội
  dung người dùng đọc và hành vi cancel thực; không bỏ kiểm contract.
- Có các dòng QML đổi lại trong checkout chung khi review; snapshot quan sát
  đã giữ riêng. Đã áp lại đúng phần chỉnh UI của lượt này và thêm hash guard.
- Bộ duyệt tự động từng không chạy test/render vì usage limit. Sau yêu cầu
  tiếp tục, cùng đường duyệt đã cho chạy thành công; không dùng đường bỏ qua.

Không sửa các thay đổi nghiên cứu của chat khác, harness/Stage 0, model setup,
launcher hoặc bản app cài sẵn. Không push/commit trong lượt này.
