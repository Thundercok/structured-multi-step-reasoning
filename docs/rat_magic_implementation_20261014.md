# RAT: triển khai luồng một ô nhập và đưa tệp

Ngày 2026-10-14; cập nhật 2026-10-15, Asia/Ho_Chi_Minh. Thay đổi local theo yêu cầu sản phẩm;
không là kết quả NCKH hoặc bằng chứng chất lượng model. Stage 0 và DocAI
giữ nguyên phạm vi hiện tại.

Checkpoint source trước sửa đã push thành công lên
`codex/rat-source-checkpoint-20261014`, commit
`650e98b0b44df75ed20a1cc5ef6463b1d68f2ebe` trong repository
`Thundercok/structured-multi-step-reasoning`, sau khi người dùng cho phép
đúng payload. Theo yêu cầu push mới, thay đổi sau checkpoint được đóng gói
riêng trên nhánh `codex/rat-magic-workflow-20261015`; dữ liệu PDF và raw
model observations giữ private trên máy.

## Hành vi đã triển khai

- Cùng composer nằm ở đáy khung; khung ở phần dưới màn hình và lớn lên trên.
  Compact/full giữ editor, bản nháp, vùng chọn và điểm neo đáy.
- Đường chính giấu menu chức năng, nút gửi/mở rộng, suggestion chips, form
  dữ liệu, trace và hàng nút copy. `RAT_DEBUG_UI=1` giữ công cụ phát triển.
- Gõ dừng/stop hoặc Escape hủy execution đang chạy; notebook và dispatcher
  chặn commit muộn của execution đó. Không tuyên bố hoàn tác kết quả đã commit.
- `deliver_document` xác nhận tệp còn tồn tại, có trong chỉ mục, không đổi
  trong lúc băm; tạo artifact `document_file` tham chiếu tệp gốc, có SHA-256
  và kích thước. Không copy/upload hoặc tự mở tệp.
- Đính kèm lấy đường dẫn từ field của artifact đã đăng ký; lời model không
  tạo đính kèm. Tệp trùng từ tìm/đọc được gộp trong cùng panel. Click tên hoặc
  Enter chuyển đúng đường dẫn cho bộ mở; tệp mất được báo tại chỗ.
- Pending operation được giữ làm ngữ cảnh. Runtime cho model một lượt hỏi
  bổ sung trong ngân sách hiện có; nếu model không trả được câu hỏi, dùng
  prompt thật của pending operation. History giữ câu hỏi và khai báo cũ với
  nhãn lịch sử, không đưa receipt cũ thành bằng chứng execution mới.
  Khi người dùng bỏ việc đó, model có thể gọi `dismiss_pending_input` bằng
  request ID đã quan sát; thao tác không xóa các kết quả đã hoàn thành.
- Planner/actor/repair/finish dùng cùng compiler context từ bản sao canonical.
  Adapter kiểm tra generation, execution, note cursor, selection, artifact
  membership/revisions và pending state; thử lại hai lần rồi fail rõ nếu
  boundary thay đổi. Revision cũ cần thiết được pin, bản đã bỏ được đánh unavailable.
- Đường chính của app dùng một vòng native actor trực tiếp, catalog nhỏ và
  schema lấy thêm theo nhu cầu (`plan_tasks=False`, `discover_tools=True`).
  Model nhận facts gọn từ cùng snapshot đã kiểm tra và tool observations trực
  tiếp; context trống được bỏ khỏi lời nhắc. Boundary canonical được ghi riêng
  trong trace. Full typed context là tùy chọn `structured_context=True` dành
  cho chẩn đoán, không bắt model nhỏ tự lần JSON pointers.
- Khi opt-in contract/planner có khai báo, runtime dùng reconciler để kiểm tra câu trả lời sớm. Còn nghĩa
  vụ đã khai thì tiếp tục trong ngân sách còn lại; hết ngân sách không đưa
  câu nhận đã làm ra như thành công. Đường trực tiếp chưa khai contract giữ
  intent/completion coverage `unchecked`, không tạo bằng chứng hoặc outcome giả.
- Planner là tùy chọn. API mặc định giữ task state và typed outcomes.
  Opt-in `planner_operations_only=True` nhận `operations` do model chọn và `respond`;
  runtime chuyển cơ học thành op-N effects và reply, ghi provenance
  `model_planner_operations`. Tối đa 12 operations và một reply; khai báo trống
  không trả lời bị từ chối rõ. Contract API giàu kiểu và fixture outcome cũ
  giữ compatibility. Không tự tạo task state, suy tên operation từ keyword hay
  xem việc khai đúng tên như chứng minh đầy đủ ý định/nội dung.
  Raw request mới nhất là user message cuối, không nằm trước lịch sử trong JSON dài.
  Actor trực tiếp nhận sẵn schema tìm/đọc/tìm trang/đọc trang/đưa tệp và
  inspect nền tảng; đường opt-in planner nhận operation đã khai nếu có;
  `request_operation_tools` mở schema còn thiếu qua một kết quả dispatcher
  thành công của execution hiện tại. Không dùng keyword câu user để chọn
  feature, không có state tool-selection thứ hai. Receipt khám phá schema
  không thay receipt đọc/đưa tệp.
- Sau một answer repair đã qua scoped check, runtime bỏ schema chỉ dành cho
  repair trước khi tiếp tục effect còn thiếu. Không khóa phần việc còn lại
  trong chế độ chỉ được trả JSON answer.
- Sửa callback copy label chạy trễ sau khi widget hội thoại bị hủy; callback
  kiểm tra vòng đời Qt trước khi chạm widget.
- Lịch sử native giữ lời user và câu trả lời/câu hỏi thật của chuột. Turn lỗi
  không tạo một assistant message giả chứa `runtime_execution_status` JSON;
  trạng thái vẫn có trong turn references. Pending question vẫn giữ nguyên để
  model dùng câu trả lời bổ sung ở lượt tiếp.
- Sửa tìm tên tệp literal có extension: ưu tiên tên đã chuẩn hóa dấu/case,
  dấu ngoặc/underscore và giữ chữ số. Truy vấn `CALCULUS Assignment 6.pdf`
  được đối chiếu với tên indexed thực, tránh để từ `pdf` lấy các PDF khác.
  Tệp đã mất không thành kết quả; tên không có thật trả rỗng. Content search
  không có filename literal vẫn hoạt động.
- Kết quả tìm được đánh rõ `read=False`, `search_metadata_only`; prompt phân
  biệt tìm metadata với đọc nội dung. Core document I/O có schema ngay từ
  đầu để model không tốn thêm bước khám phá chỉ để đọc trang hoặc đưa file.

## Bằng chứng tệp thật và giới hạn

Đã dùng một PDF học thuật thực có 16 trang trong Downloads, chỉ mục mở
read-only. Dispatch thật tìm được các trang 2, 16, 1 cho cụm từ thử; đọc
trang 2 khớp chính xác text trích bằng pypdf. Delivery giữ hash/kích thước
của bản gốc. Thời gian client quan sát cho tìm file/tìm trang/đọc/đưa file
lần lượt khoảng 0.715/2.570/0.242/0.004 giây; đây là thao tác phần mềm,
không phải latency model hoặc benchmark.

Artifact thực đó đã render bằng Qt với composer đáy. Click tên và Enter
đều chuyển đúng path tới opener được patch để tránh bật ứng dụng ngoài;
chưa quan sát PDF mở trong ứng dụng ngoài. Ảnh và raw evidence chỉ lưu ở
`/private/tmp/rat-local-file-dispatch-20261014`, không vào source/payload push.

Collector `scripts/run_rat_local_file_smoke.py` giữ tối đa 3 lượt, 5 bước/lượt,
60 giây/call, 640 completion tokens/call và 15 calls toàn luồng gồm plan/repair.
Opt-in `--native-limits --max-steps 8 --timeout 90` dùng caps mỗi lượt của GUI;
global budget vẫn 15. Nó không tự xác nhận native GUI equivalence. 16 tests
collector đã qua sau khi thêm option (overlap với core suite, không cộng đúp).
Raw calls chứa tên/nội dung tài liệu chỉ được lưu ở output riêng ngoài Git
hoặc `.rat` được xác nhận ignore. Token thiếu là unknown/null, không là 0.
Collection completed không đồng nghĩa quality success.
Để khớp đường chính hiện tại, dùng `--no-plan --discover-tools`; không bật
`--structured-context`. Khác biệt số bước với GUI vẫn được giữ rõ; chưa
gọi headless collector là native equivalence.

Lần đầu với override tạm `qwen3:4b-instruct` có 3 planner timeout, mỗi call
khoảng 60 giây; chưa có thao tác model trên PDF. Health call riêng trả OK
trong 0.540 giây (13 prompt + 2 completion tokens). Diagnostic streaming
128 tokens cho thấy planner đang sinh JSON dài: first chunk 0.383 giây,
tổng 46.11 giây và kết thúc vì giới hạn token. Đây là exposed development
smoke, không được suy ra model hoạt động tốt hay schema là nguyên nhân duy nhất.

Các lượt phát triển sau bằng `qwen2.5:1.5b` cũng chưa đạt nghiệm thu. Planner
gọn có call quan sát 9.504 giây (613 prompt +54 completion tokens), nhưng có
khai báo response thay vì effect và actor timeout. Sau khi tách shape, một
call planner mất 8.084 giây (653 +24 tokens); model vẫn có thể chọn response-only.
Có lượt error=null và reconciliation satisfied nhưng không tìm/đọc tài liệu:
đó là thất bại chất lượng trong scope người dùng, không phải thành công.
Những số này là diagnostic đã exposed trên cùng yêu cầu phát triển, không
là so sánh model/benchmark. Lịch sử raw của cả lần lỗi được giữ nguyên ở
`/private/tmp/rat-local-file-magic-20261014-run*`; không thay default đã lưu.

Sau khi sửa tên literal, run9 tìm đúng PDF bài tập; model gọi inspect trên
metadata rồi timeout, Ollama sau đó ngắt kết nối. Run10 ngày 2026-10-15 kiểm
tra core document schemas với server local tạm: model tìm đúng tệp và đọc
trang PDF 1 nhưng timeout khi trả lời; lượt sau trả lại JSON trạng thái lỗi
nội bộ, lượt đưa tệp timeout. Manual review đánh thất bại toàn luồng. Lỗi
lịch sử sau đó được sửa: native history không giả status JSON thành lời
assistant; run11 thử lại bằng model mặc định `qwen2.5:1.5b`: không làm
thao tác, hỏi lại có bắt đầu không, và có timeout. Run12 rút gọn prompt đã
thực hiện search, nhưng model suy sai rằng PDF là scan khi chưa đọc, sau đó
lặp câu trả lời đó ở hai lượt tiếp mà không trích hoặc đưa tệp. Manual review
cả run11 và run12 đều thất bại. Model API trả không lỗi không đồng nghĩa
thành công chất lượng; app chưa được nghiệm thu magic với các model này. Các lần trước vẫn được giữ như failure evidence, không xóa/chọn lại
để tạo tỷ lệ thành công. Không đổi model mặc định đã lưu.

Lượt cuối run13 dùng đúng caps mỗi lượt của GUI: 8 steps, 90 giây/call,
vẫn tối đa 15 calls và chỉ model local. Turn tóm tắt đầu timeout; turn tiếp
thực hiện search_book_pages → read_book_page, đọc 1000/1489 ký tự đầu trang,
trích đúng câu và trang PDF 1 sau khi bỏ qua khoảng trắng do trích xuất PDF
(không là byte-exact quote). Turn cuối gọi deliver_document và tạo tệp đính
kèm gốc đúng path/hash/size. Hai lượt sau mất khoảng 105.50 và 86.41 giây
client wall time; không là latency đạt yêu cầu magic. Tổng thể vẫn thất bại
nghiệm thu vì lượt đầu lỗi. Đã replay câu trả lời và artifact do model tạo qua
Qt, thử click/Enter bằng opener được patch. Đây là render/integration check,
không là một native GUI model run mới. Raw report, ảnh và manual review ở
private tmp run13. Server tạm đã dừng; không đổi model mặc định đã lưu.

## Validation cuối 2026-10-15

479 core tests và 122 UI tests đã qua, thêm 3 subtests; source hashes không đổi
trong lúc chạy. Có hai loại trừ rõ: archived probe kỳ vọng nhận câu final dù
chưa làm effect, và test MetaReasoner legacy không thuộc đường AssistantRuntime
hiện tại, kỳ vọng valid cho dữ kiện chưa đủ. Lỗi ban đầu giữ nguyên trong audit;
không tuyên bố mọi test của repository đều qua. Xem
[validation packet](../audit/rat_magic_validation_20261015/README.md).

Kiểm tra hồi quy còn sửa trường hợp planner schema lỗi làm mất attribution
`invalid` thành `unchecked`. API planner mặc định vẫn quảng bá typed outcomes;
wire operation-list là opt-in chẩn đoán. Hai format không tự chứng minh đã làm việc.

Semantic claims trong prose của đường trực tiếp chưa có verifier tổng quát;
reconciler không thể coi `unchecked` là đã phủ hết yêu cầu. Vì vậy bản local có
cơ sở UI/delivery/context đã kiểm thử nhưng chưa nghiệm thu trải nghiệm model.

## Phạm vi còn lại

Đây là bước đầu của trải nghiệm magic. Chưa có artist animation mới, canvas
tổng hợp tùy ý, tự tiếp nhận sửa mục tiêu giữa execution, OCR hoặc refresh
comparison table tự động. Ngữ cảnh đầy đủ còn có thể lớn; cần đo và review
model thật trước khi nói trải nghiệm liền mạch đã được nghiệm thu.
