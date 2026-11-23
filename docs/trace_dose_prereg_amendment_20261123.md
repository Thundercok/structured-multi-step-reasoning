# Sửa đổi đăng ký trước H4 (bản nháp, 2026-11-23)

> **Trạng thái: NHÁP — chưa có hiệu lực.** Chỉ có hiệu lực khi người làm đề tài duyệt và commit file này
> **trước** khi chạy `run_phase.sh analyze`. Sửa đổi cho `docs/trace_dose_prereg.md` (commit `c437df0`).

## 0. Ai đã thấy gì trước khi viết sửa đổi này

- **Chưa ai xem kết quả H4.** Lúc viết (2026-11-23), 5/5 ô seed 0 đã chạy xong eval và can thiệp và nằm trên đĩa
  máy M1, nhưng theo session chạy máy thì chưa ai mở tỉ lệ `follows`, accuracy hay bảng phân loại của bất kỳ ô
  nào. Seed 1 chưa chạy. `analyze` chưa chạy. Phiên viết bản nháp này (chạy trên cloud) không truy cập được đầu ra H4.
  *[Người làm đề tài xác nhận dòng này trước khi commit.]*
- **Đã thấy dữ liệu H3** (`audit/trace_source_20261117`, `audit/trace_source_seed1_20261119`; khác câu đo với H4,
  nhưng là **cùng adapter** ở hai mức 0% và 100%). Phân tích khám phá trên H3 (mục 2) là lý do đề xuất thay đổi B.
  Ghi rõ ở đây để người đọc tự cân nhắc.

## 1. Thay đổi A — phép kiểm chính lên cấp adapter

### Lý do

Mô hình chính hiện tại chỉ có random intercept theo câu hỏi. Nó coi ~5.000 dòng là độc lập (khi đã biết câu
hỏi), nhưng thực ra chỉ có **10 lần huấn luyện** (5 mức × 2 seed). Nếu mỗi lần huấn luyện tự lệch một lượng
$c \sim \mathcal{N}(0, \tau)$ trên thang logit, độ lệch đó lẫn vào hiệu ứng liều lượng (pseudo-replication).

Mô phỏng (`audit/trace_dose_20261120/amendment_20261123/`, dùng chính `fit_glmm_lrt` của `analyze.py`;
bản vectorize cho likelihood khớp bản gốc đến 12 chữ số; 200 lần lặp mỗi ô; giả định 500 câu, $\beta_0 = 1{,}5$,
$\sigma_{\text{câu}} = 1$, bỏ 15% dòng):

| Kịch bản | τ | LRT đã đăng ký | Phép kiểm cấp adapter (t, 7 bậc tự do) |
|---|---|---|---|
| Không có hiệu ứng (đúng ra phải ~0,05) | 0 | 0,06 | 0,04 |
| | 0,1 | 0,11 | 0,04 |
| | 0,2 | 0,26 | 0,03 |
| | 0,3 | 0,43 | — |
| Hiệu ứng cỡ H3, $\beta_{\text{human}} = -0{,}9$ | 0,1 | 1,00 | 1,00 |
| | 0,2 | 1,00 | 0,95 |
| Nửa hiệu ứng H3, $\beta_{\text{human}} = -0{,}45$ | 0,1 | 0,94 | 0,81 |
| | 0,2 | 0,85 | 0,47 |

Chưa biết τ thật. H3 chỉ có 2 cặp seed (self 0,885 so với 0,870; human 0,756 so với 0,759), quá ít để ước lượng.

### Phép kiểm chính mới (H4)

1. Với mỗi ô $c = (\text{seed}, \text{tỉ lệ})$: $n_c$ = số quan sát đủ điều kiện (mục 2), $f_c$ = số `follows`.
2. $y_c = \text{logit}\big((f_c + 0{,}5) / (n_c + 1)\big)$.
3. Hồi quy OLS trên 10 điểm: $y_c = b_0 + b_{\text{human}}\,x_c + b_{\text{seed}}\,s_c$, với $x_c = k/229$.
4. Phép kiểm t hai phía cho $H_0: b_{\text{human}} = 0$, 7 bậc tự do, **α = 0,05**.
5. Quy tắc đọc **giữ nguyên** như prereg gốc, chỉ thay $p_{\text{LRT}}$ bằng $p_t$ và $\hat\beta_{\text{human}}$ bằng $\hat b_{\text{human}}$.

### Các phân tích cũ đổi vai trò (chỉ mô tả, không quyết định kết luận)

- GLMM + LRT 1 bậc tự do (`H4_glmm_dose`), `per_seed_glmm`, `common_intersection_glmm`, và LRT phi tuyến 3 bậc tự do
  đều dính cùng vấn đề nên **chỉ còn là mô tả**. Báo cáo kèm cảnh báo rằng p-value của chúng có thể quá nhỏ.
- **Độ nhạy:** lặp lại phép kiểm cấp adapter trên tập câu đủ điều kiện ở **cả 10 ô**, để loại khác biệt thành phần câu giữa các ô.
- Quy tắc giữ chữ *"monotonically"* giữ nguyên ý: H4 phải đạt, **và** bảng 5 mức (trung bình $y_c$ của hai seed
  ở mỗi mức) phải giảm dần qua các mức trung gian. Với 10 điểm, không có phép kiểm phi tuyến nào đủ mạnh, nên phần này là
  đọc mô tả và phải viết như vậy.
- McNemar theo cặp (`paired_checks`) giữ nguyên. Đó là so sánh giữa **đúng hai adapter đó**, phải ghi rõ như vậy.

### Cái giá

Kém mạnh hơn nếu hiệu ứng nhỏ (0,47 ở nửa hiệu ứng H3 khi τ = 0,2). Kết quả "không phân biệt được" khi đó vẫn
phải báo cáo và lùi về Bản A theo quy tắc đọc.

## 2. Thay đổi B — câu có vết gốc bị gắn cờ (`expected = None`)

> Đây là điểm dễ bị hỏi "chọn sau khi thấy dữ liệu" nhất: lựa chọn dựa trên khám phá H3 ở dưới, không dựa trên H4.

### Bối cảnh

`plan_intervention` (`structured_llm/counterfactual.py:226-232`) vẫn giữ lại vết gốc có `Calc` sai hoặc có đáp án
không lấy từ `Calc` cuối, nhưng đặt `expected = None`. Những câu này **không thể** được tính là `follows`. Chỉ số
gốc tính chúng vào mẫu số như một lần không bám bước, nên nó trộn hai thứ: *chất lượng vết gốc* và *việc bám bước bị sửa*.

Khám phá trên H3 (đã thấy, khác câu đo với H4):

| Seed | `expected=None` self / human | `follows` self / human (mọi câu có kế hoạch) | Chỉ câu có `expected` | Bất đồng trên tập chung có `expected` | McNemar |
|---|---|---|---|---|---|
| 0 | 4/227 / 17/209 | 0,885 / 0,756 | 0,901 / 0,823 | 13 / 5 | p ≈ 0,10 |
| 1 | 4/223 / 12/220 | 0,870 / 0,759 | 0,886 / 0,803 | 19 / 4 | p ≈ 0,003 |

### Quyết định: B1 (người làm đề tài chọn ngày 2026-11-23)

- **Chỉ số chính của H4** = `follows` trên các quan sát có kế hoạch **và** có `expected` khác None. Phép kiểm cấp
  adapter ở mục 1 dùng $n_c$, $f_c$ tính theo định nghĩa này.
- **Báo cáo riêng cho từng ô:** tỉ lệ vết bị gắn cờ (`expected = None` / số có kế hoạch), như một chỉ số chất lượng vết.
- **Phân tích phụ:** chỉ số gốc (`follows` trên mọi quan sát có kế hoạch), qua cùng phép kiểm cấp adapter.
- Phương án bị loại: B2 (giữ chỉ số gốc làm chính).

Rủi ro của B1: đây là lọc theo đặc tính của chính từng adapter, giống như lọc theo "có kế hoạch" đã có. Phải báo
cáo tỉ lệ đủ điều kiện cho từng ô (prereg gốc đã yêu cầu như vậy).

## 3. Hạn chế bổ sung

- Hai adapter ở mức 0% và 100% là **chính adapter H3**, mà hiệu ứng self > human của chúng đã biết (trên câu khác).
  H4 độc lập với H3 về câu đo, **không độc lập về adapter**. Độ dốc liều lượng phụ thuộc phần lớn vào hai đầu đó.
- Mô phỏng ở mục 1 dùng các tham số giả định, không phải số đo thật.

## 4. Việc phải làm trước `analyze`

1. ~~Chọn B1 hoặc B2~~ (đã chọn B1). Xác nhận mục 0, đổi trạng thái file thành "có hiệu lực", rồi commit.
2. Thêm phép kiểm cấp adapter vào `analyze.py`, kèm test tái hiện mức báo nhầm ~0,05 khi τ > 0.
3. Thêm một dòng trỏ tới file này ở đầu `docs/trace_dose_prereg.md`.
