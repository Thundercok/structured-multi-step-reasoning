# Ma trận Phân loại & Đối chiếu Khoa học (Literature Taxonomy Matrix)

**Đề tài NCKH**: Điều phối chiến lược suy luận và quyết định dừng theo ngân sách cho mô hình ngôn ngữ nhỏ.  
**Mô hình mục tiêu**: Frozen Small Language Model (SLM, ưu tiên Qwen 1.5B–8B).  
**Ngày cập nhật**: 21/10/2026.  
**Cơ sở dữ liệu khảo sát**: 57 công trình nghiên cứu (2022–2026) được lập chỉ mục tại [docs/surveys/research_survey_20261013.md](research_survey_20261013.md).

---

## 1. Bản đồ Phân loại Cấu trúc (Structural Taxonomy)

Các phương pháp tối ưu hóa compute lúc test-time trong văn hiến được phân tách thành 6 họ phương pháp dựa trên **vị trí can thiệp** và **cơ chế điều khiển**:

```
                                  TỐI ƯU HÓA SUY LUẬN LÚC TEST-TIME
                                                  |
        +-------------------------+---------------+-------------------------+
        |                         |                                         |
  [TRƯỚC KHI SINH]         [TRONG KHI SINH]                          [SAU KHI SINH LỜI GIẢI]
  (Pre-generation)         (Within-chain token level)                (Inter-response / Multi-step)
        |                         |                                         |
1. Entry Routing           3. Within-Chain Stopping                  2. Adaptive Sampling
   & Mode Selection           - Cắt tỉa token (CoD)                     - Dừng lấy mẫu SC sớm (ESC, ReASC)
   - RTR, BEST-Route,         - Token dừng (Settle)                     - Dừng Bayes (Bayesian Stopping)
     AdoT, Thinkless          - Ép dừng (s1 budget forcing)                 |
        |                                                            4. Structured Search & Verification
5. Learned Reasoning                                                    - Cây/Đồ thị (ToT, GoT)
   (Sửa weights/latents)                                                - Bộ kiểm chứng ngoài (SSV, CRITIC)
   - AdapThink, Coconut                                                     |
                                                                     [ĐỀ TÀI CỦA CHÚNG TA: RAT-CoT]
                                                                     - 2 Giai đoạn: Entry Router + Stopping
                                                                     - Bậc thang chiến lược (Strategy Ladder)
                                                                     - Ngưỡng dừng Bayes/Bellman theo Utility
```

---

## 2. Bảng Ma trận Đối chiếu Đa chiều với Các Công trình Trọng yếu

Bảng dưới đây so sánh đề tài nghiên cứu của nhóm với các đại diện tiêu biểu nhất trong từng họ phương pháp theo 7 thuộc tính kỹ thuật cốt lõi:

| Tiêu chí phân tích | **Self-Consistency** (Wang et al., 2022) | **Tree of Thoughts** (Yao et al., 2023) | **Route to Reason** (Pan et al., 2025) `[R01]` | **BEST-Route** (Ding et al., 2025) `[R04]` | **ESC / ReASC** (Li 2024 / Kim 2026) `[S02, S06]` | **Settle / SABER** (Brown 2026 / Cheng 2026) `[C12, C13]` | **Phương pháp Đề xuất (RAT-CoT Dual-Stage)** |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Vị trí can thiệp (Intervention Level)** | Post-hoc (Tổng hợp $K$ mẫu) | Trong quá trình sinh (Từng bước nút cây) | Trước khi sinh ($t=0$, Entry Routing) | Trước khi sinh ($t=0$, Joint Routing) | Sau mỗi mẫu sinh trong tập mẫu $k=1..N$ | Bên trong chuỗi sinh token (Within-chain) | **2 Giai đoạn**: (1) Trước khi sinh ($t=0$) & (2) Giữa các bậc chiến lược |
| **2. Không gian hành động (Action Space)** | Lấy mẫu $K$ đường CoT song song | Mở rộng cây: $\{ \text{Generate}, \text{Evaluate} \}$ | Chọn 1 cặp: $(\text{Model}, \text{Strategy})$ | Chọn đồng thời: $(\text{Model}, n \text{ samples})$ | Quyết định nhị phân: $\{ \text{Sample tiếp}, \text{Dừng} \}$ | Token phát tín hiệu: $\langle\text{end-of-reasoning}\rangle$ | **Bậc thang chiến lược**: $\{ \text{Direct CoT} \to \text{SC} \to \text{External Tool/Verifier} \}$ |
| **3. Trạng thái Mô hình (Model Weights)** | **Frozen** (Không đổi trọng số) | **Frozen** | **Frozen** (Chỉ học router ngoài) | **Frozen** (Học router + reward model) | **Frozen** | **Cần SFT / RL** (Huấn luyện lại head/token) | **Frozen SLM** (Đảm bảo tính tổng quát và an toàn khi inference) |
| **4. Tín hiệu Điều khiển Dừng (Stopping Signal)** | Không có (Luôn sinh đủ $K$ mẫu) | Điểm heuristic tự đánh giá của LLM | Không có (Chạy hết chiến lược đã chọn) | Không có (Sinh đủ $n$ mẫu rồi Best-of-N) | Tần suất đồng thuận (Consensus) / Beta Bayesian | Xác suất phân phối token dừng / Nhánh đối kháng | **Calibrated Posterior Confidence** $\hat{p}_k$ kết hợp **Symbolic Verifier** |
| **5. Hàm Mục tiêu Tối ưu (Objective Function)** | Majority Voting $\arg\max_y \sum \mathbf{1}(y_i=y)$ | Maximize Path Evaluation Score | Cân bằng Accuracy vs Output Tokens | Proxy Reward của Best-of-N | Giữ nguyên Accuracy của full SC | Cắt giảm chiều dài token sinh | **Đánh đổi Hữu dụng Kinh tế (Pareto Utility)**: $U = \mathbb{E}[Y] - \lambda \cdot \mathbb{E}[\text{Cost}]$ |
| **6. Cơ chế Dừng sớm (Early Exit Mechanism)** | ❌ Không | ⚠️ Cắt tỉa nhánh (Pruning) | ❌ Không (One-shot) | ❌ Không (Cố định $n$) | ✅ Dừng lấy mẫu khi vượt ngưỡng tích lũy | ✅ Dừng giải mã chuỗi token | ✅ **Ngưỡng dừng tối ưu Bellman** $\tau_k$ được hiệu chuẩn ngoại tuyến |
| **7. Khả năng Kiểm chứng Ngoài (External Verification)** | ❌ Không | ❌ Không (Chỉ LLM tự chấm) | ❌ Không | ⚠️ Qua Reward Model chấm điểm | ❌ Không | ❌ Không | ✅ **Hỗ trợ Symbolic Verifier / Tool Execution** khi phát hiện không chắc chắn |

---

## 3. Ranh giới Khác biệt Khoa học (Scientific Novelty & Research Gap)

Từ việc tổng hợp 57 công trình, ranh giới đóng góp và sự khác biệt của đề tài được định vị rõ ràng qua 3 luận điểm cốt lõi:

### Luận điểm 1: Khắc phục hạn chế của One-Shot Entry Routing (vs. R01 Route to Reason, R04 BEST-Route)
- **Hạn chế của prior art**: Các router ở đầu vào (như RTR, BEST-Route, AdoT) buộc phải đưa ra quyết định toàn cục chỉ dựa trên embedding câu hỏi lúc $t=0$. Tại thời điểm này, mô hình **chưa thực sự suy nghĩ**, nên dễ ước lượng sai độ khó đối với các bài toán có bề ngoài đơn giản nhưng bẫy logic sâu.
- **Giải pháp của nhóm**: Kết hợp **Entry Routing** (chọn điểm xuất phát rẻ nhất có thể) với **Inter-Strategy Escalation**: Nếu sau khi sinh CoT ban đầu, tín hiệu độ tin cậy được hiệu chuẩn $\hat{p}_1 < \tau_1$, hệ thống mới kích hoạt nâng bậc lên Self-Consistency hoặc Tool.

### Luận điểm 2: Khắc phục sự tự tin thái quá & Giới hạn Tự sửa lỗi (vs. E02, E03, E06, H01)
- **Cảnh báo từ văn hiến**:
  - `[E03]` (Huang et al., ICLR 2024): *LLMs Cannot Self-Correct Reasoning Yet* — mô hình nhỏ không thể tự sửa lỗi nếu không có phản hồi độc lập từ bên ngoài.
  - `[H01]` (Caldarella et al., 2026): *Thinking Past the Answer* — suy nghĩ quá dài dẫn đến "harmful overthinking" (làm hỏng câu trả lời vốn đã đúng ở các bước đầu).
  - `[E06]` (Mei et al., 2026): *Do Reasoning Models Know When They Don't Know?* — suy luận càng sâu càng làm trầm trọng hóa overconfidence.
- **Giải pháp của nhóm**:
  - Không dựa vào LLM tự phê bình văn bản mù quáng.
  - Sử dụng **Isotonic / Platt Calibration** để ép điểm confidence về đúng xác suất tiên nghiệm.
  - Áp dụng **Hình phạt Chi phí** $\lambda \cdot \text{Cost}$ trong phương trình Bellman: Ngăn chặn triệt để hiện tượng overthinking vì mỗi bước leo thang đều phải trả giá bằng token ròng.
  - Tích hợp **Symbolic / Deterministic Verifier** (kiểm tra cú pháp, thực thi phép tính độc lập) thay vì dùng LLM verifier yếu `[E02, V07]`.

### Luận điểm 3: Khắc phục định kiến đánh giá chi phí thiếu công bằng (vs. E05 Token Economies)
- **Cảnh báo từ văn hiến**: `[E05]` (Wang et al., EMNLP 2024) chỉ ra rằng rất nhiều bộ điều phối phức tạp thực chất chỉ "ăn may" nhờ việc vô tình tiêu tốn nhiều token hơn; khi chuẩn hóa về cùng một ngân sách compute, CoT + SC đơn giản thường chiến thắng.
- **Nguyên tắc đánh giá của nhóm**:
  - Đánh giá trực tiếp trên đường biên **Pareto Accuracy–Token** tại nhiều mức $\lambda$ khác nhau.
  - Mọi chiến lược đối chứng đều chạy trên cùng một tập output cache/journal để loại trừ sai số ngẫu nhiên của bộ sinh (generation noise).
  - Phân tách rõ ràng giữa:
    1. *Rescue gain*: Số câu trả lời sai ở CoT được cứu đúng nhờ leo thang.
    2. *Corruption loss*: Số câu trả lời đúng ở CoT bị làm sai do leo thang dư thừa.
    3. *Wasted budget*: Chi phí token đổ vào các câu không thể cứu được.

---

## 4. Ma trận Rủi ro & Chiến lược Phòng thủ Thực nghiệm (Risk Mitigation)

| Rủi ro khoa học đã được chỉ ra trong Survey | Hệ quả tiềm ẩn | Cơ chế kiểm soát chặt chẽ trong Repo của nhóm |
| :--- | :--- | :--- |
| **Data Leakage giữa Router và Test** (`[R01]` note) | Router học vẹt câu hỏi, kết quả test bị phóng đại | Enforce chia 3 tập độc lập: Train (fit predictor), Calibration (fit stopping thresholds $\tau_k$), và Test (held-out evaluate). Không overlap ID. |
| **Uncalibrated Logprob** (`[E06]`) | Điểm confidence ảo dẫn đến dừng sai thời điểm | Stage 0 Gate: Bắt buộc kiểm tra $\Delta\text{AUROC}$ của logprob so với baseline độ dài trước khi cho phép policy kích hoạt. |
| **Token Accounting Mập mờ** (`[E05]`) | Báo cáo chi phí không phản ánh latency thực tế | Phân tách rành mạch: `generated_tokens`, `prompt_tokens`, và phân biệt thời gian replay offline với latency online thực tế. |
| **Harmful Drift / Overthinking** (`[H01]`) | Leo thang chiến lược làm giảm điểm so với CoT đơn lẻ | Hàm mục tiêu $U = \text{Acc} - \lambda \cdot \text{Cost}$ tự động phạt các hành động leo thang không mang lại xác suất thắng vượt trội. |
