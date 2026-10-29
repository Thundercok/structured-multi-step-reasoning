# RAT Lite .28 — overhaul UX quanh Chuột và bubble

**Generated design direction:** người dùng bổ sung ba ảnh tham chiếu; xem
[mascot, thẻ trạng thái và Workbench](rat_lite_28_generated_design_direction_20261029.md).
Bổ sung ưu tiên Chuột toàn thân ngồi trong storyboard và Workbench ba vùng công
khai; giữ các rule tương tác, không Copy CTA và shared reasoning tools.


**Interaction revision:** sau phản hồi “chưa convinced”, xem
[phản hồi → hỏi ngay → hội thoại](rat_lite_28_interaction_revision_20261029.md).
Revision này thay thế rule click/selection, activation chat và source/referent
ở plan ban đầu: input không tự là chat, đọc rộng không tự là transcript.


Trạng thái: **kế hoạch**, chưa triển khai overhaul, chưa build/test/launch. Source
`c8192972` mới là correction đầu tiên: Chuột lớn hơn, bubble bớt chrome và bỏ
nút Sao chép. Không coi correction đó là đã giải quyết toàn bộ UX. Bản được mở
lần gần nhất là .27; chưa có acceptance cho source .28.

## 1. Vấn đề và hướng thiết kế

Feedback thật: gõ, đọc và mở rộng còn rời rạc; nhiều lần sửa xong vẫn khó dùng;
.27 thu Chuột nhỏ hơn điều người dùng muốn. Ảnh tham chiếu Safari thể hiện một
nhân vật có mặt rõ cạnh đoạn đang đọc và một bubble nhỏ. Người dùng đã bỏ nút
Sao chép khỏi thiết kế. Đây là hướng bố cục, không phải yêu cầu sao chép asset
hay lời xác nhận screenshot đó là UI RAT đang chạy.

**Một nhân vật, một bubble biến đổi, một luồng công việc.** “Gọn” là giảm phần
UI phải đọc và điều khiển, giữ nhân vật dễ nhận ra. “Magical” đến từ đúng vị trí,
giữ đúng ngữ cảnh, phản hồi rõ và ít thao tác.

Các khả năng của roadmap 20 mục vẫn thuộc phạm vi đã duyệt. .28 tổ chức lại cách
truy cập chúng; không thêm một đợt capability mới vào bản overhaul UX.

## 2. Kết quả mong muốn

Các tiêu chí sau là mục tiêu nghiệm thu được đề xuất, chưa phải số đo đã đạt:

- Selection → phím tắt: một gesture để gọi; không chọn mode hoặc gửi lại chữ.
- Từ kết quả sang hỏi tiếp: một click vào Chuột, nhập rồi Enter; không mở Settings.
- Bubble đọc bình thường: nội dung và một nút đóng; không nút Sao chép,
  thanh tiêu đề, provider hoặc hướng dẫn thường trực.
- Đóng bubble, đổi extent và quay lại: không mất nguồn, draft hoặc vị trí đọc;
  một thao tác không dispatch lại công việc ngoài ý muốn.
- Hoàn tất khi đang ẩn: không mở lại cửa sổ hoặc lấy focus.
- Kết quả chưa đầy đủ/lỗi/nguồn đã sửa luôn được phân biệt với kết quả hoàn tất.

## 3. Bố cục: nhân vật trước, nội dung sát ngữ cảnh

### Chuột

Dùng artwork đầu Chuột hiện có. Baseline source .28 là host112px, optical target88px;
coi đây là điểm bắt đầu cho review thị giác, chưa phải kích thước được nghiệm thu.
Giữ nhân vật rõ mặt và cùng cỡ ở idle, working, đọc và expanded. Không đổi size
vì nội dung dài/ngắn. Cân tỷ lệ bằng vùng hình thực sau khi render, không bằng
transparent canvas của PNG.

Bố trí Chuột ở góc ngoài bubble, miệng sát mép/tail như đang nói cùng người đọc;
ưu tiên cùng vùng trống cạnh selection. Tail ngắn, không kéo một mũi nhọn dài
xuyên qua chữ. Tránh cả head lẫn bubble đè lên selection nếu work area còn chỗ.
Chưa thêm pose/asset mới trong scope bắt buộc.

### Bubble đọc

- Bề rộng khởi điểm khoảng240–320 logical px, chọn theo nội dung và chỗ trống.
  Đây là dải thiết kế cần review, không phải lý do ép mọi câu vào cùng khung.
- Một câu ngắn có chiều cao theo chữ; bỏ working-height floor khi có kết quả.
  Nội dung dài cuộn trong ngân sách compact, không tự bung cửa sổ lớn.
- Text16px, line-height dễ đọc; không giảm font để nhét nội dung.
- Không copy CTA, title/status lặp hoặc footer rỗng. Close nhỏ có hit target đủ
  dùng và phần đệm riêng; không đè chữ hoặc cắt thanh cuộn.
- Provider, ngôn ngữ, nguồn gốc và kiểm chứng ở chi tiết. Partial, dirty-source
  và lỗi có một dòng thông báo ngắn ngay cạnh nội dung liên quan.
- Expanded tiếp tục cùng reader/editor; không sinh một cửa sổ hoặc mascot khác.

### Khung nhập

Click Chuột mở ô nhập gắn ngay với bubble đang đọc. Một field và một Send khi
có nội dung; không hàng mode hoặc attachment toolbar luôn hiện. Kéo/thả/dán ảnh
vẫn hoạt động và có preview theo nhu cầu.

Chỉ khi đang hỏi về nguồn đã giữ, hiện một context chip nhẹ **“Về đoạn này ×”**.
Chip cho biết câu hỏi sẽ dùng nguồn nào; × bỏ ràng buộc nguồn cho yêu cầu mới,
không xóa nguồn hay kết quả đang đọc. Đây là thông tin ảnh hưởng hành động,
khác với metadata kỹ thuật. Thiếu referent thì hỏi một câu trong luồng.

## 4. Hợp đồng tương tác

Các tên dưới đây là trạng thái nhìn thấy của cùng một surface, không phải mode
nghiệp vụ hoặc bộ state machine thứ hai.

| Trạng thái | Thấy gì | Focus và hành động |
| --- | --- | --- |
| Idle | Chuột; không bubble trống | Click Chuột → nhập. Tray recall cũng về đúng task/idle. |
| Capturing | Phản hồi ngắn tại Chuột khi thực sự nhận intent | Giữ source PID/focus cho tới khi capture xong; không hiện form lớn. |
| Working | Một dòng tiến độ công khai ở cùng anchor | Không tự focus editor; có Stop trong menu khi cần. Draft tiếp theo được giữ riêng. |
| Reading | Bubble nội dung + Close | Nguồn app vẫn có focus cho tới khi người dùng click vào RAT. |
| Composing | Reader vẫn ở đó, field bên cạnh/dưới nó | Click Chuột hoặc chọn Hỏi tiếp mới focus input. Enter gửi; Shift+Enter xuống dòng. |
| Expanded | Cùng nội dung trong vùng đọc rộng | Giữ text selection, reading anchor, source và draft; collapse quay về anchor compact. |
| Partial/error | Nội dung đã có + lý do ngắn + một recovery phù hợp | Không thay toàn bộ kết quả bằng thông báo chung hoặc báo thành công giả. |
| Hidden | Không surface; dữ liệu task còn | Tool hoàn tất chỉ cập nhật task. Recall là hiển thị, không chạy lại. |

### Quy tắc đóng và quay lại

- **Close trên bubble:** gập bubble về Chuột, giữ công việc. Không đóng app.
- **Esc:** đóng popup trước; đang nhập thì cất input và giữ draft; đang ở subview
  thì quay lại; đang đọc thì gập về Chuột. Lệnh Ẩn RAT trong menu/tray ẩn toàn bộ.
- **Click ngoài:** bubble transient gập về Chuột; đã ghim thì giữ bubble. Không
  đồng nhất đổi app/focus với một click ngoài thật.
- Không gọi lại kết quả sau Close chỉ vì worker trả về muộn. Một click vào
  Chuột gọi lại nội dung/input theo intent rõ, không resubmit.
- Ghim là theo task, có dấu hiệu nhẹ ở menu/tooltip. Close/Esc luôn dùng được.

Hiện `hideRequested` đang ẩn cả overlay ở nhiều nơi. Overhaul cần phân biệt
`collapse_to_character`, `hide_overlay` và `quit`, cùng generation/presentation
intent guard. Không sửa bằng cách đổi nhãn Close trong QML.

### Chuột, phím tắt và clipboard

- Click: toggle input, không capture hay gọi model.
- Drag: chỉ đổi vị trí của task hiện tại. Kết thúc drag không phát sinh click.
- Chuột phải: menu theo ngữ cảnh. Không gán double-click thêm tác vụ vì dễ
  xung đột với chọn chữ/drag.
- Phím tắt từ app khác: capture mới chủ động. Trong RAT: recall theo hợp đồng
  hiện có; không lấy chữ của chính editor làm nguồn ngoài.
- Busy: giữ công việc hiện tại và draft; phản hồi ngắn tại Chuột nếu overlay
  đang thấy. Nếu RAT đang ẩn, có thể dùng badge tray. Tránh notification lặp.
- Copy ngoài app không kích hoạt tool hoặc mở bubble. Watcher vẫn tùy chọn.
- ⌘C copy selection thật; menu ngữ cảnh có Copy toàn bộ khi người dùng cần.

## 5. Hỏi tiếp và đổi công việc

Sau bản dịch, “giải thích câu cuối” phải giữ source_ref/revision. Từ được chọn
trong reader có thể trở thành referent rõ cho câu hỏi tiếp, kèm offsets và chuỗi
được chọn đối chiếu với kết quả; không thay toàn bộ nguồn bằng Clipboard mới.
Nếu lựa chọn không còn khớp sau đổi output, hỏi lại thay vì đoán.

Yêu cầu mới rõ như “tìm file …” được router/service quyết định thành task mới;
không để việc một source_ref đang tồn tại buộc mọi câu nhập thành hỏi về nguồn
cũ. QML chỉ gửi intent/context, không tự parse domain hoặc chọn provider.

Model tắt/chưa cấu hình: thông báo ngay tại thao tác cần model, một đường mở
cài đặt phù hợp; các tác vụ trực tiếp còn dùng được. Không bật model để làm UX
có vẻ liền mạch. Direct model-backed tool và model planning loop vẫn có nhãn
execution khác nhau. Không lộ private reasoning hoặc token stream giả.

## 6. Menu và chức năng phụ

Menu hiện tại chứa nhiều mục độc lập ngay cấp đầu, có thể dài hơn bubble nhiều
lần. Đưa chúng về cấu trúc theo task, chỉ hiện mục hợp lệ với context:

1. **Đọc rộng / Thu gọn**, **Hỏi tiếp**, **Ghim / Bỏ ghim** khi có kết quả.
2. **Với đoạn này…**: nguồn, sửa OCR, dịch lại/ngôn ngữ, giải thích/tóm tắt…
   Những mục cần cloud có nhãn rõ và recovery phù hợp.
3. **Gần đây…**: năm task trong RAM; recall không dispatch.
4. **Thêm…**: ảnh/vùng chữ, tìm/sắp xếp thư mục, Clipboard tùy chọn.
5. **Cài đặt…**, **Ẩn RAT**, **Thoát**. Chẩn đoán/quyền nằm trong Cài đặt/trợ giúp
   theo ngữ cảnh; không chiếm menu đầu khi trạng thái bình thường.

Giữ đường vào mọi khả năng đã duyệt. Organizer vẫn mở review đủ rộng với Apply
và Undo rõ, gắn artifact/revision và approval riêng. Không ép file mutation vào
bubble đọc vài dòng. Finder vẫn có lựa chọn hit, keyboard và coverage thật.

## 7. Vị trí, chuyển động và input mask

- Chọn anchor một lần từ geometry quan sát; neo nhân vật ổn định qua các phase.
  Bubble lớn lên về vùng trống, ưu tiên tránh selection và mép màn hình.
- Không có bounds hợp lệ: dùng góc đã nhớ; không lấy con trỏ/frame document rồi
  trình bày như vị trí selection thật.
- Source PID/geometry chỉ phục vụ lần gọi; geometry không đi vào model hoặc
  diagnostic export mặc định. Mixed-scale/display removal cần native review riêng.
- Đổi extent không ghi đè compact anchor. Đổi màn hình hoặc work area phải có
  transition xử lý riêng; không snap nhân vật về góc sau mỗi lần text thay đổi.
- Input mask theo vùng nhân vật/bubble/tail thực; khoảng trong suốt không cản
  thao tác với app nguồn. Các popup có ownership riêng để không bị outside-close.
- Chỉ dùng chuyển opacity ngắn nếu giúp thấy xuất hiện/gập lại; mục tiêu khoảng
  100–140ms để review. Reduced Motion dùng chuyển tức thời. Không chạy animation
  vị trí hoặc fake typing để che latency. Đây là đề xuất motion, chưa đo hiệu năng.

## 8. Phạm vi triển khai và thứ tự commit

| Đợt | Ưu tiên | Nội dung và điều kiện hoàn thiện source |
| --- | --- | --- |
| A. Khóa bố cục | P0 | Một sheet/spec gồm idle, một câu ngắn, đoạn dài, nhập tiếp, lỗi và expanded; dùng cùng kích thước nhân vật. Chốt tỷ lệ trước khi chỉnh lan sang nhiều view. |
| B. Lifecycle | P0 | Phân biệt gập/ẩn/thoát; focus intent, source binding, Esc và busy. Một transition owner dựa trên MiniPresentation, audit toàn bộ dismiss/recall path. |
| C. Bubble và composer | P0 | Bỏ chrome, natural height, Close không đè chữ, input gắn reader và context chip. Component còn mounted khi đổi extent. |
| D. Geometry | P0 | Head ở góc bubble, anchor ổn định, round-trip extent, screen clamping và input mask. Một nguồn kích thước native/QML. |
| E. Task/context | P0 | Hỏi tiếp vs task mới do router quyết định; menu theo context; history không mang approval/input từ task khác. |
| F. Finishing | P1 | Hover tooltip, trạng thái nhẹ tại Chuột, reduced-motion, chi tiết/readiness. Không thêm asset hoặc capability để lấp chỗ trống UI. |
| G. Handoff | P0 | Diff theo đợt, source/build identity rõ, giữ gói .27 recovery. Build và mở khi có yêu cầu, để người dùng thao tác. |

Không chạy test xen kẽ các đợt. Hoàn thiện toàn bộ source trước; mọi verification,
build hoặc launch vẫn theo yêu cầu riêng. Không hẹn thời gian hoàn thành giả.
Nếu thực hiện, ưu tiên P0 trước motion/pose để vòng feedback tập trung vào UX.

### Ánh xạ code

- `mini_presentation.py`, `look_interaction.py`: một owner của view intent,
  visibility/extent/input và retained reading context. Phase thực thi thuộc worker.
- `mini_quick_controller.py`: intent gập/ẩn/nhập/recall và snapshot. Source/task
  transitions qua orchestration chung; không thêm business execution ở UI.
- `MiniDesk.qml`: tách component trình bày reader, composer, details và menu nếu
  giúp đọc diff; vẫn một QQuickWindow, một editor/reader sống qua resize. Không
  dựng Loader phá state để đổi giao diện.
- `mini_shell.py`, `mini_placement.py`, `speech_placement.py`, `MascotPose.qml`:
  layout native/logical, optical bounds, focus, popup ownership và mask.
- `MiniSession`, shared goal router, capture/analysis tools: xử lý source-binding
  và mục tiêu mới tại service/contract; giữ các verifier và approval đang có.

## 9. Kịch bản nghiệm thu sau khi được yêu cầu

| Kịch bản | Điều phải thấy |
| --- | --- |
| Mở idle | Chuột rõ mặt; không form lớn hoặc bubble rỗng. |
| Selection + shortcut | Đúng nguồn, gần chữ hoặc fallback rõ; app nguồn chưa mất focus trước capture. |
| Kết quả một câu | Bubble theo chữ; không header/footer/copy CTA hoặc khoảng trắng working còn sót. |
| Kết quả dài | Đọc được dòng cuối; chọn chữ, ⌘C và đọc rộng/thu gọn giữ đúng ngữ cảnh. |
| Click Chuột hỏi tiếp | Một field gắn kết quả; source chip đúng, Enter gửi đúng nguồn. |
| Yêu cầu mới | Router chuyển task rõ; source cũ không làm sai yêu cầu mới. |
| Esc/Close/outside/pin | Đúng mức gập/ẩn; draft không mất; không reopen khi background hoàn tất. |
| Model tắt/lỗi mạng/nguồn hết hạn | Một thông báo thực và recovery phù hợp; không fabricate answer. |
| Finder/Organizer | Mở đúng hit; preview không chuyển file; approval và Undo không hồi sinh từ history. |
| Menu, drag, màn hình | Menu không bị clip; drag không thành click; transparent area không chặn app nguồn. |

Một screenshot cho mỗi trạng thái chỉ khi người dùng yêu cầu capture; không dùng
canned response để giả acceptance. Native/UI acceptance, loop model thật, main/M3
integration và nghiên cứu Stage0 là các bằng chứng/gate riêng.

## 10. Điều còn cần review

Không có câu hỏi chặn việc lập kế hoạch. Kích thước optical và tỷ lệ head/bubble
sẽ được đánh giá bằng cùng một layout sheet, không mặc định được chấp nhận chỉ
vì số px đã đổi. Motion và vị trí đặt menu là phần điều chỉnh sau luồng P0.

Trong .28 chưa mở rộng sang local LLM, vector DB/index cá nhân, asset generation,
main UI integration hay thay đổi research claims. Overhaul này giải quyết cách
người dùng gọi, đọc và tiếp tục công việc đã có.
