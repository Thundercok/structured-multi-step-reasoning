# Survey NCKH: Điều phối chiến lược suy luận và quyết định dừng theo ngân sách

Phạm vi: mô hình ngôn ngữ nhỏ cố định, ưu tiên Qwen3-8B; phục vụ xét duyệt đề cương và lựa chọn hướng nghiên cứu.

Ngày đối chiếu nguồn: 13/10/2026 (giờ Việt Nam). Bản tổng quan định hướng, không phải systematic review và không xác nhận tính mới.

Danh mục có 57 tài liệu: 47 bản được trích thuộc 2024–2026, trong đó 14 thuộc 2026; 10 tài liệu 2022–2023 được giữ vì vai trò nền tảng hoặc bản cập nhật liên quan. Bài mới nhất trong danh mục nộp ngày 30/09/2026.

## 1. Trả lời nhanh các câu hỏi của giảng viên

Đề tài đã được nghiên cứu đến đâu? Các thành phần chọn reasoning mode, định tuyến model/strategy, phân bổ số mẫu, dừng chuỗi theo stability/confidence và dùng verifier đều đã có prior art. Các bài 2025–2026 còn kết hợp nhiều tín hiệu và học hành vi dừng. Vì vậy, chỉ triển khai CoT/PAL, voting, Bellman hoặc ghép routing với stopping không đủ để tuyên bố thuật toán mới.

Có bao nhiêu phương pháp chủ đạo? Với câu hỏi của nhóm, tài liệu này dùng sáu họ phương pháp theo cơ chế can thiệp. Đây là taxonomy làm việc; các họ có thể chồng lấn, không phải con số được toàn lĩnh vực thống nhất. Calibration, harm và đo chi phí là các trục đánh giá đi xuyên qua các họ.

Nên đi hướng nào? Khuyến nghị giữ model nền cố định, đánh giá khi nào tín hiệu sau lời giải đầu thực sự dự đoán được lợi ích ròng của chạy thêm. Ưu tiên nghiên cứu hẹp về verification/agreement hoặc restart trước khi mở rộng full router. Đóng góp dự kiến là bằng chứng thực nghiệm và điều kiện thất bại có thể tái lập; tính mới vẫn cần đối chiếu và thực nghiệm.

## 2. Sáu họ phương pháp và thuật toán tiêu biểu

| Họ phương pháp | Can thiệp chính | Thuật toán/model tiêu biểu | Liên hệ với nhóm |
| --- | --- | --- | --- |
| 1. Entry routing | Chọn đường giải từ câu hỏi trước sinh | RTR, BEST-Route, AdoT, AdaptThink, Thinkless, ODAR | Baseline entry-only; mode native |
| 2. Adaptive sampling | Chọn số lời giải và lúc ngừng lấy mẫu | ASC, ESC, DSC, RASC, CGES, ReASC, Bayesian stopping | SC cố định và agreement gate |
| 3. Budget/within-chain stopping | Giảm hoặc kéo dài một trace đang sinh | TALE, s1, CoD, REFRAIN, Settle, SABER, Certaindex | CoT cap, CONT, restart khác nhau |
| 4. Structured search | Mở rộng/chấm các state trung gian | ToT, RAP/MCTS, GoT | Không gọi candidate selection là ToT |
| 5. Tool/verification | Thực thi, kiểm tra, rồi chọn hoặc sửa | PAL, PoT, ReAct, CRITIC, PRM, Math-Shepherd, SSV | Tách tool gain khỏi controller gain |
| 6. Learned efficient reasoning | Học mode, stop action hoặc latent thoughts | AdaptThink/AutoThink/Thinkless, AdapThink, Coconut | Khác phạm vi frozen model |

Ba thời điểm cần phân biệt: entry routing nhìn câu hỏi; inter-response stopping nhìn một hay nhiều lời giải hoàn chỉnh; within-chain stopping nhìn prefix/state đang sinh. Một controller chọn strategy tiếp theo không mặc nhiên là thuật toán cắt CoT theo token.

## 3. Tìm và đọc tài liệu như thế nào

Nguồn ưu tiên: trang tác giả trên arXiv, ACL Anthology, proceedings NeurIPS và OpenReview. Truy vấn gồm adaptive reasoning/strategy routing, adaptive self-consistency/optimal stopping, token-budget/answer convergence, tool verification/self-correction và uncertainty/budget-aware evaluation; truy thêm từ reference của các bài sát đề tài.

Phạm vi thời gian ưu tiên là 13/10/2023–13/10/2026. Các công trình nền ngoài khoảng này được ghi rõ; thống kê năm ở đầu tài liệu dựa trên bản được trích, không chỉ năm đăng preprint đầu tiên. Một paper chỉ có một mục, kể cả khi có cả preprint và bản hội nghị.

Mỗi mục có nội dung, phương pháp, kết quả tác giả báo cáo, giới hạn và mức đọc. Phần lớn là đọc abstract/trang xuất bản; một số bài sát đề tài đã đối chiếu thêm phương pháp, conclusion hoặc limitations. Không có thực nghiệm nào trong danh mục được nhóm tái lập trong lần survey này.

Các phần trăm tiết kiệm không dùng chung mẫu số: có bài đo số calls/samples, có bài đo generated tokens, FLOPs, USD hay latency hệ thống. Không xếp hạng trực tiếp bằng các số đó. Các kết quả định tính được giữ định tính khi abstract không cung cấp số hoặc không đủ thông tin để diễn giải số.

Nhãn A = ưu tiên đối chiếu khi viết đề cương; B = bổ sung hoặc mở rộng. Venue/status là thông tin nguồn hiển thị, không suy ra paper đã phản biện chỉ vì có arXiv. Các câu về hướng nghiên cứu dưới đây là suy luận tổng hợp của người khảo sát.

## 4. Bảng prior-art sát câu hỏi nghiên cứu

| Nguồn trong danh mục | Hành động/tín hiệu | Điểm đã có trước | Phần nhóm cần làm rõ |
| --- | --- | --- | --- |
| R01 — RTR | Query → model + strategy | Có cả routing strategy trong một model | Post-answer escalation; tránh test-loss tuning |
| R02 — BEST-Route | Query → model + n; proxy reward | Joint routing + compute allocation | Exact-answer quality; frozen-model path |
| R03 / S03 | Difficulty + benefit/budget | Input-adaptive compute; prior + posterior | Không chỉ gọi là ghép hai thành phần |
| S01 / S02 | Answer counts/consistency | Dừng sampling khi đủ đồng thuận | Agreement có dự đoán rescue/harm? |
| S06 — ReASC | Single-answer confidence rồi weighted counts | Gate một mẫu + tiếp tục sampling | Overconfidence; clean calibration |
| S07 / S08 | Posterior/reward và chi phí | Optimal stopping có mô hình lý thuyết | Mode/reward ≠ correctness chung |
| C02 — Manvi et al. | Output/prefix → restart benefit | Dự đoán có nên lấy lời giải khác | Frozen weights; matched CONT/restart |
| C12 / C13 | Stop score hoặc branch stability | Learned stop / training-free early exit | Training/access/overhead khác nhau |
| V07 — SSV | Weak check → accept/reject/strong check | Điều phối các verifier có error control | Gold/strong signal và chi phí thật |
| E05 / H01 | Budget match và prefix correctness | Compute confound; harmful overthinking | Tách rescue, harm và oracle diagnostic |

Khác phạm vi không tự tạo ra novelty. “Dùng Qwen3-8B trên Mac”, “giữ một model” hoặc “thêm giao diện agent” có thể là bối cảnh thực nghiệm nhưng chưa đủ là đóng góp khoa học. Nếu thuật toán đã có, một replication/benchmark hẹp vẫn có giá trị khi giải thích được cơ chế, điều kiện có ích và giới hạn.

Lưu ý tái lập cụ thể: RTR v1 ghi chọn dừng training theo test loss; nên dùng development validation riêng và gọi kết quả là bản tái lập có điều chỉnh protocol. ReASC có chế độ không nhãn dùng confidence statistics của test; với protocol repo, ưu tiên offline calibration trên split riêng và ghi rõ khác biệt với chế độ transductive. Đây là lưu ý về thiết lập, không phải kết luận toàn bộ kết quả của các bài là sai.

## 5. Hướng nghiên cứu đề xuất để giảng viên duyệt

### 5.1. Phạm vi đề xuất

Tên làm việc có thể giữ: Điều phối chiến lược suy luận và quyết định dừng theo ngân sách cho mô hình ngôn ngữ nhỏ. RQ cụ thể đề xuất: Trên Qwen3-8B cố định, thông tin kiểm chứng/đồng thuận sau lời giải đầu có giúp chọn chạy thêm để cải thiện utility trên dữ liệu chưa dùng để fit, so với entry-only và lịch chạy cố định ở ngân sách tương đương?

Lý do chọn: tận dụng pipeline có sẵn, không cần huấn luyện lại model nền, đáp án có thể kiểm chứng, và cho phép kết quả âm có ý nghĩa. Không giả định confidence logprob sẽ hữu ích; không giả định verifier luôn thắng agreement. Giữ phạm vi câu hỏi tự chứa đủ dữ kiện, tách demo RAT khỏi nghiên cứu chính.

### 5.2. Ba lựa chọn và thứ tự khả thi

- Hướng A — đánh giá tín hiệu điều phối: cố định model/recipe, so agreement, verifier và predictor của lợi ích chạy thêm. Đích là accuracy–cost, rescue/harm và mức độ tổng quát. Đây là hướng phù hợp nhất với mục tiêu controller hiện tại, sau khi qua các gate.
- Hướng B — nghiên cứu cơ chế hẹp: CoT continuation so restart có budget tương đương, hoặc ordering witness/certificate so full verification. Đã có protocol development trong repo; dùng để kiểm tra giả định trước khi mở rộng A.
- Hướng C — học native stop/mode bằng RL/SFT hoặc latent reasoning: đối chiếu AdaptThink/Settle/Coconut. Cần tài nguyên training và thay đổi model; chưa phù hợp làm phạm vi đầu với model nền cố định.

Khuyến nghị hiện tại là B để củng cố evidence, rồi chỉ mở rộng A nếu dữ liệu fresh cho thấy tín hiệu thực sự có lợi. Đây là đề xuất để thảo luận với GVHD, không thay thế preregistration, không mở campaign mới và không thay đổi Stage 0.

### 5.3. Đóng góp dự kiến và claim cần tránh

- Đóng góp dự kiến: đánh giá ghép entry và quyết định chạy thêm trong một setting đã freeze; ablation cho nguồn lợi ích; phân tích điều kiện rescue/harm; artifacts tái lập và phép đo chi phí được khai báo rõ.
- Cần kiểm chứng: tín hiệu dự đoán correctness có dự đoán được marginal benefit của escalation hay không. Một câu sai vẫn có thể không được strategy tiếp theo cứu; câu đúng có thể bị thay bằng đáp án sai.
- Không viết trước khi có evidence: thuật toán đầu tiên, tối ưu toàn cục, model nhỏ luôn vượt model lớn, giảm inference cost/latency chỉ từ output tokens, hoặc verifier đạt 100% tổng quát từ fixture development.

## 6. Thiết kế đánh giá và các đối chứng cần có

- Freeze dữ liệu/grouped splits, checkpoint/quantization/template, prompt, cap, sampling, seed, lambda và primary comparisons trước khi xem test. Bản dịch/paraphrase cùng câu gốc phải nằm cùng group/split.
- Đối chứng: từng strategy cố định; SC cùng ngân sách; entry-only router; ladder-only; entry không escalation; full controller. Phân biệt implement theo ý tưởng và tái lập paper gốc.
- Native Qwen3 thinking/non-thinking là baseline cần kiểm tra bằng chat template. Nếu DIRECT và CoT khác hard cap, ghi đó là hai recipe; muốn quy tác động cho instruction phải thêm so sánh budget tương đương.
- Fit predictor trên train; fit thresholds trên calibration; dùng validation development bổ sung nếu cần chọn hyperparameters. Không fit vào test label, không chọn lambda thắng từ test sweep.
- Đo accuracy/utility cùng tokens, số calls, escalation và invalid/truncated rate. Giữ metric generated-token của protocol hiện hành; đo thêm prompt + completion của mọi call, evaluator/tool/router overhead nếu muốn nói về full inference cost.
- Replay dùng chung recorded outputs chỉ hợp lệ khi mỗi strategy nhận query gốc và randomness không phụ thuộc history. Correction dùng answer cũ, adaptive prefix branching hoặc CONT không được suy ra từ replay các strategy độc lập.
- Online latency phải đo riêng trên hardware/library/batch đã pin, nêu warm/cold load và cache. Tổng replay strategy times không phải latency online.
- Paired analysis theo original groups, giữ variants trong group; nhiều generation seeds vẫn là lặp trên cùng câu. Dùng protocol bootstrap hiện có, nêu CI conditional trên policy/seed và không biến seed count thành số câu độc lập.
- Ordering: bắt buộc query-only symbolic baseline khi verifier đã giải uniqueness. Phân biệt witness-only checking với exact solving; tính cả fallback và invalid certificates.
- Trước main study: review gold/license/exposure, sửa scoring semantics và token accounting, kiểm model snapshot, đánh giá lại tín hiệu trên fresh development, rồi mới đáp ứng Stage 0 và freeze.

### 6.1. Rescue, harm và sự ổn định

Báo cáo số escalation cứu initial wrong → final correct và số escalation làm initial correct → final wrong. Tính rescue rate trên các câu initially wrong đã escalation; harm rate trên các câu initially correct đã escalation; báo cả counts/mẫu số và chênh lệch accuracy trên toàn bộ test. Không chỉ trình bày một vài ví dụ thành công.

Theo dõi riêng: answer stable nhưng sai; confidence cao nhưng sai; nhiều samples cùng sai; witness sai nhưng answer đúng; tool chạy thành công nhưng code hiểu sai đề; chi phí tăng mà answer không đổi; parse/cap lỗi. First-correct-prefix hoặc gold-selected path chỉ là offline oracle diagnostic, không dùng làm decision rule triển khai.

## 7. Đối chiếu với tình trạng repo ngày khảo sát

Nguồn nội bộ đã đọc: docs/research_plan.md, docs/research_protocol.md và docs/related_work.md trong checkout canonical Thundercok/nesy-docai, hiện resolve tới thư mục multi-step-structured-reasoning. Các kết luận sau phản ánh trạng thái ghi trong tài liệu, không phải audit lại toàn bộ run artifacts.

- Ưu tiên của project là bài NCKH và pipeline tái lập; RAT là demo thứ cấp. DocAI integration đang được hoãn.
- Stage 0 Qwen/Meta-Reasoner chưa được coi là qua. Việc có infrastructure, synthetic smoke hay survey này không làm thay đổi gate.
- Confidence gate được research plan ghi FAIL; đây là căn cứ để kiểm tra tín hiệu bổ sung, không chứng minh verifier là giải pháp duy nhất.
- Run 11, gen02_tune và GapB là development đã lộ. Các số pilot trong email và các replay in-sample không phải held-out confirmatory evidence.
- TOT legacy là chọn giữa các candidates hoàn chỉnh; SC legacy có scoring/cap issue; token proxy thiếu input multi-call. Cần gắn nhãn đúng khi viết related work/kết quả.
- Ordering certificate và CoT restart có protocol riêng. Tài liệu survey không chạy model, fit policy, mở test hay chỉnh research harness.

## 8. Thứ tự đọc sâu và chuẩn bị buổi xét duyệt

Lượt 1 — prior-art trực tiếp: R01, R02, S03, S06, S07, V07. Với mỗi bài, vẽ state/action, đánh dấu thông tin biết trước và sau sinh, loại nhãn/calibration, mục tiêu tối ưu và đơn vị chi phí.

Lượt 2 — nhánh restart/stop: C02, C06, C12, C13 và H01. Đối chiếu restart/continue, stability/correctness, frozen weights/training và overhead. Lượt 3 — thiết kế đánh giá: E01, E02, E05, E06 và B01.

Khi đọc Proposed Model, dùng mẫu: input → features/state → actions → decision rule → training/calibration → output selection → stopping → costs. Sau đó ghi assumptions, benchmarks, baselines, ablations, code/model/data link và điều kiện không tái lập được.

### 8.1. Câu trả lời ngắn có thể trình bày trước hội đồng

- Nhóm nghiên cứu gì? Bộ điều phối trên một LLM có sẵn: chọn recipe ban đầu và quyết định có chạy thêm dựa trên output vừa có, với ngân sách giới hạn.
- Vì sao không luôn CoT/PAL/SC? Lợi ích thay đổi theo câu/model và thêm compute có thể không cứu được lỗi, hoặc làm sai câu đã đúng. Cần đối chứng cùng budget để kiểm tra thay vì giả định.
- Điểm mới là gì? Hiện chưa khẳng định mới về thuật toán. Đóng góp dự kiến là đánh giá có kiểm soát và failure analysis của tín hiệu/decision trong setting đã chọn; chỉ chốt claim sau prior-art sâu và kết quả reviewed.
- Nhóm đã có kết quả chưa? Có development/pilot để debug và hình thành giả thuyết, chưa có bằng chứng confirmatory cho full controller. Synthetic tests kiểm phần mềm, không đo model quality.
- Nếu controller không thắng? Báo kết quả âm, phân tích tín hiệu, rescue/harm và overhead; đó vẫn là kết quả NCKH khi thiết kế hợp lệ và tái lập được.

## 9. Danh mục 57 tài liệu và ghi chú từng bài

### Định tuyến trước khi sinh và chọn reasoning mode

#### [R01] [Route to Reason: Adaptive Routing for LLM and Reasoning Strategy Selection](https://arxiv.org/abs/2505.19435) (2025)

Zhihong Pan et al. — arXiv v1; metadata ghi WWW 2026. Ưu tiên A.

- **Làm gì:** Chọn mô hình và cách suy luận theo từng câu hỏi.
- **Phương pháp:** Embedding cho model/strategy; MLP dự đoán độ đúng và output token, rồi chọn cặp theo ngân sách.
- **Kết quả tác giả báo cáo:** Báo cáo token giảm hơn 60% và độ đúng cao hơn mô hình đơn mạnh nhất trong thiết lập của bài.
- **Giới hạn/liên hệ:** Đã có ablation định tuyến nhiều strategy trên một model. V1 dùng test loss để early stopping router (§3.1); cần audit trước tái lập.
- **Đã đọc/đối chiếu:** Abstract; phương pháp/thiết lập §2–3; Discussion; Appendix A. Chưa tái lập thực nghiệm.

#### [R02] [BEST-Route: Adaptive LLM Routing with Test-Time Optimal Compute](https://arxiv.org/abs/2506.22716) (2025)

Dujian Ding et al. — ICML 2025; nguồn arXiv v1. Ưu tiên A.

- **Làm gì:** Kết hợp chọn model với số mẫu cần sinh.
- **Phương pháp:** Multi-head router chọn model và n; proxy reward model chọn best-of-n.
- **Kết quả tác giả báo cáo:** Báo cáo chi phí giảm tới 60%, chất lượng giảm dưới 1% ở các thiết lập chính.
- **Giới hạn/liên hệ:** Chất lượng chủ yếu theo reward score; chi phí USD tính giá input/output của bài. Không phải accuracy GSM8K hay stopping sau mỗi đáp án.
- **Đã đọc/đối chiếu:** Abstract; §3–4; §5.4; Limitations; Conclusion. Chưa tái lập thực nghiệm.

#### [R03] [Learning How Hard to Think: Input-Adaptive Allocation of LM Computation](https://arxiv.org/abs/2410.04707) (2024)

Mehul Damani et al. — arXiv 2024; có bản ICLR 2025. Ưu tiên A.

- **Làm gì:** Phân bổ compute vào câu có khả năng hưởng lợi.
- **Phương pháp:** Học phân phối reward theo input và budget; adaptive best-of-k và routing giữa decoder đắt/rẻ.
- **Kết quả tác giả báo cáo:** Giảm compute tới 50% ở chất lượng tương đương, hoặc cải thiện chất lượng tới 10% với budget cố định.
- **Giới hạn/liên hệ:** Độ khó phải gắn với lợi ích bổ sung, không chỉ câu dài hay khó. Cần dữ liệu huấn luyện bộ dự đoán.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R04] [Adaption-of-Thought: Learning Question Difficulty Improves Large Language Models for Reasoning](https://aclanthology.org/2024.emnlp-main.313/) (2024)

Mayi Xu et al. — EMNLP 2024. Ưu tiên B.

- **Làm gì:** Điều chỉnh prompting theo độ khó câu hỏi.
- **Phương pháp:** AdoT đo difficulty, chọn bộ demonstration và retrieval phù hợp.
- **Kết quả tác giả báo cáo:** Abstract báo cải thiện tuyệt đối tới 5,5 điểm ở arithmetic, 7,4 ở symbolic và 2,3 ở commonsense.
- **Giới hạn/liên hệ:** Adaptive demonstration khác chọn DIRECT/CoT/PAL sau khi đã có một lời giải.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R05] [AdaptThink: Reasoning Models Can Learn When to Think](https://aclanthology.org/2025.emnlp-main.184/) (2025)

Jiajie Zhang et al. — EMNLP 2025. Ưu tiên A.

- **Làm gì:** Học khi nào dùng Thinking hoặc NoThinking.
- **Phương pháp:** RL với mục tiêu ràng buộc chất lượng và importance sampling cân bằng hai mode.
- **Kết quả tác giả báo cáo:** Trên ba tập toán, abstract báo response ngắn hơn 53% và accuracy tăng 2,4% với R1-Distill-Qwen-1.5B.
- **Giới hạn/liên hệ:** Có thay đổi trọng số model nền; không phải controller bên ngoài giữ model cố định.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R06] [Learning When to Think: Shaping Adaptive Reasoning in R1-Style Models via Multi-Stage RL](https://arxiv.org/abs/2505.10832) (2025)

Songjun Tu et al. — arXiv 2505.10832. Ưu tiên B.

- **Làm gì:** Giúp model tự chọn có suy luận tường minh hay không.
- **Phương pháp:** AutoThink: RL nhiều giai đoạn với reward shaping cho hai mode.
- **Kết quả tác giả báo cáo:** Abstract hiện hành báo accuracy tương đối tăng 6,4% và token giảm 52% trên R1-Distill-Qwen-1.5B.
- **Giới hạn/liên hệ:** Có training; số tăng tương đối không được đổi thành điểm phần trăm.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R07] [Thinkless: LLM Learns When to Think](https://arxiv.org/abs/2505.13379) (2025)

Gongfan Fang et al. — arXiv 2505.13379. Ưu tiên B.

- **Làm gì:** Chọn short-form hoặc long-form reasoning.
- **Phương pháp:** Control token <short>/<think>; DeGRPO tách loss chọn mode và loss sinh đáp án.
- **Kết quả tác giả báo cáo:** Giảm sử dụng long-chain thinking 50–90% trên các benchmark được thử.
- **Giới hạn/liên hệ:** Tỉ lệ chọn long-think khác tỉ lệ tổng token tiết kiệm; cần huấn luyện trọng số.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R08] [T²: An Adaptive Test-Time Scaling Strategy for Contextual Question Answering](https://aclanthology.org/2025.emnlp-main.185/) (2025)

Zhengyi Zhao et al. — EMNLP 2025. Ưu tiên B.

- **Làm gì:** Chọn độ sâu suy luận trong QA có ngữ cảnh.
- **Phương pháp:** Think-to-Think phân rã cấu trúc, tạo ví dụ tương tự, đánh giá strategy và áp dụng lại.
- **Kết quả tác giả báo cáo:** Trên bảy benchmark CQA, báo độ đúng cao hơn baseline và overhead giảm tới 25,2%.
- **Giới hạn/liên hệ:** Cần tính các call tạo/đánh giá ví dụ; không thể chỉ đếm lời giải cuối.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R09] [ODAR: Principled Adaptive Routing for LLM Reasoning via Active Inference](https://arxiv.org/abs/2602.23681) (2026)

Siyuan Ma et al. — arXiv 2602.23681. Ưu tiên A.

- **Làm gì:** Phân bổ reasoning giữa Fast Agent và Slow Agent.
- **Phương pháp:** Difficulty estimator theo active inference; fusion theo free energy và varentropy.
- **Kết quả tác giả báo cáo:** Báo cải thiện frontier qua 23 benchmark; giảm compute 82% ở thiết lập open-source Llama 4 + DeepSeek.
- **Giới hạn/liên hệ:** Agent/model khác nhau và số liệu do tác giả báo; không suy rộng sang Qwen3-8B đơn.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [R10] [Think When Needed: Model-Aware Reasoning Routing for LLM-based Ranking](https://arxiv.org/abs/2601.18146) (2026)

Huizhong Guo et al. — arXiv v2; metadata ghi accepted SIGIR 2026. Ưu tiên B.

- **Làm gì:** Chọn Think/Non-Think trước generation trong ranking.
- **Phương pháp:** Router head dùng feature ứng viên và diagnostic checklist; chọn policy trên validation Pareto frontier.
- **Kết quả tác giả báo cáo:** Ví dụ MovieLens/Qwen3-4B: NDCG@10 tăng 6,3%, token giảm 49,5%.
- **Giới hạn/liên hệ:** Đây là ranking metric, không phải độ đúng toán; chỉ dùng làm bằng chứng phạm vi liên quan.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Lấy mẫu nhiều lời giải và dừng sampling thích nghi

#### [S01] [Let’s Sample Step by Step: Adaptive-Consistency for Efficient Reasoning and Coding with LLMs](https://aclanthology.org/2023.emnlp-main.761/) (2023)

Pranjal Aggarwal et al. — EMNLP 2023, tháng 12. Ưu tiên A.

- **Làm gì:** Tránh dùng số mẫu Self-Consistency cố định.
- **Phương pháp:** Adaptive-Consistency dừng dựa trên đồng thuận tích lũy của các đáp án.
- **Kết quả tác giả báo cáo:** Qua 17 tập và ba LLM, giảm sample budget tới 7,9 lần; accuracy giảm trung bình dưới 0,1%.
- **Giới hạn/liên hệ:** Là baseline trực tiếp cho dừng giữa các lời giải; đồng thuận không chứng minh đáp án đúng.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [S02] [Escape Sky-high Cost: Early-stopping Self-Consistency for Multi-step Reasoning](https://arxiv.org/abs/2401.10480) (2024)

Yiwei Li et al. — arXiv 2401.10480; bản ICLR 2024. Ưu tiên A.

- **Làm gì:** Giảm số lượt sampling cho CoT.
- **Phương pháp:** ESC dùng tiêu chí dừng dựa trên các đáp án đã lấy mẫu; có cơ chế điều khiển quality–cost.
- **Kết quả tác giả báo cáo:** Số mẫu giảm 80,1% trên GSM8K và 33,8% trên MATH, với performance tương đương trong bài.
- **Giới hạn/liên hệ:** Tỉ lệ giảm số mẫu phụ thuộc tập/model; không tự bằng tỉ lệ giảm token/latency.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [S03] [Make Every Penny Count: Difficulty-Adaptive Self-Consistency for Cost-Efficient Reasoning](https://aclanthology.org/2025.findings-naacl.383/) (2025)

Xinglin Wang et al. — Findings of NAACL 2025. Ưu tiên A.

- **Làm gì:** Kết hợp độ khó trước sinh và evidence sau sinh.
- **Phương pháp:** DSC dùng thông tin difficulty của batch ở cả prior và posterior để phân bổ sampling.
- **Kết quả tác giả báo cáo:** Trên sáu benchmark arithmetic/commonsense/symbolic, cost thấp hơn ASC/ESC ở performance tương đương.
- **Giới hạn/liên hệ:** Đã kết hợp tín hiệu trước/sau sinh; cần đối chiếu kỹ khi nói entry + stopping là mới.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [S04] [Reasoning Aware Self-Consistency: Leveraging Reasoning Paths for Efficient LLM Sampling](https://aclanthology.org/2025.naacl-long.184/) (2025)

Guangya Wan et al. — NAACL 2025. Ưu tiên B.

- **Làm gì:** Dừng sampling và chọn rationale tốt hơn.
- **Phương pháp:** RASC đánh giá cả chất lượng đường suy luận lẫn độ nhất quán đáp án; weighted voting và criteria-based stopping.
- **Kết quả tác giả báo cáo:** Abstract báo giảm số mẫu khoảng 70% trong khi giữ accuracy.
- **Giới hạn/liên hệ:** Scoring rationale tạo overhead; kết quả phụ thuộc chất lượng bộ đánh giá.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [S05] [CGES: Confidence-Guided Early Stopping for Efficient and Accurate Self-Consistency](https://arxiv.org/abs/2511.02603) (2025)

Ehsan Aghazadeh et al. — arXiv 2511.02603. Ưu tiên A.

- **Làm gì:** Kết hợp confidence với posterior của ứng viên đáp án.
- **Phương pháp:** Bayesian update bằng token-probability hoặc reward-model confidence; dừng khi posterior vượt ngưỡng.
- **Kết quả tác giả báo cáo:** Qua năm benchmark, calls giảm khoảng 69% (16,0 → 4,9), accuracy cách SC 0,06 điểm.
- **Giới hạn/liên hệ:** Bảo đảm lý thuyết có điều kiện về tín hiệu; confidence của repo chưa qua gate.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [S06] [Reliability-Aware Adaptive Self-Consistency for Efficient Sampling in LLM Reasoning](https://aclanthology.org/2026.findings-acl.1085/) (2026)

Junseok Kim et al. — Findings of ACL 2026. Ưu tiên A.

- **Làm gì:** Dừng khi đã đủ evidence, có trọng số reliability.
- **Phương pháp:** ReASC: gate một mẫu trước, sau đó confidence-weighted Beta accumulation; có offline calibration và GMM không nhãn.
- **Kết quả tác giả báo cáo:** Báo cost giảm tới 70% so với SC ở GSM8K/Gemma-3-4B-it; thử năm model, bốn tập.
- **Giới hạn/liên hệ:** Limitations nêu overconfidence hệ thống. Chế độ online dùng statistics của toàn bộ test; với protocol repo nên dùng calibration riêng.
- **Đã đọc/đối chiếu:** Abstract; §4/Algorithm 1; §6/Limitations. Chưa tái lập thực nghiệm.

#### [S07] [Optimal Bayesian Stopping for Efficient Inference of Consistent LLM Answers](https://arxiv.org/abs/2602.05395) (2026)

Jingkai Huang, Will Ma, Zhengyuan Zhou — arXiv v2, camera-ready ICML 2026. Ưu tiên A.

- **Làm gì:** Tìm đáp án modal với ít lượt lấy mẫu hơn.
- **Phương pháp:** Bayesian prior; L-aggregated policy chỉ giữ L−1 answer counts phổ biến; chứng minh L=3 đủ cho asymptotic optimality.
- **Kết quả tác giả báo cáo:** Báo số calls giảm tới 50% ở answer accuracy tương tự.
- **Giới hạn/liên hệ:** Đích lý thuyết là mode của phân phối đáp án; mode có thể sai. Optimality trong mô hình của bài, không cho mọi controller.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [S08] [Optimal Stopping vs Best-of-N for Inference Time Optimization](https://arxiv.org/abs/2510.01394) (2025)

Yusuf Kalayci, Vinod Raman, Shaddin Dughmi — arXiv 2510.01394. Ưu tiên A.

- **Làm gì:** Dừng generation khi lợi ích kỳ vọng không bù chi phí.
- **Phương pháp:** Pandora’s Box; UCB học phân phối reward, chuẩn hóa theo Bradley–Terry và cập nhật ngưỡng.
- **Kết quả tác giả báo cáo:** Trên AlpacaFarm/HH-RLHF, cùng performance với BoN nhưng ít hơn 15–35% generations.
- **Giới hạn/liên hệ:** Reward-model optimization trên preference tasks khác exact-answer math và chi phí một model local.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Ngân sách và dừng bên trong chuỗi suy luận

#### [C01] [Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters](https://arxiv.org/abs/2408.03314) (2024)

Charlie Snell et al. — arXiv 2408.03314. Ưu tiên A.

- **Làm gì:** So sánh cách phân bổ test-time compute theo difficulty.
- **Phương pháp:** Search dùng process verifier và điều chỉnh distribution của lời giải; chọn compute-optimal strategy cho prompt.
- **Kết quả tác giả báo cáo:** Hiệu quả scaling hơn 4 lần so với BoN; nhỏ có thể vượt model lớn 14 lần ở điều kiện FLOPs-matched được nghiên cứu.
- **Giới hạn/liên hệ:** Kết quả có điều kiện độ khó/base capability; không suy ra tăng budget luôn cải thiện.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C02] [Adaptive Inference-Time Compute: LLMs Can Predict if They Can Do Better, Even Mid-Generation](https://arxiv.org/abs/2410.02725) (2024)

Rohin Manvi, Anikait Singh, Stefano Ermon — arXiv 2410.02725. Ưu tiên A.

- **Làm gì:** Dự đoán liệu restart sẽ cho câu trả lời tốt hơn.
- **Phương pháp:** Huấn luyện generative self-evaluation bằng token định trước; adaptive sampling và early pruning.
- **Kết quả tác giả báo cáo:** Đạt 74% mức cải thiện của 16 mẫu với trung bình 1,2 mẫu; prune sớm 50–75% mẫu ở quality gần tương đương.
- **Giới hạn/liên hệ:** Có training để học self-evaluation; quyết định có thể thêm latency tuần tự. Sát nhánh CoT restart của repo.
- **Đã đọc/đối chiếu:** Abstract; Discussion/Conclusion/Limitations. Chưa tái lập thực nghiệm.

#### [C03] [Token-Budget-Aware LLM Reasoning](https://aclanthology.org/2025.findings-acl.1274/) (2025)

Tingxu Han et al. — Findings of ACL 2025; preprint 2024. Ưu tiên B.

- **Làm gì:** Nén suy luận theo mức độ phức tạp.
- **Phương pháp:** TALE ước lượng token budget theo câu hỏi và đưa budget vào prompt.
- **Kết quả tác giả báo cáo:** Abstract báo token cost giảm với mức giảm performance nhỏ; không nêu một tỉ lệ chung.
- **Giới hạn/liên hệ:** Budget được yêu cầu khác hard generation cap; tính thêm chi phí ước lượng budget nếu có.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C04] [s1: Simple test-time scaling](https://aclanthology.org/2025.emnlp-main.1025/) (2025)

Niklas Muennighoff et al. — EMNLP 2025. Ưu tiên A.

- **Làm gì:** Tạo reasoning model có thể điều khiển thinking budget.
- **Phương pháp:** SFT Qwen2.5-32B bằng 1.000 traces; budget forcing ép kết thúc hoặc chèn Wait để nghĩ tiếp.
- **Kết quả tác giả báo cáo:** AIME24 tăng từ 50% lên 57% khi kéo dài bằng budget forcing trong thiết lập bài.
- **Giới hạn/liên hệ:** Kết hợp model đã fine-tune và decoding intervention; không đồng nhất với native Qwen3 đang dùng.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C05] [Chain of Draft: Thinking Faster by Writing Less](https://arxiv.org/abs/2502.18600) (2025)

Silei Xu et al. — arXiv 2502.18600. Ưu tiên B.

- **Làm gì:** Giảm độ dài các bước suy luận bằng prompting.
- **Phương pháp:** CoD viết intermediate thoughts ngắn, chỉ giữ thông tin cần thiết.
- **Kết quả tác giả báo cáo:** Có thiết lập đạt tương đương/vượt CoT với token chỉ bằng 7,6% CoT.
- **Giới hạn/liên hệ:** 7,6% là trường hợp nổi bật, không phải bảo đảm chung; nên có CoT ngắn làm baseline rẻ.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C06] [Answer Convergence as a Signal for Early Stopping in Reasoning](https://aclanthology.org/2025.emnlp-main.904/) (2025)

Xin Liu, Lu Wang — EMNLP 2025. Ưu tiên A.

- **Làm gì:** Dừng chuỗi khi đáp án đã hội tụ.
- **Phương pháp:** Ba cách: answer-consistency stopping, tăng end-of-reasoning probability, probe có supervision từ activations.
- **Kết quả tác giả báo cáo:** Năm benchmark/năm model; ví dụ NaturalQuestions giảm token hơn 40% và accuracy tăng.
- **Giới hạn/liên hệ:** Answer stability không thay thế correctness; các cách có yêu cầu access/training khác nhau.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C07] [Thought calibration: Efficient and confident test-time scaling](https://aclanthology.org/2025.emnlp-main.722/) (2025)

Menghua Wu et al. — EMNLP 2025. Ưu tiên B.

- **Làm gì:** Dừng khi suy luận mới đã gần bão hòa.
- **Phương pháp:** Mô hình hóa chuỗi thoughts như reasoning trees lồng nhau; lightweight hidden-state probes.
- **Kết quả tác giả báo cáo:** Giữ performance với thinking token giảm tới 60% in-distribution, tới 20% OOD.
- **Giới hạn/liên hệ:** Phải truy cập hidden states và fit probe/calibration; lợi ích OOD nhỏ hơn ID.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C08] [Stop When Enough: Adaptive Early-Stopping for Chain-of-Thought Reasoning](https://aclanthology.org/2026.acl-long.1256/) (2026)

Renliang Sun et al. — ACL 2026. Ưu tiên A.

- **Làm gì:** Dừng phần reflection lặp và dư thừa.
- **Phương pháp:** REFRAIN dùng stop discriminator hai giai đoạn và sliding-window UCB để điều chỉnh ngưỡng.
- **Kết quả tác giả báo cáo:** Qua bốn benchmark/hai họ model, giảm token 20–55%, giữ hoặc tăng accuracy so với standard CoT.
- **Giới hạn/liên hệ:** Training-free vẫn có scoring/control overhead; bandit adaptation phải khai báo rõ.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C09] [Confidence Leaps in LLM Reasoning: Early Stopping and Cross-Model Transfer](https://aclanthology.org/2026.eacl-short.43/) (2026)

Pavel Tikhonov et al. — EACL 2026, Short Papers. Ưu tiên B.

- **Làm gì:** Dừng khi xác suất đáp án tăng đột ngột.
- **Phương pháp:** Heuristic training-free phát hiện confidence leap; thử chuyển partial reasoning sang model khác.
- **Kết quả tác giả báo cáo:** Abstract báo giảm generation length không mất accuracy và partial reasoning có ích khi transfer.
- **Giới hạn/liên hệ:** Dựa vào probability trajectory, khác một confidence score trên câu trả lời hoàn chỉnh.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C10] [Efficiently Scaling LLM Reasoning with Certaindex](https://proceedings.neurips.cc/paper_files/paper/2025/file/d037fd021c9aace128b8ce25001cdb6c-Paper-Conference.pdf) (2025)

Yichao Fu et al. — NeurIPS 2025; có preprint Dynasor 2024. Ưu tiên A.

- **Làm gì:** Phân bổ compute và lịch chạy cho reasoning programs.
- **Phương pháp:** Certaindex đo certainty/progress; Probe-In-The-Middle; Dynasor kết hợp budget allocation và gang scheduling.
- **Kết quả tác giả báo cáo:** Báo batch compute giảm tới 50%, online throughput tới 3,3 lần hoặc latency SLO chặt hơn 4,7 lần.
- **Giới hạn/liên hệ:** Đây là đo hệ thống serving của tác giả; không thể đổi trực tiếp sang output-token savings hay Mac latency.
- **Đã đọc/đối chiếu:** Abstract/introduction; phần mô tả Certaindex/Dynasor. Chưa tái lập thực nghiệm.

#### [C11] [When to Continue Thinking: Adaptive Thinking Mode Switching for Efficient Reasoning](https://aclanthology.org/2025.findings-emnlp.310/) (2025)

Xiaoyun Zhang et al. — Findings of EMNLP 2025. Ưu tiên B.

- **Làm gì:** Giảm thinking dư nhưng cho phép phục hồi ngầm khi viết đáp án.
- **Phương pháp:** ASRR dùng accuracy-aware length reward regulation trong học reasoning.
- **Kết quả tác giả báo cáo:** So GRPO: budget giảm tới 32,5% (1.5B)/25,7% (7B), pass@1 giảm 1,2%/0,6%.
- **Giới hạn/liên hệ:** Có training; No-Thinking vẫn có thể dùng compute trong answer generation.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [C12] [Settle: Learning When to Stop Reasoning](https://arxiv.org/abs/2609.38997) (2026)

Ryan Brown, Zihao Fu, Chris Russell — arXiv v1, 30/09/2026. Ưu tiên A.

- **Làm gì:** Học stop token từ mức ổn định của đáp án trong completed traces.
- **Phương pháp:** Train end-of-reasoning token, regularize các prediction còn lại; inference bằng decoder thông thường.
- **Kết quả tác giả báo cáo:** Qwen3-4B/MATH-500 giảm 39,9% token; forced accuracy giảm 0,50 điểm; có thử thêm Qwen3-8B.
- **Giới hạn/liên hệ:** Thay đổi weights; forced/natural accuracy cần phân biệt. Chưa phải giải pháp training-free cho model cố định.
- **Đã đọc/đối chiếu:** Abstract; Conclusion/Limitations. Chưa tái lập thực nghiệm.

#### [C13] [SABER: Stability-Aware Early Exit for LLM Reasoning via Adversarial Branch Probing](https://arxiv.org/abs/2608.27963) (2026)

Wanli Cheng et al. — arXiv v1; comments ghi EMNLP 2026 MainConference. Ưu tiên A.

- **Làm gì:** Ước lượng ổn định trước khi chạy hết các nhánh suy luận.
- **Phương pháp:** Training-free semantic perturbations tại state trung gian; probe outcomes của adversarial branches.
- **Kết quả tác giả báo cáo:** Abstract báo reasoning tokens giảm trung bình 30,2–39,8%, accuracy cạnh tranh với full-length reasoning.
- **Giới hạn/liên hệ:** Cần tính chi phí branches/probes; độ ổn định qua perturbation chưa phải chứng chỉ đúng.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Tìm kiếm có cấu trúc: cây và đồ thị

#### [T01] [Tree of Thoughts: Deliberate Problem Solving with Large Language Models](https://arxiv.org/abs/2305.10601) (2023)

Shunyu Yao et al. — arXiv v2, 03/12/2023; NeurIPS 2023. Ưu tiên B.

- **Làm gì:** Tìm kiếm qua các state suy nghĩ trung gian.
- **Phương pháp:** ToT sinh/evaluate thoughts, lookahead và backtracking với tree search.
- **Kết quả tác giả báo cáo:** Game of 24: GPT-4/CoT 4% so với ToT 74% trong thiết lập bài.
- **Giới hạn/liên hệ:** Không compute-matched mặc nhiên. Arm TOT của repo là candidate selection, chưa tái lập tree search.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [T02] [Reasoning with Language Model is Planning with World Model](https://arxiv.org/abs/2305.14992) (2023)

Shibo Hao et al. — arXiv v2, 23/10/2023; EMNLP 2023. Ưu tiên B.

- **Làm gì:** Biến reasoning thành planning có world model.
- **Phương pháp:** RAP dùng LLM làm agent/world model; MCTS cân bằng exploration và exploitation.
- **Kết quả tác giả báo cáo:** Trên plan generation, LLaMA-33B/RAP hơn GPT-4/CoT 33% tương đối; thử cả math và logic.
- **Giới hạn/liên hệ:** Có reward và world-model calls; tăng call budget có thể là nguồn lợi ích.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [T03] [Graph of Thoughts: Solving Elaborate Problems with Large Language Models](https://arxiv.org/abs/2308.09687) (2024)

Maciej Besta et al. — arXiv v4; metadata ghi AAAI 2024. Ưu tiên B.

- **Làm gì:** Tổ chức suy luận thành đồ thị thay vì đường/cây.
- **Phương pháp:** GoT nối dependencies, hợp nhất thoughts và dùng feedback loops.
- **Kết quả tác giả báo cáo:** Ví dụ sorting quality tăng 62% so ToT trong khi cost giảm hơn 31%.
- **Giới hạn/liên hệ:** Sorting quality khác math accuracy; graph operations cũng phải được tính cost.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Chương trình, công cụ và kiểm chứng

#### [V01] [PAL: Program-aided Language Models](https://arxiv.org/abs/2211.10435) (2023)

Luyu Gao et al. — arXiv v2, 27/01/2023; nền tảng, ngoài ưu tiên 2024–2026. Ưu tiên A.

- **Làm gì:** Tách hiểu bài toán khỏi thực thi tính toán.
- **Phương pháp:** LLM sinh chương trình; Python runtime giải các bước đã biểu diễn.
- **Kết quả tác giả báo cáo:** Qua 13 tác vụ; PAL/Codex trên GSM8K hơn PaLM-540B/CoT 15 điểm top-1.
- **Giới hạn/liên hệ:** Program chạy được chưa chắc biểu diễn đúng đề. PAL trong repo cần mô tả adapter và lỗi riêng.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [V02] [Program of Thoughts Prompting: Disentangling Computation from Reasoning for Numerical Reasoning Tasks](https://arxiv.org/abs/2211.12588) (2023)

Wenhu Chen et al. — TMLR 2023; arXiv v4, 23/10/2023. Ưu tiên B.

- **Làm gì:** Đưa computation trong lời giải sang chương trình.
- **Phương pháp:** PoT dùng code làm reasoning representation và external execution; có PoT + SC.
- **Kết quả tác giả báo cáo:** Tám tập math/financial QA: abstract báo hơn CoT khoảng 12% trung bình.
- **Giới hạn/liên hệ:** Lợi ích từ tool execution cần tách khỏi routing/stopping; SC làm tăng calls.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [V03] [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) (2023)

Shunyu Yao et al. — ICLR 2023, arXiv v3; nền tảng. Ưu tiên B.

- **Làm gì:** Xen kẽ reasoning với action và observation.
- **Phương pháp:** ReAct cập nhật kế hoạch bằng tool/environment feedback.
- **Kết quả tác giả báo cáo:** Thử HotpotQA/FEVER/ALFWorld/WebShop; báo tăng success 34 và 10 điểm trên hai tập interactive.
- **Giới hạn/liên hệ:** Bài gốc dùng môi trường rộng hơn vòng calculator hạn chế của repo.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [V04] [CRITIC: Large Language Models Can Self-Correct with Tool-Interactive Critiquing](https://arxiv.org/abs/2305.11738) (2024)

Zhibin Gou et al. — ICLR 2024; arXiv v4. Ưu tiên A.

- **Làm gì:** Kiểm tra và sửa initial answer bằng feedback ngoài.
- **Phương pháp:** LLM tương tác search/code tools, critique rồi sửa lặp.
- **Kết quả tác giả báo cáo:** Cải thiện ở free-form QA, mathematical program synthesis và toxicity reduction.
- **Giới hạn/liên hệ:** Targeted correction nhận câu trả lời cũ; replay strategies độc lập của repo chưa mô phỏng được.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [V05] [Let’s Verify Step by Step](https://arxiv.org/abs/2305.20050) (2023)

Hunter Lightman et al. — arXiv 2305.20050; nền tảng process supervision. Ưu tiên B.

- **Làm gì:** So process supervision với outcome supervision.
- **Phương pháp:** Huấn luyện reward model từ nhãn từng bước; PRM800K gồm 800.000 nhãn.
- **Kết quả tác giả báo cáo:** Process-supervised setup giải 78% trên một subset đại diện của MATH test.
- **Giới hạn/liên hệ:** Có training, nhiều candidates và tập subset; không chuyển số này sang toàn MATH hay verifier deterministic.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [V06] [Math-Shepherd: Verify and Reinforce LLMs Step-by-step without Human Annotations](https://arxiv.org/abs/2312.08935) (2024)

Peiyi Wang et al. — arXiv v3, 19/02/2024. Ưu tiên B.

- **Làm gì:** Tự tạo process labels để giảm phụ thuộc human annotation.
- **Phương pháp:** Math process reward model; rerank outputs và step-by-step PPO.
- **Kết quả tác giả báo cáo:** Mistral-7B/GSM8K 77,9% → 84,1% sau PPO, tới 89,1% khi thêm verification.
- **Giới hạn/liên hệ:** Gains có cả training và selection; không phải riêng stopping hay frozen model.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [V07] [When to Trust the Cheap Check: Weak and Strong Verification for Reasoning](https://arxiv.org/abs/2602.17633) (2026)

Shayan Kiyani et al. — arXiv 2602.17633. Ưu tiên A.

- **Làm gì:** Quyết định accept/reject hoặc gọi strong verifier.
- **Phương pháp:** Weak–strong policies; cấu trúc hai ngưỡng và Selective Strong Verification với online error control.
- **Kết quả tác giả báo cáo:** Chứng minh error-control có finite-sample slack; thử math và Sudoku với verification cost thấp hơn exhaustive strong checking.
- **Giới hạn/liên hệ:** Guarantee kiểm soát lệch với strong signal. Cheap execution có thể chỉ kiểm một phần output; không tự là full truth.
- **Đã đọc/đối chiếu:** Abstract; Introduction; §4–5; mô tả thí nghiệm §6. Chưa tái lập thực nghiệm.

### Học biểu diễn hoặc hành vi suy luận hiệu quả

#### [L01] [AdapThink: Adaptive Thinking Preferences for Reasoning Language Models](https://aclanthology.org/2026.findings-acl.477/) (2026)

Wenyue Xu et al. — Findings of ACL 2026. Ưu tiên B.

- **Làm gì:** Điều chỉnh reflection theo trạng thái difficulty thay vì giảm độ dài đồng loạt.
- **Phương pháp:** Adaptive preference control từ group statistics và diversity sampling theo dispersion.
- **Kết quả tác giả báo cáo:** Ở budget 32K, response length giảm 17,1–21,4%, performance tăng 6,12–6,59 điểm.
- **Giới hạn/liên hệ:** Khác AdaptThink của Zhang (2025); thuộc hướng học behavior, không controller thuần inference.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [L02] [Training Large Language Models to Reason in a Continuous Latent Space](https://arxiv.org/abs/2412.06769) (2024)

Shibo Hao et al. — arXiv 2412.06769. Ưu tiên B.

- **Làm gì:** Suy luận trong continuous hidden space.
- **Phương pháp:** Coconut đưa last hidden state làm input embedding kế tiếp thay vì decode token ngôn ngữ.
- **Kết quả tác giả báo cáo:** Vượt CoT ở một số logic tasks cần backtracking, với ít thinking tokens hơn.
- **Giới hạn/liên hệ:** Có thay đổi cơ chế/training; latent steps vẫn tốn compute dù ít textual tokens.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [L03] [Memory Augmentation Unlocks Efficient Chain-of-Thought Reasoning](https://arxiv.org/abs/2608.21265) (2026)

Simeng Zhang et al. — arXiv 2608.21265, 21/08/2026. Ưu tiên B.

- **Làm gì:** Bù mất thông tin khi nén reasoning.
- **Phương pháp:** Memory-Augmented Compression lấy reasoning patterns từ traces lịch sử làm prefill scaffolds.
- **Kết quả tác giả báo cáo:** So CoD: accuracy tăng 21,4 điểm GSM8K/28,0 MATH; latency nhanh hơn CoT 1,14–1,49 lần trong bài.
- **Giới hạn/liên hệ:** Thêm context và retrieval; split memory phải sạch, chi phí input có thể tăng.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Calibration và đánh giá có kiểm soát ngân sách

#### [E01] [Program-Aided Reasoners (Better) Know What They Know](https://aclanthology.org/2024.naacl-long.125/) (2024)

Anubha Kabra et al. — NAACL 2024. Ưu tiên A.

- **Làm gì:** So calibration của PAL và text CoT.
- **Phương pháp:** Năm datasets, hai họ model; phân tích generation diversity và temperature.
- **Kết quả tác giả báo cáo:** PAL calibration tốt hơn ở 75% thiết lập được so sánh.
- **Giới hạn/liên hệ:** Đây không phải 75% câu trả lời đúng hay kết luận PAL luôn calibrated.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [E02] [Small Language Models Need Strong Verifiers to Self-Correct Reasoning](https://aclanthology.org/2024.findings-acl.924/) (2024)

Yunxiang Zhang et al. — Findings of ACL 2024. Ưu tiên A.

- **Làm gì:** Tách khả năng tự sửa khỏi khả năng nhận biết khi cần sửa.
- **Phương pháp:** SCORE tạo/filter critique data rồi SFT self-refinement; so strong GPT-4 verifier và weak self-verifier.
- **Kết quả tác giả báo cáo:** Hai model/năm tập: self-correction tốt hơn khi có strong verifier, còn hạn chế với self-verifier yếu.
- **Giới hạn/liên hệ:** Có training và model lớn hỗ trợ. Cần đo riêng verify, revise, rescue và harm.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [E03] [Large Language Models Cannot Self-Correct Reasoning Yet](https://arxiv.org/abs/2310.01798) (2024)

Jie Huang et al. — ICLR 2024; arXiv v2. Ưu tiên A.

- **Làm gì:** Kiểm tra intrinsic self-correction không feedback ngoài.
- **Phương pháp:** Đánh giá sửa initial answer chỉ bằng khả năng của chính model.
- **Kết quả tác giả báo cáo:** Trong thiết lập nghiên cứu, nhiều model khó tự sửa và có thể giảm performance sau correction.
- **Giới hạn/liên hệ:** Là phát hiện có phạm vi; không phủ định mọi phương pháp có feedback/training về sau.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [E04] [Large Language Models Can Self-Correct with Key Condition Verification](https://aclanthology.org/2024.emnlp-main.714/) (2024)

Zhenyu Wu et al. — EMNLP 2024. Ưu tiên B.

- **Làm gì:** Tạo câu hỏi kiểm ngược một điều kiện trong đề.
- **Phương pháp:** ProCo mask key condition, gắn answer hiện tại, dự đoán lại condition; verify-then-correct lặp.
- **Kết quả tác giả báo cáo:** So Self-Correct/GPT-3.5: +6,8 EM ở QA; +14,1 accuracy ở arithmetic; +9,6 ở commonsense.
- **Giới hạn/liên hệ:** LLM verification thêm calls; không chứng chỉ symbolic đúng tuyệt đối.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [E05] [Reasoning in Token Economies: Budget-Aware Evaluation of LLM Reasoning Strategies](https://aclanthology.org/2024.emnlp-main.1112/) (2024)

Junlin Wang et al. — EMNLP 2024. Ưu tiên A.

- **Làm gì:** Phân biệt lợi ích thuật toán với lợi ích do dùng thêm compute.
- **Phương pháp:** Khung đánh giá budget-aware; cho các baseline ngân sách tương đương.
- **Kết quả tác giả báo cáo:** CoT + SC đơn giản thường vượt strategy phức tạp khi được cấp compute tương đương.
- **Giới hạn/liên hệ:** Baseline bắt buộc để tránh coi budget khác nhau là hiệu quả của controller.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [E06] [Reasoning about Uncertainty: Do Reasoning Models Know When They Don’t Know?](https://aclanthology.org/2026.findings-eacl.178/) (2026)

Zhiting Mei et al. — Findings of EACL 2026. Ưu tiên A.

- **Làm gì:** Đánh giá calibration và tác động của deeper reasoning.
- **Phương pháp:** Uncertainty quantification; IUQ yêu cầu model suy xét lại CoT trace.
- **Kết quả tác giả báo cáo:** Các model thường overconfident; reasoning sâu có thể làm nặng hơn; introspection hữu ích không đồng đều giữa model.
- **Giới hạn/liên hệ:** Không coi self-reported confidence hay dài CoT là xác suất đúng đáng tin.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Overthinking, harm và giới hạn khả năng

#### [H01] [Thinking Past the Answer: Evaluating Harmful Overthinking in Large Reasoning Models](https://arxiv.org/abs/2606.02835) (2026)

Simone Caldarella et al. — arXiv 2606.02835. Ưu tiên A.

- **Làm gì:** Tách verbose overthinking khỏi harmful overthinking.
- **Phương pháp:** Prefix-level evaluation tìm budget tối thiểu lần đầu trả lời đúng và theo dõi correctness drift.
- **Kết quả tác giả báo cáo:** First-correct-prefix analysis có mức tăng tới 21%; early stopping thông dụng giảm verbosity nhưng chưa xử lý hết harmful drift.
- **Giới hạn/liên hệ:** First-correct prefix dùng gold để phân tích, là oracle diagnostic chứ không policy triển khai.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [H02] [Knowing When to Quit: Diagnosing and Training LLMs to Abort Futile Reasoning](https://aclanthology.org/2026.findings-acl.830/) (2026)

Xinyan Guan et al. — Findings of ACL 2026. Ưu tiên B.

- **Làm gì:** Giảm reasoning vô ích khi câu vượt khả năng model.
- **Phương pháp:** CaRL dùng reward shaping khuyến khích refusal và hindsight augmentation từ failures.
- **Kết quả tác giả báo cáo:** Báo giảm futile reasoning và giữ performance qua các độ khó; abstract không có một số chung.
- **Giới hạn/liên hệ:** Có training và hành động refusal; phạm vi khác chỉ choosing next strategy.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

### Mô hình nền, bài nền tảng và survey tham khảo

#### [B01] [Qwen3 Technical Report](https://arxiv.org/abs/2505.09388) (2025)

An Yang et al. — arXiv 2505.09388, technical report. Ưu tiên A.

- **Làm gì:** Mô tả họ model và mode điều khiển suy luận của Qwen3.
- **Phương pháp:** Unified thinking/non-thinking, thinking-budget mechanism, distillation cho model nhỏ.
- **Kết quả tác giả báo cáo:** Báo performance cạnh tranh trên math/code/agent benchmarks; 119 ngôn ngữ và dialects.
- **Giới hạn/liên hệ:** Phải pin checkpoint, quantization, template và decoding. Report không đo hiệu quả controller của nhóm.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [B02] [Chain-of-Thought Prompting Elicits Reasoning in Large Language Models](https://arxiv.org/abs/2201.11903) (2022)

Jason Wei et al. — Nguồn nền tảng 2022; ngoài khoảng ưu tiên. Ưu tiên B.

- **Làm gì:** Khơi gợi multi-step reasoning bằng demonstrations.
- **Phương pháp:** Few-shot CoT cung cấp ví dụ có intermediate steps.
- **Kết quả tác giả báo cáo:** Tăng performance arithmetic/commonsense/symbolic; PaLM-540B với tám exemplars đạt kết quả mạnh trên GSM8K.
- **Giới hạn/liên hệ:** Không phải mọi model nhỏ đều hưởng lợi; CoT gốc khác native hidden thinking.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [B03] [Self-Consistency Improves Chain of Thought Reasoning in Language Models](https://arxiv.org/abs/2203.11171) (2023)

Xuezhi Wang et al. — ICLR 2023; preprint 2022, nền tảng. Ưu tiên A.

- **Làm gì:** Tăng độ đúng bằng nhiều đường reasoning.
- **Phương pháp:** Sampling diverse CoTs và chọn answer được đồng thuận cao nhất.
- **Kết quả tác giả báo cáo:** Abstract báo GSM8K tăng 17,9% so CoT; có tăng ở SVAMP/AQuA/StrategyQA/ARC.
- **Giới hạn/liên hệ:** Đồng thuận giữa samples có tương quan không phải chứng minh độc lập; voting semantics cần đúng.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [B04] [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) (2023)

Aman Madaan et al. — arXiv v2 2023, nền tảng self-feedback. Ưu tiên B.

- **Làm gì:** Cải thiện output ban đầu bằng feedback lặp.
- **Phương pháp:** Cùng một LLM làm generator, critic và refiner; không cần additional training.
- **Kết quả tác giả báo cáo:** Bảy tác vụ: task performance cải thiện khoảng 20% tuyệt đối trung bình theo abstract.
- **Giới hạn/liên hệ:** Không đổi thành +20 điểm math accuracy chung; tính thêm feedback/refinement calls.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

#### [B05] [Reasoning on a Budget: A Survey of Adaptive and Controllable Test-Time Compute in LLMs](https://arxiv.org/abs/2507.02076) (2025)

Mohammad Ali Alomrani et al. — arXiv 2507.02076; survey, nguồn thứ cấp. Ưu tiên B.

- **Làm gì:** Lập bản đồ efficient test-time compute.
- **Phương pháp:** Taxonomy L1-controllability theo budget cố định và L2-adaptiveness theo difficulty/confidence.
- **Kết quả tác giả báo cáo:** Tổng hợp trade-off performance–token và benchmark proprietary models; không phải thuật toán mới.
- **Giới hạn/liên hệ:** Dùng để mở rộng truy tìm paper; số liệu của thuật toán phải quay về nguồn gốc.
- **Đã đọc/đối chiếu:** Abstract. Chưa tái lập thực nghiệm.

## 10. Mẫu bổ sung survey và giới hạn của bản này

Mẫu cho một bài mới: tiêu đề/tác giả/năm/bản/URL; nó làm gì; state/actions và thuật toán; cần train model hay chỉ controller; dữ liệu và baseline; kết quả/đơn vị chi phí; limitations; trùng/khác với nhóm; mức đã đọc; người đọc và ngày cập nhật.

Bản này cung cấp bản đồ định hướng và nguồn để nhóm đọc tiếp. Chưa tìm hết mọi công trình, chưa audit toàn bộ code của paper, chưa tái lập số liệu và chưa đánh giá chất lượng phản biện từng bài. Việc không thấy một phương pháp trong danh mục không chứng minh research gap. Những đề xuất nghiên cứu cần được GVHD duyệt và chốt protocol trước main experiment.

