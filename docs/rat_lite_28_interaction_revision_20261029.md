# .28 interaction revision — phản hồi, hỏi ngay, hội thoại

Trạng thái: đề xuất sau khi người dùng chưa thuyết phục với phân chia
“selection → bubble, click Chuột → chat”. Chỉ sửa plan; không triển khai, build,
launch hay kiểm thử. Tài liệu này thay thế các quy tắc tương ứng ở phần goals,
composer, interaction, click/recall và follow-up của plan overhaul .28 ban đầu.
Các quyết định khác về hình Chuột, Copy CTA, geometry, tools và gates vẫn giữ.

## 1. Điều cần sửa trong lập luận trước

1. Cách gọi là một tín hiệu, không đủ định nghĩa toàn bộ nhu cầu. Một đoạn code
   có thể cần dịch, giải thích hoặc sửa; riêng hình thức snippet không cho phép
   RAT tự chọn một nghiệp vụ khác với điều người dùng gọi.
2. Một ô nhập dùng để ra lệnh một lần hoặc hỏi làm rõ không cần kéo theo cả
   transcript. Đồng nhất input với chat sẽ dựng lại cửa sổ lớn đúng lúc người
   dùng chỉ muốn hỏi thêm một câu.
3. Kích thước hiển thị, độ sâu tương tác và cách thực thi là ba việc riêng.
   Câu dài cần vùng đọc rộng; nhiều tools cần trạng thái tác vụ. Cả hai đều
   không tự yêu cầu một giao diện hội thoại.
4. Giữ source_ref hoặc vài snapshot task chưa phải có hội thoại đáng tin cậy.
   Chat phải giữ và phân biệt nguồn gốc, kết quả vừa tạo và các lượt trao đổi.

## 2. Ba mức tương tác, không có bộ chọn mode nghiệp vụ

| Mức | Dùng khi | Thấy gì | Ví dụ |
| --- | --- | --- | --- |
| **Phản hồi nhanh** | Có một hành động đã rõ trên một nguồn | Chuột + bubble kết quả; không input thường trực | Gọi Quick Look dịch đoạn đã chọn. |
| **Hỏi ngay** | Cần nhập yêu cầu, làm rõ hoặc sửa một kết quả ngay tại chỗ | Cùng bubble, thêm một field nhỏ khi chủ động; vẫn giữ context | “Giải thích từ này”, “ngắn hơn”, “tìm file báo cáo”. |
| **Hội thoại** | Người dùng muốn xem/làm việc với chuỗi lượt trao đổi | Cùng surface mở rộng thành transcript + composer + nguồn/task liên quan | So sánh hai phương án, xem lại bản sửa trước và tiếp tục trao đổi. |

Ba mức này dùng cùng task/session/execution service. “Hội thoại” là cách xem và
làm việc với lịch sử, không phải một model hoặc backend execution mode khác.
Hỏi ngay vẫn có thể dùng Agent; hội thoại vẫn có thể gọi tool xác định.

## 3. Khi nào kích hoạt từng mức

### Phản hồi nhanh: đã có ý định đủ rõ

Giữ shortcut selection hiện đã được dùng để **Quick Look dịch**. Đây là một
hành động mặc định được biết rõ, không phải suy đoán “mọi selection cần dịch”.
Tooltip/cài đặt mô tả đúng “Dịch đoạn chọn · [phím thực]”. Không thêm màn chọn mode
mỗi lần; nếu sau này đổi hành động mặc định thì là một cài đặt rõ của người dùng.

- Đoạn text/code được chọn vẫn là dữ liệu, kể cả khi nó chứa câu lệnh cho RAT.
- Gọi dịch nhưng nguồn không phù hợp/không đủ thì báo ngắn hoặc hỏi dữ kiện cần
  thiết. Không âm thầm đổi sang giải thích code hoặc thực thi nội dung snippet.
- Ảnh/Clipboard là nguồn, không phải intent. Chỉ gọi dịch ngay khi ingress đã
  mang hành động dịch hoặc có yêu cầu rõ. Dán/thả ảnh vào draft chỉ nhận attachment.
- Chọn chữ hoặc copy thông thường không mở UI, không chạy tool/model.

### Hỏi ngay: nhập một câu chưa phải mở chat

- Không có task: click Chuột mở field nhỏ “Bạn cần gì?”. Không dựng transcript rỗng.
- Đang thấy kết quả: click Chuột mở field ngay dưới kết quả để hỏi tiếp.
- RAT cần clarification: hiện một câu hỏi và cách trả lời ngay ở bubble. Capture
  chưa xong thì chưa giành focus; keyboard focus chỉ khi người dùng tương tác rõ.
- Gửi “viết ngắn lại” hoặc “giải thích từ này” rồi vẫn đọc đáp án ở bubble nhỏ.
  Kết quả trước còn trong lịch sử task, không bị xóa hoặc gửi lại.
- Đang làm việc nhiều bước: hiện tiến độ/tác vụ tương ứng, không tự mở transcript.

### Hội thoại: mở có chủ ý, hoặc khôi phục đúng view đã chọn

Đường vào: “Mở hội thoại” trong menu; khi field hỏi ngay đang mở, có một affordance
nhẹ “Xem trao đổi” nếu đã có các lượt trước. Nó không xuất hiện như một CTA thường
trực trong bubble chỉ đọc. Không đếm N lượt hoặc dùng độ dài để tự nhảy sang chat.

Khi người dùng đã chủ động mở hội thoại của task, recall task có thể khôi phục
view đó. Selection shortcut cho một nguồn mới vẫn tạo phản hồi nhanh của task
mới, không kéo theo chat cũ. Lệnh “Viết yêu cầu” mở field hỏi ngay cho task mới;
không mặc định mở một trang chat lớn.

## 4. Ma trận quyết định và ưu tiên

Thứ tự: intent hiển thị rõ của người dùng → khôi phục task/view đã chọn → yêu
cầu input thực từ service → mức phản hồi phù hợp. Không suy UI từ tool count.

| Sự kiện | Mức tiếp theo | Điều phải giữ |
| --- | --- | --- |
| Selection + shortcut dịch | Phản hồi nhanh mới | Capture/source PID trước show; task cũ và draft được giữ. |
| Click head khi chỉ còn head, có task | Khôi phục view task vừa cất | Không capture, resubmit hoặc tự mở input ngoài ý muốn. |
| Click head khi chỉ còn head, không task | Hỏi ngay | Một field trống; không transcript giả. |
| Click head khi bubble đang đọc | Hỏi ngay về task hiện tại | Nội dung còn thấy, nguồn rõ. |
| Click head khi input đang mở | Cất input, về kết quả/head | Draft còn. |
| Service cần một thông tin | Hỏi ngay | Câu hỏi cụ thể, không modal/full chat tự động. |
| Câu trả lời dài | Reader rộng/cuộn theo lựa chọn | Không coi đọc rộng là mở hội thoại. |
| Chọn Mở hội thoại / Xem trao đổi | Hội thoại | Public turns, nguồn và draft cùng task. |
| Thu gọn hội thoại | Bubble kết quả gần nhất | Transcript giữ trong RAM, không tóm tắt giả rồi xóa lịch sử. |
| Background completion khi bị cất/ẩn | Giữ mức cất/ẩn | Chỉ cập nhật dữ liệu. |
| Shortcut khi đang busy | Giữ task hiện tại; báo bận nhẹ | Không thay nguồn/draft hoặc xếp job ngầm. |

Click head phải dùng trạng thái hiển thị thực; không giữ rule toggle-input cho
cả lúc recall. Hiện `toggleComposer()` và `summonLook()` chưa đủ biểu đạt ma trận này.

## 5. Context phải đúng trước khi giao diện trông liền mạch

Mỗi task có các phần riêng:

- **Nguồn gốc:** captured artifact/ref/revision, provenance và thời hạn.
- **Kết quả đang làm việc:** artifact/output ref của bản mới nhất.
- **Referent được chọn:** đoạn chọn và offsets trên đúng output revision.
- **Intent mới:** câu người dùng vừa gửi.
- **Public turns:** các câu hỏi/trả lời và trạng thái công khai; không private reasoning.
- **Draft chưa gửi:** tách khỏi intent đang chạy và không đưa vào model.

“Giải thích câu cuối” thường nhắm nguồn đang đọc; “rút gọn bản dịch vừa rồi” nhắm
kết quả vừa tạo. Không đưa cả hai dưới nhãn mơ hồ “Về đoạn này”. Trong lúc nhập,
context chip có tên đúng: “Đoạn gốc”, “Bản dịch vừa rồi” hoặc “Phần đang chọn”.
Nếu thiếu dữ kiện để gắn referent, hỏi lại một câu; không giả hiểu được.

Bỏ chip để yêu cầu mới không xóa task cũ. Router/service xử lý câu rõ như “tìm
file …” thành task mới, UI không parse nghiệp vụ. Nhận source mới không âm thầm
thay referent của một draft đang gõ. Selection shortcut chủ động tạo task mới
có thể cất task/draft cũ rồi cho quay lại bằng history.

Lịch sử 5 task khác transcript trong một task. Giới hạn RAM/context phải rõ,
không ghi văn bản cá nhân thành lịch sử bền vững trong đợt này. Model context
pack chỉ lấy các public turn và artifact cần thiết trong budget hiện có; giữ
nguyên source expiry và thông báo khi thiếu context thay vì replay vô hạn.

## 6. Các trường hợp để tự phản biện thiết kế

| Tình huống | Sai nếu làm theo rule cũ | Quyết định mới |
| --- | --- | --- |
| Chọn một snippet code, gọi dịch | Tự hiểu rằng muốn debug code | Thực hiện hành động dịch đã gọi; muốn giải thích thì nhập yêu cầu. |
| Bản dịch ngắn, hỏi “tự nhiên hơn” | Bật cửa sổ chat lớn | Field inline; tác vụ dùng đúng bản dịch vừa tạo và giữ nguồn để đối chiếu. |
| RAT hỏi ngôn ngữ đích | Ép mở chat hoặc Settings | Một câu hỏi ngay trong bubble; trả lời rồi tiếp tục đúng request. |
| Kết quả 20 đoạn | Tự biến thành hội thoại | Đọc rộng/cuộn cùng output, không tạo thêm turn. |
| Organizer cần xác nhận | Dồn Apply vào bubble/chat thường | Review task plan đủ rộng, approval riêng; không auto-apply. |
| Muốn xem lại cách câu trả lời đã thay đổi | Chỉ còn result mới nhất | Chủ động mở transcript, xem các public turn trong task. |
| Chỉ muốn xem lại sau khi đóng | Click head lại mở editor | Khôi phục view; click tiếp khi đang đọc mới là hỏi ngay. |
| Đã mở chat rồi chuyển qua đoạn khác | Source mới bị nhét vào chat cũ | Selection shortcut tạo task phản hồi mới, cất task/draft cũ. |

## 7. Phần source cần làm thêm, không chỉ đổi điều kiện QML

Quan sát từ source hiện tại:

- `capture_translation.py` đã có nhánh capture+translate và observe-only; ingress
  phải truyền intent đúng, không suy từ file type trong UI.
- `MiniSession._agent_history` hiện phục vụ continuation của clarification và
  được clear sau hoàn tất. Nó chưa phải transcript hội thoại hoàn chỉnh.
- Snapshot task history hiện giữ state/ref/draft; chưa có public-turn ledger và
  result-reference semantics đủ cho “sửa câu trả lời vừa rồi”.
- `MiniPresentation.extent`, composer visibility và surface đã tách một phần;
  cần phân biệt read extent với conversation view. Không thêm boolean chat ở
  QML rồi coi continuity đã được nối.
- Dispatcher/verifier của analysis hiện source-bound. Làm việc với output đã
  tạo cần result-ref contract/validation phù hợp, giữ origin provenance và phân
  biệt đó là model output, không relabel thành captured source.

Thứ tự cập nhật implementation plan:

1. Chốt intent/referent/view transition table và mock cùng một ví dụ xuyên suốt.
2. Bổ sung task public-turn/result context và shared service binding; giữ budgets.
3. Wire phản hồi nhanh + hỏi ngay, focus/dismiss/recall đúng ma trận.
4. Wire conversation projection lên cùng task, tách reader rộng khỏi transcript.
5. Source-complete rồi bàn giao; chỉ build/test/launch khi được yêu cầu riêng.

## 8. Điều sẽ làm trước khi code tiếp

Tạo một layout storyboard gồm cùng một đoạn nguồn ở năm khung: gọi dịch → đọc
bubble → hỏi ngay “tự nhiên hơn” → xem trao đổi → thu gọn về kết quả mới. Thêm
hai khung failure: thiếu intent và nguồn/referent không còn hợp lệ. Mục tiêu là
review được sự liên tục trước khi thay hàng loạt view.

Đây là điều chỉnh đề xuất, chưa có acceptance. Không mở rộng main/M3 hay nghiên
cứu Stage0; model opt-in vẫn là quyết định riêng, không bị UI tự bật.
