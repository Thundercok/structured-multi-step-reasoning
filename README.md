# structured-multi-step-reasoning

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![MLX](https://img.shields.io/badge/optimized-Apple%20Silicon%20MLX-black.svg)](https://github.com/ml-explore/mlx)
[![Status](https://img.shields.io/badge/status-active%20research-green.svg)](docs/research_plan.md)
[![Hugging Face](https://img.shields.io/badge/%F0%9F%A4%97%20adapters-trace--dose%20LoRA-yellow.svg)](https://huggingface.co/thundercockk/qwen3-8b-trace-dose-lora)

Đề tài nghiên cứu khoa học sinh viên (NCKH). Câu hỏi chính: **khi một mô hình ngôn ngữ viết ra các bước giải toán,
đáp án cuối của nó có thật sự dựa vào các bước đó không?** Hay mô hình đã "biết" đáp án từ trước, và các bước chỉ
viết ra cho có?

Mô hình được dùng là Qwen3-8B, tinh chỉnh trên MacBook (Apple Silicon, thư viện MLX) bằng các bài toán đố
GSM8K. 10 adapter LoRA của thí nghiệm trace-dose (H4) có trên
[Hugging Face](https://huggingface.co/thundercockk/qwen3-8b-trace-dose-lora).

---

## Contents

- [Ý tưởng trong một phút](#ý-tưởng-trong-một-phút)
- [Thí nghiệm](#thí-nghiệm)
- [Kết quả](#kết-quả)
- [Làm sao để tin các con số này](#làm-sao-để-tin-các-con-số-này)
- [Trong repo có gì](#trong-repo-có-gì)
- [Chạy thử](#chạy-thử)

---

## Ý tưởng trong một phút

Mô hình viết lời giải theo một định dạng cố định để máy kiểm tra được (ví dụ rút gọn):

```text
Step 1: Beth nướng 4 mẻ, mỗi mẻ 2 tá.
Calc: 4*2=8
Step 2: 8 tá là 8*12=96 cái bánh.
Calc: 8*12=96
...
Answer: 6
```

Để kiểm tra mô hình có dựa vào các bước hay không, ta **sửa một bước** rồi cho mô hình viết tiếp. Ví dụ đổi
`Calc: 4*2=8` thành `Calc: 4*2=10`.

- Mô hình viết tiếp `10*12=120` rồi ra đáp án 7,5: nó **làm theo** bước bị sửa (`follows`). Như vậy đáp án phụ thuộc
  vào các bước.
- Mô hình bỏ qua con số 10 và vẫn ra 6: nó **quay về** đáp án cũ (`reverted`). Như vậy các bước có thể chỉ là phần
  trang trí.

Ví dụ thật từ dữ liệu, bài về dân số Los Angeles: phép chia `6000000/2` bị sửa từ 3.000.000 thành 3.000.005.
Mô hình lờ con số đó đi, viết lại 3.000.000 rồi ra đáp án cũ.

Lưu ý: cách đo này chỉ xem mô hình *viết gì* sau khi chữ bị sửa. Nó không nhìn vào bên trong mạng nơ-ron.

---

## Thí nghiệm

Có ba mô hình được so sánh:

| Tên | Là gì |
| :--- | :--- |
| **Gốc** (`base_prefill`) | Qwen3-8B chưa tinh chỉnh, được nhắc viết theo định dạng `Step`/`Calc` |
| **Plain** | Tinh chỉnh bằng lời giải bình thường |
| **CF** (counterfactual) | Tinh chỉnh bằng lời giải thường, cộng thêm các lời giải có một bước bị sửa và phần viết tiếp đúng theo bước sửa |

Giả thuyết:
- **H1:** CF làm theo bước bị sửa nhiều hơn Plain.
- **H2:** Plain làm theo bước bị sửa ít hơn mô hình gốc, tức là tinh chỉnh bình thường làm mô hình "lờ" các bước.

---

## Kết quả

### Đề thi GSM8K chính thức (1.319 câu, mở một lần duy nhất)

Đề thi chính thức được giữ kín suốt quá trình phát triển. Nó chỉ được tải về và chạy đúng một lần (11 đến 13/11/2026),
theo một kế hoạch đã công bố trước ([kế hoạch](docs/sealed_test_gsm8k_prereg.md),
[kết quả đầy đủ](audit/gsm8k_sealed_test_20261111/RESULTS.md)).

| | CF | Plain | Gốc |
| :--- | :---: | :---: | :---: |
| Làm theo bước bị sửa (671 câu chung) | **81,1%** | 76,3% | — |
| Giải đúng | 79,8% | 78,8% | 88,5% |

- **H1 được ủng hộ** trên đề này (p = 0,0018).
- Cái giá: cả hai bản tinh chỉnh giải đúng **ít hơn** mô hình gốc, CF kém 8,7 điểm và Plain kém 9,7 điểm.
- Khi so cả ba mô hình trên 441 câu chung (phân tích làm thêm, không có trong kế hoạch): gốc 85,3%, CF 82,1%,
  Plain 78,5%. Nghĩa là CF không làm mô hình bám bước *hơn* bản gốc. CF chỉ *mất ít hơn* so với tinh chỉnh bình
  thường.

### Lặp lại trên GSM-Plus (đề biến thể, thay số trong bài)

Một kết quả chỉ đáng tin khi lặp lại được trên dữ liệu khác.

- **H2 lặp lại được.** Plain làm theo bước bị sửa ít hơn mô hình gốc (142 so với 159 trên 185 câu, p = 0,0076).
- **H1 không lặp lại được.** CF và Plain gần như ngang nhau, ở cả lượt 500 câu (p = 0,69) và lượt 819 câu còn lại
  (p = 0,51). Gộp cả hai lượt, CF chỉ hơn 1,4 điểm, và khoảng tin cậy 95% đi từ −1,6 đến +4,5 điểm, tức là có thể bằng
  không.
- Chi tiết: [lượt 500 câu](audit/gsm_plus_replication_20261114/RESULTS.md),
  [lượt 819 câu](audit/gsm_plus_h1_holdout_20261115/RESULTS.md).

### Tinh chỉnh càng lâu thì càng lờ bước?

Thí nghiệm này chấm Plain sau 50, 200, 1.000 và 2.000 vòng huấn luyện, trên cùng 500 câu GSM-Plus
([kế hoạch](docs/sft_dose_response_prereg.md), [số liệu](audit/sft_dose_response_20261116/results.json)).

| Số vòng | Gốc | 50 | 200 | 1.000 | 2.000 |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Làm theo bước bị sửa | 84% | 77% | 73% | 73% | 71% |

Tỉ lệ giảm dần, nhưng cả hai kiểm định đã đăng ký trước đều không đạt ngưỡng. Theo quy tắc đã viết từ trước, kết
luận là **chưa phân biệt được** mức giảm rơi vào đầu quá trình hay giai đoạn sau. Hàng trên chỉ để mô tả: mỗi mốc
được tính trên một tập câu khác nhau.

### Tóm lại

Tinh chỉnh bình thường làm mô hình bớt bám các bước nó tự viết ra. Kết quả này lặp lại được. Việc huấn luyện thêm
bằng lời giải bị sửa (CF) có giúp được không thì đến giờ **chưa chắc chắn**: CF thắng trên GSM8K nhưng không thắng
trên GSM-Plus.

Hướng làm này cũng không mới. Đã có nghiên cứu huấn luyện trên lời giải bị sửa
([LIFT](https://arxiv.org/abs/2509.13334), [FRODO](https://arxiv.org/abs/2402.13950)), và đã có nhóm báo cáo rằng
tinh chỉnh bình thường làm giảm mức "trung thực" của lời giải ([Lobo et al.](https://arxiv.org/abs/2411.15382)).
Phần đóng góp của đề tài này là kiểm tra lại các hiệu ứng đó một cách chặt chẽ ([khảo sát](docs/related_work_survey_20261114.md)).

---

## Làm sao để tin các con số này

- **Viết luật trước, chấm sau.** Mỗi thí nghiệm có một tệp kế hoạch (trong `docs/*_prereg.md`). Tệp này ghi chỉ số,
  phép kiểm định và ngưỡng, và được commit lên git *trước* khi chạy. Thứ tự commit là bằng chứng rằng luật có trước
  kết quả.
- **Đề thi chỉ mở một lần.** Đề GSM8K chính thức không được đọc trong lúc phát triển, và đến nay đã dùng xong.
- **Giữ dữ liệu thô.** Mỗi lượt chạy có một thư mục riêng trong `audit/`, gồm script, output thô và kết quả.
- **Ghi rõ phần làm thêm.** Phân tích nào nghĩ ra sau khi đã thấy kết quả đều được ghi là thăm dò, không dùng để kết
  luận.
- **Báo cả kết quả không đẹp.** Ví dụ: H1 không lặp lại được; độ chính xác giảm sau tinh chỉnh; một bảng kết quả cũ
  phải [đính chính](audit/scaleup_eval_300_20261109/CORRECTION.md) vì 100 câu "chưa thấy" thật ra nằm trong dữ liệu
  huấn luyện.

Giới hạn: mỗi mô hình chỉ huấn luyện với một seed; mỗi mô hình bị sửa trên lời giải của chính nó, nên các cặp so sánh
khớp theo câu hỏi, không khớp theo lời giải.

---

## Trong repo có gì

```text
structured_llm/     mã chính: đọc định dạng Step/Calc, tạo bước sửa, chấm, can thiệp, phân tích
  trace.py          đọc và kiểm tra lời giải <think>/Step/Calc
  counterfactual.py lên kế hoạch sửa bước và tạo dữ liệu CF
  evaluate.py       chấm mô hình
  intervene.py      sửa một bước, cho mô hình viết tiếp, phân loại kết quả
  train.sh          tinh chỉnh LoRA trên Mac 16 GB
data/               dữ liệu đã cố định và danh sách chia tập
audit/              mỗi lượt chạy một thư mục: script, output thô, RESULTS.md
docs/               kế hoạch nghiên cứu, các tệp đăng ký trước, khảo sát tài liệu
tests/              kiểm thử (pytest)
```

## Chạy thử

Cần máy Mac Apple Silicon (hoặc Linux nếu chỉ chạy test) và Python 3.12.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

```bash
python -m structured_llm.gsm8k                 # chuẩn bị dữ liệu
python -m structured_llm.counterfactual        # tạo kế hoạch sửa bước
structured_llm/train.sh adapters/first 200     # tinh chỉnh 200 vòng
python -m structured_llm.evaluate --adapter adapters/first --limit 20 --out audit/first
python -m structured_llm.intervene --run audit/first --adapter adapters/first
```

Một lượt chấm đầy đủ mất nhiều giờ trên Mac 16 GB, nên ví dụ trên chỉ chạy 20 câu.

---

Repo này chỉ dành cho nghiên cứu. Trợ lý desktop RAT nằm ở repo riêng,
[`Thundercok/selective-delegation-agent`](https://github.com/Thundercok/deterministic-local-assistant), và mã nghiên cứu
không gọi tới nó. Kế hoạch đầy đủ: [`docs/research_plan.md`](docs/research_plan.md).
