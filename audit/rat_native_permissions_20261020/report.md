# RAT native startup and Accessibility repair — 2026-10-20

The rebuilt `dist/rat.app` opens its actual Cocoa workbench, handles an empty
schedule fixture, reopens, hides with Escape and exits cleanly. RAT now appears
in macOS Accessibility settings. Native global-shortcut verification remains
pending: Settings shows the existing RAT switch as on, but the running rebuilt
process reports `not_granted`, including after reopening the same bundle.
The user manually refreshed the toggle and reported Done; native trust remained false
afterward and after a same-bundle restart. The user then deferred the proposed
remove-and-re-add step. The assistant changed no security settings.

## Findings and changes

| Finding | Repair and evidence |
| --- | --- |
| Permission checks referred to whichever process was launched; a source Python grant does not authorize the frozen app. Requests swallowed bridge errors and were duplicated. | Added a shared permission adapter with bundle/executable identity, exported PyObjC prompt constant and distinct granted/denied/unavailable outcomes. The frozen app's request returned normally as `com.thundercock.rat`; its row was observed in Settings. |
| The hotkey manager could attempt a listener without trust and log that hotkeys were active. | It now waits without creating a listener, exposes its status/error and reconnects after a grant. `listener_started` deliberately means only thread startup. Real global shortcut delivery is still pending. |
| The permission monitor could reuse a stopped event across listener restarts. | Each monitor generation retains its own stop event. Tests exercise replacement and grant retry. The tray permission action refreshes on each menu opening. |
| GUI-thread SearchWorker construction performed embedding/vector warmup before startup finished. | Removed constructor warmup; searches initialize resources on their existing worker. The first semantic search may be slower. A guarded source session caught the old FastEmbed attempt; the final isolated sessions attempted no model imports/network connections. |
| The workbench selected `members[0]` when schedules were empty. | Added an anonymous empty rendering profile without invented classes or persisted schedules. The before/after probe reproduces the old IndexError; actual native fixture startup now succeeds. |
| The first frozen GUI failed importing jsonschema's URI-format dependency because `syntax_rfc3987.lark` was missing. | Added installed rfc3987_syntax/Lark grammar resources to the spec. The preserved first failure log identifies the missing file; the rebuilt bundle contains it and opens the window. No runtime/reasoning module was changed to bypass the import. |
| The build enabled argv emulation for Qt and replaced its entitlement-bearing signature with a plain ad-hoc signature. | Disabled argv emulation, supplied entitlements/signing identity to PyInstaller, removed the second signing pass and made the wrapper verify the final signature. The final bundle passes deep/strict codesign verification with the expected entitlements. |

The visible on-switch plus false native trust is a stale authorization state for
the current build. Its exact TCC internals were not inspected. This app is
ad-hoc signed, with no TeamIdentifier; changed ad-hoc builds cannot promise
permission continuity. Reopening alone did not refresh this entry.

## Verification

- **101 unique tests passed, zero failed/errors/skipped:** 72 permission/startup,
  crash shield, onboarding, instance/warmup, packaging, lightweight CLI and document
  startup tests in [regression-delivery.xml](regression-delivery.xml), plus the
  required 29 research-harness regression tests in [research.xml](research.xml).
  Earlier runs overlap and are not added to this total.
- The source native sessions and frozen bundle sessions used Cocoa, fixture state,
  an empty database/schedules/catalogs, isolated logs/IPC, disabled model discovery
  and explicit model-import/network guards. Final source and rebuilt frozen
  sessions report `embedding_loaded: false` and `blocked_operations: []`.
- Actual frozen GUI observations: visible workbench/composer, clean Command-Q,
  same-bundle reopen, Escape hide and clean targeted diagnostic shutdown. The
  latest runtime identities and transitions are in `bundle-sessions/`; the UI
  observations and their limits are in [native_observations.md](native_observations.md).
- Final packaged CLI `--help` and `--diagnostics --help` both exit 0.
- The archive's ten relevant Python modules match the current source, and signature,
  entitlements, bundle ID and URI grammar checks pass in [bundle_check.json](bundle_check.json).
  Final executable SHA-256:
  `5d0edef5e53464b14fcee902e71496998d6d145fde86c9e270cb5163cb75a847`.
- Final app: `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning/dist/rat.app`,
  bundle ID `com.thundercock.rat`, version `1.0.0`.

The initial Qt regression run had a test-only incomplete database mock (subsequently
fixed); the first bundle-inspection helper used codesign's human-readable output
where XML was required (subsequently fixed). Both failures remain in the audit.
The initial frozen GUI's missing grammar failure also remains. Exit code 0 from
that resident process alone did **not** establish successful GUI startup; window
telemetry and actual UI observations were required for the repaired build.

## Remaining acceptance and limits

Further permission work is deferred at the user's request. The user's manual toggle
refresh and a same-bundle restart both left native trust false. LaunchServices
resolves to the correct current bundle; the proposed next step was to remove the
existing Settings entry and add that exact bundle again. The assistant only
selected RAT's row. No toggle, remove/add, TCC reset or database modification was
performed by the assistant. A read-only RAT-scoped query could not open the
protected TCC databases, so their records were not inspected. The old temporary
bundle and current bundle have different ad-hoc designated requirements, but the
requirement stored by TCC was not observed; the precise cause remains unconfirmed.

When permission work resumes, observe Command-Shift-Space hide/summon the window
while another app has focus, then verify trust/shortcut delivery after reopening
this same bundle. No successful global-shortcut claim is made. See
[manual_refresh_followup.json](manual_refresh_followup.json) and
[signing_identity_comparison.json](signing_identity_comparison.json).

A macOS `getApplicationProperty: called with invalid property` diagnostic appeared
when Computer Use attempted to inspect the hidden window. No Python traceback
or crash followed; its origin remains unestablished. Source-session teardown also
emitted an IMK warning. These are recorded without treating them as proven app
failures or declaring all native warnings resolved.

These controlled sessions do not certify normal-session IPC, onboarding interaction,
personal-file indexing, Full Disk Access, semantic search/model execution or broad
end-to-end reasoning quality. No inference was performed and no Stage 0 gate or
research claim changed. The earlier PDF/OCR fixture work remains separately
documented in [the packaging/intake report](../rat_packaging_intake_20261020/report.md).

## Reproducibility and shared-checkout boundaries

The report/manifest from before the user refresh is preserved in
`delivery_before_user_refresh/`. Command records, raw output, JUnit files, closed
native sessions, launch commands,
bundle inspection and the before/after empty-schedule probe are retained here.
`source_start/` captures the already-dirty checkout before this repair;
`source_end/` and [changes_from_start.patch](changes_from_start.patch) isolate this
session's changes from existing Antigravity work. The unchanged `rat/os/app.py`
snapshot confirms the resident runtime was reused. Diagnostic state/log directories
are explicitly configurable via `RAT_STATE_DIR` and `RAT_LOG_DIR`.

Crash-shield tests now use temporary logs and restore process hooks; the orphan
instance test uses a process-list fixture. The user's live crash log retained
its initial observed size/mtime (no initial content hash was taken). No real RAT
session was killed. The checkout remains on `main`; no branch, commit, push,
pull or reset was performed. Recovery material and unrelated dirty files were
preserved. See [validation.json](validation.json) for machine-readable outcomes.

References: [Apple on code-signing identity](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements),
[PyInstaller on GUI argv emulation](https://pyinstaller.org/en/stable/feature-notes.html#optional-argv-emulation),
[Apple on adding Accessibility apps](https://support.apple.com/en-euro/guide/mac-help/mh43185/27/mac/27).
