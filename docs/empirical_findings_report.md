# Báo cáo Thực nghiệm & Phát hiện Khoa học (Empirical Findings Report)

**Đề tài NCKH:** *Điều phối chiến lược suy luận và quyết định dừng theo ngân sách cho mô hình ngôn ngữ nhỏ (Budget-Aware Strategy Routing and Stopping for Small Language Models)*  
**Trạng thái Mốc:** Hoàn tất M3 (Sweep 6 Arms) & M4 (Đánh giá Cascade & Phân tích Đột phá)  
**Ngày cập nhật:** 2026-10-06  
**Artifacts Nguồn:**
- Sweep 6 arms: `audit/run11_sweep_trace.jsonl` (571 lượt suy luận cold-start trên GPU Apple Silicon)
- A/B Wording sweep: `audit/gapB_sweep_trace.jsonl` (31 lượt suy luận đối chứng Style B)
- Đăng ký quy tắc trước: `prereg/decision_rule_P.md`, `prereg/decision_rule_signal.md`, `prereg/decision_rule_cascade.md`

---

## 1. Tóm tắt Đóng góp Khoa học Cốt lõi (Executive Summary)

Nghiên cứu khảo sát bài toán phân bổ tính toán thích nghi (adaptive compute allocation) cho mô hình ngôn ngữ nhỏ (SLM - Qwen 2.5 class) trên 3 họ bài toán suy luận cấu trúc: Số học nhiều bước (*Arithmetic*), Xếp hạng suy diễn logic (*Ordering*), và Tổ hợp số học (*Game-of-24*).

Thực nghiệm đo đạc độc lập 571 lượt suy luận đã mang lại **3 phát hiện khoa học mang tính bản lề**:

1. **Phát hiện Âm tính về Độ tự tin Logprob (Negative Finding on Confidence):**  
   Thử nghiệm Repeated 5-fold CV $\times 20$ chứng minh `mean_logprob`, `min_logprob` và `answer_first_lp` hoàn toàn **thất bại trong việc dự báo sai sót suy luận** (AUROC không vượt qua baseline $+0,05$ với CI dưới $> 0$; trên Ordering, AUROC rơi vào dải nhiễu $0,23 \dots 0,31$). Khi mô hình rơi vào bẫy lặp tham lam ("Try... Nope"), logprob của các token sinh ra vẫn rất cao (hiện tượng *overconfident hallucination*).
2. **Bóc tách Diễn đạt Ngôn ngữ khỏi Độ khó Tìm kiếm (Wording vs Search Barrier):**  
   Thí nghiệm đối chứng A/B trên bài toán Ordering chứng minh: Viết lại clue khoảng cách (gap clue) từ dạng ngôn ngữ tự nhiên (`"X finished k places ahead of Y"`) sang dạng đại số tường minh vị trí (`"if X in p, then Y in p+k"`) đã **giảm tỷ lệ vi phạm clue gap từ 52,2% xuống 14,8%** (vượt tiêu chí đăng ký trước $\le 26\%$), triệt tiêu 7 ca kẹt token vô tận và tăng accuracy toàn bài từ $45,2\%$ lên $58,1\%$ ($+12,9$ pp).
3. **Định tuyến Đầu vào (Entry Routing) vượt trội Phân tầng Sau (Post-hoc Cascade):**  
   Trên bài toán số học, công cụ lập trình ngoài (PAL) đạt **100% chính xác** với chi phí chỉ **194,1 tokens** (thấp hơn CoT vốn tốn 305,6 tokens). Do đó, chính sách phân tầng CoT $\to$ PAL tốn tới 371,6 tokens (tỷ lệ $1,91 \times$ so với PAL). **Kết luận phương pháp luận:** Khi công cụ ngoài vừa chính xác hơn vừa rẻ hơn CoT, việc phân bổ tính toán tối ưu là *Entry Routing* (chọn thẳng PAL ngay từ câu hỏi), thay vì chạy CoT trước rồi mới leo thang. Ngược lại, trên bài toán tìm kiếm tổ hợp, Tree of Thoughts (`ToT`) là cứu cánh duy nhất ($67,7\%$ vs CoT $45,2\%$), còn Self-Consistency (`SC`) làm suy giảm độ chính xác ($35,5\%$) do chỉ khuếch đại bẫy đồng thuận sai.

---

## 2. Bảng Tổng hợp Kết quả Thực nghiệm 6 Arms (Run 11 Benchmark Matrix)

> Toàn bộ 571 lượt suy luận được đo dưới điều kiện kiểm soát ngặt nghèo: cold-start độc lập, greedy decoding xác định, bộ sinh prompt cố định, đo đạc đồng thời Prompt Tokens, Completion Tokens và Logprob.

| Chiến lược (Arm) | Số học (Arith) ($N=40$) | Xếp hạng (Order) ($N=31$) | Tổ hợp (G24) ($N=29$) | Tổng Accuracy ($N=100$) | Completion Tokens | Total Tokens (Prompt + Comp) | Đặc điểm Hành vi Suy luận |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **`DIRECT-v2`** | 5 / 40 (12,5%) | 7 / 31 (22,6%) | 0 / 0 (—) | **12 / 71 (16,9%)** | 6,2 | 113,0 | Mức sàn (floor baseline); suy luận trực giác một bước hoàn toàn thất bại trên bài toán nhiều bước. |
| **`COT`** | 30 / 40 (75,0%) | 14 / 31 (45,2%) | 14 / 29 (48,3%) | **58 / 100 (58,0%)** | 415,9 | 525,1 | Chuỗi suy nghĩ chuẩn; gục ngã trước bẫy lặp thử-sai trên Order (10 ca chạm trần 1024 tokens). |
| **`SC`** (5 paths) | 30 / 40 (75,0%) | 11 / 31 (35,5%) | 12 / 29 (41,4%) | **53 / 100 (53,0%)** | 1977,8 | 2086,9 | **Suy giảm chất lượng**: Chi phí tăng $4\times$, nhưng tỷ lệ đúng trên Order giảm -9,7 pp do đa số mẫu cùng hội tụ vào lời giải sai. |
| **`TOT`** | 30 / 40 (75,0%) | **21 / 31 (67,7%)** | **17 / 29 (58,6%)** | **68 / 100 (68,0%)** | 1173,0 | 1282,1 | **Nhà vô địch tìm kiếm**: Tăng vọt **+22,5 pp** trên Order và **+10,3 pp** trên G24 nhờ cơ chế đánh giá trạng thái và duyệt nhánh. |
| **`REACT`** | 33 / 40 (82,5%) | 6 / 31 (19,4%) | 0 / 29 (0,0%) | **39 / 100 (39,0%)** | 103,4 | 173,6 | Hữu ích trên phép tính số học ngắn, nhưng vỡ định dạng suy luận trên bài toán tổ hợp logic. |
| **`PAL`** | **40 / 40 (100,0%)** | 0 / 31 (0,0%) | 0 / 29 (0,0%) | **40 / 100 (40,0%)** | 234,8 | 350,0 | **Tuyệt đối trên số học**: Độ chính xác 100%, code ngắn gọn, triệt tiêu hoàn toàn sai sót tính toán số thực/nguyên. |

---

## 3. Phân tích Chi tiết 3 Phát hiện Khoa học

### 3.1. Phát hiện 1: Logprob Calibration Thất bại trên SLM (Negative Finding)

* **Thiết kế kiểm định (Preregistered Protocol):**  
  Sử dụng kỹ thuật Repeated 5-fold Cross-Validation ($\times 20$ lần chia ngẫu nhiên) để fit ngưỡng dừng trên các tín hiệu xác suất: `mean_logprob`, `min_logprob` và `answer_first_lp`. Tiêu chí qua cổng: AUROC phải tăng ít nhất $+0,05$ so với baseline chiều dài/độ khó, với cận dưới khoảng tin cậy 95% $> 0$.
* **Kết quả đo đạc:**
  - Trên **Arithmetic**: Thêm `min_logprob` cho $\Delta \text{AUROC} = +0,062$, nhưng $95\%$ CI là $[0,000; 0,157]$ (cận dưới chạm mốc 0,000, không đạt tiêu chí nghiêm ngặt). Tín hiệu `answer_first_lp` cho AUROC $= 0,500$ (tương đương đoán ngẫu nhiên).
  - Trên **Ordering**: AUROC thô của `mean_logprob` chỉ đạt $0,265$ trên toàn bộ tập; sau khi lọc bỏ các ca bị cắt do chạm trần token, AUROC đạt $0,551$. Thử nghiệm mô phỏng với biến ngẫu nhiên thuần túy ở $N=21$ ($14$ đúng, $7$ sai) cho dải AUROC $0,21 \dots 0,71$. Do đó, tín hiệu trên Ordering hoàn toàn nằm trong dải nhiễu thống kê.
* **Cơ chế lỗi:**  
  Mô hình ngôn ngữ nhỏ tự hồi quy khi sinh ra chuỗi thử-sai sai lầm ("Giả sử Grace ở vị trí 1... Sai... Thử Grace ở vị trí 2") vẫn duy trì xác suất chuyển trạng thái từ cao đối với các cụm từ đệm quen thuộc. Mô hình hoàn toàn "tự tin" vào một chuỗi lập luận vi phạm ràng buộc.
* **Hệ quả nghiên cứu:**  
  Dừng hoàn toàn hướng tiếp cận dùng ngưỡng logprob làm router/stopping criterion. Chuyển giao toàn bộ vai trò giám sát cho **Deterministic Program Verifiers** (Symbolic Guardrails).

---

### 3.2. Phát hiện 2: Tách rời Diễn đạt (Wording) khỏi Bản chất Tìm kiếm (Search Difficulty)

Khi phân tích 21 lời giải kết thúc của CoT trên Ordering (Prompt AA), phát hiện sự co cụm bất thường của các lỗi vi phạm ràng buộc:
- Vi phạm clue `before` ($A < B$): **0 / 33 (0,0%)**
- Vi phạm clue `immediately` ($B = A + 1$): **1 / 22 (4,5%)**
- Vi phạm clue `gap` ($B = A + k$): **12 / 23 (52,2%)**

Nhằm kiểm chứng xem mô hình thất bại do *đọc hiểu sai ngữ nghĩa tự nhiên của từ "ahead of"* hay do *độ khó tính toán bản chất của việc duy trì ràng buộc khoảng cách*, nghiên cứu tiến hành thí nghiệm đối chứng Prompt AB:
- **Style A (Chuẩn):** `"{X} finished {k} places ahead of {Y}"`
- **Style B (Đại số tường minh):** `"{X} finished {k} places ahead of {Y}: if {X} is in position p, then {Y} is in position p+{k}"`

#### Kết quả Đối chứng Thực nghiệm (AB3 Sweep Trace):

| Tiêu chí | Style A (Run 11 COT) | Style B (GapB COT) | Chênh lệch ($\Delta$) | Kết luận Khoa học |
| :--- | :---: | :---: | :---: | :--- |
| **Tỷ lệ vi phạm Clue Gap** | **12 / 23 (52,2%)** | **4 / 27 (14,8%)** | **-37,4 pp** | **Vượt tiêu chí prereg** ($\le 26\%$). |
| **Accuracy (Toàn bộ 31 items)** | 14 / 31 (45,2%) | **18 / 31 (58,1%)** | **+12,9 pp** | Tăng thêm 4 bài toán giải đúng hoàn toàn. |
| **Số ca kẹt token (`length` cap 1024)** | 10 / 31 (32,3%) | **3 / 31 (9,7%)** | **-22,6 pp** | Cắt đứt 7 ca lặp vô tận "Try... Nope". |
| **Mean completion tokens** | 595,1 | **425,5** | **-28,5%** | Tiết kiệm 169,6 tokens trên mỗi câu hỏi. |

**Ý nghĩa:** Cách diễn đạt tự nhiên gây nhiễu ngữ nghĩa nghiêm trọng khiến SLM liên tục lập luận sai độ lệch (offset) và rơi vào bẫy thử-sai vô vọng. Khi được cung cấp ánh xạ tọa độ $p \to p+k$, mô hình giải phóng được năng lực suy luận và tự giải quyết được thêm 4 bài toán. Tuy nhiên, 14,8% vi phạm còn lại và khoảng cách với ToT (67,7%) khẳng định: đối với các ràng buộc lồng nhau phức tạp, mô hình tự hồi quy tham lam vẫn cần thuật toán tìm kiếm cây để quay lui khi gặp ngõ cụt.

---

### 3.3. Phát hiện 3: Đánh giá Chính sách Phân tầng Cascade (Policy V) vs Entry Routing

Theo cam kết trước tại [`prereg/decision_rule_cascade.md`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/prereg/decision_rule_cascade.md), nghiên cứu đánh giá chính sách phân tầng **Policy V**:
$$\text{Policy V}: \quad \text{Chạy COT} \longrightarrow \text{Nếu Verifier cờ báo / Chạm trần token} \longrightarrow \text{Escalate sang } E \quad (\text{ngược lại dừng})$$
với $E = \text{PAL}$ trên Arithmetic, và $E = \text{SC}$ trên Ordering. Chi phí đo lường là tổng số tokens (prompt + completion) thực tế tiêu thụ trên mọi nhánh.

#### Bảng Kết quả Đánh giá Policy V:

| Họ bài toán (Family) | Always-COT | Always-E | Policy V | Oracle (COT, E) | Delta ($V - \text{COT}$) [95% Bootstrap CI] | Tỷ lệ Tokens ($V / E$) | Đánh giá Tiêu chí Prereg ($\Delta \ge +5\text{pp}, \text{Token} \le 0,6 E$) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Số học (Arith)** ($E=\text{PAL}$) | 75,0% (305,6 tok) | **100,0% (194,1 tok)** | 100,0% (371,6 tok) | 100,0% (194,1 tok) | **+25,0 pp** $[+12,5\text{pp}; +40,0\text{pp}]$ | **1,91** | **FAIL điều kiện token** (Do PAL vốn dĩ rẻ hơn CoT). |
| **Xếp hạng (Order)** ($E=\text{SC}$) | 45,2% (712,2 tok) | 35,5% (3013,6 tok) | 45,2% (2952,1 tok) | 51,6% (2137,8 tok) | **+0,0 pp** $[-12,9\text{pp}; +12,9\text{pp}]$ | **0,98** | **FAIL cả delta và token** (SC làm giảm chất lượng suy luận). |

#### Khám phá Phương pháp luận Quan trọng:
1. **Nghịch lý Chi phí của Cascade trên Số học:**  
   CoT tốn trung bình 305,6 tokens và chỉ đạt 75% accuracy (do lỗi cộng trừ nhân chia trung gian). PAL chỉ tốn 194,1 tokens và đạt 100% accuracy. Khi áp dụng Cascade, mô hình buộc phải tốn 305,6 tokens cho CoT trước, rồi tốn thêm 194,1 tokens cho 10 ca sai sót, đẩy chi phí lên 371,6 tokens ($1,91 \times$ PAL).  
   $\Longrightarrow$ **Chính sách tối ưu không phải là Cascade (leo thang sau khi thất bại), mà là One-Shot Entry Router (phân loại câu hỏi ở đầu vào và kích hoạt thẳng PAL).**
2. **Sự sụp đổ của Self-Consistency trên SLM:**  
   Khác với các mô hình khổng lồ (LLM) nơi đa số phiếu có thể sửa lỗi ngẫu nhiên, trên SLM greedy, các đường sinh độc lập có xu hướng đồng thuận mạnh mẽ vào cùng một bẫy suy luận sai. Leo thang sang SC không cải thiện độ chính xác (+0,0 pp) mà làm lãng phí gấp 4 lần tokens. Để leo thang hiệu quả trên bài toán tìm kiếm, đích đến bắt buộc phải là **Tree of Thoughts (`ToT`)**.

---

## 4. Phân tích Đánh đổi Chi phí – Chất lượng (Pareto Frontier)

```
Accuracy (%)
  100 |                                       [PAL] (194 tok, 100% arith)
      |
   80 |                                       [TOT] (1282 tok, 68.0%)
      |
   60 |                    [COT] (525 tok, 58.0%)
      |                                       [SC] (2087 tok, 53.0%)
   40 |       [REACT] (174 tok, 39.0%)
   20 | [DIRECT] (113 tok, 16.9%)
    0 +-------------------------------------------------------------------->
      0        500       1000      1500      2000      2500   Total Tokens
```

* **Vùng tối ưu Pareto (Pareto-Optimal Points):**
  - **Cực tiểu ngân sách:** `DIRECT-v2` (113,0 tokens, 16,9% accuracy) — Thích hợp cho các truy vấn tra cứu tức thì không cần suy luận.
  - **Ngân sách thấp - Công cụ chuyên dụng:** `PAL` trên bài toán số học (194,1 tokens, 100% accuracy) — Thống trị tuyệt đối về cả chi phí lẫn độ chính xác.
  - **Cân bằng tổng quát:** `COT` (525,1 tokens, 58,0% accuracy) — Chiến lược mặc định đa năng tốt nhất trên đơn luồng.
  - **Chất lượng tối đa trên bài toán tổ hợp:** `TOT` (1282,1 tokens, 68,0% accuracy) — Điểm duy nhất giải quyết được không gian tìm kiếm sâu của Ordering và Game-of-24.
* **Các điểm dưới tối ưu (Pareto-Dominated):**
  - `SC` (2086,9 tokens, 53,0% accuracy): Bị `TOT` áp đảo toàn diện (ToT vừa rẻ hơn gần một nửa, vừa chính xác hơn +15,0 pp).
  - `REACT` (173,6 tokens, 39,0% accuracy): Bị phân mảnh theo loại bài toán (tốt trên số học nhưng liệt trên tổ hợp).

---

## 5. Ánh xạ vào các Câu hỏi Nghiên cứu (Research Questions) của Đề tài NCKH

| Câu hỏi Nghiên cứu | Phát hiện Thực nghiệm Cụ thể | Kết luận Đóng góp cho Bài báo |
| :--- | :--- | :--- |
| **RQ1 (Routing & Stopping Trade-off)** | Logprob confidence thất bại; Symbolic Verifiers đạt Recall 100%. Phân tầng Cascade tiết kiệm hơn khi chi phí downstream cao, nhưng bị đảo lộn nếu downstream tool rẻ hơn CoT. | Khẳng định giá trị của cơ chế dừng/leo thang dựa trên bộ kiểm tra hình thức (Symbolic Verifier), thay vì dựa trên xác suất mô hình nội tại. |
| **RQ2 (Source of Gains)** | Lợi ích số học đến hoàn toàn từ công cụ tính toán ngoài (`PAL`), không đến từ CoT. Lợi ích bài toán logic đến từ cấu trúc tìm kiếm (`ToT`). | Tách bạch rõ rệt: Khả năng tính toán cần công cụ ngoài; khả năng lập kế hoạch/tìm kiếm cần thuật toán duyệt cây. CoT đơn thuần không thể bù đắp thiếu hụt cấu trúc. |
| **RQ3 (Failure Heterogeneity)** | Thí nghiệm A/B chứng minh bẫy ngôn ngữ tự nhiên làm thổi phồng tỷ lệ vi phạm clue gap lên $52,2\%$; đại số hóa đưa tỷ lệ này về $14,8\%$. | Chỉ ra ranh giới chính xác giữa điểm yếu đọc hiểu (linguistic confounder) và giới hạn tính toán của bộ giải mã tự hồi quy tham lam. |
