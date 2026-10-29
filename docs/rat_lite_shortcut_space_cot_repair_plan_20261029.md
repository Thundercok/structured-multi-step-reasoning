# RAT Lite — kế hoạch sửa shortcut, Space và selection theo CoT

Ngày 2026-10-29. Người dùng yêu cầu **plan trong lượt này**, chưa yêu cầu triển
khai hay chạy kiểm thử. Mục tiêu là bôi đen → shortcut → RAT phản hồi trên
**chính Space đang làm việc**, giữ nguồn và hiển thị kết quả hoặc lỗi có thể xử
lý. Plan bao gồm chuỗi RAT–CoT thực tế, không dừng ở việc làm hotkey hiện UI.

## 1. Bằng chứng hiện có, không suy diễn

- Người dùng xác nhận shortcut làm chuyển **desktop/Space khác**.
- Settings của RAT đang lưu `option_shift_space` (`⌥⇧Space`). Helper bản đang
  chạy đăng ký keycode49/modifiers2560. Đây là cấu hình quan sát, không chứng
  minh macOS hoặc ứng dụng khác không dùng cùng tổ hợp.
- Journal `.28` đã ghi `selection → invoked → capture_requested → capture_started
  → capture_failed → present_requested → presented`. Shortcut đã tới helper,
  nhưng capture thất bại. `presented` chỉ là lời gọi hiển thị, không chứng minh
  người dùng đã thấy nội dung. Bản đó không ghi mã lỗi capture.
- Source mới sau đó đã thêm mã lỗi an toàn, lỗi sticky, Dán chữ chủ động và
  Workbench/result revision; **chưa build/test**, không thể dùng để giải thích
  hay xác nhận app đang chạy.
- `.28` và `.27` là các bundle ad-hoc cùng identifier ở các path khác nhau. Điều
  đó làm kiểm tra quyền TCC và build identity quan trọng; chưa chứng minh quyền
  là nguyên nhân của lần thất bại.
- `MiniShell.present()` có đường `activateIgnoringOtherApps_`/`requestActivate`
  khi composing; passive reader có đường return trước activation. Cần đo path
  thực tế ở capture success/failure, recall và editor, không khẳng định mọi
  shortcut đều gọi activate. `setScreen()` là display, không đồng nghĩa Space.

Một trong các chord tùy chọn hiện có là `⌃⌥Space`, trùng tổ hợp đổi input source
được Apple mô tả. Nó **không phải chord đang lưu của người dùng**, và điều đó
không giải thích được Space switch đã báo. Nguồn: [Apple keyboard shortcuts](https://support.apple.com/en-us/102650).

## 2. Hợp đồng thành công end-to-end

1. Người dùng chủ động chọn chữ trong app nguồn và gọi shortcut đã cấu hình.
2. RAT nhận đúng một intent, pin PID/foreground nguồn trước khi show/focus.
3. Thu nhận qua `capture_text` trong dispatcher, tạo `captured_text` artifact
   có ref/revision/hash và verifier. Geometry optional, tạm trong bộ nhớ.
4. Goal mặc định đã công bố là dịch: router/service lập hành động `translate_text`
   dựa trên source_ref. Nếu user ra ý định khác, dùng cùng ingress/registered
   tools; cần dữ kiện thì đưa `InputRequest` trong cùng luồng.
5. Execution tạo observations, verification, completion/partial/error và public
   response. Direct deterministic route là một đường điều phối có kiểm tra;
   chỉ gọi là model Agent loop nếu loop và model thực sự chạy. Không giả CoT.
6. UI projection cho thấy trạng thái và kết quả/clarification hoặc một lỗi với
   recovery phù hợp. Giữ input, source, task; không tự đổi Space hoặc focus app
   nguồn trong đường Quick Look thụ động.
7. User có thể hỏi tiếp với referent đúng, mở đọc rộng/Workbench có chọn lựa.
   Revision của output phải dùng pinned result ref, không đánh tráo output làm
   nguồn đã capture. Expand/close/history không tự dispatch lại tool.

**Thành công không phải chỉ có READY, window visible hay test pass.** Cần có
một lượt thật quan sát được từ trigger tới public result ở app nguồn, rồi thử
các đường lỗi và Space. App không hỗ trợ selected text phải báo đúng và đưa fallback
chủ động; không thể hứa đọc mọi app hoặc bypass vùng bị chặn.

## 3. Khóa việc chuyển Space

### 3.1 Phân biệt nguyên nhân trước khi sửa

Ghi nhận timeline theo invocation: nhận key → PID nguồn đã pin → capture begin/
end → yêu cầu show → native window show/activation/focus → kết quả. Quan sát
thông báo hệ thống `activeSpaceDidChangeNotification` và application activation
trong quá trình debug khi platform hỗ trợ; ghi trạng thái đã đổi/chưa đổi và
thứ tự sự kiện, không ghi tên/đường dẫn/cửa sổ cá nhân, nội dung text, tọa độ,
hay dùng private API để đọc Space id. Phân biệt:

- Space đổi **trước** callback: hệ thống/chord/ứng dụng khác hoặc keyboard remap.
- Space đổi khi show/raise: window đang thuộc Space khác hoặc collection behavior.
- Space đổi khi activation/requestActivate: cách app được kích hoạt hoặc chính
  sách macOS chuyển tới Space chứa cửa sổ app.
- Chỉ đổi display/đổi foreground, không đổi Space: xử lý như case riêng.

Các giả thuyết cần quan sát, không chọn một nguyên nhân chỉ dựa vào log hiện có.
Cần xem cả tray recall, shortcut từ app khác, first launch, QML popup/dialog,
editor click và completion muộn.

### 3.2 Chính sách cửa sổ

- Shortcut Quick Look: capture trước; show ở current Space mà không activate
  RAT, không requestActivate và không gọi một đường summon composer bất ngờ.
  App nguồn giữ foreground trong suốt capture; kết quả có thể đọc bằng chuột.
- Thử AppKit `NSWindowCollectionBehaviorMoveToActiveSpace` cho một window đang
  dùng khi cần activate, thay vì kéo người dùng tới Space cũ. Apple mô tả behavior
  này là chuyển window tới active Space khi window active: [AppKit collection
  behaviors](https://developer.apple.com/documentation/appkit/nswindow/collectionbehavior-swift.struct?language=objc).
- Đánh giá `CanJoinAllSpaces` và `FullScreenAuxiliary` riêng theo yêu cầu thực;
  không trộn cờ loại trừ nhau, không bật “mọi Space” một cách mặc định nếu làm
  lộ overlay hoặc thay đổi interaction. `nonactivatingPanel` chỉ áp dụng cho
  NSPanel; không giả rằng đặt flag lên QQuickView là đủ.
- Click vào editor mới được xin focus. Trước khi activate, window phải ở Space
  hiện tại. Focus/keyboard test phải giữ draft, selected text và context, kể cả
  khi window từ hidden trở lại. Nếu native binding không áp dụng được, báo rõ
  limitation và chọn phương án được quan sát; không silently chuyển Space.
- Completion hoặc lỗi sau khi user cất/ẩn không tự bật lại hay activate app.
  Error cần một tín hiệu có thể tìm lại (badge/nhật ký), không biến mất im lặng.

## 4. Phím tắt đáng tin cậy

- Cấu hình một chord cho một ý định. Thêm key recorder và danh sách đề xuất, cho
  phép user chọn chord với modifiers/key thông dụng; không chỉ hardcode ba Space
  chords. Văn bản hiển thị, native keycode/modifiers và stored value chung một
  contract; tương thích layout bàn phím và chỉ một owner.
- Kiểm tra trước các tổ hợp macOS đã biết và dành chỗ cho xung đột tùy chỉnh.
  Không quảng cáo một chord cố định là chắc chắn rảnh trên mọi máy. Registration
  exclusive thành công là bằng chứng đăng ký, không chứng minh một lượt key thật
  sẽ đến hoặc hệ thống không xử lý hành động khác.
- Đổi chord theo giao dịch: validate → đóng owner → đăng ký mới → nhận handshake
  đúng build/chord → commit settings. Nếu thất bại, khôi phục chord cũ; nếu khôi
  phục thất bại báo offline rõ, giữ kênh menu/tray. Không hủy/đổi system shortcuts.
- Không tự thay cài đặt user đang dùng chỉ vì một chord khác có vẻ an toàn.
  Ẩn/gắn cảnh báo cho `⌃⌥Space` do Apple nêu; migration giữ giá trị cũ đến khi
  người dùng chủ động đổi. Có đường gọi Quick Look bằng menu/tray nếu chord lỗi.
- Nhấn giữ/repeat chỉ một invocation cho một lần nhấn; busy báo rõ không cancel,
  không queue bí mật. Chỉ chẩn đoán metadata giới hạn, không ghi phím gõ thường.

## 5. Capture và fallback rõ nguyên nhân

- Kiểm tra quyền từ **chính tiến trình app đã ký đang chạy**, không suy ra từ
  Python ngoài app hoặc trạng thái Accessibility của bản khác. Nếu thiếu quyền,
  hiển thị đúng action mở System Settings, chỉ đường chọn đúng build; sau khi user
  tự cấp quyền có thể thử lại mà không làm mất task. Không tự thay TCC.
- Khi app nguồn hỗ trợ AX: chỉ selected text của phần tử/ancestor hợp lệ, giữ
  source PID, timeout/cancel, max length, secure field guard. Range geometry lỗi
  không hủy chữ; app đổi trước capture là lỗi riêng. Source content là data,
  không làm theo câu lệnh nằm trong selection.
- Chuẩn hóa error từ native adapter → `capture_text` → service → worker →
  controller → UI/journal: `permission_required`, `source_changed`,
  `selection_unavailable`, `empty_selection`, `too_long`, `timeout`,
  `cancelled`, `internal_error`. Mỗi lỗi có một recovery đúng; lưu code trong
  journal whitelist, không lưu exception chứa nội dung. Audit thực tế API trả
  lỗi trước khi gán code, không biến mọi AX error thành unsupported.
- Selection failure phải hiện ở current Space, không mất vì ngoài click ngay
  lập tức. Preserve prior task/source/draft và có quay lại. Current source có
  sticky notice và nút Dán chữ chủ động; review lifecycle, trạng thái clipboard
  rỗng/oversize và UI layout trước khi tuyên bố xử lý xong.
- App không expose selection: user có thể **copy có chủ đích → Dán chữ**, hoặc
  chọn vùng OCR khi thích hợp. Không mô phỏng ⌘C, thay clipboard, đọc toàn văn
  field/document, hay lách các bề mặt có quyền truy cập bị hạn chế. Capture và
  translation của fallback vẫn là shared tools với provenance chính xác.

## 6. CoT/Agent và Workbench phải nối thật

| Lớp | Việc cần hoàn thiện | Bằng chứng cần nhìn thấy |
| --- | --- | --- |
| Input/context | Explicit intent, PID, capture ref; phân biệt source/result/selected span và revision | Invocation → capture artifact/ref/hash; lỗi riêng khi ref hết hạn. |
| Route/plan | Default dịch chỉ khi action dịch đã được gọi; hỏi tiếp và multi-step qua MiniSession/router/service | Controller decision/plan public, tool name/args an toàn, không giả model run. |
| Execute | Shared dispatcher, bounded budget/cancellation; không xử lý nghiệp vụ riêng QML | Execution id, observed artifact/status và completion từ service. |
| Verify/stop | Capture hash/mode, source/result binding, segment coverage hoặc verifier phù hợp; partial/needs-input không thành pass | Verification reports và stop/completion; phân biệt cấu trúc với đúng nghĩa. |
| Projection | Bubble, inline, Workbench chiếu cùng task state và public trace | UI cho thấy đúng output và failure, không private reasoning hoặc step giả. |
| Model loop | Chỉ opt-in; multi-step dùng các tool thực sự có trong profile | Một run thật có model identity/calls, public steps, observations, verification, status và loại cost. |

Current `.28.1` source mới có initial Workbench projection và result-revision
capability. Nó chưa chứng minh transcript/context packing hoàn chỉnh, live Agent
planning hay UI acceptance. Không thêm code diff, document QA, rename/delete
hoặc auto-apply chỉ để lấp concept UI. Organizer tiếp tục explicit preview/apply/
undo và approval pin.

## 7. Phân kỳ reviewable

1. **Diagnosis và contract:** inventory chord, event timeline và activation paths;
   chuẩn error codes, nguồn pin và visibility states. Không thay nguồn làm việc
   hoặc cài đặt hệ thống.
2. **Window/Space:** native collection behavior, passive show, activation có chủ ý,
   giữ one-window/one-task, sửa gập/ẩn/recall và focus. Commit riêng.
3. **Shortcut:** recorder/validation, native protocol, conflict messaging, transactional
   rollback và stored settings migration. Commit riêng.
4. **Capture/recovery:** AX reason propagation, permission/context/fallback, error
   UI và journal whitelist; không bypass app nguồn. Commit riêng.
5. **Reasoning continuity:** service route, artifact/output ref, verification,
   task public turns, Workbench public projection và partial state; không fake CoT.
6. **Đóng gói/đối chiếu:** build identity/metadata/helper cùng bundle, preserve
   phiên bản recovery, note đúng binary. Các commit nhỏ và normal push main theo
   ủy quyền RAT Lite; giữ mọi thay đổi unrelated.

Hoàn thiện source trước verification. Plan này không tự cho phép chạy test/build,
chụp ảnh/quay video hay UI acceptance trong lượt hiện tại; thực hiện khi người dùng
đề nghị rõ. Người dùng đã có preference tự vận hành app khi mở bản thử.

## 8. Ma trận nghiệm thu cho lượt được yêu cầu

- **Space:** Space A đang chứa RAT, Space B đang chứa app nguồn; shortcut ở B →
  B vẫn active, RAT xuất hiện trên B. Tiếp tục click input rồi Esc; vẫn ở B.
  Lặp với app bình thường/full-screen, nhiều display, tray recall và popup sở hữu.
  Không đổi Space khi lỗi, đang busy hoặc completion bị ẩn.
- **Chord:** default/custom, phát hiện chord macOS/third-party đã chiếm, migration,
  rollback success/failure, press/release và restart helper. Quan sát sự kiện thực,
  không chỉ handshake. Không cần đổi system preferences để làm RAT pass.
- **Capture:** TextEdit + app browser hỗ trợ AX + app user báo ChatGPT/Codex nếu
  bề mặt cho phép; missing TCC, app source đổi, empty/protected, unsupported,
  too long, bounds unavailable. Không dùng workaround để vượt restriction.
- **Execution:** selection → captured ref → tool observation → verifier → public
  output; provider failure và partial giữ source. Thử hỏi tiếp ràng buộc source,
  sửa result pinned, task mới không dùng stale source, stale ref và cancellation.
- **Agent:** khi có opt-in/credentials thực, một goal multi-step thật với trace
  công khai và status/usage. Nếu không có thì báo chưa kiểm chứng, không thay
  bằng canned answer. UI test dùng prompt/public response thật.
- **Usability:** lỗi luôn hiện/recover, head đủ lớn, no Copy CTA, long reader,
  draft/context/pin/history, Workbench và Organizer approval riêng. Ảnh/video
  khi user yêu cầu phải là app thật, chỉ ra cả lỗi quan sát, không là mockup.

Xem lại 4 lỗi trong batch cũ, phân biệt assertion đã lỗi thời với regression và
thiếu deps; sửa kiểm tra có ý nghĩa, không xóa failure để làm xanh. Khi test được
cho phép, báo chính xác các case pass/fail/chưa chạy. Research Stage0, M3 và main
integration không được coi là hoàn tất bởi local app acceptance.

## Source implementation follow-up

User requested immediate fix after this plan. Source commits set the RAT native
window collection policy to join Spaces / auxiliary full screen before presenting
or focusing, fail closed if that policy cannot be configured, and record a
bounded active-Space-change notification around an explicit shortcut invocation.
They add optional ⌥⇧R/K/J presets while preserving the stored chord and existing
transactional rebind, and distinguish AX permission, empty selection and source
unresponsive errors. Earlier source added persistent selection error/recovery.

Capture/translation continue through the common dispatcher and verifier; these
changes do not prove that a model Agent loop ran. The existing source Workbench
is still an initial projection. This is not acceptance evidence: no build,
execution, native Space inspection, test, real selection or live model request
was run for these source changes. The running bundle remains the earlier .28.
In particular, whether this policy fixes the user's Space switch, and the cause
of the user's captured-text failure, remain unknown until the built app is used.

## Requested self-check: 2026-10-29

Built `dist/rat-lite-20261029-space-fix/RAT Mini.app` from source `a30f1a06`
with the existing `/private/tmp/rat-mini-offline-mt-deps`; launched build
`20261029.28.1` (PID 93866, helper 93877). Helper journal reported registered
and READY; no Space policy failure was logged during startup. This is not
proof of Space behavior.

With the real UI, typed `Dịch: The little rat is reading this sentence.` and
pressed Return. The app reported translate_text execution and displayed the real
answer `Con chuột nhỏ đang đọc câu này.` This verifies that one typed request
and its response worked in this build, not selection or Agent planning.

In a separate disposable TextEdit document, selected that sentence and sent
`alt+shift+space` twice via the computer-use keyboard API. Both attempts inserted
a nonbreaking space into the test document; the helper journal recorded no
selection invocation. This shows the simulated input did not activate RAT; it
cannot establish how a physical keyboard behaves. The source was a disposable
file, not the user's already-open document. No valid two-Space outcome was
obtained because the trigger did not reach the helper.

Offscreen test batch with the existing ctranslate2 dependency: 9 passed,
3 failed (`test_look_standby_hides_composer_and_preserves_draft`,
`test_copy_only_queues_and_explicit_open_uses_real_workflow`,
`test_mini_quick_layout_and_import_boundary`). The first/third contain older
layout expectations; the second must be investigated individually. None of
these results establish live shortcut or Space acceptance.

Status: shortcut and Space bug remain unverified; the earlier .28 journal had
shown physical shortcut events but capture failed. No fake response, model loop,
or successful capture claim is substituted for this missing evidence.

## Physical invocation evidence and next Hello

After the user retried on the built `20261029.28.1`, two invocations reached the
helper and shared capture, which returned `selection_accessibility_required` for
the running RAT process. System Settings showed an enabled `RAT Mini.app` entry,
but that does not prove the running bundle is trusted. The running .28.1 and the
older .28 bundle are ad-hoc signed with distinct designated cdhashes; `security
find-identity` reported zero valid code-signing identities. The entry's exact
association was not determined. No TCC or System Settings permission was changed.

The observed RAT error window displayed only its Quick Look heading while the
error existed in the accessibility tree. Source now gives the notice/preview
sufficient layout height so the message and recovery controls can appear. This
layout correction is not yet verified in a new bundle.

At the user's request for the next version, source also adds a one-time Hello
revision. It runs the shared `check_mini_readiness` operation in the application
process, explains the Accessibility permission for selection, shows a button to
open the permission pane and reveal the exact running bundle in Finder, and
requires a successful recheck before completing setup. Screen Recording is
explained separately as needed for region capture, not for pasted text/images.
No permission is granted by the UI itself. Existing settings trigger this new
Hello once; the version marker persists after completion. Source changes and
Hello have not yet been built or acceptance tested. A prompt/visible on toggle
is not evidence that the current app process has acquired permission.
