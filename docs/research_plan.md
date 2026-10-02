# Định hướng NCKH

## Sản phẩm cần đạt

Thứ tự ưu tiên: **bài báo NCKH → pipeline nghiên cứu tái lập được → app đơn giản
cho người ít rành công nghệ**. Một kết quả âm có phương pháp đúng, phân tích rõ
và tái lập được vẫn là kết quả nghiên cứu. Không đặt điều kiện phải chứng minh
phương pháp của nhóm luôn tốt hơn.

Tên đề tài làm việc: **Điều phối chiến lược suy luận và quyết định dừng theo
ngân sách cho mô hình ngôn ngữ nhỏ**.

Đối tượng nghiên cứu là bộ điều phối trên mô hình nền cố định. Phạm vi đầu tiên
không cần huấn luyện lại mô hình nền. Đo chất lượng và chi phí trên bài toán có
đáp án kiểm chứng được trước khi mở rộng sang trợ lý tài liệu cá nhân.

## Câu hỏi và giả thuyết

**RQ1:** kết hợp chọn chiến lược ban đầu và quyết định có chạy chiến lược tiếp
theo hay không có cải thiện đánh đổi accuracy–token so với chiến lược cố định
hoặc chỉ chọn một lần ở đầu vào không?

H1: full policy cải thiện `accuracy − lambda × generated_tokens/1000` trên test
so với one-shot router tại lambda đã chốt trước. Luôn báo cáo cả accuracy và
token; tăng utility không đồng nghĩa với cải thiện cả hai chỉ tiêu.

**RQ2:** lợi ích đến từ định tuyến, quyết định dừng hay công cụ tính toán?
So sánh full policy, ladder only, entry without escalation, one-shot router và
từng chiến lược cố định. Các policy dùng chung mẫu đầu ra để tránh nhầm dao động
sinh câu trả lời với hiệu quả của controller.

**RQ3:** kết quả thay đổi thế nào theo loại câu hỏi, ngân sách và generation
seed? Phân tích câu được cứu sau escalation, câu đúng bị làm sai, confidence cao
nhưng đáp án sai, và chi phí tăng mà không cải thiện đáp án.

Các giả thuyết đang chờ thực nghiệm. Thuật toán hiện tại tối ưu điểm cắt từng
bước khi giá trị downstream cố định; điều đó không bảo đảm tối ưu chung mọi
policy hoặc tổng quát tốt trên dữ liệu mới.

## Tính mới cần kiểm chứng

Hướng đóng góp dự kiến là đánh giá sự kết hợp của entry routing và stopping
dựa trên đầu ra trung gian, với một mô hình nhỏ cố định. Cần chỉ ra điều kiện
có ích và thất bại. CoT, voting, tool calling hay Bellman tự chúng không tạo
thành tuyên bố mới.

| Công trình cần đối chiếu | Quan hệ với đề tài |
| --- | --- |
| [Self-Consistency](https://arxiv.org/abs/2203.11171) | Lấy nhiều lời giải và bỏ phiếu đã có trước; dùng như thành phần đối chứng |
| [Tree of Thoughts](https://arxiv.org/abs/2305.10601) | Tìm kiếm qua các bước suy nghĩ; adapter hiện tại chỉ chọn giữa lời giải hoàn chỉnh |
| [Route to Reason](https://arxiv.org/abs/2505.19435) | Định tuyến mô hình và chiến lược; one-shot router trong repo là baseline nội bộ, chưa tái lập đầy đủ paper |
| [BEST-Route](https://arxiv.org/abs/2506.22716) | Định tuyến thích nghi cùng phân bổ tính toán; cần làm rõ phần trùng và khác trước khi chốt novelty |

Đây là danh sách khởi đầu, chưa phải tổng quan đầy đủ. Bản thảo phải đối chiếu
không gian hành động, tín hiệu quyết định, cách học policy và cách đo. Nếu phần
thuật toán đã có trước, thu hẹp đóng góp sang đánh giá thực nghiệm và giới hạn
trong bối cảnh đã chọn.

## Mốc hoàn thành

| Mốc | Sản phẩm | Điều kiện hoàn thành |
| --- | --- | --- |
| M0: phạm vi | RQ, prior-art matrix, protocol | Ghi trước metric chính, baseline, lambda, seeds và giới hạn claim |
| M1: dữ liệu | Dataset có nguồn, phiên bản, đáp án được kiểm tra | Tách nhóm bài gốc giữa train/calibration/test; test chưa xem; không thêm tiền tố để tăng cỡ mẫu |
| M2: pilot | Raw outputs của model thật trên development | Kiểm tra parser, token, confidence và thời gian; chốt prompt/model snapshot trước test |
| M3: thực nghiệm chính | Các run độc lập và bảng so sánh tái lập | Mục tiêu ban đầu ít nhất 3 generation seeds định trước; chọn cỡ mẫu theo pilot và độ rộng khoảng tin cậy |
| M4: bài báo | Bản thảo + artifact index | Mỗi bảng có manifest/raw log; báo cáo ablation, thất bại, giới hạn và kết quả âm |
| M5: demo | Luồng app tối thiểu | Người ít rành công nghệ thực hiện được tác vụ chính; đo usability riêng |

M0 và hạ tầng thí nghiệm đã được phác thảo trong lần chỉnh này. M1–M4 còn cần
dữ liệu được duyệt, chạy mô hình thật và viết kết quả. Smoke test không thay thế
các mốc đó. Gate Stage 0 đang giữ nguyên: đọc protocol Stage 0 trước khi chạy
chương trình đo/huấn luyện Qwen/Meta-Reasoner đã bị đóng băng. Việc thêm runner
không tự xác nhận gate đã đạt.

## Nhánh nghiên cứu và ứng dụng

Nhánh chính dùng câu hỏi tự chứa đủ dữ kiện, để quy lỗi cho chiến lược và
controller. Câu hỏi về quy chế trường cần nguồn và ngày hiệu lực; khi chưa có
thì không dùng làm ground truth thực nghiệm chính.

Nhánh phụ của RAT dùng tác vụ tìm file thật: tìm slide Calculus theo tên, môn,
nội dung, và cách hỏi tiếng Việt/Anh. Người dùng cần danh sách file liên quan,
không một tên file được chọn trước; chưa có lần tìm đúng được xác nhận làm mốc.
Kiểm tra liên kết document–chunk trước khi chỉnh xếp hạng (xem
[index_integrity.md](index_integrity.md)). Duyệt nhiều file và mức relevance
cho mỗi query, ưu tiên Precision@5, nDCG@10 và độ trễ; chỉ báo Recall@k khi nêu
rõ phạm vi tập relevant đã duyệt. Không trộn các metric này vào accuracy của
bài toán suy luận.

Demo tối thiểu: nhập yêu cầu → thấy vài kết quả với tên và vị trí rõ → mở đúng
file → có trạng thái không tìm thấy hoặc đề nghị làm rõ khi cần. Lịch học,
mascot, animation và thêm cửa sổ chưa nằm trên đường hoàn thành bài báo.

## Dàn ý bản thảo

1. **Giới thiệu:** câu hỏi phân bổ tính toán, phạm vi và đóng góp đã kiểm chứng.
2. **Nghiên cứu liên quan:** strategy routing, adaptive compute, stopping và uncertainty.
3. **Phương pháp:** entry predictor, ladder, confidence, utility và giới hạn thuật toán.
4. **Thực nghiệm:** nguồn dữ liệu, grouped split, model/prompt/version, baselines, chi phí và thống kê.
5. **Kết quả:** accuracy–token, paired differences, ablation, biến thiên theo seed; không điền số minh hoạ.
6. **Phân tích lỗi:** confidence sai, escalation gây hại, overhead và tính tổng quát.
7. **Demo:** phần ngắn hoặc phụ lục, chỉ các khả năng đã chạy được.
8. **Kết luận/tái lập:** phát hiện có bằng chứng, artifact và câu hỏi còn mở.

## Bàn giao cho cộng tác viên/Claude

Đọc tài liệu này và `research_protocol.md` trước khi thêm tính năng. Việc tiếp
theo là duyệt câu hỏi/đáp án và nguồn dataset, cố định split/model snapshot,
rồi chạy pilot có log. Không lấy benchmark mô phỏng làm kết quả NCKH. Mỗi đề
xuất tính năng cần giải thích nó kiểm chứng RQ nào hoặc gỡ mốc nào.
