# RAT — PDF thật, hỏi model và giới hạn trích đoạn

Ngày: 2026-10-24, Asia/Ho_Chi_Minh. Đây là acceptance cục bộ qua desktop,
không phải đánh giá chất lượng mô hình hay bằng chứng vượt Stage 0.

## Phạm vi dọn tệp

Theo lựa chọn cuối của người dùng, chỉ chuyển hai bản PDF UI giả
`Quy_che_hoc_vu_2026.pdf` vào Thùng rác. Giữ 14 PDF báo cáo/audit trong bộ
kiểm kê và mọi recovery ngoài phạm vi đó. Không làm rỗng Thùng rác.

Hai đường dẫn cũ là `docs/screencaps/tmp_data/Quy_che_hoc_vu_2026.pdf` và
`work/rat_ui_minor_20261023/after/tmp_data/Quy_che_hoc_vu_2026.pdf`.
Manifest có hash và đường dẫn khôi phục:
[trash-manifest.json](../work/rat_real_pdf_cleanup_20261024/trash-manifest.json).

## Tài liệu thật và cấu hình

Dùng nguyên bản [PDF arXiv 2201.11903v6](https://arxiv.org/pdf/2201.11903v6),
*Chain-of-Thought Prompting Elicits Reasoning in Large Language Models*.
43 trang, 891.773 byte; không dựng lại hoặc sửa nội dung.
SHA256: `7d9f878c23b460e4566aa4ec9201b1abfb3b8faefb2b1356e411cb90fef72a12`.
[Nguồn tải và hash](../work/rat_real_pdf_live_20261024/document-provenance.json).

Model local đã cài: `qwen3:4b-instruct`, Q4_K_M, digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`.
Ollama 0.34.3, `think=false`, context 8192, tối đa 640 output token/lượt.
Observer bọc SLMEngine thật để ghi request/public response và usage; không
tiêm câu trả lời. Không đổi model mặc định hoặc cấu hình campaign.

## Thay đổi và quan sát

- Menu tài liệu có **Hỏi về PDF**, dùng câu hỏi trong ô nhập. Enter tiếp tục
  tìm từ khóa. Request mang đúng đường dẫn PDF đã chọn sang document worker.
- Chỉ cấp quyền đọc đường dẫn đã chọn trong execution đó. Không lập chỉ mục
  cá nhân; tệp khác chưa có trong chỉ mục vẫn bị từ chối. Các trường context
  dành riêng cho reasoning được giữ trong request, không truyền thành kwargs
  không hợp lệ cho AssistantRuntime. Hash PDF trong request dùng toàn bộ tệp.
- Lượt đầu model trả đúng tên bài/nhóm và tóm tắt abstract, nhưng **không nêu
  giới hạn trích đoạn dù được yêu cầu**. UI trước sửa cũng bỏ sót thông tin này.
  Giữ nguyên phản hồi đó trong artifact; không sửa thành câu trả lời thành công.
- Minor UI của bản cuối: **Trích đoạn · 3.000 ký tự**, lấy từ receipt đọc thật,
  xuất hiện trong min preview và dòng trạng thái full mode. Không chèn lời
  tự soạn vào câu trả lời của model. Trạng thái xác minh vẫn UNKNOWN.

Đã thao tác qua desktop: chọn PDF bằng hộp thoại macOS, hỏi qua menu, mở/thu
kết quả, tìm `Brain Team` (1 trang khớp trong 43 trang), đọc trang 1, chép và
dán lại trích dẫn để đối chiếu tên tệp/trang/đường dẫn. Bản cuối chạy thêm hai
câu hỏi liên tiếp trên cùng PDF và chép câu trả lời thật. Ảnh là grabWindow
của cửa sổ QML native đang chạy; không phải render fixture/offscreen.

## Bằng chứng và giới hạn

[Hội thoại lượt đầu](../work/rat_real_pdf_live_20261024/conversation.md),
[hội thoại hai lượt trên bản cuối](../work/rat_real_pdf_live_20261024/scope_label_retest/conversation.md),
[request/public responses bản cuối](../work/rat_real_pdf_live_20261024/scope_label_retest/model-calls.json).

![Min mode, model thật](../work/rat_real_pdf_live_20261024/scope_label_retest/live-turn-turn-1-min.png)

![Full mode, model thật](../work/rat_real_pdf_live_20261024/scope_label_retest/live-turn-turn-1-full.png)

Tổng 3 model calls, 3.102 prompt token và 215 generated token được backend
báo cáo. Đây là usage token, không phải toàn bộ chi phí inference. Thời gian
online cả lượt: 66,29 s ở lượt đầu; 8,41 s và 6,95 s ở bản cuối. Hai lượt sau
có prompt cache (992/994 token); không dùng số này để kết luận tăng tốc chung.

Kiểm quyền đọc thực, không gọi model:
`python -m pytest tests/test_selected_document_read_scope.py -q` — pass.
Compile Python và `git diff --check` pass; không có QML warning trong bản cuối.
Hash PDF không đổi; các source được theo dõi không đổi trong lượt bản cuối.
Cửa sổ test cuối đóng với exit 0, daemon Ollama do lượt này mở đã được dừng.

Observer lượt đầu thiếu phương thức `close()` trên client document nên exit 1
ở cleanup sau khi đã hoàn tất flow. Đây là lỗi composition của observer;
đã ghi trong log, sửa observer và xác nhận bản cuối exit 0. Không suy ra lỗi
shutdown sản phẩm từ lỗi đó.

Phạm vi đọc vẫn là 3.000 ký tự đầu của văn bản trích xuất, không phải toàn bộ
43 trang. Không tự gán trang cho source thiếu page metadata. Hai câu hỏi cuối
đều tự đủ ngữ cảnh trên cùng PDF; chưa chứng minh follow-up cần nhớ nội dung
câu trả lời trước, vì prompt document hiện chỉ chứa excerpt và câu hỏi hiện tại.
Không thử lại Dừng/OCR/PDF mã hóa trong lượt này. Không chạy fixture UI/canned
answer để thay thế acceptance. Tên bài/nhóm được đối chiếu thủ công với trang
gốc, không gán PASS cho verifier hay đưa claim accuracy vào nghiên cứu.

Bước UI nhỏ được đề xuất tiếp: giữ ranh giới dòng/ý trong bản xem nhanh để
tên bài và nhóm nghiên cứu không bị nối thành một đoạn dày.
