# Native startup and Accessibility

The local development app is `dist/rat.app`, with bundle identifier
`com.thundercock.rat`. Run one canonical copy when checking macOS permissions.
Launching Python from source checks the Python process's permission; it does
not establish that the packaged RAT app is registered or authorized.

Accessibility checks and requests share `rat/os/permissions.py`. A request is
asynchronous: `prompt_requested` does not mean permission was granted. Bridge
failures are reported as `unavailable`, distinct from `not_granted`. The shortcut
manager waits without constructing an event listener until Accessibility is
trusted. `listener_started` reports a thread start, not a successful observed
global shortcut. Permission-dependent menu actions refresh whenever the menu opens.

The app can request permission and open the correct Settings pane. Enabling the
Accessibility toggle remains a macOS authorization step. There is no automatic
TCC database modification or reset. Entitlements do not grant Accessibility.

Builds disable PyInstaller argv emulation for the Qt GUI and pass the entitlements
file to the bundler. The wrapper verifies the final signature and does not replace
it with a second plain ad-hoc signature. `RAT_CODESIGN_IDENTITY` may select an
existing signing identity; otherwise the build remains ad-hoc signed. Ad-hoc
identity does not provide permission continuity across changed builds. An ad-hoc
build is not a notarized distribution.

After rebuilding an ad-hoc app, macOS can show its old Accessibility toggle as on
while the running process still reports `not_granted`. Check the running bundle
path before refreshing its authorization in Settings. Reopening alone may not
refresh a stale entry. Only the native trust result and an observed global
shortcut establish that the current build is authorized and working.

## Controlled diagnostic session

```sh
python main.py --diagnostics /tmp/rat-startup-diagnostics --seconds 30
dist/rat.app/Contents/MacOS/rat --diagnostics /tmp/rat-startup-diagnostics --seconds 120
```

Launch the bundle through Finder/LaunchServices when testing macOS's app identity.
The command form above is also useful for collecting foreground terminal logs.
Each diagnostic invocation creates a fresh dated subdirectory. It uses an isolated
state directory, fixture database, empty schedules and empty app/model catalogs.
Indexing, watchers, model preload and network connections are disabled; import
guards block inference/embedding runtimes. It uses the existing resident app and
workers, not a second engine. Its IPC name is isolated from normal user sessions.
This tests diagnostic startup and does not certify normal-session IPC or model use.

Outputs include `identity.json`, `states.jsonl`, `session.json`, `qt_messages.jsonl`
and session logs. A blocked operation is recorded separately from an actual model
call. `embedding_loaded` must remain false. `RAT_STATE_DIR` isolates application
configuration/database/schedules; `RAT_LOG_DIR` explicitly isolates crash logs.
Neither variable changes the user's home directory.

Search-worker construction performs no embedding or vector preload on the GUI
thread. A search initializes its required resources lazily on the search worker;
the first semantic search can therefore take longer. Empty schedules keep an
anonymous empty profile for rendering, without fabricating classes or persisting
a new schedule. Native GUI, permission and hotkey outcomes must be checked
separately from software tests and headless research evidence.
