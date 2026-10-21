# RAT Workbench: visual and interaction handoff

Date: 2026-10-15. Status: **selected design direction, interactive prototype only**.

Source: `/Users/thundercock2/.codex/visualizations/2026/10/14/01a138f6-57e2-71d2-8bb3-579da2083201/rat-workbench-dialogue.html`.

The prototype uses local keyword matching and an 850 ms timer. It does not call a
model, operate on personal files, or demonstrate measured runtime performance.
The native Qt UI and runtime are unchanged. This document records the prototype
and explicitly identifies requirements that still need native implementation.

## Intent and hierarchy

The selected direction is **compact, separate compartments with aligned edges**.
It supersedes the earlier opaque shared-shell variant. A transparent workbench
layout contains three distinct roles, in this reading order:

1. **Canvas:** the current work artifact, with title, content and factual status.
2. **RAT dialogue:** a short response in a paper-colored speech bubble, beside RAT.
3. **User dialogue:** the editable, green-tinted speech bubble at the bottom.

The bordered canvas contains the work and the quiet brand chrome. Speech explains,
asks or acknowledges outside that card. Long results belong in the canvas. RAT
speech and the user bubble share a right edge and, on desktop, a left edge. Tight
spacing, related colors and matching type make the compartments feel connected.
The user lane is outside the RAT stage. Expanded reading shows the latest submitted
utterance above the composer with “Bạn vừa nói”, separate from RAT speech.
No tool, feature, send or workflow buttons are added. Enter submits the same
composer throughout. The prototype's optional host `Tweak` controls are design
preview controls and are not part of the product interface.

## Compact first: selected default

Compact mode retains the artifact DOM and bottom composer. Its transparent outer
layout has maximum width **520px**; expanded reading mode is **640px**. There is
no enclosing border, opaque background, corner radius or shadow around the app.
Height follows content, input growth and text scaling; there is no hard fixed
height guarantee. Footprint measurements must identify mode, sample and viewport.

| Compact component | Actual override |
| --- | --- |
| Chrome inside canvas | Padding `2px 0 6px`; brand 18px/1.15; no extra caption |
| Canvas | Paper fill, 1px border, radius 16px, shadow `0 5px 18px`; padding `8px 16px 5px`; eyebrow and work footer hidden; title 20px/1.3; heading bottom margin 3px |
| Plan | Columns `20px / flexible / auto`, gap 10px, row padding 5px; titles 14px/1.5, minutes 12px; secondary descriptions hidden |
| RAT stage | Outside canvas, transparent; columns `112px / flexible`, gap 8px, no padding, top margin 8px; actor slot 112 × 82px; artwork 104px |
| RAT speech | Padding `9px 12px`, corners `14px 14px 14px 5px`; 13px/1.6; tail top `min(28px, calc(100% - 22px))`; wrapper top padding 5px |
| User lane | Transparent, left padding 120px (`112px + 8px`), no other padding; bubble aligns with RAT speech; bubble padding `9px 13px`, corners `14px 14px 5px 14px` |
| Input footer | Margin-top 9px; 12px text, gap 8px; secondary keyboard hint hidden |
| Role/history labels | Speaker labels visually hidden but accessible; latest submitted utterance hidden in compact, retained for expanded reading |
| Other sample content | Calculation result 30px; file icon 33 × 40px; only first note paragraph visible; expansion reveals retained note details |

Plan rows are concise rather than forcibly clipped: unusually long titles may
wrap. Completed RAT speech uses a shorter variant, e.g. “Xếp xong 90 phút rồi.
Bạn muốn đổi phần nào?”. Clarification and error speech remains readable.

At viewport widths ≤450px: chrome remains `2px 0 6px`, canvas `8px 14px 5px`, title
18px, plan columns `16px / flexible / auto` with 7px gap; stage columns
`84px / flexible`, gap 7px, no padding; actor slot 84 × 88px and artwork
80px; user lane has zero padding and a full-width composer; input footer wraps. Input otherwise inherits
15px desktop / 16px at viewport widths ≤620px; the height and 2000-character limits
remain unchanged.

Exact normalized view commands “xem chi tiết” / “thu gọn” run before task submit;
aliases include “chi tiết”, “mở rộng”, “đọc đầy đủ” / “gọn lại”, with optional final
period/exclamation. They consume their command text, persist `expanded`, and
change presentation without cancelling the active timer, changing artifacts or
adding a user turn. The footer discloses “Nói ‘xem chi tiết’” or “Nói ‘thu gọn’”;
while working it instead shows “Gõ tiếp · Esc để dừng”, and at 1700 characters the
counter takes precedence. The optional host expanded toggle is preview-only.
The native bottom-anchor behavior below remains a requirement, not a browser
window-management claim.

## Expanded reading: layout and components

Measurements below are CSS pixels in the source prototype. A Qt port must use
logical pixels and preserve the proportions at the OS display scale.

| Component | Expanded geometry and role; compact overrides above take precedence |
| --- | --- |
| Root | Full available width; outer padding `16px 14px 28px` |
| Workbench | Maximum width 640px, centered, no padding; transparent, no outer frame or shadow; natural content height |
| Quiet chrome | Inside canvas; brand left, mode right; caption hidden; gap 24px; padding `6px 0 16px` |
| Canvas | Paper fill, 1px border, 18px radius, shadow `0 5px 18px`; padding `12px 28px 0` |
| Canvas heading | Title block and duration badge; gap 20px; bottom margin 12px |
| Plan row | Columns `27px / flexible / auto`; column gap 16px; 16px vertical padding; baseline alignment |
| Canvas footer | Top rule; `12px 0 14px` padding; left status and right context; plan context “3 phần”; gap 12px |
| Dialogue stage | Transparent outside canvas; columns `144px / flexible`; gap 8px; no padding; margin-top 12px; top aligned |
| RAT slot | 144 × 150px; independent of speech size; no text or input overlays the artwork |
| RAT dialogue wrapper | Flexible width; top padding 4px; contains RAT speech only |
| RAT lane | Left aligned; maximum width 460px; speaker label above bubble |
| User lane | `display:flow-root`; transparent; padding `0 0 12px 152px`, aligning with speech (`144px + 8px`); right-aligned “Bạn” label |
| Latest user utterance | Margin `4px 0 12px 60px`; right aligned; wraps rather than ellipsizes |

The host background can show between the canvas and speech compartments. Do not
reintroduce a shared opaque stage or outer frame. Canvas and speech retain their
own boundaries; brand chrome is contained within the canvas rather than floating
above it.

**Bottom anchoring:** the user bubble is always the final interaction region.
The HTML prototype is in normal document flow, not viewport-fixed. A native
implementation must keep the composer at the bottom of the usable window and
allocate overflow to the upper work/reading area. Input growth up to its height
limit must consume space above it; it must not push the composer offscreen.
Preserve reading position when the user has scrolled away from the current work.

## Tokens and typography

Use the source token names when porting, rather than introducing per-widget colors.

| Token | Light | Dark | Purpose |
| --- | --- | --- | --- |
| `--wb-paper` | `#fffefa` | `#272a25` | Canvas and RAT speech |
| `--wb-ink` | `#30382f` | `#eeeee6` | Primary text |
| `--wb-muted` | `#616b5c` | `#b5bbae` | Supporting text |
| `--wb-line` | `#e4e7dc` | `#42483c` | Rules and paper borders |
| `--wb-soft` | `#f2f3eb` | `#33392d` | Context badge and notes |
| `--wb-stage` | `#f6f7f0` | `#2b3027` | Declared but unused by the selected transparent stage |
| `--wb-user` | `#e9eedf` | `#35402c` | User speech and illustrative prop |
| `--wb-user-line` | `#d4ddc7` | `#566649` | User speech border |
| `--wb-accent` | `#536b3f` | `#bdd39f` | Small accents and status dot |
| `--wb-focus` | `#738d5b` | `#b4ce93` | Focus outline |
| `--wb-shadow` | `#34412b12` | `#00000034` | Canvas shadow, offset `0 5px`, blur 18px |
| `--wb-floor` | `#64725220` | `#00000045` | Ground beneath RAT |
| `--wb-error` | `#984a3a` | `#edb4a4` | Error speech |

Spacing tokens `--wb-s0` through `--wb-s5` are `4, 8, 12, 16, 24, 32px`.
`--wb-density` defaults to 1; its preview range is 0.85–1.25 and scales expanded canvas
top padding (12px base) and plan-row padding. Compact overrides use fixed padding.
It is not a product control.

Font stack: `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif`.
Use a matching installed system family in Qt. No web font download is required.
Keep Vietnamese combining marks and accented capitals unclipped; do not use
fixed text heights. Use tabular numerals for durations, order and calculations.

| Text role | Expanded size / weight / line height; compact overrides above |
| --- | --- |
| Base | 15px / 400 / 1.55 |
| Canvas title | 24px / 500 / 1.35; tracking −0.5px |
| Plan title | 15px / 500 / 1.5; tracking −0.12px |
| Plan description | 13px / 400 / 1.6 |
| RAT speech | 14px / 400 / 1.65 |
| Composer | 15px / 400 / 1.65; 16px at widths ≤620px |
| Labels, footer, keyboard help | 12px; normal tracking except eyebrow +0.7px |
| Latest user utterance | 13px / 400 / 1.55 |
| Calculation result | 38px / 400 / 1.3; tracking −1px; unit 15px |

## Speech shapes and input

- RAT bubble: paper fill and 1px paper border; corners `18px 18px 18px 7px`;
  padding `14px 18px`. Tail is an 11 × 11px paper-colored shape at left −6px,
  top `min(42px, calc(100% - 28px))`, with left/bottom border, 3px lower-left radius,
  `skewY(-14deg) rotate(32deg)`. It points left toward RAT.
- User bubble: green fill and 1px user border; corners `18px 18px 7px 18px`;
  padding `14px 18px`. Tail is 12 × 12px at right 22px, bottom −6px, with
  left/bottom border, 3px lower-left radius, `rotate(-45deg) skewY(-8deg)`.
  It points downward toward the user. Tail must not be clipped by the layout.
- Speaker labels sit 6px above their bubble, inset 16px. “Chuột” aligns left;
  “Bạn” aligns right. Do not put status or RAT replies in the input footer.
- Composer has no internal border, no resize handle, no send button. Empty
  placeholder: “Bạn muốn làm gì tiếp?”. It grows from 28px to 104px, then scrolls
  internally. The prototype limits input to 2000 via HTML `maxlength`; a counter
  appears at 1700 characters. The full submitted utterance is retained up to the
  same limit, with no separate shorter history truncation.
- Focus accents the containing user-bubble border, including its tail, and adds a
  soft 3px outer halo using 16% focus color. The textarea has no separate inner
  outline: the composer has one coherent focus indication.
- Footer is 13px below the bubble, with input state left and keyboard hint right.
  No hover decoration is specified for static canvas content or speech.

Enter submits; Shift+Enter inserts a newline. Enter during IME composition does
not submit. Escape cancels while working; the composer retains focus. Standalone
“dừng”, “thôi”, “stop”, “hủy” with optional final period/exclamation also cancel.
Whitespace-only input does nothing. Input remains editable while working.

## States and simulated interactions

| Phase | Speech/status and canvas behavior |
| --- | --- |
| `done` | Brief result acknowledgement; footer “Có thể chỉnh tiếp”; current artifact remains |
| `working` | “Mình đang điều chỉnh. Phần đã làm vẫn ở đây để bạn xem tiếp.”; muted dot; input footer “Có thể gõ tiếp · Esc để dừng” |
| `question` | One clarification in RAT speech; footer “Cần thêm một ý”; same composer |
| `error` | Warm error-colored speech; footer “Còn một bước chưa xong”; completed work remains |
| `cancelled` | RAT acknowledges stop; footer “Đã dừng”; work remains |
| `empty` | Canvas title “Mình bắt đầu từ đâu?” and short invitation; no duration badge; footer “Sẵn sàng cùng bạn” |

The local demo switches among plan, fixed calculation, illustrative file and
illustrative note using keywords. “đổi … ôn tập” edits plan row 3; “thêm N phút”
adds to its duration up to 240. These are simulation rules, not supported native
capabilities. The sample file says it is illustrative and has no opening action.

Submitting again during the demo's working state replaces its timer and retains
only the latest submitted utterance. This does **not** establish native steering
or cancellation semantics. Widget state restores the draft, selected sample and
values; an initially restored interrupted `working` state becomes `cancelled`.
Each mounted instance includes a writer identifier and ignores its own state
echoes, so host echoing does not cancel active work. Native conversation persistence
remains a separate runtime concern. Draft and submitted utterance both retain up
to the same 2000-character limit.

## Expanded responsive rules

| Width | Changes from desktop |
| --- | --- |
| ≤620px | Root padding `12px 8px 20px`; chrome `4px 0 14px`; canvas `12px 20px 0`; title 22px; plan columns `22px / flexible / auto`, gap 10px, row padding 14px; stage columns `104px / flexible`, gap 8px, no padding; actor slot 104 × 140px and artwork 100px; speech padding `12px 14px`; user lane `0 0 12px 112px`; composer footer wraps |
| ≤450px | Canvas heading wraps, duration moves below title; plan minutes move to column 2 below text; stage remains a transparent grid with actor column `clamp(64px,18vw,80px)`, gap 8px, no padding; actor slot 122px high, artwork fills column width; RAT lane full dialogue-column width; bubble radius `16px 16px 16px 6px`, padding `12px 13px`; full-width user lane `0 0 12px`; user bubble padding `15px 16px`; latest utterance left margin 20px; secondary keyboard hint hidden |

Wrap long titles, filenames, speech and descriptions, including unbroken strings.
No essential text is ellipsized in the prototype. Long input scrolls only after
104px. Long work content must scroll above the bottom composer in native Qt.
Test narrow windows with enlarged system fonts; the 64–80px actor must not cover
speech. Do not show fake duration/source metadata when that field is absent.

## Artist anchors and motion

Compact anchors: artwork 104px at left 0/top −1px (`bottom:auto`), ground
82 × 7px at left 10px/bottom −28px, prop 26 × 32px at left 78px/bottom 8px.
The artwork extends into the free space to the left of the desktop composer.
At ≤450px artwork is 80px at top −1px (`bottom:auto`), ground 62 × 7px at left
6px/bottom 2px, prop 21 × 26px at left 58px/bottom 27px. The following larger
anchors apply to expanded reading.

Default artwork uses `--wb-actor-size:132px`, at actor-slot left 0/bottom 4px, with transform
origin 55%/88%. Ground is an ellipse 108 × 9px at left 10px/bottom 0. The sample
prop is 30 × 37px at left 100px/bottom 37px, rotated 7°; it changes icon by sample.
At ≤620px artwork is 100px, ground 78px wide/left 8px, prop 26 × 32px at left
72px/bottom 31px. At ≤450px artwork fills the actor column at bottom 12px;
ground is 80% wide/7px high at left 6px/bottom 10px; prop is 22 × 28px at
left `calc(100% - 24px)`/bottom 32px. These anchors are not final animation art.

Keep feet, mouth/tail direction, hand/prop attachment and readable silhouette
stable across future idle/thinking/asking/carrying/error clips. Scale the whole
character anchor set together. Artwork is noninteractive; decorative props must
not intercept composer input or obscure content.

| Trigger | Prototype motion | Duration / easing |
| --- | --- | --- |
| Submit and simulated completion | RAT rises 7px, rotates −3°, returns | 520ms, `cubic-bezier(.22,.7,.3,1)` |
| Same triggers | Plan row 3, or other canvas content, rises from +4px while soft highlight fades | 360ms, `ease-out` |

Both animations are skipped when reduced motion is preferred. No continuous
idle loop, typing dots, entrance sequence, pan/zoom or drag gesture is implemented.
The native version should animate only genuinely changed regions; the demo's
fixed row-3 highlight is not a general artifact-diff implementation.

## Accessibility and native acceptance

The source has explicit canvas, actor and composer labels. RAT speech is a polite,
atomic live status. Preserve a sensible reading order: canvas, RAT speech, last
user utterance, composer. Decorative artwork/props should not become separate
keyboard stops. The composer is the only input in this prototype; real file rows
must be keyboard operable and labeled once implemented. Announce a state change
once, not separately from every visual status label. Verify contrast, focus and
200% text scaling on the actual Qt build; no compliance result is claimed here.

Native handoff is complete only when UI state derives from existing, scoped
runtime records rather than the prototype timer:

- Bind submitted speech, draft and last utterance to the actual conversation and
  execution identity; ignore stale completions from an older generation.
- Bind canvas blocks and edits to real artifact IDs/revisions. Preserve scroll,
  selection and unaffected blocks when an artifact changes.
- Drive working/question/error/stopped/finished states from actual execution,
  pending-request and reconciliation events. A final sentence alone must not
  turn an incomplete operation into a completed canvas.
- Require a successful current-scope tool receipt and existing local path before
  showing a file as delivered or animating RAT carrying it. Opening must use that
  observed path; missing/stale files need an explicit unavailable state.
- Preserve completed artifacts and drafts on error/cancel. Do not imply transport
  cancellation or mid-run steering until those native behaviors are implemented.
- Check plan, calculation, real-file, note, empty, long-text, clarification, error,
  cancel and slow-execution journeys at desktop and narrow widths. Record native
  screenshots plus event/artifact evidence; a browser replay is not a live Qt run.

This design changes no model defaults, research harness, research claims, Stage 0
gate or DocAI integration. No Git publication is part of this handoff.

Fourteen browser interaction/layout checks passed with zero JavaScript errors.
Coverage includes widths 1024, 736, 620, 450, 390 and 320px; canvas/speech alignment;
plan-row DOM identity; busy drafts; retained work on clarification/error; no late
callbacks after cancel; long Vietnamese input; dark mode; and reduced motion.
View-only commands retain the plan DOM and do not stop the running simulation.
Earlier shared-shell screenshots and measurements are superseded. These are local
prototype checks, separate from native Qt behavior and model quality.

Measured in the browser preview at an 800px host viewport, the default plan
Workbench composition is **520 × 335.06 CSS px**. This excludes the surrounding
preview padding. This is a specimen measurement, not a fixed height for all
content or a native-window screen-area measurement.
