# Bản thảo NCKH: Tổng quan Nghiên cứu Liên quan & Phương pháp Thực nghiệm Prospective

**Ngày cập nhật:** 2026-10-25  
**Trạng thái:** Bản thảo phương pháp luận và tổng quan tài liệu phục vụ đề tài NCKH Sinh viên.  
**Nguyên tắc liêm chính học thuật:** Phần phương pháp được viết ở **thì tương lai** (prospective), khung bảng kết quả để trống (`Chưa thu`). Các số liệu lịch sử từ Run 11--13 là số liệu thăm dò phát triển (*development pool*), không lấy làm bằng chứng confirmatory.

---

## 1. Tổng quan Nghiên cứu Liên quan (Related Work)

### 1.1 Cây phân loại văn hiến (Literature Taxonomy)
Các nghiên cứu tối ưu hóa chi phí và hiệu năng tính toán tại thời điểm suy luận (*test-time compute optimization*) trên mô hình ngôn ngữ lớn và nhỏ (LLM/SLM) được chia thành 5 trường phái kỹ thuật chính:

```
                            TEST-TIME COMPUTE OPTIMIZATION
                                          |
    +-------------------+-----------------+-------------------+-------------------+
    |                   |                 |                   |                   |
1. Entry Routing   2. Adaptive       3. Within-Chain     4. Structured       5. Learned Latent
   & Mode Selection   Sampling          Stopping            Search & Tools      Reasoning
   - RTR (2025)       - Adaptive-SC     - Settle (2026)     - ToT (2023)        - Coconut (2024)
   - BEST-Route         (2023)          - SABER (2026)      - GoT (2024)        - AdapThink (2024)
     (2025)           - ESC (2024)      - s1 budget         - CRITIC (2024)
   - AdoT / Thinkless - ReASC (2026)      forcing (2025)
        |                                       |                     |
        +---------------------------------------+---------------------+
                                                |
                                   [ĐỀ TÀI: RAT-CoT DUAL-STAGE]
                                   - Giai đoạn 1: Entry Router theo Utility ($t=0$)
                                   - Giai đoạn 2: Inter-Strategy Escalation / Stopping
                                   - Kiểm chứng bằng Symbolic Verifier & Tool Sandbox
```

1. **Định tuyến đầu vào (Entry Routing & Mode Selection):**
   - *Route to Reason* (Pan et al., 2025) `[pan2025route]` và *BEST-Route* (Ding et al., 2025) `[ding2025bestroute]` phân loại câu hỏi tại thời điểm $t=0$ để chọn mô hình hoặc số lượng mẫu $n$.
   - *Hạn chế:* Đưa ra phán quyết tĩnh một lần khi mô hình chưa bắt đầu suy luận, dễ phán đoán sai độ khó trước các câu hỏi có bề ngoài đơn giản nhưng chứa bẫy logic sâu.
2. **Lấy mẫu thích ứng (Adaptive Sampling):**
   - *Adaptive-Consistency* (Aggarwal et al., 2023) `[aggarwal2023adaptive]`, *ESC* (Li et al., 2024), và *ReASC* (Kim et al., 2026) dừng lấy mẫu Self-Consistency (SC) sớm khi đạt ngưỡng đồng thuận đa số hoặc xác suất hậu nghiệm Beta-Bayes.
   - *Hạn chế:* Chỉ can thiệp vào số lượng nhánh sinh của một chiến lược cố định, chưa hỗ trợ chuyển đổi giữa biểu diễn ngôn ngữ tự nhiên và mã chương trình (code execution).
3. **Cắt tỉa trong chuỗi giải mã (Within-Chain Stopping):**
   - *Settle* (Brown et al., 2026), *SABER* (Cheng et al., 2026), và *s1* (Muennighoff et al., 2025) can thiệp vào tầng logits hoặc chèn token dừng $\langle\text{end-of-reasoning}\rangle$.
   - *Hạn chế:* Đòi hỏi huấn luyện lại trọng số (SFT/RL) hoặc can thiệp sâu vào engine giải mã nội tại, làm mất đi tính tương thích trên các mô hình đóng băng (*frozen SLMs*).
4. **Tìm kiếm cấu trúc và kiểm chứng ngoài (Structured Search & Verification):**
   - *Tree of Thoughts* (Yao et al., 2023) `[yao2023tot]`, *Graph of Thoughts* (Besta et al., 2024), và *CRITIC* (Gou et al., 2024) `[gou2024critic]` mở rộng không gian tìm kiếm và gọi công cụ kiểm tra.
   - *Hạn chế:* Chi phí token tăng theo hàm mũ; nếu thiếu cơ chế dừng có kiểm soát ngân sách thì lãng phí tài nguyên nghiêm trọng.
5. **Suy luận tiềm ẩn học sâu (Learned Latent Reasoning):**
   - *Coconut* (Hao et al., 2024) và *AdapThink* (Snell et al., 2024) `[snell2024scaling]` học suy luận trong không gian vector liên tục.
   - *Hạn chế:* Đánh mất tính giải thích minh bạch của từng bước suy luận đối với người dùng cuối.

---

### 1.2 Bảng ma trận đối chiếu đa chiều

| Tiêu chí phân tích | **Entry Routing (RTR / BEST-Route)** | **Adaptive Sampling (ESC / ReASC)** | **Within-Chain Stopping (Settle / SABER)** | **Structured Search (Tree of Thoughts)** | **Phương pháp Đề xuất (RAT-CoT)** |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Vị trí can thiệp** | Trước khi sinh ($t=0$, Entry Level) | Sau mỗi mẫu sinh $k=1..N$ | Trong quá trình giải mã token | Từng nút nhánh cây tìm kiếm | **2 Giai đoạn:** (1) $t=0$ & (2) Giữa các bậc chiến lược |
| **Không gian hành động** | Chọn cặp $(\text{Model}, \text{Strategy})$ hoặc $n$ mẫu | Nhị phân: $\{ \text{Tiếp tục}, \text{Dừng} \}$ | Token phát tín hiệu dừng chuỗi | Mở rộng cây: $\{ \text{Generate}, \text{Evaluate} \}$ | **Bậc thang chiến lược:** $\text{Direct} \to \text{CoT} \to \text{Tools/Verifier}$ |
| **Trạng thái mô hình** | Frozen SLM (chỉ học router nhẹ ngoài) | Frozen SLM | Cần SFT / RL huấn luyện lại | Frozen SLM | **Frozen SLM** (bảo toàn trọng số gốc an toàn) |
| **Tín hiệu điều khiển** | Không có (chạy hết cấu hình đã chọn) | Tần suất đồng thuận (Beta Bayesian) | Phân phối xác suất token dừng | Heuristic tự đánh giá của LLM | **Calibrated Confidence** $\hat{p}_k$ kết hợp **Symbolic Verifier** |
| **Hàm mục tiêu** | Cân bằng Acc vs Tokens / Proxy Reward | Giữ nguyên Accuracy của full SC | Cắt giảm chiều dài token sinh | Cực đại hóa điểm đường đi | **Đánh đổi Hữu dụng Pareto:** $U = \mathbb{E}[Y] - \lambda \cdot \mathbb{E}[\text{Cost}]$ |
| **Cơ chế dừng sớm** | Không (One-shot) | Dừng lấy mẫu khi vượt ngưỡng tích lũy | Dừng chuỗi token | Cắt tỉa nhánh cây (Pruning) | **Ngưỡng dừng Bellman** $\tau_k$ được hiệu chuẩn ngoại tuyến |
| **Kiểm chứng ngoài** | Không | Không | Không | Thường chỉ LLM tự chấm | **Hỗ trợ Symbolic Verifier & Sandbox Execution** |

---

### 1.3 Ranh giới đóng góp khoa học (Research Gaps)
1. **Khắc phục hạn chế của One-Shot Entry Routing:** Thay vì phán quyết vội vàng ở $t=0$, RAT-CoT sử dụng Entry Router để chọn *điểm xuất phát rẻ nhất*, sau đó kết hợp *Inter-Strategy Escalation*: chỉ khi độ tin cậy được hiệu chuẩn $\hat{p}_1 < \tau_1$ hoặc verifier báo vi phạm ràng buộc thì mới leo thang sang Self-Consistency hoặc Tool.
2. **Khắc phục hiện tượng Tự tin Thái quá & Suy nghĩ Quá mức (Overconfidence & Overthinking):**
   - Huang et al. (2024) `[huang2024large]` chỉ ra LLMs không thể tự sửa lỗi một cách mù quáng nếu thiếu phản hồi độc lập từ môi trường.
   - Caldarella et al. (2026) `[caldarella2026thinking]` chứng minh hiện tượng suy nghĩ quá dài làm hỏng câu trả lời đúng vốn có (*harmful overthinking*).
   - RAT-CoT tích hợp các bộ kiểm định hình thức (*symbolic verifiers*) và hàm hữu dụng kinh tế có hình phạt chi phí $\lambda \cdot \text{Cost}$ trong phương trình dừng tối ưu Bellman để ngăn chặn triệt để lãng phí tính toán.

---

## 2. Thiết kế Phương pháp Thực nghiệm Prospective: Định tuyến Chiều dài GSM8K

> [!IMPORTANT]
> Đây là **thiết kế prospective đang chờ thực hiện**, viết nghiêm ngặt ở **thì tương lai**. Toàn bộ các bảng số liệu đều để trống.

### 2.1 Tập dữ liệu và phân vùng 48/48
- **Nguồn dữ liệu:** GSM8K training set đã khóa tại commit `3101c7d5072418e28b9008a6636bde82a006892c`.
- **Lựa chọn ngẫu nhiên:** Sử dụng xếp hạng băm SHA-256 với seed 42 để chọn 96 nhóm câu hỏi chưa từng xuất hiện trong 24 định danh đã chuẩn hóa của pilot trước đó.
- **Phân chia 48/48:**
  - 48 nhóm fitting (dùng để khớp quy tắc định tuyến).
  - 48 nhóm development validation (dùng để đo lường hiệu năng).
  - Cả hai phần đều thuộc development pool; tập official test tuyệt đối không được đụng tới.
- **Kiểm duyệt dữ liệu:** 96 câu hỏi đã được nhóm nghiên cứu giải độc lập từ đề bài trước khi so sánh đáp án gốc: 93 câu hoàn toàn trùng khớp logic, 3 câu thuộc tập fitting đang chờ phê duyệt đề xuất làm rõ câu chữ (adjudication proposal).

### 2.2 Không gian quyết định và hàm hữu dụng
- **Không gian chiến lược:** DIRECT, CoT, PAL.
- **Đặc trưng duy nhất:** Số từ phân tách bằng khoảng trắng (*whitespace-delimited word count*) của câu hỏi gốc, trước khi nối hậu tố chỉ dẫn chiến lược.
- **Menu 27 quy tắc cố định:** 24 quy tắc 2 nhánh tại các ngưỡng cắt 20, 40, 60, 80 từ kết hợp với 3 quy tắc hằng (luôn DIRECT, luôn CoT, luôn PAL). Không dùng leo thang, stopping hay embedding trong baseline này.
- **Hàm hữu dụng (Utility):**
  $$\text{Utility} = \text{Accuracy} - 0.1 \times \frac{\text{Mean Generated Tokens}}{1000}$$
- **Quy tắc phân xử hòa (Tie-breaking):** Ưu tiên Accuracy cao hơn $\to$ Token thấp hơn $\to$ Quy tắc hằng $\to$ Thứ tự từ điển của mã quy tắc.
- **Niêm phong quyết định (Sealed Selection):** Quy tắc được chọn và điểm số trên tập fitting bắt buộc phải được tính toán, lưu trữ và băm bất biến (SHA-256) trước khi mở xem điểm số validation.

### 2.3 Cấu hình mô hình và thực thi
- **Mô hình nền tảng:** `mlx-community/Qwen3-8B-4bit` (revision `545dc4251c05440727734bcd94334791f6ab0192`).
- **Tham số sinh:** Prompt profile `english-math-v1`, temperature 0, thinking off, generation seed 42, trần 1.024 tokens/lượt gọi.
- **Sandbox PAL:** Thực thi Python độc lập với timeout helper 5 giây.
- **Bảo mật đề bài:** Mô hình tuyệt đối không nhận được lời giải hoặc đáp án mẫu từ tập dữ liệu.
- **Ngân sách tối đa:** 96 câu $\times$ 3 chiến lược = 288 generation calls, tối đa 294.912 generated tokens.

---

### 2.4 Khung bảng kết quả dự kiến (Chưa có số đo)

| Phương pháp (Method) | Accuracy | Mean Gen Tokens | Mean Prompt Tokens | Utility | PAL Failures |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Query-only selected rule** | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* |
| **Fitting-selected fixed reference** | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* |
| **DIRECT** | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* | Không dùng tool |
| **CoT** | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* | Không dùng tool |
| **PAL** | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* | *Chưa thu* |

---

### 2.5 Phân tích thống kê & Các tuyên bố giới hạn bắt buộc
- **Khoảng tin cậy Bootstrap:** Khoảng tin cậy phân vị 95% dự kiến tính từ 2.000 lượt lấy mẫu lại có hoàn lại (*group-bootstrap draws*) theo đơn vị nhóm trên tập validation, seed 42.
- **Tính có điều kiện:** Khoảng tin cậy có điều kiện dựa trên quy tắc đã chọn và seed quan sát được; không bao gồm độ bất định của bước fitting và không chứng minh tính vững chắc trên nhiều seed.
- **Giữ nguyên kết quả âm:** Khoảng tin cậy chứa 0 không chứng minh tính tương đương; mọi kết quả âm tính đều phải được báo cáo trung thực, không thay đổi quy tắc hay ngưỡng cắt sau khi quan sát tập validation.
- **Khai báo giới hạn chi phí:** Token sinh chỉ là một phần chi phí; không đại diện cho toàn bộ chi phí suy luận thực tế (full inference compute), độ trễ online của controller, hay mức tiêu thụ năng lượng.
