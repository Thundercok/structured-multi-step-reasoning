# Tín hiệu dừng: kiểm lại pilot development đã lưu

2026-10-23, Asia/Saigon. Phân tích retrospective trên 23 nhóm GSM8K development
đã xem, seed 42, 69 bản ghi DIRECT/CoT/PAL. Không chạy inference, fit policy,
rescore gold hoặc đọc held-out candidate. Human/publication review vẫn pending.
Đây là chẩn đoán để chọn phép kiểm tiếp theo, không phải một decision gate đã đạt.

Phần [marginal-value trong comparison brief](../../../../docs/research_comparison_brief_20261004.md#marginal-value-of-another-recipe--exact-development-accounting)
đã bổ sung phân rã cost/rescue/harm và đoạn viết cho bản thảo. `marginal_value.json`
giữ kết quả tính chính xác, source/input hashes và giới hạn; `marginal_value.png`
và `.svg` là biểu đồ cùng dữ liệu. Fixed PAL đúng 21/23 với 2.002 token sinh;
luôn CoT rồi PAL độc lập vẫn 21/23 nhưng 4.229 token. Không có gate mới được fit
hoặc model call. Tái lập bằng `analyze_marginal_value.py --output NEW_DIRECTORY`;
script từ chối ghi đè outputs đã có. Đây là một phần phân tích của gói hiện
tại, không phải study/dataset/controller mới.

`collection_envelope.json` và `estimate_collection_envelope.py` bổ sung bản tính
**planning** chỉ đọc source và metadata: [quyết định tiếp theo trong research plan](../../../../docs/research_plan.md#quyết-định-tiếp-theo--thiết-kế-có-thể-duyệt-2026-10-23).
Ba seeds giả định × 179 items có thể cần tới 8.055 generation calls và 537
embeddings theo defaults, khác với selected-path cost của một policy replay.
Đây không phải run, allocation hoặc power analysis; không đọc held-out content.

## Kết quả có thể đối chiếu

| Cách dùng outputs đã lưu | Đúng / 23 | Tổng token sinh | Token sinh trung bình | Generation calls trên các path |
| --- | ---: | ---: | ---: | ---: |
| Luôn CoT | 19 | 2.227 | 96,8 | 23 |
| Luôn PAL | 21 | 2.002 | 87,0 | 23 |
| CoT → PAL chỉ khi parse fail / length stop / tool failure | 19 | 2.227 | 96,8 | 23 |
| CoT → PAL cho mọi câu | 21 | 4.229 | 183,9 | 46 |

Quy tắc failure-marker được xét **sau khi đã đọc báo cáo cũ**, không phải
preregistered policy. Nó không trigger trên câu nào: tất cả CoT có parse marker,
finish reason `stop`, không có failed tool event. Bốn câu CoT sai đều lọt qua;
confidence lưu của chúng nằm trong khoảng **0,9471–0,9692**. Không tìm ngưỡng
mới hoặc dùng các số này để fit lại confidence đã trượt gate lịch sử.

So các output CoT/PAL cùng câu: **17 cùng đúng, 4 rescue, 2 harm, 0 cùng sai**.
PAL chạy tool thành công 23/23, bao gồm cả hai câu PAL trả lời sai. Những phép
kiểm execution/format này không xác nhận cách hiểu đề hoặc độ đúng đáp án.

Hai dòng cascade là **conditional replay trên outputs độc lập đã lưu**, với
PAL nhận query gốc, không nhận câu trả lời CoT. Không phải targeted correction,
model run mới hay latency online. Chi phí cộng token sinh của mọi call được
chọn; chưa gồm prompt tokens, tool/router overhead hoặc full inference cost.
Không suy từ mẫu nhỏ này rằng PAL luôn thắng trên family/model/budget khác.

## Hệ quả cho đề xuất tiếp theo

1. Giữ failure markers làm guardrail; ngân sách hết/hủy/deadline vẫn là trạng
   thái dừng, không phải lý do để gọi thêm vượt giới hạn. Marker sạch không
   đồng nghĩa answer đúng.
2. Ưu tiên **kiểm chứng** checker có phạm vi tác vụ rõ, với valid/invalid/
   unknown và coverage được báo riêng. Checker rationale/equation không tự là
   answer verifier; không đổi một nhãn VALID hoặc tool success thành xác suất
   đúng cao. Dùng public answer/artifact/witness, không yêu cầu raw/private CoT.
3. Giữ fixed PAL bên cạnh fixed CoT khi đánh giá routing/stopping. Cứ chạy CoT
   rồi PAL có thể tốn cả hai nhưng vẫn chỉ nhận answer của PAL. Entry routing
   hiện có cho phép chọn PAL trực tiếp; cần đo giá trị của việc chọn/chạy thêm,
   không mặc định mọi câu phải đi qua CoT.
4. Agreement là đối chứng/tín hiệu ứng viên, không miễn phí: phải phát sinh các
   outputs trước khi so. Không dùng four-arm agreement nhìn thấy hết outputs
   như một cheap gate trước CoT. Raw confidence/composite hiện tại vẫn chỉ là
   diagnostic cho tới khi có evidence phù hợp; historical FAIL không tự chứng
   minh mọi tín hiệu khác cũng fail hoặc verifier đã thành công.

Đây là **đề xuất thứ tự kiểm chứng**, chưa chọn checker/policy cho campaign.
Không tự thêm một arm/method hoặc mở nhánh nghiên cứu mới. Trước collection
cần review data, đúng phạm vi checker, model/prompt/caps, signal availability,
primary contrast và budget theo protocol hiện hành. Dùng các packet đã có.

## Tái lập và giới hạn

```bash
.venv/bin/python audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/analyze_saved_pilot.py
```

Script pin `records.json` SHA-256
`858af874dc7ba0393e0aef6a4d7ba39fc3fa2a6e67347b1bc09708ed38ddee54`, kiểm
tất cả declared artifact hashes và bảo toàn inputs. `diagnostics.json` giữ
counts/costs; `items.json` chỉ giữ development IDs, stored correctness và
markers, không chép lại câu hỏi/đáp án. `provenance.json` giữ hashes/source và
xác nhận không đổi historical inputs. `output.txt` là stdout lần phân tích.

Script kiểm 69 records, mỗi ID có đúng ba strategies, 23 nhóm riêng, không
missing/duplicate arms, caps 1.024, splits train/calibration, và đối chiếu
19/23 CoT, 21/23 PAL, 4 rescue/2 harm với báo cáo development cũ. Không refit
hay chạy replay bằng harness source mới để vượt historical source guards.
Correctness lấy từ bản ghi đã được audit; không có semantic gold review mới.
Không tính CI/p-value hoặc biến 69 strategy records thành 69 câu độc lập.

## Gói kiểm chứng checker đã chuẩn bị — 2026-10-23

**Đề xuất lấy Game of 24 làm lát cắt kiểm tra contract đầu tiên**, trong family
đã có. Đây chưa phải quyết định đổi main study hoặc bật policy mới. Tái sử dụng
`scripts.verifiers.verify_g24_rationale` và `VerificationStatus` hiện tại;
không tạo verifier/runtime/enum khác. Tên hàm legacy có `rationale`, nhưng input
đề xuất chỉ là public answer expression và bốn số đã biết, không cần raw/private CoT.

### Contract được đề xuất

Phạm vi: đúng bốn số nguyên dương được bind từ câu hỏi/metadata đã review,
mỗi số dùng đúng một lần; toán tử `+ - * /`, ngoặc, mục tiêu 24. Checker kiểm
giá trị bằng phân số chính xác qua `check24`. Caller không đưa gold, reference
solution hoặc answer của evaluator vào checker.

| Kết quả hiện có | Ý nghĩa trong phạm vi này | Cách dùng được đề xuất, chưa bật |
| --- | --- | --- |
| `valid` | Biểu thức được hỗ trợ dùng đúng multiset số đầu vào và có giá trị 24. | Có thể chấp nhận public expression theo contract đó; không biến thành confidence 1.0 hoặc xác nhận một tác vụ khác. |
| `invalid` | Output vi phạm yêu cầu được kiểm, ví dụ dùng sai số hoặc cho kết quả khác 24. | Xem xét strategy kế tiếp chỉ nếu request/token budget và lifecycle còn cho phép. |
| `unverifiable` | Thiếu đầu vào bắt buộc hoặc không lấy/parse được biểu thức được hỗ trợ. | Báo không kiểm được; không gộp với đúng/sai. Có thể tiếp tục trong budget hoặc kết thúc với trạng thái chưa xác minh. |

Public `unknown` nếu UI dùng tên đó cần map từ `unverifiable` qua adapter hiện
có; không đổi enum âm thầm. Cancel/deadline/budget exhausted vẫn dừng thực thi.
Đây là đề xuất policy semantics; probe chưa nối checker vào stopping/routing
hoặc đánh dấu bundle approved. Không dùng raw heuristic confidence làm đại diện
cho checker result để lách việc khai báo loại tín hiệu trong contract.

### Phần đã kiểm

- `checker_scope_probe.py`: **17/17 authored G24 cases khớp kỳ vọng**, gồm biểu
  thức hợp lệ/phân số chính xác, sai giá trị, sai multiset, thừa/thiếu số, sai
  vế phải, thiếu marker/inputs và syntax không parse được. Gold-field mutation
  không đổi kết quả. Đây là kiểm phần mềm trên ví dụ được tác giả chủ động tạo.
- Ba scope controls xác nhận: phương trình số học đúng vẫn có thể đi cùng
  final answer sai; integer-answer checker không áp dụng chung cho câu hỏi có
  đáp án phân số; ordering witness có thể valid mà chưa trả final answer.
  Đây là giới hạn của contract, không gán cả ba thành bug của checker legacy.
- Bộ hiện có `tests/test_verifiers.py`: **38 passed in 0.34s**, không inference.
  Raw stdout/JUnit ở `verifiers.txt` và `verifiers.xml`.
- `check_saved_g24.py`: hash-pin pilot development ngày 04/10, kiểm cả 8 output
  CoT ở cap 1.024; không chọn câu theo kết quả. **4 valid, 1 invalid,
  3 unverifiable**. Bốn valid khớp stored-correct; bốn còn lại stored-wrong.
  Đây là coverage post-parser trên public expressions, không phải đánh giá
  parser raw response hoặc đo thêm một lần sinh mới. `Answer:` được thêm làm
  adapter cho public answer đã có.

**Giới hạn quan trọng:** checker và procedural scorer đều gọi `check24`.
Việc chúng đồng ý trên 8 câu không phải independent precision/recall validation,
không chứng minh 100% correctness tổng quát và không dự đoán benefit của fallback.
Coverage quyết định được ở đây là 5/8, còn 3/8 không kiểm được. Chưa có matched
fallback outputs cho lát cắt này để tính rescue/harm hay policy value.

### Đối chứng và kết quả cần có trước khi dùng để quyết định nghiên cứu

Giữ fixed initial strategy, fixed fallback **chạy trực tiếp**, cùng initial →
fallback luôn chạy và checker-gated path trên cùng saved outputs khi có đủ
data phù hợp. Tính mọi call trên path, kể cả fallback sai; giữ riêng unknown,
parse/truncation và execution failure. Đây là điều kiện để đánh giá cổng, chưa
phải lệnh bổ sung arms hoặc sửa study protocol trong lượt này.

G24 có solver xác định sẵn: `scripts.gen_tasks.sols24` và implementation DP
trong `scripts.prepare_development_pilot.solve_24`. Cần giữ **query-only solver
baseline** với scope/parser/CPU cost rõ ràng. Solver không dùng model vẫn tiêu
thụ compute. Nếu nó đáp ứng tác vụ tốt hơn, phải báo kết quả đó; không bỏ baseline
để tạo lợi thế cho controller. G24 có thể phù hợp để kiểm contract nhưng không
nhất thiết là family tốt nhất để chứng minh giá trị của LLM routing/stopping.

Trước một phép đo mới: thống nhất scope tín hiệu với runtime/bundle sau repair
parity, reuse existing development review packet, ghi provenance input numbers,
chốt baseline/fallback, model/prompt/caps và ngân sách. Gold/semantic validation
cần tham chiếu độc lập với chính `check24`. Human/data/Stage 0 và execution
freeze vẫn theo protocol hiện hành; không tải/chạy model trong gói này.

Chạy lại các kiểm tra offline, trên source hashes được ghi kèm:

```bash
.venv/bin/python audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/checker_scope_probe.py
.venv/bin/python audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/check_saved_g24.py
.venv/bin/python -m pytest tests/test_verifiers.py -q
```

`checker_scope.json` giữ authored controls/source hashes. `saved_g24_coverage.json`
giữ ID/status, hashes của pilot và checker, không chép raw response hoặc gold.
Historical artifacts được kiểm hash trước/sau và giữ nguyên. Hai script không
fit policy, không đọc held-out candidate, không import/load Qt hoặc model.

## Tham chiếu độc lập và gói dữ liệu để review — 2026-10-23

Đã bổ sung **tham chiếu audit độc lập với parser/nhãn của production** tại
`independent_g24_reference.py`. Giá trị kỳ vọng của biểu thức synthetic được
tính ngay khi dựng cây toán học bằng phân số chính xác. Một interpreter dùng
tokenizer và hai stack kiểm lại giá trị/precedence, không gọi `ast`, `check24`
hoặc hàm production để tạo expected labels. Checker production chỉ được gọi
ở phía cần đối chiếu. Tham chiếu này nằm trong audit, không thay verifier của RAT.

| Bộ số tự tạo | Biểu thức phân biệt | Đúng 24 theo construction | Không đúng 24 | Lệch quyết định chấp nhận |
| --- | ---: | ---: | ---: | ---: |
| 1, 2, 3, 4 | 7.656 | 242 | 7.414 | 0 |
| 3, 3, 8, 8 | 1.890 | 1 | 1.889 | 0 |
| 5, 5, 5, 1 | 1.242 | 2 | 1.240 | 0 |
| 1, 1, 1, 1 | 301 | 0 | 301 | 0 |

Tổng **11.089 biểu thức thuộc bốn bộ số**, với **11.579 lần gọi checker** khi
tính thêm các ca đảo thứ tự inputs và thay sai multiset cho biểu thức đúng.
Mười manual controls kiểm chính tham chiếu, gồm phân số, precedence, sai vế
phải, thiếu số, division-by-zero và syntax thiếu. Không có acceptance mismatch
trong phần grammar hữu hạn này. Các số đếm là software cases phụ thuộc nhau,
không phải 11.089 câu hỏi benchmark độc lập, accuracy mô hình hoặc một chứng
minh đúng trên mọi input. Expression enumeration bỏ các phép chia 0; manual
control riêng kiểm nhánh đó.

Trên tám public answers development cũ, interpreter độc lập xác nhận **bốn
biểu thức valid**, tương ứng bốn ca checker chấp nhận. Bốn câu còn lại ngoài
grammar đọc được của tham chiếu, nên giữ `unverifiable`; checker production
phân loại chúng là một invalid và ba unverifiable. Không sửa classifier tham
chiếu để ép khớp bảng, không gọi đây là full three-state agreement hoặc 100%
independent precision/recall. Raw/private rationale không được đưa vào tham chiếu.

### Đường đi tiếp đã cụ thể

Đã kiểm hash gói review development có sẵn và đối chiếu **8/8** query hashes,
bốn số trong metadata với các operands từ independent-solution proof của gói.
`development_review_index.json` chỉ lập chỉ mục tới tám mục cũ; không tạo
release, đổi splits/golds hoặc tự thêm human approval.

Mở **mục 9–16** trong
[gói review development hiện có](../../../development-pilot-preflight-20261004-runtimefix/review.md)
(bắt đầu ở dòng 121): mỗi mục đã có câu hỏi, reference, independent solution
và chỗ ghi quyết định review. Cần review wording, bốn số/điều kiện dùng số,
solution và source/ownership; ghi người review/ngày/quyết định thật. Mọi trạng
thái human review vẫn pending. Đây là tám nhóm **đã exposed**, phục vụ review
contract/development, không phải test mới hoặc một tập fresh independent.

Sau khi binding được Anti sửa và dữ liệu/phạm vi được review, bước cần chốt là
phép đo development với model/prompt, fallback, per-call/total caps, seed và
ngân sách rõ ràng. Giữ baseline initial/fallback chạy trực tiếp, always-escalate,
checker-gated và solver; kiểm unknown/coverage cùng rescue/harm và mọi cost.
Chưa có quyền gọi model hoặc một campaign freeze mới từ công việc audit này.
Độ đúng checker trong grammar không thay bằng chứng gate giúp quyết định chạy
thêm, và solver baseline có thể cho thấy LLM không cần thiết ở tác vụ hẹp này.

Lệnh tái lập và artifacts:

```bash
.venv/bin/python audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/independent_g24_reference.py
```

`independent_g24_reference.json/.txt` giữ counts, mismatches, per-ID status,
source/probe hashes và historical input hashes. Không lưu lại hàng vạn biểu
thức; generator xác định và source hash cho phép dựng lại. Inputs lịch sử và
source checker khớp hash trước/sau. **0 model calls, 0 fitting, không đọc
held-out candidate.**

## Đề xuất phép đo development sau review — chưa cho phép chạy

Đây là **đề xuất để duyệt**, không phải execution freeze hoặc một main-study
protocol mới. Dùng tám nhóm G24 **đã exposed** trong gói review cũ, một seed 42,
model ứng viên `mlx-community/Qwen3-8B-4bit` revision
`545dc4251c05440727734bcd94334791f6ab0192` theo provenance lịch sử. Model hiện
tại/chọn checkpoint vẫn cần được chốt và kiểm lại trước execution; không load
weights hoặc tải model để lập đề xuất này.

Đề xuất thu outputs cố định qua pilot entry point hiện có: CoT, SC (5 samples),
candidate selection (3 candidates + 1 selector), cap **1.024 token mỗi call**,
prompt/profile và parser được pin theo source sẽ duyệt. Không fit router hoặc
threshold. Tối đa 8 × (1 + 5 + 4) = **80 generation calls / 81.920 generated
tokens** theo cấu hình đó; **0 embedding calls** vì là fixed-strategy pilot.
Đây chỉ là trần completion tokens, chưa phải full inference cost, giá điện
hoặc latency. Không có 80 calls được cấp thêm bởi tài liệu này.

Từ cùng outputs nhận query gốc, so fixed CoT/SC/candidate-selection, đường
luôn chạy thêm và checker-gated ladder; giữ query-only solver baseline, CPU
cost và mọi call phát sinh. Checker chỉ kiểm public output được recipe chọn,
không dùng gold hoặc nhìn trước output chưa chạy. Báo coverage/unknown,
rescue/harm, parse/truncation, generated/prompt tokens và failures. Các seeds/
recipe repetitions không tăng số nhóm độc lập từ tám thành 24 hoặc 80.

Phép đo này chỉ giúp chẩn đoán integration và giá trị của gate trên development
đã xem, không đánh giá đầy đủ H1 hoặc cung cấp held-out benefit. Phải review
wording/gold/input-number provenance/source ownership, pin model/prompts/settings,
xác nhận resource/attempt limits và quyền chạy trước khi thực thi. Failed calls
phải được giữ trong accounting; không tự retry hoặc dùng synthetic fallback.
Nếu collector chưa giữ đủ partial/failure evidence cho cấu hình sẽ chạy, chốt
điều đó trước khi xin ngân sách. Các so sánh chính và gate của main study giữ nguyên.
