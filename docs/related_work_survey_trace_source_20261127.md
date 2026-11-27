# Khảo sát văn liệu (Cổng 2): Nguồn vết (`self` vs. `human`) × Độ bám bước phản thực

**Ngày khảo sát:** 2026-11-27
**Phạm vi kiểm tra:** arXiv Atom API (metadata + tóm tắt nguyên bản) và tìm kiếm web học thuật. Chưa quét toàn văn ACL Anthology / OpenReview / Google Scholar — vì vậy trong bài báo chỉ viết *"theo hiểu biết của chúng tôi"* (*to our knowledge*), không khẳng định tuyệt đối *"chưa ai làm"*.

---

## 1. Ba nhóm công trình gần nhất (đã xác minh trực tiếp qua arXiv API)

### Nhóm A — SFT làm giảm độ trung thực CoT (hiện tượng đã biết, chưa tách yếu tố nguồn vết)
| Công trình | arXiv / Năm | Đã làm | Khác biệt với đề tài của chúng ta |
|---|---|---|---|
| **Lobo et al.** — *On the Impact of Fine-Tuning on Chain-of-Thought Reasoning* | `2411.15382` (11/2024) | Đo QLoRA 4-bit SFT trên GSM8K, MedQA, CosmosQA; cho thấy SFT làm giảm độ trung thực trung bình | Không tách yếu tố của SFT (không so vết `self` vs. `human`, không quét liều lượng) |
| **RFEval** (Han, Lee, Do) — *Benchmarking Reasoning Faithfulness under Counterfactual Reasoning Intervention* | `2602.17053` (02/2026) | So chặng Base / SFT / RL trên MiMo-7B, Olmo-3-7B bằng can thiệp do LLM viết & chấm | Không tách nguồn vết trong SFT; không đo khớp giá trị tất định |

### Nhóm B — Phương pháp huấn luyện tăng độ trung thực (tăng cường phản thực / RL)
| Công trình | arXiv / Năm | Đã làm | Khác biệt với đề tài của chúng ta |
|---|---|---|---|
| **LIFT** (Swaroop et al.) | `2509.13334` (09/2025) | LoRA trên vết phản thực đã lọc tác động nhân quả (Qwen3-8B, GSM8K) | Tập trung tạo phương pháp tăng cường; không kiểm tra nguồn vết (`self` vs. `human`) hay độ bền OOD trên GSM-Plus |
| **CCR** (Akter et al.) | `2509.01544` (09/2025) | Đổi toán tử trong vết làm dữ liệu phản thực trên GSM8K | Tương tự LIFT: tối ưu mục tiêu huấn luyện, không tách nguồn vết |
| **CASE** (Wang et al.) | `2607.18820` (07/2026) | CoT phản thực + mặt nạ attention trên Qwen3-8B | Tương tự, không kiểm định giả thuyết nguồn vết |
| **CST** (Hase & Potts) | `2602.20710` (02/2026) | Thưởng CoT giúp mô phỏng đầu ra trên đầu vào phản thực | Đo khả năng mô phỏng (simulability), không phải bám bước tính toán trung gian |
| **Chain of Faith** (Meng & Kong) | `2611.02672` (11/2026) | Thêm 4 hàm thưởng nội tại (policy-internal rewards) vào GRPO trên GSM8K, StrategyQA | Hướng RL (GRPO), không phải chẩn đoán nguyên nhân suy giảm dưới SFT |

### Nhóm C — Chênh lệch phân phối `on-policy` / `self-generated` vs. `off-policy` / `human` trong SFT
| Công trình | arXiv / Năm | Đã làm | Khác biệt với đề tài của chúng ta |
|---|---|---|---|
| **Gekhman et al.** — *Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?* | `2405.05904` (EMNLP 2024) | SFT trên tri thức mới làm tăng ảo giác tuyến tính theo mức học | Đo ảo giác tri thức sự kiện (factual QA), không đo độ bám bước CoT |
| **SDFT** (Shenfeld et al.) — *Self-Distillation Enables Continual Learning* | `2601.19897` (01/2026) | Tự chưng cất on-policy từ mẫu minh họa để tránh quên thảm họa | Đo độ đúng & quên liên tục, không đo độ bám bước phản thực |
| **Towards On-Policy SFT** (Zhang et al.) | `2602.12222` (02/2026) | Lý thuyết phân biệt phân phối (DDT), IDFT và Hinted Decoding cho On-Policy SFT | Đo tổng quát hóa & độ đúng, không đo độ trung thực / can thiệp bước |
| **On-Policy SFT for Efficient Reasoning** (Zhao et al.) | `2602.13407` (02/2026) | Lọc vết tự sinh đúng & ngắn gọn làm SFT on-policy | Đo cân bằng độ đúng – độ dài token, không đo độ bám bước |
| **Peng et al.** — *Measuring and Mitigating Post-hoc Rationalization in Reverse CoT* | `2602.14469` (02/2026) | Vết sinh khi đã lộ đáp án (Reverse CoT) gây hợp lý hóa sau và lệch train–inference | Cơ chế khác: lộ đáp án khi sinh vết; ở thí nghiệm của ta cả vết `self` và `human` đều là lời giải thuận hợp lệ |
| **Xu et al.** — *Better Answers, Weaker Evidence Control: Evidence Bypass in On-Policy Distillation* | `2611.01967` (11/2026) | **Đối chiếu rất hay cho phần Discussion:** chưng cất on-policy (OPD) tăng độ đúng QASPER/PeerQA nhưng làm tăng bỏ qua bằng chứng bị sửa (+15,7 đ%) | Can thiệp vào *tài liệu nguồn* (document QA) dưới OPD, không phải bước tính toán tự viết (`Calc`) dưới SFT; cho thấy hiệu ứng nguồn dữ liệu phụ thuộc vào ngữ cảnh (tài liệu ngoài vs. suy luận nội tại) |

---

## 2. Kết luận Cổng 2: **ĐẠT (có chỗ đứng rõ cho EACL 2027 SRW Short Paper)**

1. **Khoảng trống xác thực:** Chưa thấy công trình nào trên arXiv tách riêng **nguồn vết huấn luyện (`self-generated` vs. `human-written`)** trên cùng một tập câu hỏi bằng **thiết kế trộn lồng nhau theo liều lượng (0/25/50/75/100%)**, đo trực tiếp **độ bám bước tính toán trung gian tất định (`follows`)** có tiền đăng ký, đồng thời đặt cạnh kết quả âm tính của tăng cường phản thực trên GSM-Plus (H1 không lặp lại so với H3/H4 lặp lại rõ).
2. **Cách định vị an toàn & sắc cho bài 4 trang:**
   - Nối trực tiếp hai dòng văn liệu đang tách rời nhau: **(i) SFT làm giảm độ trung thực CoT** (Lobo et al., 2024; LIFT; CASE) và **(ii) chênh lệch phân phối off-policy vs. on-policy trong SFT** (Gekhman et al., 2024; SDFT, 2026; Zhang et al., 2026).
   - Đặt đối chiếu với **Xu et al. (2026)** ở phần Discussion để tránh tuyên bố quá đà rằng "on-policy luôn tốt cho mọi dạng trung thực".
