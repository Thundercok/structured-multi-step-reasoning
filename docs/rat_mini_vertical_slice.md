# RAT Mini — quyết định vertical slice và UX

Latest continuation, 2026-10-29: user resumed RAT Lite unified interaction and
authorized small commits/normal pushes. Source .24 replaces four workspace
choices with compact/expanded task presentation and one composer. See
[unified source handoff](rat_lite_unified_interaction_handoff_20261029.md).
No tests/build/launch/acceptance were run for this change; bundles predate it.

**Tên gọi tương lai — quyết định người dùng 2026-10-28:** RAT Mini sẽ mang tên
**RAT Lite** (“Lite”), vẫn là cùng vertical slice của RAT–CoT. Mini/Lite đang
tạm gác vì chưa phát triển xong. Chưa đổi identifiers, đường dẫn hay bản build
theo quyết định này; chỉ thực hiện chuyển tên khi tiếp tục phần việc đó.

Ngày chốt: 2026-10-26, Asia/Saigon. Nguồn: chỉ đạo trực tiếp của người dùng
trong phiên phát triển Mini. Đây là định hướng hiện hành, không phải xác nhận
mọi phần dưới đây đã được triển khai.

## Vai trò của Mini

### M5.11 — miễn phí và plug-and-play cho cặp Anh ↔ Việt

Người dùng chốt giữ miễn phí và yêu cầu tham khảo cách app khác giải quyết
quota, không coi việc thêm API key là giải pháp mặc định. Sau đối chiếu Firefox,
Argos và Easydict, bản M5.11 đóng kèm model OPUS-MT/Argos en↔vi và runtime
CTranslate2. Fresh install mặc định Tự động: cặp đã kèm dịch trên máy; cặp khác
vẫn online và chịu quota. Không tải model hay cài Python/server trên máy nhận.
Đây là MT backend trong tool dịch chung, không phải local Agent LLM hoặc utility
UI riêng. Hợp đồng, source refs, verifier và AgentExecutionService giữ nguyên.
Chi tiết nguồn/license/giới hạn: [dịch local](contracts/local_translation.md).

Thừa kế M5.10: Spotlight tìm đồng thời tối đa 3 scope, cancel reaps subprocess;
coverage ghi số scope hoàn tất. Menu phụ có chọn ảnh qua FileDialog dùng chung
ImageInput/capture tool. API key chỉ là tùy chọn nâng cao trong Keychain; không
đổi lựa chọn miễn phí của người dùng. Chưa suy ra thumbnail drag đã đạt từ picker.
Hai chiều đã chạy model thật qua service trên 3 đoạn công khai với cloud bị
chặn trong tiến trình kiểm tra. Còn gate UI bản đóng gói và máy nhận; xem audit.

### M5.9 — sửa lỗi từ kiểm thử live 2026-10-27

Cập nhật live sau mở khóa: M5.9 tìm đúng `BEST-Route.pdf`, Enter mở đúng Preview
URL; 2 scope Spotlight timeout nên coverage chỉ partial. Ảnh dán từ Preview
đã OCR thật; sửa chữ → tạo artifact mới với parent/root/hash/provenance khớp
nguồn → verifier cấu trúc PASS. Dịch nguồn ban đầu và retry đều rate limited,
chữ sửa được giữ. Screenshot khớp tại audit M5.9/live/01 và 03; ảnh 02 stale
đã đánh dấu. Native drop chưa có receipt; Finder automation timeout. Máy lại
khóa sau các bước này. Chưa đủ gate stable/recipient/main integration.


M5.8 đã chạy thật theo yêu cầu “tự test”: ảnh copy từ Preview → dán vào RAT →
OCR → MyMemory dịch thành công một lượt; Google429 và lượt sau quota thất bại.
Sửa OCR bằng bàn phím giữ draft/ẩn bản dịch cũ, nhưng retry bị
`invalid_object:result` do contract thiếu các trường capture kế thừa. M5.9
cho correction dùng chung schema capture và giữ chuỗi parent/root/hash; tắt
HTTP INFO để tránh ghi nguồn dịch vào URL log. Hai regression contract pass;
không thay thế acceptance UI. Thêm gợi ý “Thả ảnh hoặc ⌘V” ở footer.

Spotlight ngoài sandbox đang bật và thấy PDF công khai; trace không có kết quả
đã nhận nhầm `tm BEST-Route.pdf` do công cụ gõ mất dấu. Cần retest đúng tên file,
không kết luận OS tắt index hoặc app Finder hỏng từ lần nhập này.
Native thumbnail/drop, máy người nhận, UI main và vòng LLM thực vẫn chưa nghiệm
thu. Bằng chứng/lỗi thật ở `audit/rat_mini_m58_20261027/live/` và audit M5.9.

### Ứng viên M5.8 — sửa ingress ảnh thu nhỏ macOS

M5.7 có lỗi drop thumbnail được người dùng báo và UI xác nhận. Native Qt MIME
ingress thay chuỗi URL QML, hỗ trợ pixel/encoded image/file-reference và nhánh
file promise bất đồng bộ; normalize cùng paste vào ImageInput. QML chỉ chiếu
trạng thái, nghiệp vụ vẫn qua tools. Xem [contract](contracts/native_image_drop.md).
Chưa xác nhận thumbnail thật trên M5.8; đã tự test Clipboard theo chỉ đạo mới. Main chưa tích hợp.

### Ứng viên M5.7 — ổn định hóa và nghiệm thu theo từng mốc

Theo [kế hoạch bàn giao/main](rat_mini_release_plan.md): editor chữ thu gọn mặc
định, lỗi tự mở phần chữ, Chi tiết bản dịch ở menu phụ; giữ source khi đổi
provider; chuẩn hóa lỗi mạng/quota, phục hồi config sai kiểu và bridge hiện
app đã chạy. Chuẩn bị gói M5.7 và screenshot thật đã được yêu cầu. Chưa nghiệm
thu máy người nhận, chưa tích hợp UI main; trạng thái thực nằm trong audit.

### M5.6-dev — hiệu chỉnh OCR và dịch lại, source chưa kiểm thử

Giấy kết quả có editor chữ OCR, xem bản ban đầu và dịch lại. Phần sửa đi qua
tool `correct_captured_text` tạo artifact mới; workflow headless dùng source_ref
mới để dịch. Retry chữ không đổi bỏ qua OCR; lỗi mạng giữ source/draft. Bản dịch
cũ ẩn khi draft đang thay đổi. Chuỗi parent/root/hash dành cho đối chiếu trong
session, không tự tạo dữ liệu huấn luyện hoặc chứng minh model học tốt hơn.
Chưa build/test M5.6 và chưa tích hợp UI main. ZIP M5.4 không chứa thay đổi này.

### M5.5-dev — tăng phần dùng chung, source chưa kiểm thử

ImageInput headless giữ snapshot/provenance; workflow capture→source_ref→dịch
được tách khỏi Qt worker sang engine. Capture và translation contracts kiểm
tra cấu trúc/hash/pin nguồn; UI chỉ chiếu nhãn nguồn. Xem
[hợp đồng tái sử dụng](contracts/image_translation_ingress.md).
Main chưa được nối. Chưa build/test M5.5; ZIP M5.4 vẫn là bản đóng gói trước đó.

### Hướng hiện hành M5.4: screenshot kéo thả

Người dùng đã đưa ⌥⇧D vào backlog. Dùng ⌘⇧4 của macOS để lưu screenshot,
rồi thả một ảnh từ Desktop/Finder vào RAT để tự OCR/dịch. Có thể gõ chỉ dẫn
ngôn ngữ trước khi thả. Paste pixel hoặc file ảnh gắn draft, Enter để dịch.
UI chỉ chuẩn hóa đầu vào; `capture_text(image)` tạo artifact và `translate_text`
nhận source_ref qua dispatcher/service chung. Không cần RAT tự chụp màn hình.
M5.4 không khởi động helper hay đăng ký global hotkey. Main profile chưa nối
drag/drop này. Source M5.4 chưa kiểm thử; không suy ra acceptance từ các bản cũ.
Chi tiết và kế hoạch kiểm chứng nằm ở [backlog](backlog/rat_mini_global_capture.md).

### Lịch sử hotkey transport M5.3 — đã hoãn

⌥⇧D được một native Carbon helper nhận trên event loop riêng rồi gửi `PRESSED`
qua pipe về `QProcess` trên GUI thread. Helper chỉ nhận intent, không đọc màn
hình/Clipboard và không gọi nghiệp vụ. GUI tiếp tục phát `regionCaptureRequested`
qua luồng tool capture/OCR/translation hiện có. Không cần Accessibility hay
Input Monitoring cho adapter này. Helper thoát khi stdin đóng, kể cả GUI crash;
UI báo lỗi đăng ký hoặc helper dừng thay vì tuyên bố hotkey hoạt động.

Bản M5.3 đóng gói chứa sẵn helper. Khi phát triển M5.3 từ source, chạy
`zsh tools/build_rat_mini_hotkey.sh` một lần trước `python mini_app.py`.
Main profile chưa nối adapter/ingress này. Việc compile/đăng ký thành công không
thay thế bằng chứng bấm hotkey vật lý từ ứng dụng khác.

Mini là một vertical slice end-to-end của RAT chính trong cùng hệ RAT–CoT.
Người dùng đang phát triển slice này để dùng lại cho RAT chính; việc đưa app
cho bạn dùng thử là một mốc phân phối/feedback, không định nghĩa Mini thành
sản phẩm nghiệp vụ riêng hoặc demo dùng xong bỏ.

Slice hẹp về số capabilities nhưng đầy đủ chiều sâu:

`Yêu cầu → làm rõ/định tuyến/lập kế hoạch → tool dispatch → quan sát thật →
verification → artifact/trạng thái → UI → app đóng gói`.

Không mở rộng tính năng chỉ để giống toàn bộ RAT chính. Không coi việc có
capability registry là bằng chứng vòng suy luận/model đã chạy thật.

## UX đã chốt: một luồng liền mạch

Cập nhật M5.14, 2026-10-27: workbench tạm thời, RAT cố định kích thước và né
cạnh; copy/open/đổi app ẩn nhưng giữ phiên. OCR/xem ảnh thay body. Có nghiệm
thu ngắn thật cho dịch, paste ảnh, correction/retry và Finder 3/3 mở PDF;
giới hạn từng build ở [handoff M5.14](../audit/rat_mini_m514_20261027/README.md).
Chưa coi đã nghiệm thu thumbnail drag, click-through, M3 hay vòng Agent/main UI.
Hợp đồng: [Transient workbench](contracts/transient_workbench.md).

Cập nhật nguồn M5.13, 2026-10-27: thực hiện nhận ảnh thống nhất (drop/paste/picker),
thumbnail bộ nhớ, yêu cầu có thể sửa/thử lại, paper/mascot và cài đặt Nâng cao;
nối soft wrap OCR qua capture contract chung. Chưa chạy test, mở app
hay chụp nghiệm thu cho thay đổi mới; bản đóng gói có trạng thái ở handoff.
Finder mới được bổ sung chẩn đoán và
candidate mitigation; nguyên nhân timeout trong app vẫn chưa được xác nhận.
Chi tiết: [M5.13 source handoff](../audit/rat_mini_m513_20261027/README.md).

- Dùng lại diện mạo UI RAT chính: chuột, ô nhập giấy, giấy kết quả mở phía trên,
  các thành phần tương tác dùng chung.
- Một ô nhập và một nút gửi. Người dùng diễn đạt điều muốn làm, không cần chọn
  mode Tìm file/Dịch hoặc biết tên tool/provider.
- Bộ điều phối chọn tool theo yêu cầu và ngữ cảnh rõ ràng. Yêu cầu chưa đủ hoặc
  mơ hồ thì hỏi một câu ngắn ngay trong luồng; không mở màn hình chọn mode.
- Ví dụ “tìm báo cáo hôm qua” đi tới Finder; “dịch đoạn này: Hello world” đi
  tới Translation. Câu trần như “Hello world” không tự chứng minh ý định dịch;
  cách xử lý cần dùng ngữ cảnh hoặc hỏi lại, không đoán chắc cho mọi đầu vào.
- Kết quả tìm file là danh sách chọn/mở; bản dịch là văn bản có thể sao chép.
  UI thể hiện đang làm, thiếu input, partial, lỗi và hủy từ execution thật.
- Clipboard, phím tắt và cài đặt là thao tác phụ. Chỉ lấy/gửi Clipboard khi
  người dùng yêu cầu tương ứng; không tự theo dõi hoặc gửi nền.
- Các thao tác trực tiếp, kể cả mở file đã chọn và dịch Clipboard, vẫn dùng
  cùng tool contracts/service/dispatcher; không đặt handler nghiệp vụ trong QML.

## Phần phải tái sử dụng cho RAT chính

| Thành phần | Quy tắc |
| --- | --- |
| Intent/routing và làm rõ | Thiết kế thành logic dùng chung, nhận profile/capabilities và ngữ cảnh; không để UI Mini tự chọn nghiệp vụ bằng nút mode |
| Tool contracts và providers | Finder/Translation có schema, observations, lỗi và verifiers; không tạo bản handler khác khi tích hợp main |
| Execution lifecycle | Dùng service chung, giữ cancellation, stale-result guard, needs_input, partial và budget |
| UI | Tái sử dụng QML components và quy ước snapshot; controller chỉ chuyển input/trình bày output |
| Composition | Profile Mini giới hạn đúng hai capabilities; cấu hình main có thể dùng cùng khả năng mà không phụ thuộc cửa sổ Mini |
| Evidence | Ghi tách software tests, UI/backend thật, model loop thật và kiểm thử máy người nhận |

Nhánh xác định có thể dùng kế hoạch một action với 0 model calls qua service
chung. Nhánh cần suy luận đi qua runtime Agent với tools cùng registry. Khi
model/key chưa khả dụng, giữ chức năng xác định và thông báo hoặc hỏi lại;
không dựng câu trả lời Agent giả. Đây không phải yêu cầu mọi thao tác đều gọi LLM.

“Dùng lại cho main” nói về RAT chính và khả năng tích hợp, không phải yêu cầu
tạo branch hay push. Tiếp tục làm trên `main` theo workflow repo hiện hành.

## Scope đang làm và phần hoãn

Đang làm: tìm file bằng Spotlight và dịch snippet nhập/Clipboard, nối vào
luồng tương tác thống nhất, app macOS có thể đưa cho người không lập trình.

Hoãn: vector DB, semantic embedding, local LLM, Swift Translation, dịch dàn
trang tài liệu và tối ưu dung lượng/RAM. Không tự đưa các hạng mục đó trở lại
vì đặc tả ban đầu có đề cập. Giữ nghiên cứu/Stage 0 và tuyên bố chất lượng riêng.

## Trạng thái bàn giao hiện tại

- Có backend Spotlight và Translation qua MiniSession/AgentExecutionService;
  đã có bằng chứng tìm/mở file và dịch trực tiếp/Clipboard thật.
- M3 đã chuyển từ QtWidgets sang Qt Quick, dùng chung QuietButton, DeskIcon,
  KeycapBadge và FinderResultsView với RAT chính. Đã có app/ZIP và ảnh UI thật.
- **Build M3 vẫn có `find/translate` mode trong controller/UI. Người dùng đã
  bác bỏ cách tương tác này.** Không dùng evidence/build M3 để gọi UX một ô
  nhập của M4 đã hoàn thành.
- Tiếp nối M4: source đã bỏ mode, chuyển submit qua `ToolGoalRouter` trong
  `rat/engine/goal_routing.py` và `MiniSession.submit`. Router không phụ thuộc
  Qt/Mini; main profile chưa được nối router này. Mini đã giữ lượt hỏi lại bằng
  InputRequest và tiếp tục qua service/tool contracts hiện có. Phần routing
  xác định và hỏi lại không phải một vòng suy luận model; nhánh yêu cầu nhiều
  bước vẫn dùng runtime Agent đã có. Evidence M4 và giới hạn live nằm trong
  `audit/rat_mini_m4_20261026/`, không suy ra từ evidence M3.
- Nhánh model cloud đã có dây nối runtime; chưa xác nhận vòng model thật trong
  phiên này vì chưa có API key. Chưa xác nhận trên máy người nhận hoặc notarize.
- Bằng chứng và lỗi lịch sử giữ tại `audit/rat_mini_m2_20261026/` và
  `audit/rat_mini_m3_20261026/`; không sửa raw logs để biến lỗi thành pass.

### M5 — sửa workflow theo yêu cầu, chưa kiểm thử

- ⌥⇧D phát signal về GUI thread, ẩn RAT, nhường compositor trước khi gọi
  capture tool chọn vùng. Tool OCR tạo captured_text/source_ref rồi dùng
  translation tool chung; hủy vùng không dùng Clipboard thay thế.
- Vị trí con trỏ lúc capture hoàn tất được giữ để hiện kết quả gần ngữ cảnh.
  Không gọi requestActivate cho kết quả chụp vùng.
- Paste được snapshot trên GUI thread: văn bản giữ origin cho router; URL tệp
  local thành yêu cầu tìm tên file; pixel ảnh được giữ làm draft, Enter để OCR
  và dịch. Ảnh không đưa vào model tool arguments; dùng trusted capture context.
- Router dùng nội dung, nguồn nhập, nhận diện ngôn ngữ và bước trước để chọn
  tool. Chỉ hỏi lại khi chưa đủ tín hiệu; không bảo đảm suy đúng mọi ý định mơ hồ.
- Chuột bám cạnh ô nhập với lề 12px; bong bóng theo vị trí chuột, không còn
  offset đẩy chuột ra ngoài mép trái.
- Không chạy app, test, smoke, OCR hay chụp ảnh acceptance cho M5. Build/ZIP
  là bước đóng gói, không xác nhận runtime. Không dùng evidence M4 thay thế.

## Việc tiếp theo và giới hạn kiểm thử

1. M4 đã thực hiện trong source: bỏ mode selector, nối submit qua routing và
   đưa Clipboard vào menu phụ, giữ file cards và translation projection.
2. Giữ ngữ cảnh hỏi lại trong session, không lưu mode trong UI. Yêu cầu rõ mới
   thay thế câu hỏi cũ; câu trả lời bổ sung giữ source ref/args của tool.
3. Khi tích hợp RAT chính, dùng cùng ingress router qua composition/profile;
   chưa tuyên bố main profile đã dùng router mới.
4. Kiểm tra tối thiểu đúng phần đổi: khởi động, một lượt tìm, một lượt dịch và
   trường hợp làm rõ bị thay đổi; sau đó cập nhật app/ZIP và trạng thái tài liệu.

Người dùng đã chốt bổ sung: **không tự test tốn token trừ khi được yêu cầu rõ**.
Hoàn thiện toàn bộ phần sửa trước; không xen kẽ test trong lúc phát triển.
Quy tắc này thay thế đề xuất tự chạy kiểm tra tối thiểu ở mục 4 bên trên.
Không tự chạy test suite, smoke, luồng UI hoặc chụp ảnh acceptance. “Tiếp tục”
không mặc nhiên cho phép test. Chỉ claim hành vi có bằng chứng thật; mục chưa
kiểm tra thì ghi rõ. Lượt chốt quyết định ban đầu
chỉ ghi tài liệu; trạng thái triển khai và kiểm tra M4 được cập nhật
riêng ở trên và trong audit.

### Chốt phiên theo yêu cầu wrap-up — M5.12

Dịch offline đã chạy thật qua UI M5.11 (ảnh chọn/OCR/sửa/dịch lại) và M5.12
(nhập Hello world., tự route, ra Chào cả thế giới.). M5.12 giữ output Spotlight
trước timeout nếu có và không kết luận no-hit khi chưa scope nào hoàn tất.
Tuy vậy Finder trong app vẫn 0/3 timeout, trong khi provider headless thấy PDF
công khai ở Documents. Chưa chốt nguyên nhân, không tự yêu cầu Full Disk Access.
Bài thử corpus-only bị dừng vì Mac khóa rồi người dùng yêu cầu wrap-up; cấu hình
test được trả default, cấu hình người dùng không đổi. Thumbnail/native drop,
chất lượng dịch/soft-wrap, máy M3 và main integration chưa nghiệm thu.
Gói cuối, hash, screenshot và bước tiếp: audit/rat_mini_m512_20261027/status.json.

### M5.15 — explicit scope extension, 2026-10-27

User approved the ten-point plan in docs/rat_mini_m515_handoff.md, including
Folder Organizer (item 7), Hello setup (8), minor UI (9), bounded final acceptance
(10), and gated reuse in main (6). This overrides the earlier two-capability-only
Mini composition for this milestone, without enabling timetable/semantic/DocAI.
Organizer is a shared reasoning capability, not a UI-only utility. Setup uses a
shared readiness operation. Main composition and M3 acceptance remain gated.
This specific turn authorizes tests only after source completion; it does not
revoke the general rule against automatic tests in later turns.

### M5.16 — UX source rework, unverified

2026-10-27: user remains dissatisfied across interaction, layout and workflow,
and explicitly pauses tests. Authorized source implementation of the M5.16 plan:
one presentation surface, independent next draft/request edit, explicit Finder
keyboard focus, sticky artifact actions, stable mascot anchor and short inline
Hello/help/settings. See docs/rat_mini_m516_implementation.md. No new app/ZIP,
UI acceptance or screenshot. M5.15 remains the existing distributable; M3/main
integration gates remain open. Future turns must not infer test permission from
this implementation authorization.

### Look / Minimal / Single / Full — source follow-up, 2026-10-27

User approved four presentation modes in the same session. Look supplies captured
text as an observation to shared tools/Agent; Minimal folds to one line; Single
keeps the production layout; Full adds source/result comparison when wide enough.
Source shortcut pair: ⌥Space Look / ⌥⇧Space Minimal. This does not enable screen
capture by hotkey or restore ⌥⇧D. No tests/build/launch for these changes; main
UI/binding migration and M3 remain gated. Current bundle predates the changes.
See [Look source handoff](rat_mini_look_modes.md).

### Look accepted visual direction — standing standby + C/B, source only

2026-10-27: user approved implementing original standing-sprite standby (no A),
floating-head C for short translations and peeking-head/hand B for paragraphs.
Look now has its own no-input bubble surface rather than the old shared composer,
with fixed original-sprite scale and separate edge anchor. Explicit Look image/
text input uses the existing capture/translation tool chain; no new model or
business executor. See docs/rat_mini_look_modes.md. No tests, launch, screenshots
or build for this revision. The current app/ZIP predates it; main/M3 integration
and Stage 0 remain unchanged.

### Shortcut correction — 2026-10-28

User corrected the intended mapping: tap ⌥⇧Space → Look; hold ⌥⇧Space →
Minimal. This supersedes the prior opposite mapping. The existing source and
0.5.17 / 20261028.6 bundle still use the old direction; no code or build was
changed by this decision. See docs/rat_mini_look_modes.md.

### Look repair source handoff — 2026-10-28

The current source reverses the shortcut to tap → Look / hold → Minimal, adds
explicit screen-region capture through the shared tools, preserves the previous
session on capture cancellation, and revises the bubble/copy and C/B sprites.
Details and verification limits are in `rat_mini_look_modes.md`. The existing
packaged app predates these changes; this revision has not been built or tested.
Real model-driven CoT, visual acceptance and main integration remain unconfirmed.

Latest continuation: `docs/rat_mini_look_handoff_20261028.md`. The repair was later
built as 20261028.7 and sent an open command; the newer near-text floating head,
Wall presentation and corner indicator concept remains unimplemented.
