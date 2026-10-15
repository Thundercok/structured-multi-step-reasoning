# RAT: gõ điều muốn làm, Chuột nhận việc

Ngày: 2026-10-14, Asia/Ho_Chi_Minh. Đây là yêu cầu sản phẩm mới nhất của người
dùng, bổ sung cho [nghiên cứu tính liền mạch](rat_cohesion_research_20261014.md).
Trạng thái: đích trải nghiệm; phần đầu đang được triển khai trong app local.
Kết quả phần mềm và thử PDF thật ở [ghi nhận triển khai](rat_magic_implementation_20261014.md).
Chưa nghiệm thu toàn bộ trải nghiệm bằng model thật. Không thay pipeline
NCKH, mặc định model hay Stage 0. DocAI tiếp tục độc lập.

Người dùng muốn cảm giác như có phép màu: chỉ gõ điều mình muốn, Chuột hiểu
công việc, tự tìm cách làm và mang kết quả trở lại. Họ không phải biết tên
chức năng hoặc cách nối các công cụ. Sau này họa sĩ sẽ cung cấp chuyển động
phong phú cho Chuột; trải nghiệm cần nhập vai nhất có thể mà vẫn dễ đọc,
dễ sửa và trung thực về việc đã thực sự làm.

## Một nơi để nói, một kết quả để tiếp tục

- Đường chính chỉ có ô nhập yêu cầu, Chuột và kết quả đang làm. Không cần bấm
  nút gửi: Enter gửi, Shift+Enter xuống dòng. Không đặt tab, menu công cụ,
  form điền trường hay bộ nút chức năng trên đường hoàn thành công việc.
- Ô nhập nằm ở đáy. Khung ở phần dưới màn hình, kết quả nở lên trên; giữ
  nguyên editor, bản nháp, vùng chọn và điểm neo khi compact/full thay đổi.
- Khi nhờ đưa tệp, Chuột mang đính kèm của tệp thật vào cuộc trò chuyện.
  Tên tệp có thể nhấn hoặc mở bằng Enter. Không nhận đường dẫn bịa trong
  lời model làm tệp đã tạo. Tệp mất trên máy phải được nói rõ.
- Mọi câu hỏi tiếp, sửa nguồn, đổi ý và yêu cầu dừng đều gõ ở cùng ô đó.
  Có thể dùng Escape để dừng nhanh; đây là lối tắt tùy chọn, không phải bước
  bắt buộc. Gõ yêu cầu mới trong lúc đang làm vẫn phải có cách tiếp nhận rõ.
- Kết quả thay đổi ngay tại nơi đang đọc. Tìm sách, đọc trang và rút trích dẫn
  là những việc Chuột làm để tạo câu trả lời, không thành ba màn hình hoặc
  một chồng kết quả trung gian bắt người dùng tự ghép.
- Khi thật sự thiếu dữ kiện, Chuột hỏi một câu tự nhiên, cụ thể. Dùng thông
  tin đã có trước; không hỏi lại hoặc ép người dùng điền schema. Có nhiều
  nguồn phù hợp thì nêu lựa chọn bằng lời để người dùng trả lời ngay.
- Nguồn tài liệu, số trang và giới hạn cần biết xuất hiện cạnh nội dung liên
  quan. Chi tiết mở rộng chỉ là tùy chọn; người dùng vẫn hoàn thành được việc
  bằng lời, không phải tìm đúng thao tác trong một menu.
- Khi sửa một ý, giữ phần còn đúng, cập nhật phần liên quan và cho biết điều
  vừa đổi ngắn gọn. Kết quả cũ vẫn có lịch sử; không để người dùng gõ lại từ đầu.

## Chuột nhận việc và sống cùng công việc

Chuột đứng bên trái như lựa chọn đã chốt. Click vào Chuột chỉ tạo emote hoặc
phản ứng giãy tại chỗ; không mở notes, gọi công cụ, gửi chat hay đổi công việc.
Ô nhập, điểm đang đọc và bản nháp được giữ khi chạm nhân vật.

Chuyển động có thể giàu biểu cảm: nhận lời nhờ, chú ý tới nguồn mới, đọc,
ghi chép, chuyển sang bước tiếp, chờ người dùng, vui khi có kết quả hoặc dừng
lại khi được yêu cầu. Những trạng thái này phải bám vào sự kiện thực. Thở,
nhìn và các cử chỉ trang trí được phép; không diễn cảnh đã lưu, đã đọc xong
hoặc đã thành công khi chưa có kết quả xác nhận.

Họa sĩ có thể thay từng cử chỉ bằng các đoạn animation nhiều sắc thái và nối
chuyển động giữa chúng. Giữ những thời điểm rõ để nhận animation: nhận việc,
đang tìm/đọc/ghi, có kết quả từng phần, cần trả lời, lỗi và dừng. Đây là brief
cho tài sản hình ảnh tương lai, không tuyên bố bộ animation đó đã có.

Khi người dùng đang đọc, Chuột dịu lại; không che chữ, đẩy nội dung hoặc liên
tục giành chú ý. Có chế độ giảm chuyển động với trạng thái tĩnh dễ hiểu.
Âm thanh không tự bật. Tính cách vui nhẹ, không giục, trách, nài người dùng
quay lại hoặc làm họ thấy có lỗi khi dừng hay bỏ việc.

## Hai hành trình ngắn

**Tìm phần sách rồi đổi nguồn.** Người dùng gõ: “Tìm phần binary search trong
sách DSA, giải thích ngắn và cho hai trích dẫn.” Chuột nhận việc; kết quả đang
làm dần có câu giải thích và hai đoạn trích kèm nguồn trang. Người dùng gõ:
“Dùng cuốn tiếng Việt kia.” Nếu nguồn rõ, Chuột đọc nguồn mới và sửa đúng phần
phụ thuộc; nếu còn hai cuốn phù hợp, chỉ hỏi một câu để chọn. Người dùng tiếp:
“Bỏ giải thích, chỉ ghi hai đoạn đó.” Chuột làm theo mục tiêu mới và chỉ xác
nhận đã ghi khi có ghi chú thực sự được lưu trong cuộc trò chuyện.

**Lịch và tài liệu thành một việc.** Người dùng gõ: “Mai học gì, chọn phần sách
vừa đủ để ôn trước buổi đó.” Một kết quả chung đưa buổi học và nội dung cần đọc
kèm nguồn. Người dùng gõ: “Chỉ 15 phút thôi, giữ ví dụ với mảng.” Cùng kết quả
được rút gọn, không yêu cầu tra lịch hay chọn sách lại. “Dừng, giữ hai trang
đã đọc” khiến Chuột dừng bước tiếp theo và giữ dữ liệu hợp lệ. Phần đã lưu
trước khi dừng phải được nói đúng; không giả là đã hoàn tác.

Các hành trình trên là ví dụ đích trải nghiệm, chưa phải transcript đã chạy
thành công. Đề xuất ôn tập không được hiển thị như sự kiện lịch đã tạo.

## Năm điều có thể quan sát để nghiệm thu

1. Người dùng hoàn thành cả hai hành trình chỉ bằng ô nhập; không phải mở
   tab/menu công cụ, điền form hoặc nhấn nút chức năng để nối các bước.
2. Câu hỏi tiếp và sửa nguồn cập nhật đúng kết quả đang nói tới; không bắt
   nhắc lại dữ kiện, không nhân thành chồng khối trung gian, không mất chỗ đọc.
3. Khi thiếu dữ kiện thật, chỉ hỏi điều cần để tiếp tục bằng hội thoại; khi
   thông tin đã đủ, Chuột làm tiếp mà không đòi thêm bước xác nhận vô ích.
4. Gõ “dừng” hoặc nhấn Escape dừng đúng công việc; kết quả hợp lệ và bản nháp
   còn nguyên, không có kết quả muộn chen vào hoặc lời báo lưu không có thật.
5. Chạm Chuột chỉ emote; animation phản ánh tiến độ thật, yên khi đọc, không
   che nội dung. Giảm chuyển động vẫn rõ trạng thái, âm thanh mặc định tắt.

## Phân biệt hiện tại, đích và prototype

Source local đã chuyển composer xuống đáy, giấu điều khiển kỹ thuật mặc định,
nhận dừng bằng lời/Escape và đưa tệp từ artifact thật. `RAT_DEBUG_UI=1` hiện
lại điều khiển phát triển. Hỏi bổ sung đi qua câu trả lời và pending operation;
form chỉ hiện ở debug. Khi đang chạy, câu sửa khác được giữ làm bản nháp;
chưa tự ngắt và lập lại toàn bộ công việc. Kết quả vẫn dùng renderer đã đăng
ký; canvas ghép hoàn toàn và animation do họa sĩ cung cấp vẫn là đích sau.

Prototype trong hội thoại chỉ minh họa cảm giác một ô nhập, Chuột và một kết
quả biến đổi. Dữ liệu, thời gian và phản ứng mẫu phải được ghi rõ là mô phỏng;
không ngụ ý đã tìm PDF cá nhân, đọc lịch thật, lưu notes hay gọi model/backend.
Prototype trực quan không thay nghiệm thu hội thoại thật và không chứng minh
chất lượng model. Giữ riêng bằng chứng phần mềm, nội dung và trải nghiệm.
