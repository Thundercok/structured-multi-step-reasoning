# RAT — hỏi tiếp PDF và min preview giữ ngắt dòng

Ngày: 2026-10-24, Asia/Saigon.

Document worker trước đây nhận history nhưng prompt chỉ chứa excerpt và câu
hỏi hiện tại. Bản này đưa tối đa hai lượt public hoàn chỉnh gần nhất của cùng
đường dẫn và cùng SHA256 vào prompt. Kiểm qua desktop thật cho thấy yêu cầu
“chỉ rút gọn ý thứ hai vừa rồi” giữ đúng ý được tham chiếu. Lượt giải thích
tiếp theo còn chung chung; không coi cả hội thoại là chất lượng đã được xác minh.

## Thay đổi

- `ConversationHistory.document_messages` lấy các lượt completed liên tiếp
  của đúng revision tài liệu, không lấy partial/cancelled hoặc summary đã cắt.
  Một lượt hoàn tất của tài liệu khác hay chat thường kết thúc chuỗi ngữ cảnh.
- Controller lưu scope path/hash từ immutable request cùng kết quả đọc thật.
  Scope này theo turn snapshot, không phụ thuộc PDF đang chọn lúc callback đến.
- Prompt giữ nguyên từng cặp câu hỏi/câu trả lời, bỏ metadata nội bộ và đặt
  câu hỏi hiện tại ở cuối. Tối đa hai cặp và ngân sách byte bảo thủ cho context
  8192. Nếu cặp mới nhất không vừa, trả lỗi rõ ràng thay vì âm thầm bỏ referent;
  cặp cũ hơn có thể bị loại khi thiếu chỗ. Không tạo thêm model call để tóm tắt.
- System prompt phân biệt câu trả lời cũ với evidence: chỉ dùng reply cũ để
  hiểu chỉnh sửa; thông tin tài liệu vẫn phải dựa trên excerpt được đọc hiện tại.
- **Minor UI nhận diện bản này:** min preview giữ ngắt dòng giữa các ý thay
  vì ghép thành một đoạn. Vẫn tối đa ba dòng hiển thị và dấu cắt khi cần.
  Câu trả lời đầy đủ và nội dung sao chép được giữ nguyên.

## Hội thoại thật

Dùng lại nguyên bản PDF arXiv `2201.11903v6`, 43 trang. Không dựng PDF hoặc
tiêm câu trả lời UI. [Provenance và hash](../work/rat_pdf_followup_live_20261024/document-provenance.json)
trỏ tới đúng tệp gốc đã tải ở lượt trước; SHA256 sau run không đổi:
`7d9f878c23b460e4566aa4ec9201b1abfb3b8faefb2b1356e411cb90fef72a12`.

Qwen3 `4b-instruct` local, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`,
Ollama 0.34.3, `think=false`, context 8192, output cap 640/lượt. Mọi truy vấn
được nhập/bấm qua desktop CUA trong cửa sổ native QML; observer chỉ ghi log
và ảnh, dùng SLMEngine thật. Phiên bắt đầu với lịch sử rỗng và state riêng.

| Lượt | Yêu cầu thực | Phản hồi public / nhận xét thủ công | History đã gửi |
| --- | --- | --- | --- |
| 1 | Từ abstract, hai ý đánh số: kỹ thuật và kết quả, mỗi ý ≤22 từ | Hai ý về few-shot CoT và khả năng suy luận. | 0 lượt |
| 2 | “Chỉ rút gọn ý thứ hai vừa rồi còn tối đa 12 từ. Không nhắc lại ý thứ nhất.” | “2. Cải thiện đáng kể khả năng suy luận phức tạp.” Đúng referent, không lặp ý một, 10 đơn vị tách bởi khoảng trắng, bỏ số thứ tự. | 1 lượt |
| 3 | “Giải thích rõ hơn ý đó trong đúng một câu, tối đa 25 từ tiếng Việt.” | “Phương pháp này giúp mô hình suy luận rõ ràng hơn qua các bước trung gian.” Đúng độ dài nhưng còn chung chung, chưa làm rõ các nhiệm vụ/kết quả trong abstract; đánh giá **partial**. | 2 lượt |

[Toàn bộ hội thoại](../work/rat_pdf_followup_live_20261024/conversation.md),
[request và public raw responses](../work/rat_pdf_followup_live_20261024/model-calls.json),
[observed responses/telemetry](../work/rat_pdf_followup_live_20261024/response-observations.jsonl),
[acceptance summary](../work/rat_pdf_followup_live_20261024/acceptance-summary.json).

Đã đối chiếu từng assistant message trong request lượt 2/3 với đúng câu trả
lời thực trước đó; không có câu trả lời dựng thêm. Chuyển min/full và chép
phản hồi thực qua nút Sao chép. Ảnh lấy từ grabWindow của cửa sổ đang chạy.

![Min mode giữ ranh giới hai ý](../work/rat_pdf_followup_live_20261024/live-turn-turn-1-min.png)

![Full mode sau yêu cầu rút gọn ý hai](../work/rat_pdf_followup_live_20261024/live-turn-turn-2-full.png)

Ảnh của lượt chưa đạt hoàn toàn vẫn giữ:
[min lượt 3](../work/rat_pdf_followup_live_20261024/live-turn-turn-3-min.png),
[full lượt 3](../work/rat_pdf_followup_live_20261024/live-turn-turn-3-full.png).
Mỗi lượt đều có ảnh min/full riêng trong thư mục run.

## Kiểm tra và giới hạn

`python -m pytest tests/test_selected_document_context.py -q`: **5 passed**.
Đây là kiểm hợp đồng prompt/scope bằng public reply đã ghi nhận trước đó,
không chạy backend hoặc tiêm đáp án vào UI. Bao phủ cách ly tệp/revision,
loại cancelled, thứ tự và metadata message, từ chối latest pair quá dài,
không nhận system message/orphan reply trong history.
Compile Python và `git diff --check` pass. Không có QML warning; cửa sổ đóng
exit 0. Các source theo dõi trong manifest không đổi trong run. Không tải model
mới hoặc đổi cấu hình model mặc định; daemon do lượt kiểm mở được dừng sau run.

3 model calls báo cáo tổng **3.474 prompt token + 87 generated token**. Đây là
usage token, không phải toàn bộ chi phí inference. Online latency cả lượt
lần lượt **28,59 s / 2,25 s / 3,89 s**, bao gồm đọc tệp và model. Cache/model
residency khác nhau giữa các lượt; không diễn giải thành cải thiện tốc độ chung.

Giới hạn còn lại: excerpt vẫn chỉ 3.000 ký tự đầu; cửa sổ history tối đa hai
lượt, không phải bộ nhớ toàn phiên; bản cũ chưa có scope hash không được dùng
làm document history. Việc tham chiếu ngữ cảnh đã hoạt động trong yêu cầu chỉnh
sửa được thử, nhưng lượt 3 cho thấy chất lượng giải thích vẫn cần cải thiện.
Không chạy lại Dừng/OCR/đổi PDF bằng desktop trong lượt này; cách ly file/hash
được kiểm ở hợp đồng, chưa phải live acceptance cho chuyển tài liệu. Verifier
UI giữ **UNKNOWN**. Không đổi research harness, campaign gate hoặc tuyên bố
accuracy; đây là smoke của ứng dụng, không vượt Stage 0.

Minor UI tiếp theo được đề xuất: giữ số thứ tự trong preview để “ý thứ hai”
dễ nhận diện ngay khi người dùng ở min mode.
