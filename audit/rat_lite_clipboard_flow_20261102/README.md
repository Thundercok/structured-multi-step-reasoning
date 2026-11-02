# RAT Lite: Clipboard & Screenshot Translation Flow, 2026-11-02

Recorded with `scripts/record_rat_lite_demo.py --root "/Users/Shared/RAT Lite demo" --out audit/rat_lite_clipboard_flow_20261102` from source.
Real QML window, real controller, real tools: local meaning index and on-device translation.

## Verified Flow Highlights (§5 & §7 of spec)

1. **Clipboard Text Translation (`07_clipboard_translation.png`)**:
   - Copied snippet from PDF containing soft line-breaks, end-of-line hyphenation, and `\ufb01` ligature:
     `The dominant sequence transduction models are based on com-\nplex recurrent... requiring signi\ufb01cantly less time to train.`
   - Triggered via shortcut handler (`quickLookSelection()`): detected fresh clipboard content without needing Accessibility permissions.
   - Cleans PDF linebreaks and joins words, preserves academic glossary terms (`sequence transduction`), translates cleanly on-device via local OPUS-MT.

2. **Screenshot Translation (`07b_screenshot_translation.png`)**:
   - Screenshot placed in clipboard (equivalent to macOS `⌃⌘⇧4` interactive capture).
   - Triggered via shortcut handler (`quickLookSelection()`): detected fresh clipboard image.
   - Performed on-device Vision OCR to extract text (`Language models translate text across languages.`).
   - Translated cleanly on-device via local OPUS-MT (`Mô hình ngôn ngữ dịch chữ sang nhiều ngôn ngữ khác nhau.`) with 0 permissions required.

3. **Fallback & Permission Invite Logic**:
   - When no fresh clipboard content exists and Accessibility is untrusted, the controller presents the friendly notice inviting Accessibility permission with an explicit "Mở Trợ năng…" button and fallback "Dán chữ".
   - `pasteSelectionFallback()` handles both images and text from clipboard seamlessly.
