# Cách Chuột làm — Workbench presentation proposal

Status: proposed, not integrated or accepted. UI source is being edited by
Gemini; this work leaves those files unchanged. Qt/QML migration remains last
in the backlog. No research scope, model behavior or Stage 0 change is proposed.

## User outcome

The user should see what RAT is doing, what evidence is available, what remains
uncertain and how to steer the work through the same bottom composer. Workbench
space should expose useful work rather than a long stream of model narration.

Keep three distinct meanings:

1. **Work trail:** observed operations, results, failures and missing inputs.
2. **Explanation:** a concise user-facing account of the answer, sources,
   assumptions and limitations. It is not proof of the model's internal process.
3. **Worked solution:** mathematical or algorithmic steps that directly teach
   the requested method. These belong in the result itself and can have scoped
   tool checks when available.

## Two visual proposals

- **Tiến trình dẫn đường:** a short current phase and two or three completed
  milestones above the emerging result. Best when the task has several useful
  observable steps. Group repeated reads/searches rather than logging each call.
- **Bằng chứng sát kết quả:** result first, with page/source links adjacent to
  the claim they support; a quiet “Cách Chuột làm” disclosure holds the work
  trail. Prefer this as the everyday default to retain space for useful results.

Both preserve the approved separate paper canvas, prominent mouse, RAT speech
and green bottom composer. The mouse communicates a short current observation
or question; it does not recite the complete trail. New results appear as soon
as they are available, independent of animation or final answer completion.

The interactive conversation prototype uses synthetic PDF/page events and a
merge-sort example, explicitly labeled as a demonstration. It is not evidence
of a real search, native Qt implementation or model performance. View commands
in the prototype are local presentation controls. No model call is made.

## Minimal existing integration seam

`rat/engine/work_trace.py:summarize_step` already projects a public
`TraceEntry(number,title,detail,status)` from observed `AgentStep` values.
`rat/ui/work_context.py:WorkTracePane` exists per assistant turn; it is currently
hidden outside `RAT_DEBUG_UI=1`. Omnibar already sends progress, completed steps
and terminal state to this pane with ownership/generation checks.

Reuse that per-turn projection and existing artifact store. Do not introduce a
second execution store or request additional model calls just to narrate work.
Separate current status from the completed-step count; current `_title()` hides
the status behind the count once entries exist.

For richer rows, allowlist references already available on `AgentStep`:
turn/execution ID, sequence, operation label, committed artifact ID/revision,
source basename and observed page range, scoped check status, measured duration
when present. Do not expose raw arguments/results, full document bodies,
private paths, prompts, `thought`, `model_input` or `raw_completion`. Current
error/note details require public-copy projection before being shown by default.

Progress is currently a phase string, not a structured tool-start stream. Use
only observed phases; do not infer exact tool starts, a fixed future roadmap,
percent completion or ETA. `plan_tasks=False` means many turns have no planned
roadmap. A proposed plan must be labeled as a proposal if one exists.

## Behavior rules

- Always distinguish running, completed operation, needs input, partial failure,
  stopped and unchecked. Use text plus status marks, not color alone.
- A check mark means the specific operation completed. “Verified” requires a
  specific recorded check and its scope. A produced answer does not certify
  factual correctness or overall task completion.
- Reveal sources/page ranges only after the corresponding observation. Source
  selection alone does not establish support for every sentence in an answer.
- Support detail/collapse through the composer and optionally a quiet native
  disclosure. Opening detail changes no task, model call, draft, focus or scroll.
- Stop freezes the previous execution's trail and keeps useful completed work.
  Late events cannot mutate the new work. Clarification appears beside the
  affected result and is answered through the same input.
- Do not auto-open the trail, pull the reader to its bottom or rebuild result
  widgets on every token. Update on meaningful events and preserve selection.
- Avoid per-token narration, fabricated milestones or decorative delays. Keep
  hidden-window animations off and honor reduced motion.

## Acceptance before integration

Replay completed, needs-input, partial-error and stopped tasks; include no-tool
answers, repeated operations, a moved file and a late callback. Verify public
details contain no private/raw reasoning fields. Confirm the same editor and
artifact renderer identities survive expanded detail, scrolling and revisions.
Check readable bounds at narrow width and enlarged type. Measure presentation
cost separately from model latency; fixtures do not establish live model quality.

Research context: the [Microsoft Human-AI interaction guidelines](https://www.microsoft.com/en-us/research/publication/guidelines-for-human-ai-interaction/)
are a design reference, not evidence of RAT usability. [Anthropic's tracing
research](https://www.anthropic.com/research/tracing-thoughts-language-model)
reports examples where a model's stated explanation differs from its observed
internal mechanism; therefore this proposal does not equate narration with an
audited internal trace.
