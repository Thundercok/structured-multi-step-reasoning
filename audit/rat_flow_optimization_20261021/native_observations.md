# Final Cocoa fixture observations

Source: CUA native accessibility observations in this Codex conversation, final
session `20261021T041439Z-6c2634cd`, process 63592. These are recorded observations;
no screenshot files are claimed. Open/preview callbacks are doubles, and the
controller backend/policy are synthetic. The final source snapshot matches the
tested and packaged source.

1. The window opened with the composer focused and no input.
2. Pasting `flow` showed two authored TXT hits, `flow-first.txt` and
   `flow-second.txt`. The editor retained `flow` and focus.
3. Tab → Space → Return → Escape returned to the composer with `flow` retained.
   `fixture_events.jsonl` independently records preview/open of the first file.
4. Replacing the draft with `giải thích fixture` and pressing Return showed
   `Đây là kết quả fixture synthetic; không gọi model thật.` with one public
   observed step. The event log records synthetic embedding and strategy COT.
5. Pasting `Bản nháp còn giữ`, expanding with Command-L, then collapsing with
   Command-L retained that exact draft, editor focus and the answer in both states.
6. Command-Q ended the process. The subsequent AX read reported procNotFound;
   the session record and wrapper confirm a clean exit 0, no model loads or
   blocked operations. No permission toggle or global event tap was used.

Earlier fixture sessions remain in `native-sessions/` for traceability. The first
also confirmed draft retention; the middle session did not confirm that step
after a user-activity interruption and is not used as its evidence.
