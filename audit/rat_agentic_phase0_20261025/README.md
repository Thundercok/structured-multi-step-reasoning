# Agentic migration — phase 0, 2026-10-25

Software cleanup only. No new Agent service/model loop or live acceptance.

- Selected-document QA keeps the runtime's actual answer checks. A successful
  read no longer overwrites answer verification with PASS or invents page 1.
  Removed the unsupported verification outcome from the selected-QA default
  contract; read receipts and response outcomes remain separate from correctness.
- Reading synthesis dispatch returns an observable `model_unavailable` error
  without a draft artifact until an Agent/model adapter is connected. Card
  parsing and selected natal-profile loading remain registered tools.
- The legacy synthesis helper remains an explicitly labelled heuristic prototype,
  inaccessible through production synthesis dispatch. Its steps and boundary
  audit are UNKNOWN; it no longer invents Mercury–Saturn interpretation/grounds.
- Minor visible change in ReadingDesk: “Soạn bản luận · chờ Agent/model”. The
  unconditional green boundary badge is replaced by neutral unknown wording.

Evidence: `headless.txt` and `headless.xml`. Synthetic software inputs and scripted
model replies only; negative probes include a wrong answer and an insufficient-data
reply after a successful indexed read, with no fabricated PASS/page. Dispatcher
probe checks that unavailable synthesis creates no artifact.

Command:

```sh
.venv/bin/python -m pytest tests/test_selected_document_qa.py tests/test_selected_document_read_scope.py tests/test_reading_session.py -k 'not profile_recalculates_and_ignores_injected_positions and not quick_pdf_controller_reading_draft_flow' -q --tb=short --junitxml=audit/rat_agentic_phase0_20261025/headless.xml
```

Two Qt-dependent tests were excluded from that headless command. Full Reading
tests aborted with exit 134 importing PyQt via `quick_pdf_controller.py:18` in
the profile projection test; retry with QT_QPA_PLATFORM=offscreen also aborted.
Adding selected_document_context likewise aborts during collection at its UI
import. Controller/QML behavior, screenshots and live model conversations remain
unverified. No screenshot or successful UI acceptance is claimed.

Known remaining migration: Reading UI still dispatches directly through its
controller; common AgentExecutionService, resource/budget boundaries, model-driven
interpretation and full production inventory belong to phases 1–5. No model
inference, research harness changes or Stage 0 change in this phase.
