# Review đề xuất Spotlight/CoT — 2026-10-16

Kết luận: giữ hướng tìm kiếm lũy tiến, model cư trú và điều phối theo bằng chứng.
Chưa dùng bản đề xuất như spec triển khai hoặc bằng chứng hiệu năng. Lượt này
chỉ review source, artifacts và tài liệu tham khảo; không chạy inference, sửa
runtime/UI hoặc thay đổi protocol nghiên cứu.

## Phần nên giữ

- Kết quả tên ứng dụng/tệp, FTS và metadata hiện trước phần ngữ nghĩa.
- Tìm kiếm vẫn dùng được khi model chưa sẵn sàng; chỉ nạp ngữ cảnh khi người dùng
  chủ động chọn nguồn để hỏi. Giữ prefix tài liệu tách khỏi luồng gõ tìm kiếm.
- Cùng composer, selection theo identity của tài nguyên, bỏ kết quả truy vấn cũ.
- Tái sử dụng registry, dispatcher, artifact store, execution IDs và receipts.
- Headless acceptance trước, sau đó thử hành trình UI; tách khỏi đánh giá NCKH.

## Những điểm cần sửa trước khi code

| Nhận định trong đề xuất | Đối chiếu và sửa |
| --- | --- |
| Tổng tài nguyên 5,5–6,5 GB, còn dư 9,5–10,5 GB | Chưa có phép đo tổng app/hệ thống hỗ trợ các số này. 2,99 GB chỉ là đỉnh allocation MLX của fixture. Không suy ra RAM khả dụng từ phép trừ với RAM danh nghĩa. Các bảng quota mới là ý tưởng, chưa phải giới hạn được cưỡng chế. |
| 5,36–9,24 giây là tái lập chỉ mục | Đây là wall time đọc + chuẩn bị ngữ cảnh + trả lời trên fixture. Không đo tái lập chỉ mục. 26,05 giây cũng không chứng minh đã chạm trần context token. |
| FTS 10–30 ms, vector 100–300 ms, thao tác dưới 50 ms, UI 60 FPS | Đặt thành mục tiêu đo với quy mô index, cold/warm, tải đồng thời và phân vị rõ ràng. Không ghi như kết quả đã đạt hoặc lời bảo đảm. |
| Tóm tắt PDF bằng text từ index, kiểm tra hash trước mỗi câu | Code hiện tại đọc/trích xuất tệp trên đĩa qua operation đã đăng ký, tối đa 3.000 ký tự. Prefix so khớp token của context chuẩn hóa; chưa có cơ chế pin phiên theo path/mtime/hash như đề xuất. |
| AssistantRuntime được cách ly trên thread model | Chỉ native load/inference/release của ResidentDocumentModel chạy trên thread riêng. Caller thực hiện runtime/tool read; GUI phải đặt công việc đó trên worker. |
| Tạo chuẩn biên lai mới trong kernel/contracts.py | Đã có ExecutionJournal/ReceiptEnvelope trong completion.py và contracts/dispatcher hiện có. Bổ sung adapter/outcome khi cần; không tạo hệ receipt song song. |
| Mỗi phím hủy toàn bộ FTS/vector đang chạy | Cancellation token và bỏ callback muộn không đồng nghĩa dừng được kernel đang tính. Dùng hàng chờ chỉ giữ truy vấn mới nhất; không để truy vấn nhanh mắc sau embedding cũ. Mỗi worker giữ ownership/kết nối DB phù hợp. |
| Tự cắt KV hoặc giữ khóa weights khi áp lực bộ nhớ | Chưa có tích hợp policy này vào native service. Không cắt tùy ý cache chứa dữ kiện cần thiết. Cần giải phóng qua owner thread, có trạng thái rõ ràng và kiểm tra tác động tới tác vụ đang chạy. |

`statvfs` trả thống kê filesystem chứa đường dẫn, không tính dung lượng thư mục.
Công cụ đo ứng dụng phải định nghĩa logical bytes/allocated bytes và phạm vi đã
đếm; xử lý dữ liệu dùng chung, symlink, lỗi quyền và đếm trùng. Model có thể gợi
ý ứng viên để kiểm tra, không cung cấp bằng chứng quyền sở hữu thư mục.
[Python os.statvfs](https://docs.python.org/3/library/os.html#os.statvfs).

Với mở ứng dụng, tách yêu cầu mở đã được gửi, callback xác nhận khởi chạy và
ứng dụng thực sự sẵn sàng. PID của tiến trình `open` không phải PID của game.
NSWorkspace có callback trả về app/error; chưa đủ để nói người dùng đã vào được
game hoặc client đã đăng nhập. Riot Client và League of Legends cũng phải giữ
identity riêng, tránh alias âm thầm thay đích.
[Apple NSWorkspace.openApplication](https://developer.apple.com/documentation/appkit/nsworkspace/openapplication(at:configuration:completionhandler:)).

Không thêm độ chờ bắt buộc 300 ms sau một lựa chọn chủ động nếu chưa có lý do
được đo. Không đưa token/receipt chi tiết lên bề mặt chính của mọi thao tác;
giữ trạng thái ngắn và cho xem chi tiết khi cần.

## Phần CoT hiện chưa thành một thiết kế có thể kiểm chứng

Bản dán tuyên bố có năm tầng và tiêu chí dừng nhưng không có định nghĩa đầy đủ
của từng tầng/gate. Nhận diện một ứng dụng hoặc lấy được receipt không chứng
minh toàn bộ mục tiêu đã đạt; receipt sinh xong không chứng minh tóm tắt đúng.
Đề xuất cần chốt outcome, điều kiện còn thiếu, action hợp lệ và ngân sách trước
khi quyết định tiếp tục. Không ngắt generation chỉ vì bắt được một tên thực thể
trong stream; kết quả chưa hoàn chỉnh có thể không dùng được.

Ba paper có thật, nhưng cách gắn chúng vào RAT còn vượt nội dung được trích:

- [SEVRA](https://arxiv.org/abs/2606.19808) nghiên cứu chọn kiểm tra lại đáp án
  bằng gate từ trạng thái quan sát được. Paper cũng cho thấy baseline tăng ngân
  sách lượt đầu có thể hiệu quả token hơn selective verification. Nó không
  chứng minh một ladder Spotlight tùy ý sẽ nhanh hơn.
- [DEER](https://arxiv.org/abs/2504.15895) dùng điểm chuyển reasoning và confidence
  của trial answer, khác cơ chế dừng thuần receipt. Adapter MLX hiện dùng
  thinking=False và chưa triển khai thuật toán này.
- [Budget Boundary Effects](https://arxiv.org/abs/2609.38699) phân tích cap,
  completion eligibility và selector bằng replay toán học. Nó không cung cấp
  bằng chứng hiệu năng online cho Spotlight hoặc bộ phân rã BATS được mô tả.

Tìm chuỗi `BATS` không thấy trong ba bản toàn văn đã kiểm tra. Cần nguồn đúng
cho cơ chế đó hoặc ghi rõ nó chỉ là đề xuất, chưa phải phương pháp đã đối chiếu.

## Kiến trúc thu hẹp nên chốt

Giữ một bộ điều phối trên trạng thái công việc/contract hiện có. Từ dữ kiện đã
quan sát, chọn một trong: trả kết quả, tìm sâu hơn, đọc nguồn, gọi model, thực
thi hành động được yêu cầu hoặc hỏi làm rõ. Kiểm tra outcome sau mỗi bước;
không gọi model thêm khi mọi yêu cầu có thể kiểm chứng đã được thỏa mãn. Dừng
với trạng thái chưa hoàn tất khi hết ngân sách; không giả thành công.

Phân biệt rõ hai phần:

1. Tác vụ xác định như tìm/mở app dùng lookup và execution checks. Đây là
   nền tảng thực thi nhanh, không phải bằng chứng đóng góp CoT.
2. Tác vụ cần suy luận dùng model đề xuất bước có cấu trúc từ các resource IDs
   quan sát được, đối chiếu constraints, rồi cân nhắc bước tiếp. Native adapter
   hiện chưa hỗ trợ general structured action output; phải triển khai và kiểm
   chứng riêng trước khi nối thành agent offline. Chưa fit controller mới từ
   fixture, chưa bật learned gate chưa được review.

## Lát cắt đầu tiên được khuyến nghị

**Tìm ứng dụng/tệp và trả kết quả lũy tiến, headless trước.**

- Catalog ứng dụng có identity/path được kiểm chứng và alias tường minh; không
  quét app catalog lại trên mỗi phím. Bare query chỉ tìm, không tự mở app.
- Luồng tên tệp/FTS/metadata trả một snapshot dùng được mà không khởi tạo LLM
  hoặc embedding. Ngữ nghĩa là bước bổ sung độc lập khi đã sẵn sàng.
- Query ID/generation, stable resource IDs, giới hạn hàng chờ và trạng thái
  partial/complete/cancelled; kết quả bổ sung giữ nguyên selection.
- Fake catalog và index fixture có nhãn synthetic: kiểm tra đúng tài nguyên,
  alias mơ hồ, tệp/app bị gỡ, hủy/query mới, semantic lỗi/chưa sẵn sàng, và
  **0 lượt LLM/0 lượt embedding trước kết quả đầu tiên**.
- Đo time-to-first-usable-result và kết quả cuối bằng monotonic clock, ghi cold/
  warm và phân vị; không biến mốc 50 ms thành assert unit test thiếu kiểm soát.

Sau khi có bằng chứng này: nối vào composer hiện có; thêm operation mở app có
receipt; nối Hỏi tệp với native MLX; sau đó mở rộng bài toán structured reasoning
có constraints và verifier phù hợp. Đo dung lượng game để sau vì phạm vi sở hữu
dữ liệu khó hơn tìm/mở app.

Đánh giá NCKH giữ protocol hiện hành. So sánh trong cùng tập tác vụ và công cụ,
cùng quy tắc chọn/kiểm tra và ngân sách hữu hạn. Ghi prompt + completion của mọi
lượt, cache/load/prefill/generation và wall time riêng; generated tokens không
phải full inference cost. Baseline “sinh không giới hạn” không phải mặc định
công bằng hoặc khả thi. Không tự tạo bộ test 100 kịch bản rồi coi là held-out.
Stage 0 và yêu cầu review dữ liệu không thay đổi.
