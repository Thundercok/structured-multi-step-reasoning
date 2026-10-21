# Antigravity — một lượt duy nhất: vòng 3 + VFP V1–V6 + overnight toàn hệ

Yêu cầu trực tiếp của người dùng ngày 2026-10-19: cho Antigravity chạy một lượt
overnight sweep; “cho chạy được gì chạy hết 1 lượt … vì tôi ngủ sẽ rất lâu”.
Thực thi các phần có đủ điều kiện, lưu kết quả đến đâu chắc đến đó và tiếp tục
các phần độc lập khi một phần bị lỗi/thiếu môi trường. Không chỉ trả kế hoạch.

**Giao việc hợp nhất, đã được người dùng xác nhận:** thực hiện liền một lượt
gồm **review vòng 3 → toàn bộ visual_refinement_plan.md (V1–V6) → full overnight
sweep → native/performance/evidence → handoff cuối**. Đây là một công việc có
nhiều bước, không phải các đề xuất chờ duyệt lần lượt. Không dừng sau F2, sau
263 tests hay sau một mục V để hỏi có tiếp tục không; tự chuyển bước trong phạm
vi đã giao. Nếu còn failure sau sửa, tiếp tục chẩn đoán/sửa và kiểm đúng phần
ảnh hưởng; phần bị blocker không ngăn các phần độc lập còn lại.

## 1. Một hệ thống, một mục tiêu nghiên cứu

**RAT SỬ DỤNG CoT; CoT ĐƯỢC THỂ HIỆN BẰNG RAT. RAT là implementation chính
của phương pháp trong đề tài NCKH.** Không tách RAT thành demo phụ hoặc một dự
án ngoài NCKH. Reasoning, routing, verification, stopping, budget, execution
contracts và evidence trong RAT đều là core khi phục vụ phương pháp.

Đọc `AGENTS.md`, `docs/project_scope.md`, `docs/research_plan.md`,
`docs/research_protocol.md` và hướng dẫn trong các thư mục định sửa. Harness
headless đo tái lập phương pháp đang được triển khai trong RAT; bài NCKH sử dụng
các artifacts có provenance của cùng hệ thống này.

Phân biệt software acceptance, native application measurements và so sánh chất
lượng mô hình để gắn đúng claim vào đúng bằng chứng. Giữ Stage 0, dữ liệu/split,
execution freeze của từng campaign theo protocol. Chạy mọi smoke/offline check
đủ điều kiện; campaign chưa đủ gate/freeze phải ghi pending với lý do cụ thể,
không đánh dấu pass và không dùng blanket overnight request để tự vượt gate.

## 2. Baseline mới nhất và quyền làm việc

Bản bàn giao mới báo đã sửa F1–F5 của vòng 2. Codex đã chạy độc lập đủ **263
tests pass** trên source mới, gồm cả 7 probe vòng 2, với Qt offscreen và
model/launcher mock. Source và probe cũ được hash đối chiếu.

Review vòng 3 phát hiện **F2 còn một ca P2**: UDF SQL xét summary đầy đủ nhưng
metadata projection cắt summary còn 200 ký tự. PDF có chỉ báo `slide` ở ký tự
301 được SQL nhận rồi bị `SearchFilters.accepts()` loại sau projection. Sửa
ca này và kiểm tra regression trước khi chốt F2. Không làm nặng đường tìm bằng
cách trả full content hoặc thêm inference. Giữ nguyên probe mới ở
`audit/rat_milestones_abc_review_r3_20261019/test_slide_summary_projection.py`.

Đọc các bằng chứng và giữ nguyên lịch sử:

- `audit/rat_milestones_abc_independent_review_20261018/review.md`
- `audit/rat_milestones_abc_review_r2_20261018/review.md`
- `audit/rat_milestones_abc_review_r2_20261018/test_additional_headless.py`
- `audit/rat_milestones_abc_review_r2_20261018/test_additional_ui.py`
- `audit/rat_milestones_abc_review_r3_20261019/` — kết quả 263 tests độc lập và
  probe F2 summary projection mới, gồm short-summary control.
- `audit/rat_overnight_sweep_handoff_20261019/handoff_source.json`
- `/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/visual_refinement_plan.md`
- `audit/rat_overnight_sweep_handoff_20261019/visual_reference/` — snapshot plan,
  metadata và 5 ảnh Qt offscreen đã xem; đây là reference trước refinement,
  không tự coi là ảnh acceptance trên source sau các sửa mới.

Sửa mới nhất nằm ở `rat/crawler/db.py`, `rat/engine/finder_intent.py`,
`rat/engine/work_trace.py`, `rat/ui/omnibar.py`, `rat/ui/workbench_scene.py`.
Kiểm lại source trước khi ghi và phát hiện drift từ các chat đang làm chung.

Giữ `main`; không commit/push/pull/reset/force hoặc tạo branch. Không xóa/sửa
raw audits, reviewed snapshots, recovery hoặc thay assertion của probe cũ.
Giữ cờ experimental mặc định tắt. Không khôi phục DocAI/EVRP/watch bot/Spider
vào startup. Mọi tệp và DB nghiệm thu phải là fixture tổng hợp trong audit/tmp,
không index tài liệu cá nhân, không thay settings cá nhân để chạy test.

Cho phép chẩn đoán và sửa lỗi có căn cứ trong phạm vi hệ thống, gồm lỗi phát
hiện mới trong sweep, rồi kiểm tra đúng phần đã sửa. **Tiếp tục đầy đủ plan
V1–V6 được handoff dẫn tới**, theo yêu cầu người dùng phải đọc và nối tiếp cả
handoff lẫn plan. Không mở rộng sang redesign ngoài các quyết định đó, đổi
mascot hoặc thêm tính năng không liên quan.

## 2a. Thực thi Visual Refinement Plan V1–V6

Làm sau kiểm tra/sửa correctness đang mở, trước native acceptance và ảnh cuối.
Phải đọc source hiện tại, đối chiếu từng ảnh/reference rồi triển khai; không
thay plan bằng một vòng chạy test chung. Ghi trạng thái và evidence từng V.

- **V1 — QSS source cards:** sửa object-ID chứa dấu `:`, `/`, `.` làm hỏng
  selector; dùng ID an toàn, ổn định, tránh collision giữa các resource. Giữ
  nguyên resource_id/artifact identity, focus và hành động Mở tệp. Chụp lại
  source card/button cả light/dark, không chỉ assert stylesheet string.
- **V2 — bỏ hiển thị nguồn/câu trả lời trùng:** source-read artifacts
  `document_content`, `book_page_content`, `document_search`, `book_page_search`
  đã có SourceCard/ExcerptCard thì ẩn renderer ở overview, **vẫn giữ renderer
  instance** để source_detail mượn lại, giữ selection/scroll/revision. Khi speech
  bubble hiện đủ câu trả lời và không có interactive/non-source artifact hoặc
  revision transition, thu gọn/ẩn ResultDeskCard. Vẫn populate answer_lbl;
  hiện card khi streaming, bubble truncated, cần tương tác hoặc revision đổi.
  Không xóa answer, artifact hoặc nguồn để làm gọn; giữ renderer identity và
  source-detail/back state. Kiểm đủ done/wait/error/cancel/long answer.
- **V3 — clipping:** wrap/elide candidate labels và trace trong viewport;
  đường dẫn rút gọn phải **vẫn phân biệt được từng bản cài**, full path giữ
  trong tooltip/payload. Không cắt cụt dữ liệu execution hoặc đổi candidate ID.
  Kiểm geometry/visibleRegion ở desktop/420px, light/dark.
- **V4 — Finder:** chips ngắn, scope banner giải thích rule một lần; giữ
  filter/date/scope/error rõ ràng. Hiện toggle trace nhẹ khi Finder có grounded
  structured flow, kể cả phase empty; bare query không tạo trace giả. Không
  đổi semantics parser hoặc thêm model call để làm đẹp projection.
- **V5 — theme/thought trail:** dùng theme tokens cho source/result/title và
  ba chấm, kiểm pixel light/dark và reduced motion. Giữ asset/tỷ lệ mascot.
- **V6 — font alias/startup:** xác định nơi thực sự dùng Sans Serif và fallback,
  thay bằng FONT_FAMILY phù hợp nền tảng. Ghi log trước/sau và startup timing
  trên điều kiện matched; không khẳng định giảm 110–220 ms chỉ từ việc hết log.

V2 là thay đổi visibility/projection trong cùng Workbench, không phải chuyển
nguồn/câu trả lời sang panel hay composer thứ hai. Tests cần kiểm các điều kiện
visibility và dữ liệu vẫn truy cập được; không sửa yếu assertion cũ cho xanh.

## 3. Một lượt sweep — không dừng ở bộ 263 tests

Tạo thư mục audit mới có timestamp, không ghi đè thư mục cũ. Đầu tiên lưu:
git head/branch/status, source hashes, môi trường/dependencies sẵn có, model
local thực tế, phiên bản/checkpoint và toàn bộ queue dự kiến trong `plan.json`.
Lưu `progress.json` và log riêng mỗi task để tiếp tục được nếu agent ngắt.

### A. Test toàn bộ mã active

- Inventory tất cả `tests/test_*.py` và root `test_*.py`. Collection có timeout,
  chạy active tests một lượt, theo process/file hoặc nhóm hợp lý để một import
  lỗi/hang không làm mất phần còn lại. Không thu thập tests từ historical
  `audit/**/reviewed_source`, recovery, scratch, legacy hoặc modules đã gỡ.
- Thêm các acceptance probes đang active từ hai vòng review và Finder/keyboard
  trước đó. Giữ bảng case IDs để không cộng trùng test giữa các nhóm.
- Bắt buộc bao phủ 263 tests của bàn giao. Danh sách lệnh gốc nằm trong
  `audit/rat_milestones_abc_review_r2_20261018/commands.json`; thêm hai file
  `test_additional_*.py` vào bộ đó. Nếu 245 active regression đã chạy trong full
  pass, chỉ chạy thêm 18 audit probes, không lặp cả baseline vô ích.
- Thêm hai ca `test_slide_summary_projection.py` của vòng 3 và tests có ý nghĩa
  cho V1–V6; báo unique counts thực tế, không cố giữ nhãn 263 khi bộ đã mở rộng.
- Kiểm tra bộ headless/research, reasoning/controllers/verifiers, DB/FTS/index,
  document intake, lifecycle/receipts, UI/Finder/keyboard, worker/cancel/quit.
- Không âm thầm bỏ `test_memory_sentinel`, `test_omnibar` hoặc test treo. Ghi
  collection/runtime timeout, diagnostic và điều kiện thiếu; tiếp tục nhóm khác.
  Phân biệt failed, skipped, blocked, timeout, not-collected và passed.
- Không cài/download dependencies hoặc model mới. Không dùng cloud/network
  provider. Live-test nào cần dịch vụ không sẵn có thì ghi unavailable; không
  gọi model thật từ test suite ngoài native-call ledger đã khóa bên dưới.
- Sau fix chỉ rerun phần bị ảnh hưởng và checks bắt buộc. Một lần regression
  cuối cho source cuối khi có thay đổi; không retry cùng test nhiều lần để lấy
  một lần xanh. Giữ các lần fail.

### B. Smoke và consistency toàn hệ

- Chạy supported entry point `python -m experiments.research_study --help`, rồi
  các synthetic/mock/replay smoke đã có protocol và không phát sinh model calls.
  Kiểm tra flags/output paths trước khi chạy; không gọi campaign mặc định mù.
- Kiểm train/calibration/test group disjointness bằng fixture/offline checker,
  verifier/stopping/budget semantics và artifact hash checks hiện có. Không fit
  lại threshold trên test hoặc sửa nhãn/dataset đã freeze để làm xanh.
- Giữ nghiên cứu headless độc lập Qt/personal indexing; kiểm lazy import/fast
  finder không nạp model/embedding và không scan app catalog theo từng phím.
- Chạy CLI/document intake smoke trên fixture. Nếu OCR engine sẵn có, thử fixture
  scanned PDF; nếu không sẵn thì báo thiếu điều kiện, không tải engine/model.
- Chạy lint/build/manuscript validation hiện có nếu đủ dependencies. Không sửa
  claim khoa học bằng test count, không xuất bản/upload gì.

### C. Native RAT và các trạng thái thực

Kiểm trong cùng composer/Workbench:

1. Slide DSA + loại file + tuần lịch + Unicode/không dấu; cả ngày tạo/ngày sửa,
   `đã tạo`/`created`, cận timestamp lẻ và mismatch tổ tiên trước LIMIT.
2. Báo cáo mới nhất: content-only report, sort trước limit, stale/missing index.
3. App: bare query không mở; partial phải chọn; exact/alias; hai bản cài; phủ
   định; app bị xóa/executable mất; OS từ chối. Mock launch cho regression;
   không tự mở game. Có thể dùng app fixture vô hại cho OS smoke nếu đủ điều kiện.
4. Selected QA: read đúng nguồn/range, token stream, scoped verification,
   truncation/abstention, error, cancel, callback muộn, hỏi tiếp và đổi nguồn.
5. Sau QA chuyển sang direct action ở success/wait/error: trace dùng đúng
   execution/resource/artifact/receipt, không kế thừa PASS của lượt cũ.
6. Key/input, first usable hit và paint theo query/generation: empty snapshot
   không tính hit, semantic update không ghi đè, query/reset/cancel vô hiệu mốc cũ.
7. Keyboard/IME, draft/caret/selection/focus/scroll, source detail, stop/reset,
   quit và không để composer bị đẩy khỏi màn hình.

Giữ `thinking=False`; UI chỉ hiển thị public explanation/observed evidence,
không raw/private thought, raw_completion, model_input hoặc reasoning tokens.

## 4. Model thật và performance: chạy một lượt có ledger

Yêu cầu mới cho phép overnight sweep và mở rộng khỏi lát cắt smoke 5 calls cũ.
Không chạy lại benchmark 126 calls lịch sử hoặc campaign chất lượng mô hình.
Chỉ dùng checkpoint local đã cài/cấu hình, một model owner/service, không thêm
provider hoặc tự chọn model khác khi lỗi. Tách adapter selected QA và general
agent protocol; không giả định native QA adapter đã hỗ trợ tool calling.

Khóa danh sách native cases trước inference: cold-short, warm-short,
long-excerpt, changed-file, changed-document, answer-outside-excerpt,
cancel-during-prefill, cancel-during-decode, ask-after-cancel. Mỗi case tối đa
một request; dùng fake backend cho timing/cancel stage không điều khiển được
chính xác bằng native và ghi rõ loại bằng chứng. Thêm tối đa ba matched
before/after requests cho cold-short/warm-short/long-excerpt **chỉ khi thực sự
sửa performance giữa hai lần**. Tổng hard cap **12 real generation requests**,
kể cả failed/cancelled/truncated; tối đa 640 output tokens/request, timeout
90 s/request theo session hiện có. Ghi `calls.jsonl` ngay trước mỗi request;
không gọi thêm để paraphrase trace, chụp ảnh hoặc che một câu trả lời sai.

Nếu không đổi performance, mỗi native scenario chỉ chạy một lần. Nếu không
đủ model/native environment, ghi blocker và hoàn tất software/fixture phần khác.

Đo cùng fixture/model/prompt/budget, ghi rõ cold/warm và tải đang hoạt động:

- Key → editor, query → first usable hit, delivery → paint; báo event boundaries,
  query ID/generation và số mẫu. Phân biệt slot time với input/UI latency.
- QA: read, queue, load, tokenize, document-prefix prefill, question-suffix
  prefill, cache copy, generation/decode, first displayed text, submit → done;
  prompt/output tokens, prefix reuse và số calls. Phase chưa đo được ghi null/
  chưa đo. `prefill_ms=0` của prefix cache không chứng minh suffix không prefill.
- Idle CPU và process RSS/current memory; ghi peak RSS riêng. `ru_maxrss` là peak,
  không gọi nó là current RAM. MLX allocation báo riêng, không thay tổng RAM.
- Ghi individual real-model samples; không suy p95 từ vài lượt. UI synthetic
  nhiều mẫu có thể báo median/p95 kèm n và cách đo. Không đặt wall-time asserts
  flaky vào unit tests. So sánh trước/sau chỉ khi điều kiện thực sự matched.

Đọc scripts hiện có trước khi tái sử dụng. Ví dụ
`scripts/run_native_document_ui_session.py` đang hardcode model/output audit
cũ và `scripts/profile_rat_latency.py` dùng Ollama path. Không chạy mù hoặc ghi
đè evidence cũ; chuẩn hóa output dir/args tối thiểu khi cần.

## 5. Bằng chứng chung cho RAT và bài NCKH

Tạo `rat_cot_evidence_map.md` với các cột:

`method component → reasoning/runtime implementation → harness counterpart →
contract/verifier/stop/budget → tests/native runs → raw artifact → claim được hỗ trợ`.

Nêu rõ phần đang thực sự dùng chung, adapter khác nhau và phần chưa nối/chưa đo.
Đừng suy tương đương từ tên CoT/controller. Native timing là application evidence;
replay timing là replay; model-quality comparison cần dữ liệu/protocol phù hợp.
Đây là các lớp bằng chứng cho cùng dự án, không phải chia RAT và NCKH thành hai hệ.

## 6. Ảnh, thời hạn và handoff cuối

Ảnh desktop/narrow 420px, light/dark/reduced-motion, working/done/wait/error,
thought bubble, nguồn và trace thực tế. Ghi rõ `qpa_platform=cocoa` cho native;
offscreen/QWidget.grab/fixture replay phải có nhãn đúng. Không chụp nội dung cá
nhân hoặc gọi fixture replay là native IME/live model acceptance.

Một lượt toàn queue, không lặp vô hạn hoặc chạy thêm chỉ để kéo dài qua đêm.
Wall-clock tối đa 12 giờ; xong sớm thì kết thúc. Đặt timeout hữu hạn theo task,
ghi stdout/stderr/JUnit và tiến độ. Một task treo không được chặn mọi task sau.
Chỉ dừng process do lượt này tạo; không kill daemon/model/process của chat khác,
không đổi sleep/power settings của máy. Cho phép STOP marker trong audit để
dừng trước task/request tiếp theo, flush logs và giữ mọi artifact.

Handoff cuối gồm:

- source start/end và drift, diff của sửa thực tế, commands và unique test counts;
- F1–F5/R1–R8: fixed/remaining, ca mới và giới hạn;
- V1–V6: thay đổi, điều kiện visibility/identity, ảnh trước/sau và kết quả;
- full queue: pass/fail/skipped/timeout/blocked, không bỏ các failure;
- CPU/RAM và latency với phạm vi/cỡ mẫu, native calls/tokens ledger;
- ảnh có nhãn, evidence map dùng cho bài NCKH, việc chưa kiểm chứng;
- công việc tiếp theo cụ thể để Codex review. Không tuyên bố toàn hệ đạt chỉ từ
  263 tests; không gọi pending campaign là đã qua Stage 0.

Chỉ kết thúc với một báo cáo hợp nhất: vòng 3, từng V1–V6, full sweep,
native/performance và evidence map đều có trạng thái/kết quả/artifact cụ thể.
Nếu một phần thực sự không chạy được, ghi blocker và phần đã hoàn thành;
không giấu hoặc gọi toàn bộ lượt là hoàn tất thành công khi còn phần pending.

Người dùng đang ngủ: tự giải quyết lựa chọn kỹ thuật thường lệ trong phạm vi
trên. Nếu thiếu quyền truy cập/model/môi trường, ghi lại và làm các phần độc lập;
không dừng ở câu “đang chờ test” khi vẫn còn việc trong queue có thể thực hiện.
