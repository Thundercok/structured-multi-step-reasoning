# RAT Mini M5.13 — actual UX review, 2026-10-27

User explicitly requested direct inspection: “see it for yourself”. This was a narrow real UI review, not full release acceptance. No app source, preferences or package was changed. Existing M5.13 app was opened via its exact package path.

Observed interactions:
1. Idle app: duplicated invitation text in bubble/composer; capture guidance and version in footer. Actual screenshot 01-idle.png.
2. Typed and verified exact public input: Hello world. This is a short public text for translation. Submitted once. Actual result: Xin chào, đây là một đoạn văn ngắn cho việc dịch thuật. UI reported on-device English → Vietnamese. Result omits world/public; structural completion is not semantic acceptance. Screenshot 02-first-request.png and matching AX diff. Edit request restored the exact input and focused the composer.
3. Cleared that public draft; opened paperclip picker. Selected existing actual screenshot audit/rat_mini_m57_20261027/public-textedit-input.png via the native Open dialog. Origin/provenance are retained in the earlier audit; no generated image fixture. Picker→OCR→translation completed. Screenshot 03-image-result.png and matching AX diff. Observed OCR toolbar noise remains in translated output (I u / Helv), and public is omitted. This does not establish native thumbnail drop or clipboard-image acceptance.
4. Opened Sửa chữ trong ảnh once. Editor showed original OCR with aligned prose lines joined. The resulting stack grew substantially; translated text extended below visible result area and required scrolling. Filename repeated in request/header; thumbnail could not practically be used to compare text. Main composer, source editor and result competed for attention; multiple collapse controls appeared. Screenshot 04-edit-ocr.png and matching AX diff. No OCR edit/retry was submitted in this review. Closed the OCR editor at end; app remains on the actual image result.

Proposed next iteration, not implemented:
- One compact request/result surface; remove repeated idle prompt and duplicate image filename.
- Show the relevant result first. Reduce permanently visible composer/footer chrome during a result; keep a clear single path to the next request.
- Source edit replaces the result body temporarily instead of stacking another editor above it; clear Save/Translate again and Back actions, with draft preserved.
- Image preview should be inspectable when needed; a postage-stamp thumbnail alone does not let the user verify text.
- Keep mascot at the edge without reserving an oversized empty column. One collapse action with clear scope.
- Treat observed translation omissions as a separate real output-quality failure, not a layout issue solved by UI polishing.

No Finder run, global-shortcut test, native screenshot-thumbnail drag, cloud transmission of private content, M3 check or research acceptance was performed. Main Agent planning/integration and Stage 0 remain unchanged.
