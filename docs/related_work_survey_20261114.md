# Khảo sát công trình liên quan: tính mới của đề tài

Ghi ngày 2026-11-14, sau khi có kết quả tập test GSM8K niêm phong và phân tích hậu nghiệm với `base_prefill`.
Đọc toàn văn bản HTML trên arXiv; số liệu và câu trích lấy trực tiếp từ bài.

## Các bài gần nhất

| Bài | Phương pháp | Mô hình, dữ liệu | So với mô hình gốc chưa tinh chỉnh? |
| --- | --- | --- | --- |
| LIFT (arXiv 2509.13334, trước tên là FRIT) | Thay một bước bằng một dữ kiện không liên quan, viết tiếp, chấm mức ảnh hưởng tới đáp án; tinh chỉnh LoRA trên các vết bị can thiệp làm đổi đáp án | **Qwen3-8B**, Qwen3-4B, Mistral-7B; **GSM8K**, SVAMP, StrategyQA | So với một bản SFT chỉ huấn luyện đáp án, cùng siêu tham số. Độ đúng tương đương bản SFT |
| Lobo và cs., "On the Impact of Fine-Tuning on CoT Reasoning" (arXiv 2411.15382) | Không đề xuất phương pháp; đo QLoRA 4-bit SFT | Llama-3-8B, GPT-3.5, GPT-4; **GSM8K**, MedQA, CosmosQA | **Có.** "fine-tuning leads to an average decrease in the faithfulness of CoT reasoning"; độ đúng khi dùng CoT cũng giảm |
| CASE (arXiv 2607.18820) | Dữ liệu CoT phản thực, mất mát chọn lọc, mặt nạ attention | Llama-3.1-8B, **Qwen3-8B**, R1-Distill-7B; ARC, StrategyQA, LogiQA | **Có**, bảng "Base LLM". Ở thiết lập chuyển miền, FRODO và các phương pháp khác không vượt mô hình gốc |
| FRODO (Paul và cs., EMNLP Findings 2024) | Mục tiêu ưu tiên phản thực và nhân quả (DPO) | Llama-2-7B, Mistral-7B, Llama-3-70B; GSM8K và các bộ khác | So với SFT và chưng cất CoT |
| Causal Consistency Regularization (arXiv 2509.01544) | Sửa phép toán trong vết (đổi `+` thành `-`) làm dữ liệu phản thực | Llama-2-13B, Llama-3-8B, Mistral-7B; GSM8K | So với SFT và giám sát quá trình |
| CST (arXiv 2602.20710) | Thưởng cho vết giúp mô phỏng đầu ra trên đầu vào phản thực | Qwen3 4B đến 235B | Hướng khác: dự đoán được, không phải đi theo bước |

## So với ba điểm đề tài định nhận là mới

1. **Huấn luyện phản thực làm đáp án đi theo bước bị sửa nhiều hơn tinh chỉnh thường.** Đã có. LIFT làm gần như
   đúng việc này, cùng Qwen3-8B, cùng GSM8K, cùng LoRA, có bản SFT đối chứng.
2. **Tinh chỉnh thường làm giảm mức đi theo bước so với mô hình gốc.** Đã có. Lobo và cs. báo kết quả này trên
   GSM8K với QLoRA 4-bit. Kết quả hậu nghiệm của mình (Plain 346 so với gốc 376, p = 0,0003) chỉ lặp lại.
3. **CF giữ mức đi theo bước gần mô hình gốc.** Không thấy bài nào nói đúng câu này. Nhưng đây là kết quả hậu
   nghiệm, và chỉ ghép hai kết quả đã biết. CASE còn cho thấy nhiều phương pháp không vượt mô hình gốc.

## Còn lại gì

- **Phương pháp đánh giá:** tập test niêm phong, đăng ký trước và push trước khi tải dữ liệu, đo `follows` khớp
  chính xác giá trị bị sửa, có phân loại kết quả. Không bài nào ở trên làm đủ những việc này. Đây là ưu điểm về độ
  tin cậy, không phải ý tưởng mới.
- **Thiết lập:** chế độ suy nghĩ của Qwen3, định dạng `Step`/`Calc`, chạy trên máy cá nhân. Chưa đủ để gọi là mới.

## Kết luận

Đề tài không có luận điểm mới về phương pháp hay hiện tượng. Cách nói đứng được: một lần **kiểm chứng lại có đăng ký
trước** các kết quả của LIFT và Lobo và cs. trên Qwen3-8B ở chế độ suy nghĩ, với tập test niêm phong. Bài báo hiện
chỉ trích Lanham và cs.; cần thêm sáu bài trong bảng.

## Quyết định

2026-11-14: người làm đề tài chấp nhận khung "kiểm chứng lại có đăng ký trước". Không nhận phương pháp CF hay hiện tượng SFT làm giảm mức đi theo bước là đóng góp mới.
