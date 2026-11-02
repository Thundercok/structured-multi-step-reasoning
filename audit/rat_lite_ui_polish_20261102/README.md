# RAT Lite: UI Polish Verification, 2026-11-02

Recorded with `scripts/record_rat_lite_demo.py --root "/Users/Shared/RAT Lite demo" --out audit/rat_lite_ui_polish_20261102` from source.
Real QML window, real controller, real tools: local meaning index (multilingual MiniLM, on device)
and on-device Anh ↔ Việt translation.

## Visual Polish Changes Verified

1. **Composer Placeholder**:
   - Updated default text to `"Tìm file, app hoặc dịch…"`.
   - Verified in `01_empty.png`: fits within 440 px composer width without truncation (~284 px available, ~175 px needed).
2. **Settings ComboBoxes (`shortcutChord`, `targetLanguage`)**:
   - Styled with `desk.inputColor` background, 1 px `desk.edge` border, radius 8, text `desk.ink`.
   - Verified in `11_settings.png`: both ComboBoxes now match the desk color scheme and border radius.
3. **Clarify State Header & Space Cleanup**:
   - Header row and its 1 px divider hidden when header title is empty (`desk.title === ""`).
   - `resultScroll` hidden and `resultSheet` sized snugly around status text and intent buttons (`08_clarify_buttons.png`), eliminating leftover vertical blank space above the intent buttons.
4. **Send Button Visibility & Tab Navigation**:
   - `sendControl` is hidden when draft is empty and no attachment exists (`01_empty.png`).
   - Shortcut keycap (`⌥⇧Space`) remains visible.
   - Keyboard tab order cycles cleanly: editor ↔ moreControl ↔ closeControl when empty, and editor ↔ sendControl ↔ moreControl ↔ closeControl when non-empty.
5. **"Đoạn gốc" Toggle**:
   - Styled with `plain: true` (no border or background, 12 px `desk.muted` text with chevron; hover transitions to `desk.ink`).
   - Verified in `06_translation_source.png`.
6. **Unsupported Language Error**:
   - Unsupported language error (`10_unsupported_language.png`) displays in `desk.ink` text with a small `DeskIcon` `"warning"` icon instead of red text (`desk.pdfInk`).
   - Other errors retain red text (`desk.pdfInk`).
