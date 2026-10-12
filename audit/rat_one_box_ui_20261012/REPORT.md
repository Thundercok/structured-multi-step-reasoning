# RAT one-box UI — 2026-10-12

## Outcome and scope

Implemented the user's requested single conversation box. Compact and full
retain one composer, conversation stream, task state and artifact store.
Submitting a prompt or receiving a tool result no longer forces full mode.
The app running from source was restarted and inspected on macOS.

This changes presentation and interaction, not model intelligence. ADR-002's
adaptive model/UI work remains backlogged. Research/model defaults, experiment
scope, Stage 0 and research claims were not changed.

## Implementation

- One multiline composer: Enter submits, Shift+Enter inserts a newline. Size
  changes preserve the same editor and its selection/caret.
- Compact shows the current exchange; full exposes retained history. Mode
  changes keep the same result widgets and chart canvas, without execution.
- Window height follows content at its actual width, with screen bounds and
  a stable top anchor when space permits. Interactive results open from their
  beginning. Streaming respects the user's reading position.
- Main navigation, detached speech bubble, watermark, duplicate composer and
  nested result/form frames are removed from the main conversation surface.
- Forms reflow their existing fields; metadata edits and detail disclosures
  open inline. Secondary actions use menus. Settings returns to the same chat.
- Artifact revision replacement restores unfinished edits, selection, focus,
  open detail sections and the selected celestial point.
- Direct artifact work keeps the last valid result visible, prevents overlapping
  submissions and displays failures inside the box. Model work retains Stop.
- Geometry/disclosure motion respects macOS reduced motion or
  `RAT_REDUCE_MOTION=1`. Reset retains the user's size choice.
- Scroll timers belong to the stream widget and are cancelled on reset or
  destruction. Disclosure state follows toggle signals, including accessibility
  state actions.

`before/`, `baseline_sha256.json`, `changed_files.json` and `ui_changes.patch`
record this change against the working-tree baseline. Prior unrelated work was
preserved. The two pre-existing files without initial snapshots have narrowly
identified changes in the manifest: a pending-input heading and a hidden import.

## Validation

Final UI command:

```bash
QT_QPA_PLATFORM=offscreen python3.12 -m pytest \
  tests/test_rat_one_box_ui.py tests/test_omnibar.py \
  tests/test_interaction_kernel_ui.py tests/test_timetable_chat_cards.py \
  tests/test_assistant_worker.py tests/test_natal_chart_ui.py -q
```

**98 passed, 3 subtests passed**: [verified_ui_checks.txt](verified_ui_checks.txt). Coverage includes
draft/selection/focus, pending forms, canvas selection, revision updates,
single submission, no forced expansion, retained history, reading position,
reopening/reset, actual registered actions, drawing layout, Settings return,
accessibility toggles and destruction with queued scroll work.

Headless runtime/domain command:

```bash
python3.12 -m pytest tests/test_interaction_kernel.py \
  tests/test_interaction_kernel_regressions.py tests/test_assistant_runtime.py \
  tests/test_rat_task_memory.py tests/test_rat_chat_session.py \
  tests/test_natal_chart.py tests/test_natal_places.py -q
```

**92 passed**: [headless_regressions.txt](headless_regressions.txt).
Compilation and tracked-file whitespace checks passed. These are software
checks with fixtures; they are not measured model-quality evidence.

Earlier check logs are retained, including outdated UI expectations, a layout
initialization error, a scroll-padding assertion and a Qt callback lifetime
crash. The final run supersedes those attempts. The crash prompted replacement
of free scroll callbacks with widget-owned timers and a regression that deletes
windows while scroll updates are queued.

## Visual and native checks

`preview.py` captures actual Qt widgets with fixture inputs. It does not run a
model or index personal files. The example uses 2000-06-15 09:30, Ho Chi Minh
City; all preview birth data are illustrative.

- [Idle compact](compact_empty.png)
- [Inline birth inputs](compact_inputs.png)
- [Compact chart](compact_chart.png)
- [Full chart](full_chart.png)

On the native macOS app, the inline form was filled with the same illustrative
birth data. Switching compact/full retained all fields and an unsent composer
draft. The real dispatcher calculated the chart in compact. Its time editor
retained 10:00 and focus across expansion; Apply updated the chart to revision 2
and the title to 10:00 while retaining the composer draft. Native inspection also
identified the accessibility disclosure mismatch addressed above.
After restarting the final source, the same inline form calculated the example
chart again. Activating the disclosure through macOS accessibility now exposed
the actual celestial-position table, including coordinates and houses.

Launch metadata: [native_launch.json](native_launch.json). The log is outside
the repository at the path recorded there. The initially locked Mac was
unlocked by the user before native inspection.

## Limits

No frozen `.app`/DMG was rebuilt. The updated application runs from source.
These checks do not establish usability improvement, model reasoning quality,
end-to-end model latency, or comprehensive IME/screen-reader compatibility.
User feedback on the interaction remains the acceptance step for RAT-UX-03.

