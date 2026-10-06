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

| Mốc | Sản phẩm | Trạng thái | Điều kiện hoàn thành & Bằng chứng thực nghiệm |
| --- | --- | :---: | --- |
| **M0: Phạm vi & Prereg** | RQ, prior-art, protocols, decision rules | **HOÀN THÀNH (100%)** | Đã commit các file prereg: `decision_rule_P.md`, `decision_rule_signal.md`, `decision_rule_cascade.md` trước khi đọc dữ liệu test. |
| **M1: Dữ liệu chuẩn** | Dataset procedural có verifier độc lập | **HOÀN THÀNH (100%)** | `data/gen02_tune.json` v0.2.1 (100 items), ground truth giải tích bằng toán, độc lập giữa các split. |
| **M2: Pilot & Tín hiệu** | Pilot model thật, kiểm chứng Logprob vs Verifier | **HOÀN THÀNH (100%)** | Đo logprob trên MLX (`run11_snapshot.jsonl`): Logprob confidence **FAIL** prereg; Hoàn thành Symbolic Verifier (`scripts/verifiers.py`) đạt **Recall 100%**. |
| **M3: Thực nghiệm chính** | Sweep độc lập 6 arms trên model thật | **HOÀN THÀNH (100%)** | Hoàn thành đủ 571/571 dòng run11: DIRECT 16.9%, COT 58.0%, SC 53.0%, TOT 68.0%, REACT 39.0%, PAL 40.0% (100% arith). ToT thống trị bài toán tìm kiếm (order 67.7%, g24 58.6%). |
| **M4: Bài báo & Cascade** | Cascade policy evaluation & Wording Ablation | **HOÀN THÀNH (80%)** | Đã hoàn tất đánh giá Policy V (prereg): Arith delta +25.0pp CI [+12.5; +40.0], Order delta +0.0pp CI [-12.9; +12.9]. Hoàn tất kiểm chứng Style A vs Style B (gapB): vi phạm clue gap giảm từ 52.2% xuống 14.8%, acc tăng +12.9pp. |
| **M5: Minh họa RAT** | Demo luồng app tối thiểu | **KẾ TIẾP** | Thực hiện sau khi hoàn tất bài báo NCKH. |

## Nhật ký Tiến trình Thực nghiệm (Chronological Execution Log)

| Thời điểm / Bước | Hành động & Mã nguồn | Kết quả & Phát hiện Khoa học chính | Artifacts & Commit |
| --- | --- | --- | --- |
| **Run 7 - Run 8** | Hợp nhất harness 6 arm, sửa render gap clue | Chuẩn hóa `scripts/run_sweep.py` và `scripts/analyze_oracle.py`, cố định tập dữ liệu `gen02` v0.2.1. | Commit `809e0ec`, Tag `harness-v1-run8` |
| **Stage P Audit** | Chạy đánh giá P sweep trên DIRECT & COT | arith PASS tiêu chí prereg; order & g24 sụp đổ do vòng lặp greedy ("Try... Nope"). Xác nhận cần các arm tìm kiếm mạnh hơn. | Commit `b37dbc5` (`prereg/decision_rule_P.md`) |
| **Run 11 Launch** | Khởi chạy 6-arm sweep (`DIRECT, COT, SC, TOT, REACT, PAL`) trên GPU Apple Silicon | Đo đạc đầy đủ logprob và completion tokens dưới điều kiện kiểm soát ngặt nghèo (cold-start, deterministic greedy). | Background PID 23672, `audit/run11_sweep_trace.jsonl` |
| **Prompt X & Y** | Phân tích hiệu chuẩn Logprob (Repeated 5-fold CV $\times 20$) | **Kết quả âm tính có giá trị (Negative Finding)**: Logprob không vượt qua baseline (+0.05 AUROC với CI > 0). Order rơi vào dải nhiễu 0.23–0.31. **FAIL prereg**, quyết định dừng fit ngưỡng logprob, chuyển sang Symbolic Verifier. | Commit `a8789d2`, `b4cc2a0` (`prereg/decision_rule_signal.md`) |
| **Prompt Z** | Lập trình Deterministic Program Verifiers | Hoàn thành `scripts/verifiers.py`: `arith_verifier` và `order_verifier`. Đạt **Recall 100%** trên mẫu sai; FPR = 0% trên arith, 21.4% trên order (bắt đúng 3 ca model suy luận vi phạm clue nhưng đoán bừa trúng đáp án). 12 unit test PASS. | Commit `0474647` |
| **Prompt AA** | Bóc tách cơ chế lỗi Clue Gap & nâng cấp LaTeX Verifier | **Phát hiện đột phá**: 12/23 (52.2%) clue gap bị vi phạm so với 0/33 (0.0%) clue before. Bổ sung hỗ trợ LaTeX (`\times`, `\div`, `\cdot`) cho `arith_verifier`, 18 unit tests PASS. Khóa prereg cascade policy. | Commit `ebd0d30`, `a024ea9` (`prereg/decision_rule_cascade.md`) |
| **Run 11 Done** | Hoàn thành sweep 571/571 dòng trên GPU | Đủ 6 arms: TOT dẫn đầu tổng thể (68.0%) và vượt trội trên Order (67.7% vs COT 45.2%). PAL đạt 100% arith với token cực thấp (194 tok). SC (53.0%) thua COT (58.0%) do khuếch đại bẫy greedy. | `reasoning-run11/audit/run11_sweep_trace.jsonl` |
| **Prompt AB** | Thực nghiệm đối chứng cách diễn đạt (Style A vs Style B) | **Xác nhận giả thuyết Wording**: Tỷ lệ vi phạm clue gap giảm ngoạn mục từ 52.2% (12/23) xuống **14.8% (4/27)** (đạt tiêu chí $\le 26\%$). Tỷ lệ dừng do cạn token giảm từ 10 xuống 3; accuracy tổng thể tăng từ 45.2% lên **58.1% (+12.9pp)**. | Commit `52323fa`, Tag `harness-v1-gapB`, `reasoning-gapB/audit/gapB_sweep_trace.jsonl` |
| **Cascade Policy V** | Đánh giá chính sách phân tầng theo prereg | **Arith**: delta +25.0pp, 95% Cluster-Bootstrap CI [+12.5pp; +40.0pp]; tuy nhiên ratio token V/PAL = 1.91 (PAL vốn rẻ hơn COT nên chỉ cần Entry Router, không cần Cascade). **Order**: delta +0.0pp (SC kém hơn COT, ToT mới là cứu cánh). | `prereg/decision_rule_cascade.md` |


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
6. **Phân tích lỗi:** confidence sai, escalation gây hại, overhead và tính tổng quát.
7. **Demo:** phần ngắn hoặc phụ lục, chỉ các khả năng đã chạy được.
8. **Kết luận/tái lập:** phát hiện có bằng chứng, artifact và câu hỏi còn mở.

## Bàn giao cho cộng tác viên/Claude

Đọc tài liệu này và `research_protocol.md` trước khi thêm tính năng. Việc tiếp
theo là duyệt câu hỏi/đáp án và nguồn dataset, cố định split/model snapshot,
rồi chạy pilot có log. Không lấy benchmark mô phỏng làm kết quả NCKH. Mỗi đề
xuất tính năng cần giải thích nó kiểm chứng RQ nào hoặc gỡ mốc nào.
