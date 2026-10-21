# Independent review — RAT–CoT overnight repair, 2026-10-19

**Kết luận: request changes. Chưa đạt PASS / READY FOR INTEGRATION.**

Đã chạy độc lập **271/271 pass**: 265 regression cũ + 6 visual probes giữ nguyên.
Đã đối chiếu đủ 132 active test files, 132 JUnit và raw logs: **1.685 pass,
19 fail**, không có sai lệch count giữa XML và inventory. Đây là tiến bộ thực
so với bàn giao trước. Tuy nhiên, kiểm tra tiếp tái hiện startup crash, mất câu
trả lời sau navigation và nhãn bản cài trùng nhau; native queue/performance và
evidence map còn giới hạn cần sửa trước khi kết luận hoàn tất.

## Các phát hiện

### R1 — [P1] System tray crash trên đường khởi động resident, không phải legacy test failure

Vị trí: `rat/os/menu_bar.py:107–119`; caller `rat/os/app.py:389`.

Stylesheet đã được chuyển thành f-string để chèn `FONT_FAMILY`, nhưng các block
`QMenu::item`, `QMenu::item:selected`, `QMenu::separator` vẫn dùng brace đơn.
Python cố nội suy `{ padding: ... }`, gây **NameError: name 'padding' is not defined**
ngay trong `SystemTrayManager()`.

Đã tái hiện độc lập bằng test đang có
`tests/test_crash_shield.py::TestCrashShield::test_system_tray_manager_shutdown`.
Đây không chỉ là một expectation cũ: `ResidentApplication.run()` tạo tray không
có catch tại điểm này, trước app event loop; đường GUI/resident dùng constructor
này sẽ không khởi động hoàn chỉnh. Working diff với HEAD xác nhận đổi stylesheet
sang f-string mà chỉ escape block QMenu đầu tiên. Source này đã lỗi từ snapshot
overnight trước, không phải do bốn-file repair mới; vẫn là blocker trong scope
overnight và V6, không được miễn bằng nhãn legacy/staging.

Sửa brace toàn bộ stylesheet hoặc tránh nội suy các CSS block. Giữ test lifecycle
và kiểm resident initialization bằng fixtures, không bật personal indexing hay
hotkeys thật. Log độc lập nằm trong `followup.txt` / `followup.xml`.

### R2 — [P2 / V2] Câu trả lời biến mất khỏi cả hai nơi hiển thị sau source-detail → back

Vị trí: `rat/ui/omnibar.py:2450–2452`, logic tương tự ở khoảng dòng 5065;
`rat/ui/workbench_scene.py:3672–3680`. Đường mode-back ở `OmnibarWindow._on_scene_mode_changed`.

Điều kiện `bubble_has_full_answer` đọc **_copy_text** trước `dialogue.text()`.
Copy buffer có thể chứa nguyên answer dù bubble đang hiển thị status
“Mình đã đặt kết quả và nguồn tham chiếu trên bàn. Chạm nguồn để xem chi tiết.”
và `_truncated=False`. Khi đó card bị ẩn dù câu trả lời không thực sự nằm trong
bubble. Mode-back đổi nội dung bubble mà chưa reconcile visibility card.

Tái hiện: selected-file QA trả `LOTUS-7319` → ban đầu bubble đủ answer, card ẩn
đúng → mở source detail → quay lại overview. Bubble chỉ còn status, card vẫn ẩn;
answer chỉ nằm trong copy buffer/hidden label. Refresh qua `_sync_workbench_scene`
cũng gây mất answer khỏi màn hình.

Hai ca navigation/refresh fail; control trạng thái ngay khi vừa trả lời pass.
Cần xác định visibility từ **nội dung đang render**, có chuẩn hóa formatting phù
hợp, và cập nhật đồng bộ khi bubble/mode/snapshot thay đổi. Nếu bubble không
hiện answer, hiện card hoặc phục hồi answer vào bubble; vẫn giữ answer_lbl,
renderer identity và source-detail state.

### R3 — [P2 / V3] Parent-folder basename không bảo đảm phân biệt hai bản cài

Vị trí: `rat/ui/view_renderer.py:292–298`.

Code tính common/relative path nhưng bỏ kết quả khi parent có tên; chỉ dùng
`Path(p).parent.name`. Với `/Applications/League of Legends.app` và
`/Users/fixture/Applications/League of Legends.app`, cùng version, cả hai button
đều có nhãn **Applications · League of Legends · v1.0**. Đây là cặp system/user
installation thường gặp, không phải vấn đề chỉ xảy ra với chuỗi dài bất thường.

Probe mới fail ngay cả khi so toàn bộ text; tooltip vẫn giữ full path. Control
Applications/Riot Games pass, phù hợp với 6 probe cũ. Cần tìm suffix/relative path
ngắn nhất còn unique trong toàn bộ candidates, xử lý collisions trước khi
elide/wrap và giữ execution payload/index nguyên vẹn.

### R4 — [P2] Phiên 12 lượt backend chưa thay được native scenario queue và ledger chưa checkpoint trước request

Vị trí: `scripts/run_native_performance_session.py:121–208`;
scope gốc `docs/prompts/antigravity_overnight_rat_cot_sweep_20261019.md:192–204`.

12 record nhận được đều status success, completion 20–44 tokens, latency dưới
90 s; tổng **370 completion tokens**. Không phủ nhận các kết quả backend đó.
Nhưng script hỏi 12 fact questions trên cùng một tài liệu, không đổi file/source,
không tạo long-excerpt/outside-excerpt case, không hủy prefill/decode hay hỏi sau
hủy. Script chỉ tạo QApplication, không tạo OmnibarWindow và không đưa stream
vào UI. Vì vậy đây là **real-model backend smoke**, chưa nghiệm thu native
composer/stream/cancel/source-switch/paint theo queue đã giao. Offscreen screenshots
là một lớp bằng chứng khác trong cùng RAT–CoT, không nối thành live UI acceptance
chỉ vì backend riêng đã trả lời thành công.

Ngoài ra, `calls.jsonl` được mở bằng `w` rồi chỉ ghi sau khi request trả về. Nếu
process dừng giữa generation, attempt đó không có trong ledger; chạy script lại
sẽ xóa lịch sử cũ. Không có pre-request request ID/start event hay durable global
budget accounting như scope đã yêu cầu. Hiện có thể kiểm 12 record, chưa thể dùng
cách ghi này để chứng minh mọi interrupted attempt đã được tính.

Giữ nguyên ledger, xem ngân sách 12 lượt đã dùng hết; **không tự chạy thêm model**.
Sửa instrumentation/ledger bằng fake backend và append/checkpoint trước request,
test interruption/resume/double-run không gọi model thật. Các scenario chưa chạy
phải ghi not-run/blocked; phần cần thêm real generation để nghiệm thu về sau cần
ngân sách mới. Không chạy lại 12 câu để lấy một gói xanh khác.

### R5 — [P2] Telemetry còn trộn CPU toàn máy, prefix prefill và latency ứng dụng

Vị trí: `scripts/run_native_performance_session.py:218–220`,
`audit/rat_overnight_sweep_repair_20261019/handoff.md:123–135`.

`psutil.cpu_percent(interval=1.0)` đo CPU toàn hệ thống; nó không phải
`psutil.Process().cpu_percent(...)`. Vì vậy **57,8% không phải idle CPU của RAT**.
Đọc RSS hiện tại/peak của process có phép đo thực, nhưng process này là runner
backend, không phải resident app/Workbench. Thu thập CPU app cần process scope
và idle window xác định; chưa đo thì null, số host giữ dưới tên host CPU.

`prefill_ms=0` ở lượt warm chỉ là **document-prefix đã chuẩn bị**:
`MLXDocumentSession.chat_with_meta` gọi backend generate với
`full[len(prefix):]`; `generation_ms` bao gồm phần question-suffix xử lý trước
token đầu tiên. Handoff cần nói rõ suffix prefill chưa được đo riêng. Cold/warm
là các câu hỏi khác nhau, nên chưa là matched before/after proof cho cache speedup.
Warm samples thực có range **4.635,92–47.359,53 ms**, median **6.364,26 ms**, gồm
cả call 8 ở **31.830,36 ms**, không chỉ một outlier 47,3 s.

Cảnh báo font 203 ms lần này được thu thật, không còn hardcode 0. Tuy nhiên nó
xuất hiện ở QApplication/font probe trước khi tạo bất kỳ RAT window nào. Nó
chưa phải matched startup-to-first-paint của app hay bằng chứng một stylesheet
cụ thể còn gây 203 ms. Không có marker paint, editor/hit latency hoặc first
displayed UI text trong phiên này. Giữ raw warning và ghi đúng phạm vi phép đo;
không suy ra chi phí font bằng 0 cũng không gán toàn bộ warning cho app chưa chạy.

### R6 — [P2] Evidence map vẫn có symbol không tồn tại, dù tuyên bố AST chính xác 100%

Vị trí: `audit/rat_overnight_sweep_repair_20261019/rat_cot_evidence_map.md:31,67`;
`handoff.md:170`.

Đã rút claim receipt dừng decode/giảm token và giới hạn recall: đúng hướng.
Nhưng `UnifiedDispatcher` không tồn tại trong `rat/kernel/dispatcher.py`
(class thật là `ActionDispatcher`), `CandidateChoiceButton` không có class
definition trong renderer, và `_execute_launch_app` không được định nghĩa trong
applications capability. AST check giữ tại `map_symbol_checks.json`.

Thay bằng symbol/call path thật hoặc ghi rõ đó là tên mô tả component. Map
shared production kernel khác với “harness đang gọi cùng code”; các ô telemetry
phải trỏ tới sample/artifact có thật, không suy measurements từ việc một test
import module. RAT vẫn là implementation chính trong cùng hệ NCKH; cần ghi đúng
trạng thái adapter/shared/not-wired thay vì suy tương đương qua tên component.

## Trạng thái các phát hiện trước

| Phát hiện cũ | Kết quả lần này |
| --- | --- |
| O1 — evidence/claims | Đã rút claim decode stopping/100% recall; còn R6 về symbol/provenance |
| O2 — hardcoded performance | Đã có raw Qt warning và readings thật; còn R5 về measurement boundaries |
| O3 — full sweep/native queue | 132-file sweep đã có log/XML và counts đúng; 19 fail cần triage, native coverage còn R4 |
| O4 — V2 | 2 probe cũ pass; navigation/refresh phát sinh R2 |
| O5 — V3 | 2 probe cũ pass; same-parent-basename collision còn R3 |
| O6 — V4 | Đóng trên 2 probe cũ; structured flow hiện toggle, bare query không tạo trace giả |
| F2 vòng 3 và các correctness probes cũ | Vẫn pass trong bộ 271 |

## Xử lý 19 fail trong full sweep

Inventory và raw logs khớp nhau; không cần chạy lại toàn bộ 132 files chỉ để
chứng minh đã chạy. Tuy nhiên, gọi cả 6 file fail là legacy/staging chưa được
chứng minh. Ít nhất startup crash R1 là active production. Hai parser fail trong
`tests/test_harness_regressions.py` cũng đã tái hiện độc lập; cần đối chiếu untyped
compatibility contract với typed research scoring trước khi sửa code hoặc cập
nhật test. Chưa suy ra campaign accuracy bị sai từ hai assertion này.

Các nhóm còn lại là query compounds, reranker golden, VGC cascade và VGC UI.
Phải triage từng failure thành code bug / stale expectation có quyết định
contract / environment, kèm source path và bằng chứng; không đổi nhãn thành
nonblocking chỉ vì không nằm trong bộ 265. Không thay frozen scoring/dataset hoặc
research claims để lấy test xanh. Stage 0 giữ nguyên.

## Evidence của review

- `command.json`, `regression_and_visual.txt/xml`: **271 pass**, 0 fail/error/skip.
- `test_followup_acceptance.py`: 5 ca UI mới, **3 fail / 2 pass**.
- `followup_command.json`, `followup.txt/xml`: 5 ca đó cộng 3 existing failure
  checks (tray + 2 parser), tổng **6 fail / 2 pass**.
- `evidence_checks.json`: active file set, 132 JUnit consistency, 19 failure
  messages, token/latency aggregates và old artifact integrity.
- `source_start.json`: 40 file (37 reported + 3 runner scripts), toàn bộ reported
  source_end khớp; `supporting_source.json` đóng băng thêm 7 file cho call paths.
- `received_artifacts/` giữ nguyên toàn bộ gói nhận được; review trước không đổi
  artifact nào theo manifest, gồm cả probe/lần fail lịch sử.
- Reviewer không sửa production code hoặc tests cũ; không gọi model thật,
  không launch OS app, không chạy resident có indexing/hotkeys thật. Không thực
  hiện thêm campaign hay đổi research gate.

Brief sửa tiếp nằm tại `message_to_antigravity.md`.
