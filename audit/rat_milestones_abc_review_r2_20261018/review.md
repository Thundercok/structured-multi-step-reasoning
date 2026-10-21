# Review vòng 2 — bản sửa Milestones A/B/C

Hoàn tất review ngày **2026-10-19**, Asia/Ho_Chi_Minh. Thư mục giữ hậu tố
20261018 vì vòng review bắt đầu ngày 18/10 và tiếp tục sau yêu cầu “go on”.

**Verdict: request changes — còn 5 vấn đề P2.**

Đã xác minh độc lập **256 tests trong bộ bàn giao đều qua**, gồm 245 regression
và toàn bộ 11 probe của vòng review trước. Probe cũ không bị sửa/nới assertion;
hash của toàn bộ audit cũ vẫn nguyên vẹn. Tuy nhiên **7 probe bổ sung fail**,
tương ứng 5 lỗi gốc dưới đây. Vì thế chưa thể đóng đầy đủ R4/R5/R6/R7.

Chỉ review và ghi audit, không sửa production code. Source không thay đổi từ
lúc bắt đầu vòng review tới lúc hoàn tất. Các file trong `reviewed_source/`
ghi lại đúng mã đã chạy; `repair_diff.patch` đối chiếu với snapshot vòng trước.

## F1 — [P2] Lỗi mở app sau QA vẫn hiện “kiểm tra đạt” của QA cũ

**Liên quan R6. Vị trí:** `rat/ui/workbench_scene.py:1199-1213`;
`rat/engine/work_trace.py:588-608`.

Luồng tái hiện qua Omnibar thực tế:

1. Hỏi một tệp tổng hợp có index, nhận câu trả lời từ scripted model và
   reconciliation đã thỏa mãn.
2. Catalog nhận một `League of Legends.app` hợp lệ.
3. Xóa executable của app fixture sau khi lập catalog.
4. Submit `mở Liên Minh`: revalidation trả lỗi, không gọi launcher.

Workbench chuyển đúng sang `phase == 'error'`, nhưng reasoning flow vẫn gồm
“Đọc tài liệu”, “Đưa câu trả lời” và **“Đủ điều kiện hoàn tất theo biên nhận” /
`verified_pass`**, trỏ tới receipt QA cũ. Không có bước lỗi của thao tác vừa chạy.

Bản sửa chỉ xóa state cũ sau khi có artifact success/needs_input. Nhánh lỗi
return trước khi xóa `_steps`, contract, reconciliation và journal. Projection
sau đó ưu tiên reconciliation cũ `satisfied` trước lỗi hiện tại.

Cần mở phạm vi execution/trace mới cho direct action kể cả khi không tạo được
artifact, ghi lỗi thực tế vào flow và không dùng reconciliation của lượt trước
để kết luận cho thao tác hiện tại. Vẫn giữ nguồn/kết quả lịch sử để xem lại.

**Probe:** `test_failed_direct_launch_after_qa_has_current_error_trace` — FAIL.
Ca disambiguation sau QA của vòng trước hiện PASS; lỗi này nằm ở nhánh thất bại.

## F2 — [P2] SQL xét toàn bộ đường dẫn làm mất slide hợp lệ trước LIMIT

**Liên quan R4. Vị trí:** `rat/crawler/db.py:575-579`;
`rat/engine/progressive_search.py:238-243`.

Thêm `d.file_path` vào SQL giúp ca thư mục cha trực tiếp của vòng trước qua.
Nhưng SQL giờ chấp nhận dấu hiệu slide trong **mọi thư mục tổ tiên**, còn
`is_slide_row()` chỉ xét filename, summary và thư mục cha trực tiếp.

Fixture có:

- Một tệp hợp lệ `slides/DSA_actual.pdf`.
- Sáu tệp mới hơn trong `slides/archive/books/DSA_reference_*.pdf`, không có
  chỉ báo slide trong filename, summary hoặc thư mục cha `books`.

Query `slide DSA mới nhất`, `limit=1` trả rỗng. SQL chọn ba tệp reference trước
LIMIT vì đường dẫn có tổ tiên `slides`; Python loại cả ba sau đó. Slide hợp lệ
đã bị cắt khỏi candidate set, dù chính `is_slide_row()` xác nhận nó hợp lệ.

Cần áp dụng cùng predicate trước LIMIT ở hai tầng; tăng hệ số overfetch không
giải quyết được trường hợp có nhiều false positives. Probe dùng thư mục gốc
trung tính để tên test pytest không vô tình đóng vai trò chỉ báo slide.

**Probe:** `test_ancestor_slide_matches_cannot_consume_limit_before_valid_parent_match`
— FAIL.

## F3 — [P2] Cụm ngày tạo chưa được nhận diện và loại khỏi FTS nhất quán

**Liên quan R5. Vị trí:** `rat/engine/finder_intent.py:246-252`, `300-316`.

`create_pat` có `đã tạo`, `created`, `written`, nhưng biểu thức dùng để bắt cả
cụm thời gian `verb_prefix` không bao gồm chúng một cách tương ứng. Vì chỉ xét
`create_pat` trong `m.group(0)`, một phần câu vẫn còn trong query hoặc ngày tạo
tiếp tục bị hiểu thành ngày sửa:

| Câu nhập | Query còn lại | date_field thực tế |
| --- | --- | --- |
| `Slide DSA đã tạo tuần trước` | `DSA đã` | `created` |
| `slides DSA created last week` | `DSA created` | `modified` |

Cả hai đều không yêu cầu làm rõ. Ca đầu thêm điều kiện FTS `đã` không thuộc từ
khóa người dùng muốn tìm; ca sau vừa thêm từ FTS vừa dùng sai trường ngày.
Đường `tạo tuần trước` ngắn của probe cũ hiện qua.

Cần dùng cùng định nghĩa cụm động từ để bắt/xóa modifier và chọn date field,
hoặc giữ trạng thái chưa hiểu/làm rõ; không chỉ thêm từ vào regex phân loại
không bao giờ nhận được toàn bộ cụm đó.

**Probe:** `test_creation_date_phrase_is_consumed_without_changing_its_meaning`
— 2 FAIL.

## F4 — [P2] Metric phím → editor bị ghi đè lại thành thời gian chạy slot

**Liên quan R7. Vị trí:** `rat/ui/omnibar.py:2301`, `2341`, `2367`.

Bản sửa đã lấy timestamp KeyPress và tính `last_key_to_editor_ms` ở đầu slot.
Nhưng các phép gán cũ ở cuối nhánh query rỗng và cuối hàm vẫn tính lại từ
`t_edit0`, xóa mất kết quả vừa đo.

Probe dùng clock xác định: KeyPress tại 9.0 s, textChanged tại 10.0 s và thời
gian chạy slot bằng 0. Kết quả đúng là 1.000 ms, thực tế lưu **0 ms**. Đây là
giá trị mô phỏng để kiểm tra phép tính, không phải số đo hiệu năng sản phẩm.

Cần giữ metric bắt đầu từ KeyPress qua tất cả đường return; nếu cần đo thời
gian chạy slot thì dùng tên/field riêng và phân biệt mẫu không có input event.

**Probe:** `test_key_to_editor_measurement_is_not_overwritten_by_slot_duration`
— FAIL.

## F5 — [P2] Metric kết quả đầu bị ghi đè và ghi cả khi chưa có kết quả

**Liên quan R7. Vị trí:** `rat/ui/omnibar.py:2248-2252`.

Snapshot đầu lấy đúng thời gian submit → delivery rồi đặt
`_finder_query_submit_t0 = None`. Nhưng snapshot tiếp theo của cùng query đi
vào fallback `snapshot.elapsed_ms` và ghi đè `last_query_to_first_hit_ms` bằng
thời gian worker của lần cập nhật muộn hơn. Ngoài ra nhánh này không kiểm tra
`snapshot.hits`, nên delivery rỗng vẫn được ghi là thời gian tới kết quả đầu.

Hai probe xác định:

- Snapshot đầu có hit cho 1.000 ms; snapshot semantic cùng query có
  `elapsed_ms=7.000` làm metric đổi thành 7.000 ms.
- Snapshot lexical rỗng vẫn ghi 1.000 ms dù chưa có hit nào.

Cần giữ trạng thái first usable hit theo query/generation, chỉ chốt khi có hit
và không ghi đè bởi các snapshot sau. Có thể lưu thời gian delivery rỗng hoặc
completion riêng nếu cần. Các giá trị clock giả lập không phải benchmark.

**Probes:**
`test_first_hit_latency_is_not_overwritten_by_later_same_query_snapshot`,
`test_empty_delivery_does_not_claim_a_first_hit_latency` — 2 FAIL.

## Đối chiếu 8 vấn đề vòng trước

| Finding cũ | Trạng thái trong vòng review này |
| --- | --- |
| R1 — exact/alias trước tự mở app | Đóng trong phạm vi đã review; probe partial-match qua, có kiểm tra exact name/alias trước execution. |
| R2 — cắt prefix từ khóa | Đóng trong phạm vi đã review; cả ba probe giữ từ khóa qua. |
| R3 — report mất sau metadata projection | Đóng trong phạm vi đã review; marker predicate giữ được content-matched report, probe trung tính qua. |
| R4 — SQL/Python slide rule | Sửa được ca gốc; chưa đóng do F2 trước LIMIT. |
| R5 — ngày tạo/ngày sửa | Sửa được câu ngắn gốc; chưa đóng do F3. |
| R6 — trace direct action sau QA | Disambiguation gốc qua; chưa đóng nhánh lỗi do F1. |
| R7 — ranh giới timer UI | Probe không paint qua; chưa đóng các metric còn lại do F4/F5. |
| R8 — timestamp phần lẻ cuối tuần | Đóng trong phạm vi đã review; cận exclusive được ưu tiên, probe qua. |

Không còn P1 đã xác nhận trong phạm vi vòng này. B không có blocker mới trong
bộ offscreen đã chạy. Native Cocoa/IME, số đo model thật, baseline performance
CPU/RAM và hạn chế prefill suffix ghi trong review trước vẫn chưa được nghiệm
thu bởi các test này. Không thay research harness hoặc Stage 0.

## Validation và khả năng tái hiện

| Bộ test | Kết quả |
| --- | --- |
| Bộ 256 tests từ bàn giao, chạy độc lập một lệnh | 256 passed, 43.94 s |
| Probe headless bổ sung | 3 failed, 0.17 s |
| Probe UI bổ sung | 4 failed, 4.25 s |

Đây là bộ test được chọn cho review, **không phải tuyên bố toàn bộ repository
test suite đã qua**. Thời gian trên là thời gian chạy test.

Model thật: **0 generations**. App thật: **0 launches**. QA dùng tệp/index
tổng hợp và scripted model; launcher mock, Qt `qpa_platform=offscreen`.

Lệnh và tham số đầy đủ nằm trong `commands.json`. Hai lệnh probe bổ sung:

```bash
.venv/bin/python -m pytest \
  audit/rat_milestones_abc_review_r2_20261018/test_additional_headless.py -q

QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  audit/rat_milestones_abc_review_r2_20261018/test_additional_ui.py -q
```

Các probe mới biểu diễn yêu cầu đúng cần đạt; giữ nguyên assertions khi sửa.

Lần xin chạy UI trước bị automatic approval review từ chối vì quota của dịch
vụ duyệt, không phải kết luận thao tác không an toàn. Sau yêu cầu “go on”, cùng
lệnh đã được duyệt và chạy thành công ngày 19/10; không còn blocker này.

Artifacts: `regression.{txt,xml}`, `probes_headless.{txt,xml}`,
`probes_ui.{txt,xml}`, `validation.json`, source manifests,
`reviewed_source/`, `repair_diff.patch`, `artifact_manifest.json`.
