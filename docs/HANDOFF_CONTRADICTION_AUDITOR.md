# HANDOFF — Contradiction Auditor v2 (CPU-only, không LLM verifier)

> [!IMPORTANT]
> **Trạng thái / Status:** `frozen; 46 synthetic rows, agent-authored; BLOCK recall 19/21; external validity unknown.`

Đích trong repo: `rat/engine/contradiction_auditor.py`. Gói gồm:

| File | Vai trò |
|---|---|
| `contradiction_auditor.py` | Module tham chiếu (≈680 dòng, stdlib thuần) |
| `test_contradiction_auditor.py` | 72 test lõi (+2 xfail strict = gap đã biết) |
| `test_report_and_edges.py` | 68 test + 1 xfail: span, annotation, summary, 4 lỗi biên, Unicode, phía query (`infer_query_condition`) |
| `mutation_check.py` | 58 mutant cố ý; test suite **phải** đỏ trên từng cái |
| `eval_gold.py` + `gold/seed.jsonl` | Bộ gold 46 ca (44 chấm điểm, 2 `known_gap`), **toàn bộ `origin: synthetic`** (c45 suy ra từ một BLOCK trong log thật) |
| `label_sheet.py` | Gán nhãn **mù** cho gold thật: `export` ra CSV (không có verdict của auditor), người gán nhãn điền `expected_gate`, `import` ra JSONL `origin: llm_real`; cột `split` dev/test chia theo hash của query |
| `smoke_calls.py` | Smoke test trên log thật: **mỗi answer đối chiếu với source CỦA CHÍNH NÓ**, báo COVERAGE, in từng BLOCK kèm câu nguồn |
| `probe_edge_bugs.py`, `probe_robust.py` | Script tái hiện 4 lỗi biên và kiểm Unicode/đo thời gian (in output thô) |
| `HANDOFF_CONTRADICTION_AUDITOR.md` | File này |

**Đọc trước khi làm:** repo đã có một `contradiction_auditor.py` (agent từng báo phân tích `L60-160`, `L250-350`). Tôi **chưa thấy file đó**. Module này là spec tham chiếu, **không ghi đè mù**. Đối chiếu public interface (mục 6) rồi mới merge.

---

## 1. Mục tiêu

Kiểm tra `res.answer` có vi phạm `SourceEvidence` không, **không gọi LLM**.

| Yêu cầu | Cách giải |
|---|---|
| Tách telemetry (`Executed COT: 18 tokens`) khỏi claim | `is_telemetry`: đầu dòng/đơn vị vận hành **và không có từ miền**. Mức **câu**, nên telemetry cùng dòng với claim không nuốt claim (gold c40) |
| (a) Ngưỡng vs giá trị đạt (TOEIC ≥600 vs 650) | `Role.NORM` vs `Role.FACT` + interval membership → `SATISFIED_BOUND` |
| (b) Khác chủ thể (An 650, Bình 700) | `Ent.instance` + `applies()` → `DISJOINT_ENTITIES` |
| (c) Mâu thuẫn thật (tối đa 6 vs 7 năm) | Interval không bằng nhau → `GROUNDING_CONFLICT` + `reason` |

---

## 2. Chạy và tái hiện

```bash
python -m pytest -q                      # kỳ vọng: 144 passed, 3 xfailed
python mutation_check.py                 # kỳ vọng: 58/58 killed, exit 0
python eval_gold.py gold/seed.jsonl      # in confusion matrix + precision/recall từng lớp
python probe_edge_bugs.py                # raw output 4 lỗi biên + span
```

```python
from contradiction_auditor import build_index, audit_answer, copy_footer, infer_query_condition
kb = build_index(source_evidence_text)               # cache theo tập retrieval
rep = audit_answer(res.answer, kb, infer_query_condition(query))   # None = không ghim; luôn an toàn
rep.gate          # "BLOCK" | "REGENERATE" | "ANNOTATE" | "PASS"
rep.annotations   # [Annotation(kind, reason, start, end, anchor)]  — offset trên res.answer GỐC
rep.summary       # dict đếm + rep.summary["note"] (câu tiếng Việt cho thanh độ phủ)
copy_footer(rep)  # chuỗi thêm vào khi người dùng copy văn bản thuần; "" nếu không cần
```

`audit_text` / `gate` / `build_index` / `extract_all` vẫn giữ nguyên chữ ký của v1. `atoms()` trả `Atom` có thêm `start, end, scope_src, scope_start, scope_end` (offset trên text **gốc**, kể cả sau khi bỏ markdown/NFC/ngoặc diễn giải).

---

## 3. Pipeline

| Stage | Hàm | Ghi chú |
|---|---|---|
| 0 | `normalize_map` | **Giữ offset.** NFC (NFD từ macOS/PDF), NBSP→space, bỏ zero-width, bỏ markdown (`** __ ` #`), `=>`→"nên", bỏ `Điều/Khoản 15`, "sáu năm"→6, "4 năm rưỡi"→4.5, bỏ thang điểm "hệ 4/10/100" (không kèm năm/học kỳ), bỏ ngoặc diễn giải `(tương đương …)` |
| 1 | `is_telemetry` | Theo câu |
| 2 | `_walk` / `atoms` | Tách dòng → bảng markdown → header scope → câu → mệnh đề; gán `condition`, `entity`, `outcome`, span, `per_semester` |
| 3 | `extract` → `Tup` | Operator = cue gần số nhất; hòa thì cue đứng trước thắng. Đơn vị `credit/semester`, `…/remaining` tách khỏi tổng |
| 4 | `match` | Interval; `Res` |
| 5 | `audit` + `_evasion_pass` | Bucket theo `condition`; sau đó chặn `QUERY_SCOPE_EVASION` |
| 6 | `audit_answer` | Annotation 2 tầng + summary cấp answer |

---

## 4. Verdict, `gate`, và hợp đồng UI

| Verdict | Nghĩa | `gate` |
|---|---|---|
| `GROUNDING_CONFLICT` | Mâu thuẫn nguồn. `reason`: `looser/tighter/boundary_only/point_outside/fact_vs_bound/fact_value/query_scope_conflict/query_scope_evasion` | **BLOCK** |
| `AMBIGUOUS_SCOPE` | Không nói hệ nào, các hệ trong nguồn bất đồng | **REGENERATE** |
| `OUT_OF_COVERAGE` | Hệ ngoài KB hoặc `UNKNOWN:<x>`: **chưa kiểm chứng** | **ANNOTATE** |
| `SCOPE_ELIDED` | Đúng theo hệ trong query nhưng answer không tự nói | **ANNOTATE** |
| `SATISFIED_BOUND` / `DISJOINT_ENTITIES` / `NOT_COMPARABLE` | Khớp / khác chủ thể / không so được hoặc không parse (`unparsed:*`) | PASS |

**Hợp đồng UI (đã chốt trong lượt này, không phải chọn 1 trong 3 mức):**

| Tầng | Quy tắc |
|---|---|
| Neo nhãn | `OUT_OF_COVERAGE`/`SCOPE_ELIDED` có `scope_src == "HEADER"` → **một** nhãn trên dòng header (`anchor="HEADER"`), không lặp từng bullet. Còn lại (`INLINE`, không scope, mọi `CONFLICT`/`AMBIGUOUS`) → nhãn trên mệnh đề (`anchor="CLAUSE"`); với `INLINE` span phủ luôn cue (`Hệ X: …`) để người đọc thấy phạm vi |
| Cấp answer | `rep.summary`: số mệnh đề đã đối chiếu (khớp/mâu thuẫn/chưa kiểm chứng), **số câu không có số chưa được kiểm**. **Không có trạng thái "verified" xanh toàn bài**: pipeline chỉ nhìn câu có số, một câu văn xuôi không số không bao giờ được kiểm |
| Copy văn bản thuần | HTML badge mất khi copy; `copy_footer(rep)` trả dòng `[Lưu ý: …]` để gắn vào cuối bản copy khi có mục chưa kiểm chứng |

Lý do không dùng 1 mức: chỉ neo bullet thì lọt văn xuôi/câu ghép; chỉ neo câu thì câu ghép hai hệ (1 vế SAT, 1 vế OOC) nhập nhằng; chỉ neo cả answer thì xóa giá trị của phần đã kiểm và cho phép "rửa" qua thẻ nguồn cuối bài.

**Câu hỏi chính sách còn mở (chủ dự án chưa quyết):** claim `EXPEL` thuộc hệ ngoài KB nên `ANNOTATE` hay `REGENERATE`? Giữ `ANNOTATE`.

---

## 5. Quyết định thiết kế *cố ý* (trông như bug, đừng "sửa")

| Hành vi | Lý do | Test ghim |
|---|---|---|
| Rule vs rule dùng **bằng nhau**: `tối đa 5` vs nguồn `tối đa 6` vẫn CONFLICT (`tighter`); `trên 2.0` vs `tối thiểu 2.0` là `boundary_only` | Trần quy chế hai chiều: nới → vi phạm, thu hẹp → tước quyền lợi. **Rủi ro FP có thật** với "trên" dùng lỏng trong tiếng Việt; chưa có dữ liệu thật để cân | `test_c_cap_statements_block_both_directions` |
| Câu điểm `là X năm` lenient (X trong bound thì ổn) | Tránh báo oan | `test_c_point_statement…` |
| FACT không kèm hậu quả mà ngoài bound → `NOT_COMPARABLE` | "SV đạt TOEIC 550" không khẳng định đạt chuẩn | `test_a_fact_without_assertion…` |
| Trong một bucket `condition`: pessimistic; giữa các bucket bất đồng: `AMBIGUOUS_SCOPE` | Index theo `(metric, unit)` không phân biệt điều khoản | `test_bucket_is_pessimistic…` |
| `query_condition` chỉ thắt chặt (→ CONFLICT), không nới (→ `SCOPE_ELIDED`) | Ngữ cảnh query nằm ngoài artifact | `test_query_context_may_tighten…` |
| `query_condition=None` = "không có ngữ cảnh", không phải bucket chung | Từng là bug | `test_no_query_context_is_not_the_general_bucket` |
| **Tên hệ quen + từ lạ liền sau = hệ khác** (`hệ chính quy chất lượng cao` → `UNKNOWN:…`). Chỉ khi từ sau thuộc `_PRED` (động từ/danh từ vị ngữ) mới coi là hệ đã biết | Tiền tố `` từng cho SATISFIED giả dưới `full-time`. **Đánh đổi:** `_PRED` là whitelist hữu hạn; từ vị ngữ ngoài danh sách bị coi là tên hệ dài hơn (an toàn: ra `ANNOTATE`, không ra SATISFIED) | `test_extended_programme_name…`, `test_known_programme_followed_by_a_predicate…` |
| **Canary chạy ở mọi cue**, kể cả inline có dấu phẩy | Canary chỉ ở dòng header lọt `Đối với hệ X, …` | `test_inline_unknown_programme_with_comma` |
| `hệ <số>` là thang điểm **trừ khi** kèm `năm`/`học kỳ` (`hệ 5 năm`, `hệ 4,5 năm` là tên chương trình) | Stoplist `\d` cũ chặn nhầm tên thật; regex dùng `(?![.,]?\d)` để chặn backtrack `4,5`→`4` | `test_digit_programme_names…`, `test_grading_scales…` |
| **`QUERY_SCOPE_EVASION`**: query ghim hệ đã biết, answer chỉ dùng nhãn hệ lạ cho metric đó, và giá trị **vi phạm** luật của hệ được hỏi → `CONFLICT`. Nếu answer cũng nói về hệ được hỏi (hoặc không scope) cho metric đó thì nhãn lạ chỉ là thông tin thêm → `OUT_OF_COVERAGE` | Chặn `CONFLICT → unverified` bằng từ đồng nghĩa ngoài `PROGRAM` | `test_query_scope_evasion…` (+3 test biên) |
| Hệ lạ → `UNKNOWN:<x>` → không bao giờ SATISFIED | Trùng ngưỡng với hệ khác cho SATISFIED giả | `test_unknown_programme_canary` |
| `PROGRAM` sinh từ **từ vựng miền**, không từ KB | Parser mù với hệ ngoài KB là gốc vòng regenerate không thoát | — |
| Chế tài (`EXPEL`) chỉ so với chế tài | "Buộc thôi học khi <30 tín chỉ" ≠ "cần ≥120 để tốt nghiệp" | `test_sanction_and_requirement…` |
| Tên riêng = từ viết hoa + động từ thành tựu, trừ `Được/Không/Đã/…` | Tên giả biến claim thành FACT | `test_sentence_initial_function_word…` |
| FACT: `đạt/đã/đang/hoàn thành/tích lũy` đủ; `có` cần `SV` | Tiếng Việt hay lược chủ ngữ | `test_program_subject_with_co…` |
| `15 tín chỉ mỗi học kỳ` → unit `credit/semester`; `còn tối đa 1 năm` → `…/remaining` | Không phải tổng/trần chương trình | `test_per_semester…`, `test_remaining_time…` |
| Ngoặc diễn giải (`tương đương`, `tức`, `khoảng`, `≈`) bị **bỏ** trước khi trích | Nếu giữ: 2 số/câu → `multi_number`, claim sai lọt. **Đánh đổi:** nếu số trong ngoặc mới là claim sai, nó không bị kiểm (gap #8) | `test_restatement_parenthetical…` |
| Bảng markdown → mỗi ô số thành một mệnh đề có span cả hàng | Bảng trước đó không có dấu câu nên không scope được | `test_markdown_table_rows…` |

---

## 6. Việc agent phải làm trong repo (điều chưa biết)

1. **Đọc `contradiction_auditor.py` hiện có**, liệt kê interface đang được import. Giữ tên enum nếu đã có người dùng.
2. **Nối dây:** `SourceEvidence`→`build_index`; `res.answer`→`audit_answer`; `rep.gate`→`verification_status`. Xác định `SourceEvidence` là text hay object, telemetry nằm trong `res.answer` hay kênh riêng.
3. **`infer_query_condition(query)` — đã có bản tham chiếu trong module (stage 7), dùng nó, đừng viết lại.** Nguyên tắc: **ghim sai là lỗi nguy hiểm** (biến `ANNOTATE` thành `BLOCK`, xem `test_a_false_pin_would_turn_annotate_into_block`), `None` luôn an toàn. Mọi nghi ngờ → `None`: nhiều hệ, `hệ <nhãn lạ>` (kể cả `hệ 5 năm`, `hệ 4,5 năm`), tên đã biết + từ lạ (`chính quy chất lượng cao`). Từ nghi vấn (`bao/mấy/nào/…`) và liên từ nằm trong `_Q_STOP` nên không bị đọc thành tên dài hơn. **Bản agent tự viết đã thử 2 lần và cả hai sai**: v1 (regex canary chép lại, lỗi backtrack `4,5`) ghim nhầm `hệ chính quy là gì và hệ 4,5 năm là gì?`; v2 (`any(prog in raw_x)` trên span tham lam, bỏ `_EXT`) ghim nhầm 7/18 query đối kháng, gồm `hệ chính quy chất lượng cao …`, `hệ đại trà khác hệ chính quy …`.
4. **UI:** map `Annotation` → badge theo `anchor`; thanh độ phủ từ `summary["note"]`; thêm `copy_footer()` vào handler copy. Đọc `rat/ui/answer_presentation.py` trước, tôi chưa thấy file.
5. **CI invariant — CHƯA có.** Mọi `condition` không-`None` trong KB ∈ `set(PROGRAM.values())`.
6. **Counter `UNKNOWN:<x>` — CHƯA có.** Log mọi `OUT_OF_COVERAGE`; `x` lặp nhiều thì đưa vào hàng đợi review **thủ công**.
7. **Điền `PROGRAM`** bằng các hệ thật của TDTU (hiện là danh sách tôi tự điền) và rà `_PRED` với câu trả lời thật.
8. **Giới hạn vòng regenerate** (`AMBIGUOUS_SCOPE`); hết lượt dùng template từ KB theo scope câu hỏi.

---

## 7. Bằng chứng (raw, tái hiện được)

| Hạng mục | Kết quả | Chạy |
|---|---|---|
| Test | `144 passed, 3 xfailed` | `pytest -q` |
| Mutation | `58/58 killed` (49 lõi/v2 + 7 phía query + 2 cue `đăng ký`). 6 mutant v1 hết hiệu lực sau refactor và đã viết lại; M45 sống sót ban đầu → thêm test | `python mutation_check.py` |
| Gold (v1 → v2) | v1 trên c01–c42: **29/40** đúng (3 contradiction lọt `PASS`, 3 false `BLOCK`). v2 trên c01–c42: **40/40**. v2 trên c01–c44: **42/42** (c43/c44 thêm sau khi probe Unicode; chưa chạy v1) | `python eval_gold.py gold/seed.jsonl` |
| Latency `audit_answer` | answer ngắn (2 câu) median **0.15 ms**; answer 9.0 KB median **10.8 ms**, max 17.4 ms | `python probe_robust.py` |

Latency đo trên sandbox (Python 3.13, x86_64), **không phải máy bạn**; chưa đo cold start/import. Bước chuẩn hóa giữ offset chạy vòng Python nên tăng tuyến tính theo độ dài; 10 ms cho 9 KB chấp nhận được cho UI nhưng đáng đo lại.

### Smoke test trên log thật: kết quả của agent KHÔNG dùng được làm bằng chứng

Agent báo `7.521` snippet, `PASS 7519 / BLOCK 2`, `3` mệnh đề định lượng được đối chiếu, `UNKNOWN: 0`. Đọc đúng: **coverage ≈ 0,04%**. `PASS` ở đây nghĩa là *không so được gì*, không phải đã kiểm chứng. Tập quét là log nghiên cứu (có suy luận toán GSM8K), không phải câu trả lời về quy chế, nên `UNKNOWN: 0` và "INVERSION_PAIRS 0 false positive" đều **không có nội dung** (n=3, và chưa biết `INVERSION_PAIRS` có kích hoạt lần nào). Hơn nữa nó dùng **một KB chuẩn chung** cho mọi snippet. Chạy lại bằng `smoke_calls.py` (mỗi call dùng source của chính nó, lọc call quy chế).

Hai BLOCK: (1) `TOEIC tối thiểu 650` → BLOCK với KB chuẩn (600), **PASS** khi source nói 650: artefact của harness nếu source của call đó ghi 650. (2) `phải đăng ký … 14 tín chỉ` → BLOCK kể cả với source **trung thực** có câu `…14 tín chỉ trong mỗi học kỳ chính`: **false positive thật của engine**, đã sửa (xem gap #14, gold c45/c46).

### ⚠ Con số gold KHÔNG phải bằng chứng recall

44 ca do **cùng bên viết module** soạn (`origin: synthetic`). Nhãn c01–c30 được viết trước khi chạy nhưng sau khi tôi đã thiết kế v1; c31–c44 được soạn **từ danh sách lỗi đã biết**, rồi mới sửa module. Nên `42/42` chỉ nói rằng: các lỗi đã biết được sửa và có test giữ. **Không** nói gì về câu trả lời LLM thật. Bằng chứng duy nhất cho recall là gold từ `res.answer` thật có nhãn tay (mục 9).

---

## 8. Chỗ hở đã biết, theo mức rủi ro

| # | Mức | Hở | Hiện trạng |
|---|---|---|---|
| 1 | **P0** | **Chưa đo recall/precision trên dữ liệu thật** | Mục 9 |
| 2 | **P0** | **Không có slot ngoại lệ** ("trừ trường hợp gia hạn tối đa 8 năm") | `xfail strict`: `test_gap_exception_clause` |
| 3 | P1 | Học kỳ ↔ năm không quy đổi: "tối đa 14 học kỳ" (sai) lọt `PASS` | `xfail strict`: `test_gap_semester_unit`; gold c42 `known_gap` |
| 4 | P1 | **Biểu thức tương đối** ("gấp đôi hệ chính quy") không có số → câu **không bao giờ được kiểm** | Chỉ lộ ở `summary.sentences_without_numbers`; gold c41 `known_gap` |
| 5 | P1 | Một atom nhiều số (khoảng "từ 2 đến 3 năm") | `unparsed:multi_number`, không bỏ âm thầm nhưng chưa kiểm |
| 6 | P1 | Số **trong ngoặc diễn giải** bị bỏ: nếu claim sai nằm trong ngoặc thì không bị kiểm | Chủ ý (mục 5); chỉ an toàn khi số ngoài ngoặc đúng |
| 7 | P1 | `_PRED` là whitelist: từ vị ngữ hợp lệ ngoài danh sách làm hệ đã biết thành `UNKNOWN` (ra `ANNOTATE`, không gây sai nguy hiểm, nhưng tăng nhiễu) | Cần log `UNKNOWN:` trên dữ liệu thật |
| 8 | P1 | `NOT_COMPARABLE` mất `reason` cụ thể trong `_bucket` | Khó debug |
| 9 | P2 | Thực thể không nối qua câu; `scope` thời gian chỉ dùng khi dựng `Tup` tay | Có test ghim |
| 10 | P2 | Tiền (dấu chấm nghìn), phần trăm, số chữ ngoài 1–10 | Chưa xử lý (gold c25 PASS vì không có metric) |
| 11 | P2 | Số La Mã/ký hiệu `≥` có trong cue nhưng chưa test nhiều tổ hợp; `boundary_only` với "trên/dưới" dùng lỏng | Cần dữ liệu thật |
| 12 | P3 | Scope "mọi hệ"; tên hệ viết tắt ngoài `vlvh` | Chưa xử lý |
| 14 | P1 | **Hai điều khoản cùng `(metric, unit)` trong một nguồn** (tải đăng ký 14 tín chỉ/kỳ vs tổng 120) bị gộp một bucket → pessimistic → BLOCK oan một claim đúng và có trích dẫn. Đã giảm bằng cue `đăng ký` → `credit/semester` (có chốt chặn `tổng/tích lũy/tốt nghiệp/xét…`), **chưa giải tận gốc** | Hướng gốc: dùng `Theo Điều N` trong claim để giới hạn nguồn vào đúng điều (hiện `normalize` bỏ số điều). Tìm thấy từ log thật, chỉ có 1 ví dụ: **đừng tin cue này tổng quát hóa** |
| 13 | P1 | Query: nhãn lạ **không có chữ "hệ"** (`so sánh hệ chính quy và đại trà`) → vẫn ghim `full-time` | Cần từ điển nhãn; `xfail strict`: `test_gap_unknown_label_without_he_in_query` |

---

## 9. Giao thức gold set thật (P0 #1) — quyết định mặc định đã chọn

Bạn chọn "cứ mặc định": đã **sinh bộ synthetic** (`gold/seed.jsonl`) làm hồi quy. Để có bằng chứng recall thì thay bằng dữ liệu thật:

0. **Điều kiện tiên quyết (đã xác nhận thiếu):** log hiện có không chứa câu trả lời về quy chế thật (`so_tay_quy_che_dao_tao_2026.txt` do script benchmark sinh; các call thật còn lại là hỏi đáp về bài báo Wei et al.). Cần **Quy chế đào tạo thật của TDTU (PDF công khai)** nạp vào `rat`, rồi hỏi ≥100 câu có chủ đích (gồm câu so sánh hệ, câu có số, câu bẫy ngưỡng).
1. Lấy **≥100 cặp** `(SourceEvidence, res.answer, query)` từ log `rat` thật (không sinh lại bằng LLM), phân tầng theo điều khoản (thời gian, tín chỉ, ngoại ngữ, chế tài, học phí) và có cả câu ghép hệ.
2. **Gán nhãn tay `expected_gate` TRƯỚC khi chạy auditor**: `python label_sheet.py export …` → điền CSV → `python label_sheet.py import …` (`origin: "llm_real"`). Hai người gán nhãn cho ≥20% số ca, đo đồng thuận.
3. Chia **dev/test theo query** (50/50). Chỉ sửa module trên dev; số cuối cùng báo trên test.
4. Báo **precision và recall theo từng lớp** (`eval_gold.py` đã in) kèm **số mẫu của lớp**. Quy tắc nhanh: với `n` ca BLOCK thật và 0 lọt, cận dưới recall 95% ≈ `1 − 3/n` (n=30 → ≥90%; n=100 → ≥97%). Dưới 30 ca BLOCK thì không kết luận được recall.
5. Ca nào module sai: ghi `known_gap` hoặc sửa + thêm test + mutant. **Không** xóa ca khó.

---

## 10. Luật cho agent

1. **Không báo xong nếu chưa dán output thô** của `pytest -q`, `python mutation_check.py`, `python eval_gold.py`.
2. Mọi con số (latency, số test, số mutant, gold) phải **tự chạy lại**, không chép từ file này.
3. Đổi ngữ nghĩa verdict/precedence thì thêm **test và mutant**. Mutant sống sót = test chưa ghim. Refactor làm mutant `INVALID` thì **viết lại mutant**, đừng bỏ.
4. Không xóa hay nới `xfail strict`; sửa được gap thì test XPASS-fail, lúc đó đổi thành test thường.
5. Không thêm lời gọi LLM, mạng, hay phụ thuộc ngoài stdlib.
6. Sửa regex xong chạy trên tiếng Việt **NFC lẫn NFD**, có dấu/viết hoa/NBSP. `[A-ZÀ-Ỹ]` không an toàn (chứa cả chữ thường). Tránh lookahead phủ định bọc quantifier có thể backtrack (bài học `hệ 4,5 năm`).
7. Tích hợp (mục 6) làm trước, mở rộng gap (mục 8) sau. P0 #1 quyết định mọi thứ khác đáng làm hay không.
8. **Không** thực thi các Mega-Prompt khác trong dossier ở thread này; chúng thuộc tab khác.

## 11. Tiêu chí hoàn thành tích hợp

- [ ] Interface cũ còn dùng được (hoặc migration có chủ đích).
- [ ] `pytest -q`, `mutation_check.py`, `eval_gold.py` xanh **trong repo thật**, output dán kèm.
- [ ] `res.answer` thật qua `audit_answer` không ném exception trên ≥100 câu; mọi `unparsed` và `UNKNOWN:` được log.
- [ ] `infer_query_condition` của repo = bản tham chiếu (chạy `test_query_*` trên đúng hàm đó).
- [ ] UI hiển thị nhãn theo `anchor`, thanh độ phủ, và `copy_footer`; không có trạng thái "verified" toàn bài.
- [ ] Latency đo lại trên máy chủ dự án.
- [ ] Gold thật (mục 9) với recall/precision **theo từng lớp**, kèm số mẫu.
