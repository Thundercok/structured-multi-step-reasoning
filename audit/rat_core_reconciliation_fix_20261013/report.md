# RAT core — sửa trực tiếp sau review Round 3

Theo yêu cầu “bạn xử lý gọn luôn đi”, Codex đã sửa sáu nhóm lỗi đã tái hiện
trong review. **292 tests passed**, gồm 33 probes lịch sử, 227 selected
regressions và 32 boundary regressions trong product test suite. 11 fixture
transcripts xuất lại đạt assertions; exporter từ chối folder đã tồn tại và
không đổi nội dung cũ.

## Thay đổi

- `rat/engine/completion.py`: validate nested outcome fields trước matching;
  JSON export đệ quy cho immutable containers; JSON equality giữ array/object
  semantics và không coi boolean là số; common input/source/proof matchers.
- Calculator so canonical AST đã normalize, không lấy cùng numerical result
  làm chứng cứ cho cùng expression. Notes kiểm typed args ở committed parent
  operation trước khi kiểm terminal version. Generic consumer resolve declared
  producer artifact/revision và đối chiếu input reference; nguồn chưa resolve
  được giữ unmet.
- Response có proof requirement phải có PASS phù hợp. Verification receipts
  filter cùng conversation/turn/execution/generation. Native final checks lưu
  hash của candidate để proof cũ không áp vào câu trả lời mới; recheck gần nhất
  cho cùng candidate được dùng. Legacy trusted journal fixtures có explicit
  `final-answer` evidence marker vẫn được hỗ trợ; native path luôn bind hash.
- `rat/engine/assistant_runtime.py`: cùng outcome schema/decoder cho planner,
  native decisions và continuation/provided contracts. Planner quảng bá
  expected_args; model không cấp identity/frozen/valid flags. Raw malformed
  hoặc null metadata không bị rơi mất vì kiểm truthiness. Frozen contract có
  thể clone/rebind cho execution mới mà không sửa bản gốc.
- `tests/test_rat_completion_boundaries.py`: đưa 17 review probes thành
  regressions tự chứa, thêm 15 cases cho các ingress, candidate linkage,
  recheck, native planner ON/OFF và immutable contract rebinding.

Không thêm feature branches/keyword router, call model phụ, model/planner default
change, UI layout/notes panel hay DocAI. Source ngoài hai core files được giữ
nguyên trong phạm vi baseline đã snapshot. Research scope/Stage 0 không đổi.

## Kiểm chứng

| Kiểm tra | Kết quả |
| --- | --- |
| Probes lịch sử + selected regressions + boundary tests | 292 passed in 10.64s; exit 0 |
| Source trước/sau tests | Hai core files và test mới ổn định |
| Mock fixture export | 11/11 assertions qua |
| Ghi lại folder transcript đã tồn tại | FileExistsError, hash được giữ |
| Audit inputs lịch sử | 92 files không đổi hash |
| AST, whitespace của files sửa/thêm | Qua |
| git diff --check của runtime sửa | Qua |

Một lần kiểm `git diff --check` toàn checkout báo blank EOF trong hai test files
đã sửa từ trước bởi cộng tác viên; chúng không thuộc diff này và không được sửa
để cleanup. Kiểm tra scoped cho thay đổi của lượt này qua.

Các kết quả là software fixtures và mock native clients, **0 live inference**.
Chưa đo latency/cache/AI quality sau sửa và chưa kiểm UI/native. Việc đóng các
ca lỗi tái hiện không xác nhận model sẽ khai đủ mọi requested outcome hoặc hiểu
mọi intent. Scope/formal checker chưa hỗ trợ vẫn giữ unresolved/not_checked.

## Bàn giao

Các finding R1–R6 trong review Round 3 đã được xử lý trong bản sửa này. Review
và logs cũ giữ nguyên như evidence lịch sử; dùng packet này để xác định source
mới. Bước kế tiếp có thể là audit context A offline; schema snapshot B/C và
one-call D vẫn cần thiết kế theo phase đã thống nhất. Không giảm historical
note payload thành ID-only trước khi có resolver đọc note revision thật.

Artifacts: [patch](changes.patch), [tests log](regression_tests.txt),
[source/test hashes](test_run.json), [exporter check](exporter_check.json),
[validation](validation.json), [handoff cho Anti](handoff_antigravity.md).
