# Antigravity — bước tiếp theo của RAT–CoT sau consolidation, 2026-10-20

Thực thi trọn một lượt các phần đủ điều kiện bên dưới, gồm sửa code cần thiết,
kiểm tra, raw evidence và handoff. Đừng chỉ trả kế hoạch hoặc dừng sau bước A.
Khi một bước phụ thuộc thiếu review/ngân sách/môi trường, ghi blocker cụ thể
và tiếp tục các phần offline độc lập. Không cần hỏi lại để làm công việc đã
được giao trong prompt này.

Mục tiêu: đưa controller CoT hiện có tiến gần một luồng RAT có provenance,
execution limits và trạng thái kết quả kiểm tra được; đồng thời chuẩn bị đúng
điều kiện dữ liệu/protocol cho bài NCKH. RAT là implementation chính của CoT;
harness headless cung cấp đánh giá tái lập cho cùng hệ thống.

## 1. Đọc và xác nhận baseline trước khi sửa

Đọc `AGENTS.md`, `docs/project_scope.md`, `docs/research_plan.md`,
`docs/research_protocol.md` và các hướng dẫn thư mục áp dụng. Sau đó đọc:

- `audit/rat_cot_structural_consolidation_review_r3_20261020/review.md` và
  `validation.json`: **consolidation đã được nghiệm thu**, S1/S2/P3 đóng.
  Review r3 nằm trong folder r3; folder r2 giữ raw tests làm bằng chứng.
- `audit/rat_overnight_sweep_codex_review_r7_20261020/review.md`,
  `test_failed_request_reporting.py` và
  `audit/rat_overnight_sweep_codex_repair_r7_20261020/handoff.md`,
  `validation.json`, `repair_diff.patch`, commands/raw logs/JUnit.
- `docs/rat_online_reasoning_20261019.md`, `reasoning/runtime.py`,
  `rat/engine/meta_reasoner.py`, `tests/test_online_reasoning.py` và nơi gọi
  engine/worker thực tế trong RAT.
- `docs/vgc_verification_fix_20261020.md`: dùng trạng thái verifier hiện tại,
  không đưa lại CPA/học phí/confidence/token giả của nhánh legacy.
- `docs/cot_restart_entrypoint_20261019.md`,
  `docs/cot_restart_fresh_adapter_20261016.md` và phần metadata/README của
  `audit/cot_restart_fresh_data_review_20261016/`.

Trạng thái đã biết, cần đối chiếu với checkout:

1. Consolidation đã qua kiểm tra identity/patch/pickle/import isolation và
   source hashing canonical. Không mở lại refactor này hoặc rollback các sửa
   parser/Isotonic sau consolidation.
2. Repair overnight r7 sửa G1 và báo **331/331 pass**. Codex đã chạy độc lập
   **4/4 G1 probes pass**, đối chiếu **51/51 source hashes** khớp r7; chưa
   gọi lần kiểm nhỏ đó là một lần chạy độc lập toàn bộ 331.
3. `OnlineReasoningController` đã chạy với fitted predictor/stopping trong
   synthetic tests, qua injection vào `MetaReasonerEngine(controller=...)`.
   Singleton/UI mặc định chưa dùng controller. `policy_source` là nhãn do
   caller cung cấp, không tự chứng nhận bundle được review.
4. Fresh restart smoke đã có trong `python -m experiments.research_study`.
   Packet 71 items/70 groups vẫn pending independent/human review; chưa có
   reviewed execution freeze hoặc quyền chạy real collection.

Ghi source hashes và dirty status lúc bắt đầu. Nếu source khác baseline, lưu
diff và xác định phần nào do chat khác sửa; giữ nguyên công việc đó. Không
restore source snapshot lên checkout để làm hash hoặc test khớp.

## 2. Quyền thực thi và giới hạn của lượt này

- Làm việc trên `main`. Không commit, tạo branch, push, pull, reset hoặc force.
- **Ngân sách real-model mới = 0.** 12 generation calls cũ đã dùng hết; prompt
  này không gia hạn quota. Không gọi real embedding/generation, cloud provider,
  tải model/dependency, hoặc load real weights trong tests/smoke.
- Stage 0, publication/data gates và execution freeze giữ nguyên. Không bật
  real fresh-data mode hoặc sửa guard để dùng plan/source không tương thích.
- Có thể sửa code offline cần cho B, dùng backend double/fixtures và fit policy
  trên dữ liệu synthetic ghi nhãn rõ. Không gắn fixture policy thành approved
  production policy hoặc dùng nó để chạy model thật.
- Giữ singleton/UI mặc định controller-free cho tới khi có bundle thực được
  review và execution contract đầy đủ. Có thể làm composition path opt-in,
  default-off và kiểm nó với fixture; missing/incompatible bundle phải fail closed.
- Giữ nghiên cứu headless độc lập Qt/personal indexing. Không scan file cá nhân
  hoặc app catalog để thực hiện smoke. Dùng tài liệu/DB/app fixtures.
- Giữ raw audits, run artifacts, nguồn đã freeze và recovery material. Không
  khôi phục DocAI/EVRP/watch bot hoặc mở rộng Spider. Không làm thêm cosmetic UI.

## A. Reconcile và hoàn tất gói overnight r7

Kiểm diff cuối, source hashes, G1 success/failure/partial/zero-dispatch logic,
attempt budget, counters và warm-session scope. Dùng các probe đã có; chỉ thêm
case có ý nghĩa cho gap thực sự còn thiếu. Failed/cancelled attempts vẫn tính
budget; failed requests không được ghi successful/verified.

Đối chiếu bộ 331, parser/scoring và ledger trong r7 với raw XML/log và actual
commands. Lịch sử 12 real calls phải giữ byte-identical, SHA256:

`556fadbbbf87312bc13c5a39b49af226378849579f17816f3cb6228d2e140b34`.

Phân loại riêng: source fix, self-validation, Codex acceptance, native acceptance
và model-quality evidence. Không tự ghi rằng Codex đã nghiệm thu toàn bộ r7
hoặc native cases. Bản ghi mới phải đủ để Codex review trực tiếp sau handoff.
Không rerun campaign hoặc xin thêm calls để sửa reporting.

## B. Hoàn thiện hợp đồng bundle và execution trong RAT

Đọc và tái sử dụng controller, worker, cancellation và execution IDs hiện có;
tránh tạo một engine hoặc model owner thứ hai chỉ phục vụ acceptance.
Triển khai phần còn thiếu đủ để kiểm một đường chạy opt-in end-to-end bằng
fixture qua application worker, không chỉ gọi trực tiếp controller trong test.

### B1. Bundle provenance và compatibility

Tạo schema/validator và composition boundary cho fitted policy. Bundle cần
liên kết được với artifacts/review và có ít nhất:

- model/snapshot, prompt/strategy settings, backend protocol;
- embedding dimensions, feature schema/version, predictor, stopping thresholds,
  confidence/calibrator semantics, lambda và cost metadata;
- source/artifact hashes, dataset/group versions, train/calibration provenance,
  split separation và phạm vi review;
- budget/token semantics, execution mode và các điều kiện tương thích.

Validator phải đối chiếu metadata với policy/backend thực được inject, không
chỉ nhận một chuỗi `policy_source` hoặc nhãn `approved`. Bundle chưa review,
thiếu trường hoặc mismatch phải được báo rõ và không chạy inference. Không
tạo auto-loader pickle/joblib hoặc coi file tùy ý là trusted fitted policy.
Chọn cơ chế tối thiểu phù hợp code hiện có, ghi quyết định và giới hạn.

Fixture dùng policy fit thật trên synthetic train/calibration disjoint và phải
được ghi `synthetic/development-only`. Không dùng candidate held-out data để
fit/tune, không tự sản xuất một bundle “đã human-approved”. Nếu thiếu bundle
thật, vẫn hoàn thành schema/validator/composition/tests rồi ghi native activation
pending với đúng input còn thiếu.

### B2. Worker, budget, deadline, cancel và nguồn

- Chạy controller trong worker; không block Qt main thread. Ràng buộc callbacks
  bằng execution/query generation và resource/artifact identity hiện có.
- Budget phải rõ đơn vị: strategy invocation, underlying generation request và
  generated tokens không đồng nhất. SC/TOT/ReAct có thể có nhiều calls bên trong;
  adapter phải chặn/ghi nhận từng attempt cần charge, kể cả fail/cancel/timeout.
  Embedding/prompt/full inference costs được ghi đúng scope hoặc để unmeasured.
- Cancel/deadline phải ngăn strategy tiếp theo, bỏ callback muộn và giải phóng
  trạng thái đúng. Không gọi `Future.cancel()` là đã dừng backend đang chạy.
  Nếu backend chỉ hỗ trợ cooperative cancel, ghi giới hạn; dùng double điều
  khiển được để kiểm prefill/decode. Không claim hard preemption chưa có.
- Kiểm hỏi lại sau cancel, đổi file/nội dung/document giữa lượt, stale result
  và answer ngoài excerpt. Kết quả phải gắn đúng nguồn/range/version; thiếu
  bằng chứng thì unresolved/abstain, không kế thừa PASS của lượt trước.
- Phân biệt strategy `LLMBackend` với selected-document QA backend. Không giả
  định `MLXDocumentSession` có embedding/strategy/tool contracts chỉ vì có QA.
- UI/trace chỉ thể hiện public execution summaries và observed evidence.
  Không hiển thị raw/private reasoning, model inputs hoặc gắn verified từ
  model confidence. Các state working/done/wait/error/cancel phải phản ánh
  outcome thực tế, không dùng canned answers để thay backend failure.

### B3. Native acceptance readiness

Tạo ma trận cases với fixture, entry point, expected outcome và evidence type:
token streaming, cancel prefill/decode, hỏi sau cancel, đổi file/document,
outside-excerpt/unresolved, failure/timeout và callback muộn. Nêu cách đo queue,
load/prefill/decode, first displayed text và submit-to-done nếu instrumentation
thực sự có. Null cho phase chưa đo; generated-token cost không phải full cost.

Chạy phần fixture/offscreen đủ điều kiện. Native UI interaction không gọi model
có thể kiểm nếu môi trường sẵn và không đụng dữ liệu/hành động cá nhân. Không
khởi động UI test với autoload/warmup model thật; inject double và kiểm đường
startup trước khi mở cửa sổ. Không
gọi screenshot offscreen là native acceptance. Các case cần real inference giữ
`not-run: no remaining authorized real-model budget`. Chuẩn bị execution plan
có danh sách cases/caps/ledger/output cụ thể để user review sau, không tự chọn
quota hoặc chạy thêm một request “chỉ để thử”.

## C. Chuẩn bị dữ liệu/protocol NCKH, giữ blind review và các gate

Rà metadata, hashes, group frame và review workflow của packet 71/70 đã có;
không xuất toàn bộ pending held-out queries/gold vào context triển khai.
Không sửa parser/controller/prompts theo nhãn held-out. Tách human review
questions/gold khỏi quá trình phát triển; bản xuất đã có phải giữ nguyên.

Tạo hồ sơ ready-for-review gồm:

1. Index nguồn và checklist human reviewer: ownership/license, gold rationale,
   grouping/variants, known prior exposure, quyết định từng item/group. Nếu
   chưa có reviewer evidence thì giữ pending, không thay human review bằng
   một lần agent đọc hoặc chỉ chạy schema checker.
2. Kiểm structural leakage/split/identity và artifact integrity bằng code hiện
   có; báo phạm vi kiểm, không claim đã loại toàn bộ pretraining contamination.
3. Draft freeze checklist cho group representatives, sample size/power,
   primary F−CONT/F−O comparisons, O/F/CONT/A settings, seeds/caps/cost scope,
   practical margin và versioned decision implementation. 70 candidate groups
   không phải cỡ mẫu đã chứng minh đủ power. Không tối ưu theo observed test.
4. Bounded real-execution plan **chưa được authorize**, chỉ rõ các review,
   model/backend compatibility và Stage 0 còn thiếu. Có thể làm sensitivity/
   power calculations trên assumptions hoặc synthetic data có nhãn; không tự
   phê duyệt thiết kế hay đổi pending thành frozen/approved.

Tiếp tục dùng `python -m experiments.research_study` làm entry point nghiên cứu.
Fresh smoke hiện là synthetic-only; giữ real execution disabled. Không dùng
lại 12 câu/plan lịch sử như frame mới, không nới source guards để chạy dưới
code mới. Reviewer-facing packet phải chỉ rõ phần nào có thể làm offline và
phần nào cần quyết định/human review.

## 3. Kiểm thử và bằng chứng

Trước khi chạy, đọc commands/tests hiện có và kiểm output dirs. Không ghi đè
review/repair cũ. Không chạy script native mù vì có thể hardcode model/path.

Checks bắt buộc khi đổi harness/threshold-related code:

```bash
.venv/bin/python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Chạy các tests có ý nghĩa cho phần sửa, gồm online reasoning, worker/cancel,
bundle rejection/compatibility, verifier và fresh smoke nếu bị ảnh hưởng.
Thêm cases cho mismatch/missing review, hết budget giữa các subcalls, timeout,
cancel giữa rung, late callback và hỏi tiếp. Test bằng deterministic doubles,
không wall-time assertions dễ flaky và không gọi model thật.

Một lần regression cuối trên source cuối, dựa trên selectors của bộ 331 và
tests mới liên quan. Dùng output mới; redirect fixtures/ảnh của audit tests
bằng cơ chế như các wrapper review gần đây, không thay assertions. Không
hardcode “331 pass” nếu collection/counts thay đổi; phân biệt subset để khỏi
cộng trùng. Không rerun full 132-file sweep nhiều lần; lỗi cũ chỉ mở lại khi
thay đổi đợt này chạm đúng contract, giữ backlog còn lại có evidence.

Lưu command/argv, env, exit codes, stdout/stderr thô và JUnit. Không ghi log
bằng echo các dòng pass hoặc sửa expected/gold để lấy xanh. Giữ các lần fail,
ghi passed/failed/skipped/blocked/timeout đúng thực tế. Hai native MLX bfloat16
tests có thể skip tùy môi trường; không tính skip thành pass.

Mọi hash/baseline tham chiếu phải có snapshot; thay source thì tạo version mới.
Software tests, fixture/offscreen interaction, native application measurements
và model-quality comparisons phải được phân loại đúng trong cùng evidence map.

## 4. Handoff cuối cần cụ thể và review được

Tạo folder mới, ví dụ `audit/rat_cot_runtime_acceptance_20261020/`; nếu đã tồn
tại thì dùng suffix riêng, không ghi đè. Ít nhất có:

- `handoff.md`, `validation.json`: completed/pending theo từng phần A/B/C;
- source_start/end hashes, reviewed source/diff và unrelated changes đã giữ;
- commands/env/exit codes, raw logs/JUnit, unique counts/subsets;
- bundle schema/compatibility matrix, specimen synthetic có nhãn và các kết
  quả từ chối/cho phép composition thực;
- worker/budget/deadline/cancel evidence và native case matrix có status thật;
- data-review index + pending-human-review/freeze checklist, kế hoạch real
  execution chưa được authorize;
- `rat_cot_evidence_map.md`: method → canonical/runtime → harness counterpart
  → contracts/verification/stop/budget → raw evidence → claim/limit;
- artifact manifest và đối chiếu hash các audits/12-call ledger cần bảo toàn.

Kết thúc bằng phần đã chạy được, phần chưa đủ gate, blocker/input chính xác
và đường dẫn để Codex review. Có thể hoàn tất toàn bộ delivery offline khi
native/data gates còn pending; không ghi “toàn hệ đã nghiệm thu” hoặc
“thực nghiệm NCKH đã xong” từ test counts. Không tự gửi tin sang chat khác,
publish/upload hoặc bật mặc định điều kiện chưa được review.
