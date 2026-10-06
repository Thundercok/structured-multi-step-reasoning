# Báo cáo Thực nghiệm & Khảo sát Thăm dò (Empirical Findings Report)

**Đề tài NCKH:** *Điều phối chiến lược suy luận và quyết định dừng theo ngân sách cho mô hình ngôn ngữ nhỏ*  
**Mô hình khảo sát:** `mlx-community/Qwen3-8B-4bit` (snapshot `545dc4251c05440727734bcd94334791f6ab0192`, `enable_thinking=false`)  
**Tập dữ liệu:** `data/gen02_tune.json` ($N=100$, development pool đã lộ) & `data/gen02_tune_gapB.json` ($N=31$)  
**Trạng thái bằng chứng:** Khảo sát thăm dò trên tập development (Exploratory on exposed tune pool); các quy tắc và verifier được phát triển sau khi quan sát mẫu lỗi (in-sample). Cần xác minh độc lập trên tập confirmatory (`gen02_v2`) trước khi mở held-out test.  
**Ngày cập nhật:** 2026-10-06  
**Artifacts Nguồn:**
- Trace 6 arms: `audit/run11_sweep_trace.jsonl` ($N=571$)
- Trace đối chứng Gap B: `audit/gapB_sweep_trace.jsonl` ($N=31$)
- Script báo cáo: `scripts/report_results.py`
- Bảng và biểu đồ audit: `audit/AD_report_results.txt`, `audit/AD_oracle_rule.txt`, `audit/AD_posthoc_tot.txt`, `audit/AD_failure_modes.txt`, `audit/AD_sc_consensus.txt`, `audit/AD_pareto.png`

---

## 1. Tóm tắt Đóng góp & Giới hạn Khoa học (Executive Summary)

Nghiên cứu khảo sát bài toán phân bổ tính toán và điều phối chiến lược suy luận cho mô hình ngôn ngữ nhỏ (`Qwen3-8B-4bit`) trên 3 họ bài toán cấu trúc: Số học (*Arithmetic*, $N=40$), Xếp hạng logic (*Ordering*, $N=31$), và Tổ hợp số học (*Game-of-24*, $N=29$).

Dữ liệu thực nghiệm 571 lượt sinh từ Run 11 và 31 lượt sinh đối chứng Gap B ghi nhận các phát hiện cốt lõi sau:

1. **Tín hiệu Tự tin Logprob không đạt Cổng Đăng ký trước (Preregistered Gate Fail):**  
   Thử nghiệm lặp 5-fold CV $\times 20$ trên `mean_logprob`, `min_logprob` và `answer_first_lp` ghi nhận cận dưới của khoảng tin cậy 95% $\le 0$ tại $n_{\text{neg}} = 10$ (Arith) và $n_{\text{neg}} = 7$ (Order). Tín hiệu logprob **không vượt qua cổng preregistration**, do đó nghiên cứu dừng việc fit ngưỡng logprob làm router.
2. **Hiệu ứng Diễn đạt Clue Khoảng cách trên Ordering (Consistent with Wording Effect):**  
   Viết lại clue khoảng cách theo dạng đại số tường minh vị trí ($p \to p+k$) làm **tỷ lệ vi phạm clue gap giảm từ 52,2% xuống 14,8%** (nhóm trích xuất được) và **giảm 7 ca kẹt trần độ dài** (10 ca $\to$ 3 ca). Tuy nhiên, trên 19 bài toán hoàn tất ở cả 2 cách viết, số câu đúng là 13/19 (Style A) và 11/19 (Style B) ($n=31$, một lượt chạy đơn lẻ, không có CI). Do đó, dữ liệu **chưa có bằng chứng về sự thay đổi độ chính xác nội tại**; hiệu ứng quan sát được chủ yếu là giải phóng mô hình khỏi bẫy lặp chạm trần token.
3. **Đánh giá Cổng Oracle 6 Arms: NO-GO trên toàn bộ các họ bài toán:**  
   Theo [`prereg/decision_rule_oracle.md`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/prereg/decision_rule_oracle.md), cổng yêu cầu khoảng trống Oracle (gap) $\ge 10$ pp và cận dưới 95% CI $\ge 5$ pp. Kết quả kiểm định phân cụm bootstrap cho thấy: Arithmetic đạt gap $= 0,0$ pp (PAL đạt 100%, không còn dư địa); Ordering đạt gap $= +12,9$ pp nhưng cận dưới CI chỉ đạt $+3,2$ pp ($< 5$ pp); Game-of-24 đạt gap $= +6,9$ pp ($< 10$ pp). Cả 3 họ đều nhận kết luận **NO-GO**, nghĩa là không đủ khoảng trống bổ sung giữa các arm để fit ngưỡng router toàn cục.
4. **Phân hóa Chiến lược theo Họ Bài toán (Home Arms):**  
   - **Số học:** PAL đạt 40/40 (100,0%) với 194,1 tokens (rẻ hơn CoT 305,6 tokens). Việc chạy CoT rồi mới leo thang sang PAL (Policy V) tốn 371,6 tokens ($1,91\times$ so với PAL), cho thấy phân tầng sau (cascade) là lãng phí tài nguyên trên bài toán có công cụ ngoài rẻ hơn.
   - **Xếp hạng & Tổ hợp:** Best-of-3 with judge (`TOT`) dẫn đầu (Order 67,7%, G24 58,6%) ở mức chi phí $\approx 2,4\times$ CoT. Ngược lại, Self-Consistency (`SC`) suy giảm độ chính xác (Order 35,5%, G24 41,4%); phân tích vote share (AD5) xác nhận 30,0% các ca sai trên Order có ít nhất 3/5 mẫu đồng thuận trên cùng một đáp án sai.

---

## 2. Bảng Tổng hợp Kết quả Thực nghiệm 6 Arms (AD1)

> Dữ liệu trích xuất từ script [`scripts/report_results.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/scripts/report_results.py) đọc từ `audit/run11_sweep_trace.jsonl` (lưu tại `audit/AD_report_results.txt`).

| Family | Arm | n | Accuracy (corr/n) | Mean Prompt Tok | Mean Comp Tok | Mean Total Tok | %Length |
| :--- | :--- | ---: | :---: | ---: | ---: | ---: | ---: |
| **arith** | DIRECT-v2 | 40 | 12,5% ( 5/40) | 110,6 | 6,2 | 116,8 | 2,5% |
| arith | COT | 40 | 75,0% (30/40) | 125,6 | 180,0 | 305,6 | 0,0% |
| arith | SC | 40 | 75,0% (30/40) | 125,6 | 896,6 | 1022,2 | 0,0% |
| arith | TOT (best-of-3 + judge) | 40 | 75,0% (30/40) | 125,6 | 563,0 | 688,6 | 0,0% |
| arith | REACT | 40 | 82,5% (33/40) | 86,6 | 102,1 | 188,7 | 0,0% |
| arith | PAL | 40 | **100,0% (40/40)** | 131,6 | 62,5 | **194,1** | 0,0% |
| **order** | DIRECT-v2 | 31 | 22,6% ( 7/31) | 102,1 | 6,1 | 108,1 | 0,0% |
| order | COT | 31 | 45,2% (14/31) | 117,1 | 595,1 | 712,2 | 32,3% |
| order | SC | 31 | 35,5% (11/31) | 117,1 | 2896,5 | 3013,6 | 48,4% |
| order | TOT (best-of-3 + judge) | 31 | **67,7% (21/31)** | 117,1 | 1776,9 | **1894,0** | 0,0% |
| order | REACT | 31 | 19,4% ( 6/31) | 78,1 | 56,3 | 134,3 | 0,0% |
| order | PAL | 31 | 0,0% ( 0/31) | 123,1 | 304,4 | 427,5 | 3,2% |
| **g24** | COT | 29 | 48,3% (14/29) | 78,0 | 549,8 | 627,8 | 44,8% |
| g24 | SC | 29 | 41,4% (12/29) | 78,0 | 2487,0 | 2565,0 | 55,2% |
| g24 | TOT (best-of-3 + judge) | 29 | **58,6% (17/29)** | 78,0 | 1368,8 | **1446,8** | 0,0% |
| g24 | REACT | 29 | 0,0% ( 0/29) | 39,0 | 155,7 | 194,7 | 0,0% |
| g24 | PAL | 29 | 0,0% ( 0/29) | 84,0 | 398,1 | 482,1 | 27,6% |

---

## 3. Đánh giá Cổng Preregistered Decision Rule Oracle (AD2)

> Quy tắc: Khoảng trống Oracle $\text{gap} = \text{Oracle Acc} - \text{Best-Single Acc} \ge 10$ pp và Cận dưới 95% Cluster-Bootstrap CI $\ge 5$ pp. Lưu tại `audit/AD_oracle_rule.txt`.

| Family | Best-Single Arm (Acc, Tok) | 6-Arm Oracle (Acc, Tok) | Gap (pp) | 95% Cluster-Bootstrap CI | Prereg Gate Decision |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **arith** | PAL (100,0%, 194,1 tok) | 100,0% (40/40), 169,2 tok | +0,0 pp | [+0,0 pp; +0,0 pp] | **NO-GO** |
| **order** | TOT (67,7%, 1894,0 tok) | 80,6% (25/31), 645,9 tok | +12,9 pp | [+3,2 pp; +25,8 pp] | **NO-GO** |
| **g24** | TOT (58,6%, 1446,8 tok) | 65,5% (19/29), 533,6 tok | +6,9 pp | [+0,0 pp; +17,2 pp] | **NO-GO** |

**Diễn giải khoa học:** Cả 3 họ bài toán đều không thỏa mãn tiêu chí mở fit router. Arithmetic không có khoảng trống (PAL đạt trần 100%). Ordering có gap 12,9 pp nhưng độ bất định thống kê cao (cận dưới CI rơi xuống +3,2 pp $< 5$ pp). Game-of-24 có gap chỉ 6,9 pp.

---

## 4. Chính sách Leo thang Hậu nghiệm V' (Post-Hoc Escalation to TOT) (AD3)

> Gắn nhãn **Post-Hoc**: Nhánh leo thang $E = \text{TOT}$ được lựa chọn sau khi đã quan sát kết quả vượt trội của TOT trong Run 11.  
> Cơ chế: Chạy COT $\to$ Nếu Verifier cờ báo vi phạm hoặc kết thúc bằng trần độ dài (`length`) $\to$ Leo thang sang TOT. Lưu tại `audit/AD_posthoc_tot.txt`.

| Family | Always-COT | Always-TOT | Oracle(COT,TOT) | Policy V' (post-hoc E=TOT) | Delta (V' - COT) [95% CI] | Token Ratio (V' / TOT) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **order** | 45,2% (712,2 tok) | 67,7% (1894,0 tok) | 74,2% (1025,2 tok) | **71,0% (2088,1 tok, esc: 20/31)** | **+25,8 pp** [+6,5 pp; +45,2 pp] | 1,10 |
| **g24** | 48,3% (627,8 tok) | 58,6% (1446,8 tok) | 62,1% (780,6 tok) | **62,1% (1649,8 tok, esc: 15/29)** | **+13,8 pp** [+3,4 pp; +27,6 pp] | 1,14 |

*Lưu ý về Verifier Recall:* Bộ `order_verifier` và `check24` được xây dựng và tinh chỉnh trực tiếp trên các lỗi quan sát được của tập `gen02_tune` (in-sample). Tỷ lệ recall cao và delta trên cần được kiểm chứng lại (confirmatory replication) trên tập split chưa thấy (`gen02_v2`).

---

## 5. Chẩn đoán Cơ chế Thất bại của PAL và REACT (AD4)

> Khảo sát nguyên nhân các arm đạt 0% accuracy trên Ordering và Game-of-24. Lưu tại `audit/AD_failure_modes.txt`.

| Arm | Family | Total | Failure Mode | Count | Share (%) | Nguyên nhân gốc rễ (Root Cause) |
| :--- | :--- | ---: | :--- | ---: | ---: | :--- |
| **PAL** | order | 31 | exception (sandbox import block) | 30 | 96,8% | Prompt PAL yêu cầu gán số vào biến `result` và cấm import. Khi giải xếp hạng, mô hình cố tình viết `from itertools import permutations` $\to$ Sandbox chặn import fail-closed. |
| **PAL** | order | 31 | wrong value (syntax token parsed) | 1 | 3,2% | Lời giải sinh mã chứa comment hoặc từ khóa cú pháp không trả về tên hợp lệ. |
| **PAL** | g24 | 29 | exception (sandbox import block) | 21 | 72,4% | Mô hình cố import `itertools.product` để duyệt biểu thức $\to$ Bị sandbox chặn. |
| **PAL** | g24 | 29 | wrong value / invalid syntax | 8 | 27,6% | Mô hình trả về giá trị scalar 24 hoặc cú pháp biểu thức sai quy cách. |
| **REACT** | g24 | 29 | wrong value / invalid format | 22 | 75,9% | ReAct chỉ có công cụ tính toán số học (`calculate[...]`), không có công cụ tìm kiếm cây. Vòng lặp ReAct sinh biểu thức tính thử nhưng không ghép đủ 4 số. |
| **REACT** | g24 | 29 | wrong type (scalar 24) | 7 | 24,1% | G24 yêu cầu chuỗi biểu thức toán học (VD: `((12*6)/1)/3`), nhưng ReAct trả về kết quả scalar là số `24`. |

---

## 6. Phân tích Phân phối Đồng thuận Phiếu Self-Consistency (AD5)

> Kiểm tra giả định "đa số mẫu cùng hội tụ vào đáp án sai". Lưu tại `audit/AD_sc_consensus.txt`.  
> *Lưu ý kỹ thuật:* Trường `sc_vote_share` ghi trong trace cũ bị chia thừa cho 5; cột dưới đây khôi phục lại tỷ lệ phiếu thực tế của nhánh chiến thắng ($k / 5$).

| Family | Phân nhóm | n | Mean Winner Vote Share | Median Winner Share | Số ca có Winner Share $\ge 0,6$ ($\ge 3/5$ phiếu) |
| :--- | :--- | ---: | :---: | :---: | :---: |
| **order** | Correct | 11 | 0,782 | 0,800 | 10 / 11 (90,9%) |
| order | **Wrong** | 20 | **0,440** | **0,400** | **6 / 20 (30,0%)** |
| order | Total | 31 | 0,561 | 0,600 | 16 / 31 (51,6%) |
| **g24** | Correct | 12 | 0,600 | 0,600 | 8 / 12 (66,7%) |
| g24 | **Wrong** | 17 | **0,282** | **0,200** | **1 / 17 ( 5,9%)** |
| g24 | Total | 29 | 0,414 | 0,400 | 9 / 29 (31,0%) |

**Ý nghĩa:** Trên Ordering, trong **30,0%** trường hợp sai, có ít nhất 3 trên 5 đường sinh ngẫu nhiên cùng đồng thuận vào một đáp án sai (consistent with bias reinforcement). Ngược lại, trên Game-of-24, các mẫu sai phân tán mạnh (median winner share chỉ 0,20 - mỗi mẫu một đáp án sai khác nhau).

---

## 7. Đồ thị Đánh đổi Pareto theo Từng Họ Bài toán (AD6)

Biểu đồ Pareto độc lập cho từng họ bài toán được xuất ra file đồ họa chất lượng cao tại:  
[`audit/AD_pareto.png`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/audit/AD_pareto.png)

```
[Biểu đồ Pareto 3 Panel: Arithmetic | Ordering | Game-of-24]
- Panel 1 (Arith): PAL thống trị tuyệt đối (100%, 194 tok), triệt tiêu nhu cầu CoT (306 tok) hay Policy V (372 tok).
- Panel 2 (Order): COT (45%, 712 tok) -> TOT (68%, 1894 tok) -> Policy V' (71%, 2088 tok) -> 6-Arm Oracle (81%, 646 tok).
- Panel 3 (G24): COT (48%, 628 tok) -> TOT (59%, 1447 tok) -> Policy V' (62%, 1650 tok) -> 6-Arm Oracle (66%, 534 tok).
```

---

## 8. Trả lời Câu hỏi Cốt lõi của Prompt AD

**Câu hỏi:** *Tại sao một bộ phân loại họ bài toán (Family Classifier) đã đạt gần tới độ chính xác Oracle trên tập dữ liệu này, và router thực sự có việc để làm ở đâu?*

### 1. Tại sao Family Classifier đạt gần bằng Oracle?
Trên tập dữ liệu `gen02_tune`, mỗi họ bài toán có một chiến lược chuyên biệt vượt trội (Home Arm):
- Arithmetic: $\text{PAL} = 40/40$ ($100,0\%$).
- Ordering: $\text{TOT} = 21/31$ ($67,7\%$).
- Game-of-24: $\text{TOT} = 17/29$ ($58,6\%$).

Một bộ phân loại họ câu hỏi đơn giản (dựa vào từ khóa hoặc embedding):
$$\text{arith} \to \text{PAL}, \quad \text{order} \to \text{TOT}, \quad \text{g24} \to \text{TOT}$$
sẽ đạt độ chính xác:
$$\text{Accuracy} = \frac{40 + 21 + 17}{100} = \mathbf{78,0\%}$$
Trong khi đó, giới hạn lý thuyết tối đa của bộ 6-Arm Oracle trên toàn bộ 100 câu hỏi chỉ là:
$$\text{Oracle} = \frac{40 + 25 + 19}{100} = \mathbf{84,0\%}$$
Khoảng cách giữa phân loại họ câu hỏi tĩnh ($78,0\%$) và Oracle hoàn hảo ($84,0\%$) chỉ là **6,0 điểm phần trăm** (vỏn vẹn 6 câu hỏi). Do đó, tuyên bố "Entry routing vượt trội cascade" trên dữ liệu này thực chất phần lớn là hệ quả tầm thường của việc nhận diện đúng định dạng bài toán (bài toán toán học dùng Python, bài toán suy diễn dùng tìm kiếm).

### 2. Router thực sự có việc để làm ở đâu?
Router không có giá trị phân biệt giữa PAL và ToT (vì đó là bài toán nhận diện dạng câu hỏi ở đầu vào). Router **chỉ thực sự có ý nghĩa trong 2 bối cảnh**:
1. **Đánh đổi Chi phí – Chất lượng Nội bộ (Intra-family trade-offs trong Order và G24):**  
   ToT đạt $67,7\%$ trên Order nhưng tốn $1894$ tokens ($2,7\times$ CoT). Một router thông minh có nhiệm vụ phân biệt: câu Order nào có đồ thị ràng buộc đơn giản, tuyến tính để giải bằng CoT (712 tokens), và câu nào có ràng buộc lồng nhau/chu trình phức tạp để kích hoạt ToT.
2. **Kiểm tra Rationale và Dừng / Leo thang Có điều kiện (Verifier-guided stopping):**  
   Khởi chạy CoT giá rẻ; sử dụng `order_verifier` hoặc `check24` để phát hiện lỗi lập luận hoặc vòng lặp chạm trần. Nếu vi phạm, leo thang sang ToT. Chính sách này đạt $71,0\%$ trên Order và $62,1\%$ trên G24, giữ được chất lượng của ToT mà vẫn cung cấp cơ chế kiểm định hình thức cho từng lời giải.
