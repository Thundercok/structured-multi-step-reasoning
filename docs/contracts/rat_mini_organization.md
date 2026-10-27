# Folder Organizer — M5.15

User-approved extension of Mini's capability profile, 2026-10-27. Shared engine,
capability contracts, dispatcher artifacts and verification are reusable in main;
main composition and live model planning are not enabled by this change.

`plan_folder_organization(folder, rule=type|month)` → `organization_plan`.
Only one folder inside configured scopes; regular top-level files; skips hidden
entries, links, directories and conflicting destinations. Up to 100 moves / 1,000
entries per preview. Month means local modification month, not creation date.
Preview expires after 30 minutes. Nothing moves during preview.

`apply_folder_organization(artifact_id, revision)` → `organization_receipt`.
Hidden from model tool list. Requires trusted execution context
`organization_approval={artifact_id,revision}` plus `user_initiated`; a model
argument cannot approve it. Before each move: current scope, directory identity,
file identity (device/inode/size/mtime), destination directory and exclusive
rename. macOS `renameatx_np(RENAME_EXCL)` never overwrites an existing name.
No unsafe fallback on unsupported filesystems. A journal intent is flushed and
fsynced before each rename; journal storage is local to the app state directory.
A repeated Apply for the same plan returns its receipt instead of reexecuting.

`get_last_organization()` returns the last durable receipt without moving files.
Use it after cancellation/restart to recover a receipt discarded by a cancelled
UI execution. It does not resume Apply automatically.

`undo_folder_organization(artifact_id, revision)` requires a fresh explicit UI
approval of the receipt. Only matching destination identities move back, using
exclusive rename. A new source file or modified destination produces a conflict;
retry Undo after resolving it. Interrupted rename intents are reconciled against
both locations. Empty category directories remain. There is no deletion,
recursive scan, background watcher or automatic reorganization.

Dataflow: composer/picker → routing → MiniSession → AgentExecutionService →
dispatcher → organizer → durable journal → artifact → structural verifier → UI.
Apply/Undo: visible artifact pin + trusted gesture → same service and dispatcher.
Observations exposed to model contain counts/states, not detailed file names.
Deterministic routes make zero Agent LLM calls. Structural verification checks
plan digest and journal membership, not later filesystem stability.

States: request → preview → applying → applied / partial → undoing → undone /
undo_partial. Cancellation can leave a durable partial receipt: recover it, then
explicitly Undo. Stale preview/scope/folder → create a new preview. Outside scope
→ add the intended folder in Settings, then preview. Name conflict/source change
→ skip, preserve originals, show receipt. Journal failure → stop; do not silently
continue unrecorded moves. Concurrent external edits are reported; no transaction
can lock out arbitrary other applications.

Acceptance: preview moves nothing; Apply without trusted approval fails; normal
Apply/Undo preserves content; retries do not move twice; changed source, occupied
name, symlink destination and undo conflict preserve files. Restart can load the
receipt and recover interrupted intents. Live UI evidence uses copies of genuine
public documents/images, with recorded origin and hashes. M3 acceptance pending.

Implementation reference: Apple SDK `sys/stdio.h` declares `RENAME_EXCL=0x4`
and `renameatx_np`; [Apple's volume capability documentation](https://developer.apple.com/documentation/foundation/urlresourcekey/volumesupportsexclusiverenamingkey?language=objc)
describes the exclusive rename option. Unsupported volumes produce a per-file
failure; there is no overwrite-capable fallback.
