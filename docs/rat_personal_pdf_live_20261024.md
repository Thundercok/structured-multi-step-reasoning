# RAT — kiểm bằng PDF có sẵn trên máy và giữ số trong preview

Ngày 2026-10-24, Asia/Saigon. Theo yêu cầu người dùng, tìm PDF trong máy và
chọn tài liệu học tập có sẵn, thay cho tải thêm hoặc tạo fixture.

## Tệp gốc

Chọn `Ensemble Learning.pdf`, slide Lê Anh Cường / TDTU, 24 trang,
2.225.530 byte, tại:
`/Users/thundercock2/Documents/Github/dump/schoolworks/hoc-may/Ensemble Learning.pdf`.
Trang đầu và nội dung trang 2–3 đã được đọc/kiểm hình; metadata PDF ghi ngày
tạo 2022-04-09. Đây là tệp có sẵn được mở tại chỗ, không sao chép hoặc viết
lại PDF. Không khẳng định URL tải ban đầu vì không lấy được metadata đó.

SHA256 trước/sau:
`5420e93ef4d7ae4b87cfb583a821eeb5e04efba73356fdb8f68f99f3a139f56e`.
Hash và mtime không đổi.
[Provenance đầy đủ](../work/rat_personal_pdf_live_20261024/document-provenance.json).

![Trang 3 của PDF gốc](../work/rat_personal_pdf_live_20261024/original-page-03.png)

## Minor UI

Min preview giữ số thứ tự vốn có trong phản hồi (`1.`, `2.`), cùng ngắt dòng
đã có từ lượt trước. Không tự thêm số, không sinh bản tóm tắt khác. Vẫn giới
hạn ba dòng; full answer và copy giữ nguyên nội dung model. Thay đổi duy nhất
về hành vi sản phẩm trong lượt này nằm ở formatter `answer_excerpt`.

## Luồng thực đã kiểm

Cửa sổ RAT QML native, nhập/bấm qua desktop CUA. Chọn đúng PDF bằng hộp thoại
macOS; phiên hội thoại bắt đầu rỗng, state riêng. Model local đã cài:
`qwen3:4b-instruct`, Q4_K_M, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`;
Ollama 0.34.3, `think=false`, context 8192, output cap 640/lượt.
Không dùng canned answer hay backend giả; không gửi PDF lên dịch vụ cloud.

| Lượt | Yêu cầu | Phản hồi public thật |
| --- | --- | --- |
| 1 | So sánh Bagging và Boosting, hai ý đánh số, mỗi ý ≤14 từ | `1. Bagging: Huấn luyện song song, dùng tập dữ liệu ngẫu nhiên.` / `2. Boosting: Huấn luyện tuần tự, học từ sai lầm trước đó.` |
| 2 | Chỉ rút gọn ý hai, ≤10 từ; giữ số 2, không lặp ý 1 | `2. Tuần tự, học từ sai lầm.` |
| 3 | Giải thích “ý đó” trong một câu ≤25 từ, bám mô tả trong slide | `Boosting học từ sai lệch của mô hình trước để cải thiện kết quả.` |

Đối chiếu thủ công: lượt đầu phân biệt đúng song song/tuần tự; lượt hai giữ
đúng referent và số thứ tự, 7 đơn vị cách nhau bằng khoảng trắng sau số 2;
lượt ba nói rõ Boosting và việc học từ sai lầm mô hình trước, phù hợp mô tả
trang 3. “Cải thiện kết quả” là diễn giải mục đích, không phải kết quả đo được.
Đây là quan sát của một hội thoại cụ thể, không phải xác nhận chất lượng chung.

Đã kiểm min/full từng lượt, chép câu trả lời, sau đó chọn **trang 3** trong
menu PDF để đọc trực tiếp và chép trích dẫn. Trích dẫn chứa đúng tên tệp, trang
PDF 3 và đường dẫn gốc. Không tự gán trang 3 cho source của model: model source
vẫn thiếu vị trí trang, còn bước đọc trang này là hành động riêng của người dùng.

[Hội thoại đầy đủ](../work/rat_personal_pdf_live_20261024/conversation.md),
[request/public raw responses](../work/rat_personal_pdf_live_20261024/model-calls.json),
[kết quả kiểm](../work/rat_personal_pdf_live_20261024/acceptance-summary.json),
[trích dẫn đã chép](../work/rat_personal_pdf_live_20261024/clipboard-observed.txt).

![Min mode giữ số 1 và 2](../work/rat_personal_pdf_live_20261024/live-turn-turn-1-min.png)

![Full mode của câu hỏi tiếp](../work/rat_personal_pdf_live_20261024/live-turn-turn-3-full.png)

[Ảnh đọc trang nguồn trong RAT](../work/rat_personal_pdf_live_20261024/live-page-full.png).
Mỗi lượt có ảnh min/full riêng từ cửa sổ thực đang chạy, không phải fixture.

## Kiểm tra và giới hạn

3 model calls báo cáo **3.821 prompt token + 71 generated token**. Đây là
usage token, không phải toàn bộ chi phí inference. Online latency cả lượt:
**17,31 s / 3,32 s / 4,83 s**; cache/model residency khác nhau nên không suy ra
khả năng tăng tốc chung. Lịch sử thực trong prompt được đối chiếu lần lượt
0/1/2 lượt và khớp nguyên public answer trước đó.

Compile formatter và `git diff --check` pass. Kiểm số thứ tự bằng public reply
đã lưu trước đó pass; không tiêm reply đó vào UI hiện tại. Source manifest không
đổi trong run, không có QML warning, cửa sổ đóng exit 0. Daemon model do lượt
kiểm mở đã được dừng. Không thay model mặc định hoặc research harness.

Hai lỗi ở công cụ kiểm độc lập được ghi trong acceptance summary: probe native
extractor trong sandbox exit 134; render Poppler ban đầu báo fontconfig cache
không ghi được. GUI native sau đó đọc thành công chính tệp này, còn trang 3
render với font cache riêng trong workspace. Đây không phải lỗi UI/model được
che bằng kết quả dựng sẵn. CUA có một lần không bấm được menu theo AX index;
đọc lại screenshot rồi bấm trực tiếp trên menu đã gửi đúng một request.

Giới hạn vẫn là 3.000 ký tự đầu văn bản trích xuất và tối đa hai lượt lịch sử.
UI verifier giữ **UNKNOWN**, không gán PASS từ đối chiếu thủ công. Không đo
accuracy hoặc thay Stage 0. Không chạy Dừng/OCR trong lượt này.

Minor UI được đề xuất tiếp: cải thiện cách ngắt dòng khi đọc trang PDF; văn
bản hiện giữ các xuống dòng cứng của slide nên có chỗ gãy câu dù khung còn rộng.
