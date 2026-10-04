# RAT: hướng giao diện cho hỏi đáp và suy nghĩ cùng AI

Ngày đối chiếu nguồn: **2026-10-03**. Đây là nghiên cứu tài liệu và đề xuất thiết kế, chưa phải kết quả thử nghiệm RAT. Người dùng ưu tiên hỏi đáp, suy nghĩ cùng AI; muốn Chuột prominent, hơi cọc, cheeky, tongue-in-cheek, không cố gây cười. Người dùng đã làm rõ ưu tiên giao diện gọn, thu lại nhanh để trở về workflow đang làm. Cửa hội thoại lớn chỉ là phương án mở thêm khi cần, không phải trải nghiệm mặc định.

## Hành vi sản phẩm đã được tài liệu hóa

Raycast Quick AI hỗ trợ hỏi tiếp; `⌘J` chuyển cả lịch sử, model và đính kèm sang AI Chat, giữ ngữ cảnh khi mở rộng. [Quick AI](https://manual.raycast.com/ai/quick-ai).

Raycast AI Chat có lịch sử lâu dài, hỏi tiếp dựa trên thread, sửa tin nhắn rồi chạy lại và điều khiển lượt đang streaming. [AI Chat](https://manual.raycast.com/ai/ai-chat).

Claude Desktop trên Mac cho gọi ô nhập từ app khác và chọn năm hội thoại gần nhất. Điều đáng tham khảo là giảm công mở và quay lại việc đang làm. [Quick entry](https://support.claude.com/en/articles/12626668-use-quick-entry-with-claude-desktop-on-mac).

Raycast gom thao tác theo mục được chọn vào Action Panel; Alfred cho xem nhanh file rồi mở bằng Enter. Hai pattern giúp nghĩ về thao tác sát kết quả, nhưng không phải bằng chứng so sánh giao diện AI. [Action Panel](https://manual.raycast.com/action-panel), [Alfred previews](https://www.alfredapp.com/help/features/previews/).

## Nghiên cứu thực nghiệm và giới hạn

- **Amershi et al., CHI 2019:** 18 hướng dẫn được kiểm tra bởi 49 người làm thiết kế trên 20 sản phẩm AI. Các nguyên tắc liên quan: dễ gọi, bỏ qua, sửa sai, nhớ tương tác và thích nghi thận trọng. Đây là đánh giá hướng dẫn, không đo lợi ích của một bố cục cụ thể. [Paper](https://www.microsoft.com/en-us/research/wp-content/uploads/2019/01/Guidelines-for-Human-AI-Interaction-camera-ready.pdf).
- **AI Chains, CHI 2022:** 20 người thử cả hai giao diện; model nền giống nhau nhưng prompt, chuỗi và can thiệp khác. Cảm nhận kiểm soát và chất lượng đầu ra cải thiện; thời gian không cải thiện có ý nghĩa thống kê. Không thể quy lợi ích riêng cho bố cục; độ phức tạp là trở ngại. [Paper](https://arxiv.org/html/2110.01691v3).
- **Sensecape, UIST 2023:** N=12, so sánh workspace phân cấp với chat kèm canvas cơ bản. Người dùng khám phá nhiều khái niệm hơn; chín người thích Sensecape để hiểu sâu. Giao diện đối chứng dễ điều hướng hơn đôi chút. Mẫu nhỏ, phiên ngắn; không chứng minh hiểu biết lâu dài. [Paper](https://arxiv.org/pdf/2305.11483).
- **Script&Shift, CHI 2025:** thử usability N=12 và so sánh ngẫu nhiên N=84 giữa ba giao diện viết. Log cho thấy nhóm chat gửi lại yêu cầu nhiều hơn; nhóm có hỗ trợ tại nội dung dùng chiến lược đa dạng hơn. Kết quả chủ yếu mô tả hành vi, không chứng minh tốc độ hay chất lượng vượt trội. [Paper](https://arxiv.org/html/2502.10638v1).
- **Mark et al., CHI 2008:** thí nghiệm email N=48. Người bị gián đoạn làm nhanh hơn nhưng báo stress, bực bội và nỗ lực cao hơn. Bài học là không chỉ đo tốc độ; đây không phải nghiên cứu mascot, phần lớn mẫu là sinh viên. [Paper](https://www.ics.uci.edu/~gmark/chi08-mark.pdf).

NN/g năm 2023 theo dõi 18 người trong hai tuần, ghi 425 hội thoại. Không thấy tương quan giữa độ dài chat và đánh giá hữu ích. Đây là quan sát tự báo cáo: nhiều lượt không tự động nghĩa là thất bại. [Conversation types](https://www.nngroup.com/articles/ai-conversation-types/).

NN/g năm 2026 quan sát chatbot trên website, đề nghị tránh ép cuộn khi đọc, cho đổi kích thước và dùng nút gợi ý theo ngữ cảnh. Có ví dụ usability cụ thể, nhưng không phải so sánh trợ lý desktop. [Chatbot guidelines](https://www.nngroup.com/articles/ai-chatbots-design-guidelines/).

## Ba kiến trúc cần cân nhắc

Bảng dưới là nhận định thiết kế cho RAT, chưa phải điểm đo.

| Kiến trúc | Phù hợp | Trở ngại |
| --- | --- | --- |
| Overlay gọn | Hỏi nhanh, lấy kết quả rồi quay lại app | Đọc dài, hồi tưởng và chỉnh đáp án chật chội |
| Chat đơn giản, có lịch sử | Hỏi tiếp, đọc kỹ, so sánh ý tưởng | Cần gọi nhanh và thu gọn thuận tiện |
| Chat cùng ghi chú tùy chọn | Gom kết luận, giữ ý đã chốt | Thêm thao tác và công học cách dùng |

Sau khi người dùng làm rõ workflow, đề xuất chọn **ô gọi nhanh, thu gọn nhanh làm giao diện mặc định; lịch sử hội thoại là nền dữ liệu, không phải cửa sổ lớn bắt buộc**. Gọi Chuột → hỏi hoặc nghĩ tiếp → dùng kết quả → thu lại và trở về app đang làm. Mở rộng để đọc dài khi cần, giữ nguyên câu hỏi, vị trí đọc và bản nháp; không biến một lần hỏi thành việc phải chuyển hẳn sang workspace khác. Hướng thứ ba dành cho giai đoạn sau. Đây là lựa chọn theo ưu tiên workflow của người dùng, chưa phải kết luận giao diện hiệu quả nhất từ nghiên cứu.

## Giả thuyết thiết kế riêng cho RAT

Cửa gọi nhanh và cửa đầy đủ dùng cùng định danh hội thoại, lịch sử, bản nháp và đính kèm. Nút “Mở rộng” giữ nguyên câu đang đọc; “Cuộc trò chuyện mới” là thao tác rõ ràng. Không âm thầm đổi ngữ cảnh chỉ vì đóng cửa sổ. Thu lại bằng một thao tác, giữ câu hỏi và kết quả, trả focus về app trước đó; gọi lại tiếp tục mạch cũ. Cần chốt riêng việc sau khi thu lại còn Chuột nổi trên màn hình hay ẩn hẳn và gọi bằng phím tắt. Không tự dán kết quả vào app khác.

Một vùng duy nhất chứa đáp án chính. Nội dung ngắn vẫn gọn; đáp án dài có đủ chỗ đọc và cuộn. Khi streaming, giữ vị trí người đang đọc; nút “Xuống mới nhất” đưa họ trở lại. Có thể thay kích thước cửa sổ.

Ô nhập cố định phía dưới. “Dừng” hiện khi xử lý; “Sửa”, “Sao chép”, “Thử lại” dễ tìm sau đó. Thao tác quan trọng có nhãn; phím tắt bổ trợ. Lỗi hiển thị trong hội thoại, giữ bản nháp và cho phục hồi. Trạng thái không hoàn tất phải khác “Xong”.

Đáp án có cấu trúc theo công việc: kết luận trước, giải thích cần thiết, so sánh bằng bảng khi có ích. Đính kèm hiện thành mục có tên, có thể bỏ. AI biết gì từ tài liệu hay lịch sử phải được thể hiện đủ để người dùng hiểu ngữ cảnh. Nút “Giải thích đoạn này”, “Phản biện” chỉ xuất hiện khi liên quan.

Sau này, người dùng có thể ghim một ý sang ghi chú giữ được, chỉnh hoặc loại bỏ nó. Đó là công cụ giữ tiến triển; không phải yêu cầu đưa toàn bộ suy nghĩ lên sơ đồ.

## Hình thức và tính cách Chuột

Giữ giấy ấm, nét vẽ riêng, chút bất đối xứng ở chi tiết trang trí; chữ, lề, nút và thứ bậc thông tin phải rõ. Theo ưu tiên được người dùng làm rõ, **Chuột là nhân vật prominent của app**, không phải logo nhỏ hay vật trang trí ở góc. Có một vùng hiện diện rõ để đón người dùng, phản hồi và báo trạng thái bằng biểu cảm; khi chưa nhập, Chuột có thể chiếm sân khấu chính. Khi đọc đáp án dài, Chuột vẫn là người đối thoại nhận diện được, nhưng không che chữ hay tự chen vào bằng chuyển động lặp. Đáp án có vùng đọc đủ rộng, không bị nhốt trong bong bóng chật.

Nghiên cứu về gián đoạn ở trên không kiểm tra kích thước mascot và không đủ để kết luận mascot cần nhỏ. Ở RAT, giả thuyết cần kiểm chứng là **mascot nổi bật, hành vi kiệm và có chức năng**: biểu cảm giúp nhận biết đang chờ, đang nghĩ, đã dừng hoặc gặp lỗi; kích thước, vị trí và mức chuyển động được đánh giá cùng độ dễ đọc.

Chuột được phép cọc và khô, không cần thân thiện kiểu tổng đài. Ví dụ nguyên bản: “Ừ, đưa đây.”; phản biện: “Khoan. Chỗ này chưa khớp.”; lỗi: “Đứt giữa chừng rồi. Thử lại nhé.” Nút vẫn ghi “Thử lại”. Chất cheeky nằm ở nhịp câu và biểu cảm, không buộc mỗi lượt phải có punchline. Mức độ cọc cần kiểm chứng, nhất là lúc người dùng gặp lỗi.

## Cách kiểm chứng trước khi triển khai rộng

Đề xuất 6–8 người thử nghiệm định hình, gồm người ít rành công nghệ; mỗi phiên 45–60 phút kể cả hướng dẫn và phỏng vấn. Mỗi người làm ba loại tác vụ trên từng bố cục: chín lượt ngắn, prompt tương đương nhưng khác nội dung. Tác vụ gồm hỏi nhanh rồi sao chép, hỏi tiếp và quay lại, sửa hiểu nhầm kèm đọc dài. Cân bằng thứ tự bố cục và phiên bản tác vụ.

Dùng cùng đáp án soạn sẵn và nhịp streaming giữa phương án. Phép thử này đo điều hướng, đọc và phục hồi, không xác nhận hiệu quả suy nghĩ cùng AI. Ghi hoàn thành, tìm lại ngữ cảnh, phục hồi lỗi, mất vị trí đọc, thời gian, nỗ lực; quan sát lý do vướng. Kiểm tra bàn phím và nhận biết trạng thái.

Mẫu nhỏ giúp tìm vấn đề, không chứng minh “tốt nhất” về thống kê. Sau đó kiểm tra riêng prototype nhiều lượt với model thật, cùng cấu hình giữa bố cục, để đánh giá việc cùng suy nghĩ. Usability độc lập pipeline NCKH và Stage 0; tài liệu chưa xác nhận chất lượng model hay hiệu quả inference.
