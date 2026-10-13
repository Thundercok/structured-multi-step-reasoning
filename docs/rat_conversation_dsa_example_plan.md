# RAT: hoàn thiện hội thoại xuyên suốt bằng một ví dụ DSA

Ngày: 2026-10-13, Asia/Saigon. Trạng thái: đã có baseline phần mềm và regression
cho core/UI; chưa đạt tiêu chí chấp nhận toàn bộ luồng bằng model thật.
Smoke development đã lưu có timeout và lỗi nội dung; xem
[review smoke](../audit/rat_conversation_core_codex_review_20261013/smoke_review.json).

## Vấn đề và phạm vi đã xác nhận

Người dùng muốn chuyển trọng tâm từ nhiều vòng sửa UI sang một công việc chạy
được từ đầu đến cuối trên RAT thật, kèm minor UI changes. Người dùng chọn DSA
làm ví dụ cho cuộc trò chuyện và đã làm rõ: dùng ví dụ DSA để thử luồng RAT.
Đây là công việc cải thiện core hội thoại chung, không phải yêu cầu dựng một
sản phẩm gia sư hoặc một màn hình DSA riêng.

Quyết định UI ngày 2026-10-13 đã chốt: chỉ chỉnh cách đọc code, notes và khoảng
cách. Chuột tiếp tục đứng bên trái trên canvas trong suốt và là nhân vật trang
trí. Chạm Chuột chỉ tạo phản ứng giãy/emote tại chỗ. Ghi chép thuộc từng lượt
chat; truy cập và sửa bằng chính dòng ghi chú. Một composer và cùng ngữ cảnh
ở full/compact. Personality vui nhẹ nằm ở cách phản hồi và emote.
Baseline source đã nối định danh lượt/execution, notes/version/event và UI vào
runtime chung. Kiểm tra phần mềm không xác nhận model hiểu đúng ví dụ DSA;
cấu hình model không đổi trong lượt chuẩn bị publish.

## Mục tiêu và câu chuyện sử dụng

1. Người dùng hỏi tiếp về ví dụ đang đọc mà không phải nhắc lại đề hoặc dữ kiện.
2. Một sửa đổi thay đổi đúng kết quả đang nói tới; lượt trước vẫn giữ bản trước.
3. Ghi chú, kết quả, thao tác và trace được gắn với đúng lượt/công việc.
4. Đổi kích thước, dừng hoặc gặp lỗi vẫn giữ draft và dữ liệu đã được nhận.
5. Bàn giao một luồng chạy trên native RAT từ cùng source đã kiểm tra.

Là người đang hỏi về DSA, tôi muốn hỏi “vì sao đoạn này?” để tiếp tục đúng ví dụ.
Tôi muốn đổi một dữ kiện để xem tác động mà không bắt đầu lại.
Tôi muốn mở lại đoạn trước, sửa ghi chú hoặc dừng khi câu trả lời đi sai hướng.
Những nhu cầu này cũng áp dụng cho lịch, tìm tài liệu và các kết quả khác.

## Cuộc trò chuyện dùng để thiết kế

Đoạn dưới là kịch bản sản phẩm đề xuất, không phải transcript model đã chạy.
Binary search chỉ là ví dụ đầu tiên; không dùng các câu này làm keyword router.

| Lượt | Người dùng | Hành vi mong muốn của RAT |
| --- | --- | --- |
| 1 | “Mình chưa hiểu binary search. Giải thích bằng ví dụ nhỏ, đừng đưa code vội.” | Trả lời gọn bằng một ví dụ; giữ yêu cầu về cách giải thích có nguồn từ câu người dùng. |
| 2 | “Dùng mảng [2, 4, 6, 8, 10], tìm 8 đi.” | Dùng đúng mảng và mục tiêu người dùng vừa cung cấp. Một bảng ngắn có thể nằm ngay trong phản hồi. |
| 3 | “Sao phải dùng mid + 1?” | Hiểu đây là hỏi thêm về bước vừa trình bày. Giữ công việc và ví dụ hiện tại; không đòi nhập lại toàn bộ đề. |
| 4 | “Đổi sang tìm 6 nhé.” | Cập nhật mục tiêu trong cùng ví dụ, tạo phiên bản mới. Lượt tìm 8 vẫn đọc được với nguồn và liên kết rõ. |
| 5 | “Quay lại đoạn mid + 1 lúc nãy.” | Dẫn về đúng lượt/phần kết quả cũ. Ngữ cảnh không được lấy chỉ từ widget gần nhất. |
| 6 | Dừng khi đang xử lý, rồi hỏi tiếp | Hủy đúng execution; callback muộn không được ghi vào lượt mới. Giữ kết quả đã commit và draft đang nhập. |

Nếu có hai ví dụ và tham chiếu mơ hồ, hỏi người dùng chọn đúng ví dụ. Nếu chỉ
có một ví dụ phù hợp, dùng dữ kiện đã có. Một câu hỏi phụ không tự thành công
việc mới; đổi mục tiêu thực sự cần được phản ánh trong trạng thái chung.

Để đối chiếu nội dung mẫu: với khoảng inclusive [0, 4], bước đầu có mid=2,
a[mid]=6; tìm 8 chuyển l=3, sau đó mid=3 và tìm được index 3. Tìm 6 dừng ngay
ở mid=2. Đây là ví dụ do người viết kế hoạch kiểm tra, không phải evidence của
model hoặc của checker DSA đang có.

## Core chung cần hoàn thiện

| Yêu cầu P0 | Tiêu chí chấp nhận |
| --- | --- |
| Lượt và execution có định danh, gắn với công việc hiện tại | Notes/event/result biết lượt sở hữu và execution tạo ra chúng. Direct action có lượt tương tác và liên kết kết quả đích; không mặc định gắn vào phản hồi mới nhất. |
| Dữ liệu được giữ theo nguồn và phiên bản | Sửa note/kết quả tạo phiên bản mới; bản cũ giữ nội dung. Quote xác thực thuộc đúng lượt. Generation chặn callback muộn nhưng không thay thế ID lượt/execution. |
| Tham chiếu hội thoại và kết quả dùng chung | Câu nói và action trực tiếp tham chiếu cùng ID/revision. Chọn lượt cũ không làm mất ví dụ đang làm; phiên bản stale bị từ chối và giữ draft. |
| Model chọn cách tiếp tục bằng ngữ cảnh thật | Hỏi thêm, trả lời câu hỏi phụ, sửa hoặc tiếp tục đi qua runtime chung. Dữ kiện còn thiếu là observation có cấu trúc; chỉ hỏi phần cần để tiếp tục. Quyết định không được cứu bằng kịch bản if/else theo tên môn/câu mẫu. |
| Thông báo công việc dựa trên event | “Đã ghi”, “đã chạy”, “đã kiểm tra” chỉ xuất hiện khi có event/evidence tương ứng. Plan và lời giải thích của model được phân biệt với thao tác thực. |
| Hủy/lỗi giữ trạng thái hợp lệ | Không commit kết quả từ execution đã hủy vào lượt kế tiếp. Lỗi không xóa kết quả hoặc note đã commit. |
| Chạm nhân vật chỉ là tương tác trang trí | Có phản ứng giãy/emote; không gọi model/operation, mở note, điều hướng chat, đổi dữ liệu, làm mất draft/caret/focus hoặc dời ô chat. Reduced motion dùng emote tĩnh. |

Tận dụng `AssistantRuntime`, registry, dispatcher, `ArtifactStore`,
`WorkNotebook`, conversation history và renderer hiện có. Đường thiết kế
notes theo lượt nằm trong
[kế hoạch notes](rat_turn_notes_plan.md).
Phần quyết định continuation/làm rõ nối với
[ADR-002](adr-002-rat-adaptive-interaction.md).

Kết quả chỉ bằng chữ cũng cần tham chiếu về lượt/snapshot để hỏi tiếp được.
Ví dụ DSA trước hết dùng text, code block hoặc bảng chung; không cần renderer
thuật toán riêng. Phạm vi đầu tiên là công việc trong hội thoại đang mở.
Thiết kế nhiều công việc đồng thời và lưu qua lần khởi động sau nằm ở P2.

### Vai trò kiểm chứng

Verifier hiện tại hỗ trợ số học với scope rõ; chưa kiểm chứng code DSA,
độ phức tạp hoặc tính đúng tổng quát của thuật toán. Khi chưa chạy checker phù
hợp, lời giải thích DSA không mang nhãn “đã kiểm chứng”. Các kiểm tra lifecycle
có thể xác nhận ID/revision/hủy nhưng không xác nhận lời giải thích là đúng.

Kịch bản DSA cần đối chiếu nội dung với reference được review và lưu raw output.
Nếu cần checker cho một dạng kết quả cụ thể, đăng ký vào contract verifier chung
và ghi phạm vi kiểm tra. Chạy một số input không chứng minh chương trình đúng
với mọi input. Code execution tùy ý chưa nằm trong lát cắt này.

## Minor UI changes đã chốt phạm vi

Giữ bố cục native và vị trí Chuột. Người dùng chọn mức 1: chỉ chỉnh cách đọc.
Phạm vi gồm:

- Code đọc được, giữ indentation, chọn/copy thuận tiện qua thành phần hiện có.
- Notes là dòng nhẹ trong đúng lượt; editor mở tại chỗ; nguồn/lịch sử mở thêm.
- Spacing chỉ sửa tại chỗ nội dung thực bị khó đọc. Trạng thái và trace sẵn có
  dùng cùng event core; không bổ sung một thanh nút gợi ý mới.

Không có notebook/panel ghi chú riêng hoặc đường mở note qua nhân vật.
Click handler, tooltip và accessible name của Chuột cần cùng phản ánh hành vi
trang trí. Callback trong native app và preview đã được cập nhật nhất quán,
với regression Qt cho emote, notes inline và draft/focus. Chấp nhận trải nghiệm
native từ người dùng vẫn còn chờ.

## Phạm vi còn lại

- P1: dùng lại kiểm chứng đã đăng ký cho các kết quả có scope hỗ trợ;
  mở thêm nguồn/tài liệu khi được yêu cầu. Nút gợi ý theo ngữ cảnh không nằm
  trong đợt minor UI đã chọn.
- P2: nhiều công việc đồng thời, persistence qua restart, checker DSA chuyên
  môn hoặc sinh presentation khai báo linh hoạt hơn sau khi có nhu cầu thật.
- Không dựng khóa học/curriculum, hồ sơ đánh giá năng lực DSA, IDE hoặc một
  ứng dụng học tập riêng trong đợt này; người dùng đã xác định DSA là ví dụ.
- Không đưa DocAI vào RAT, đổi default model hay thay pipeline/bộ điều phối
  NCKH trong phạm vi đề xuất này.

## Kiểm tra và tiêu chí bàn giao

Các mục dưới là mục tiêu nghiệm thu đề xuất, không phải số đo đã đạt:

- 6/6 bước trong kịch bản có đúng ownership/revision và dữ liệu kỳ vọng trong
  kiểm tra contract. Không có ghi muộn sau hủy, chạy lại khi toggle hoặc mất draft.
- Có transcript model thật cho câu gốc và một số cách diễn đạt mới; ghi riêng
  lỗi hiểu yêu cầu, mất trạng thái, thao tác sai và lỗi nội dung. Không thay
  model thất bại bằng đáp án mẫu thành công.
- Review mức đúng của quyết định và lời giải thích riêng với PASS của phần mềm.
  Ghi token prompt/completion, thời gian model, tool/verifier và latency thực.
  Chốt mục tiêu latency hoặc tỷ lệ thành công sau khi có baseline.
- Người dùng thử toàn bộ luồng trên native RAT ở full/compact. Review cả khi
  hỏi tiếp, sửa, mở bản cũ và dừng; không chỉ xem ảnh fixture.
- Chạm Chuột ở cả hai kích thước chỉ phản ứng trang trí; không mở note/trace,
  cuộn chat, gửi yêu cầu hoặc làm mất focus của composer/editor đang nhập.

Đây là kiểm tra phát triển sản phẩm RAT. Không dùng các lượt DSA này làm kết
quả bài báo hoặc bằng chứng vượt Stage 0. Dữ liệu/experiment nghiên cứu giữ
quy trình review, split và entry point độc lập theo AGENTS.md.

## Trình tự và điểm duyệt

1. **Chốt hợp đồng hội thoại.** Phạm vi minor UI và tương tác trang trí đã được
   người dùng chọn; duyệt cách giữ/sửa/tham chiếu dữ liệu trước mốc core.
2. **Hoàn thiện core chung.** ID lượt/execution, notes/version/event và đường
   continuation; kiểm tra Python độc lập Qt. Sau đó thử luồng bằng model thật
   và review các lỗi trước khi mở rộng.
3. **Nối vào native RAT và chỉnh UI nhỏ.** Dùng core thật trong app chính;
   kiểm tra cùng cuộc trò chuyện, cùng composer và Chuột ở cả hai kích thước.

Không có deadline đã cam kết. Mỗi mốc có kết quả cụ thể để người dùng duyệt
trước mốc tiếp theo; không kéo dài việc duyệt từng pixel.

## Câu hỏi còn mở

- Người dùng: các chỉnh sửa hợp đồng hội thoại trước mốc core nếu có;
  binary search là ví dụ minh họa và có thể đổi mà không đổi kiến trúc.
- Engineering: reference cho phản hồi chỉ bằng chữ nên nối vào turn snapshot
  và artifact store hiện có thế nào để tránh thêm một nguồn trạng thái riêng?
- Engineering/product: sau baseline, lượt hỏi hoặc cách trình bày nào thực sự
  giúp tiếp tục công việc, và phần nào tạo nhiễu?

Các lựa chọn engineering sẽ được giải bằng source và test trong mốc core;
không yêu cầu người dùng chọn tên lớp hoặc chi tiết kỹ thuật.
