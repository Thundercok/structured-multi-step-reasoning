# Kế hoạch tinh chỉnh mô hình nhỏ

Cập nhật: 2026-11-02. Đây là bản đề xuất. Các ngưỡng ở mục 4 cần thầy hướng dẫn
xem và phải chốt trước khi chạy mô hình tinh chỉnh lần đầu.

## 1. Phạm vi

**Đã chốt (người dùng báo sau buổi báo cáo 2026-11-02):** "mô hình mới" được hiểu
là tinh chỉnh một mô hình nhỏ có sẵn, không làm kiến trúc mới. Chưa có văn bản xác
nhận.

**Chưa chốt:**
- Cập nhật đề cương đã nộp theo quy trình nào. Mục 4 vẫn ghi "không huấn luyện lại
  trọng số".
- Làm một mình trong 6 tháng thì cắt phần nào. Mục 3 đề xuất thu hẹp phần điều phối.

## 2. Số đo trên máy (MacBook M1, 16 GB)

Chạy LoRA 8 lớp trên dữ liệu tổng hợp, chỉ để đo tốc độ và bộ nhớ. Không nói lên
chất lượng. Log ở [`audit/lora_smoke_20261102/`](../audit/lora_smoke_20261102/).

| Mô hình | Lô | Kết quả | Tốc độ | RAM đỉnh |
| --- | ---: | --- | ---: | ---: |
| Qwen3-8B-4bit | 2 | **Lỗi Metal ở bước đầu** ("Impacting Interactivity") | | |
| Qwen3-8B-4bit | 1 | Đạt, có chia nhỏ tác vụ GPU | 14 token/giây | 5,1 GB |
| Qwen3.5-4B-MLX-4bit | 2 | Đạt, adapter tải và sinh chữ được | 10 token/giây | 7,1 GB |

Lúc đo máy đang bận với các tác vụ khác, nên hai dòng tốc độ không so được với nhau.
Muốn huấn luyện ổn định cần các biến sau, và nên để máy rảnh:

```bash
MLX_MAX_OPS_PER_BUFFER=10 MLX_MAX_MB_PER_BUFFER=512
```

**Ước tính ở 14 token/giây:** nguồn tinh chỉnh có 1.205.336 token (7.353 câu).

| Khối lượng | Thời gian trên M1 |
| --- | ---: |
| 1.000 câu | khoảng 3,3 giờ |
| 2.000 câu | khoảng 6,5 giờ |
| 1 epoch toàn bộ | khoảng 24 giờ |

## 3. Thiết kế thí nghiệm

**Mô hình:** Qwen3-8B-4bit, snapshot `545dc425…`, vì toàn bộ mốc so sánh đã đo trên
mô hình này. Qwen3.5-4B chỉ là phương án dự phòng.

**Tinh chỉnh chiến lược nào: CoT.**
- PAL không còn chỗ để cải thiện: 48/48 câu trên tập calibration, trong khi CoT đạt
  43/48 ([báo cáo, mục 10](gsm8k_rq1_rq2_full_policy_evaluation_20261031.md)).
- GSM8K có sẵn lời giải từng bước bằng ngôn ngữ tự nhiên, nhưng không có chương trình
  mẫu cho PAL.

**Dữ liệu tinh chỉnh:** GSM8K `train.jsonl` đã lưu trữ (revision `3101c7d5`, khớp mã
băm). Loại 120 câu đã dùng để phát triển, còn 7.353 câu; tách 200 câu làm tập valid.
Bỏ chú thích máy tính `<<...>>`. Không dùng tập test chính thức. Chưa lọc câu trùng
về nghĩa.

**Dữ liệu đánh giá:** cần bộ khó hơn GSM8K. Ứng viên đầu tiên là
[GSM-Plus](https://arxiv.org/abs/2402.19255).
- Nó sinh từ tập test chính thức, không trùng với dữ liệu tinh chỉnh, nhưng dùng nó
  là đã mở tập test chính thức, nên cần ghi rõ trong báo cáo.
- Chia theo câu gốc, xếp hạng bằng SHA-256 như các bộ trước: 100 nhóm cho dev-khó,
  ít nhất 314 nhóm niêm phong cho test.
- **Chưa dùng được ngay:** kho GitHub `qtli/GSM-Plus` không khai báo giấy phép (kiểm
  tra 2026-11-02), và mình chưa mở dữ liệu thật. Cần xem bản phát hành khác hoặc hỏi
  tác giả trước khi dùng cho bài báo.

**Cỡ mẫu 314 nhóm** là tính theo giả định: phát hiện chênh 5 điểm phần trăm, 10% câu
bất đồng giữa hai mô hình, power 80%. Cần tính lại bằng tỷ lệ bất đồng đo được trên
dev-khó.

**So sánh chính:** CoT tinh chỉnh với CoT gốc, trên cùng câu hỏi, với λ = 0,1.
Báo cáo riêng tỷ lệ đúng, số token và U kèm khoảng tin cậy bootstrap theo nhóm.

**So sánh phụ:**
- CoT tinh chỉnh với PAL gốc: tinh chỉnh có đuổi kịp công cụ tính toán không.
- Bộ điều phối đơn giản dùng mô hình gốc và mô hình tinh chỉnh.

**Giới hạn cần ghi trong bài:** Qwen có thể đã thấy GSM8K khi được huấn luyện, nên
kết quả trên các bộ sinh từ GSM8K có thể cao hơn thực tế.

## 4. Hai điểm quyết định (đề xuất)

| Điểm | Khi nào | Điều kiện đi tiếp | Nếu không đạt |
| --- | --- | --- | --- |
| **Đủ độ khó** | Cuối tháng 12 | Trên dev-khó, mô hình gốc đạt CoT ≤ 90% và PAL ≤ 95% | Đổi bộ đánh giá, không tinh chỉnh tiếp trên bộ quá dễ |
| **Đáng làm tiếp** | Cuối tháng 1 | Trên dev-khó, U của CoT tinh chỉnh cao hơn CoT gốc ít nhất 0,02 | Báo thầy, quay về bộ điều phối, ghi nhận kết quả âm |

Với 100 nhóm, khoảng tin cậy còn rộng. Điểm này chỉ quyết định có làm tiếp hay không,
không dùng để kết luận mô hình tốt hơn. Không đổi ngưỡng sau khi đã thấy kết quả.

## 5. Lịch

| Thời gian | Việc | Xong khi |
| --- | --- | --- |
| Tháng 11 | Hỏi thầy hai câu ở mục 1, cập nhật đề cương; kiểm tra GSM-Plus | Có phạm vi được xác nhận; biết dùng được bộ nào |
| Tháng 12 | Học nền LoRA; **tự tay** chạy tinh chỉnh 1.000 câu; thêm `adapter_path` vào `qwen_mlx_backend.py` và ghi mã băm adapter vào manifest; đo độ khó | Qua điểm "đủ độ khó" |
| Tháng 1 | Tinh chỉnh 2.000 câu, rồi một epoch nếu cần; chốt ngưỡng và giao thức | Qua điểm "đáng làm tiếp" |
| Tháng 2, 3 | Tinh chỉnh bản cuối; chạy test niêm phong | Có bảng kết quả |
| Tháng 4, 5 | Phân tích lỗi, viết báo cáo và bản thảo | Nộp báo cáo |

**Thời gian chạy test ước tính:** lần chạy trước tốn 26,6 giây mỗi câu cho 3 chiến
lược. 300 nhóm × 2 mô hình × 3 seed là khoảng 13 giờ. Câu khó hơn sẽ tốn thêm, nhưng
vẫn chạy được trên M1.

## 6. Kinh phí

Khoản thuê máy 2.499.999 đồng tương đương khoảng 96 USD (tỷ giá giả định 26.000
đồng/USD). Giá RTX 4090 đang được rao từ khoảng 0,34 đến 0,89 USD/giờ, tức khoảng 108
đến 283 giờ. Giá này lấy từ các trang tổng hợp, cần xem lại trên trang của nhà cung
cấp trước khi chi.

**Đề xuất: chưa thuê trước điểm "đáng làm tiếp".** Một epoch trên M1 đã chạy được
trong khoảng một ngày. Chỉ thuê khi cần thử nhiều cấu hình, vì 3 epoch × 3 cấu hình
tốn khoảng 9 ngày chạy liên tục trên M1.

**Hai rủi ro khi thuê:**
- **Không dùng trực tiếp được bản MLX 4-bit trên GPU NVIDIA.** Phải tinh chỉnh trên
  trọng số gốc, gộp, rồi lượng tử hóa lại để chấm trên M1. Khi đó mô hình gốc dùng để
  so sánh cũng phải đi qua đúng quy trình này.
- **Chứng từ thanh toán.** Cần hỏi trường có chấp nhận hóa đơn nước ngoài không.
