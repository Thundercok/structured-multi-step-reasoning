# Lượt đo cuối trên dev MATH (câu 301–500), 2026-11-05

Lượt đo kiểm định giả thuyết được tiền đăng ký (pre-registered) trong `docs/research_plan.md` ngày 2026-11-04, chạy trên 200 câu chưa từng xem của dev MATH (câu 301 đến 500). Toàn bộ mã băm (`frozen_sha256.txt` và `labels_sha256.txt`) được chốt và kiểm tra toàn vẹn trước khi sinh bất kỳ chương trình nào.

## Giả thuyết tiền đăng ký

*Chương trình độc lập bắt lỗi lập luận mà chương trình dịch chép lại, còn chương trình dịch bắt lỗi thực thi ít nhất bằng chương trình độc lập.*

## Kết quả chính (Tập nhãn thống nhất `primary`)

- **Độ tin cậy nhãn:** Hai lượt gán nhãn độc lập (agent và `agy`, gán mù trước khi sinh chương trình) đạt độ đồng thuận rất cao: Cohen's $\kappa = 0,947$ (39 câu gán nhãn, chỉ 1 câu lệch bị loại vào nhóm `excluded`).
- **Tổng quan:** 141 câu đúng, 59 câu sai (trong đó: 24 lỗi lập luận `reasoning`, 13 lỗi thực thi `execution`, 21 câu bị cắt `truncated`, 1 câu `excluded`).

### Bảng đối chiếu 5 điều kiện tiên quyết

| Điều kiện | Tiêu chí đăng ký | Thực tế đo được | Kết luận |
| --- | --- | --- | :---: |
| **1. Cỡ mẫu reasoning** | $\ge 20$ câu | 24 câu | **ĐẠT** |
| **2. Bắt lỗi reasoning** | Độc lập > Dịch, McNemar $p < 0,05$ | Độc lập: 10/24 (41,7%), Dịch: 2/24 (8,3%), lệch: 9 vs 1, $p = 0,0215$ | **ĐẠT** |
| **3. Khoảng cách bắt vs báo nhầm** | Chênh bắt reasoning > Chênh báo nhầm trên câu đúng | $0,334 > 0,057$ (Báo nhầm: Độc lập 10/141 [7,1%], Dịch 2/141 [1,4%]) | **ĐẠT** |
| **4. Bắt lỗi execution** | Dịch $\ge$ Độc lập | Dịch: 9/13 (69,2%), Độc lập: 8/13 (61,5%), lệch: 2 vs 1, $p = 1,0$ | **ĐẠT** |
| **5. Cổng phát hiện kết hợp (hoặc 1 trong 2)** | Bắt $\ge 50\%$, báo nhầm $\le 20\%$ | Bắt: 32/59 (54,2%, KTC 95%: 41,7–66,3%), Báo nhầm: 12/141 (8,5%, KTC 95%: 4,9–14,3%) | **ĐẠT** |

**Toàn bộ 5 điều kiện tiên quyết đều THỎA MÃN (`holds: true`).**

## Chi tiết các nhóm lỗi

| Nhóm dữ liệu | Chương trình độc lập (PAL) | KTC Wilson 95% | Chương trình dịch | KTC Wilson 95% | Lệch (Độc lập / Dịch) | McNemar $p$ |
| --- | ---: | --- | ---: | --- | :---: | ---: |
| **Lỗi lập luận (`reasoning`, $N=24$)** | 10/24 (41,7%) | 24,5–61,2% | 2/24 (8,3%) | 2,3–25,8% | 9 / 1 | **0,0215** |
| **Lỗi thực thi (`execution`, $N=13$)** | 8/13 (61,5%) | 35,5–82,3% | 9/13 (69,2%) | 42,4–87,3% | 1 / 2 | 1,0000 |
| **Báo nhầm trên câu đúng ($N=141$)** | 10/141 (7,1%) | 3,9–12,6% | 2/141 (1,4%) | 0,4–5,0% | 10 / 2 | 0,0386 |

## Phân tích độ nhạy, không dùng để kết luận

- **Chỉ nhãn A, hoặc chỉ nhãn B:** cả hai đều vẫn đạt 5 điều kiện, p = 0,0215.
- **Chỉ các câu cả hai chương trình đều ra số (125 câu):** reasoning chỉ còn 12 câu, nên điều kiện 1 không đạt (`holds: false`). Độc lập bắt 10/12, dịch bắt 1/12, p = 0,0039. Lát cắt này loại câu theo kết quả chạy của chính hai chương trình, nên không so công bằng.

## Hạn chế cần đọc cùng kết quả

- **Điều kiện 5 được nâng bởi câu bị cắt.** Trong 32 câu bị bắt có 11 câu là lời giải bị cắt 2.048 token, không có dòng `Answer:`, nên cờ khác đáp án gần như luôn bật. Bỏ các câu này, còn khoảng 21/38 (tính bằng phép trừ, chưa chạy lại script). Khoảng tin cậy 95% của 32/59 có cận dưới 41,7%, thấp hơn ngưỡng 50%.
- **Chỉ 24 câu reasoning và 13 câu execution.** Điều kiện 4 (dịch ≥ độc lập, 9/13 so với 8/13) không phân biệt được hai bên, p = 1,0.
- **Khoảng 25% chương trình không ra số** (độc lập 52/200, dịch 50/200), nên cờ không bật ở các câu đó.
- **Nhãn:** cả hai lượt thấy đề, đáp án mẫu và lời giải, chưa có người rà. Lượt đầu của `agy` đã thấy nhãn của agent nên không độc lập; lượt dùng là lượt chạy lại trong phiên mới. Chỉ có 39 câu được gắn nhãn.
- **Một tập dev, một mô hình, chưa tinh chỉnh, chưa chạy tập niêm phong.**

## Chi phí token và thời gian thực thi

- **Độ dài trung bình:** Lời giải 734,9 token; Chương trình độc lập 398,2 token; Chương trình dịch 255,0 token.
- **Tỉ lệ không ra số:** Độc lập 52/200 (26,0%), Dịch 50/200 (25,0%).
- **Độ chính xác nếu lấy chương trình làm đáp án:**
  - Lời giải gốc: 141/200 (70,5%)
  - Chương trình dịch: 123/200 (61,5%)
  - Chương trình độc lập: 120/200 (60,0%)

## Cách đọc

Cả 5 điều kiện tiền đăng ký đều đạt trên câu mới. Đây là kết quả của một phép đo lại trên một tập dev, chưa phải xác nhận luận điểm. Điều kiện và ngưỡng do agent đề xuất; người làm nghiên cứu mới đồng ý đo, chưa quyết định giữ luận điểm. Cách chương trình dịch chép lại lỗi lập luận chưa được kiểm định trực tiếp. Hướng "viết chương trình để kiểm lại lời giải" đã có người làm (xem phần khảo sát trong `math_translate_20261104/README.md`), nên chưa thể coi là đóng góp mới.
