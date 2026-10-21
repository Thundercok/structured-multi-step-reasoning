# Desktop flow integration — 2026-10-21

The normal work surface and progressive finder are enabled by default. Explicit
`RAT_WORKBENCH_SCENE=0` and `RAT_WORKBENCH_FINDER=0` retain the compatibility paths.
The composer, conversation, dispatcher, artifact store and model owners are reused.

## Daily interaction

- Summon the same window and continue the current draft, selection and work.
- Type to retrieve indexed file metadata. Typing alone opens nothing and performs
  no generation. Application metadata discovery starts once, after the window is
  shown; file retrieval can run before that catalog arrives.
- Tab, or Down at the bottom of the composer, enters the result list. Up above the
  first result returns to editing. Enter on a result opens it; Space previews it.
  Focused action buttons retain their own action. Enter in the composer submits
  the request, and Shift-Enter remains a newline. IME composition is respected.
- Escape from the results returns to the composer. The existing execution-cancel,
  detail/back and hide semantics remain. Command-L changes reading space while
  retaining the same editor and result state.

The schedule, club and embedded settings pages are constructed on first access
and then reused. The initial index statistics/recent list and the embedded model
list are read on background threads and delivered through queued Qt signals.
Startup displays the configured model name without probing its service. This
does not establish model availability and does not change the separate modal
SettingsDialog's existing behavior.

## Shared request boundary

`rat.engine.execution.ExecutionRequest` carries the existing conversation
execution/turn identity, query generation, selected-document path and context.
`create_execution_worker()` is the desktop composition point:

| Request | Existing implementation |
| --- | --- |
| Selected document | AssistantWorker and selected_document_qa, including its existing source checks |
| General assistant | AssistantWorker and AssistantRuntime |
| Composed reasoning | OnlineReasoningWorker and the supplied MetaReasonerEngine |
| Direct artifact/action callback | ArtifactWorker and the existing dispatcher/receipt scope |

Direct actions retain their existing dispatcher ownership and generation-based
delivery guard; the envelope is not a second journal or artifact store.
The regular assistant-worker import no longer imports the strategy runtime.

The host may supply an already-composed engine through the QApplication property
`ratReasoningEngine`. The existing `is_reasoning_query()` hint selects that branch;
otherwise general assistant handling continues. This hint is not newly trained or
claimed to have measured routing accuracy. Selected-document QA takes precedence.

The host constructs the engine with `build_composed_meta_reasoner(bundle, backend,
matching_policy)` and retains the backend's existing ownership. The worker factory
revalidates bundle compatibility before dispatch. There is no automatic policy
file loader, provider fallback, weight loading or second engine/model owner.
`ratAllowSyntheticPolicy=True` is an explicit fixture-host option; default hosts
reject synthetic policies. No production policy was approved or activated here.

Strategy deadline/quota controls go to the existing reasoning worker. Controls
unsupported by another branch fail explicitly instead of being ignored. Empty
budgets preserve zero and are not replaced with defaults. Result identity is
checked before adapting it to the conversation consumer.

Strategy results retain their cost ledger and provenance. An unknown prompt-token
count remains null in the ledger; the legacy integer display fields use a
generated-token-only scope in that case. A completed strategy does not become a
verified answer or a successful tool effect. Public step events contain only an
observed strategy name/count, not private reasoning or raw model input.

## Evidence and limits

See `audit/rat_flow_optimization_20261021/` for exact commands, source snapshots,
fixture tests, native UI observations and the candidate bundle check. Tests use
isolated state and prevent real model imports/network connections. The Cocoa
fixture host uses authored files, a synthetic fitted policy and open/preview
doubles. It disables global event taps and makes no permission changes.

This delivery implements flow priorities 1–3. General chat streaming, answer
quality/model selection, broad document continuation and recovery polish remain
separate work. No new model calls, research-data review, Stage 0 change or measured
general model-quality improvement follows from the software checks.
