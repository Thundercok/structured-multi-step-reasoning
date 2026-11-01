# RAT Lite: real-window demo, 2026-11-01

Recorded with `scripts/record_rat_lite_demo.py --root "/Users/Shared/RAT Lite demo"` from source.
Real QML window, real controller, real tools: local meaning index (multilingual MiniLM, on device)
and on-device Anh ↔ Việt translation. Frames come from the app's own window (`rat_lite_demo.mp4`, 32 s).
`run_log.txt` lists the controller state at each screenshot.

Demo files have names that say nothing about their content (`1706.03762v7.pdf`, `Document (3).docx`,
`scan_0012.pdf`). Vietnamese descriptions found the right file first in 9 of 10 scripted queries;
"tìm transformer paper" missed because the demo text never contains the word.

App search (`04b`, `04c`): "tìm app nhắn tin" → Messages, Zalo, Discord; "tìm app làm slide thuyết trình"
→ Keynote, PowerPoint, with native icons. Translations keep research terms (`05`: "Tự chú ý đa đầu
(multi-head self-attention)").

Verified: meaning-based file and app search, typed translation, clipboard translation, clarify buttons,
unsupported-language message, settings. Index of 6 files: ~3 s; queries ~0.1 s after model load.

Not verified: OS keyboard routing (text is inserted into the QML field), the global hotkey on a
selection in Preview, Accessibility prompts, Spotlight (returns nothing for user folders on this Mac),
launching an app from the list (the launch path was tested with a stub launcher), behaviour on an 8 GB Mac
(model load adds ~800 MB RSS while indexing or querying). The panel was pinned during recording so
clicks elsewhere on the screen would not dismiss it.
