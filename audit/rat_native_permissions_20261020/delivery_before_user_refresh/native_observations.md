# Native UI observations

Observed through Codex Computer Use on 2026-10-20 after the grammar-resource rebuild.
This is a human-readable record of tool observations; raw runtime states are in the session files.

- The running `com.thundercock.rat` app exposed its actual `rat` dialog with the Vietnamese workbench welcome text and editable composer. The diagnostic fixture had no schedules. Its runtime state confirmed `window_visible: true`.
- System Settings > Privacy & Security > Accessibility exposed a `rat.app` row, with its switch already on. The assistant did not enable that switch. The running app still reported `not_granted`; requesting permission returned normally without a bridge exception.
- Command-Q closed PID 80960 cleanly (session exit code 0). Reopening the exact same signed bundle produced PID 82003 and another visible window, but the native Accessibility API still returned false.
- An action-time user confirmation was requested before any attempt to refresh the security-sensitive Accessibility toggle. No TCC reset/database changes were made.

- On the same-bundle reopen, Escape hid the window (`states.jsonl`, elapsed 205.46 seconds). Computer Use could no longer obtain a window AX tree and timed out. The process emitted a macOS `getApplicationProperty: called with invalid property` diagnostic at that time; no Python traceback or crash followed. Its origin is not established.
- The assistant stopped only diagnostic PID 82003 using SIGTERM after checking its exact executable and `--diagnostics` arguments. The resident shutdown completed with exit code 0. No real-session process was terminated.
- Global shortcut activation remains unverified because native trust remained false and security authorization confirmation was pending.
