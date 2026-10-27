# RAT Mini M4 — single-composer vertical slice

Changed: removed find/translate UI mode. MiniJob submits goals to MiniSession,
which uses headless ToolGoalRouter to compile deterministic one-action plans,
ask InputRequest clarifications, or enter the existing Agent runtime for a
multi-step goal. All business operations still use AgentExecutionService and
registered Finder/Translation capabilities. No private UI-only search/translation.

ToolGoalRouter is reusable by main composition; main is not wired to this new
ingress yet. Deterministic routing is not model inference. No real cloud Agent
loop is claimed in this session. Stage 0 unchanged.

Minimal checks only, at the user's request:
- 3 focused routing tests passed (0.50s).
- QML startup plus session clarification smoke passed; no fake backend answers.
- Live packaged search/translation/clarification evidence, if run, is in live/.

M3 ZIP is retained as recovery. M4 is the successor; prior M3 acceptance does
not establish acceptance of the new goal ingress. No broad regression/UI tour
was rerun.
