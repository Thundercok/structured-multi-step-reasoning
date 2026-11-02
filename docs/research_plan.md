# Kế hoạch nghiên cứu và lộ trình Q1

Cập nhật: 2026-11-02. **Đây là đề xuất, chưa có xác nhận bằng văn bản của thầy hướng
dẫn.** Đề cương đã nộp vẫn ghi "không huấn luyện lại trọng số" ở mục 4 và lấy bộ điều
phối làm đối tượng ở mục 3, nên cần cập nhật trước khi kế hoạch này có hiệu lực.

**Đề tài:** Xây dựng mô hình ngôn ngữ lớn có suy nghĩ có cấu trúc. Bản nháp BM02 ghi
"Thiết kế Mô hình Ngôn ngữ lớn hướng tới khả năng suy luận nhiều bước có cấu trúc";
cần đối chiếu với tên đã đăng ký.

## Luận điểm

**Kiểm tra phần suy nghĩ chỉ có ích khi đáp án thật sự phụ thuộc vào phần suy nghĩ đó.**

Đối tượng nghiên cứu là chính mô hình: Qwen3-8B được tinh chỉnh bằng LoRA, không làm kiến
trúc mới. Bài báo trả lời: để một kiểm tra rẻ, tất định dự đoán được câu trả lời sai trên
mô hình nhỏ, thì cần huấn luyện gì, và mức trung thực phải đạt bao nhiêu?

## Vì sao không chỉ làm "tinh chỉnh để trung thực hơn"

Việc đó đã có người làm. Đây là tra nhanh từ tóm tắt và trang arXiv, chưa phải khảo sát hệ
thống.

| Công trình | Đã làm | Chưa làm (theo phần đã đọc) |
| --- | --- | --- |
| [CASE](https://arxiv.org/abs/2607.18820) (preprint 7/2026) | Tinh chỉnh LoRA với CoT phản thực và che attention; Qwen3-8B, Llama-3.1-8B, DeepSeek-R1-Distill-Qwen-7B; báo cáo tăng khoảng 37% độ trung thực | Không có GSM8K, phản thực sinh bằng LLM, không đo phát hiện lỗi hay chi phí trên thiết bị |
| [FoCus](https://neurips.cc/virtual/2025/131093) (workshop NeurIPS 2025) | Tinh chỉnh trên dữ liệu có cấu trúc, tăng tới 29,4% với Qwen3-8B | Chưa đọc được bản đầy đủ |
| [FRODO](https://arxiv.org/abs/2402.13950) (Findings EMNLP 2024) | Huấn luyện mô hình nhỏ suy luận trung thực hơn | Bộ không phải toán |
| [Breaking the Chain](https://arxiv.org/abs/2603.16475) (preprint 3/2026) | Phản thực tất định; đưa ánh xạ ra công cụ ngoài gần như xóa khoảng cách trung thực | Không tinh chỉnh, không phải toán |
| [Correctness Conditioning](https://arxiv.org/abs/2610.37070) (preprint 10/2026) | Trên số học: chỉ đo câu đúng làm lệch kết quả (+7,4 điểm ở lượt chính) | Không huấn luyện |
| [RFEval](https://arxiv.org/abs/2602.17053) (ICLR 2026) | Lỗi trung thực tập trung ở toán và code | Không nối sang phát hiện lỗi |
| [Lobo và cộng sự](https://arxiv.org/abs/2411.15382) (preprint) | Tinh chỉnh có thể làm **giảm** độ trung thực | Bằng chứng hạn chế, tác giả tự ghi nhận |
| [Structural CoT](https://arxiv.org/abs/2610.15107) (preprint 10/2026) | **Gần nhất về phương pháp:** LoRA và GRPO trên mô hình nhỏ, đồ thị thực thi được, có đo can thiệp, trên GSM8k+ | Không đánh giá bộ kiểm tra hay phát hiện lỗi. Cùng nhóm với Breaking the Chain, nên là đối thủ cần theo dõi |
| [From Decorative to Load-Bearing](https://arxiv.org/abs/2609.25366) (9/2026) | Sửa một bước rồi cho viết tiếp; trên GSM8K khoảng 94,5% lờ đi chỗ sửa; độ khó giải thích 98,8% phần deviance được giải thích | Nhãn từ LLM, chỉ trên câu vốn đúng, không đo bộ kiểm tra dự đoán câu sai theo mức phụ thuộc |
| [Causal Consistency Regularization](https://arxiv.org/abs/2509.01544) (preprint) | Huấn luyện bằng đổi toán tử, trên GSM8K và bộ khác | Không đánh giá bộ kiểm tra dự đoán câu sai |
| [TrAC](https://arxiv.org/abs/2608.00422) (preprint 8/2026) | Dùng phần suy nghĩ để dự đoán câu sai trên toán, cũng tính AUROC và AURC | Không có trục độ trung thực. **Là mốc so sánh cho RQ3** |
| [Faithfulness as Information Flow](https://arxiv.org/abs/2605.24286) (preprint 5/2026) | Cùng tiền đề, huấn luyện để trung thực hơn | Tóm tắt không mô tả bộ kiểm tra hay dự đoán lỗi; chưa đọc toàn văn |

**Kết quả cổng 2, tạm đạt.** Khảo sát do `agy` chạy không thấy bài nào trùng hoàn toàn. Tôi mở lại 5 bài
gần nhất ở trên, gồm 2 bản toàn văn và 3 trang tóm tắt, đều đọc qua công cụ tóm tắt tự động: không bài
nào cho thấy đã đo giá trị dự đoán của bộ kiểm tra theo mức trung thực. **Nhiều bài nêu cùng tiền đề, nên ý tưởng không mới; phần
chưa ai đo là kiểm chứng định lượng.** Chưa truy cập được trực tiếp Semantic Scholar, OpenReview, ACL
Anthology và Google Scholar. Theo dõi arXiv hằng tháng, vì nhiều bài ở đây mới đăng trong vài tuần gần
đây. Không dùng từ "uncrowded" hay "chưa ai làm" trong bài nếu chưa có khảo sát đầy đủ hơn.

## Bằng chứng nội bộ

Đọc lại đầu ra thật của mô hình gốc trên 93 câu đã lộ
([phân tích](../audit/base_error_anatomy_20261102/README.md)): 34/93 đầu ra CoT chỉ có kế
hoạch, không có phép tính, đúng 23/34; có viết phép tính thì đúng 58/59. Đây là tương quan.
11/12 câu CoT sai không viết phép tính nào. Câu sai vẫn có confidence 0,94 đến 0,98.

## Câu hỏi nghiên cứu

- **RQ1, cơ chế (mới, đóng góp chính).** Giá trị dự đoán câu sai của kiểm tra tất định có tăng
  theo độ trung thực không?
- **RQ2, huấn luyện.** Trên toán, độ trung thực đo bằng phản thực tất định thay đổi thế nào giữa
  prompt tốt, công cụ tính ngoài, tinh chỉnh thường và tinh chỉnh có phản thực?
- **RQ3, chi phí.** So với đối chiếu PAL và suy nghĩ tự do, cách này tốn bao nhiêu token và thời
  gian trên M1 cho cùng mức phát hiện lỗi?

Kết quả âm vẫn là kết quả: "kiểm tra có giá trị như nhau bất kể độ trung thực" cũng là một phát
hiện đáng công bố nếu phương pháp đúng.

## Định dạng và dữ liệu

Cấu trúc nằm trong khối `<think>`. Dòng `Calc` là chương trình nhỏ nên code tính lại được cả
chuỗi. Xem `structured_llm/trace.py`.

```text
<think>
Step 1: Natalia sold 48/2 = 24 clips in May.
Calc: 48/2=24
Step 2: Natalia sold 48+24 = 72 clips altogether.
Calc: 48+24=72
</think>

Answer: 72
```

Nguồn là `data/gsm8k_source/train.jsonl`, revision `3101c7d5`, có kiểm tra mã băm. Loại 120 câu
đã dùng để phát triển. Chưa đọc tập test chính thức.

| Bộ | Tạo bằng | Nội dung |
| --- | --- | --- |
| `data/structured_gsm8k_v1` | `python -m structured_llm.gsm8k` | 7.059 câu train, 99 valid, 100 dev. Chia bằng xếp hạng SHA-256 trước khi lọc |
| `data/structured_gsm8k_cf_v1` | `python -m structured_llm.counterfactual` | Thêm 3.318 câu phản thực do code tính lại, không dùng LLM; valid giữ nguyên |

Bản đầu của bộ phản thực có 3/25 mẫu lỗi; sau khi siết lọc còn 1/25 lỗi nhỏ và lỗi đó đã được
chặn. **Phần đọc này do agent làm, chưa có người rà.** 100 mẫu chờ rà ở
`audit/counterfactual_review_20261102/sample.md`. Đổi số có thể tạo bài toán kỳ cục về nghĩa dù
phép tính vẫn đúng, cần ghi trong bài.

## Chỉ số

Mọi chỉ số tính tất định.

| Chỉ số | Ý nghĩa | Trần trên lời giải mẫu |
| --- | --- | ---: |
| `format_valid` | Toàn bộ đầu ra đúng ngữ pháp | 100% (điều kiện lọc) |
| `calc_accuracy` | Tỷ lệ dòng `Calc` tính đúng | 100% (điều kiện lọc) |
| `grounded_rate` | Tỷ lệ toán hạng có trong câu hỏi hoặc kết quả trước đó | 80,9% |
| `answer_from_last_calc` | Đáp án trùng kết quả `Calc` cuối | 94,9% |
| `correct` | Đáp án đúng, đọc lỏng để so công bằng với đầu ra tự do | |

**Độ trung thực** (`structured_llm/intervene.py`): sửa một kết quả trung gian, cho mô hình viết
tiếp, xếp thành `follows`, `reverted`, `other`, `no_answer`. **Kết quả chính tính trên mọi vết can
thiệp được, không chỉ câu đúng**, theo
[Correctness Conditioning](https://arxiv.org/abs/2610.37070); câu đúng báo cáo phụ. Phải báo cáo
tỷ lệ đủ điều kiện, vì câu không đủ điều kiện cũng là một dạng chọn lọc. `reverted` có thể là mô
hình tự sửa lỗi, nên phải đọc đầu ra trước khi diễn giải.

**Thiết kế RQ1 ở cấp từng câu:** vết bị cờ (phép tính sai, hoặc đáp án không lấy từ `Calc` cuối)
vẫn được can thiệp, ở một phép tính đúng trước chỗ sai. Vết này không có đáp án kỳ vọng, nên chỉ
quan sát đáp án có đổi hay không (`moved`). Bảng `rq1` trong kết quả đếm câu sai theo hai chiều:
đáp án có đổi và vết có bị cờ. **Giới hạn:** vết sai định dạng không can thiệp được, và can thiệp
chỉ làm được trên vết có phép tính đúng trước chỗ sai, nên vẫn còn chọn lọc; phải báo cáo tỷ lệ
đủ điều kiện. Mô hình thống kê cụ thể chốt khi ghi giao thức.

**Rủi ro nhiễu lớn nhất của RQ1 là độ khó.** Câu khó có thể vừa dễ sai vừa khiến đáp án phụ thuộc phần
suy nghĩ hơn ([Jia và Mu](https://arxiv.org/abs/2609.25366)), nên tương quan thô giữa độ trung thực và
khả năng phát hiện lỗi có thể chỉ phản ánh độ khó. Vì vậy phải so **trên cùng một câu hỏi giữa các điều
kiện**, dùng hiệu ứng ngẫu nhiên theo câu, và báo cáo theo số bước. Nếu hiệu ứng biến mất sau khi kiểm soát
độ khó thì đó là kết quả âm phải báo cáo.

**Một điểm yếu của bộ kiểm tra:** dòng `Calc: 220=220` đúng ngữ pháp và đúng số học nhưng không kiểm chứng
gì. Phải đếm riêng các dòng rỗng nghĩa này.

## So sánh

| Chế độ | Mô hình | Prompt |
| --- | --- | --- |
| `tuned`, `tuned_cf` | Có adapter, thường và có phản thực | Chỉ câu hỏi |
| `base_instructed` | Gốc | Mô tả định dạng và một ví dụ |
| `base_tool`, `tuned_tool` | Gốc hoặc có adapter | Như chế độ tương ứng, nhưng runtime tính kết quả mỗi dòng `Calc`. Thời gian không so được vì mỗi lần gọi phải chạy lại prompt; so bằng token |
| `base_showcalc` | Gốc | Yêu cầu viết mọi phép tính, tắt thinking |
| `base_native` | Gốc | Chỉ câu hỏi, suy nghĩ tự do |
| `base_pal` | Gốc | Viết chương trình, chạy qua bộ thông dịch không dùng `exec` |

**Không dùng CoT và DIRECT cũ làm mốc:** nhãn của chúng không khớp hành vi thật, so vào sẽ cho mức
tăng ảo. Báo cáo cũ giữ nguyên làm tư liệu, dữ liệu thô ở `runs/`.

## Các cổng dừng (đề xuất, cần thầy xem)

Làm từ rẻ đến đắt. Chốt ngưỡng trước khi chạy. Không đổi ngưỡng sau khi đã thấy kết quả.

| Cổng | Hạn | Điều kiện đi tiếp | Nếu không đạt |
| --- | --- | --- | --- |
| **0. Học được định dạng** | 11/2026 | Trên dev, `format_valid` của `tuned` ≥ 90% | Xem lại định dạng hoặc dữ liệu |
| **1. Có khoảng trống** | 11/2026 | `base_instructed` theo `Calc` bị sửa < 95% trên mọi vết can thiệp được | Bỏ RQ2, chuyển trọng tâm sang RQ3 |
| **2. Có chỗ đứng** | 11/2026 | Khảo sát hệ thống không thấy bài đã làm RQ1 | Đổi câu hỏi trước khi tốn thêm công |
| **3. Bộ đủ khó** | 12/2026 | Trên bộ khó, `base_showcalc` và `base_pal` đều ≤ 90% | Đổi bộ đánh giá |
| **4. Có tín hiệu** | 1/2027 | Trên dev-khó, kiểm tra bắt ≥ 50% câu sai, báo nhầm ≤ 20%, ở ít nhất một điều kiện | Bỏ mục tiêu Q1, viết hướng tiếng Việt hoặc báo cáo trung thực |

## Cỡ mẫu và thời gian máy

| Cần đo | Cỡ mẫu (alpha 0,05, power 0,8) |
| --- | --- |
| Chênh độ trung thực 10 điểm, 20% đến 30% cặp bất đồng | 155 đến 234 cặp |
| Chênh độ trung thực 15 điểm, 20% đến 30% cặp bất đồng | 68 đến 103 cặp |
| Recall phát hiện lỗi, sai số ±0,10 | Khoảng 100 câu sai mỗi điều kiện |

Có 100 câu sai đòi hỏi 5.000 câu nếu đúng 98%, nhưng chỉ 1.001 câu nếu đúng 90% và 501 câu nếu đúng
80%. **Vì vậy GSM8K train không đủ cho RQ1 và bộ khó là bắt buộc.**

Ước tính, sẽ thay bằng số đo: huấn luyện khoảng 214 token mỗi vòng ở 15 token/giây, tức 2.000 vòng
mất khoảng 8 giờ và một epoch khoảng 28 giờ. 2 loại mô hình với 3 seed ở 2.000 vòng mất khoảng 48
giờ. Lượt đo cũ sinh khoảng 10 token/giây, nên 1.000 câu với 5 chế độ mất khoảng 30 đến 40 giờ. M1 làm
được nếu chạy nhiều đêm. **Chưa cần thuê máy trước cổng 4.**

## Dữ liệu kiểm tra cuối

Ứng viên đầu là [GSM-Symbolic](https://github.com/apple/ml-gsm-symbolic): có sẵn dữ liệu; điều khoản
không thấy cấm nghiên cứu nhưng cần đọc kỹ. Nó sinh từ tập test GSM8K, nên dùng nó là nới quy tắc
hiện tại và **phải có quyết định của người làm nghiên cứu, ghi rõ trong bài**.
[GSM-Plus](https://arxiv.org/abs/2402.19255) không khai báo giấy phép khi kiểm tra ngày 2026-11-02.
Qwen có thể đã thấy GSM8K khi huấn luyện.

## Tạp chí mục tiêu

Số liệu lấy từ trang tổng hợp, các nguồn có chỗ mâu thuẫn. **Kiểm tra lại trên Scimago, JCR và
trang tạp chí trước khi gửi.** Trước hết phải hỏi trường tính Q1 theo danh sách nào; tôi chưa tìm
thấy quy định hiện hành cho bài của sinh viên.

| Thứ tự | Tạp chí | Thông tin đã thấy | Nhận xét |
| --- | --- | --- | --- |
| Mục tiêu chính | [Neural Networks](https://www.journalmetrics.org/journal/neural-networks) | Q1; IF 2025 khoảng 6,3, nguồn khác ghi cao hơn | Hợp với phần huấn luyện và cơ chế |
| Mục tiêu chính | [Knowledge-Based Systems](https://www.journalmetrics.org/journal/knowledge-based-systems) | JCR Q1; IF 2025 khoảng 7,6; khoảng 5 tháng đến khi đăng; truy cập mở trả phí khoảng 3.130 USD, hybrid nên không bắt buộc | Hợp nếu nhấn vào độ tin cậy của hệ thống |
| Mục tiêu chính | [Information Processing & Management](https://academicjobs.com/academic-journals/information-processing--management/1032) | Khoảng 4 tháng đến khi nhận, CiteScore 11 | Cần xem phạm vi có hợp không |
| Với cao | [TACL](https://transacl.org/index.php/tacl/about) | JCR Q1; miễn phí; review khoảng 8 tuần theo LetPub | Rào cao nhất, nhưng phản hồi nhanh và hợp cộng đồng nhất |
| Dự phòng | [JIT](https://www.tandfonline.com/journals/tjit20/about-this-journal) | Tạp chí của TDTU; Scopus Q1, CiteScore 8,2 (2024); IF 2,1; khoảng 103 ngày đến quyết định sau phản biện; thông tin phí mâu thuẫn | Phải hỏi xem trường có tính không, và phạm vi thiên về viễn thông |

Bài hội nghị như NeurIPS, ICLR hay ACL rất có giá trị trong ngành nhưng không có xếp hạng quartile
như tạp chí, nên chỉ chọn nếu trường chấp nhận.

## Lịch

| Thời gian | Việc | Xong khi |
| --- | --- | --- |
| Tháng 11 | Hỏi thầy về phạm vi, tên đề tài, tiêu chuẩn Q1 và thứ tự tác giả; khảo sát hệ thống; **tự tay** chạy lại một vòng nhỏ | Qua cổng 0, 1, 2 |
| Tháng 12 | Tinh chỉnh 2.000 vòng, có và không có phản thực, 3 seed; quyết định bộ khó | Qua cổng 3 |
| Tháng 1 | Đo trên dev-khó; chốt ngưỡng và giao thức, ghi trước khi chạy | Qua cổng 4 |
| Tháng 2 | Chạy tập niêm phong. **Đăng preprint nếu thầy đồng ý**, vì lĩnh vực đổi nhanh | Có bảng kết quả, có preprint |
| Tháng 3, 4 | Phân tích lỗi; viết bản thảo; gói mã và dữ liệu để tái lập | Bản thảo đủ để thầy đọc |
| Tháng 5 | Nộp báo cáo; gửi tạp chí | Đã gửi bài |

Q1 thường mất nhiều tháng, nên mục tiêu thực tế cho tháng 5 là **đã gửi bài**, không phải đã được nhận.

## Rủi ro lớn nhất

| Rủi ro | Cách giảm |
| --- | --- |
| Có người công bố RQ1 trước | Cổng 2; theo dõi arXiv hằng tháng, nhất là nhóm Structural CoT; preprint sớm |
| Hiệu ứng RQ1 chỉ là nhiễu do độ khó | So trên cùng câu hỏi giữa các điều kiện; báo cáo kết quả âm nếu có |
| Làm một mình, kinh nghiệm công bố hạn chế | Xin thầy đọc sớm; chốt giao thức trước khi chạy |
| Tinh chỉnh làm giảm độ trung thực | Vẫn là kết quả; có 3 seed và đo ngay ở cổng 1 |
| Mô hình 8B bị hỏi về chữ "lớn" trong tên đề tài | Thống nhất cách gọi với thầy khi cập nhật đề cương |
| Người phản biện hỏi "sao không dùng công cụ tính" | Đưa `base_tool` vào làm mốc so sánh ngay từ đầu |
