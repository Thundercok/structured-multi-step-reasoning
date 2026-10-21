# Independent review of RAT Milestones A / B / C

Reviewed 2026-10-18, Asia/Ho_Chi_Minh. Verdict: **request changes**.

Review theo yêu cầu người dùng: chỉ review độc lập hai báo cáo bàn giao, không
sửa production code. Phạm vi gồm B/C ngày 2026-10-17 và A/projection reasoning
ngày 2026-10-18, đối chiếu prompt
`docs/prompts/antigravity_performance_natural_finder_thoughts_20261017.md`.
Theo thứ tự trong prompt gốc, projection reasoning thuộc mốc D; báo cáo thứ hai
gộp phần này vào tên Milestone A. Review kiểm tra chức năng thực tế của cả hai.

## Kết luận và bằng chứng

- **245 regression pass**: 176 tests trong bộ tích hợp và 69 tests bổ sung cho
  runtime, CLI, warmup cùng probe Finder/keyboard đã bàn giao.
- Bộ tích hợp chứa đầy đủ **130 tests** được báo cáo cho Milestone A; cả 130 qua
  trên source hiện tại. Test pass không bảo đảm các acceptance khác đã đạt.
- **10/11 probe mới fail**, tương ứng **8 vấn đề độc lập** dưới đây: 1 P1,
  6 P2, 1 P3. Probe giữ selection của phần câu trả lời đã stream qua.
- Qt được kiểm tra bằng `QT_QPA_PLATFORM=offscreen`. Không chạy model thật,
  không mở app thật, không quét tệp cá nhân. QA sử dụng scripted model và đọc
  tệp tổng hợp có index; launcher được mock.
- Source cuối Milestone A khớp toàn bộ manifest bàn giao. Manifest B/C khác ở
  `rat/ui/omnibar.py`, `rat/ui/workbench_scene.py`, `tests/test_workbench_scene.py`,
  là những tệp cũng được sửa trong Milestone A. Đây không tự thân là lỗi; review
  áp dụng cho trạng thái tích hợp mới nhất.
- Không có production file trong manifest thay đổi trong lúc review. Chỉ thêm
  bằng chứng vào thư mục audit này. Không commit, tạo branch hoặc push/pull/reset.

## R1 — [P1] Tự mở app từ một tên chỉ khớp tiền tố

**Vị trí:** `rat/kernel/capabilities/applications.py:154-184`, đặc biệt dòng 184;
`rat/engine/app_resolver.py:151-155`.

Với catalog chỉ có `League of Legends.app`, submit `mở League` gọi launcher ngay.
`ApplicationCatalog.search()` trả cả exact, prefix và word matches, nhưng handler
chỉ kiểm tra số lượng rồi chọn `candidates[0]`. Tên rút ngắn chưa phải alias đã
khai báo vẫn được dùng để thực thi.

Prompt yêu cầu chỉ tự mở sau submit với một **exact/explicit-alias match duy
nhất**, hoặc sau khi người dùng chọn Mở trên một ứng viên. Một kết quả gợi ý
duy nhất không đáp ứng điều kiện đó. Cần giữ match quality/identity tới execution;
partial matches phải chờ lựa chọn. Probe ghi nhận launcher mock đã được gọi,
không chỉ kiểm tra một giá trị trạng thái trả về.

**Probe:** `test_partial_name_requires_selection_before_app_launch` — FAIL.

## R2 — [P2] Xóa filler làm mất tiền tố của từ khóa thật

**Vị trí:** `rat/engine/finder_intent.py:520-528`.

Các nhóm filler đều tùy chọn, dùng `\s*`, không buộc ranh giới từ. Vì thế:

| Câu nhập | Từ khóa đúng | Từ khóa thực tế |
| --- | --- | --- |
| `slide format` | `format` | `mat` |
| `slide money` | `money` | `ey` |
| `báo cáo banking mới nhất` | `banking` | `king` |

Truy vấn bị đổi nghĩa trước khi vào FTS nên tệp hợp lệ biến mất hoặc kết quả sai
được trả về. Cần nhận diện filler như từ/cụm từ hoàn chỉnh thay vì prefix của từ
khóa. Ba ca thử đều tái hiện cùng một lỗi gốc.

**Probe:** `test_filler_removal_preserves_whole_keyword` — 3 FAIL.

## R3 — [P2] Tệp báo cáo khớp FTS bị loại sau khi chiếu metadata

**Vị trí:** `rat/engine/progressive_search.py:235-237`;
`rat/engine/finder_intent.py:82-90`; `rat/crawler/db.py:579-582`.

Tệp `Q3.pdf` có content `Quarterly report DSA`, summary `Quarterly results`,
nằm ở đường dẫn trung tính. `Database.search_metadata(..., report_rule=True)`
trả đúng tệp vì FTS đã xác nhận có từ `report`. Nhưng projection cố ý không có
`content_text`; `eff_filters.accepts(row)` lại chạy `is_report_row()` trên
projection đó, không thấy từ chỉ báo và loại tệp. `bản báo cáo mới nhất` trả rỗng
dù DB đã trả đúng ứng viên.

Cần giữ bằng chứng predicate đã đạt từ DB hoặc dùng một định nghĩa report thống
nhất cho cả lexical và semantic lanes mà không phải đọc toàn văn theo phím.
Probe dùng đường dẫn trung tính: tên thư mục pytest chứa chữ `report` có thể che
lỗi vì `is_report_row()` tìm cả trong toàn bộ `file_path`.

**Probe:** `test_content_matched_report_survives_metadata_projection` — FAIL.

## R4 — [P2] Quy tắc PDF slide khác nhau giữa SQL và Python

**Vị trí:** `rat/crawler/db.py:568-572`;
`rat/engine/finder_intent.py:54-78`.

`is_slide_row()` chấp nhận `slides/DSA.pdf` dựa trên thư mục cha trực tiếp,
đúng với docstring của rule này. Nhưng SQL chỉ xét filename và summary nên loại
tệp trước khi Python có thể xét nó. Với content `DSA trees`, summary `Trees and
graphs`, query `slide DSA` không trả tệp trong thư mục `slides`.

Cần thống nhất predicate ở hai tầng; nếu giữ parent-folder rule, SQL phải áp dụng
nó trước LIMIT. Việc bỏ parent rule ở một tầng cũng cần sửa rõ hợp đồng/giải
thích, thay vì tiếp tục dùng hai định nghĩa.

**Probe:** `test_slide_parent_rule_is_consistent_in_sql` — FAIL.

## R5 — [P2] Diễn giải ngày tạo thành ngày sửa mà không làm rõ

**Vị trí:** `rat/engine/finder_intent.py:243-247`;
`rat/crawler/db.py:558-561`.

Parser xóa cả `tạo`, `làm`, `viết` như modifier thời gian, nhưng intent không lưu
trường ngày được yêu cầu; DB luôn lọc `modified_at`. Với clock cố định
18/10/2026 +07:00, tệp DSA tạo 07/10, sửa 18/10 bị loại khỏi query
`Slide DSA tạo tuần trước`, không có trạng thái cần làm rõ.

Prompt yêu cầu giữ phân biệt ngày tạo/ngày sửa. Cần biểu diễn date field trong
plan và lọc đúng metadata, hoặc làm rõ khi chưa hỗ trợ ngày tạo; không âm thầm
thay nghĩa câu nhập.

**Probe:** `test_creation_time_is_not_silently_replaced_with_modification_time`
— FAIL.

## R6 — [P2] Trace mở app tiếp tục dùng bằng chứng của lượt QA trước

**Vị trí:** `rat/engine/work_trace.py:318-319`;
`rat/ui/workbench_scene.py:3789-3797`.

Tái hiện qua đường submit của Omnibar: hỏi một tệp tổng hợp, nhận câu trả lời,
sau đó submit `mở Liên Minh` với hai bản cài. Dispatcher trả `needs_input` và
artifact chọn ứng viên đúng. Nhưng `_steps`, contract và reconciliation của QA
còn được giữ; nhánh direct-artifact trong `build_reasoning_flow()` đòi `not
steps` nên bị bỏ qua.

UI hiện các bước đọc tệp/trả lời cũ và một bước chờ gắn vào receipt QA cũ,
không có bước tìm hai ứng viên hoặc reference tới input-request artifact mới.
Kết quả vẫn chờ chọn, nhưng phần giải thích công khai không còn bám bằng chứng
của tác vụ hiện tại. Cần quản lý phạm vi trace của direct action riêng trong cùng
Workbench, vẫn giữ nguồn/kết quả cũ để người dùng xem lại.

**Probe:** `test_app_disambiguation_replaces_prior_qa_trace` — FAIL, đã kiểm
tra qua `_submit_chat_prompt` → dispatcher → `_on_artifact_result` thực tế;
chỉ patch worker start để kiểm soát thời điểm delivery.

## R7 — [P2] Timer UI chưa đo sự kiện được ghi trên tên metric

**Vị trí:** `rat/ui/omnibar.py:2236-2239`, `2282`, `2284-2287`.

`last_delivery_to_paint_ms` được chốt ngay khi slot cập nhật widget kết thúc,
không đợi `QEvent.Paint`. Probe tắt updates, xác nhận không có paint event, nhưng
metric vẫn nhận một số ms. Đây là thời gian chạy slot, không phải delivery →
paint. Tương tự, `last_key_to_editor_ms` bắt đầu sau khi `textChanged` đã được
phát; còn `last_query_to_first_hit_ms` ưu tiên timer worker, bỏ thời gian delivery
UI và tiếp tục có thể bị snapshot sau ghi đè.

Cần ghi đúng tên/phạm vi cho timer hiện có, hoặc đặt mốc tại input event và
paint của đúng query/generation. Không dùng các giá trị hiện tại để kết luận
đạt mục tiêu latency editor/paint của Milestone A.

**Probe:** `test_delivery_to_paint_metric_waits_for_a_paint_event` — FAIL.
Số ms trong log là thời gian slot của fixture offscreen, không phải benchmark.

## R8 — [P3] Mất phần cuối khoảng tuần với timestamp có phần lẻ

**Vị trí:** `rat/engine/finder_intent.py:410-414`;
`rat/crawler/db.py:558-561`.

Parser đồng thời đặt `date_max_exclusive = end` và `date_max = end - 1`;
DB áp dụng cả hai điều kiện. Tệp sửa lúc Chủ Nhật 11/10/2026
23:59:59.500 +07:00 bị loại khỏi `tuần trước`, dù timestamp nằm trong khoảng
nửa mở [05/10 00:00, 12/10 00:00). Metadata file hỗ trợ timestamp float.

Cần chỉ dùng cận trên exclusive cho khoảng lịch hoặc bảo toàn chính xác ngữ
nghĩa timestamp khi hỗ trợ tương thích `date_max` cũ.

**Probe:** `test_last_week_half_open_range_includes_fractional_last_second`
— FAIL.

## Trạng thái từng milestone và giới hạn nghiệm thu

| Mốc | Đánh giá trong review này |
| --- | --- |
| B — nhãn/không gian/geometry | Các regression geometry, keyboard, theme và narrow offscreen đã chạy đều qua. Chưa phát hiện blocker riêng của B trong phạm vi đã thử. Chưa xác nhận native Cocoa/IME bằng phiên thật mới. |
| C — parser/filter/app launch | Đã có implementation và positive-path tests; chưa nghiệm thu do R1–R5, R8. |
| A / D — QA streaming, telemetry, reasoning projection | Bộ 130 tests được báo cáo qua, giữ selection trong stream qua; chưa nghiệm thu tích hợp do R6–R7 và thiếu bằng chứng performance thực tế nêu dưới đây. |

Audit Milestone A gốc chỉ chứa hai source manifests; không có log/XML của lần
130 tests, bảng baseline trước/sau, số đo CPU/RAM hay ảnh acceptance mới trong
chính thư mục đó. Lần review này bổ sung bằng chứng software regression, không
bổ sung số đo model thật hoặc native UI acceptance.

Giới hạn telemetry native cần giữ rõ khi làm bước sau: `prefill_ms` hiện bao
quanh `_prepare(prefix)`, còn suffix câu hỏi được đưa vào `stream_generate`
bên trong timer `generation_ms` (`mlx_document_session.py:168-186`). Vì thế
`prefill_ms=0` khi prefix đã sẵn chỉ nói về prefix; không chứng minh câu hỏi mới
không cần prefill. Chưa dùng dữ liệu này để so sánh model latency trong review.

Không có thay đổi research harness, chất lượng model, tính mới CoT hay Stage 0.
Không coi mock/scripted model, offscreen Qt hoặc passing-test count là bằng
chứng chất lượng model hoặc hiệu năng thực tế.

## Lệnh tái hiện và artifact

Chạy tại repository root, dùng cùng `.venv/bin/python`:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_progressive_search.py tests/test_mlx_document_session.py \
  tests/test_selected_document_qa.py tests/test_selected_document_ui.py \
  tests/test_workbench_scene.py tests/test_rat_completion_reconciliation.py \
  tests/test_rat_completion_boundaries.py tests/test_document_model_startup.py \
  tests/test_rat_magic_ui.py tests/test_research_study.py \
  test_optimal_stopping.py test_entry_predictor.py -q

QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  tests/test_assistant_runtime.py tests/test_rat_headless_cli.py \
  tests/test_resident_warmup.py \
  audit/rat_finder_codex_review_20261016/test_finder_integration_probes.py \
  audit/rat_finder_codex_review_r2_20261017/test_keyboard_followups.py -q

.venv/bin/python -m pytest \
  audit/rat_milestones_abc_independent_review_20261018/test_review_probes.py -q

QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  audit/rat_milestones_abc_independent_review_20261018/test_ui_review_probes.py -q
```

Các probe mới hiện phải fail như mô tả; đây là yêu cầu đúng cần đạt khi sửa,
không phải regression suite đã pass. Không đánh dấu xfail hay nới assertion.

Lần đầu chạy Qt trong sandbox bị abort tại import `PyQt6.QtTest`; chạy ngoài
sandbox đã hoàn tất. Không tính lần abort đó là lỗi production. XML/log cuối
cùng chứa kết quả đầy đủ của các lần chạy dùng để kết luận.

- `regression.txt` / `regression.xml`: 176 pass, 41.76 s theo console.
- `preserved_regression.txt` / `preserved_regression.xml`: 69 pass, 14.09 s.
- `probes_headless.txt` / `probes_headless.xml`: 8 fail, 0.29 s.
- `probes_ui.txt` / `probes_ui.xml`: 2 fail / 1 pass, 7.67 s.
- `source_start.json`, `source_end.json`, `reviewed_source/`: hash và snapshot
  source đã review, gồm các tệp trong manifest bàn giao và phần wiring liên quan.
- `validation.json`: tổng hợp kết quả, phạm vi và số real model/app calls.

Các thời gian trên là runtime của bộ test, không phải latency của sản phẩm.
