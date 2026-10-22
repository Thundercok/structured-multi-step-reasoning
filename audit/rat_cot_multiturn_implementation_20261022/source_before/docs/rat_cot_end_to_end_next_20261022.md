# Bước tiếp theo: hoàn thiện một luồng RAT–CoT xuyên suốt

Ngày 2026-10-22, Asia/Saigon. Chuẩn bị độc lập trong lúc Anti xử lý runtime; chưa thay đổi production, default model, policy approval hoặc research protocol.

## Kết quả cần đạt

Người dùng thực hiện một công việc nhiều lượt trong RAT: yêu cầu → ngữ cảnh có định danh → chiến lược suy luận → kiểm tra/dừng/ngân sách → kết quả và bằng chứng trở lại đúng cuộc trò chuyện. RAT triển khai phương pháp; headless pipeline đánh giá nó. Không chia thành hai sản phẩm hoặc ép mọi thao tác đơn giản phải gọi model.

Dùng lại kịch bản DSA đã được chọn trong [kế hoạch hội thoại](rat_conversation_dsa_example_plan.md). Không tạo tutor, màn hình DSA, renderer thuật toán hoặc controller thứ hai.

## Source hiện tại đã có gì

| Điểm nối | Đã có | Còn cần hoàn thiện hoặc chứng minh |
| --- | --- | --- |
| Composer → request | Omnibar tạo ExecutionRequest với turn/execution ID, generation, history và task context. | Cùng request phải giữ đủ ngữ cảnh qua nhánh reasoning. |
| Request → worker | create_execution_worker chọn worker; có nhánh reasoning và policy validation. | UI đọc QApplication property ratReasoningEngine; trong source đã tìm, chỉ tests gắn property này. Cần composition host rõ ràng cho chế độ được phép. |
| Worker → controller | OnlineReasoningWorker gọi engine/controller và chuyển budgets, deadline, cancel, IDs. | Nhánh factory hiện chuyển request.query và controls, chưa chuyển history/task context sang reasoning worker. Cần input snapshot có nguồn, không chỉ prompt cuối. |
| Controller → cuộc trò chuyện | execution_response chuyển answer, ledger, policy/bundle và ID về consumer chung. | Chứng minh nhiều lượt, revision, cancel và callback muộn trên cùng UI. |
| Composer → composed policy → result | Có test một lượt bằng synthetic backend trong tests/test_flow_interaction.py. | Mở rộng từ lát cắt đã có sang kịch bản nhiều lượt; test source hiện có chưa phải native model acceptance. |

Các nhận xét trên là source inspection tại thời điểm chuẩn bị, không phải kết luận mọi kết nối đều thiếu. Cần đối chiếu lại sau khi Anti hoàn tất. Không sửa singleton/loader để tự bật một policy chưa được duyệt.

## Lát cắt thực hiện sau Anti

1. **Hoàn thiện composition host bằng cách dùng factory và model owner hiện có.** Chế độ development có thể inject synthetic engine với nhãn rõ. Production chỉ nhận bundle/backend được duyệt; trạng thái chưa có policy phải trung thực, không gắn nhãn online_policy cho fallback khác. Không tự tải thêm model hay mở ngân sách.
2. **Giữ ngữ cảnh cho reasoning trong ExecutionRequest chung.** Chuẩn bị snapshot của câu hỏi, lượt được tham chiếu, dữ kiện hiện tại và revision. Chuyển snapshot qua adapter hiện có, giữ riêng câu người dùng nhập để hiển thị. Không lấy nội dung từ widget gần nhất làm source of truth. Nếu prompt/context khác harness, ghi rõ khác biệt; không suy cùng chất lượng chỉ vì dùng cùng controller.
3. **Kiểm tra toàn luồng bằng fixture trước.** Tận dụng test composer/worker đang có, ghi observed backend input và output IDs để kiểm các hàng dưới. Không thêm bộ audit độc lập chỉ chấm helper functions.

## Kịch bản chấp nhận thống nhất

| Bước | Tương tác đã chọn | Cần quan sát trên luồng thật của RAT |
| --- | --- | --- |
| 1 | Giải thích binary search bằng ví dụ, chưa đưa code. | Engine được chọn có provenance; trả kết quả về cùng turn/execution. |
| 2 | Dùng mảng [2,4,6,8,10], tìm 8. | Backend input có mảng/mục tiêu và liên hệ đúng chủ đề ở lượt 1. |
| 3 | “Sao phải dùng mid + 1?” | Backend input tham chiếu đúng ví dụ/lượt 2; không mất ngữ cảnh khi đi vào reasoning worker. |
| 4 | “Đổi sang tìm 6.” | Target mới là 6; tạo revision mới, giữ nguyên kết quả và dữ kiện của lượt tìm 8. |
| 5 | “Quay lại đoạn mid + 1.” | Tham chiếu đúng lượt cũ; mở kết quả cũ không ghi đè công việc hiện tại. |
| 6 | Dừng trong lúc xử lý, sau đó hỏi tiếp. | Hủy đúng execution; callback cũ không ghi vào lượt mới; kết quả đã commit và draft được giữ. |
| 7 | Budget=0, lỗi backend hoặc thiếu dữ kiện. | Không dispatch khi quota bằng 0; failure/unresolved/cancelled hiển thị đúng, không báo completed hoặc verified giả. |

Ở mỗi bước, kiểm cùng một gói evidence: query/context snapshot có nguồn, turn/execution/generation, strategy path, stopping/status, actual cost ledger, kết quả hiển thị và verification scope. Không hiển thị raw/private reasoning.

Fixture chỉ xác nhận routing, context, lifecycle và presentation. Nó không chứng minh model hiểu DSA. Verifier số học hiện có không tự xác minh tính đúng thuật toán hoặc giải thích DSA; giữ UNKNOWN/unverified nếu chưa có checker phù hợp.

## Việc có thể làm song song ngay

- Chuẩn bị source map và các assertions nhiều lượt ở trên; đọc và tái sử dụng test composer/worker hiện có.
- Đánh dấu UI failures theo ảnh hưởng lên luồng: nhận yêu cầu, tham chiếu, hành động và khả năng đọc kết quả là acceptance của RAT–CoT; trang trí tách khỏi critical path.
- Chờ Anti hoàn tất sửa core rồi thống nhất một source snapshot trước khi sửa/run integration. Không thay các file runtime/bundle/worker đang được sửa đồng thời.

Ngân sách model thật vẫn 0. Human data review và Stage 0 giữ nguyên; chưa chạy model acceptance hoặc thay đổi phạm vi nghiên cứu. Khi có source ổn định và đủ điều kiện ngân sách, bước sau fixture mới là native acceptance trên cùng kịch bản, với raw artifacts và giới hạn rõ ràng.
