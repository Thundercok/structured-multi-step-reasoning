# Trạng thái tích hợp RAT–CoT và giới hạn UI — 2026-10-22

Luồng context/worker/host được triển khai và kiểm trên **Widgets Omnibar**.
Bộ kiểm cuối: **115 passed in 11.36s**, gồm suite research bắt buộc.
Không dùng kết quả này để xác nhận Qt Quick hoặc chất lượng model.

Các phần đã hoàn thiện trong source hiện tại:

- ExecutionRequest cố định context ở lúc tạo, trả bản sao snapshot; evidence dùng snapshot đã thực thi. Prompt nhận history cùng refs; tham chiếu cũ được giữ ngoài cửa sổ recent-context. Explicit ref không có source bị từ chối trước dispatch.
- Host có API install_reasoning_engine và tham số inject qua resident launcher. Hội thoại được host chọn reasoning tiếp tục đi chung engine, không định tuyến lại từng câu ngắn bằng keyword. Chế độ synthetic hiển thị nhãn fixture. Default không tự tải/kích hoạt policy.
- Approved Platt calibration yêu cầu params, type, fitted state và số lượng đúng artifact/stopping thresholds. Approved isotonic artifact binding chưa được hỗ trợ thì bị từ chối rõ. Không fit/tune dữ liệu nghiên cứu hoặc cấp policy approval mới.
- Test nhập 4 lượt từ composer thật, dùng một composed synthetic engine, kiểm displayed query, backend input, lịch sử và navigation giữ draft. Đây là fixture để kiểm phần mềm.

Bản kiểm đầu có 5 failures trong tests DSA được bàn giao; các thay đổi từ chat khác vào các file shared được giữ. Bản implementation có 73 pass/1 fail ở QSignalSpy chờ signal trả sớm; helper nhận signal đã có trước wait. Bản cuối 115 đạt. Không ghi đè stdout/XML của các lần trước.

**Chưa thể gọi đây là hoàn tất luồng trên UI mới.** Source Qt Quick PDF dùng
PDFDesk.qml → QuickPDFController → selected_pdf, chưa gọi shared reasoning
factory. Prototype PaperDesk.qml là fixture riêng. Các alias repo trỏ cùng một
checkout; khác nhau là các entry points và adapters. Hai nhánh UI chưa được
nghiệm thu trên cùng cửa sổ. Kế hoạch hiện hành đã được cập nhật tại
`docs/rat_cot_end_to_end_next_20261022.md`.

Các test DSA về revision hiện có setup/commit ArtifactStore trực tiếp trong
fixture; chúng chưa chứng minh tự động chuyển câu sửa dữ kiện thành artifact
revision mới qua UI. Không coi assertions store này là model/app acceptance.

Bước tiếp theo dùng UI Quick đã chọn làm nơi tích hợp adapter gọi runtime chung,
giữ các sửa thiết kế/PDF. Không xây thêm reasoning controller hoặc state store.
Acceptance phải khai rõ launcher/UI source, runtime và backend mode, rồi kiểm
người dùng đi xuyên suốt trên đúng bề mặt đó.

0 real-model calls; generated-token counts của backend fixture là authored.
Không đo full inference cost/online model latency. Stage 0 và data review giữ
nguyên. Không commit/branch/push. Source/diff ghi trạng thái workspace shared,
không quy toàn bộ thay đổi trong diff cho riêng chat này.
