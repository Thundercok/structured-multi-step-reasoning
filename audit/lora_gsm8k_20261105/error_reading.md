# Vì sao adapter đúng ít hơn `base_prefill`: đọc từng câu, 2026-11-06

**Đọc sau khi đã thấy số, một người đọc (agent), chưa có người rà, nhãn không mù.** Chỉ đọc 100 câu dev đã có đầu ra. Không huấn
luyện thêm, không đo tập mới.

Đọc các câu `base_prefill` đúng mà adapter sai: 12 câu của `tuned_cf`, 9 câu của `tuned` thường, gồm 19 câu khác nhau (2 câu cả hai sai).

## Nhãn

- **Hiểu đề sai:** đọc sai một số liệu hoặc một quan hệ trong đề.
- **Kế hoạch sai:** đọc đúng đề nhưng thiếu bước, dừng sớm hoặc bỏ sót một đại lượng.
- **`Calc` sai:** kết quả ghi trong `Calc` hoặc trong lời bước sai số học.
- **`Calc` đúng, bước sau dùng sai:** kết quả đúng nhưng bước sau lấy nhầm.
- **Trích đáp án sai hoặc bị cắt.**

Ranh giới giữa hiểu đề sai và kế hoạch sai còn mơ hồ ở 2 câu (`0556de23`, `069d0428`), nên số theo hai nhãn này chỉ là tương đối.

## Từng câu

| Câu | Adapter | Đáp án mẫu → adapter | Nhãn | Trích từ đầu ra thô | `Calc` đúng hết |
| --- | --- | --- | --- | --- | --- |
| `038474b6` | cf | 15 → 13 | Kế hoạch sai: bỏ sót 2 giáo viên | `So there were 10+3 = 13 people left` | có |
| `04163f5a` | cf | 39 → 24 | Hiểu đề sai: lấy mức giảm 0,4 làm giá | `25 * $0.4 = $10` | có |
| `04222269` | cf | 2 → 10 | Kế hoạch sai: dừng trước bước chia cho 5 ngày | `600/60=10 hours` rồi trả lời 10 | có |
| `045a4b9c` | cf | 2 → 3 | Hiểu đề sai: 6 ngày thay vì 4, kèm lỗi định dạng (đơn vị) | `30 minutes/day * 6 days` | không đọc được |
| `0490d526` | cf | 1525 → 850 | `Calc` sai | `Calc: 150*5/100*10=750` (đúng là 75) | không |
| `0535a2bf` | cf | 460 → 360 | `Calc` sai, chuỗi 4 số | `Calc: 130+110+100+120=360` | không |
| `0556de23` | cả hai | 8 → 0,5 | Hiểu đề sai: chia thay vì nhân | `50/4 = 12.5 spotted brown toads` | có |
| `0557ecbe` | cf | 504 → 720 | Kế hoạch sai: gộp ngày 2 và 3, bỏ bước 30% | `900 - 20% of 900 = 900 - 180 = 720` | có |
| `05846387` | cf | 25 → 50 | Hiểu đề sai: một phần tư thành một nửa; lời và `Calc` lệch nhau | `500 x 2/4 = 250` / `Calc: 500-250=250` | có |
| `059e1768` | cf | 150 → 180 | Hiểu đề sai: nhân đôi số của thứ Bảy | `On Saturday, Tanika sold 60 x 2 = 120` | có |
| `05fb4a91` | cf | 12 → 50 | Hiểu đề sai: dùng 50 thay vì 19 người | `50 x 2 = 100 doughnuts were eaten` | có |
| `069d0428` | cf | 3 → 7,5 | Hiểu đề sai: tính 3 giờ một lần thay vì 5 ngày | `$20 x 3 = $60 per weekday` rồi `60+100` | có |
| `069d0428` | thường | 3 → 60 | Kế hoạch sai: bỏ tiền công mỗi giờ | `1200 / 20 = 60 weeks` | có |
| `04483c31` | thường | 100 → 80 | `Calc` sai, chuỗi 4 số | `Calc: 20+60+40-20=80` | không |
| `0483a43e` | thường | 3450 → 3600 | `Calc` sai, nằm trong lời bước không có `Calc` | `150+3000+3000-2700=3600` | có, nhưng lỗi nằm ngoài `Calc` |
| `04d03ed7` | thường | 88 → 20 | Hiểu đề sai: "ba lần nhiều hơn" thành chia 3; kèm lỗi định dạng (chuỗi bằng) | `20/3 = 6.666... green marbles` | có |
| `0533264e` | thường | 210 → 370 | Hiểu đề sai: "tổng $40" thành $40 mỗi quyển | `2*40 = $80` | có |
| `0556de23` | thường | 8 → 0,5 | Hiểu đề sai, như bản cf | `50/4 = 12.5` | có |
| `056e151c` | thường | 25 → không có | Bị cắt: lặp sau một `Calc` phân số, hết 1.024 token | `Calc: 20/100=1/5` rồi `So 1/5=5 means 1/5=5` lặp | không |
| `0587b07c` | thường | 310 → 160 | Kế hoạch sai: chỉ tính km cuối, không cộng | `$10 x 2^(5-1) = $10 x 16 = $160` | có |
| `05e8ecc8` | thường | 76 → 75 | `Calc` sai, gộp hai bước thành một biểu thức | `Calc: 38/32*64=75.2` (đúng là 76) | không |

## Đếm

| Loại lỗi | `tuned_cf` (12) | `tuned` thường (9) |
| --- | ---: | ---: |
| Hiểu đề sai | 7 | 3 |
| Kế hoạch sai | 3 | 2 |
| `Calc` sai | 2 | 3 |
| `Calc` đúng, bước sau dùng sai | 0 | 0 |
| Trích đáp án sai hoặc bị cắt | 0 | 1 |

`045a4b9c` tính vào hiểu đề sai. 9/12 câu của `tuned_cf` và 6/9 câu của `tuned` thường có mọi dòng `Calc` đúng số học, nên một bộ kiểm
tra chỉ xem `Calc` sẽ không bắt được chúng.

**Đối chiếu với lỗi định dạng:** trong 21 ca chỉ 3 ca có lỗi định dạng. Chỉ một ca lỗi định dạng là nguyên nhân: `Calc` phân số
`20/100=1/5` dẫn tới lặp rồi bị cắt. Hai ca còn lại (đơn vị, chuỗi bằng nhau) sai vì hiểu đề sai, lỗi định dạng chỉ đi kèm.

**Đổi cách chấm không cứu được:** không có ca nào đáp án đúng mà bị trích sai. `loose_answer` đọc đúng cả 21 ca, kể cả các ca sai định dạng.

## Dữ liệu huấn luyện có dạy kiểu lỗi này không

Số từ `error_stats.py`, lưu ở `error_stats.json`. Dòng phản thực là 3.119 dòng của `structured_gsm8k_cf_v1` không có trong bản thường.

| | Train thường | Dòng phản thực | `tuned` | `tuned_cf` | `base_prefill` |
| --- | ---: | ---: | ---: | ---: | ---: |
| Số từ mỗi bước | 13,9 | 13,8 | 11,8 | 13,0 | 16,2 |
| Bước không có `Calc` | 10,0% | 1,9% | 19,6% | 8,2% | 16,8% |
| `Calc` rỗng nghĩa (`150=150`) | 1,5% | 0,2% | 13,1% | 10,1% | 1,5% |
| `Calc` chuỗi từ 2 phép tính | 13,5% | 11,8% | 15,2% | 13,4% | 13,9% |
| Đáp án không nguyên | 0 | 0 | 1 | 2 | 0 |

- **Không thấy mẫu dạy sai trực tiếp:**
  - Mọi `Calc` chuỗi trong train đều đúng (3.070/3.070 và 1.157/1.157), lời và `Calc` gần như không lệch nhau (1/22.476 và 4/9.743), không có đáp án không nguyên.
  - Đọc 4 dòng phản thực ngẫu nhiên: đề và lời giải khớp nhau.
  - Bộ tạo dữ liệu bỏ dòng có lỗi định dạng, nên chuỗi bằng nhau, đơn vị, phân số hay so sánh không có trong train.
- **Lệch so với train:**
  - Adapter viết `Calc` rỗng nghĩa nhiều gấp khoảng 7–9 lần dữ liệu huấn luyện, nên kiểu này không học trực tiếp từ dữ liệu.
  - Bước không có `Calc` của `tuned_cf` (8,2%) thấp hơn hẳn `tuned` (19,6%). Điều này khớp với việc dòng phản thực gần như bước nào cũng có `Calc` (1,9%).
- **Lời bước ngắn hơn mô hình gốc:** dữ liệu GSM8K viết bước ngắn, thường chỉ `a*b=c` mà không nói đang tính gì, và adapter viết bước ngắn hơn `base_prefill` (11,8–13,0 so với 16,2 từ). Mô hình gốc hay mở bước bằng "Calculate the …", tức nêu rõ đại lượng trước khi tính. Đây là mối liên hệ thấy sau khi đọc, chưa kiểm định.

## Giả thuyết có thể kiểm chứng rẻ, đề xuất cho người dùng chốt

1. **Phần lớn khoảng cách là nhiễu của một seed và một checkpoint.** Kiểm chứng không cần huấn luyện: chấm `tuned` của cả hai adapter ở
   checkpoint 1.000, 1.500 và 2.000 (đã lưu) trên `valid.jsonl` (99 câu, mới chỉ dùng để tính loss), cùng `base_prefill`. Mất khoảng
   20 phút mỗi lượt, tổng khoảng 2,5 giờ. Nếu khoảng cách với `base_prefill` đổi dấu hay dao động quá 5 câu giữa các checkpoint, thì
   chưa nên giải thích bằng dữ liệu. Dùng `valid` để đọc sẽ làm nó không còn sạch, nên phải ghi rõ.
2. **Học kiểu bước ngắn của GSM8K làm mô hình bỏ bước nêu đại lượng, dẫn đến hiểu đề sai hoặc kế hoạch sai** (10 và 5 trong 21 ca). Kiểm chứng rẻ, chưa huấn luyện:
   cho adapter `tuned_cf` viết tiếp từ phần mở `<think>\nStep 1: Calculate the` trên đúng 19 câu này và trên toàn bộ dev, rồi đếm số câu
   sửa được. Nếu sửa được nhiều câu hiểu đề sai mà không làm hỏng câu đúng, mới đáng tính đến việc viết lại lời bước trong dữ liệu. Phép
   thử này đổi lời nhắc sau khi đã thấy số, nên chỉ là chỉ báo, không phải kết quả.

Đổi cách chấm không phải hướng đi: không ca nào sai vì trích đáp án.
