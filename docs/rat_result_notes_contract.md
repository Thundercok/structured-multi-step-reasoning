# RAT: giữ kết quả và ghi chú xuyên suốt hội thoại

Ngày 2026-10-13, Asia/Saigon. Người dùng đã đồng ý dùng luồng **tính → ghi →
sửa → so với bản cũ → dừng và tiếp tục** làm mốc kế tiếp trong lúc Antigravity
hoàn tất review luồng DSA. Đây là cải thiện core RAT, tách khỏi pipeline NCKH.

## Vấn đề và thay đổi

Calculator trước đó trả kết quả trong trajectory của một execution, nhưng không
lưu vào artifact store. `record_work_note` chỉ nhận trích dẫn từ tin nhắn user.
Vì vậy yêu cầu ghi một kết quả được tính ra không có nguồn hợp lệ để nối vào notes.

Kết quả calculator hiện có artifact ID, revision, inputs và lượt/execution sở
hữu trong store chung. Lượt sau đọc lại bằng `inspect_artifact`. Mỗi lần tính mới
tạo một kết quả mới; lịch sử thay thế trong lát cắt này thuộc phiên bản note,
không phải chỉnh sửa tại chỗ artifact calculator.

Operation hiện có `record_work_note` nhận đúng một nguồn:

- `source_quote`: trích dẫn lời user, giữ hợp đồng cũ.
- `source_result`: ID, revision và đường dẫn trường scalar trong payload thật.
  Runtime xác định lượt nguồn; model không được tự khai lượt đó.

Nguồn kết quả hỗ trợ string/number/bool, tối đa 500 ký tự. Đường dẫn trường qua
dictionary dùng dấu chấm như validator view hiện có; chưa hỗ trợ phần tử array.
Các trường không tồn tại, revision không tồn tại, kết quả đang chờ, object/array
và số không hữu hạn bị từ chối trước khi ghi note.

Nội dung chép đúng trường nguồn có authority `observed_result`. Checker đã đăng
ký của nguồn cũng có thể kiểm tra một statement trong phạm vi hỗ trợ. Hiện tại
checker số học kiểm tra một kết quả số hoặc phương trình đầy đủ với đúng biểu
thức, giá trị và artifact/revision nguồn; note “18 * 7 = 126” có thể được xác nhận
với `source_verification.scope=source_calculation_note`. Cơ chế này gọi checker
của operation đã có, không thêm một tool hay bộ định tuyến riêng cho notes.

Diễn giải ngoài phạm vi vẫn là `unconfirmed_model_suggestion`. Giá trị `confirmed`
xác nhận sao chép hoặc kiểm tra mang scope đã ghi; không chứng nhận toàn hội thoại
hay chuyển dữ liệu tool thành dữ kiện user. Checker lỗi/không đúng contract giữ
UNKNOWN; statement chứng minh sai không được commit. User tự xác nhận đề xuất
tạo authority `user_supplied`; tự sửa text bỏ proof cũ. Bản cũ giữ nguồn/revision
và proof của chính nó, dẫn sang bản thay thế; thay note cần ID và revision quan sát.

Calculator dùng contract `present_result=False`: dữ liệu được giữ để tham chiếu,
cách trình bày tiếp tục qua câu trả lời và trace đã có. Presenter dùng metadata
chung để tránh tự tạo một thẻ dữ liệu phụ cho observation này. Các artifact
deliverable khác vẫn hiện qua renderer hiện có. Bố cục, Chuột và composer không
thay đổi trong mốc này.

## Nghiệm thu phần mềm

`tests/test_rat_calculation_conversation.py` chạy qua runtime, registry,
dispatcher, artifact store, notebook và history thật với quyết định model được
tiêm sẵn. Đây là fixture, không đo model hiểu hoặc tự chọn hành động.

| Bước | Điều kiện kiểm tra |
| --- | --- |
| Tính `18 * 7` | Kết quả 126, nguồn thuộc đúng lượt/execution; kiểm chứng literal arithmetic. |
| Ghi kết quả | Note thuộc lượt yêu cầu ghi, nguồn thuộc artifact ở lượt tính. |
| Đổi 7 thành 9 và sửa note | Có kết quả 162 và note revision 2; bản 126 giữ nguyên với liên kết thay thế. |
| So với bản trước | Đọc cả hai kết quả thật, tính chênh 36; PASS chỉ là số học, không chứng minh diễn giải yêu cầu. |
| Dừng sau khi tính gấp đôi | Giữ kết quả 324 đã commit; chưa ghi note; callback ghi muộn bị chặn. |
| Tiếp tục | Execution mới đọc kết quả đã giữ rồi tạo note revision 3; lượt dừng vẫn cancelled. |

Các kiểm tra âm gồm nguồn/field/revision giả, hai nguồn đồng thời, thiếu nguồn,
revision stale và nguồn không biểu diễn được. Lời model nói “đã ghi” mà không
thực hiện vẫn có 0 note events và completion `unchecked`/verification `UNKNOWN`;
lát cắt này chưa tự nhận diện và chặn mọi lời khẳng định sai bằng ngôn ngữ tự nhiên.

`tests/test_rat_result_presentation.py` dùng Qt offscreen để kiểm tra observation
được giữ mà không thêm thẻ phụ, và các deliverable khác vẫn hiện.

## Phần tiếp theo cần review

1. Chạy development smoke bằng model thật trên câu gốc và cách diễn đạt mới.
   Chấm việc chọn action, dữ kiện dùng, note events, revision và lời giải thích
   riêng với phần mềm. Lưu cả failure; không tiêm các quyết định fixture vào live run.
2. Đo số model calls, prompt/completion tokens và latency online. So sánh planner
   trên cùng cấu hình trước khi thay lựa chọn mặc định; chưa đo lại tốc độ sau đổi prefix.
3. Kiểm tra native compact/full với core mới; kiểm tra ghi/sửa inline và trace.
   Qt offscreen không thay thế nghiệm thu trải nghiệm.

Mốc phần mềm đầu tiên không chạy model mới. Lượt review bàn giao sau đó đã có hai
development smoke bằng 1.5B/4B, nằm trong
[review sau R5](../audit/rat_post_r5_handoff_review_20261013/review.md). Các smoke
này chạy trước sửa guard/kiểm chứng note và không xác nhận source sau sửa.

Thời gian/member hiện được tách khỏi system prefix cố định. Kiểm tra xác nhận
prefix không đổi theo đồng hồ; mức cải thiện tốc độ chưa đo. Thời gian checker
note nằm trong operation time và proof note, không cộng vào tổng thời gian
VerificationSession của các check answer/operation; chưa tuyên bố full inference
cost hoặc latency toàn app.

Không đổi default model, controller
nghiên cứu, splits, publication claims hoặc Stage 0; DocAI tiếp tục để riêng.
Các raw smoke của Antigravity giữ nguyên và thuộc snapshot source đã ghi khi
chạy, không tự trở thành evidence cho source mới.
