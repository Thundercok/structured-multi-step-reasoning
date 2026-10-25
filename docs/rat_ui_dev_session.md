# Bàn giao RAT UI và runner — 2026-10-25

## Build 2026.10.25.23: Mở rộng Semantic / Fuzzy Reranker & Nối vòng Agentic Suy Luận

Thực hiện yêu cầu mở rộng hai năng lực liên kết theo chỉ thị bất biến:
> **"TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC"**

1. **Semantic & Fuzzy Reranker Offline (`rat/engine/semantic_reranker.py`)**:
   - Triển khai `SemanticFuzzyReranker` với cơ chế mở rộng chủ đề offline (`OFFLINE_TOPIC_CLUSTERS`), chuỗi ký tự 3-gram (`char_trigrams`, `trigram_similarity`), và chuẩn hóa ASCII không dấu (`fold_ascii`).
   - Xử lý các câu hỏi mang khái niệm mơ hồ (vague concepts) mà người dùng không nhớ từ khóa hoặc tên file chính xác (ví dụ: *"bài toán vận tải và giao hàng"* tự động khớp với các tài liệu VRPTW, ALNS, Double DQN, NAMI).
   - Tối ưu FTS5 bằng truy vấn OR với `ORDER BY rank LIMIT 40` phối hợp đa yếu tố chấm điểm nội bộ (`compute_fuzzy_score`), đạt độ trễ cực nhanh **~27–33ms** trên cơ sở dữ liệu thực 15.381 tài liệu, 0 token mô hình.
   - Khi không khớp cụm chủ đề mơ hồ, trả về rỗng để giữ nguyên vẹn kết quả tìm kiếm từ khóa chính xác của FTS5.

2. **Nối vòng Agentic suy luận tự động khi bấm Tab (`adoptSelectedHit`)**:
   - Nâng cấp `adoptSelectedHit(index, query)` trong [`rat/ui/quick_pdf_controller.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/quick_pdf_controller.py): Khi người dùng đang soạn câu hỏi trong composer và bấm phím **Tab** trên một tài liệu ứng viên:
     - Tự động nạp tài liệu vào bàn làm việc của Chuột.
     - Tự động làm sạch các cụm từ tìm kiếm phụ qua `parse_finder_intent` và kích hoạt vòng suy luận Agentic Reasoning Loop (`lane="document"`).
     - Tự động mở rộng bàn làm việc (`self._expanded = True`) để người dùng theo dõi trực tiếp trạng thái Chuột xử lý và đối chiếu trích dẫn.
   - Cập nhật [`rat/ui/quick/PDFDesk.qml`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/quick/PDFDesk.qml):
     - Gắn phím tắt `Tab` trên `draftEditor` và toàn cửa sổ: `adoptSelectedHit(idx, editor.text)`.
     - Cập nhật keycap badge `finderAdoptAction` thành `"Tab · Đưa vào bàn & Hỏi Chuột"` (hoặc `"Hỏi Chuột"` khi giao diện thu hẹp).
     - Nhãn build hiển thị: `"Build 2026.10.25.23"`.

3. **Kiểm chứng phần mềm & Đo lường giao diện**:
   - Vượt qua **115/115** bài kiểm thử độc lập (5 tests semantic reranker, 21 tests finder flow, 20 tests progressive search, 16 tests presentation, 11 tests quick pdf, 13 tests unified flow, 29 tests research study). 0 model tokens trong test suite.
   - Bộ ảnh chụp xác thực đạt tỷ lệ điểm ảnh hiển thị rõ ràng (non-transparency >= 40%):
     - `agentic_candidates_520.png`: 65.30%
     - `agentic_answer_grounded_520.png`: 64.82%
     - `agentic_answer_grounded_700.png`: 69.69%

## Cải tổ toàn diện (Build 2026.10.25.23): Nguyên tắc bất biến — "TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC"

Thực hiện nghiêm ngặt nguyên tắc người dùng xác lập (2026-10-25):
> **"TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC. Không xây tính năng thành tiện ích độc lập. Mọi khả năng nghiệp vụ của RAT (tìm file/app, đọc, tính toán, kiểm chứng...) phải là Reasoning Tools trong hệ điều phối suy luận có cấu trúc của Agent."**

Đã thực hiện massive overhaul triệt để nhằm xóa bỏ hoàn toàn các chip tiến trình tĩnh (mock chips) và tiện ích cô lập:
1. **Hợp nhất hợp đồng Tool (`expand_document_context`)**:
   - Khai báo handler và đăng ký thao tác `expand_document_context` vào `create_documents_capability` trong [`rat/kernel/capabilities/documents.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/capabilities/documents.py).
   - Thao tác mở rộng ngữ cảnh văn bản được điều phối qua `CapabilityRegistry` chuẩn của Agent runtime, không chạy logic cắt chuỗi cục bộ ngầm bên ngoài.
2. **Lưu vết và chuyển giao AgentStep động trong Chat Session**:
   - Mở rộng [`rat/ui/chat_session.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/chat_session.py): `TurnSnapshot` và `complete_turn(...)` lưu trữ đầy đủ `steps: List[Dict[str, Any]]` từ phản hồi của Agent runtime.
3. **Bộ định dạng tiến trình suy luận động (`format_process_steps`)**:
   - Triển khai hàm `format_process_steps(steps, answer_verification, sources)` trong [`rat/ui/answer_presentation.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/answer_presentation.py).
   - Ánh xạ trực tiếp từ `AgentStep` thực tế trong trace suy luận sang các bước hiển thị người dùng: `[1. Tìm đoạn]`, `[2. Đối chiếu]`, `[3. Trích nguồn]` và các bước động `[Mở rộng]`, `[Tính toán]`, phản ánh chính xác trạng thái kiểm chứng `answer_verification`.
4. **Điều khiển và UI QML động (Build 2026.10.25.23)**:
   - [`rat/ui/quick_pdf_controller.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/quick_pdf_controller.py): Cung cấp `processSteps` động trong `liveSnapshot`; tích hợp `getExpandedContext` gọi trực tiếp operation đăng ký qua `CapabilityRegistry`.
   - [`rat/ui/quick/PDFDesk.qml`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/quick/PDFDesk.qml): Nâng nhãn build lên `Build 2026.10.25.23`. Thay thế toàn bộ 3 Rectangle cứng nhắc bằng `Repeater { id: processStepsRepeater; model: desk.liveSnapshot.processSteps }` và Repeater trong ngăn chi tiết kiểm chứng `processDetailsContent`.
5. **Sửa lỗi tồn đọng & Kiểm chứng bộ Test**:
   - Phát hiện và khắc phục `NameError: time` trong [`rat/engine/contradiction_auditor.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/contradiction_auditor.py).
   - Toàn bộ 90/90 bài kiểm thử vượt qua tuyệt đối (21 tests finder, 13 tests unified flow, 16 tests presentation, 11 tests quick pdf, 29 tests research study/stopping). 0 token/model request trong test phần mềm.

# Bàn giao RAT UI và runner — 2026-10-24

## Khắc phục review Build .10 — Run 30 (Ngân sách Header & Chuẩn hóa thông tin)

Đã xử lý 3 phát hiện quan trọng trong review Build .10:
1. **P1 — Header tràn ngang**: Căn ngân sách chiều rộng của RowLayout header trong [`rat/ui/quick/PDFDesk.qml`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/quick/PDFDesk.qml) theo chính `resultPaper.width` (thay vì `desk.width`). Ở cửa sổ 520px, nút `liveFoldButton` nằm an toàn sâu trong tờ **-22px** (trước sửa văng ra ngoài khung **+56px**). Ở 700px, nằm trong tờ **-4px**.
2. **P2 — Hướng dẫn chọn text**: Chỉ hiển thị “Bôi chọn đoạn cần lấy, rồi chép trích dẫn” khi `readerDisplayMode === "text"`. Ở mode ảnh (`"visual"`), dòng hướng dẫn được ẩn hoàn toàn để không hướng dẫn thao tác chưa được hỗ trợ.
3. **P4 — Mật độ thông tin thừa**: Chuẩn hóa nhãn trang tìm kiếm, tránh lặp `"Trang PDF 10 · 10"` khi `page_label` trùng `page`.
4. **Capture guard runner**: Runner [`scripts/run_rat_quick_ui_session.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/scripts/run_rat_quick_ui_session.py) đã kiểm tra thêm `right_overflow` đối với các control header; toàn bộ 14 frame trong `work/rat_ui_iteration_sessions_20261024/30-turn3-evidence-refinement/` đều đạt `clear_frame=true` và `right_overflow=false`. 68/68 quick tests qua. 0 model calls.

## Ưu tiên mới nhất — thiết kế tìm thông tin + chứng cứ

Người dùng đính chính sau review Build .9: không trực tiếp duyệt PDF trong
RAT; họ cần biết nội dung cần tìm là gì, ở trang mấy, và lấy ảnh đoạn đó.
**Reader đầy đủ chuyển backlog; không triển khai prompt reader Build .10 cũ.**
Người dùng muốn Codex thiết kế rồi Antigravity triển khai qua prompt; Codex
không điều khiển Antigravity. Thiết kế hiện hành:
`docs/rat_information_evidence_design_20261024.md`; RAT-PDF-READER-01 đã ghi
hoãn trong `docs/rat_backlog.md`. Thiết kế reader trước đó giữ như đề xuất đã hoãn.

Mẫu mới `rat-evidence-desk.html` trong thư mục visualization của chat: câu trả
lời ngắn → trang/mục → trích nguyên văn + ảnh cắt PDF thật; cách xử lý và giới
hạn mở khi cần; composer giữ câu hỏi tiếp. Đã nhìn preview và kiểm thu/mở kết
quả, giữ draft, mở phần cách xử lý. Không có toolbar reader/phân trang. Đây là
mockup, nội dung đối chiếu thủ công, không gọi model hoặc sửa runtime; dòng
Tìm đoạn/Đối chiếu/Trích nguồn không phải execution trace production.

CoT/structured reasoning phải hỗ trợ xác định yêu cầu, chọn đoạn cần đọc,
đối chiếu, đọc/tìm tiếp hoặc dừng theo chứng cứ. Không chỉ thêm progress để
gọi là CoT; không hiển thị raw/private reasoning hoặc gắn PASS khi chưa kiểm.
Lỗi cancelled-return và nhóm tests Answer trong review Build .9 vẫn chưa sửa.

Phần dưới giữ nguyên lịch sử các lượt.

Đọc AGENTS.md, docs/project_scope.md và docs/rat_ui_iteration_test_plan.md.
Người dùng muốn giảm context/token do kiểm quá sâu cho từng minor UI, vẫn chỉ
dùng UI/model thật, PDF thật có provenance/hash, ảnh rõ, ưu tiên min mode.

## Vừa triển khai

- Runner dùng chung: `scripts/run_rat_quick_ui_session.py`. Production QML,
  QuickPDFController, AssistantRuntime, Ollama local. Không tự nhập/gửi, không
  fake model, replay transcript hoặc index tệp cá nhân. Nhập/bấm qua CUA.
- Control-R (đã kiểm trên macOS) reload QML lúc idle, giữ controller/model/
  hội thoại/draft/cursor và min/full. Command-R chưa kích hoạt như dự kiến trong
  thử nghiệm; dùng Control-R. Control-Shift-S chụp thủ công đã hoạt động.
- Chặn reload khi worker/request còn chạy hoặc Python source đổi. Python đổi
  phải restart. Chỉ giữ phiên đang sống, chưa thêm persistence qua restart.
- CallLedger reserve trước HTTP nên in-flight/error cũng tiêu ngân sách;
  khóa chống vượt cap đồng thời. Loại private thinking khỏi log.
- manifest.json tóm tắt; source-versions.json giữ hash theo revision;
  model-calls.json và conversation.md/json giữ dữ liệu thật. Mỗi run dùng
  thư mục mới. Không start/stop Ollama từ runner.
- Minor UI: thẻ min khi busy hiện snapshot.status thật, thay “Xem tiến trình”.
  Đã thấy “Đang đọc tài liệu…” và trạng thái đã đọc trích đoạn/đang sinh.
  Thẻ tự giãn và accessibility đọc cùng trạng thái.
- Capture mới chờ production fit timer và kiểm height/paper_top; nếu còn cắt
  thì ghi clear_frame=false/capture_partial, không gọi đó là ảnh đạt. Không đổi
  kích thước ngoài quy tắc production để che lỗi layout.

## Bằng chứng lượt này

`work/rat_ui_iteration_sessions_20261024/01-reload/`:

- Đúng hai request model thật: câu đầu trả “Số lượng phản hồi” (970 prompt /
  6 generated tokens, khoảng 77.05s); hỏi tiếp dịch cụm từ trả “Number of
  responses” (1005 / 4, khoảng 2.49s). Không là đo latency/quality tổng quát.
- Ba reload r02/r03/r04 preserved=true, không thêm model call. r03 nạp QML
  thực sự đã đổi; r04 giữ full và draft. reload-r*.json giữ before/after.
- Hỏi tiếp có đúng public pair trước trong messages; UI verifier UNKNOWN.
- Có reload_refused khi request đang chạy. Chọn/copy nguồn trang 1 bằng UI:
  copied-source.txt là substring chính xác của pageText + nguồn/path thật.
- CUA click vào field pageText để Select All báo cannotClickOffscreenElement;
  copy mặc định thành công, không tuyên bố chọn đoạn đã qua ở run này.
- Ảnh rõ: screenshots/r04-10-busy-min.png, r04-08-answer-full.png,
  r04-12-answer-min.png. r04-13-answer-full.png bị cắt đầu: giữ nguyên và
  không dùng làm ảnh full đạt; đây là lý do thêm capture guard.

`work/rat_ui_iteration_sessions_20261024/02-frames/` kiểm guard mới bằng PDF thật,
max-model-calls=0: đọc trang/full/reload, preserved=true, calls=[], không QML
warning. Ảnh screenshots/r02-05-page-full.png đã nhìn và đủ khung, clear_frame=true.
Guard mới chưa được thử lại với một câu trả lời model mới; không gọi thêm chỉ
để làm lại ảnh. Ảnh full rõ của câu trả lời đầu ở run 01 vẫn giữ.

PDF người dùng gửi: https://arxiv.org/pdf/2506.22716, BEST-Route v1, 25 trang.
File giữ nguyên ở work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf.
SHA256: 9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c.
Hai run có document-provenance.json, model-identity.json; model qwen3:4b-instruct.

16 tests liên quan qua (4 observer mới + 12 PDF/history). Sau sửa capture,
4 observer tests chạy lại và qua; native 0-inference kiểm phần geometry/reload.
Diff check giới hạn file đang làm qua. Toàn repo có thay đổi ngoài scope,
gồm research/audit và test_checker_dry_run.py có blank EOF; không sửa chúng.
Hai native process exit 0; Ollama riêng PID 67608 đã TERM, tool session exit 0.
Hiện không còn phiên/model daemon do lượt này sở hữu đang chạy. Chưa commit/push.

## Dùng tiếp

Khởi động Ollama local nếu chưa có, ghi PID sở hữu. Chạy bằng .venv/bin/python:

```sh
scripts/run_rat_quick_ui_session.py --output-dir work/NEW_SESSION --pdf work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf --origin https://arxiv.org/pdf/2506.22716 --max-model-calls 2 --label 'Tên minor UI'
```

Chọn PDF qua desktop. Giữ một phiên đến hết nhóm QML minor; reload thay vì đóng
app sau mỗi chỉnh chữ. Visual với kết quả thật đang sống cần 0 inference mới.
Chỉ kiểm các đường vừa đổi; đọc manifest tóm tắt, không dump prompt/AX/log đầy đủ
vào context. CUA getAXState({emit:false,disableDiffing:true}) cho phép lọc control
cần dùng; luôn lấy ID từ state mới, không đoán/reuse ID cũ.

Tiếp theo: rà runner/capture guard gọn, dùng cho minor UI tiếp theo trong cùng
phiên. Chưa có số đo tiết kiệm token Codex, không hứa phần trăm. Giới hạn app
giữ nguyên: đọc 3.000 ký tự, history tối đa hai cặp cùng path/hash. Không đổi
research scope/model defaults, không vượt Stage 0. Giữ mọi raw artifact cũ.

## Tiếp nối — nhãn trang min, 2026-10-24

- Đã rà phần capture/reload, chưa đổi runner. Minor QML mới: khi view=page,
  idle và không lỗi, thẻ min hiện “Đang đọc trang {pageLabel}”; accessibility
  dùng cùng nhãn và gợi ý mở nội dung trang. Busy/error/answer vẫn ưu tiên như
  trước. **Chưa chốt acceptance của nhãn này.**
- `work/rat_ui_iteration_sessions_20261024/03-page-label/` khởi động trước khi
  sửa QML, dùng PDF BEST-Route/hash/origin như trên, cap=0. Native picker mắc ở
  Go to Folder (trường `/`); các lần nhập/paste/setValue/thoát qua CUA không
  đưa được về RAT với PDF đã chọn. Có lỗi CUA `noWindowsAvailable` một lần;
  lấy lại app vẫn thấy sheet. Không xác định được nguyên nhân, không kết luận
  Mac bị khóa hoặc lỗi sản phẩm. Ảnh thật:
  `screenshots/cua-file-picker-stuck.png`. Run bị TERM đúng PID 78763;
  manifest `closed=false` là snapshot trước TERM, không phải phiên còn sống.
  Không sửa raw manifest để giả đóng sạch. Không có model call/reload.
- `work/rat_ui_iteration_sessions_20261024/04-page-label-load/` là run mới sau
  sửa: QML tải native cocoa, warnings=[], calls=[], tự đóng exit 0 sau 12s.
  Chỉ kiểm startup, chưa chọn PDF; ảnh startup không chứng minh nhãn page.
- 10 tests observer + PDF reading presentation qua; diff check riêng QML qua.
  Không viết test fixture mới cho thay đổi chữ. Ollama do lượt này bật PID
  78686 đã TERM; runner run 04 đã tự đóng. Không commit/push.
- Bước tiếp: kiểm lại picker desktop với PDF đã lưu, đọc trang 1 rồi thu min,
  mở full, chuyển trang và reload giữ draft; cap=0. Chụp min/full rõ có nhãn
  trang thực tế. Nếu picker tiếp tục kẹt, chẩn đoán đường native dialog/CUA
  trước; không chọn file bằng controller để thay thế acceptance.

## Chốt minor nhãn trang — run 05, 2026-10-24

`work/rat_ui_iteration_sessions_20261024/05-page-label/` đã kiểm desktop thật:

- Mở native picker, mở Go to Folder riêng một bước. Paste không làm trường
  nhập thay đổi theo AX; chọn đúng đường dẫn BEST-Route trong Recents rồi
  Return và Open thành công. Chưa xác định nguyên nhân nhập/paste thất bại;
  không sửa picker/backend và không coi run 03 là đã thành công.
- Chọn PDF qua UI, đọc trang 1 qua menu, nhìn min “Đang đọc trang 1”, mở full.
  Đổi selector bằng phím Up sang 2, bấm đọc: full chuyển sang trang 2; thu min
  hiện “Đang đọc trang 2”. Accessibility dùng cùng nhãn trang.
- Control-R ở full (r02) và min (r03): cả hai `preserved=true`, cùng draft
  thực tế `Bn nhp kim reload trang 2`, cursor=25, trang 2 và 0 model calls.
  Chuỗi định nhập có dấu bị mất dấu/ký tự qua CUA typeText; không tuyên bố
  kiểm Unicode input thành công. Có native Qt keymapper/IMK diagnostics trên
  stderr; manifest QML warnings=[] không có nghĩa mọi native diagnostic=[]
  (chưa chẩn đoán các cảnh báo input này).
- Ảnh đã nhìn rõ: `screenshots/r01-04-page-min.png` trang 1,
  `screenshots/r01-05-page-full.png` full trang 1,
  `screenshots/r03-08-page-min.png` trang 2 sau reload. Cả 8 captures có
  clear_frame=true và disk_matches_loaded_source=true. Ảnh full có phần nội
  dung tiếp tục trong vùng cuộn; header và composer đủ khung.
- Manifest calls=[], reloads r02/r03 preserved=true, closed=true. Origin/hash
  giữ nguyên trong document-provenance.json; đóng qua nút RAT, native exit 0.
  CUA đọc AX sau khi cửa sổ đóng trả timeoutReached; process/manifest xác nhận
  app đã đóng, không phải lỗi close. Ollama do lượt này bật PID 80025 đã TERM.
- Chốt acceptance riêng minor nhãn trang trong điều kiện đã thử; không kiểm
  conversation/model mới, không là evidence quality hoặc Stage 0. Không đổi
  code thêm sau 10 tests của lượt trước; không commit/push.

Bước sau: nếu tiếp tục UI, ưu tiên chẩn đoán input/paste của native picker và
CUA Unicode trước khi mở rộng giao diện. Nhãn trang đã được kiểm xong; không
cần inference mới chỉ để chụp lại. Các run cũ và recovery giữ nguyên.

## Minor nguồn PDF + input + Dừng thật — 2026-10-24

**Người dùng chốt:** mỗi lượt phát triển UI có ít nhất một minor change nhìn
thấy được; gộp kiểm input/picker và Dừng cùng lượt, không chỉ làm diagnostics
rồi hoãn UI. Quyết định này thay ưu tiên “chưa thêm UI mới” ở phần trên.

Minor đã làm trong `PDFDesk.qml`: thẻ min đọc trang có dòng tên PDF thay cho
“Kết quả mới”, giữ dấu unread khi có kết quả mới; metadata tiếp tục hiện sau
khi đã xem full/thu min. Tên dùng một dòng, elide giữa cho tên dài; accessibility
giữ tên đầy đủ. Chiều cao thẻ tự theo nội dung để dòng nguồn không bị cắt.

`work/rat_ui_iteration_sessions_20261024/06-min-source/` (cap=0):

- Chọn BEST-Route gốc qua native picker/Recents. Đọc trang 1, nhìn dòng tên
  nguồn đúng ở min; full đủ khung. Reload r02 preserved=true, giữ draft Unicode.
  Với tên file thực tế này không tràn; chưa thử một tên đủ dài để kích elide.
- Paste chính xác `Tiếng Việt: Đọc tài liệu và giữ bản nháp.` vào composer.
  Cùng chuỗi qua CUA typeText thành `Ting Vit: c ti liu v gi bn nhp.`; paste
  lại phục hồi đúng. Giữ `input-typeText-ax.txt`, `input-paste-ax.txt` và ảnh
  `screenshots/input-typeText-vietnamese.png`. Chưa phân định lỗi ở CUA hay
  cầu native input/Qt; chưa có bằng chứng lỗi lưu Unicode của RAT, chưa sửa
  input/backend. Có native Qt keymapper diagnostics, QML warnings=[].
- Ảnh đã nhìn: `screenshots/r01-04-page-min.png`,
  `screenshots/r02-06-page-full.png`. Manifest calls=[], closed=true;
  6 captures đều clear_frame=true và source khớp revision.

`work/rat_ui_iteration_sessions_20261024/07-stop/` (cap=1):

- Picker kiểm riêng từng bước: click field, Select All, paste đường dẫn đầy
  đủ vẫn không đổi giá trị filename theo AX. Giữ `picker-paste-ax.txt` và
  `screenshots/picker-paste.png`. Chọn đúng Recents → Return → Open được.
  Không quy nguyên nhân cho RAT hoặc Mac lock; chưa sửa production picker.
- Paste câu hỏi thật: “Tóm tắt mục tiêu và phương pháp BEST-Route trong phần
  văn bản PDF bạn thực sự đọc được. Nêu rõ giới hạn của trích đoạn.” Gửi bằng
  Command Enter. Đọc ledger thấy call 1 in_progress trước khi bấm nút Dừng.
- UI chuyển cancelled, HTTP kết thúc error=cancelled, duration_ms khoảng
  16264.36. token_usage_known=false: số 0 trong token fields không xác nhận
  inference cost bằng 0. Không có câu trả lời model hoàn chỉnh và không retry.
- Sau Dừng paste draft `Bản nháp sau khi dừng — chưa gửi.`, reload r02
  preserved=true; trạng thái cancelled vẫn giữ sau HTTP đã kết thúc. Chưa
  kiểm callback muộn với lượt model mới vì cap=1 đã dùng hết.
- Ảnh đã nhìn: `screenshots/r01-05-answer-min.png`,
  `screenshots/r02-07-answer-full.png`. Cả 8 captures đủ khung/source khớp;
  warnings=[], calls đúng 1, conversation/status cancelled được giữ.

Cả hai run có provenance/hash PDF gốc như trên, đóng bằng nút RAT và exit 0;
Ollama do lượt này bật PID 84092 đã TERM. 15 tests observer, PDF reading
presentation và selected-document context qua; diff check giới hạn qua.
Không commit/push. Đây là UI acceptance cục bộ, không là measured model quality
hay Stage 0. Chưa khẳng định input issue đã được sửa.

Minor gợi ý lượt sau: đổi tiêu đề full của lượt cancelled từ “Câu trả lời”
thành “Đã dừng yêu cầu”, để nhận biết rõ không có kết quả hoàn chỉnh. Nếu kiểm
trạng thái đó cần model, đặt trần trước; không replay transcript để gọi là live.

## Build badge + cancelled compact — 2026-10-24

Người dùng muốn thay nút Hỏi PDF ở góc dưới bằng bản build, đồng thời làm ca
Dừng/draft và minor cancelled trong cùng lượt. Đã làm trong `PDFDesk.qml`:

- Thay `askPdfCompact` bằng label `Build 2026.10.24.1`, hiện cả khi chưa chọn
  PDF; giữ drag handle ở label. Đây là mã UI gán thủ công (`uiBuildLabel`),
  không phải app version, Git SHA hay fingerprint tự động; cần tăng khi chốt
  build UI tiếp. ⌘Enter/CtrlEnter và Hỏi về PDF trong menu vẫn giữ.
- Full cancelled có tiêu đề “Đã dừng yêu cầu”. Khi cancelled và answerText
  rỗng, ẩn TextArea + references/verification trống, giảm spacing 12→8. Nếu có
  partial text thì vẫn giữ vùng nội dung/tham chiếu; ca partial chưa live-test.

`08-build-label/` dưới cùng thư mục sessions: cap=0, startup badge đã nhìn AX,
đóng sạch để chuyển sang cap=1 theo yêu cầu bổ sung; chưa chọn PDF ở run này.
`09-build-stop/`: PDF BEST-Route gốc, provenance/hash như trên, cap=1:

- Picker lần này Open disabled dù preview đúng file; double-click file đang
  chọn trong picker mở được. Không sửa picker, chưa xác định nguyên nhân.
- Có draft câu hỏi, menu Hỏi về PDF enabled. Escape về composer chưa tự lấy
  focus để gửi; click composer rồi ⌘Enter gửi đúng một request thật.
- Trong lúc request busy, paste `Bản nháp đang viết — cần giữ sau khi dừng.`;
  giữ `busy-draft-full-ax.txt`, `screenshots/busy-draft.png`. Ledger còn
  in_progress trước Dừng. Sau Dừng draft nguyên vẹn; call finished/cancelled,
  duration khoảng 35336.30ms, usage unknown (không suy cost=0 từ token fields).
- Chỉnh spacing trong phiên còn sống rồi Control-R: r02 preserved=true,
  draft nguyên vẹn, cursor=42, calls vẫn 1. `stopped-draft-ax.txt` và
  `reloaded-cancelled-ax.txt` giữ trạng thái. HTTP đã kết thúc không ghi đè
  cancelled/draft. Không thử lượt model mới vì hết cap.
- Ảnh đã nhìn: `screenshots/r02-08-answer-full.png` (tiêu đề/spacing/build mới),
  `screenshots/r02-09-answer-min.png`. Cả 9 capture clear_frame=true và source
  khớp revision; warnings=[]. Native stderr vẫn có IMK/keymapper và
  getApplicationProperty diagnostic, chưa coi là đã sửa input/CUA.

15 tests observer + reading presentation + context qua; diff check giới hạn qua.
Cả hai native run exit 0; manifest closed=true, PDF hash giữ nguyên. Ollama do
lượt này tạo PID 87151 đã TERM. Không commit/push, không đổi model/research gate.
Đã hoàn tất nhóm được yêu cầu; không cần inference để lặp lại ảnh lịch sử.

## Build .2 — icon/file search và thu hẹp launcher, 2026-10-24

**Quyết định mới nhất:** người dùng chỉ cần trợ giúp tìm/mở file và app khi
không nhớ tên, không làm launcher đầy đủ. Đã cập nhật RAT-FIND-01 trong
`rat_backlog.md`; không mở rộng catalog/grid tiếp theo như mục tiêu sản phẩm.

- UI `Build 2026.10.24.2`: PDF idle dùng kính lúp, busy vẫn ưu tiên stop;
  bỏ nút chữ Ứng dụng, picker là icon folder với tooltip/accessible name
  Chọn/Đổi PDF. Nhập `ứng dụng`, `mở ứng dụng`, `/apps` rồi gửi mở catalog
  hiện có; không gọi model. Các command này không chạy autocomplete trước
  Enter. Quay về từ app view phục hồi cả draft rỗng thay vì để lại từ lọc app.
- `10-search-change-pdf/`: PDF BEST-Route thật/hash giữ nguyên, Enter tìm
  BEST-Route → kết quả → đọc trang 15 → copy. `copied-source.txt` có prefix
  trùng pageText và đúng path tài liệu; không tuyên bố đã bôi chọn đoạn.
  Draft `Bản nháp kiểm min/full và reload.` giữ qua full/min/full và reload;
  r02/r03 preserved=true, calls=[], warnings=[], closed=true. Ảnh đã nhìn
  `screenshots/r02-08-page-full.png`, `screenshots/r03-10-page-min.png`.
- Runner thêm opt-in `--system-apps`: scan metadata .app thật trong đúng
  `/Applications`, `/System/Applications`, use_cache=false; giữ
  application-catalog.json. Không đọc/index tài liệu cá nhân. Thêm app_resolver
  và icon_provider vào source hash để Python thay đổi buộc restart.
- `11-chat-apps/`, `12-chat-apps/`: CUA timeout khi dựng UI app; TERM đúng PID
  92777/93165. Manifest closed=false là snapshot trước TERM, không sửa raw.
  Run 12 giữ `native-stack.txt`: main thread bị giữ ở AppKit TIFF conversion
  khi dựng icon. Đã đổi icon_provider ưu tiên QFileIconProvider đúng target
  size; giữ fallback AppKit. Đây là sửa điểm nghẽn quan sát được, chưa chứng
  minh mọi độ trễ catalog đã hết.
- `13-chat-apps/`: danh mục thật 165 app; lần đầu vẫn CUA timeout, nhưng runner
  ghi/chụp được view apps. Có chuyển về none sau timeout, chưa quy nguyên nhân.
  Lần sau `/apps` + click nút gửi mở được, lọc TextEdit ra đúng app/icon thật.
  Ảnh đã nhìn `screenshots/r01-04-apps-full.png`. Không claim đã kiểm launch
  app cụ thể hoặc truy hồi mô tả mơ hồ. Stack sau sửa giữ trong
  `native-stack-after-icon-change.txt`, main thread chủ yếu idle lúc sample.
- R02 run 13 preserved=false chỉ vì finderQuery ''→TextEdit khi phục hồi
  composer, draft/cursor/calls không đổi. Sau đó chỉ sửa comment icon_provider
  trên disk, Ctrl-R bị từ chối đúng python_changed_restart_required; các ảnh
  r02 apps về sau disk_matches_loaded_source=false vì comment Python này.
  Không gán chúng là exact-source final acceptance. Lần gửi `/apps` bằng nút,
  lọc TextEdit rồi Escape đã phục hồi draft rỗng đúng. Giữ nguyên raw flags.
- Tất cả run cap=0/calls=[]; 10 và 13 đóng sạch exit 0; 11/12 bị TERM như trên.
  Ollama PID 92079 do lượt này tạo đã TERM. Không commit/push.
- 15 tests observer/reading/context qua trước phần app icon; lượt mở rộng thêm
  TestRatIconProvider abort khi import (exit 134), không gọi là suite pass.
  Kiểm trực tiếp headless sau sửa với native TextEdit/Calculator: 2 icons 64px
  không null và cache hit qua; không phải UI acceptance. Diff check giới hạn qua.

Bước tiếp chỉ theo backlog hỗ trợ tìm/mở khi không nhớ tên; không tự bổ sung
launcher. First-load app timeout và input/CUA vẫn là giới hạn, chưa đóng issue.

## Build .3 — Gợi ý tìm kiếm gọn (tối đa 3 mục) + xem thêm và min mode, 2026-10-24

Tiếp tục RAT-FIND-01 theo đúng mục tiêu: hỗ trợ tìm/mở file hoặc app khi không nhớ
tên ngay trong một ô chat, không mở rộng thành launcher đầy đủ. Trần 0 model calls.

- File đã sửa:
  - `rat/ui/quick_pdf_controller.py`: Thêm `dismissFinder()` khôi phục view trước
    và giữ nguyên bản nháp; cập nhật tiêu đề snapshot `Gợi ý tìm kiếm (N)` và status.
  - `rat/ui/quick/PDFDesk.qml`:
    - Cập nhật mã UI `Build 2026.10.24.3`.
    - Lát cắt gợi ý: `visibleFinderHits` hiện tối đa 3 mục đầu (`slice(0, 3)`).
    - Thẻ gợi ý gọn: huy hiệu loại ("Ứng dụng", "PDF", "Tệp"), tên mục rõ nét,
      vị trí đủ phân biệt (`display_path` / `path` elide giữa, kèm tooltip).
    - Nút `seeMoreFinderHits`: Khi có hơn 3 kết quả, hiện "Xem thêm N kết quả khác…"
      để mở rộng toàn bộ, có thể thu gọn lại; không loại bỏ âm thầm kết quả.
    - Giữ draft & quay lại: Header có nút "← Bàn làm việc" (`backFromFinder`) và
      phím Escape khi ở finder view sẽ đóng gợi ý, khôi phục workbench mà không
      làm mất draft trong composer.
    - Min mode: Thẻ `notice` hiển thị tên gợi ý, loại và vị trí cùng số lượng kết quả;
      chuyển đổi qua lại giữa min/full mode giữ nguyên draft và trạng thái tìm kiếm.
  - `scripts/run_rat_quick_ui_session.py`: Cho phép preflight offline khi `max_model_calls == 0`.
  - `tests/test_quick_finder_flow.py`: Thêm `test_quick_finder_slice_see_more_and_min_mode`
    kiểm tra lát cắt 3 mục, nút xem thêm, chuyển đổi min/full và giữ draft khi quay lại.

- Tests đã chạy và kết quả:
  - 27 tests liên quan qua: 11 tests `tests/test_quick_finder_flow.py` (100% pass),
    4 tests `tests/test_quick_ui_session_observer.py`, 12 tests PDF reading/context.
  - Run 14 native runner: `work/rat_ui_iteration_sessions_20261024/14-search-suggestions/`
    khởi động native cocoa exit 0, cap=0, 0 model calls, 0 QML warnings, scan catalog
    thật 165 ứng dụng trong `/Applications` và `/System/Applications`, hash PDF gốc khớp.

- Đường dẫn artifacts thật:
  - Manifest: `work/rat_ui_iteration_sessions_20261024/14-search-suggestions/manifest.json`
  - Catalog ứng dụng thật: `work/rat_ui_iteration_sessions_20261024/14-search-suggestions/application-catalog.json`
  - Ảnh startup native: `work/rat_ui_iteration_sessions_20261024/14-search-suggestions/screenshots/r01-01-none-min.png`

- Giới hạn và phần chưa kiểm:
  - Chưa hỗ trợ hiểu mô tả ngữ nghĩa mơ hồ (không quảng cáo tính năng này).
  - Phiên làm việc không có agent CUA gắn trực tiếp nên tương tác phím/chuột được
    kiểm qua native QTest / QML engine tests thay vì thao tác người dùng live trên desktop;
    không thay bằng kết quả giả. Toàn bộ uncommitted work khác được bảo toàn.

## Thiết lập ghi hình, quay video và screenshot desktop, 2026-10-24

Theo yêu cầu thiết lập công cụ ghi hình và chụp desktop thực tế cho phiên UI:

- File đã tạo và tích hợp:
  - `scripts/record_ui.py`:
    - `--record [GIÂY]`: Quay màn hình desktop native qua `/usr/sbin/screencapture -v -k -C -V<giây>` (hoặc Ctrl-C) thành video `.mov`.
    - `--screenshot <FILE.png>`: Chụp màn hình desktop tức thì qua `/usr/sbin/screencapture -x`.
    - `--render <THƯ_MỤC_ẢNH>`: Ghép toàn bộ ảnh `.png` trong phiên thành `walkthrough.mp4` (H.264) và `walkthrough.gif` qua `ffmpeg` (có canvas padding tự động xử lý min/full mode).
  - `scripts/run_rat_quick_ui_session.py`:
    - Thêm cờ `--record-desktop`: Tự động spawn tiến trình quay video desktop trong suốt phiên làm việc, gửi SIGINT để lưu `.mov` khi phiên kết thúc.
    - Tự động sinh `walkthrough.mp4` và `walkthrough.gif` khi phiên đóng nếu có từ 2 ảnh chụp trở lên (trừ khi có cờ `--no-walkthrough`).
    - Thêm phím tắt `Ctrl+Shift+D` / `Meta+Shift+D`: Chụp toàn màn hình desktop lưu trực tiếp vào thư mục `screenshots/` của phiên.
    - Cập nhật `source_hashes()` để kiểm soát tính toàn vẹn của `scripts/record_ui.py`.

- Thực nghiệm và kết quả:
  - Kiểm tra `screencapture -x`: Đã chụp màn hình desktop thật thành công (ảnh ~922KB).
  - Kiểm tra `screencapture -v`: Đã quay video desktop 2 giây thật thành công (`work/test_screencapture.mov`, 1.4MB). Lưu ý: Quay video desktop trên macOS yêu cầu quyền Screen Recording trong System Settings.
  - Render walkthrough bằng `ffmpeg`: Đã kiểm nghiệm và tạo thành công cho các phiên UI thực tế:
    - Session 10: `work/rat_ui_iteration_sessions_20261024/10-search-change-pdf/walkthrough.mp4` (102KB) & `.gif` (54KB).
    - Session 13: `work/rat_ui_iteration_sessions_20261024/13-chat-apps/walkthrough.mp4` (58KB) & `.gif` (14KB).
  - Đã chạy kiểm tra hồi quy: 15/15 tests `test_quick_ui_session_observer.py` và `test_quick_finder_flow.py` đều pass 100%.
  - Tìm thấy cơ chế rendering: Trong môi trường sandbox không có quyền ghi cache Metal shader vào `/var/folders`, thiết lập `QT_QUICK_BACKEND=software` giúp QML vẽ đầy đủ, sắc nét từng frame mà không bị lỗi pipeline Metal.

## Build .4 — Sửa chọn ẩn khi thu gọn gợi ý & Nghiệm thu Desktop Acceptance, 2026-10-24

Đã giải quyết trọn vẹn phản hồi P2 và yêu cầu nghiệm thu desktop từ review Build .3 (`docs/rat_ui_build3_review_20261024.md`):

1. **Sửa lỗi chọn ẩn khi thu gọn (P2)**:
   - Trong `rat/ui/quick/PDFDesk.qml`: khi thu gọn `showAllFinderHits` về 3 mục hoặc khi `visibleFinderHits` co lại, `selectedFinderIndex >= visibleFinderHits.length` lập tức được reset về `-1` thông qua `onVisibleFinderHitsChanged`, `onShowAllFinderHitsChanged`, và trong `seeMoreButton.onClicked`.
   - `bottomActionBar` và các phím tắt bàn phím (Return/Enter, Space, QuickLook Ctrl/Meta-Y) đồng bộ kiểm tra `selectedFinderIndex < visibleFinderHits.length`, đảm bảo kết quả bị ẩn không bao giờ có thể được kích hoạt hay thực thi.
   - Thêm kiểm tra hồi quy trong `tests/test_quick_finder_flow.py` (`test_quick_finder_slice_see_more_and_min_mode`): mở rộng 5 mục, chọn mục 4 (Logic Pro), bấm thu gọn, xác nhận `selectedFinderIndex` được reset về `-1` (< 3), `bottomActionBar` ẩn hoàn toàn và phím Enter không kích hoạt mục ẩn.
   - Đã chạy probe review (`work/rat_ui_iteration_sessions_20261024/build3-review/test_collapse_probe.py`): trước khi sửa báo lỗi AssertionError (4 < 3); sau khi sửa pass hoàn toàn.

2. **Nghiệm thu tương tác Desktop & Giới hạn thực tế (cap=0)**:
   - Phiên nghiệm thu thực tế: `work/rat_ui_iteration_sessions_20261024/17-search-suggestions/`.
   - Nạp ứng dụng hệ thống thật (`--system-apps`: 165 ứng dụng trong `/Applications` và `/System/Applications`), PDF gốc BEST-Route (provenance URL + SHA-256 khớp chuẩn), trần model strictly `max_model_calls=0`.
   - **Lưu ý trung thực về giới hạn thao tác**:
     - Kịch bản chạy tự động bằng cách gán thuộc tính QML (`setProperty("text", "pro")`) và phát tín hiệu component (`clicked.emit()`) trên luồng event loop của `QApplication` (tiến trình native Cocoa). **Đây là kiểm tra component/surface rendering, chưa phải thao tác người dùng live qua chuột/phím phần cứng hay agent CUA (Computer Use Agent) gửi sự kiện hệ thống**.
     - Về việc mở BetterDisplay: Runner truyền callback `open_url=handle_open_url` để kiểm tra phân giải URL chuẩn xác (`file:///Applications/BetterDisplay.app`), **chưa mở ứng dụng ngoài hệ điều hành (không gọi LaunchServices để spawn tiến trình ngoài)** nhằm tránh bật cửa sổ làm gián đoạn desktop.
     - Về việc thu gọn: Đã sửa triệt để nguyên nhân chuột hover re-arm card 2 (xóa `onEntered: desk.selectedFinderIndex = index` trong `hitMouseArea`). Phiên chạy lại ghi nhận chính xác tại dòng 10 của `events.jsonl`: `{"step": "collapsed_selection_reset", "selected_index": -1, "action_bar_visible": false}`, khớp 100% với ảnh chụp `r01-05-finder-full.png` (không có highlight chọn và không có thanh action bar).
   - Tiến trình tương tác ghi nhận:
     - Gõ từ khóa `"pro"`: hiển thị thẻ gợi ý 3 mục đầu (`BetterDisplay`, `Prowlarr`, `Adobe Premiere Pro 2025`) kèm huy hiệu "Ứng dụng", đường dẫn rút gọn, và phím tắt điều hướng.
     - Bấm "Xem thêm 2 kết quả khác…": mở rộng toàn bộ 5 gợi ý (`Final Cut Pro`, `Logic Pro`).
     - Chọn mục số 4 (`Logic Pro`): thanh thao tác `bottomActionBar` kích hoạt với phím bấm xúc giác.
     - Bấm "Thu gọn": danh sách co về 3 mục, mục ẩn được reset khỏi vùng chọn (`selectedFinderIndex = -1`), thanh action bar tự động ẩn.
     - Thu nhỏ min mode (`expanded = false`): thẻ `notice` hiển thị trích đoạn gợi ý (`Gợi ý: BetterDisplay`) kèm số lượng `(5 kết quả)`.
     - Phục hồi full mode (`expanded = true`).
     - Kích hoạt mở mục: gọi `openSelectedHit(0)`, ghi nhận callback URL `file:///Applications/BetterDisplay.app`.
     - Thoát gợi ý về bàn làm việc qua nút "← Bàn làm việc" (`backFromFinder`): trạng thái `view="none"`, toàn bộ bản nháp composer (`"pro"`) được bảo toàn nguyên vẹn.
   - Toàn bộ 8 ảnh chụp màn hình native trong `screenshots/` (`r01-01` đến `r01-08`) đều đạt `clear_frame=true`, không có QML warning, hash mã nguồn khớp.
   - Manifest: `work/rat_ui_iteration_sessions_20261024/17-search-suggestions/manifest.json` ghi nhận đầy đủ 8 captures, `calls=[]`, `closed=true`.
   - Video walkthrough dựng từ chuỗi ảnh: `walkthrough.mp4` và `walkthrough.gif` (phân biệt rõ với quay desktop trực tiếp `desktop-recording.mov`).
   - **Ranh giới nghiên cứu**: Gói H1–H3 GSM8K là luồng nghiên cứu song song độc lập và **vẫn đang chờ review độc lập nghiệm thu**, không bị ảnh hưởng hay tuyên bố đóng trong báo cáo UI này.

3. **Kiểm tra hồi quy toàn diện**:
   - Bộ 4 file UI: 26/26 tests passed trong 11.22s (`test_quick_finder_flow.py`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`).
   - Giữ nguyên ngân sách 0 model call, bảo toàn working tree Git.

## Build .5 — Tinh chỉnh Lượt 1 (Icons) & Lượt 2 (Tập giấy nghiêng có viền mảnh & Căn trục Composer), 2026-10-24

Thực hiện tuần tự từng lát cắt giao diện nhỏ theo hướng giữ trọn cá tính tập giấy trên bàn Chuột (`PaperDesk`):

1. **Lượt 1 (Chuẩn hóa Icons trên `DeskIcon.qml` & `PDFDesk.qml`)**:
   - Đồng bộ lưới SVG `24x24` (`stroke-width="1.85"`), nhân `devicePixelRatio` + `mipmap: true`.
   - Tách riêng `"pdf"` (tô màu `desk.pdfInk` trong `contextChip`), thêm `"paperclip"` (`choosePdf` `16px`), `"send"` (sửa nút `askSelectedPdf`), `"sparkle"`, làm sạch `"folder"` và thay mũi tên Unicode lẻ (`←`, `→`, `›`, `⌄`) sang `DeskIcon`.
2. **Lượt 2 (`Build 2026.10.24.5` — Phương án A: Tập giấy nghiêng có viền & trục Composer)**:
   - Giữ độ nghiêng cá tính của tờ lót dưới `composer` (`-1.1°`), tờ lót dưới `resultPaper` (`-0.9°`) và thẻ `notice` (`-1.2°`); đồng bộ kích thước + `radius` của tờ lót `composer`, thêm `border: 1px desk.edge` và `antialiasing: true`.
   - Căn sát lề trái `uiBuildLabel` (`Build 2026.10.24.5`) thẳng trục với `draftEditor` và `contextChip`, thêm viền `1px desk.edge` cho `contextChip`, nâng `controlRadius: 10`.
   - Kiểm tra: `27/27` tests pass (`test_quick_finder_flow.py`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`, `test_selected_document_read_scope.py`); phiên native `work/rat_ui_iteration_sessions_20261024/19-turn2-paper-framing/` đạt `qml_warnings: []`, `clear_frame: true`, `disk_matches_loaded_source: true`, `calls: []` (`max_model_calls=0`).

## Build .6 — Lượt 2b (F1) + Sửa góc giao `resultPaper × composer` + Lượt 3 (Thẻ gợi ý gọn & Cuộn riêng), 2026-10-24

Thực hiện gộp Lượt 2b (`Hướng F1`), sửa lỗi thị giác ở góc giao `resultPaper × composer × Chuột` do người dùng chỉ ra, và Lượt 3 trên `rat/ui/quick/PDFDesk.qml` + `tests/test_quick_finder_flow.py` (`Build 2026.10.24.6`):

1. **Lượt 2b (`Hướng F1` — Bàn giấy thoáng & kéo thả động)**:
   - Bỏ nhãn tĩnh `"Kéo thả PDF"` ở chân `composer` khi rỗi (cập nhật nhắc vào tooltip nút `choosePdf`); khi `pdfDropArea.containsDrag` mới hiện động `"·  Thả PDF vào bàn Chuột"` kèm viền `1.5px desk.accent`.
2. **Sửa góc giao `resultPaper × composer` bị cấn**:
   - Ẩn tờ giấy lót nghiêng `-1.1°` của `composer` khi `expanded && hasWorkbench` (loại bỏ mảng xám `z: 2` vẽ đè chéo lên mặt trắng `resultPaper` `z: 1` và thò lệch mép phải ở Full mode; vẫn giữ nguyên 100% ở Min mode).
   - Đổi viền `composer` khi `editor.activeFocus` sang `desk.selectedEdge` êm mắt thay vì viền xanh đậm cắt ngang bụng Chuột; ẩn `logToggle` (`Chi tiết & nhật ký`) ở view `finder` và `apps`.
3. **Lượt 3 (Thẻ gợi ý gọn, vùng cuộn `finderListScroll` riêng & thẻ phím màu giấy)**:
   - Xóa cặp `IconButton` ẩn (`opacity: 0`, cao `28px`) bị lặp ở dòng 2 của `hitCard`, thu gọn chiều cao thẻ (`~68px` → `~50px`) và tăng chiều rộng đường dẫn thêm `+64px`.
   - Bọc `finderRepeater` trong `finderListScroll` (`max 206px`) kèm tự cuộn `Qt.callLater` theo `selectedFinderIndex`, giữ cố định tiêu đề `"Gợi ý tìm kiếm (N)"`, nút `"Thu gọn"` và `bottomActionBar` không bị cắt ngang thẻ cuối.
   - Bọc icon `PDF`/`Tệp` trong ô giấy `28×28` (`radius: 7`, `1px desk.edge`) và đóng khung phím tắt trong `KeycapBadge` dạng pill màu giấy mềm.
4. **Kiểm chứng (`max_model_calls=0`)**:
   - `33/33` tests pass (`test_quick_finder_flow.py`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`, `test_selected_document_read_scope.py`, `test_quick_pdf.py`).
   - Phiên native Cocoa kịch bản `finder-suggestions`: `work/rat_ui_iteration_sessions_20261024/20-turn2b-turn3-finder-seam/` (`10` ảnh chụp `clear_frame: true`, `qml_warnings: []`, `disk_matches_loaded_source: true`, `calls: []`, kèm `walkthrough.mp4` và `walkthrough.gif` dựng từ chuỗi ảnh phiên — không gán là quay desktop thao tác tay trực tiếp).

## Build .7 — Lượt 4: Bù 3 Điểm neo Bàn giấy + Đồng bộ Header & Dải mờ chân trang chống cắt chữ, 2026-10-24

Tiếp tục tinh chỉnh hoàn thiện giao diện theo phản hồi thị giác của người dùng (giải quyết triệt để cảm giác "thiếu thiếu" và hiện thực hóa Lượt 4), mã UI `Build 2026.10.24.7`:

1. **Bù 3 điểm neo cảm giác "thiếu thiếu" trên `rat/ui/quick/PDFDesk.qml`**:
   - Tờ giấy lót `composer` luồn xuống `z: 0` (sau lưng `resultPaper` `z: 1`), hạ `y: composer.y + 1` và xoay `-0.8°`: cạnh trên bị che kín sau lưng `resultPaper` nên góc giao sạch tuyệt đối không có nêm xám đè lên, trong khi sườn dưới phải của `composer` có mép tập giấy lấp ló giữ trọn độ dày đầm tay của bàn Chuột như Min mode.
   - Thêm đường chỉ giấy mảnh `1px desk.edge` neo chân hàng phím `bottomActionBar` trong view `finder`, kết hợp đường chỉ `1px` ngăn cách dưới header tạo cấu trúc sổ tay rõ ràng.
   - Bổ sung nhịp trạng thái sống ở chân `composer` cạnh nhãn Build: chấm xanh `· ● Chuột sẵn sàng` khi rỗi; `· ↑↓ chọn · ↵ mở · Esc đóng` khi mở gợi ý; `· Trang N/M · ↵ tìm từ khóa` khi đọc PDF; `· ↵ tìm trong PDF · ⌘↵ hỏi Chuột` khi kẹp tài liệu.
2. **Đồng bộ Header & Chống chém đứt chữ khi đọc PDF / Trả lời (Lượt 4)**:
   - Thu gọn tiêu đề view `answer` về nhịp `11px` (`● Câu trả lời của Chuột`) đồng bộ toàn bộ view; đưa câu hỏi người dùng thành tiêu đề trang `15px Medium` thẳng trục lề trái.
   - Thêm dải mờ giấy `22px` (`Gradient` `transparent` → `desk.paperColor`) ở chân vùng cuộn `resultScroll` khi còn nội dung phía dưới, kết hợp thanh cuộn dọc mảnh `4px` màu sage (`desk.selectedEdge`) và `bottomPadding: 14` trên `pageText` — chữ ở mép đáy mờ êm tự nhiên, không bị chém ngang thân chữ.
   - Bổ sung icon mũi tên `trailingIconName: "arrow-right"` (`12px`) trên nút `"Đọc trang →"` của kết quả tìm kiếm.
3. **Kiểm chứng (`max_model_calls=0`)**:
   - `33/33` tests pass (`test_quick_finder_flow.py`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`, `test_selected_document_read_scope.py`, `test_quick_pdf.py`).
   - Phiên native Cocoa: `work/rat_ui_iteration_sessions_20261024/21-turn4-anchors-header-reading/` ghi nhận đầy đủ captures `clear_frame=true`, `qml_warnings: []`, `disk_matches_loaded_source: true`, `calls: []`, sinh `walkthrough.mp4` và `walkthrough.gif` (không gán là desktop acceptance thao tác tay). Bổ sung ảnh chụp thực tế đọc Trang 15 và tìm kiếm PDF gốc BEST-Route vào artifact log.


## Build .8 — Lượt 1 (Kế hoạch UX-First): Chatbox Hỏi Thẳng Bằng `Enter` & Snapshot Vùng Khớp PDF ("Tìm Đâu Cap Đó"), 2026-10-24

Thực hiện Lượt 1 của lộ trình cải thiện UX trước – UI sau (`Build 2026.10.24.8`):

1. **UX cốt lõi — Trả lại `Enter` cho Hỏi Chuột (Chatbox thuần nhất)**:
   - Hợp nhất xử lý phím `Return`/`Enter` trong `rat/ui/quick/PDFDesk.qml` (`handleComposerReturn` + `submitDraft`): dù có đính kèm PDF hay không, nhấn `Enter` hoặc bấm nút Gửi (`sendButton`, giữ icon `"arrow-up"`) luôn gửi câu hỏi thẳng tới Chuột (`submitQuery`); `Shift+Enter` xuống dòng.
   - Loại bỏ toàn bộ phím tắt/nút phụ gây chồng chéo hoặc nuốt câu hỏi: xóa `⌘↵` (`askSelectedPdf`), xóa nút `"Hỏi về PDF"` trong `documentPopup`, xóa nút tách đôi `⇧↵ Hỏi về PDF` ở `bottomActionBar` của Finder, và sửa `QuickPDFController.askAboutHit` để nhánh lập trình `.pdf` kèm câu hỏi nạp đồng bộ `select_pdf` trước khi `submit(q)`.
   - Tách chức năng tìm chữ offline trong PDF (`liveController.search`) sang nút kính lúp `openPdfSearch` trên `contextChip` + phím tắt `⌘F` / `Ctrl+F` mở thanh `pdfSearchField` / `runPdfSearch` gọn bên trong `documentPopup` (bảo toàn 100% câu hỏi đang gõ dở trong `draftEditor`).

2. **Thay đổi UI nhận diện (`Build 2026.10.24.8`) — Snapshot vùng khớp trên PDF ("Tìm ra ở đâu thì cap ở đó")**:
   - Thêm `rat/ui/pdf_snapshot_provider.py` (`PdfSnapshotRenderer`) sử dụng `PyQt6.QtPdf` (`QPdfDocument` + `QPdfSearchModel`), hoàn toàn độc lập khỏi `rat/engine/book_pages.py`:
     - Khôi phục cụm chữ hoa/dấu tiếng Việt từ `snippet` trước khi dò `QRectF`, gom băng dọc quanh dòng khớp (`106pt–166pt`), tô nền giấy `#fdfdf9` + highlight vàng ấm + thanh dọc sage `4px` **dưới** lớp chữ đen của PDF, xuất `data:image/png;base64,...` có bộ nhớ đệm LRU (`max_docs=4`, `max_snaps=48`).
   - Thêm slot `QuickPDFController.pageSnapshot` (kiểm tra chặt `resolved == self._selection.path` và `1 <= page <= page_count`) và truyền `path` + `snippet` an toàn cho tham chiếu PDF trong `rat/ui/answer_presentation.py`.
   - Hiển thị thẻ `PdfSnapshotCard` bấm-để-mở-trang trong kết quả tìm kiếm PDF (`searchSnapshot_<page>`) và dưới tham chiếu trang của câu trả lời (`sourceSnapshot_<index>`).

3. **Kiểm chứng & Giới hạn trung thực (`max_model_calls=0`)**:
   - Bộ test: `48/48` tests pass (`test_quick_pdf.py` gồm test mới `test_pure_chatbox_enter_asks_pdf_and_renders_citation_snapshot`, `test_quick_finder_flow.py`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`, `test_selected_document_read_scope.py`, `test_selected_pdf.py`), không có cảnh báo QML hay QtPdf.
   - Phiên chụp native Cocoa (`QT_QUICK_BACKEND=software`): `work/rat_ui_iteration_sessions_20261024/24-turn1-chatbox-pdf-snapshot/` trên PDF gốc `arxiv_2506.22716_original.pdf` (`https://arxiv.org/pdf/2506.22716`, SHA-256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`), ghi nhận `14` captures `clear_frame: true`, `qml_warnings: []`, `Ctrl+R` reload `preserved: true`, kèm `walkthrough.mp4` và `walkthrough.gif` dựng từ chuỗi ảnh cửa sổ phiên (không gán là thao tác chuột/phím phần cứng trực tiếp hay nghiệm thu hội thoại model live; các thư mục chạy nháp `22-*`, `23-*` được giữ nguyên nguyên trạng).

## Build .9 — Lượt 2 (Kế hoạch UX-First): Chặn Finder Cướp Màn Hình + Làm Mới Toàn Diện Tờ `Answer` & Ngăn Kéo Gợi Ý, 2026-10-24

Thực hiện Lượt 2 theo gói UI người dùng chọn (`Build 2026.10.24.9`):

1. **UX cốt lõi — Chặn Finder tự nhảy ra cướp màn hình (`rat/ui/quick_pdf_controller.py`)**:
   - Trong `_handle_finder_snapshot`: khi `hits == []` (`0` tệp/app khớp), không bật `_view = "finder"` và không tự bung cửa sổ Full; nếu đang ở Finder mà gõ tiếp không còn khớp thì tự động trả về trạng thái trước đó (`answer` hoặc `none`).
   - Khi đang mở đọc `view == "answer"` hoặc gõ câu hỏi hội thoại (`_is_conversational_query == True`), giữ nguyên màn hình hiện tại và lưu ngầm `finderHits`; thêm slot `openFinderSuggestions()` để mở chủ động từ thẻ ngăn kéo và khôi phục đúng `answer` + `expanded` khi bấm `← Câu trả lời` / `Esc`.

2. **Nâng cấp UI tờ `Answer` & Ngăn kéo Gợi ý (`Build 2026.10.24.9`)**:
   - `rat/ui/answer_presentation.py` (`answer_html`): hỗ trợ vẽ bảng Markdown (`|...|`) kẻ khung sắc nét, khung Code Card full-width có nhãn ngôn ngữ (`PYTHON`, ...), hộp Blockquote (`> ...`) có vạch nhấn, chữ nghiêng `*...*` và đường phân cách `---` tương thích `QQuickTextNode`, bảo toàn tuyệt đối ràng buộc không sinh thẻ tải tài nguyên ngoài (`<img>`, `<a>`, `<script>`, `<iframe>`, `<object>`).
   - `rat/ui/quick/PDFDesk.qml`: nâng `uiBuildLabel` lên `"Build 2026.10.24.9"`, đóng khung câu hỏi người dùng trong thẻ giấy `answerQuestionCard` (`BẠN HỎI` + thanh dọc sage `3.5px` + chevron mở rộng), thêm dải `CHUỘT TRẢ LỜI` kèm huy hiệu kiểm tra, nút `← Câu trả lời` động trên Finder, và thẻ ngăn kéo `finderDrawerTab` (`N tệp/app khớp · Xem ▴`) nhô nhẹ ở mép trên bên phải `composer`.

3. **Kiểm chứng & Giới hạn trung thực**:
   - Bộ test: `64/64` tests pass across full 8 test suites (`test_quick_pdf.py`, `test_quick_finder_flow.py` gồm `test_dismiss_finder_restores_cancelled_or_empty_answer_state` và `test_finder_never_hijacks_active_answer_or_zero_hit_chat_and_exposes_drawer_tab`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`, `test_selected_document_read_scope.py`, `test_selected_pdf.py`, và toàn bộ 14 tests `test_quick_answer_presentation.py` sau khi đồng bộ `complete_fixture(..., expanded=True)`), `qml_warnings: []`, không segfault.
   - Xử lý phản hồi review Codex (`docs/rat_ui_build9_review_20261024.md`): Sửa triệt để P2 bằng hàm `_restore_pre_finder_state()`, lưu giữ `_pre_finder_status` và khôi phục nguyên trạng view `answer` (kể cả khi câu trả lời rỗng do huỷ bỏ/thất bại) cùng thông báo trạng thái thay vì ép về `none` / "Chuột sẵn sàng".
   - Phiên native Cocoa (`QT_QUICK_BACKEND=software`, `--system-apps`, `max_model_calls=0`): `work/rat_ui_iteration_sessions_20261024/27-turn2-finder-answer/` ghi nhận đầy đủ bước chat 0-hit giữ nguyên cửa sổ gấp gọn (`277px`), thẻ ngăn kéo `5 tệp/app khớp · Xem ▴`, mở Finder chủ động và `Ctrl+R` reload `preserved: true`, kèm `walkthrough.mp4` và `walkthrough.gif`. Daemon Ollama local (`127.0.0.1:11434`) đang tắt tại thời điểm chạy (`Connection refused`) nên không bơm câu trả lời giả vào phiên live; ảnh chụp tờ `Answer` (Light & Dark) được xuất riêng từ bài kiểm thử định dạng QML và ghi nhãn rõ ràng.

## Build .10 — Lượt 3: Đại tu Seamless PDF Reader (Đọc PDF Liền Mạch), 2026-10-24

Thực hiện Lượt 3 theo quyết định của người dùng: Đại tu toàn diện giao diện đọc PDF thành trải nghiệm đọc liền mạch (`Seamless PDF Reader`) trong tờ `resultPaper` của RAT Quick Desk (`Build 2026.10.24.10`):

1. **Luồng đọc PDF liền mạch trong `resultPaper` & Bỏ `documentPopup`**:
   - Loại bỏ hoàn toàn `documentPopup` dạng cửa sổ phụ che chắn bàn làm việc.
   - Thêm phương thức `openPdfDocument(path)` trong `rat/ui/quick_pdf_controller.py`: khi chọn file/kéo-thả PDF, tự động mở Trang 1 trên `resultPaper` (`auto_read_on_select = True`), đồng thời giữ nguyên bản nháp trong `draftEditor` của `composer`.
   - Bấm vào chip tài liệu (`contextChip` / `documentMenu`) mở lại đúng trang PDF đang đọc hiện tại (`showCurrentPdfPage()`), chỉ reset về Trang 1 khi chọn tài liệu mới.
   - Hiển thị trạng thái loading/error trung thực, bảo đảm không hiển thị nội dung của file trước đó khi chuyển tài liệu.

2. **Thanh điều hướng đọc (Reader Header) co giãn an toàn ở 520px**:
   - Header tích hợp nút lùi/tiến trang với kiểm tra biên an toàn (`‹ [pagePicker] / [total] ›`), ô nhập số trang nhảy nhanh, nút tìm chữ (`openPdfSearchInPage`), nút mở PDF gốc (`openOriginal`), nút sao chép trích dẫn (`copyCitation`), và nút thu workbench (`liveFoldButton`).
   - Căn chỉnh layout phản hồi linh hoạt: khi cửa sổ co về 520px (`resultPaper.width <= 370px`), tên tài liệu tự động co giãn (`elide: Text.ElideMiddle`), các nút điều khiển không bị đẩy tràn ra ngoài khung cửa sổ.
   - Thêm spacer giãn cách co giãn (`Item { Layout.fillWidth: true }`) đảm bảo các nút hành động bên phải luôn bám sát lề phải bàn giấy.

3. **Hai chế độ đọc song song (Trang gốc & Văn bản)**:
   - Thêm thanh chuyển đổi chế độ đọc `readerModeToggle` dạng segmented pill (`[ Trang gốc | Văn bản ]`) ngay đầu trang tài liệu.
   - **Trang gốc (`visual`):** Render hình ảnh toàn trang bằng `PyQt6.QtPdf` qua `PdfSnapshotRenderer.render_full_page_data_url()`, bộ nhớ đệm LRU giới hạn tối đa 8 trang (`_full_page_snaps`), tuyệt đối không nạp trước toàn bộ tài liệu.
   - **Văn bản (`text`):** Hiển thị văn bản trích xuất trực tiếp trong `pageText` cho phép bôi chọn đoạn trích và bấm `Chép trích dẫn`.

4. **Tìm kiếm từ khóa nội tuyến (`inlineFindBar`)**:
   - Nhấn `⌘F` / `Ctrl+F` hoặc bấm icon kính lúp hiển thị thanh tìm kiếm nội tuyến ngay trên mặt bàn làm việc mà không bật popup và không can thiệp vào `draftEditor`.
   - Phím `Enter` trong thanh tìm kiếm chỉ kích hoạt tìm chữ trong PDF; phím `Enter` trong `composer` vẫn hỏi Chuột.
   - Phím `Escape` đóng thanh tìm kiếm trước mà không làm gấp gọn bàn làm việc.
   - Giữ nguyên các thẻ snapshot vùng khớp đã hoàn thiện ở Build .8.

5. **Bảo toàn ngữ cảnh & Điều hướng đa tầng**:
   - Mở trang từ danh sách tham chiếu câu trả lời (`openAnswerSource` / `jumpToPdfPage`) ghi nhận cờ `canBackToAnswer`, hiển thị nút `← Câu trả lời` (`backToAnswer`) để quay lại câu trả lời vừa xem chỉ bằng 1 cú click (0 model call).
   - Chuyển đổi qua lại giữa Min mode và Full mode bảo toàn nguyên vẹn file đang mở, trang đang đọc, bản nháp câu hỏi và vị trí con trỏ.
   - Đồng bộ toàn diện bộ kiểm thử `tests/test_quick_answer_presentation.py` với luồng không popup.

6. **Kiểm chứng & Giới hạn trung thực (`max_model_calls=0`)**:
   - Bộ test: `65/65` tests pass trên toàn bộ 8 file quick test suites (`test_quick_pdf.py` với 8 tests gồm `test_build10_seamless_reader_and_navigation_suite`, `test_quick_finder_flow.py`, `test_quick_ui_session_observer.py`, `test_pdf_reading_presentation.py`, `test_selected_document_context.py`, `test_selected_document_read_scope.py`, `test_selected_pdf.py`, `test_quick_answer_presentation.py`).
   - Phiên native Cocoa (`work/rat_ui_iteration_sessions_20261024/29-turn3-seamless-reader/`): Nạp PDF gốc BEST-Route (`arxiv_2506.22716_original.pdf`, SHA-256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`), ghi nhận 14 ảnh chụp native `clear_frame: true`, `qml_warnings: []`, `reload: 2, preserved: true`, ngân sách model `calls: []` (0 request).
   - Xuất video walkthrough: `walkthrough.mp4` và `walkthrough.gif` dựng từ chuỗi khung hình PNG phiên chạy Cocoa Native qua `ffmpeg` (minh bạch phân biệt với video quay desktop thao tác người dùng live).

## Build .11 — Thu gọn Metadata Nguồn & Tối ưu Bố cục Trình bày Chứng cứ (Evidence Presentation), 2026-10-24

Triển khai lượt tinh chỉnh UI/UX nhỏ theo thiết kế `docs/rat_information_evidence_design_20261024.md` và phản hồi review visual (`Build 2026.10.24.11`), định vị đúng đây là nguồn thông tin đối chiếu (tránh hiểu lầm là trình đọc PDF độc lập):

1. **Gộp tiêu đề nguồn thành một dòng rõ ràng (`pageSourceTitle`)**:
   - Tiêu đề nguồn hiển thị dạng `Nguồn · Trang N/M` (`font.pixelSize: 13, font.weight: Font.DemiBold, desk.ink`) phản ánh chính xác số trang và tổng số trang thực tế.
2. **Dòng phụ tên tệp thu gọn (`pageMetadataLabel`)**:
   - Tên tệp chuyển xuống dòng phụ nhỏ hơn (`11px, desk.muted`), tự động co ngắn bằng `Text.ElideMiddle` khi tên dài, hỗ trợ rê chuột (`ToolTip`) xem tên tệp đầy đủ mà không xô lệch bố cục nút chuyển chế độ đọc `[Trang gốc | Văn bản]`.
3. **Loại bỏ nhãn số trang trùng lặp**:
   - Dọn sạch số trang bị lặp lại ở footer của composer (`composerDropStatus`): chuyển thành `↵ hỏi Chuột · ⌘F tìm chữ trong PDF` đồng nhất.
   - Cụm điều hướng trang (`liveHeader`) giữ trọn vẹn số trang và ô nhảy trang `pagePicker` để thao tác nhanh.
4. **Tối ưu khoảng cách hiển thị nội dung nguồn**:
   - Giảm khoảng cách đỉnh `resultScroll.y` từ `50px` xuống `46px` và `spacing` trong `resultContents` từ `10px` xuống `6px`, giải phóng không gian theo chiều dọc giúp nội dung trang nguồn hiển thị rộng rãi, không bị che khuất bởi composer.
5. **Kiểm chứng trung thực (`max_model_calls=0`)**:
   - Không gán câu trả lời mẫu (`_last_assistant_answer`) hay kết quả trích dẫn giả định.
   - Nạp PDF thật có kiểm tra hash provenance: `work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf` (SHA-256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`).
   - Tìm kiếm từ khóa thật (`"routing"`) qua UI và mở trang 1.
   - Chụp toàn bộ cửa sổ Trước và Sau tại `520px` và `700px` với `QT_QUICK_BACKEND=software` (tránh lỗi cache Metal trên macOS sandbox làm ảnh trong suốt), kiểm tra dữ liệu pixel không rỗng (`nonzero_rgb > 2,300,000`).
   - Bộ test: `69/69` quick UI tests pass, `29/29` research study tests pass. Bản nháp composer và trạng thái min/full được bảo toàn tuyệt đối.

## Build .13 — Ưu tiên Trích đoạn Khớp & Hợp nhất Luồng Nguồn (Single Unified Source Flow), 2026-10-24

Hoàn thiện theo định hướng thiết kế chứng cứ thông tin (`docs/rat_information_evidence_design_20261024.md`) và giải quyết phản hồi review Build .11 & .12: Thống nhất một luồng nguồn duy nhất khi mở kết quả tìm kiếm, bỏ bộ chọn chế độ đọc để người dùng đọc ngay đoạn chứng cứ (`Build 2026.10.24.13`):

1. **Bỏ switcher `[ Đoạn khớp | Trang gốc ]` — Hợp nhất một luồng nguồn duy nhất**:
   - Loại bỏ hoàn toàn thanh switcher `readerModeToggle` và logic chuyển mode ngầm không cần thiết trong luồng mở kết quả tìm kiếm.
   - Mở kết quả tìm kiếm lập tức hiển thị trích đoạn khớp thực tế, highlight từ khóa nổi bật, tên tệp và số trang nguồn.
   - Nếu trang không có đoạn trích khớp (ví dụ duyệt sang trang khác), hiển thị thông báo nhẹ `"Chưa có đoạn trích cho trang này."` cùng nút `"Mở PDF gốc"`, không tự chuyển đổi ngầm thành embedded reader.
   - Đặt hành động phụ `"Mở PDF gốc"` (`openOriginalExternal`) ở góc phải thanh tiêu đề nguồn để mở file bằng ứng dụng ngoài của hệ thống; không nhúng thêm chế độ đọc visual cồng kềnh trong RAT.

2. **Xác nhận sao chép trung thực qua Clipboard OS**:
   - Bổ sung tín hiệu `copyConfirmed = pyqtSignal(str)` và hàm xác thực `_set_and_verify_clipboard()`.
   - Cơ chế: Ghi chuỗi trích dẫn vào `QGuiApplication.clipboard().setText()`, sau đó lập tức đọc lại `cb.text()` để đối chiếu nội dung thực tế. Nhãn `"Đã chép"` trên giao diện chỉ xuất hiện khi và chỉ khi clipboard OS đã được ghi và xác thực khớp 100%.
   - Kiểm thử tự động assert trực tiếp trên `app.clipboard().text()`, không chỉ bắt signal vào danh sách.

3. **Chỉ sao chép vùng chọn đang hiển thị — Không đọc component đang ẩn**:
   - `requestCopy()` được giới hạn nghiêm ngặt: chỉ đọc `selectedText` từ component đang thực sự hiển thị (`matchedExcerptText.selectedText` khi xem trang nguồn; `answerText.selectedText` khi xem câu trả lời).
   - Nếu người dùng không bôi chọn cục bộ, tự động sao chép toàn bộ trích đoạn khớp kèm chú thích nguồn: `— {filename}, trang PDF {page}\n{path}`.
   - Tuyệt đối không đọc vùng chọn từ các component đang ẩn (`pageText`).
   - Tự động xóa vùng chọn khi đổi trang hoặc đổi view để tránh rò rỉ selection cũ.

4. **Tối ưu hiển thị cho chiều rộng 520px**:
   - Dòng tiêu đề `"Đoạn khớp với từ khóa…"` được thiết lập `wrapMode: Text.Wrap` và `Layout.fillWidth: true`, hiển thị trọn vẹn từ khóa tìm kiếm mà không bị cắt xén ở chiều rộng 520px.
   - Nhãn `"Trích đoạn (…)"` được đưa xuống dòng phụ lùi lề (`Layout.leftMargin: 12`) để không tranh chấp chiều rộng với tiêu đề từ khóa.
   - Thêm khoảng đệm thở ở cuối `resultContents` (`implicitHeight: 32`), đảm bảo thanh cuộn `resultScroll` có thể cuộn nội dung trích đoạn lên trên hoàn toàn, không bị composer ở đáy cửa sổ che khuất.

5. **Bảo toàn ngữ cảnh & Giữ trọn vẹn bản nháp**:
   - Mở kết quả, sao chép trích đoạn, bấm `"Mở PDF gốc"`, thu/mở min/full, hoặc bấm `"Kết quả"` (`backToSearch`) để quay lại danh sách đều bảo toàn 100% câu hỏi đang soạn dở trong composer, từ khóa tìm kiếm và trang nguồn.

6. **Kiểm chứng trung thực (`max_model_calls=0`)**:
   - Fixture PDF thật có hash đối chiếu: `work/rat_reading_live_20261024/arxiv_2506.22716_original.pdf` (SHA-256 `9746346dc6e6552ccdd20158a0eb4b01e927a3cb46242ebaf3d36a9d3b611d9c`).
   - Thao tác desktop thật qua script tích hợp `scripts/verify_turn4_matched_excerpt.py`: tìm từ khóa `"routing"`, mở kết quả Trang 10, kiểm tra hiển thị trích đoạn + highlight, kiểm tra clipboard thật `app.clipboard().text()`, kiểm tra sao chép đoạn chọn cục bộ vs cả đoạn, kiểm tra fallback trang 25, kiểm tra mở file ngoài không làm mất draft.
   - Chụp cửa sổ tại kích thước chuẩn 520px và 700px với `QT_QUICK_BACKEND=software`:
     - `work/turn4_evidence/turn4_matched_excerpt_520px.png` (tỷ lệ pixel màu 69.65%)
     - `work/turn4_evidence/turn4_matched_excerpt_700px.png` (tỷ lệ pixel màu 71.31%)
   - Kết quả test độc lập từng bộ:
     - `tests/test_quick_pdf.py`: 11/11 passed
     - `tests/test_quick_unified_flow.py`: 13/13 passed
     - `tests/test_quick_finder_flow.py`: 13/13 passed
     - `tests/test_quick_answer_presentation.py`: 16/16 passed
     - Research study gates (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`): 29/29 passed.
   - Ghi nhận hiện tượng kỹ thuật: Khi chạy ghép nhiều file test Qt trong một tiến trình pytest đơn lẻ trên macOS, việc xung đột luồng nền (search index / render pipe) có thể gây segfault/bus error. Chạy độc lập từng bộ test hoạt động ổn định và pass 100%. Không thực hiện git commit hay git push.

## Build .14 — Dọn Header Luồng Nguồn Trích đoạn Khớp & Hoàn thiện UX Một Mode, 2026-10-24

Dọn dẹp header của luồng nguồn mở từ kết quả tìm kiếm để hoàn thiện UX một mode thống nhất (`Build 2026.10.24.14`):

1. **Header tối giản**:
   - Header chỉ giữ 3 thành phần: `"Quay lại kết quả"` (`backToSearch`), `"Chép đoạn"` (`copyCitation`), và nút `"-"` (`liveFoldButton`, `"Thu gọn"`).
   - Ẩn hoàn toàn cụm điều hướng trang `pageNavCluster`: không còn prev/next, ô nhập số trang `pagePicker`, hay nút nhảy trang `readPage` trong luồng này.
   - Số trang chỉ là thông tin hiển thị tại `"Nguồn · Trang N"`.
   - Bỏ icon mở tệp bị trùng trên header (`openOriginal`); chỉ giữ duy nhất một nút `"Mở PDF gốc"` (`openOriginalExternal`) đặt cạnh tiêu đề nguồn và tên tệp trong `resultContents`.
   - Không thêm điều hướng hoặc tính năng mới. Bảo toàn draft, từ khóa và hành vi quay lại danh sách kết quả.

2. **Nghiệm thu thao tác desktop thật (`scripts/verify_turn4_matched_excerpt.py`)**:
   - Tìm kiếm từ khóa `"routing"` trên tệp PDF thật `arxiv_2506.22716_original.pdf`.
   - Mở đoạn trích trang 10 -> Header chỉ có 3 nút: Quay lại kết quả, Chép đoạn, Thu gọn.
   - Sao chép toàn bộ đoạn & bôi chọn cục bộ -> Xác nhận clipboard OS thật (`app.clipboard().text()`).
   - Bấm `"Quay lại kết quả"` -> Trở về danh sách tìm kiếm, bản nháp giữ nguyên vẹn.
   - Báo cáo rõ giới hạn: `_open_url` được mock trong script để kiểm tra QUrl gửi đi, chứng minh đường dẫn file URL cục bộ chính xác đã được chuyển đến opener (`QDesktopServices.openUrl`), nhưng chưa chứng minh ứng dụng ngoài thực sự được kích hoạt trên desktop và không mở đúng trang vì chỉ truyền file URL.
   - Chụp ảnh 520px và 700px tại `work/turn4_evidence/turn4_matched_excerpt_520px.png` và `turn4_matched_excerpt_700px.png`.
   - Toàn bộ 82/82 tests pass (11 test_quick_pdf + 13 test_quick_unified_flow + 13 test_quick_finder_flow + 16 test_quick_answer_presentation + 29 research study). 0 model calls. Không thực hiện git commit hoặc git push.

## Build .15 — Chốt Khả năng Đọc Đoạn Dài ở 520px & Tinh chỉnh Thanh Cuộn, 2026-10-24

Chốt khả năng đọc và cuộn văn bản dài tại bề rộng production 520px, hoàn thiện thanh cuộn (`Build 2026.10.24.15`):

1. **Cuộn desktop thật và xác nhận không bị che khuất**:
   - Sử dụng thao tác kéo chuột thực tế (`QTest.mousePress`, `QTest.mouseMove`, `QTest.mouseRelease`) trên con trượt (thumb) thanh cuộn để cuộn từ `contentY = 0.0` đến `193.0`.
   - Vùng cuộn `resultScroll` kết thúc tại `y = 410.0`, cách đỉnh `composer` (`y = 422.0`) một khoảng đệm an toàn `12.0px`.
   - Bôi chọn và sao chép dòng cuối `"Model Cascade"` thành công, clipboard OS xác thực đúng dữ liệu.

2. **Tinh chỉnh thanh cuộn (Minor UI)**:
   - Nâng độ rộng thanh cuộn dọc `resultVerticalScroll` lên `6px`, bo tròn `radius: 3`, màu tương phản nhận diện tốt trên nền giấy (`#809277` light mode / `#6a7761` dark mode, `#4a5940` khi hover).
   - Thêm track nền mờ khi tương tác; ẩn hoàn toàn (`policy: ScrollBar.AlwaysOff`) khi nội dung không tràn khung (trang 25 fallback).

3. **Kiểm thử và bàn giao ảnh**:
   - Chụp 520px đầu đoạn (`turn4_matched_excerpt_520px_top.png`), cuối đoạn (`turn4_matched_excerpt_520px_bottom.png`) và 700px (`turn4_matched_excerpt_700px.png`).
   - Kiểm tra quay lại danh sách (`backToSearch`) -> mở lại đoạn -> thu/mở min/full bảo toàn 100% bản nháp.
   - Toàn bộ 82/82 test pass, 0 model request, không thực hiện git commit/push.

## Build .16 — UX Hỏi Tiếp trong Composer & Bảo Toàn Đoạn Nguồn Khi Focus, 2026-10-24

Hoàn thiện UX hỏi tiếp trong composer khi người dùng đang đọc tài liệu (`Build 2026.10.24.16`):

1. **Bảo toàn đoạn nguồn khi composer nhận focus**:
   - Khi focus vào ô soạn thảo (`draftEditor`), view trích đoạn nguồn (`view == "page"`) giữ nguyên trạng thái hiển thị, không tự ý đóng nguồn hay mở Finder/Spotlight.
   - Sửa đổi kiểm tra trong `PDFDesk.qml` để `onComposerTextChanged` không kích hoạt tìm kiếm file tài liệu nếu đã có tài liệu được chọn (`_selection is not None`).

2. **Placeholder ngữ cảnh hỏi tiếp linh hoạt**:
   - Khi draft trống và tài liệu đang được chọn (`desk.liveSnapshot.fileName` tồn tại), `placeholderText` hiển thị `"Hỏi tiếp về tài liệu này…"`.
   - Placeholder là văn bản gợi ý thuần túy, tuyệt đối không tự chèn vào draft và không tự động gửi câu hỏi.

3. **Chip ngữ cảnh hiển thị tên tệp sạch**:
   - Nút chip tài liệu `documentButton` chỉ hiển thị `desk.liveSnapshot.activeContext.title` (tên tệp), loại bỏ nhãn số trang khỏi chip để người dùng hiểu rõ câu hỏi áp dụng cho toàn bộ tài liệu chứ không bị giới hạn trong trang đơn lẻ.

4. **Bảo toàn bản nháp 100% qua mọi điều hướng**:
   - Bản nháp được bảo toàn qua các luồng: `backToSearch` -> mở lại search hit -> thu nhỏ min mode -> mở rộng full mode.

5. **Kiểm thử tích hợp & Báo cáo giới hạn minh bạch**:
   - Kịch bản `scripts/verify_turn4_matched_excerpt.py` kiểm tra focus bằng mouse click thật trên QML item, kiểm tra các primitive `paste()`, `undo()`, `redo()`, cuộn chuột desktop ở 520px và bảo toàn draft.
   - Sửa rõ bản chất của `setProperty`: `setProperty` chỉ kiểm tra data binding và tính năng lưu giữ bản nháp (draft retention contract) qua các trạng thái điều hướng, KHÔNG PHẢI là thao tác gõ phím bằng bộ gõ hay dán bằng Cmd+V.
   - Phân định rõ ràng: Nghiệm thu gõ tiếng Việt bằng bộ gõ hệ điều hành (macOS IME) và dán/undo/redo bằng phím tắt vật lý OS (Cmd+V, Cmd+Z, Cmd+Shift+Z) được ghi nhận là CHƯA XÁC NHẬN trong môi trường tự động (cần người dùng tương tác trực tiếp trên desktop).
   - 0 request model tiêu tốn (không gửi câu hỏi).
   - 82/82 software test độc lập pass 100% (11 quick_pdf + 13 quick_unified + 13 quick_finder + 16 answer_presentation + 29 research study).
   - 0 request model, không can thiệp backend/routing, không sửa research, không git commit/push.

## Build .17 — Hiển Thị Tên Nguồn Cạnh Câu Trả Lời & Chuẩn Bị Luồng Hội Thoại PDF Thật, 2026-10-25

Triển khai minor UI đặt tên tài liệu nguồn ngay cạnh câu trả lời để người dùng biết RAT vừa dựa vào tài liệu nào (`Build 2026.10.25.17`):

1. **Tên tài liệu nguồn cạnh câu trả lời (`answerDocumentLabel`)**:
   - Đặt nhãn tên tệp nguồn thực tế (từ `answerSources[0].title` hoặc `fileName`) ngay sau `"CHUỘT TRẢ LỜI"` trên thanh tiêu đề câu trả lời trong `PDFDesk.qml`.
   - Có dấu phân cách `·`, màu `desk.accent`, font cỡ 11, hiển thị tooltip với tên đầy đủ khi hover qua `HoverHandler`.
   - Rõ ràng, dễ nhận biết giúp người dùng đối chiếu ngay tài liệu làm căn cứ trả lời.

2. **Kiểm thử phần mềm độc lập**:
   - Bổ sung ca kiểm thử trong `tests/test_quick_answer_presentation.py` xác thực `answerDocumentLabel` hiển thị đúng `"Source.pdf"`.
   - Cập nhật nhãn build cho phép `"Build 2026.10.25.17"` trong `tests/test_quick_finder_flow.py`.
   - Toàn bộ 82/82 software test độc lập pass 100%.

3. **Bảo toàn trạng thái ngân sách 0 request model**:
   - Chưa gửi request model thật nào trong lượt này; giữ nguyên 0 request cho đến khi người dùng cấp ngân sách cụ thể cho ca hội thoại trực tiếp.

## Build .19 — Mở Rộng Ngữ Cảnh Nguồn & Tinh Gọn Giao Diện Bàn Giấy (Decluttering), 2026-10-25

Triển khai tính năng "Mở rộng ngữ cảnh" theo Mục 6 của hợp đồng thiết kế `docs/rat_information_evidence_design_20261024.md` và giải quyết triệt để phản hồi thị giác giao diện bị rối/chồng chéo ("box-in-box") (`Build 2026.10.25.19`):

1. **Tính năng Mở rộng ngữ cảnh (`expandContextButton`)**:
   - Backend & Controller: `rat/engine/selected_document_qa.py` bổ sung trường `full_excerpt` trong kết quả trích đoạn; `rat/ui/answer_presentation.py` cung cấp `extendedSnippet` (lên tới 1800 ký tự) và cờ `hasMoreContext`; `QuickPDFController.getExpandedContext()` cho phép QML truy xuất ngữ cảnh đầy đủ quanh vị trí tìm thấy.
   - QML UI: Nút `expandContextButton` hiển thị `+ Ngữ cảnh` (khi đang thu gọn) hoặc `Thu gọn` (khi đang mở rộng). Nhấp nút toggle mượt mà giữa đoạn trích cô đọng (181 ký tự) và đoạn mở rộng (610 ký tự), đồng thời hiển thị tag nhận diện `"Ngữ cảnh mở rộng"`.
   - Nút `copyCitationButton` (Chép trích dẫn) tự động sao chép văn bản mở rộng kèm trích dẫn nguồn khi đang ở trạng thái mở rộng.

2. **Tinh giản & Tái cấu trúc Giao diện (Decluttering & Typography)**:
   - Khắc phục triệt để hội chứng "hộp lồng trong hộp" (box-in-box): Loại bỏ khung viền phụ bên trong `evidenceSnippetBox`, sáp nhập thành một thẻ tiện ích liền mạch duy nhất `evidenceSourceCard`.
   - Bổ sung đường dẫn chỉ thị màu sage (`desk.accent`, rộng 3px) dọc cạnh trái trích đoạn, tạo điểm nhấn cấu trúc báo chí chuyên nghiệp.
   - Tối ưu hóa khoảng cách (spacing), padding (8px), bo góc (8px), và điều chỉnh giãn dòng `lineHeight: 1.3` cho toàn bộ văn bản nguồn.
   - Sửa lỗi đè lớp tương tác: Đặt `ScrollBar.horizontal.policy: ScrollBar.AlwaysOff` và vô hiệu hóa tương tác chuột trên gradient bóng mờ đáy trang (`enabled: false`), loại bỏ hoàn toàn hiện tượng click target bị nuốt.

3. **Kiểm chứng & Xuất bằng chứng**:
   - Xuất thêm ảnh nghiệm thu `turn5_evidence_sheet_context_expanded.png` (520x670) với tỉ lệ pixel không trong suốt 100.00%.
   - Cập nhật test suite: 16 test trong `tests/test_quick_answer_presentation.py` kiểm tra trọn vẹn chu kỳ click `expandContextButton` -> mở rộng -> chép -> thu gọn.
   - 82/82 software test độc lập pass 100% (53 quick desktop tests + 29 research study tests).
   - 0 request model / 0 token trong toàn bộ đợt kiểm thử và xuất ảnh.
   - Không commit/push git.



## Build .20 — Finder theo công dụng, 2026-10-25

Tiếp tục RAT-FIND-01 theo bàn giao; PDF vẫn done for now. Minor UI: nhãn
“Khớp công dụng” / “Khớp tên ứng dụng” / “Khớp chỉ mục tài liệu” trên dòng
gợi ý, cạnh đường dẫn; giữ tooltip đường dẫn đầy đủ.

- Functional lookup theo bundle ID đã cài: tính toán/máy tính, trình duyệt/lướt
  web, gõ/viết code, soạn thảo, ghi chú. Không tạo đường dẫn app giả; nhiều
  app phù hợp vẫn giữ các lựa chọn. Mapping áp dụng cả catalog cache cũ.
- Chuẩn hóa tiền tố tìm file kể cả khi không chỉ rõ định dạng/thời gian, ví dụ
  “tìm file quy chế tín chỉ”; giữ từ khóa chủ đề và không mở rộng crawl.
  “tìm file” trống không liệt kê tùy tiện toàn bộ kho.
- Giữ kiến trúc lexical/semantic độc lập và latest-query cancellation hiện có.
  Không thêm LLM, embedding, OCR hay scan catalog vào đường gõ phím.
- Không đổi shortcut hiện có (PDF Enter chọn tài liệu, Shift+Enter hỏi tệp,
  Cmd+Enter hiện trong Finder); Tab vẫn phục vụ điều hướng focus. Không tuyên
  bố toàn bộ plan cũ đã triển khai/nghiệm thu.

Bằng chứng local: `artifacts/finder_build20_20261025/report.json`, ảnh compact,
full 520/700, dismissed và logs. Script tái lập: `scripts/verify_finder_build20.py`.
Backend thật: 170 app đã cài, chỉ mục SQLite hiện có 602,628,096 byte (read-only).
Không fixture kết quả UI, không PDF mới, không request model, không launch app.

Số đo cuối (mỗi query 1 lượt đầu + 30 lượt warm, không phải nghiên cứu model):

| Truy vấn | Lượt đầu ms | Warm median ms | Warm p95 ms |
| --- | ---: | ---: | ---: |
| mở cái app tính toán | 3.91 | 1.72 | 2.17 |
| mở trình duyệt | 2.30 | 2.17 | 2.23 |
| mở app gõ code | 2.13 | 2.07 | 2.10 |
| tìm file quy chế tín chỉ | 89.51 | 21.86 | 27.38 |
| slide mạng máy tính | 24.19 | 8.92 | 10.33 |
| tìm file | 0.30 | 0.16 | 0.22 |

Scan catalog không cache: 237.79 ms, ngoài đường gõ phím.
10 lượt gõ ASCII tương đương “mo cai app tinh toan” bằng native QTest key events:
input-to-QML median 21.43 ms, p95 58.01 ms.
Số này gồm thời gian phát chuỗi phím và event delivery, chưa đo compositor/frame
presentation, IME tiếng Việt, cold OS cache hoặc latency model. Đã click drawer
thật, xác nhận label visible, chụp cửa sổ Qt thật ở 520/700, Down/Esc giữ draft.
Chưa nghiệm thu mở app qua OS hoặc hội thoại model trong lượt này.

Kiểm tra: 20 backend/catalog + 13 quick_finder + 11 quick_pdf + 16
answer_presentation + 13 quick_unified = 73 passed, chạy riêng từng bộ Qt.
Lượt gộp Qt trước đó bus error trong answer_presentation; giữ giới hạn này,
không diễn giải việc rerun riêng pass là đã sửa nguyên nhân bus error. Sandbox
ban đầu làm Qt abort do phát hiện CPU neon; chạy ngoài sandbox import được.
Smoke lần đầu dùng native style không phù hợp; lần sau shortcut Meta+A của
QTest không chọn hết nên nối hai câu. Đã sửa script dùng Basic và Qt
ControlModifier (ánh xạ Command trên macOS); giữ log thất bại
`live_run.log` cùng các log retry. Đây là lỗi hạ tầng smoke, không phải hội thoại
model thất bại. Ảnh cuối đã xem trực tiếp, có nhãn công dụng và đường dẫn thật.
Không commit/push. Các thay đổi và artifacts có trước được giữ nguyên.


## Build .21 — Mở app thật và xác nhận tại composer, 2026-10-25

User đồng ý bước tiếp theo: tìm trình duyệt → ↑↓ chọn → Enter mở qua OS,
giữ draft, báo lỗi rõ, có minor UI nhận diện Build .21.

- Thêm `applicationLaunchFeedback` dưới composer, wrap text ở cửa sổ hẹp.
  Thành công ghi “Đã gửi yêu cầu mở <tên>.”, không suy ra app đã tải xong.
  Lỗi gửi yêu cầu hoặc app bị gỡ/bundle không hợp lệ hiển thị inline, không
  chuyển sang màn lỗi PDF. Feedback hết khi người dùng sửa câu đang gõ.
- Trước khi mở `.app`, kiểm tra lại Info.plist, executable và bundle ID đối
  chiếu bản catalog nếu có. Không xác nhận code signature hoặc chống mọi race
  filesystem. Các lỗi OS chi tiết không đưa nguyên văn ra UI.
- Phát hiện và sửa stale-row window: khi query thay đổi, bỏ hàng cũ ngay trước
  khi chờ kết quả mới; Enter không thể mở index của truy vấn trước.

Live smoke: `scripts/verify_finder_build21.py`, artifacts tại
`artifacts/finder_build21_20261025/`. Dùng catalog thật và index hiện có,
QTest native ASCII keys “mo trinh duyet” (chưa nghiệm thu IME tiếng Việt),
không injected model answers/search hits, 0 model requests.

Lượt thành công: thấy Google Chrome + Safari, Down chọn Safari, Enter gọi
QDesktopServices.openUrl thật. API nhận yêu cầu; NSWorkspace xác nhận Safari
đang chạy sau đó. Safari đã chạy từ trước, nên đây là mở/kích hoạt app đang chạy,
KHÔNG phải xác nhận cold-start/latency khởi động. Report có thời gian quan sát
kèm qWait 100ms; không dùng làm benchmark startup. Ảnh đã xem trực tiếp:
`browser_selected_520.png`, `browser_opened_520.png`, `browser_opened_700.png`,
`browser_opened_compact.png`. Draft giữ nguyên sau mở và thu gọn.

Failure UI: `missing_app_error.png` hiển thị lỗi với đường dẫn `.app` thực sự
không tồn tại trong thư mục artifacts; gọi public launch slot, KHÔNG tạo kết quả
Finder giả và KHÔNG xóa app đã cài. Trường hợp app bị gỡ/đổi ID/mất executable/
plist hỏng, OS từ chối hoặc ném exception dùng unit contract fixtures, không
được tính là acceptance OS thật. Đã xác nhận sửa draft xóa feedback.

Lượt smoke đầu thất bại do đọc hàng cũ trước khi final query hoàn thành và đã
mở một tệp Markdown local cũ thay vì trình duyệt. Giữ report/log/ảnh thất bại ở
`attempt1_stale_results/`; không sửa raw evidence. Sửa cả controller (vô hiệu
hàng cũ) và script (chờ query đúng cùng application candidates), thêm regression
test chứng minh mở row 0 bị chặn trước khi event loop giao kết quả mới.

Kiểm tra riêng từng bộ Qt: 20 finder + 11 quick_pdf + 16 answer_presentation +
13 quick_unified = 60 passed. `git diff --check` sạch. Không sửa research scope,
Stage 0, PDF behavior hoặc thêm model request. Không commit/push; giữ nguyên
các thay đổi và artifacts của công việc khác.


## Bàn xem lượt 1 / Build .23 — 2026-10-25

Mục tiêu cuối do người dùng chốt: trải nghiệm như phiên chat xem bài/lá số hiện
có nhưng đẹp hơn, linh hoạt, ưu tiên phần nhìn thấy bài và chart trước bản luận.
Làm từng bước nhỏ, cải thiện file handling một ít mỗi lượt. Người dùng bổ sung
nguyên tắc bất biến mọi khả năng đi theo reasoning agentic; đã ghi ở AGENTS và
project_scope. Không tiếp tục luồng Finder .22 đang dở như một task riêng.

Triển khai lát cắt đầu:
- `/reading` hoặc Cmd+Shift+R mở ReadingDesk trong workbench hiện có. Dữ liệu
  giữ trong phiên khi thu/mở hoặc quay về; composer draft không bị xóa bởi các
  thao tác điều hướng. Lệnh `/reading` chỉ tiêu thụ chính chuỗi lệnh đó.
- Mở hồ sơ rat-natal-v1 từ Natal Atlas; tính lại bằng Swiss Ephemeris, không tin
  positions JSON nhập. Wheel và 5 vị trí cá nhân nằm trước phần bản luận.
- Bàn bài nhập tay: major/minor, 12 lá tối đa, aliases, xuôi/ngược và lá rơi không
  làm lệch số vị trí; reject lá không nhận diện hoặc trùng thay vì bỏ qua ngầm.
  Ký hiệu line-art do RAT dựng, chưa phải bộ ảnh minh họa deck hoàn chỉnh.
- Layout 2/3 cột theo chiều rộng, có click và keyboard focus/Enter/Space chọn lá.
  Compact hiện số lá và tên hồ sơ. Bản luận hiển thị chưa tạo, nút gửi bị khóa.
- Minor file handling: nút đính kèm theo ngữ cảnh hồ sơ JSON; filter picker/drop,
  giới hạn 20KB, schema rõ, nguồn file hiển thị; lỗi không xóa chart/cards cũ.
- Khắc phục Qt SVG dò font fallback list như một font bị thiếu, gây lần load
  rất chậm: presentation dùng Helvetica Neue trên macOS; không sửa phép tính.

Theo steering agentic, đã chuyển domain logic vào rat.engine.reading_session,
đăng ký prepare_reading_spread/load_reading_profile ở default registry. Controller
chỉ gọi dispatcher dùng chung với Agent, dùng result contract, lưu artifacts /
execution events và refs; load profile cần selected_document_path tường minh.
rat.ui.reading_presentation chỉ dựng SVG từ chart tool đã tính, không tự đọc file
hoặc tính lại. Không phải vòng model agentic hoàn chỉnh: planning/interpretation
chưa nối vào view, không có inference, không giả lập câu trả lời thành công.
Không coi tool registration là đã hoàn tất nguyên tắc toàn hệ; còn phải nối
vòng Agent ở lượt sau và kiểm tra các đường nghiệp vụ cũ trong task riêng.

Bằng chứng: scripts/verify_reading_turn1.py, artifacts/reading_turn1_20261025/.
Dùng profile local từ dữ liệu sinh người dùng thực sự cung cấp, SHA256 trong
report; cards nhập từ những lá người dùng báo trong chat. Không chép dữ liệu sinh
vào source/test fixtures. Capture Qt window thật empty, full 520/700, card section
520, import error, compact. Nhập bài/draft, apply, fold, mở compact và back dùng
Qt click/paste/key events; chọn profile dùng public slot, CHƯA nghiệm thu native
file picker/drop hoặc IME tiếng Việt. Card-section screenshot đặt contentY bằng
property để xem phần cuối, không phải bằng chứng wheel/trackpad input. 0 model
requests. Report cuối passed, refs gồm hai operation và draft-preservation check.

Kiểm tra:
- 30 headless tests pass: reading session/tools, natal chart, places, interaction
  kernel sau khi nối hợp đồng. tools_tests_final.log.
- Các suite Qt đã chạy riêng trong lượt UI: finder 21, quick_pdf 11 (retry),
  answer_presentation 16, unified 13. Trước cập nhật hợp đồng tools; final live
  smoke kiểm tra lại import/prepare qua dispatcher và artifact refs sau steering.
- Mở rộng assistant_runtime suite có 3 lỗi: thiếu message Runtime context trong
  test_context_includes_followup_and_selected_member; hai case {} và content rỗng
  trả empty_model_response trong khi tests kỳ vọng invalid_model_output. Cả ba
  tái hiện khi monkeypatch bỏ hai operation mới khỏi registry trong tiến trình
  kiểm tra (3 failed, 5 passed). Không sửa runtime/test expectations ngoài scope.
- Lượt Qt đầu có failure rồi abort; quick_pdf chạy lại riêng -x có 11 passed.
  Không khẳng định đã sửa nguyên nhân Qt lifecycle abort.
- Giữ attempts lỗi: Qt Image.Status enum không chuyển được sang Python; shortcut
  mở compact không kích hoạt trong smoke; SVG font alias load timeout; schema
  result contract ban đầu thiếu items. Đã sửa script/presentation/result schema,
  chạy lại final smoke pass. Các ảnh/log cũ ở attempt1/2/3/5_tool_contract và
  before_agentic_contract không được coi là nghiệm thu hợp đồng cuối.

Còn thiếu theo chủ ý lát cắt: nhập/sửa dữ liệu sinh trực tiếp, khoảng giờ sinh,
đối chiếu nhiều hồ sơ, câu hỏi từng vị trí/liên kết lá bổ sung, deck artwork hoàn
chỉnh, soạn/sửa/chốt bản luận và live-model agentic acceptance. Hồ sơ/cards hiện
chỉ giữ trong memory phiên. Không thay Stage 0, không commit/push, giữ các thay
đổi của công việc khác.


## Build .22 — Tìm & Xử lý Tệp theo Định hướng Reasoning Agentic (RAT-FIND-01), 2026-10-25

Triển khai toàn diện theo chỉ đạo tối cao của người dùng: *"TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC"* (Mọi tính năng RAT đều đóng vai trò công cụ suy luận trong vòng lặp CoT, không phải tiện ích thụ động cô lập) và yêu cầu thực thi một turn kỹ thuật chuyên sâu (`Build 2026.10.25.22`):

1. **Chuẩn hóa Truy vấn Hội thoại Tự nhiên (`rat/engine/finder_intent.py`)**:
   - Tách và khử các từ đệm hội thoại tự nhiên tiếng Việt & tiếng Anh (`tìm giùm tôi`, `giúp mình`, `hộ tôi`, `cho tôi`, `cái slide`, `cái file`, `bài báo về`, `tài liệu về`, `please find for me`, `can you get the slide on...`).
   - Ví dụ: Truy vấn `"tìm giùm tôi cái slide về dự án NAMI"` lập tức chuẩn hóa thành terms `"dự án NAMI"` + `slide_rule: True` chỉ trong < 0.5ms bằng biểu thức chính quy tối ưu, khắc phục triệt để lỗi 0-hit FTS5 do từ đệm trước đây.

2. **Lý do Khớp Ngữ cảnh Minh bạch (`rat/engine/progressive_search.py`)**:
   - Bổ sung trường `match_reason` giàu ngữ cảnh cho từng SearchHit:
     - `Khớp bài giảng / slide` (khi khớp quy tắc slide).
     - `Khớp báo cáo / tài liệu` (khi khớp quy tắc báo cáo/bài báo).
     - `Khớp nội dung: <trích đoạn ngắn>` (khi khớp văn bản trích dẫn bên trong tài liệu).
     - `Khớp tóm tắt: <tóm tắt>` (khi khớp metadata tóm tắt).
     - `Khớp chỉ mục tài liệu` (mặc định).
   - Loại trừ hoàn toàn các tệp rỗng/zombie (`st_size == 0`) khỏi kết quả tìm kiếm và danh sách ứng viên, ngăn chặn việc nạp phải các file hỏng/dở dang từ thư mục Downloads.

3. **Cơ chế Đưa Tài liệu vào Bàn Chuột (`adoptSelectedHit`) & Giữ Trọn Bản Nháp**:
   - `rat/ui/quick_pdf_controller.py`: Bổ sung `@pyqtSlot(int, result=bool) def adoptSelectedHit(self, index)`. Cho phép người dùng đưa tài liệu được tìm thấy vào bàn làm việc của Chuột (`activeContext`) để hỏi tiếp ngay lập tức mà **tuyệt đối không xóa bản nháp** trong ô composer (`editor.text` được bảo toàn 100%).
   - QML UI (`rat/ui/quick/PDFDesk.qml`):
     - Phím tắt `Tab` trên `draftEditor` được nâng quyền ưu tiên (`Keys.priority: Keys.BeforeItem`) kết hợp window `Shortcut { sequence: "Tab" }`: khi đang chọn một ứng viên trong danh sách gợi ý, bấm `Tab` sẽ lập tức nạp tài liệu vào bàn làm việc.
     - Thanh hành động đáy (`bottomActionBar`) bổ sung tactile keycap badge `finderAdoptAction`: hiển thị nhãn `"Tab · Đưa vào bàn Chuột để hỏi"` (hoặc `"Đưa vào bàn"` ở màn hình hẹp), hỗ trợ cả nhấp chuột lẫn phím bấm.
     - Nhãn hướng dẫn composer (`composerDropStatus`): `"↑↓ chọn · ↵ mở · Tab đưa vào bàn Chuột · Esc đóng"`.

4. **Chế độ Ngăn kéo Tinh tế (Subtle Drawer Tab) cho Câu hỏi Hội thoại**:
   - Khi người dùng gõ câu hỏi hội thoại tự nhiên (>= 5 từ), Finder không tự động chiếm trọn toàn bộ không gian soạn thảo. Thay vào đó, kết quả xuất hiện dưới dạng một tab ngăn kéo tinh tế (`finderDrawerTab`: `3 gợi ý · ▾`) nằm kín đáo phía trên composer. Người dùng có thể tiếp tục gõ mà không bị gián đoạn, hoặc bấm tab / dùng phím mũi tên để mở danh sách ứng viên khi muốn.

5. **Nghiệm thu Tự động Desktop Thật (`scripts/verify_finder_build22.py`)**:
   - Kịch bản kiểm chứng tự động toàn diện trên dữ liệu tệp và chỉ mục thật:
     - Thử nghiệm 1 (Slide bài giảng): Gõ `"tìm giùm tôi cái slide về dự án NAMI"`, phát hiện ứng viên `Dự án NAMI - Hybrid RL-ALNS.pptx`, hiển thị tab ngăn kéo `3 gợi ý · ▾`, nhãn `Khớp bài giảng / slide`.
     - Thử nghiệm 2 (Tài liệu nghiên cứu): Gõ `"tìm tài liệu pdf về ALNS Double DQN"`, phát hiện ứng viên PDF hợp lệ `Phản biện học thuật “Tối ưu hóa lựa chọn toán tử trong ALNS bằng Double DQN cho bài toán VRPTW”.pdf`. Bấm phím `Tab` nạp tài liệu thành công vào bàn làm việc (`_selection` và `fileName` cập nhật), bản nháp câu hỏi được giữ nguyên vẹn 100%.
     - Kiểm tra trực quan: Chụp 3 ảnh màn hình desktop thật với `QT_QUICK_BACKEND=software` tại các kích thước 520px và 700px. Kiểm tra độ phủ pixel không trong suốt đạt từ 64.94% đến 70.84% (vượt xa ngưỡng quy định >= 40%):
       - `artifacts/finder_build22_20261025/agentic_finder_candidates_520.png` (1040x950)
       - `artifacts/finder_build22_20261025/agentic_file_adopted_desk.png` (1040x610)
       - `artifacts/finder_build22_20261025/agentic_finder_candidates_700.png` (1400x882)
       - Sao chép toàn bộ sang thư mục artifacts hội thoại.

6. **Kết quả Bộ Test Độc lập Toàn hệ thống (110 passed, 0 failed)**:
   - `tests/test_quick_finder_flow.py`: 21 passed
   - `tests/test_progressive_search.py`: 20 passed
   - `tests/test_quick_pdf.py`: 11 passed
   - `tests/test_quick_unified_flow.py`: 13 passed
   - `tests/test_quick_answer_presentation.py`: 16 passed
   - Research study gates (`test_research_study.py`, `test_optimal_stopping.py`, `test_entry_predictor.py`): 29 passed.
   - Ngân sách suy luận: 0 request model / 0 token trong toàn bộ quá trình tìm kiếm và nạp tệp (tính toán hoàn toàn cục bộ, đáp ứng < 30ms cho tương tác gõ phím). Không vi phạm solo Git workflow (không commit, không push).
