# RAT Lite .25 — explicit selected-text Quick Look

User decision 2026-10-29: skip the intermediate copy → shortcut design and
implement highlight → shortcut directly. Source-only, unbuilt and unverified.
The running .24 app does not contain this feature. No tests, smoke, UI capture,
permission changes, build or relaunch were performed for this implementation.

## Gesture and source boundary

⌥⇧Space now emits one SELECTION intent on key-down. Release clears the held-key
latch; holding does not select a different mode or submit again. Carbon helper
protocol SELECT1 replaces HOLD2. Python rejects old helpers; both helper and
Python must be packaged together. The chord stays the same. Compose/recall are
available through RAT menus and the existing UI rather than hold timing.

The controller snapshots only the frontmost source PID on the GUI thread before
RAT is presented. It passes the PID in trusted execution context, never model
arguments. Requests while another job/capture is active do not cancel that job.
Invoking while RAT itself is frontmost recalls the existing interaction instead.

`capture_text(mode=selection)` remains model-invisible and requires an explicit
user action. The shared tool calls `rat.os.selected_text.read_selected_text()`.
That adapter requires Accessibility trust, pins the source application, and reads
AXSelectedText from its focused element or up to three ancestors. Individual AX
messages use a 0.3-second timeout and cancellation is checked between calls.
Secure-text roles are rejected. It never reads whole-field AXValue, sends ⌘C,
reads/writes Clipboard or traverses the entire accessibility tree.

The source PID is checked again before returning text. Missing/empty selection,
changed app, missing permission and oversized text fail explicitly; there is no
fallback to old Clipboard contents. The current limit is 8,000 characters.
Unsupported applications may still need manual paste or image ingress. We have
not established support for Safari, Chrome, Preview, Word or any other app in a
native run for this source revision.

Apple references: [selected-text attribute](https://developer.apple.com/documentation/applicationservices/kaxselectedtextattribute?language=objc),
[AX messaging timeout](https://developer.apple.com/documentation/applicationservices/1459345-axuielementsetmessagingtimeout).
The selected-text attribute is required for editable text elements; this does
not guarantee support for every read-only document or browser selection.

## Shared execution and presentation

The worker uses the existing capture→artifact→source_ref→translate workflow,
AgentExecutionService, dispatcher, capture/translation contracts and verifiers.
Capture provenance says `source_kind=selection`; hash and source pin come from
the actual capture. This remains a deterministic tool path; no live model call
or model-planning evidence is added. Existing provider settings determine where
translation runs; bundled English↔Vietnamese stays under the current policy.

The current task/session is preserved until capture succeeds, using the existing
isolated capture session with the shared artifact store. On success it becomes
the current session, and explicit invocation allows showing the processing/result
surface. RAT is not shown before AX has read the source, to avoid taking away
its focus. Later translation completion cannot reopen a dismissed surface.

Capture failure restores the old execution/result state. A separate selection
notice explains the failure, with an explicit Accessibility Settings action
when required. Permission is requested/opened only by that button/menu gesture;
receiving a hotkey does not grant trust. After granting access the user returns
to the source and presses the shortcut again; no automatic background retry.
Recall clears the notice and restores the previous result. Drafts remain intact.

## Delivery and remaining work

Source build identifier is .25; the build script now explicitly collects
ApplicationServices. No new bundle exists yet. Physical shortcut latency,
native permission recovery, selection coverage, source-focus preservation and
actual translation remain unverified. Old mode/helper assertions in historical
tests will need aligning in a separately authorized verification pass.

This scope takes precedence over the proposed continuous-panel repair for the
current turn. That UX feedback remains unresolved; selection ingress does not
establish typing/reading/expansion continuity. Main integration, recipient M3 and
Stage 0 remain gated. All future domain work still uses shared reasoning tools.
