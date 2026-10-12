# Paper tham khảo

Cập nhật: 2026-10-01. Danh mục phục vụ đọc và trích dẫn cho đề tài NCKH;
đây chưa phải tổng quan tài liệu đầy đủ hay kết luận về tính mới.
Ghi chú ngắn dựa trên abstract/trang xuất bản gốc, cùng phần phương pháp DA đã
đối chiếu. Chưa tái lập các thực nghiệm của những paper này.

BibTeX: [references.bib](references.bib). Mỗi dòng dưới đây có link nguồn gốc.
Năm trong BibTeX là năm của bản được trích: bản hội nghị nếu dùng ACL Anthology,
bản arXiv nếu dùng arXiv; không suy diễn tình trạng phản biện từ việc có preprint.

## Định tuyến và phân bổ suy luận

| Paper | Năm bản tham khảo | Nội dung liên quan | BibTeX key |
| --- | --- | --- | --- |
| [Route to Reason](https://arxiv.org/abs/2505.19435) | 2025, arXiv | Chọn kết hợp mô hình và chiến lược theo truy vấn; cần đối chiếu khi nói về entry routing của repo. | `pan2025route` |
| [BEST-Route](https://arxiv.org/abs/2506.22716) | 2025, arXiv | Chọn mô hình cùng số lượng câu trả lời cần lấy mẫu; liên quan phân bổ ngân sách cho mô hình nhỏ. | `ding2025bestroute` |
| [Adaptive-Consistency](https://aclanthology.org/2023.emnlp-main.761/) | 2023, EMNLP | Điều chỉnh số mẫu theo mức đồng thuận và tiêu chí dừng; tham khảo trực tiếp cho adaptive stopping. | `aggarwal2023adaptive` |
| [Scaling Test-Time Compute](https://arxiv.org/abs/2408.03314) | 2024, arXiv | Nghiên cứu phân bổ tính toán theo độ khó bài toán; hữu ích khi thiết kế so sánh accuracy và chi phí. | `snell2024scaling` |

## Truy xuất và độ đầy đủ của bằng chứng

| Paper | Năm bản tham khảo | Nội dung liên quan | BibTeX key |
| --- | --- | --- | --- |
| [Adaptive-RAG](https://aclanthology.org/2024.naacl-long.389/) | 2024, NAACL | Phân loại độ phức tạp để chọn không truy xuất, truy xuất một bước hoặc nhiều bước. | `jeong2024adaptive` |
| [Self-RAG](https://arxiv.org/abs/2310.11511) | 2023, arXiv | Huấn luyện mô hình truy xuất khi cần và đánh giá tài liệu/đầu ra bằng reflection tokens. | `asai2023selfrag` |
| [IRCoT](https://aclanthology.org/2023.acl-long.557/) | 2023, ACL | Xen kẽ truy xuất và suy luận cho câu hỏi nhiều bước, để thông tin đã tìm được dẫn hướng lần tìm tiếp theo. | `trivedi2023ircot` |
| [FLARE](https://aclanthology.org/2023.emnlp-main.495/) | 2023, EMNLP | Dùng dự đoán câu tiếp theo và tín hiệu thiếu tự tin để chủ động tìm tài liệu rồi sinh lại câu. | `jiang2023flare` |
| [Sufficient Context](https://arxiv.org/abs/2411.06037) | 2024, arXiv; bản sửa 2025 | Phân biệt lỗi do ngữ cảnh thiếu dữ kiện với lỗi mô hình dùng ngữ cảnh; liên quan quyết định trả lời hoặc từ chối. | `joren2024sufficient` |

## Phạm vi đọc và độ ổn định của truy vấn

| Paper | Năm bản tham khảo | Nội dung liên quan | BibTeX key |
| --- | --- | --- | --- |
| [Declarative Attention](https://arxiv.org/abs/2609.02737) | 2026, arXiv | Mô hình khai báo phạm vi chú ý và inference engine thực thi attention mask; đây là paper trong nội dung Facebook bạn gửi. | `ho2026attention` |
| [LLMLingua-2](https://aclanthology.org/2024.findings-acl.57/) | 2024, Findings of ACL | Nén prompt bằng phân loại token, có thể tham khảo khi nghiên cứu chi phí xử lý ngữ cảnh. | `pan2024llmlingua2` |
| [How You Ask Matters!](https://arxiv.org/abs/2604.10745) | 2026, arXiv | Đánh giá tác động của cách diễn đạt cùng một ý định lên chất lượng, chi phí và quyết định truy xuất. | `jang2026queryvariations` |

## Ghi chú cho bài được gửi: Declarative Attention

Nguồn phương pháp: [bản HTML v1](https://arxiv.org/html/2609.02737v1), đặc biệt
phần 2.3 và 5.4. Tác giả thuộc KAIST và Google DeepMind; nộp arXiv ngày 02/09/2026.

- Ba chế độ là đọc toàn bộ ngữ cảnh, đọc đoạn được chỉ định, hoặc dựa vào phần
  câu trả lời đã sinh; câu hỏi và chỉ dẫn vẫn được giữ.
- Thực thi mask ở tầng inference là phần thiết yếu. Chỉ thêm thẻ vào prompt
  hoặc chọn đoạn ở tầng ứng dụng không phải tái lập DA.
- Lượng token được attention truy cập khác số token được sinh ra. Bộ đo hiện
  tại của repo chưa đo chi phí attention.
- Các con số thời gian 0,71×/0,77× là dự báo từ mô hình hiệu năng, không phải
  số đo thời gian thực để đem so trực tiếp với app trên Mac.

## Thứ tự đọc gợi ý

Đối với phần nghiên cứu đang có: Route to Reason → Adaptive-Consistency →
BEST-Route. Đối với nhánh tìm tài liệu: Sufficient Context → Adaptive-RAG →
IRCoT → Self-RAG. Đọc DA khi cần hiểu thêm việc điều khiển phạm vi chú ý.

Khi đọc sâu, ghi riêng giả định, dữ liệu, baseline, nguồn chi phí và phần cần
huấn luyện của từng paper. Các ý tưởng routing, dừng thích nghi và xen kẽ
retrieval/reasoning đã có nghiên cứu trước; danh mục này không xác nhận rằng
ghép chúng lại là một đóng góp mới.
