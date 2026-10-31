# RAT Mini Look — handoff 2026-10-28

Latest delivered build: .15, `dist/mini-speech-20261028-large-corner-final/`.
User requested continuing acceptance and enlarging the seated Look rat. Host is
96×100 with seated optical target 86; head stays 36. Native .13/.14 idle/Clipboard
evidence and the .15 explicit-recall repair are recorded in
[larger-corner report](../audit/rat_mini_speech_20261028/large-corner/README.md).
31 size/Look checks passed, then bounded recall/auto-hide checks. Queue/long-read
native acceptance remains open; do not infer it from passing software checks.
QA processes stopped and user's original .8 session preserved.

Latest source is now [shared speech handoff](rat_mini_speech_handoff_20261028.md),
planned .10. User authorized a reusable SpeechBubble/MascotPose/shared placement
implementation. .9/.10 remain unbuilt and untested; .8 is the last opened bundle.

Current unbuilt source follow-up: .9 compact/transient Look, documented at the
top of `docs/rat_mini_look_clipboard_20261028.md`. User requested smaller,
unobtrusive UI that disappears automatically. Whole overlay hides after five
seconds without engagement, retains the result, and may reappear on the next
copy while Look remains enabled. No new tests/build/launch for .9.

Latest source continuation: [Look Clipboard flow](rat_mini_look_clipboard_20261028.md).
Later asset clarification: Look errors use the user-selected seated error rat,
including short errors. The added gestures sheet and other error references are
saved in the mascot backlog. Source wiring only; no new build or acceptance.
The user authorized automatic response to new copied text while Look is enabled,
then requested completing the full Look flow. The .8 source wires that flow and
disables Mini LLM use by default behind an explicit Advanced opt-in. This
supersedes the earlier pending-Clipboard and standing-busy notes below. No .8
build, launch, tests or live acceptance; .7 remains the prior bundle.

## Later user selections in continuation

User reaffirmation: this work is on RAT Mini as a proof of concept for main RAT.
Mini is the reusable vertical slice of the same RAT–CoT system. Plan and implement
Look, Clipboard ingress, routing, execution, verification and presentation with
reuse in main in mind. Mini acceptance does not itself enable main integration;
report the two states separately. This reaffirmation does not authorize tests or
change research claims/Stage 0.

- The user specified the screen corner for the seated Look indicator during
  long-content presentation; corner placement is still pending implementation.
- The upper-left head on `docs/design/rat-mascot-backlog-20261028/rat-head-expressions.png`
  replaces the short-result head in source as `rat_look_head_v2.png`.
- A separately supplied seated rat is selected for Look idle while waiting for
  the user, superseding the standing-only idle decision. Source wires
  `rat_look_idle_seated_v1.png` only for non-busy standby; busy keeps the standing
  mascot. The fixed 122×128 canvas is retained.
- The long-result reading surface now requests width 420 and height up to 380
  in source, still screen constrained. This is partial Wall presentation work.
- Clipboard trigger and near-text placement are not decided or implemented.

References and original images are retained in
`docs/backlog/rat_mascot_pose_references_20261028.md`. Extracted sprites are
image-generated adaptations, not pixel-identical crops. No tests, app launch,
screenshots or builds were run for these continuation changes; the .7 bundle
below predates them. Main integration/model acceptance/M3/Stage 0 stay open.

## Điểm tiếp tục

Người dùng đang dùng thử Mini và muốn lên kế hoạch tiếp. Yêu cầu mới nhất là
handoff, không phải cho phép phát triển/test tiếp trong lượt này.

Repo: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Đọc `AGENTS.md`, `docs/project_scope.md`, `docs/rat_mini_vertical_slice.md`,
`docs/rat_mini_m516_ux_plan.md`, `docs/rat_mini_m516_implementation.md` và tài liệu này.
`docs/rat_mini_look_modes.md` là lịch sử; các quyết định mới bên dưới thay thế
những đoạn cũ trái ngược.

Branch thực tế quan sát lúc handoff: `rescue/human-control`. Hướng dẫn người dùng
vẫn yêu cầu làm trên `main`; lượt này không chuyển/tạo branch. Cần đối chiếu trạng
thái Git hiện tại trước khi tiếp tục, giữ mọi thay đổi không liên quan; không tự
push/pull/reset hoặc chuyển checkout làm mất/lẫn thay đổi. Không suy ra rằng toàn
bộ thay đổi đang thấy thuộc lượt sửa Look.

## Hướng trải nghiệm mới — chưa triển khai

Người dùng nói: “floating head will respond near text that is copied to clipboard,
and then when it a wall of text we will change it to wall mode, and a rat will sit
in the corner to let us know it's look mode”.

- Nội dung ngắn: đầu Chuột nổi và phản hồi nhỏ gần đoạn chữ vừa copy.
- Nội dung dài: chuyển sang Wall mode, khung đọc đoạn dài cuộn được.
- Có Chuột ngồi ở góc để nhận biết đang trong Look. Vị trí góc màn hình hay góc
  khung và việc có giữ indicator trong cả hai trạng thái chưa được người dùng
  xác nhận riêng; không biến diễn giải của assistant thành quyết định đã chốt.
- Wall là cách trình bày nội dung dài trong Look; hệ workspace đã chốt là
  `look / minimal / single / full`. Chưa có quyết định thêm workspace thứ năm.
- Lúc chờ dùng sprite Chuột gốc đứng yên, giữ kích thước. Người dùng đã chốt
  trước đó C cho 1–2 từ/câu ngắn, B cho đoạn; chưa dùng A.

Assistant đề xuất đặt phản hồi gần con trỏ tại thời điểm gọi vì Clipboard thường
không có tọa độ nguồn chữ, rồi né mép màn hình. Assistant cũng đề xuất luồng copy
→ gọi Look bằng phím, không theo dõi mọi lần copy. Đây là đề xuất kỹ thuật trong
tin trả lời cuối, người dùng chưa xác nhận riêng. Chưa triển khai đặt theo con trỏ,
auto-ingress Clipboard khi gọi, Wall mới, hoặc sprite Chuột ngồi ở góc. Không tự
bật clipboard watcher hay đọc liên tục chỉ từ mô tả này.

## Bản vừa build và gửi lệnh mở

- App: `dist/mini-look-20261028-repair/RAT Mini.app`.
- ZIP: `dist/mini-look-20261028-repair/RAT Mini.zip`.
- Version: `0.5.17`, build `20261028.7`.
- Build hoàn tất; script ký ad-hoc và tạo ZIP. Không tuyên bố notarized.
- Đã chạy `open -n` với đường dẫn app trên, lệnh trả mã 0. Không đọc UI/log sau
  launch để xác nhận cửa sổ hoặc binary thực tế đang chạy; bridge single-instance
  có thể gọi lại instance cũ nếu cùng state đang hoạt động. Không claim live
  acceptance hoặc mọi sửa đổi đã hoạt động chỉ từ lệnh mở.
- Không chạy test suite, smoke, tour UI, chụp screenshot hoặc lượt model thật
  trong lượt build/mở. Người dùng chưa báo kết quả acceptance từng chức năng.

Build lần đầu thiếu metadata ctranslate2; lần sau sandbox không thu thập Qt Cocoa
plugin. Build cuối ngoài sandbox đã thành công với deps tạm:

```bash
RAT_MINI_SPIKE_DEPS=/private/tmp/rat-mini-repair-deps:/private/tmp/rat-mini-offline-mt-deps \
RAT_MINI_DIST_DIR="$PWD/dist/mini-look-20261028-repair" \
zsh tools/build_rat_mini_app.sh
```

`/private/tmp/rat-mini-repair-deps` chứa sentencepiece 0.2.2, cài riêng phục vụ
build; không cài vào môi trường repo. Log: `/private/tmp/rat-mini-look-repair-build.log`.
Deps/log tạm có thể hết hạn, không xem chúng là nền tái lập lâu dài.

## Source đã sửa trong bản .7 — cần người dùng xác nhận

- `LookSurface.qml`: sprite C/B riêng thay crop rời, bubble thu gọn, scroll đoạn
  dài, bỏ tooltip che chữ. Copy truyền chính `speech.text` đến controller.
- Sprite: `rat/assets/rat_look_head_v1.png`, `rat/assets/rat_look_peek_v1.png` được
  generate dựa trên Chuột gốc và concept B/C. Chưa được người dùng chấp nhận;
  standby dùng `rat_mascot_cutout.png`. Chưa phải sprite Chuột ngồi của hướng mới.
- `mini_presentation.py`: chọn C/B theo độ dài; ưu tiên kết luận Agent nếu có;
  thông báo ngắn nếu đoạn đã cùng ngôn ngữ đích; copy theo nội dung thật đang hiện.
- `mini_quick_controller.py`: `copyLook(str)`; chọn vùng qua menu/tray; giữ task,
  OCR, preview và draft cũ cho đến khi capture thành công; khôi phục khi hủy trước
  capture. Capture dùng MiniSession tạm cùng artifact store, sau capture nhận
  session đó làm phiên hiện tại để tiếp tục clarification/dịch. Draft composer
  độc lập. Các hành vi này là source intent, chưa được xác nhận live.
- `snippet_translation.py`, `capture_translation.py`, `mini_worker.py`,
  `kernel/input_context.py`, `kernel/capabilities/translation.py`: region qua
  `capture_text → translate_text`, provenance `screen_region`, giới hạn 12 MB /
  25 triệu pixel; giữ ảnh trong memory để xem lại qua callback trusted context.
  Không gửi pixels vào model/tool args hoặc lưu trong artifact. Verifier kiểm
  tra cấu trúc/hash, không xác nhận nghĩa OCR/bản dịch.
- `mini_shell.py`: không tự present khi capture hoàn tất; phục hồi cửa sổ nếu
  thay window flags làm ẩn cửa sổ vốn đang active. Chưa xác nhận focus thật.
- `tools/rat_hotkey.c`, `rat/os/mini_hotkey.py`: **tap ⌥⇧Space → Look; hold ít
  nhất 0.5 giây rồi thả → Minimal**, protocol `HOLD2` để từ chối helper cũ. Menu
  đồng bộ. ⌥Space thuộc Spotlight; ⌘V là paste. Không dùng quyết định đảo ngược
  trong lịch sử. Độ ổn định phím thật ở bản .7 chưa được xác nhận.
- `mini_cloud.py`, `mini.py`, `execution_service.py`: telemetry đếm request và
  response riêng; `is_live_model` cần model response ở model-loop; event hoàn tất
  phản ánh completion status. Nhánh Agent dùng runtime/service/dispatcher chung,
  chưa có lượt model thật được xác nhận. Tool dịch xác định không tự chứng minh CoT.
- `mini_quick.py`, `MiniDesk.qml`, `mini_placement.py`, build script: wiring assets,
  menu chọn vùng, anchor mascot ổn định và version .7. Một assertion placement
  trong `tests/test_rat_mini_look.py` đã chỉnh, chưa chạy.

## Cách tiếp tục

1. Bắt đầu từ hướng mới ngắn/dài và indicator Chuột ở góc; phân biệt yêu cầu người
   dùng với đề xuất vị trí con trỏ/trigger chưa được xác nhận. Ưu tiên ít chrome,
   kích thước nhỏ, không input trong Look, không tự thiết kế lại Minimal.
2. Khi người dùng yêu cầu làm tiếp, đọc source liên quan và sửa toàn bộ lượt trước
   khi kiểm chứng; mọi nghiệp vụ đi qua reasoning tools/service/dispatcher/verification.
3. Người dùng tự thao tác và gửi nhận xét. Chỉ build/mở khi được yêu cầu; không
   tự chạy suite, smoke, UI tour, screenshot hoặc chuỗi retry. Lượt cho phép
   build/mở vừa rồi không cấp quyền kiểm thử chung cho tương lai.
4. Xác nhận model thật là mục riêng: cần lượt yêu cầu thật, public answer, tool
   observations, verification, completion status và telemetry; không thay bằng
   fixture/canned result hoặc bộ đếm. Chưa chạy khi chưa được yêu cầu kiểm chứng.

Mini vẫn là indev vertical slice dùng lại cho RAT chính; chưa nghiệm thu main UI
integration/M3. Không thay scope nghiên cứu hoặc Stage 0. Giữ một composer trong
Minimal, draft độc lập với yêu cầu cũ, OCR sửa được, đường Back rõ, giữ phiên khi
ẩn/gọi lại, background completion không giành focus.
