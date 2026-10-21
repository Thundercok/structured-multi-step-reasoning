# Flash — two remaining Workbench repairs

Continue the previous revision within the same UI scope. Read AGENTS.md and the prior revision prompt. Preserve concurrent changes, keep the scene flag default off, and do not commit/push/pull/reset/create branches. Do not change inference/runtime/research/DocAI.

Font rendering, overlapping relationship labels, and the active-stop fixture are improved. Current source hashes match your Cocoa manifest. Two blockers remain:

1. **The detail-state regression currently passes without exercising scene updates.** In `test_detail_view_state_preserved_during_unrelated_progress`, `_conversation.begin_turn()` does not call `scene.begin_turn()`. The scene therefore has no active execution and rejects the progress/step callbacks. Fix test setup to establish matching generation/execution/turn ownership and assert that each intended event was accepted, with an observable scene change. Require a genuinely scrollable detail and verify draft/selection/focus as well as disclosures.

   I ran your existing test with that single setup correction through:

   ```bash
   QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest audit/rat_workbench_flash_review_20261016/test_live_detail_probe.py -q --tb=short
   ```

   Result: **1 failed in 4.11s**, at `tests/test_workbench_scene.py:977`: the explicitly collapsed disclosure becomes open again.

   Fix the production path, not the assertion. In `WorkbenchScene.apply_snapshot()`, `borrowed_updated` checks only whether the artifact ID is present. `on_step()` supplies all known artifacts, including unchanged ones. The code returns the borrowed renderer before `_render_detail_for_source()` can capture its state, then forces disclosures open when no state is available. Avoid reparenting/reborrowing unchanged artifact revisions; capture and restore necessary state before detaching for a genuine update. Both the corrected original regression and the independent probe must pass.

2. **Dark mode is unreadable in your own evidence.** Inspect `docs/evidence/rat_workbench_native/native_scene_dark.png`: table cells, speech, and composer text are dark against a dark background. Apply actual theme-aware colors to artifact renderers/tables and dialogue/composer text, including selection, inputs, and actions. Check already-mounted widgets during light → dark → light. Add a focused regression that exercises the theme transition and verifies readable foreground/background pairs. Replace the dark screenshot only after inspecting it.

Finally correct the evidence wording: `scripts/reproduce_native_workbench_scene.py` uses Cocoa Qt with a patched worker, injected events, and `QWidget.grab()`. Call it a **native Qt fixture replay/widget capture**. It does not capture the WindowServer framebuffer or establish real model execution. Keep the native IME limitation explicit.

Run the original eight UI modules plus the independent probe. Report exact results and refreshed evidence. Make these small repairs; do not redesign the scene or launch a model benchmark.
