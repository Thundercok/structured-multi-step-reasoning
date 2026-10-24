# HANDOFF — Contradiction Auditor v2 (CPU-only, không LLM verifier)

Đích trong repo: `rat/engine/contradiction_auditor.py`. Gói gồm:

| File | Vai trò |
|---|---|
| `contradiction_auditor.py` | Module tham chiếu (≈680 dòng, stdlib thuần) |
| `test_contradiction_auditor.py` | 72 test lõi (+2 xfail strict = gap đã biết) |
| `test_report_and_edges.py` | 38 test (31 hàm, tính cả parametrize) lớp v2: span, annotation, summary, 4 lỗi biên, Unicode |
| `mutation_check.py` | 49 mutant cố ý; test suite **phải** đỏ trên từng cái |
| `eval_gold.py` + `gold/seed.jsonl` | Bộ gold 44 ca (42 chấm điểm, 2 `known_gap`), **toàn bộ `origin: synthetic`** |
| `probe_edge_bugs.py`, `probe_robust.py` | Script tái hiện 4 lỗi biên và kiểm Unicode/đo thời gian (in output thô) |
| `HANDOFF_CONTRADICTION_AUDITOR.md` | File này |

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
python -m pytest -q                      # kỳ vọng: 110 passed, 2 xfailed
python scripts/mutation_check_auditor.py # kỳ vọng: 49/49 killed, exit 0
python scripts/eval_gold.py gold/seed.jsonl # in confusion matrix + precision/recall từng lớp
python scripts/probe_edge_bugs.py        # raw output 4 lỗi biên + span
```

```python
from rat.engine.contradiction_auditor import build_index, audit_answer, copy_footer, infer_query_condition
kb = build_index(source_evidence_text)
query_condition = infer_query_condition(query)
rep = audit_answer(res.answer, kb, query_condition)
rep.gate          # "BLOCK" | "REGENERATE" | "ANNOTATE" | "PASS"
rep.annotations   # [Annotation(kind, reason, start, end, anchor)]  — offset trên res.answer GỐC
rep.summary       # dict đếm + rep.summary["note"] (câu tiếng Việt cho thanh độ phủ)
copy_footer(rep)  # chuỗi thêm vào khi người dùng copy văn bản thuần; "" nếu không cần
```

---

## 3. Pipeline

| Stage | Hàm | Ghi chú |
|---|---|---|
| 0 | `normalize_map` | **Giữ offset.** NFC (NFD từ macOS/PDF), NBSP→space, bỏ zero-width, bỏ markdown (`** __ \` #`), `=>`→"nên", bỏ `Điều/Khoản 15`, "sáu năm"→6, "4 năm rưỡi"→4.5, bỏ thang điểm "hệ 4/10/100" (không kèm năm/học kỳ), bỏ ngoặc diễn giải `(tương đương …)` |
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
