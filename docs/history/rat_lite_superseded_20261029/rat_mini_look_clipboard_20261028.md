# RAT Mini — complete Look flow, source revision 20261028.8

## Compact transient follow-up — source 20261028.9

User feedback prioritizes making Look smaller, unobtrusive and automatically
disappearing. Only source changes in this follow-up; no build, test, launch,
screenshot or resource measurement. The .8 bundle below predates these changes.

- Look canvas is 80×84, with the short-response head in a 56×60 image box;
  other workspaces keep their existing mascot dimensions. Short speech requests
  88–196 width and a minimum 44 height, with compact text padding and side actions.
  Long reading requests 340 width and up to 300 height. Actual optical scale is
  still subject to native/user review, including source asset transparent padding.
- The listening dot moves next to the small character's lower edge. Idle help
  text appears on hover instead of always occupying the corner.
- After five seconds without interaction, hide the entire Look overlay, including
  the idle character. Hover, scrolling/dragging text and owned menus pause the
  timer; leaving restarts the interval. Running work suspends automatic hiding.
  Copy/close/Esc hides immediately through the same retained-result state.
- Automatic hiding preserves the enabled watcher. A newly accepted copy may
  show the passive overlay again without explicit activation. Explicit Hide or
  Turn off Look still stops watching. Completion alone does not show a hidden
  window. The tray now has a latest Look result recall action.
- English/Vietnamese translation quality is unchanged; the user's observed
  idiom mistranslation remains unresolved. This is a presentation refinement of
  Mini's reusable Look flow, not main integration or live model CoT acceptance.

## User-requested build/open

On the user's later request to open the app, the build script completed with the
existing temporary build dependencies and created
`dist/mini-look-20261028-clipboard/RAT Mini.app` and `RAT Mini.zip` (0.5.17 /
20261028.8). The script signed ad-hoc; this is not notarization. Build log:
`/private/tmp/rat-mini-look-clipboard-build.log`. An `open -n` command for that
exact bundle returned 0. No live UI inspection, test, screenshot, model request
or acceptance flow was run. A successful launch command does not establish that
the window stayed open or the new behavior passed acceptance. Earlier no-build
statements below describe the source implementation stage.

Mini is the proof of concept/reusable vertical slice for main RAT in the same
RAT–CoT system. The following describes source intent, not runtime acceptance.
No tests, smoke, app launch, screenshots, model calls or build were run.

1. **Invocation.** Tap ⌥⇧Space or choose Look. Open the result projection with
   the seated idle sprite, baseline the current clipboard, and wait for a new
   copy. Passive presentation does not explicitly activate Mini, so the reader
   can keep keyboard focus. Hold/release still opens Minimal.

2. **Observation.** `LookClipboard` is an input adapter with a 400 ms timer around
   NSPasteboard.changeCount. Read text only after a changed count stays stable
   for at least 250 ms (normally the next timer tick). A stopped watcher has no
   polling timer. No CPU/RAM/latency measurements have been made.

3. **Input limits.** Auto-ingress accepts nonempty text, excluding image/file URL
   MIME. Text over 8,000 characters shows a split-input notice; it is not silently
   truncated. Explicit image paste/drop and region capture keep their existing
   shared workflow. The watcher stores no clipboard history; task artifacts and
   retry data retain the accepted source through the existing session.

4. **Deduplication.** Retain a digest of the last delivered text. RAT's Copy
   updates the native counter baseline and digest to avoid self-triggering.
   Rapid copies coalesce. A newly observed count drops the older queued snapshot.
   Retry is explicit and can process the same source again.

5. **Execution.** Accepted text goes through MiniJob and the shared
   capture_text → captured_text/source_ref → translate_text → verification and
   artifact pipeline. The GUI does not perform translation. Verifiers establish
   structural/source integrity, not semantic translation quality.

6. **Concurrency.** One worker runs and at most one latest text snapshot waits.
   A newer eligible copy cancels an automatic Look worker and invalidates its UI
   generation; the replacement starts after that worker finishes. Cancellation
   cannot promise immediate interruption of a native/network inference call.
   Explicit work is not canceled by the watcher. Leaving Look, pausing, opening
   another surface, region capture or a needs_input question suspends monitoring
   and drops queued clipboard work. Resumption establishes a fresh baseline.

7. **Presentation.** Short results use the selected floating head and compact
   speech. Longer text uses the scrollable 420-wide/up-to-380-high reading panel
   and seated rat at the bottom-right usable screen corner. This is Look's long
   projection (legacy internal B variant), not a fifth workspace. The sprite
   canvas stays 122×128. Idle/busy uses the seated sprite with a small status
   label. A dot reports the actual listening timer state.
   Later user selection: visible errors and local input/watcher notices use
   `rat_look_error_seated_v1.png` for either short or long text. Head/shrug error
   references are saved for later; they are not mapped into Look. Error text,
   retained source and recovery actions remain authoritative.

8. **Placement/focus.** The cursor at detection selects the display and anchors
   short speech; it is not the original text's selection bounds. Geometry clamps
   to available screen bounds. Long reading and idle use the screen corner.
   Result updates only fit geometry; they do not show/activate a hidden window.
   Window masks keep interaction in the paper/mascot, with existing menu handling.
   Native focus, mask and multi-display behavior remain unverified.

9. **User controls.** Close/Esc dismiss the Look result, retain artifacts and
   return to waiting; dismissing a missing-input question abandons that pending
   question. Copy takes exactly the displayed text and returns to waiting. The
   secondary menu offers pause/resume, latest-result recall, explicit retry via
   result action, Minimal for typing and Turn off Look. Hide/Turn off Look stops
   monitoring. Pausing monitoring does not cancel an already running task.

10. **No default LLM dependency and delivery.** `llm_enabled=False` gates Mini's
    model lane and CloudModelClient before key access or network requests. Old
    settings without the flag remain disabled; a stale LLM translation selection
    becomes automatic. Ambiguous inputs ask for intent, compound inputs ask for
    a first explicit step. Optional cloud reasoning/LLM translation requires the
    Advanced opt-in. English ↔ Vietnamese automatic translation uses the existing
    bundled specialist MT engine; other translation services can still use the
    network. This deterministic lifecycle is not evidence of live model CoT.
    Future bundle metadata is .8, visible label `Look · Clipboard source`; no .8
    app or ZIP has been built. Main UI integration, recipient M3 and research
    Stage 0 remain separate and open.

Later user-operated acceptance should inspect actual copy, rapid replacement,
own-copy suppression, long scrolling, close/recall, pause/off, source correction,
missing language, backend errors and multiple displays. Run only checks the user
explicitly requests. Do not infer acceptance or resource efficiency from this
source handoff or historical tests.
