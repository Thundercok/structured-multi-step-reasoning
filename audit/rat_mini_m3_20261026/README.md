# RAT Mini M3 evidence

UI uses Qt Quick paper/composer layout derived from main RAT PDFDesk. Shared
production components: QuietButton, DeskIcon, KeycapBadge, FinderResultsView.
Mini-only controller calls MiniSession/AgentExecutionService, retaining two
capabilities. No vector/embedding, PDF controller or QtWidgets in Mini startup.

- Mini/controller/runtime tests: 49 passed. Includes synthetic layout tests,
  explicitly not live backend/model acceptance.
- Main production Qt Quick boundary: 2 passed.
- Shared main Finder card/action-bar test: 1 passed.
- Broader combined main Finder tests crashed in Qt; raw logs retained. This
  does not establish full main UI regression acceptance.
- Root `python mini_app.py` startup smoke passed with offscreen Qt.
- Live packaged acceptance and release receipt are recorded separately below.

Agent cloud runtime wiring is retained; no real-model loop is claimed without
an API key/run. Direct UI actions use registered reasoning tool contracts,
dispatch, observations and verification. Stage 0 is unchanged.
