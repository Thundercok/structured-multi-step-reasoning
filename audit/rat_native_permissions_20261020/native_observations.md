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

## Follow-up after the user handled the toggle

- The user chose to refresh permission personally and reported Done. The assistant never changed the toggle.
- PID 94378 still reported `not_granted`. Command-Q exited cleanly. The same unchanged bundle was restarted as PID 96408, which also reported `not_granted` with a visible window and `waiting_permission` hotkey status.
- LaunchServices resolved `com.thundercock.rat` to the verified repository `dist/rat.app`. A read-only RAT-scoped TCC query could not open either protected database; no records were read or modified. The current and earlier temporary bundles have different ad-hoc designated requirements (see signing_identity_comparison.json), but the requirement stored by TCC was not observed.
- The assistant selected the existing RAT row without changing permission. Replacing the entry with the exact current app was proposed; the user replied “Leave it for now.” No removal, addition or TCC reset was performed.
- Only the latest diagnostic process was stopped, after verifying its exact executable and diagnostic arguments. It exited cleanly. Global-shortcut verification remains deferred; there is no successful delivery claim.
