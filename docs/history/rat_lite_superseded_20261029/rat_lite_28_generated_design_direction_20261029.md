# .28 design direction — các yếu tố từ ba ảnh generated

Trạng thái: **bổ sung plan từ yêu cầu người dùng**, chưa triển khai/build/launch.
Ba ảnh là concept generated, không phải UI RAT đang chạy và không xác nhận bất
kỳ nội dung, khả năng, tiến độ hoặc kết quả nào xuất hiện trong ảnh. Các chữ nhỏ
bị méo được dùng để nhận diện ý tưởng, không thành microcopy cuối cùng.

Tài liệu này bổ sung plan overhaul và interaction revision. Các thay đổi mới
quan trọng: seated full-body mascot là baseline thị giác cần storyboard; UI có
các thẻ chuyên biệt theo payload; Workbench có ba vùng thay vì chỉ transcript lớn.
Quyết định không có nút Sao chép vẫn giữ dù ảnh minh họa có nhiều CTA khác.

## 1. Đọc kỹ bố cục chung

- Cả bộ ảnh đều đặt RAT trên desktop/app nguồn, thường gần mép dưới, với nhân vật
  toàn thân ngồi có tỷ lệ rõ mặt. Có biến thể bên trái và bên phải. Gói UI gắn với
  nhân vật thay vì giống một dialog hệ thống đứng độc lập.
- Hình Chuột vừa là điểm nhận diện vừa là điểm nối input/output; pose thay đổi
  theo trạng thái như đọc bằng kính lúp, chờ, phân vân hoặc mệt. Một sparkle lớn
  xuất hiện trong vài concept; chỉ lấy ý phản hồi nhẹ, không bê nguyên vật trang trí.
- Có một input bar ngang, các thẻ nổi phía trên và vài chip nhỏ theo context.
  Có light/dark với surface dịu, border mảnh, góc bo; màu xanh/vàng/đỏ dùng cho
  hành động, cảnh báo, lỗi. Không suy được contrast hoặc kích thước thật từ ảnh.
- Các thẻ khác nhau về chức năng: một câu trả lời, nguồn, chọn dữ kiện, công việc
  nhiều bước, preview hành động và cảnh báo không nên render cùng một template.
- Screenshot cuối mở một workspace có Chat Feed, một vùng bước/CoT và Documents.
  Đây là gợi ý kiến trúc thông tin, không yêu cầu lộ private chain-of-thought.

Lấy ngôn ngữ thiết kế này, không copy các stack bị lặp, văn bản méo, phần phủ
Dock, nút quá nhỏ hoặc thanh lỗi chạy tận mép trên màn hình.

## 2. Yếu tố của ảnh 1 — sáu tình huống

| Concept nhìn thấy | Đưa vào plan | Nội dung thật và ranh giới cần có |
| --- | --- | --- |
| Suy luận đa bước | Thẻ task với một dòng các giai đoạn công khai, bước hiện tại và kết quả ngắn. Các bước đã chạy có trạng thái riêng. | Plan dự kiến và việc đã thực hiện phân biệt rõ. Dữ liệu từ service/events, không raw reasoning hoặc fake countdown “chờ 2 giây”. |
| Trích dẫn / đọc nhanh | Đoạn trả lời/quote nối với chip nguồn, có hành động xem đúng nguồn tại chỗ. | Chip gắn artifact/resource/revision; có page/span thì phải được reader quan sát thật. Hiện tại source_analysis có literal excerpts; PDF/DOCX multi-document reading chưa tự có từ việc vẽ chip. |
| Xem trước / áp dụng | Thẻ preview nêu hành động, đối tượng, số lượng và đường xem thay đổi; Apply tách rõ khỏi Preview. | Ưu tiên áp dụng pattern vào Organizer đã có. Rename mọi screenshot như ảnh là capability mở rộng cần hợp đồng/preview/receipt riêng, không kích hoạt từ mockup. |
| Hỏi lại để làm rõ | Một câu hỏi cùng các lựa chọn ngắn lấy từ dữ liệu thật, nằm ngay trên input hiện tại. | Chọn chip điền dữ kiện cho đúng InputRequest; không đặt mode Tìm/Dịch. Không auto-select/auto-submit đáp án mặc định. |
| Nghi vấn dữ liệu | Thẻ “Có thông tin khác nhau”, kèm hai nguồn/đoạn liên quan và điều cần làm rõ. | Phân biệt khác thời kỳ/phạm vi với mâu thuẫn thật; suy luận model chỉ ghi “có thể mâu thuẫn” khi chưa kiểm chứng. Không fabricate tài liệu hoặc kết luận. |
| Lỗi / thử lại | Lỗi cục bộ trong cụm RAT, có reason ngắn và đúng một recovery chính: thử lại, cấu hình hoặc quyền. | Giữ draft/source/kết quả partial. Retry tái dùng request/ref hợp lệ; không chạy lại mutation đã có receipt hoặc mở một stack toast toàn màn hình. |

## 3. Yếu tố của ảnh 2 — sáu tình huống

| Concept nhìn thấy | Đưa vào plan | Nội dung thật và ranh giới cần có |
| --- | --- | --- |
| Lịch sử gần đây | Thẻ recent task/public turns, có chip tài liệu liên quan để quay lại đúng công việc. | Reuse khay 5 task RAM, cộng public-turn ledger theo interaction revision. Tên file chỉ khi đã có observation; recent task không tự là chat history hay filesystem crawl. |
| OCR | Thẻ nhận chữ: preview ngắn, số ký tự thật, mở chữ/ảnh và sửa chữ đã đọc. | Dùng capture/correction artifact cùng parent/root/hash. “Đã lưu” chỉ hiện sau một save operation thật; không coi artifact trong RAM là file TXT đã lưu. |
| Đang tải / xử lý file lớn | Thẻ công việc có tên đối tượng, phase và progress thật; có Stop khi cancellable. | % chỉ từ total/completed xác định. Nếu không có tổng đáng tin thì indeterminate + tên bước. Không fake45%, ETA hoặc streaming. File lớn phụ thuộc reader/budget thực của capability. |
| Thông báo cập nhật | Một thẻ thông tin nhỏ, có thể đóng, xuất hiện khi người dùng mở app/build có thay đổi liên quan. | Nội dung từ manifest/release notes và khả năng thực đã đóng gói. Không tự thêm background updater, network polling hoặc quảng cáo CSV chưa triển khai. |
| So sánh code | Thẻ summary +/−, đường vào diff hai đoạn; có thể đọc rộng khi cần. | Đếm từ diff xác định trên hai input/ref đã pin. “Khác dòng” không phải xác minh code đúng; không chạy code, sửa file hoặc Apply tự động. Cần bổ sung tool/contract nếu triển khai chức năng này. |
| Xác nhận xóa | Pattern cảnh báo có phạm vi, đối tượng/số lượng và Cancel/Confirm rõ, cùng khả năng xem danh sách. | Gắn approval vào đúng plan/revision. Không thêm delete capability chỉ vì có hình. Phải đặc tả loại xóa, phục hồi và receipt trước khi có action thật; approval cũ không hồi sinh từ history. |

## 4. Yếu tố của ảnh 3 — Workbench

**Thêm Workbench vào đích thiết kế**, mở chủ động từ cùng task đang dùng. Nó là
mức không gian làm việc, không phải tự chuyển vào RAT main hoặc mở một app khác.

| Vùng | Nội dung đề xuất | Không được suy diễn |
| --- | --- | --- |
| Trao đổi | Public user/assistant turns, draft và kết quả có liên kết tới artifacts | Snapshot mới nhất không thay cho transcript thật. |
| Tiến trình | Mục tiêu, plan công khai nếu có, tool steps đã chạy, observation, verification và phần chưa hoàn tất | Không raw model thoughts/private CoT; không dựng sơ đồ “suy nghĩ” giả từ animation. |
| Nguồn / Kết quả | Input đã pin, snippets, documents nếu capability có đọc thật, các output/diff/receipts của task | Tìm thấy filename không có nghĩa đã đọc tài liệu; đăng ký tool không nghĩa model loop đã chạy. |

Dùng label **Trao đổi / Tiến trình / Nguồn & kết quả** thay vì “Thought Map (CoT)”.
Các artifact/step có thể chọn để xem bằng chứng công khai và quay về câu trả lời
liên quan; không để ba cột thành ba luồng độc lập.

- Rộng đủ: ba vùng. Hẹp: một vùng chính với các vùng phụ mở theo nhu cầu; không
  nhét ba cột khiến chữ nhỏ hoặc đặt tab thành mode nghiệp vụ.
- Một mascot, một editor sở hữu draft và một task active. Khi Workbench mở,
  không để một phiên bản floating khác tiếp tục nhận input phía sau.
- Mở/thu về compact giữ task, source/ref, draft, vị trí đọc và lựa chọn. Close
  Workbench quay về nơi đã mở nó, không kết thúc task hay tự dispatch lại.
- Cần giữ distinction **đọc rộng một kết quả**, **xem hội thoại** và **Workbench
  có nhiều vùng**. Chúng dùng chung session, được mở theo nhu cầu; độ dài hoặc
  số tool không tự quyết định mở Workbench.
- Nếu UI thật cần khác window role để resize, handoff phải nêu và kiểm chứng
  focus/owner; thiết kế mặc định vẫn ưu tiên cùng window và không duplicate state.
- Gói Workbench trong Lite không tự bật main profile; main/M3 vẫn là gate riêng.

## 5. Mô hình UI cập nhật: ba trục độc lập

1. **Độ tương tác:** phản hồi → hỏi ngay → hội thoại.
2. **Không gian:** bubble → đọc rộng → Workbench theo lựa chọn.
3. **Loại nội dung:** answer / source / progress / clarification / preview /
   conflict / error / history / OCR / diff / announcement.

Không tạo 12 “mode” theo 12 screenshot. Renderer chọn thẻ từ artifact/event/input
request thật. UI thao tác vẫn dispatch qua contracts chung; state hiển thị không
quyết định nghiệp vụ và không phát sinh tool call chỉ vì expand/collapse.

Một ví dụ đích: chọn đoạn → bubble phản hồi → hỏi ngay → task cần hai nguồn thì
hiện nguồn/clarification → người dùng mở Workbench để đối chiếu → có thay đổi file
thì review plan và Apply riêng → thu về bubble kết quả. Các bước cần capability
chưa có chỉ được storyboard với nhãn concept, không giả thành acceptance.

## 6. Quy tắc visual và pose

### Nhân vật

Ưu tiên **Chuột toàn thân ngồi** như cả bộ ảnh làm baseline storyboard mới. Dùng
asset ngồi đã có trước khi sinh asset mới. Điều này điều chỉnh hướng head-only của
correction c8192972; kích thước đó chưa được user chấp nhận.

Đầu/crop có thể là biến thể peek được chọn có chủ ý sau review; không tự biến
nhân vật thành icon nhỏ khi lời đáp ngắn. Các pose có vùng hình thực tương đương
và cùng điểm neo/baseline; không nhảy vị trí vì đổi ảnh.

Đề xuất vocabulary: idle/ngồi, đọc/tìm với kính lúp nếu có asset phù hợp,
working/chờ, clarification/nghiêng chú ý, conflict/phân vân, error/nghỉ. Pose chỉ
phụ họa một trạng thái đã có bằng chứng, luôn có text phù hợp; không dùng vẻ vui
để che lỗi hoặc mặt mệt làm tín hiệu duy nhất. Reduced Motion không có loop/nhún.
Không cần đủ pose mới để ship phần interaction P0.

### Thẻ và stack

- Bubble đọc đơn giản vẫn chỉ nội dung + Close; không thêm Copy CTA.
- Khi đã có input/hành động, dùng một input bar cùng một thẻ chính và tối đa
  một thẻ phụ đang mở. Nguồn hoặc lịch sử bổ sung gom vào nhóm/chip, không stack
  nhiều panel như một số ảnh generated.
- Chip có nhãn và biểu tượng/type; tooltip cho tên bị cắt. Không dùng màu làm
  bằng chứng duy nhất cho ready/conflict/error.
- Close cục bộ chỉ đóng/cất thẻ đó theo lifecycle đã chốt. Cancel công việc,
  Cancel approval và Quit là intent khác, không dùng chung icon rồi đoán.
- Light/dark chia sẻ spacing, hierarchy và trạng thái. Surface dịu, text dễ đọc;
  màu cảnh báo/hành động vừa đủ. Contrast/hit target phải review từ UI thật,
  không claim đạt chuẩn từ screenshot generated.
- Position tránh Dock/menu bar/app selection; không mặc định dính đáy trái.
  Chọn mép hợp lệ và giữ anchor, chứ không chạy theo con trỏ.

## 7. Phân kỳ đã đưa vào roadmap

| Đợt | Deliverable | Phạm vi |
| --- | --- | --- |
| .28 UX core | Storyboard nhân vật + answer/input, gập/recall, đọc rộng và Workbench shell | P0; dùng capabilities thật đang có, không fabricate nguồn/tiến độ. |
| .28 states | Các thẻ clarification, lỗi/retry, tiến độ public, OCR, recent và Organizer preview | Reuse các contracts có sẵn; phần tiến độ chỉ hiện dữ liệu có thật. |
| .28 Workbench | Public-turn ledger, progress/event projection, sources/results linked và round-trip compact | Theo dependency result-ref/context của interaction revision; main UI integration chưa nằm trong đó. |
| Đợt capability tiếp | Multi-document grounded reading/conflict, code diff, rename, delete, save OCR nếu muốn thực thi | Đưa thành backlog rõ; mỗi mục cần shared tool/contract/verifier/approval thích hợp trước khi expose action. |
| Polish/release | Pose vocabulary, light/dark và thông tin build | Không biến notification thành background updater, không chờ asset mới để sửa P0. |

Người dùng yêu cầu yếu tố trong các ảnh cho version sau. Toàn bộ pattern được
lưu trong plan; các capability mở rộng được tách dependency để tránh bỏ qua hoặc
ngầm tuyên bố đã có chỉ vì đã vẽ UI. Không có permission question chặn lượt plan.

## 8. Storyboard tiếp theo phải thể hiện được

1. Cùng một Chuột toàn thân ở idle, đọc và input; tỷ lệ ổn so với bubble/app nguồn.
2. Bubble một câu không Copy, mở input hỏi tiếp, context nguồn/kết quả chính xác.
3. Một clarification với hai chip thật và một đường nhập đáp án khác.
4. Một task nhiều bước: phase, hai nguồn, partial/error và recovery.
5. OCR: chữ nhận → sửa → output, phân biệt chưa lưu file với đã nhận chữ.
6. Organizer: preview → review → explicit Apply → receipt/Undo, dùng capability có thật.
7. Workbench ba vùng liên kết với task ở khung 4, rồi thu về đúng bubble/draft.
8. Một scene nâng cao như conflict/diff với nhãn **concept — capability chưa nối**.

Storyboard dùng cùng nội dung xuyên suốt để nhìn continuity; mockup không được
lẫn vào evidence live. Không chạy model, test, UI tour hoặc capture screenshot
thật trong lượt thêm plan này.
