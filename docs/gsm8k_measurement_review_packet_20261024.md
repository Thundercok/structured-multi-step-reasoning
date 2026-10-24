# GSM8K development — gói review và bản thảo phương pháp, 2026-10-24

**Chuẩn bị review, chưa phải execution freeze.** Nguồn triển khai liên quan
vẫn khớp fingerprints của nghiệm thu H1–H3. Không chạy lại suite khi source
chưa đổi. Candidate 48/48 chưa được mở hoặc fit; inference budget vẫn 0.

Gói làm việc:

- [Cấu hình và source hashes](../audit/gsm8k_measurement_review_packet_20261024/configuration_draft.json).
- [Phiếu review dữ liệu trống](../audit/gsm8k_measurement_review_packet_20261024/data_review_ledger_template.csv).
- [Protocol hiện hành](gsm8k_development_validation_protocol_20261004.md) và
  [nghiệm thu H1–H3](../audit/gsm8k_h1_h3_acceptance_20261024/README.md).

Phiếu chỉ có header, không có câu hỏi/đáp án hoặc quyết định giả. Dataset hash
trong cấu hình lấy từ manifest lịch sử, không phải xác nhận review nội dung mới.
Các trường người review, custodian và authorization để null có chủ đích.

## Phần phương pháp có thể đưa vào bản thảo

Đây là **thiết kế prospective đang chờ thực hiện**, không viết ở thì đã chạy.

Chúng tôi dự kiến đánh giá một baseline định tuyến chỉ sử dụng độ dài câu hỏi
trên mô hình nền cố định. Từ GSM8K training revision đã pin, thiết kế chọn 96
nhóm chưa thuộc 24 normalized identities của pilot cũ bằng SHA-256 ranking,
seed 42; các vị trí xen kẽ phân thành 48 nhóm fitting và 48 nhóm development
validation. Cả hai phần là development; official test không dùng. Semantic
duplicates, wording và gold cần được review trước generation; 96 nhóm là quy
mô screening, chưa phải justification về power của publication.

Không gian quyết định gồm DIRECT, CoT và PAL. Feature duy nhất là số từ tách
bằng whitespace trong câu hỏi gốc, trước strategy suffix. Menu cố định có 24
quy tắc hai nhánh ở các cutoff 20, 40, 60, 80 từ và ba quy tắc hằng. Mỗi câu
chỉ chọn một recipe, không escalation, stopping, embedding hoặc confidence gate.

Trên fitting, rule và fixed comparator được chọn theo utility
`accuracy − 0.1 × mean_generated_tokens / 1000`. Khi hòa utility, ưu tiên accuracy
cao hơn, token thấp hơn, rule hằng rồi lexical rule ID. Lambda 0,1 chỉ thuộc
phép đo development này. Selection và fitting scores được lưu và băm trước khi
xem outcomes/scores validation; hash và access ledger không tự ngăn mọi thao
tác đọc file ngoài ứng dụng, nên cần quy trình lưu ký cụ thể.

Ba recipe được dự kiến thu một lần trên mỗi câu với cùng snapshot Qwen đã
pin, `english-math-v1`, temperature 0, thinking off, generation seed 42 và cap
1.024 token/call. PAL có một lần execution với timeout helper 5 giây. Model
không được nhận gold/source solution; evaluator giữ labels. Journal phải lưu
generation trước PAL execution, giữ chi phí đã đo và diagnostics khi tool lỗi.
Unknown generation outcomes giữ reservation riêng và dừng để review; không
coi reservation là token đo được hoặc tự retry.

Validation báo năm dòng: rule được chọn, fixed reference được chọn từ fitting
và ba fixed recipes. Primary contrast duy nhất là rule trừ selected reference.
Báo accuracy, generated/prompt tokens, utility, strategy counts, rescue/harm và
PAL failures. Chi phí full collection gồm cả fitting và validation, cả ba arms;
chi phí selected path chỉ gồm arm được chọn. Stored strategy duration gồm tool
time là replay metric, không phải online controller latency. Generated tokens
không đại diện full inference cost, giá tiền hoặc mức tiêu thụ năng lượng.

Khoảng percentile 95% dự kiến dùng 2.000 resamples của original validation
groups, seed 42. Khoảng có điều kiện trên rule và generation seed quan sát,
không bao gồm fitting uncertainty hoặc chứng minh robustness nhiều seeds.
Nếu rule collapse thành constant phải báo rõ. Khoảng chứa 0 chưa chứng minh
tương đương; giữ cả kết quả âm, không đổi rule/cutoff/comparator từ validation.

## Khung bảng kết quả — chưa có số đo

| Method | Accuracy | Mean generated tokens | Mean prompt tokens | Utility | PAL failures |
| --- | --- | --- | --- | --- | --- |
| Query-only selected rule | Chưa thu | Chưa thu | Chưa thu | Chưa thu | Chưa thu |
| Fitting-selected fixed reference | Chưa thu | Chưa thu | Chưa thu | Chưa thu | Chưa thu |
| DIRECT | Chưa thu | Chưa thu | Chưa thu | Chưa thu | Không dùng tool |
| CoT | Chưa thu | Chưa thu | Chưa thu | Chưa thu | Không dùng tool |
| PAL | Chưa thu | Chưa thu | Chưa thu | Chưa thu | Chưa thu |

Paired effects/CI, rescue/harm, fitting-only/validation-only/full cost và
failure counts chỉ điền từ reviewed artifacts. Không dùng số fixture hoặc
historical pilot để lấp bảng này. Phép đo không kiểm H1 main entry-plus-stopping
và không cô lập causal effect của tool khỏi recipe/prompt.

## Việc cụ thể tiếp theo

1. **Adapter thật:** hiện chỉ có staged interface/mock. Lát cắt tiếp theo phải
   tách generation/tool của `QwenMLXBackend` mà giữ suffix, template, decoding,
   parsing và confidence của DIRECT/COT/PAL. Chỉ truyền query/format metadata
   cho model-facing stage. Đo và lưu raw prompt/messages thực tế; không dựng
   lại trace bằng query trần khi prompt thật có suffix/template.
2. **Parity offline trước:** dùng injected generation/tool fixtures để đối chiếu
   legacy và staged, gồm PAL success/failure, length stop và crash boundaries.
   Không nạp MLX/model, không thu candidate để thử adapter. Giữ gate nhận
   measured staged đóng cho tới review adapter và freeze cụ thể.
3. **Data review có người chịu trách nhiệm:** sau khi phạm vi mở candidate đã
   được xác nhận, điền ledger bằng giải độc lập từ query trước khi so gold;
   review semantic overlap/exposure, rồi human sign-off. Nếu thay retained
   frame, phát hành release mới và review lại 48/48 contract trước collection.
4. **Freeze và ngân sách:** rehash model/tokenizer/template, source và môi
   trường; chốt custodian/access procedure, cấu hình thực thi và authorization.
   Trần 288 calls/294.912 generated tokens vẫn là đề xuất, không phải quyền chạy.

Giữ bridge đã đóng, checker C1–C3, Stage 0 và SoL-Pi backlog như hiện tại.
