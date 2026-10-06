# Định hướng NCKH

## Sản phẩm cần đạt

Thứ tự ưu tiên: **bài báo NCKH → pipeline nghiên cứu tái lập được → app đơn giản
cho người ít rành công nghệ**. Một kết quả âm có phương pháp đúng, phân tích rõ
và tái lập được vẫn là kết quả nghiên cứu. Không đặt điều kiện phải chứng minh
phương pháp của nhóm luôn tốt hơn.

Tên đề tài làm việc: **Điều phối chiến lược suy luận và quyết định dừng theo
ngân sách cho mô hình ngôn ngữ nhỏ**.

Đối tượng nghiên cứu là bộ điều phối trên mô hình nền cố định. Phạm vi đầu tiên
không cần huấn luyện lại mô hình nền. Đo chất lượng và chi phí trên bài toán có
đáp án kiểm chứng được trước khi mở rộng sang trợ lý tài liệu cá nhân.

## Câu hỏi và giả thuyết

**RQ1:** kết hợp chọn chiến lược ban đầu và quyết định có chạy chiến lược tiếp
theo hay không có cải thiện đánh đổi accuracy–token so với chiến lược cố định
hoặc chỉ chọn một lần ở đầu vào không?

H1: full policy cải thiện `accuracy − lambda × generated_tokens/1000` trên test
so với one-shot router tại lambda đã chốt trước. Luôn báo cáo cả accuracy và
token; tăng utility không đồng nghĩa với cải thiện cả hai chỉ tiêu.

**RQ2:** lợi ích đến từ định tuyến, quyết định dừng hay công cụ tính toán?
So sánh full policy, ladder only, entry without escalation, one-shot router và
từng chiến lược cố định. Các policy dùng chung mẫu đầu ra để tránh nhầm dao động
sinh câu trả lời với hiệu quả của controller.

**RQ3:** kết quả thay đổi thế nào theo loại câu hỏi, ngân sách và generation
seed? Phân tích câu được cứu sau escalation, câu đúng bị làm sai, confidence cao
nhưng đáp án sai, và chi phí tăng mà không cải thiện đáp án.

Các giả thuyết đang chờ thực nghiệm. Thuật toán hiện tại tối ưu điểm cắt từng
bước khi giá trị downstream cố định; điều đó không bảo đảm tối ưu chung mọi
policy hoặc tổng quát tốt trên dữ liệu mới.

## Tính mới cần kiểm chứng

Hướng đóng góp dự kiến là đánh giá sự kết hợp của entry routing và stopping
dựa trên đầu ra trung gian, với một mô hình nhỏ cố định. Cần chỉ ra điều kiện
có ích và thất bại. CoT, voting, tool calling hay Bellman tự chúng không tạo
thành tuyên bố mới.

| Công trình cần đối chiếu | Quan hệ với đề tài |
| --- | --- |
| [Self-Consistency](https://arxiv.org/abs/2203.11171) | Lấy nhiều lời giải và bỏ phiếu đã có trước; dùng như thành phần đối chứng |
| [Tree of Thoughts](https://arxiv.org/abs/2305.10601) | Tìm kiếm qua các bước suy nghĩ; adapter hiện tại chỉ chọn giữa lời giải hoàn chỉnh |
| [Route to Reason](https://arxiv.org/abs/2505.19435) | Định tuyến mô hình và chiến lược; one-shot router trong repo là baseline nội bộ, chưa tái lập đầy đủ paper |
| [BEST-Route](https://arxiv.org/abs/2506.22716) | Định tuyến thích nghi cùng phân bổ tính toán; cần làm rõ phần trùng và khác trước khi chốt novelty |

Đây là danh sách khởi đầu, chưa phải tổng quan đầy đủ. Bản thảo phải đối chiếu
không gian hành động, tín hiệu quyết định, cách học policy và cách đo. Nếu phần
thuật toán đã có trước, thu hẹp đóng góp sang đánh giá thực nghiệm và giới hạn
trong bối cảnh đã chọn.

## Mốc hoàn thành & Tiến độ thực tế (Milestone Tracking)

`gen02_tune`, Run 11 và GapB đều là development đã lộ theo
`research_protocol.md`. Hoàn thành một artifact kỹ thuật không đồng nghĩa đã hoàn
thành bằng chứng cho bài báo. Stage 0 của chiến dịch Qwen/Meta-Reasoner chưa đổi.

| Mốc | Sản phẩm | Trạng thái | Điều kiện hoàn thành & Bằng chứng thực nghiệm |
| --- | --- | :---: | --- |
| **M0: Phạm vi & Prereg** | RQ, prior-art, protocols, decision rules | **ĐANG HOÀN THIỆN** | Có các decision rule P/signal/cascade, nhưng analyzer signal hiện chưa thực thi đúng repeated 5-fold CV ×20, baseline có completion length và `answer_first_lp`. Cần đồng bộ protocol--implementation trước khi gọi gate là đã chấm. |
| **M1: Dữ liệu chuẩn** | Dataset procedural có verifier độc lập | **ĐANG REVIEW** | `data/gen02_tune.json` v0.2.1 là pool development đã lộ, không phải held-out test. Bundle procedural mới đã tách development/test về cấu trúc nhưng human review, license/ownership, prior-exposure review và freeze publication còn chờ. |
| **M2: Pilot & Tín hiệu** | Pilot model thật, kiểm chứng confidence và verifier | **CHƯA QUA GATE** | Có trace model thật và verifier development. Kết luận confidence chưa chấm đúng prereg; Recall 100% của verifier chỉ trên fixture lỗi trong-sample và cần fresh development replication. |
| **M3: Thực nghiệm chính** | Sweep nhiều seed trên model/dataset đã freeze | **CHƯA CHẠY** | Run 11 đã đủ 571 bản ghi development nhưng dùng model session tuần tự, mixed sampling, token proxy thiếu input multi-call và SC có lỗi scoring semantics. Nó dùng để debug/thiết kế, không hoàn tất M3. |
| **M4: Bài báo & Cascade** | Policy evaluation, ablation và tổng hợp bằng chứng | **ĐANG LÀM** | Policy V hiện là replay trong-sample; GapB là paired exploratory (9 rescues, 5 harms, McNemar exact hai phía p≈0,424) và có selection-by-extractability. Chưa có claim confirmatory. |
| **M5: Minh họa RAT** | Demo luồng app tối thiểu | **ĐỂ SAU** | Chỉ thực hiện sau khi evidence pipeline và bản thảo nghiên cứu đạt gate. |

## Nhật ký Tiến trình Thực nghiệm (Chronological Execution Log)

| Thời điểm / Bước | Hành động & Mã nguồn | Kết quả & Phát hiện Khoa học chính | Artifacts & Commit |
| --- | --- | --- | --- |
| **Run 7 - Run 8** | Hợp nhất harness 6 arm, sửa render gap clue | Chuẩn hóa runner và analyzer legacy; `gen02` v0.2.1 chỉ được cố định cho chiến dịch development lịch sử, không phải publication dataset. | Commit `809e0ec`, Tag `harness-v1-run8` |
| **Stage P Audit** | Chạy đánh giá P trên DIRECT & COT | Quan sát development cho thấy nhiều lỗi lặp greedy ở Ordering/G24; dùng để hình thành arm và chẩn đoán tiếp theo, không phải kết quả held-out. | Commit `b37dbc5` (`prereg/decision_rule_P.md`) |
| **Run 11 Launch** | Chạy 6-arm sweep trên Qwen3-8B-4bit/Apple Silicon | Model được nạp một lần và tái sử dụng tuần tự. DIRECT/COT/ReAct/PAL greedy; SC sampling năm nhánh; `TOT` lịch sử sampling ba lời giải hoàn chỉnh rồi selector greedy. | `audit/run11_sweep_trace.jsonl` |
| **Prompt X & Y** | Phân tích confidence | Analyzer đã chạy exploratory AUROC và một 5-fold CV seed 0. Nó chưa tái lập repeated 5-fold ×20, thiếu `completion_tokens` trong baseline CV và thiếu `answer_first_lp`; chưa thể chấm PASS/FAIL prereg. | Commit `a8789d2`, `b4cc2a0` (`prereg/decision_rule_signal.md`) |
| **Prompt Z** | Lập trình deterministic verifiers | Có `arith_verifier` và `order_verifier` cùng unit tests. Recall/FPR đã báo chỉ thuộc fixture development in-sample; chưa có bằng chứng tổng quát trên fresh set. | Commit `0474647` |
| **Prompt AA** | Phân tích clue gap và hỗ trợ LaTeX | Quan sát trích xuất được 12/23 vi phạm gap và 0/33 before; mẫu số phụ thuộc response trích xuất được. Dùng làm chẩn đoán development, không gọi là phát hiện confirmatory. | Commit `ebd0d30`, `a024ea9` (`prereg/decision_rule_cascade.md`) |
| **Run 11 Done** | Hoàn thành 571 bản ghi development | Giữ ma trận accuracy như số thô. `TOT` là candidate selection chứ không phải tree search; proxy token thiếu prompt multi-call. SC còn lỗi: một nhánh length ép cả arm sai, ảnh hưởng 31/100 bản ghi có `parsed`. | `audit/run11_sweep_trace.jsonl` |
| **Prompt AB** | Paired wording ablation Style A/B | B đạt 18/31 so với A 14/31, với 9 rescues và 5 harms; McNemar exact hai phía p≈0,424. Tỷ lệ gap 12/23 so với 4/27 có selection-by-extractability. | Commit `52323fa`, Tag `harness-v1-gapB`, `audit/gapB_sweep_trace.jsonl` |
| **Cascade Policy V** | Replay policy đã khóa trên pool development | Legacy replay cho Arith +25,0 pp và Ordering +0,0 pp, nhưng verifier là in-sample, SC bị lỗi semantics và token proxy không phải full inference cost. Bỏ diễn giải oracle cost; cần fresh replication trước mọi claim. | `prereg/decision_rule_cascade.md` |


## Nhánh nghiên cứu và ứng dụng

Nhánh chính dùng câu hỏi tự chứa đủ dữ kiện, để quy lỗi cho chiến lược và
controller. Câu hỏi về quy chế trường cần nguồn và ngày hiệu lực; khi chưa có
thì không dùng làm ground truth thực nghiệm chính.

RAT được định hướng là trợ lý cá nhân theo hướng “second me”, hỗ trợ công việc
hằng ngày dựa trên ngữ cảnh, nhu cầu và cách làm việc của từng người. Định hướng
này phục vụ nhiều đối tượng người dùng. Đây là mục tiêu phát triển lâu dài;
trong đề tài NCKH hiện tại, RAT vẫn là ứng dụng minh họa, còn thí nghiệm và bài
báo là ưu tiên. Các khả năng cá nhân hóa cần được xây dựng và đánh giá riêng.

Tác vụ minh họa ban đầu của RAT là tìm file thật: tìm slide Calculus theo tên, môn,
nội dung, và cách hỏi tiếng Việt/Anh. Người dùng cần danh sách file liên quan,
không một tên file được chọn trước; chưa có lần tìm đúng được xác nhận làm mốc.
Kiểm tra liên kết document–chunk trước khi chỉnh xếp hạng (xem
[index_integrity.md](index_integrity.md)). Duyệt nhiều file và mức relevance
cho mỗi query, ưu tiên Precision@5, nDCG@10 và độ trễ; chỉ báo Recall@k khi nêu
rõ phạm vi tập relevant đã duyệt. Không trộn các metric này vào accuracy của
bài toán suy luận.

Demo tối thiểu: nhập yêu cầu → thấy vài kết quả với tên và vị trí rõ → mở đúng
file → có trạng thái không tìm thấy hoặc đề nghị làm rõ khi cần. Lịch học,
mascot, animation và thêm cửa sổ chưa nằm trên đường hoàn thành bài báo.

## Dàn ý bản thảo

1. **Giới thiệu:** câu hỏi phân bổ tính toán, phạm vi và đóng góp đã kiểm chứng.
2. **Nghiên cứu liên quan:** strategy routing, adaptive compute, stopping và uncertainty.
3. **Phương pháp:** entry predictor, ladder, confidence, utility và giới hạn thuật toán.
4. **Thực nghiệm:** nguồn dữ liệu, grouped split, model/prompt/version, baselines, chi phí và thống kê.
5. **Kết quả:** accuracy–token, paired differences, ablation, biến thiên theo seed; không điền số minh hoạ.
6. **Phân tích lỗi:** giới hạn confidence, escalation rescue/harm, overhead và tính tổng quát.
7. **Demo:** phần ngắn hoặc phụ lục, chỉ các khả năng đã chạy được.
8. **Kết luận/tái lập:** phát hiện có bằng chứng, artifact và câu hỏi còn mở.

## Bàn giao cho cộng tác viên/Claude

Đọc tài liệu này và `research_protocol.md` trước khi thêm tính năng. Thứ tự gần
nhất là sửa/retrospective-rescore semantics của SC, triển khai đúng analyzer
confidence đã preregister, chốt phạm vi token cost multi-call, rồi duyệt và freeze
dataset/model/prompt/seed trước pilot mới. Không lấy benchmark mô phỏng hoặc Run 11
development làm kết quả NCKH. Mỗi đề xuất tính năng cần giải thích nó kiểm chứng RQ
nào hoặc gỡ mốc nào.
