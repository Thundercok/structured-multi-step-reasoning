# RAT flow delivery — 2026-10-21

Implemented the authorized priorities 1–3: a shared desktop execution request and
worker factory, reduced synchronous UI startup work, and default progressive
finder interaction with retained state. RAT and CoT remain one system. No research
claims, Stage 0 status, model defaults or production policy activation changed.

## Changes

- Existing assistant, selected-document QA, composed reasoning and direct-operation
  workers share one factory. Conversation/turn/generation identities are reused;
  mismatched results are rejected. Document QA retains precedence. Direct actions
  retain their existing dispatcher/receipt scope and generation delivery guard.
- A host-supplied already-composed engine can execute the existing controller from
  the regular composer. Compatibility is revalidated; production rejects synthetic
  bundles. No automatic model/provider/policy loader was added. Quotas preserve
  zero, unsupported controls fail explicitly, and the original cost ledger remains
  attached. Completion alone is not marked verified; private reasoning is not
  exposed as public step text.
- Secondary schedule/club/embedded-settings pages construct once on demand. Initial
  index metadata and embedded model listings move off the GUI thread. Startup no
  longer probes model-service availability; configured name is not a ready claim.
  The separate modal settings dialog keeps its previous behavior.
- Finder starts with file retrieval available and scans app metadata after show.
  Its coordinator survives catalog delivery, preserving monotonic query IDs and
  suppressing stale queued results. Default scene/finder have explicit env=0 opt-outs.
- Tests cover actual QThreads, composer/controller delivery, lazy reuse, blocked
  metadata I/O, keyboard interaction, draft/caret/focus retention, catalog races,
  identity rejection, cancellation, zero quotas and synthetic-policy rejection.

This delivery changes 5 existing files and adds 4
source/test/doc files. 9 captured baseline files are unchanged,
including MetaReasoner, AssistantRuntime and the packaging spec.
Use `changes_from_start.patch` and source snapshots instead of attributing the
checkout's many unrelated changes to this delivery.

Two additional shared files changed concurrently, outside this delivery's edits:
`reasoning/runtime.py` (mtime 11:04 +0700) and `reasoning/bundle.py` (11:00 +0700).
They were preserved and recorded separately in `concurrent_changes_from_start.patch`.
The final test run occurred after both modifications, and the final archive check
also compares these modules against their current source. Their behavior changes
are not attributed to flow optimization, and this audit is not a separate review
of their research or policy semantics.

## Validation

- Final combined run: **186 unique cases passed**, no failures/errors/skips,
  across 17 selectors. This includes the required 29 research regression cases
  and 20 new execution/interaction cases. `delivery-final.command.json` preserves
  exact argv/environment; JUnit and stdout are raw evidence. Overlapping earlier
  runs are not added to this count.
- Final Cocoa source fixture: default finder, keyboard preview/open, composer
  through synthetic composed controller, compact/expanded draft retention and
  clean exit were observed. See `native_observations.md` and the raw session.
  Hotkey is disabled; actual open/preview are doubles; no personal files, model
  inference, network access, app launches or permission changes were exercised.
- Separate candidate build, CLI `--help`, strict/deep codesign, exact entitlements,
  bundle ID and grammar resource passed. Sixteen embedded Python modules match
  final source bytecode. The frozen candidate GUI has not been acceptance-tested.
- Scoped `git diff --check` passes. The global check reports six whitespace
  findings in unrelated files; they were left untouched.
- Initial failures are retained: `focused` exposed null prompt-token adaptation;
  `focused-r2` and `composed-ui-debug` exposed a wrong AgentStep keyword in a Qt
  callback. Both defects were fixed before green runs. The later catalog/query-ID
  race was fixed and its regression case is included in the final 186.

## Startup fixture measurement

Three alternating baseline/current fresh-process pairs, offscreen Qt, empty
authored DB/catalog/model doubles, uncontrolled OS caches/background activity.
The baseline uses captured UI sources from this session's start. Medians:

| Metric | Baseline | Final source |
| --- | ---: | ---: |
| import_ms | 474.64 | 381.27 |
| constructor_ms | 7031.47 | 2672.18 |
| show_and_events_ms | 155.52 | 139.75 |
| widgets_after_construct | 356.00 | 252.00 |

Times are milliseconds; widget count is a count. Import, construction and
show/event processing are separate samples, not a measured native end-to-end
interaction. Construction still takes about 2.67 seconds
in this fixture. These measurements establish neither global-hotkey latency,
model latency, model quality nor a universal speedup. Per-run values and source
hashes are in `startup_final/startup_probe.json`; the earlier probe remains intact.

## Reviewable artifacts and remaining work

Candidate: `/private/tmp/rat-flow-20261021-dist/rat.app`

Candidate executable SHA-256: `a65148e481606f84e51e01a1b8684dc9799690a5e1315a8eb00b5be49734a830`

The existing `dist/rat.app` was not replaced. Its executable SHA-256 remains
`5d0edef5e53464b14fcee902e71496998d6d145fde86c9e270cb5163cb75a847`, matching the preceding native-permissions audit. No git
commit, branch, push, pull or reset was performed. No installer/permission refresh
is implied by the candidate build.

See `docs/rat_flow_optimization_20261021.md` for composition and compatibility
behavior. Model setup stays deferred. An explicitly supplied compatible
production bundle/backend is needed to activate the controller branch outside
fixtures; no reviewed policy was assumed. General chat streaming, broader
document continuation and recovery polish remain separate work.
