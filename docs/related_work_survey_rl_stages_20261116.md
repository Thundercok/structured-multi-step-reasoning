# Khảo sát: mức bám bước qua các chặng huấn luyện (Base, SFT, RL)

Ghi ngày 2026-11-16. Hướng đang xét: đo mức bám bước bị sửa ở các chặng Base, SFT, RL-Zero, RL của MiMo-7B. Metadata
lấy từ arXiv API; RFEval đọc từ bản HTML v3, các bài còn lại mới đọc tóm tắt.

## Các bài gần nhất

| Bài | Làm gì | Kết quả về chặng huấn luyện |
| --- | --- | --- |
| RFEval, Han, Lee, Do (arXiv 2602.17053, 2026-02) | Chèn đoạn suy luận phản thực do LLM viết vào vết suy luận, xem lập trường và đáp án có đổi theo không; LLM chấm; greedy; 7 nhóm việc, có GSM8K | **Làm đúng hướng này.** Ablation cùng họ trên **MiMo-7B** và **Olmo-3-7B** (Base, SFT-only, RL-only, SFT+RL): SFT giữ nguyên hoặc tăng nhẹ độ trung thực, thêm RLVR sau SFT làm giảm. MiMo: 59,3 / 60,1 / 58,7 / 46,3 |
| Yu, Tartaglini, Hase, Guestrin, Potts (arXiv 2604.22074, 2026-04) | Đo tác động nhân quả của các token suy luận lên đáp án (CIR) | RLVR tăng độ đúng nhưng không tăng đều CIR; một ít SFT trước RLVR giúp tăng |
| Basu, Chakraborty (arXiv 2603.22816, 2026-03) | Đo tỉ lệ bước thật sự cần cho đáp án trên 16 mô hình | Khác biệt chính nằm ở cách huấn luyện RL, không ở việc có token suy nghĩ |
| Chen và cs., Anthropic (2025) | Đo việc mô hình có nói ra gợi ý mà nó dùng hay không | RL theo kết quả làm tăng độ trung thực lúc đầu, rồi chững lại ở mức thấp |

## Kết luận

Hướng 1 như đã nêu **đã có người làm**: RFEval dùng chính MiMo-7B và cùng câu hỏi theo chặng. Làm lại trên MiMo với
phép đo khớp chính xác của mình thì lại chỉ là một lần kiểm chứng lại.

## Chỗ còn mở (chưa khảo sát kỹ)

Hai kết quả không khớp nhau:

- RFEval: SFT **không** làm giảm độ trung thực so với Base (SFT chính thức của MiMo và Olmo: dữ liệu lớn, vết dài do
  mô hình thầy viết).
- Lobo và cs. (2411.15382) và H2 của đề tài (đã lặp lại trên GSM-Plus): SFT **làm giảm** (LoRA hoặc QLoRA nhỏ, theo
  một việc cụ thể).

Câu hỏi: **tính chất nào của SFT làm giảm mức bám bước?** Ví dụ: cỡ dữ liệu, chỉ một việc hay nhiều việc, LoRA hay
tinh chỉnh toàn bộ, vết tự sinh hay do mô hình thầy viết. Phép đo khác nhau (khớp chính xác so với LLM chấm lập trường)
cũng có thể là nguyên nhân. Cần khảo sát riêng câu hỏi này trước khi chọn.

## Khảo sát câu hỏi hẹp: tính chất nào của SFT làm giảm mức bám bước (2026-11-16)

Tìm theo các yếu tố: LoRA hay tinh chỉnh toàn bộ, cỡ dữ liệu, vết tự sinh hay do mô hình thầy viết, một việc hay
nhiều việc. Đọc tóm tắt trên arXiv.

| Bài | Liên quan |
| --- | --- |
| Lobo và cs. (2411.15382) | SFT làm giảm độ trung thực, rõ hơn ở mô hình nhỏ và khi tinh chỉnh trên dữ liệu không phải suy luận; GPT-4 gần như không đổi. Không tách các yếu tố của SFT |
| Tanneru và cs. (2406.10625) | Tinh chỉnh chỉ tăng nhẹ độ trung thực trong điều kiện hẹp, không tổng quát |
| SCOTT, Wang và cs. (ACL 2023) | Vết do thầy viết mà không nhất quán thì trò học theo; mục tiêu phản thực giúp tăng |
| Xu và cs. (2611.01967, 2026-11) | **Gần nhất về cách làm.** Chưng cất on-policy tăng độ đúng nhưng làm mô hình bỏ qua bằng chứng bị sửa (+15,7 điểm), mức bỏ qua tăng theo việc mô hình đã thiên về đáp án cũ trước khi huấn luyện. Có nghiên cứu tách yếu tố huấn luyện. Nhưng đây là bằng chứng trong tài liệu, không phải bước suy luận |
| Peng và cs. (2602.14469) | Vết sinh khi đã thấy đáp án gây hợp lý hóa sau; ảnh hưởng tới mô hình trò |

**Chưa thấy bài nào** tách các yếu tố của SFT để xem yếu tố nào làm giảm mức bám bước suy luận bị sửa. Tìm kiếm chưa
đầy đủ, nên đây là khoảng trống có khả năng, chưa chắc chắn.

Một giả thuyết cơ chế lấy từ Xu và cs.: SFT làm mô hình "nhớ" đáp án, nên ít phải dựa vào bước. Kiểm được ngay trên dữ
liệu có sẵn: các câu mà mô hình đoán đúng đáp án khi chưa viết bước có bám bước ít hơn không.

## Quyết định

2026-11-16: người làm đề tài chọn câu hỏi "tính chất nào của SFT làm giảm mức bám bước" làm hướng nghiên cứu chính
cho giai đoạn tới. Kết quả GSM8K và GSM-Plus hiện có là bài 1 (nền móng: công cụ đo, quy trình, H2 đã lặp lại).
