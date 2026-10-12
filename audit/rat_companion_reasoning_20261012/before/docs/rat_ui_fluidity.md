# RAT: bố cục linh hoạt và tương tác liên tục

Date: 2026-10-12. Status: đã triển khai trong source RAT; kiểm tra bằng Qt fixtures và cửa sổ macOS thật. Review trải nghiệm của người dùng còn mở.
Tracking: [RAT-UX-01 / 02 / 03](rat_backlog.md).

## Persona đã xác nhận: người bạn nhận việc và ghi chép

Người dùng xác nhận ngày 2026-10-12: Chuột là một người bạn nhận điều người
dùng nói, ghi chép, làm việc rồi trả kết quả. Personality cần hiện trong cách
làm việc và bề mặt một box chat. Phần này là hướng thiết kế đã xác nhận; chưa
triển khai trở lại mascot hoặc thay hành vi model trong đợt UI trước.

- Chuột có một vị trí nhỏ bên ô nhập, giữ cùng danh tính khi compact/full.
  Chuyển động gắn với sự kiện thật: nhận yêu cầu, có dữ kiện mới được ghi,
  đang thực thi, cần bổ sung hoặc có kết quả. Kết quả và ô nhập vẫn là trọng tâm.
- Giọng thân thiện, bình tĩnh, trực tiếp. Hài hước tùy hoàn cảnh; không đặt
  yêu cầu mỉa mai làm tính cách mặc định. Câu hỏi bổ sung nêu đúng điều còn
  thiếu để tiếp tục việc người dùng đang làm.
- Một dòng ghi chú ngắn có thể mở để xem/sửa điều Chuột đang dùng cho công
  việc. Ghi chú thể hiện dữ kiện và ràng buộc có nguồn; suy đoán hay kế hoạch
  của model không được hiển thị như lời người dùng đã xác nhận.
- Khi làm xong, đưa kết quả chính và thao tác tiếp ngay trong cùng bề mặt.
  Khi đang đọc, sự hiện diện của Chuột nhẹ hơn. Trạng thái đang làm phải
  theo worker/execution event; lời model nói “xong” không xác nhận thực thi.

### Thay đổi chung được đề xuất, chưa triển khai

1. Một ngữ cảnh công việc dùng chung cho lịch, tệp và lá số: mục tiêu,
   dữ kiện/ràng buộc, đối tượng đang nói tới, kết quả và phần còn thiếu.
2. Ghi chép có nguồn và phạm vi: phân biệt người dùng với người khác,
   dữ kiện chính xác với gần đúng, thông tin mới sửa với giá trị cũ. Dữ kiện
   trong phiên phục vụ công việc hiện tại; lưu dùng lâu dài có thao tác rõ ràng
   và có thể xem, sửa, quên. Chưa bổ sung database memory trong cập nhật này.
3. Tiếp tục, sửa, đổi mục tiêu và dừng cùng công việc. Dữ kiện hợp lệ và kết
   quả đã có được dùng tiếp; yêu cầu mới không phải điền lại một màn hình.
4. Kết quả phối hợp theo mục tiêu, có tham chiếu dữ liệu thật. Ví dụ một kế
   hoạch ôn tập có lịch rảnh và tài liệu liên quan trong cùng kết quả.
5. Phản hồi nhanh và trung thực: nhận việc ngay, hiển thị phần đã sẵn sàng,
   cập nhật cùng kết quả, thông báo lỗi có đường sửa. Thao tác trực tiếp dùng
   dispatcher hiện có; yêu cầu tự do vẫn cần model hiểu và chọn hành động.

Các đề xuất này nối với RAT-AI-01/02/03 trong backlog. Chưa đổi trạng thái
backlog, triển khai runtime, benchmark hoặc đưa ra claims năng lực mới.

## Ý định của người dùng

Người dùng xác nhận UI cứng nhắc ở **cả bố cục lẫn cách chuyển trạng thái**.
Sau đó người dùng xác nhận hướng **mọi chức năng trong một box chat**, với
**full và compact là một trải nghiệm liền mạch, đơn giản**. Đây là yêu cầu
sản phẩm đã xác nhận. Source đã áp dụng bố cục dưới đây; không coi kiểm tra phần mềm là bằng chứng usability.
Hướng thay đổi kiến trúc/model đã được lưu riêng trong backlog. Brief này tập
trung vào cách bề mặt phản ứng với nội dung và thao tác; không cần triển khai
toàn bộ ADR-002 để thử một thiết kế tương tác tốt hơn.

Đích thiết kế: người dùng cảm nhận mình đang tiếp tục làm việc trên cùng một
kết quả. Không cần tìm lại nơi nhập, đọc lại các lớp tiêu đề hoặc đi sang một
form mới mỗi khi chỉnh một chi tiết.

## Một box chat, hai mức không gian

Full và compact là hai mức không gian của cùng một bề mặt và cùng một công
việc. Người dùng chỉ mở rộng hoặc thu lại chỗ nhìn; không đổi ứng dụng, chức
năng, hội thoại hoặc cách thao tác. Kết quả trực quan, tệp, lịch, câu hỏi và
điều khiển cần thiết đều xuất hiện trong box này.

| Phần giao diện | Compact | Full | Thứ phải giữ khi chuyển |
| --- | --- | --- | --- |
| Ô nhập | Một vị trí nhập yêu cầu và hỏi tiếp. | Chính ô nhập đó, thêm không gian khi cần. | Text, caret/selection, input method composition và focus. |
| Kết quả đang làm việc | Nội dung vừa đủ đọc/thao tác; có thể cuộn hoặc mở chi tiết ngay trong box. | Thêm vùng đọc/hình/so sánh. | ID/revision, lựa chọn, dữ liệu đang chỉnh và trạng thái pending. |
| Hội thoại | Ưu tiên đoạn và kết quả liên quan hiện tại; lịch sử vẫn truy cập được. | Có thêm chỗ xem lịch sử và nội dung dài khi người dùng mở. | Cùng lịch sử và tham chiếu; quay lại đúng phần đã đọc ở mỗi mức. |
| Điều khiển | Gắn với dữ liệu đang nhìn; thao tác phụ trong menu. | Cùng ý nghĩa và vị trí tương đối; không thêm một dashboard chức năng. | Action đích, khả năng dùng bàn phím, submit/stop/cancel. |
| Công việc đang chạy | Feedback ngắn và khả năng dừng trong box. | Cùng công việc, không chạy lại. | Worker, execution state và kết quả đã có. |

Compact có thể xem và làm việc với lá số, tìm tệp hoặc lịch; không bị giới hạn
thành màn hình gõ rồi bắt chuyển full để làm chức năng thật. Full cho thêm chỗ
đọc và thao tác. Nội dung cần chỗ lớn hơn có thể mở ngay trong box bằng hành
động rõ ràng của người dùng. Gửi câu hỏi hoặc nhận tool result không tự chuyển
full. Auto-grow nhỏ trong compact và lựa chọn full của người dùng là hai việc
khác nhau; cần giới hạn theo màn hình và tránh dời điểm neo.

Không mặc định mỗi chức năng là một card/form hoàn chỉnh đặt trong chat.
Một trả lời ngắn có thể chỉ là chữ; kết quả tìm tệp là những dòng tệp có action;
lá số là hình và metadata chỉnh được; một câu hỏi bổ sung là câu hỏi và các
điều khiển cần thiết. Không dựng lại app con, navigation bar hay bộ nút riêng
cho từng domain trong full.

Việc chuyển kích thước phải nối cùng nội dung và phản hồi ngay. Không fade
ra hết rồi thay sang một giao diện khác. Khi thu gọn, giữ trạng thái chi tiết
để mở lại được, và đưa focus về điểm thao tác hợp lệ nếu phần đang focus được
thu lại. Một click/phím toggle không submit thêm, gọi model, tính lại lá số
hay khởi động lại worker. Thử toggle liên tục trong lúc stream/chỉnh dữ liệu.

Ràng buộc triển khai: một conversation/task/artifact state và một nguồn draft.
Hai bộ composer, renderer hoặc pending state độc lập không phải kiến trúc đích.
Có thể giữ widget rồi reflow; nếu phải đổi view thì việc phục hồi đầy đủ trạng
thái cần kiểm chứng. Nút mở/thu là affordance nhẹ trên chính box, không là
entry point sang một màn hình mới. Giữ cách nhập và ngôn ngữ điều khiển nhất
quán ở hai mức; phương án bố cục đầu tiên đặt ô nhập trên cùng ở cả hai mức.

## Triển khai trong source

- Compact/full dùng một `ChatComposer` nhiều dòng và một `ChatStreamWidget`.
  Enter gửi, Shift+Enter xuống dòng; không tự mở full khi gửi/nhận kết quả.
- Compact ưu tiên lượt hiện tại; full mở thêm lịch sử đã giữ nguyên widget.
  Bản nháp, caret/selection, focus, artifact/revision, điểm chọn trên hình và
  chi tiết đang mở được bảo toàn qua đổi kích thước. Revision mới khôi phục
  trạng thái editor từ renderer cũ.
- Ô chat tăng chiều cao theo nội dung và chiều rộng thực, giới hạn theo màn
  hình. Điểm neo phía trên giữ ổn định khi đủ chỗ. Kết quả tương tác mở từ đầu;
  stream không kéo người đang đọc trở lại cuối. Mỗi mức giữ vị trí đọc riêng.
- Bỏ navigation, speech bubble, watermark và khung lồng ở bề mặt chính.
  Form reflow các widget sẵn có; lá số giữ cùng canvas khi thu/phóng; chi tiết
  và editor mở tại chỗ. Thao tác phụ nằm trong menu. Cài đặt mở modal rồi trở
  về cùng chat thay vì thay chat bằng một trang tiện ích.
- Nút gửi trở thành Stop khi model đang chạy; khi thao tác artifact đang
  chạy, giữ kết quả cũ và chặn submit chồng. Toast/lỗi hiện trong box.
- Resize/disclosure hỗ trợ reduced motion qua thiết lập macOS hoặc
  `RAT_REDUCE_MOTION=1`. Làm mới chat giữ lựa chọn full/compact của người dùng.

Bản xem trước và log kiểm tra: [audit UI](../audit/rat_one_box_ui_20261012/REPORT.md).
Đây là kiểm tra giao diện bằng dữ liệu minh họa và thao tác dịch vụ thật;
không phải benchmark model. Model, bộ điều phối và pipeline NCKH không thay.

## Quan sát trước triển khai

- Cửa sổ thật đã xem có navigation bar, assistant card, artifact card, form
  frame và ô nhập phía dưới. Các lớp border/padding làm form thành trọng tâm.
- `view_renderer.py` tạo frame cho card, table và form. Form stylesheet áp lên
  `QFrame` cũng có thể làm các label con mang thêm border/padding; cần scope
  style rõ trong lúc triển khai, không chỉ xóa một viền ngoài.
- Form dựng tất cả trường theo hàng label/input cố định; label rộng 80 px.
  Nội dung dài hoặc thay đổi mục đích vẫn đi qua cùng cấu trúc đó.
- `omnibar.py` có các kích thước compact/expanded/interaction định trước.
  Gửi yêu cầu mở bề mặt interaction; lựa chọn expanded trước đó được giữ.
- `set_expanded` hiện ẩn quick composer/speech bubble để hiện chat stream và
  chuyển focus sang `full_chat_input`; compact dùng `chat_composer_input`.
  Đây là hai cách dựng bề mặt cần hợp nhất theo yêu cầu mới. Chỉ làm animation
  resize giữa chúng không đủ đảm bảo cùng trải nghiệm và trạng thái nhập.
- App **đã có** animation resize và một số animation khác. Vấn đề không phải
  hoàn toàn thiếu animation; cần nối các trạng thái nội dung có ý nghĩa.
- Cùng revision được giữ widget; khi revision đổi, `ArtifactPanel` tạo renderer
  mới, khôi phục draft rồi thay renderer. Cần kiểm tra tiếp khả năng giữ focus,
  lựa chọn trên hình, scroll và chuyển động khi thay nội dung.

Các nhận xét này dựa trên UI/code; chưa có đo usability, contrast hoặc latency
cho phương án mới. Màu giấy/ink và nội dung chuyên môn vẫn có thể dùng tiếp.

## Nguyên tắc bố cục

1. **Một bề mặt chính.** Phân cấp bằng khoảng cách, typography và nhóm nội
   dung. Chỉ dùng khung khi nó giải thích một quan hệ thật như hai kết quả so
   sánh; bỏ lồng card/form theo tầng kỹ thuật.
2. **Hình dạng theo nội dung.** Câu hỏi ngắn dùng ít không gian; danh sách
   có chiều cao theo số dòng; hình có vùng nhìn phù hợp; chi tiết mở liền tại
   chỗ. Có giới hạn theo màn hình và vùng đọc; không phóng cả app cho mọi reply.
3. **Giữ một điểm định hướng.** Ô yêu cầu là điểm vào ổn định. Kết quả mở phía
   dưới nó trong phương án thử đầu tiên. Khi mở rộng, giữ cùng điểm neo thay
   vì dời cả cửa sổ quanh tâm. Không ép autoscroll khi người dùng đang đọc.
4. **Chỉnh ở dữ liệu đang nhìn.** Ngày/giờ có thể chọn để sửa; file có thao tác
   ở dòng file; phần đang chọn trên hình có thông tin ngay cạnh. Menu phụ chứa
   thao tác ít dùng. Không biến mọi metadata thành nút cùng mức nhấn mạnh.
5. **Tiết lộ chi tiết theo nhu cầu.** Tóm tắt hoặc hình chính hiện trước;
   thông tin bổ sung nối vào cùng nội dung. Luôn có cách quay lại và thao tác
   bằng bàn phím; chức năng cần thiết không chỉ hiện khi hover.

Wireframe ý tưởng, không phải screenshot hoặc output AI:

```text
Khi cần bổ sung dữ kiện        Khi có kết quả

  [ô yêu cầu ổn định]            [ô yêu cầu ổn định]
  một câu hỏi cụ thể             ngày · giờ chỉnh được · nơi
  lựa chọn/nhập tiện dụng        kết quả chính, không lồng thẻ
                                thông tin của phần đang chọn
                                chi tiết mở liền tại chỗ
```

Giao diện nên wrap/stack được với tiếng Việt dài và tăng font. Bảng chuyên môn
có thể scroll khi cần; tránh nhiều vùng scroll lồng nhau và label cố định gây
cắt chữ. Giữ các giới hạn kích thước cần thiết cho đọc và thao tác, nhưng dùng
content/layout policy thay vì một hình dạng duy nhất cho mọi trạng thái.

## Nguyên tắc chuyển trạng thái

Chuyển động phải chỉ ra quan hệ: nội dung đang mở từ đâu, phần nào được đổi,
thao tác nào đang chờ. Không thêm chuyển động liên tục để làm UI “có sức sống”.
Khi người dùng tắt/giảm motion, cấu trúc và phản hồi vẫn rõ.

| Chuyển trạng thái | Hành vi cần thử | Điều cần giữ |
| --- | --- | --- |
| Nhập → cần hỏi thêm | Câu hỏi và lựa chọn liên quan mở bên dưới ô nhập, bề mặt tăng vừa đủ. | Focus, dữ kiện đã nói và điểm neo cửa sổ. |
| Gửi → đang xử lý | Phản hồi ngay tại vị trí vừa gửi; trạng thái ngắn gắn với công việc thật. | Nội dung đang đọc và khả năng dừng. |
| Đang xử lý → có kết quả | Vùng nội dung tăng theo kết quả; cập nhật vùng đã sẵn sàng, không flash một trang trống. | Vị trí người dùng và trạng thái các kết quả khác. |
| Kết quả → chỉnh metadata | Một editor nhỏ mở từ đúng nhãn; Apply/Cancel và lỗi ở gần giá trị. | Kết quả gốc vẫn nhìn được, có thể thoát bằng bàn phím. |
| Apply → đang tính → đã cập nhật | Giữ hình trước trong lúc chờ, đánh dấu nó là kết quả cũ; khi xong cập nhật phần liên quan và báo thay đổi ngắn. | Không hiển thị input mới như metadata của số liệu cũ đã được tính xong. |
| Kết quả → chi tiết | Mở liền nội dung liên quan, giữ chỗ của phần được chọn. | Selected point/row và khả năng đóng/quay lại. |
| Lỗi → sửa | Giữ dữ liệu và editor; lỗi nêu cách sửa cạnh giá trị hoặc thao tác liên quan. | Không reset cả form/canvas. |
| Dừng/hủy/reset | Dừng feedback xử lý; giữ kết quả hợp lệ nếu công việc chỉ bị hủy. Reset chủ động mới xóa bề mặt theo semantics hiện có. | Callback muộn không làm UI đổi lại. |

Cần kiểm tra cập nhật theo artifact/field ổn định để nối trạng thái, không
dùng crossfade toàn cửa sổ che việc nội dung bị thay mới. Hủy animation trước
và cập nhật đích mới khi input đến liên tục; không để click bàn phím phải chờ
animation kết thúc. Chưa chốt easing/duration trước khi thử prototype.

## Prototype và kiểm tra thiết kế

Đề xuất một prototype dùng các state/result fixture đã có, ghi rõ là minh họa
thiết kế. Không fake một model hiểu được mọi câu. Cần thực hiện cùng chuỗi:

1. Mở yêu cầu, bổ sung dữ kiện rồi xem kết quả.
2. Sửa một giá trị tại chỗ; thử thành công, lỗi và Cancel.
3. Mở/đóng chi tiết, đổi lựa chọn và giữ vị trí đọc khi có update.
4. Thử kết quả ngắn, hình lớn, tiếng Việt dài, tăng font và bề mặt hẹp.
5. Dùng bàn phím và reduced motion; thử dừng/reset trong lúc xử lý.
6. Compact → full → compact khi đang gõ, chọn text, stream, nhập bổ sung,
   chỉnh kết quả và đọc chi tiết. Không mất draft/selection, đổi artifact đích,
   tự submit hay thực thi lại; full chỉ tăng chỗ nhìn.
7. Dùng lịch, tệp và lá số từ cùng một điểm nhập ở cả hai mức. Xác nhận không
   có capability nào bắt người dùng vào màn hình chức năng riêng.

Review trực tiếp: có nhận ra phần vừa đổi không, có phải tìm lại nơi nhập
không, có bị nhảy vị trí đọc không, điều khiển có xuất hiện ở nơi mong đợi
không. Một ảnh tĩnh hoặc thêm hiệu ứng không đủ để kết luận UI đã bớt cứng.

Các regression về draft, ID/revision, precision, export và cancel/reset được giữ trong bộ kiểm tra. Source và app chạy từ source đã cập nhật; model và claims nghiên cứu giữ nguyên. Chưa có nghiên cứu usability hoặc đo cảm nhận liền mạch với người dùng; cần phản hồi trực tiếp cho vòng chỉnh tiếp.
