# Bàn giao RAT UI và runner — 2026-10-24

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
