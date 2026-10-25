# RAT — trợ lý soạn bản luận cho người xem

Ngày: 2026-10-25, Asia/Ho_Chi_Minh. Trạng thái hiện tại: công cụ chuẩn bị
bài/lá số đã đăng ký, suy luận model chưa nối. Đợt 0 đã chặn synthesis giả;
cleanup đã chuyển template ra recovery và dọn projection/script tương ứng.
Xem [execution agentic thống nhất](rat_agentic_execution_redesign_20261025.md)
và [bằng chứng cleanup](../audit/rat_agentic_phase0_20261025/cleanup/README.md).
Không dùng mô tả Build .25 trước review làm xác nhận model acceptance.

## Nguyên tắc người dùng bổ sung trong lượt 1

**“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.”** Xem `AGENTS.md`.
Đây là quy tắc áp dụng toàn RAT, không chỉ bói toán. Không xây đường nghiệp vụ
riêng cho UI: UI dùng chung tools, dispatcher, artifact và bước kiểm tra của
Agent. Đăng ký tool không tự chứng minh vòng suy luận end-to-end đã hoàn tất.

Lượt 1 / Build .23-.24: Bàn xem mở bằng `/reading`, mở rộng không gian 1100 px
theo màn hình (roomyActive), thu gọn giữ nguyên phiên xem, tài liệu và bản nháp.
Đăng ký `prepare_reading_spread` và `load_reading_profile`.

Lượt 2 / Build .25: operation `synthesize_reading_draft` đã đăng ký nhưng
hiện trả `model_unavailable` qua dispatcher, không tạo artifact `reading_draft`.
Template sáu bước và phần UI trình bày template đã được dọn khỏi runtime;
bản phục hồi nằm trong audit cleanup. Chức năng tạo bản luận bằng model, sửa
và lưu revision qua Agent/dispatcher vẫn chờ migration; các control biên tập
còn trong source không chứng minh luồng đó đã hoạt động.

## Hướng người dùng đã chọn

Người dùng muốn RAT hỗ trợ xem tarot và bản đồ sao, đẹp và thuận tiện cho công
việc xem bói của chính mình. Vai trò đã chọn: RAT soạn bản luận trước; người
dùng sửa và chốt. Phần tìm/mở file đang dở được để sang một bên, không rollback
hay coi là hoàn tất. Không đưa dữ liệu sinh hoặc nội dung riêng của phiên trao
đổi cá nhân vào tài liệu thiết kế hay fixtures.

## Trải nghiệm đề xuất — chưa phải quyết định đã duyệt

Giữ một composer của RAT. Khi bắt đầu phiên xem, hiện bàn bài và vùng biên tập
trong workbench. Màu giấy/mực hiện có, lá bài đủ lớn, trạng thái ngược rõ, không
thêm dashboard hoặc buộc người dùng qua nhiều màn hình. Một phiên có thể chỉ
tarot, chỉ natal hoặc kết hợp; thiếu một nguồn không được tự tạo nguồn đó.

1. Hồ sơ: phân biệt người hỏi, người được xem và vai trò trong câu hỏi. Ngày,
   giờ, nơi sinh, nguồn tọa độ và độ bất định thuộc riêng từng người.
2. Câu hỏi và trải: lưu câu hỏi chính, câu hỏi của từng vị trí, deck/truyền thống,
   quy ước xuôi/ngược; cho người dùng thêm ghi chú cách luận riêng.
3. Nhập bài thật: tên lá, xuôi/ngược, thứ tự, lá rơi và lá bổ sung. Lá bổ sung
   liên kết vị trí/lá gốc; lá rơi được ghi riêng, không làm lệch số thứ tự.
   Nhận diện ảnh và rút bài số để các vòng sau; không tự nhận rằng đã rút bài.
4. Bản đồ sao: dùng bộ tính hiện có, hiển thị wheel/bảng và đối chiếu nhiều hồ
   sơ. Khoảng giờ sinh có bản so sánh; không tự sửa giờ theo mô tả tính cách.
5. Bản luận nháp: sửa trực tiếp, chọn đoạn để viết lại, giữ phiên bản người dùng
   đã sửa. Dữ liệu/nguồn và các giả thuyết được phân biệt với lời diễn giải.
6. Bản chốt: xem trước để người dùng tự lưu/xuất. Không tự gửi cho người khác.

## Structured reasoning / CoT trong RAT

Đây là tác vụ ứng dụng để triển khai điều phối có cấu trúc. Tarot/astrology là
extension; các hợp đồng dữ liệu, chọn công cụ, kiểm tra và dừng có thể tái sử
dụng cho hệ RAT–CoT. Chưa có kết quả chứng minh cải thiện reasoning/model quality.

Luồng đề xuất:

- Kiểm tra dữ kiện: người, thời gian, timezone, vị trí trải, chiều lá, bối cảnh.
- Chọn việc cần thực hiện: tính chart bằng tool; chỉ phân tích khoảng giờ hoặc
  synastry khi tác vụ yêu cầu. Không chạy nhiều chiến lược/model mặc định.
- Lập bản diễn giải theo từng vị trí rồi tổng hợp các quan hệ liên quan.
- Xem xét cách đọc thay thế và chi tiết không phù hợp, không ép mọi nguồn cùng
  kể một câu chuyện. Bối cảnh mới có thể thay đổi giả thuyết; giữ dấu sửa đổi.
- Kiểm tra: đúng chủ thể, đúng bài, đúng số liệu và đủ căn cứ. Nhãn mức độ hỗ
  trợ của nguồn không phải xác suất tiên đoán đúng.
- Soạn bản luận công khai có căn cứ tóm tắt, giới hạn và câu hỏi còn mở; không
  hiển thị raw/private chain-of-thought hay nhật ký suy nghĩ nội bộ.
- Dừng khi đã đủ cho câu hỏi và ngân sách; không kéo dài bằng rút thêm vô hạn.

Số liệu vị trí thiên thể/góc có thể kiểm chứng bằng phép tính. Diễn giải chiêm
tinh/tarot không trở thành sự kiện về nội tâm người khác hoặc dự báo chắc chắn
chỉ vì đã qua verifier. Cho phép giọng văn luận giải truyền thống mà không lặp
cảnh báo ở mọi đoạn, đồng thời giữ các phân biệt này trong cấu trúc dữ liệu.

## Căn cứ có thể mở xem

Một nhận định trong bản nháp có thể dẫn tới lá bài và vị trí trải, số liệu chart
và phiên bản phép tính, ghi chú người dùng, tài liệu ý nghĩa đã chọn hoặc bối
cảnh được kể. Bấm vào sẽ hiện tóm tắt căn cứ, cách đọc thay thế và giới hạn.
Không bịa nguồn, không dùng các nguồn lặp nhau làm bằng chứng độc lập.

## Lát cắt đầu tiên đề xuất

Tarot nhập tay + tái sử dụng natal hiện có + bản luận có thể sửa/chốt. Ưu tiên
đúng hồ sơ và liên kết bài trước animation, nhận diện ảnh, thư viện deck lớn,
transits, composite hoặc tính năng quản lý khách hàng.

Thử một phiên thật qua UI: tạo trải, nhập lá xuôi/ngược/lá rơi, bổ sung một lá
đúng vị trí, sửa giờ sinh của một người, tạo bản nháp bằng model thật và sửa/chốt
đoạn luận. Giữ prompt, phản hồi, failures, thời gian/token và screenshots.
Nếu model không chạy được phải ghi giới hạn, không chèn đáp án mẫu làm acceptance.

## Đánh giá đề xuất

- Software: không nhầm hồ sơ hoặc áp dụng sai khoảng giờ, không mất draft/sửa
  tay, không lẫn lá bổ sung và lá rơi, không dùng action của phiên bản cũ.
- Calculation: chart/interval/aspects dùng kết quả tool quan sát được.
- Human review: đọc đúng vị trí, rõ ràng, phù hợp truyền thống đã chọn, xem xét
  cách đọc khác, lượng sửa cần thiết trước khi người dùng chốt.
- Performance: tách thời gian tính chart, inference và thao tác UI; ghi model,
  prompt/version, ngân sách, tokens và lỗi thật.

Không chấm xác suất cảm xúc người khác hay "bói đúng tương lai" bằng tự đánh
giá của model. Bất kỳ so sánh nghiên cứu nào cần protocol riêng và dữ liệu đã
review; thiết kế này không thay campaign, experimental freeze hoặc Stage 0.

## Cần làm rõ trong vòng thiết kế tiếp theo

Deck/truyền thống mặc định và thư viện nghĩa do người dùng chọn; hình ảnh lá
bài và quyền sử dụng; cách xem lại phần đã biên tập khi tạo nháp mới; lưu hồ sơ
local và quyền xóa/xuất; số model calls/token/time budget cho một phiên thật.
