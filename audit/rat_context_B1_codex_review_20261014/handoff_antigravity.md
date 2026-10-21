# Anti: sửa B1 theo Codex review, chưa wire B2

Đọc `audit/rat_context_B1_codex_review_20261014/review.md` và
`probe_results.json`; replay từ root:

```bash
PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m audit.rat_context_B1_codex_review_20261014.probes
```

Hiện21 probes:1 valid control,20 violates_requirement,0 probe_error. Runner
ghi `probe_results.json` tại review folder; khi replay cho **bản sửa**, chạy trên
copy của runner trong fresh repair folder và giữ nguyên source/evidence review
gốc. Chuyển các cases thành meaningful regression tests của B1; không đổi
expectation để giữ behavior đang làm mất ngữ nghĩa.

Codex giữ quyết định thiết kế. Anti thực hiện source/test/resource chores:

1. F1: positive typed ownership/exact slot paths và registered projector
   metadata. Bỏ global fallback theo leaf key. Unmodeled payloads/args/expected
   values/doc/proposal JSON là opaque, kể cả chứa quote/note/$value_ref. Wrapper
   shape phải exact; reject malformed generated wrapper, raw object giữ literal.
2. F2: exact JSON type/value +provenance trước dedupe. Không str/strip matching,
   không overwrite quote/source_ref.quote riêng, không ID-only substitution của
   immutable events bằng historical views. Khác value giữ inline raw. Dùng
   envelope+pointer tới value gốc để giữ scalar/list/string operation_result.
   Retain canonical provenance/status; không normalize IDs/revisions/owner để
   che missing data. Nếu duplicate identity bodies conflict, explicit error.
3. F3: boundary/control consistency trước assessment/render; scope filter
   receipts/proofs đúng conv/turn/exec/known generation. Giữ epochs riêng.
   Không fill missing receipt epoch/identity bằng current context. Foreign
   control block phải explicit error, old proof không vào current proof_refs.
   B1 không tự đọc live stores hoặc fabricate copy certificate; chuẩn bị API
   để B2 source copier đưa validated stamps/copies đúng boundary.
4. F4: semantic validation cho unique identity, pointer graph/cycles, all
   indexes/pins/current typed/native bindings. Missing refs có unavailable reason
   hoặc explicit error. Missing selected ID không được biến thành chose-empty;
   thiếu revision phải xử lý explicit theo thiết kế, không bịa default. Cycle
   guards có cả ở validator và expander. Không recursive traverse raw payload
   để khám phá “refs” theo wording.
5. F5: canonical dict/object assessment nhất quán; runtime-invalid export không
   qua proposal decoder rồi thành valid/met. Giữ errors/freeze/identity nguyên.
6. F6: schema là package-owned versioned resource, không load audit để runtime
   hoạt động và không fallback draft khác shape. Tests có thể so hash resource
   với approved design copy; không modify frozen audit copies để runtime pass.

Ưu tiên giữ public API hoặc migration rõ cho tests/callers. Một safe generic
result envelope chứa original value và receipt pointer tới nó có thể giúp F1/F2;
chỉ registered result projector được mở structured subslots. Không thêm matcher,
intent/relevance router, new model call, controller/freeze policy hay UI panel.

Deliver fresh `audit/rat_context_B1_fix_<timestamp>/`: manifest **trước** edits/
tests, source patch, focused new tests, original14+6 tests, selected292 regression
command từ existing core packet, raw logs/exit/hashes và generic examples.
Không overwrite original B1/review/design artifacts, không xóa failure logs,
không git push/pull/reset/force, không live inference/DocAI/Stage0 change.

Handoff cho Codex ghi từng F1–F6 đã xử lý thế nào, case nào remaining và precise
diff. Không gọi schema pass là semantic approval, không nói đã ngăn injection
mọiwhere chỉ từ một fake ref dưới remaining. B2 chỉ sau review source/cases mới.

Brief local để user chuyển sang Anti; không được gửi trực tiếp bằng app tool.
