# Huấn luyện MSRA Giai đoạn 1 (Structural Cold-Start SFT)

> **Mục tiêu:** Huấn luyện mô hình Qwen3-8B làm quen với cấu trúc lập luận đồ thị có hướng **MSRA XML DAG**, hình thành phản xạ phân rã bài toán thành các đơn vị con đóng gói ($v_t = \langle g_t, \tau_t, \mathcal{D}_t, y_t, \sigma_t \rangle$), cô lập biến phụ thuộc Markovian và thẩm định biên trước khi mở rộng sang học tìm kiếm trợ giúp (Help-Seeking).

---

## 1. Dữ liệu Huấn luyện ([`data/structured_msra_coldstart_v1`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/data/structured_msra_coldstart_v1))

Dữ liệu được chuyển đổi tất định và thẩm định 100% DAG hợp lệ từ hai nguồn dữ liệu chuẩn:

| Nguồn | Số câu Train | Số câu Valid | Tỷ lệ chuyển đổi hợp lệ | Ghi chú |
| --- | ---: | ---: | ---: | --- |
| **GSM8K Enriched** | 7.061 | 99 | 100,0% | Step 1 có tiền tố nêu đại lượng |
| **MATH Checkable (Level 3–5)** | 725 | 76 | 100,0% | Phép tính kiểm chứng bằng SymPy |
| **TỔNG CỘNG** | **7.786** | **175** | **100,0%** | 0 lỗi DAG, SHA-256 niêm phong |

### Thống kê Cấu trúc Đồ thị Lập luận (Empirical DAG Complexity):
* **Tổng số nút lập luận ($\mathcal{V}$):** 23.662 nút.
* **Số bước trung bình mỗi bài:** 3,04 bước (Dao động từ 1 đến 9 bước).
* **Bậc vào phụ thuộc biến ($\vert{}\mathcal{D}_t\vert{}$):**
  * $0$ biến phụ thuộc (bước cơ sở): 46,99% (11.118 nút).
  * $1$ biến phụ thuộc (chuỗi suy diễn tuyến tính): 35,82% (8.475 nút).
  * $2$ biến phụ thuộc (kết hợp hai kết quả trung gian): 13,30% (3.147 nút).
  * $\ge 3$ biến phụ thuộc: 3,89% (919 nút).
* **Độ dài ký tự trung bình:** 1.558 ký tự ($\approx 350-400$ tokens), 90% dưới 2.444 ký tự, vừa vặn hoàn hảo trong cửa sổ 1.024 token của LoRA.

---

## 2. Cấu trúc Thẻ Token XML Chuẩn

```xml
<step id="1" budget_remaining="2.00">
  <subgoal>Phát biểu mục tiêu con tường minh</subgoal>
  <deps>None</deps>
  <capability>CAP:SYMBOLIC_CALC</capability>
  <decision>SOLVE_LOCAL</decision>
  <execution>Biểu thức hoặc suy diễn cụ thể</execution>
  <verification status="COMMIT">Thẩm định tính hợp lệ tiên nghiệm</verification>
  <output_var>v1 = giá_trị</output_var>
</step>
```

---

## 3. Lệnh Thực thi

Kịch bản huấn luyện đã được tích hợp kiểm tra nguồn điện AC tự động:

```bash
# Chạy huấn luyện độc lập trên CPU/Metal sau khi tuyến GSM8K kết thúc:
./audit/lora_msra_20261107/run_msra_stage1.sh
```

---

## 4. Ngưỡng Nghiên cứu & Tiêu chí Đánh giá (Gate Criteria)

* **Cổng Định dạng (Format Gate):** Tỷ lệ sinh đúng 100% cú pháp thẻ XML và không có chu trình DAG trên 100 câu dev $\ge 90\%$.
* **Cổng Bảo toàn Độ chính xác (Accuracy Retention):** Độ chính xác đáp án cuối cùng không được suy giảm quá 3% so với mô hình baseline trên cùng tập câu.
