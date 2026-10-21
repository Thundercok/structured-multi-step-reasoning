# Anti — sửa core chung trước context optimization

Codex đã đối chiếu package `audit/rat_core_reconciliation_round3_20261013/`:
8/8 source hashes khớp, 33 probes cũ + 227 regressions = **260 passed**.
11 transcript fixtures xuất lại đạt assertions; exporter từ chối folder cũ
và giữ nguyên hash. Các sửa đã báo trước được ghi nhận.

**Chưa chốt core.** 17 boundary probes bổ sung có **11 failed, 6 passed**.
Đọc [review.md](review.md), [boundary_probes.py](boundary_probes.py) và
[log](boundary_probes.txt). Đây là deterministic/mock-native evidence, không
phải đánh giá model thật. Codex giữ vai trò thiết kế/review, chưa sửa runtime
hay product tests.

Sửa trong core chung, tránh tạo các bộ kiểm completion riêng cho từng feature:

1. **[P1] Validator contract dùng chung.** Native `source_ref` là string vẫn
   được nhận, tới final matcher thì crash `.get()`. Validate nested args/refs/
   dependencies/flags ở mọi ingress, trả invalid có reason, giữ effects đã
   commit. Review đường continuation/initial decision cùng schema.
2. **[P1] Immutable JSON values.** Nested MappingProxyType không deepcopy/
   export được; JSON arrays bị tuple hóa khiến thao tác chọn đúng `["a"]`
   bị unresolved. Thêm recursive JSON export và JSON-aware equality, giữ
   deep freeze. Dùng chúng cho mọi refs/args, không workaround riêng cho select.
3. **[P1] Typed input fidelity.** Calculate đang chấm `63 * 2` thỏa
   expected expression `18 * 7` chỉ vì đều ra 126. Canonical AST cùng expression
   vẫn cho `(18 * 7)` qua; không dùng numerical equality thay input binding.
   Note adapter đang bỏ qua expected text: lưu162 thỏa requested126. Đối chiếu
   committed operation args qua parent receipt, rồi terminal note version.
4. **[P1] Source binding cho consumer.** Generic adapter bỏ source_ref:
   calculate126 → inspect artifact999 vẫn satisfied consumer của calc.
   Producer completion và producer output linkage phải được kiểm độc lập.
   Common typed ref resolver/adapter metadata; requirement chưa hỗ trợ giữ
   unmet/unsupported, không bỏ qua rồi satisfied.
5. **[P1] Common scoped-proof gate.** Response đòi literal proof vẫn satisfied
   khi proof thiếu/UNKNOWN/FAIL. Foreign generation proof cũng thỏa calculate.
   Chọn proof đúng identity/generation, scope/authority/evidence/revision và
   candidate. Câu chat không khai proof vẫn trả lời được, không thêm tool giả.
6. **[P2] Native planner contract schema.** `_plan_task` chưa có expected_args
   trong outcome schema. Công bố và decode cùng schema chung cho ON/OFF;
   positive controls cần đi qua client mock, không chỉ inject Python objects.

Không thay đổi/skip/xfail probes cũ để đạt pass. Probe empty-contract trong log
initial của Codex đã được sửa theo ADR cho phép unchecked; bản final là chuẩn
review. Đừng lấy kết quả 12 failures ở log initial làm verdict cuối.

Chạy offline bằng Python đã có:

```bash
PYTHONDONTWRITEBYTECODE=1 /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -m pytest audit/rat_reconciliation_round3_codex_review_20261013/boundary_probes.py audit/rat_reconciliation_round2_codex_review_20261013/remaining_contract_probes.py audit/rat_reconciliation_codex_review_20261013/contract_probes.py -p no:cacheprovider -q
```

Giữ selected regression suite trong review log và nguyên tắc no-overwrite
exporter. Hash source trước/sau run; log exit code thực, raw errors và đủ
transcripts. Folder mới cho bàn giao kế tiếp, không ghi lại evidence lịch sử.
Không inference/UI/default-model/planner change, không DocAI/NCKH scope change,
không git push/pull/reset/force.

Context design A/B/C/D phù hợp nhưng còn hai dependency rõ: historical note refs
chưa đọc được qua `inspect_artifact` (ArtifactStore khác WorkNotebook), và context
snapshot cần giữ dữ liệu/continuity đủ cho follow-up ngoài tasks/notes. Đừng
giảm bản cũ thành ID-only trước khi resolver có thật. Registry deterministic
order cần audit trước khi sort; mock bytes/chars không chứng minh cache hay
speed-up. Chốt core rồi audit A, thiết kế B/C và spec D riêng.

Brief này chưa được gửi bằng tool sang Anti; người dùng có thể chuyển nguyên
file cùng audit folder.
