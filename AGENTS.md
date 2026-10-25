# Project priorities

## Nguyên tắc bất biến — quyết định người dùng, 2026-10-25

**“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.”**

Không xây tính năng thành tiện ích độc lập. Mọi khả năng nghiệp vụ của RAT
(tìm file/app, đọc, tính toán, kiểm chứng, tarot/natal và các khả năng sau này)
phải là Reasoning Tools trong hệ điều phối suy luận có cấu trúc của Agent.
UI nhập liệu/trình bày và các thao tác trực tiếp phải dùng chung hợp đồng tool,
dispatcher, kết quả quan sát được và bước kiểm tra với Agent; không tạo đường
thực thi nghiệp vụ riêng chỉ dành cho UI. Công cụ xác định vẫn thực hiện phép
tính chính xác. Không suy ra vòng Agent/model đã được nối chỉ vì đã đăng ký
tool: bàn giao phải nêu rõ phần hợp đồng, UI projection và vòng suy luận đã/chưa
triển khai, cùng bằng chứng thật. Không thay đổi Stage 0 hoặc tuyên bố nghiên cứu.


The primary outcome is a student research paper (NCKH) supported by a reproducible
experiment pipeline. RAT is the primary application implementation of the CoT /
structured-reasoning method, not a disposable secondary demo. RAT uses CoT; CoT
is implemented and expressed through RAT. Treat them as one system, not two
independent projects. The headless
pipeline evaluates the method reproducibly; it does not replace RAT as the
implementation target. Read `docs/project_scope.md` for the user-confirmed
relationship, core/extension boundaries and cross-chat handoff rules.
Read `docs/research_plan.md` and `docs/research_protocol.md` when changing research
scope, evaluation, model behavior or project claims.

Prioritize reviewed data, valid comparisons, raw artifacts and manuscript evidence.
RAT work that implements reasoning, verification, routing, stopping, execution
contracts or evidence is core project work. Classify RAT changes by function,
not by the `rat/` directory or absence from headless imports. Cosmetic UI and
unrelated feature expansion are secondary unless explicitly requested. Keep research
experiments headless and independent of personal-file indexing and Qt.

The supported research entry point is `python -m experiments.research_study`.
Legacy simulator outputs, notebook claims and passing software tests are not
evidence of measured model quality. Label synthetic results and proposed
contributions explicitly. Keep train, calibration and test groups disjoint.

Preserve the existing Stage 0 gate for the Qwen/Meta-Reasoner campaign; adding
experiment infrastructure does not establish that the gate has passed. Prefer
smoke validation while real-model experiments remain pending review.

For changes to the research harness or threshold fitting, run:

```bash
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Publish only claims supported by reviewed run artifacts. State whether costs are
synthetic, generated-token counts, or full inference costs, and distinguish
replayed strategy time from measured online latency.

- Never git push/pull/reset/force unless the user says so in the same message.


# Canonical repository and deferred DocAI

The primary repository is now `Thundercok/nesy-docai`, locally accessible through
`~/github/nesy-docai` (real checkout: `SoftwareEngineering2026`). Structured
reasoning and RAT live at the root. On 2026-10-17 the user authorized removing
the remaining standalone `modules/docai/` after reusing PDF/OCR in
`document_intake/`. The module is now removed with verified recovery at
`audit/docai_removal_20261017/`. Keep shared PDF, Apple Vision and Tesseract
readers in place. Invoice XML/Z3 remains deferred; do not restore the module
or add it to RAT startup without a later request. The legacy reasoning checkout/shared worktrees and
`.migration-backups/` are recovery material; do not remove them as routine cleanup.

# Spider separation decision — 2026-10-16

The user selected `Thundercok/tdtu-timetable-compiler` as the destination for
the Spider source, despite its current timetable-related name. Treat Spider
as an independent project outside RAT/CoT scope; its future mass rework belongs
there. Do not infer a timetable/RAT integration request from the repository name.
The existing optional Python adapter may remain, default-disabled; no further
Spider feature expansion is an active main-project priority. Preserve source,
license and local changes until the destination import is published and verified.
Do not report physical removal or a completed remote migration before it occurs.


# EVRP removal decision — 2026-10-17

The user explicitly chose to delete EVRP/SaigonRide from the main project and
rebuild it from scratch later if needed. `modules/evrp/` has been removed; no
destination repository or integration is pending. Do not restore/import it as
routine work. Preserve its verified recovery archive, history bundle and audit
material under the existing recovery policy. RAT–CoT remains one system.

# Solo Git workflow

Use `main` as the working branch for this solo project. Do not create feature
or checkpoint branches unless the user explicitly asks. Preserve unrelated
uncommitted work and existing recovery material. Push only when requested.

# RAT UI acceptance — user decision, 2026-10-23

Test conversations through the real UI and real backend/model as a user would.
Do not inject canned assistant answers or fake model results for UI/flow testing.
Retain actual prompts, public responses, failures and screenshots so the user
can inspect the conversation. If live execution is unavailable, report that
limitation instead of substituting a fabricated successful conversation.
Historical fixture tests/artifacts do not establish live UI acceptance. Keep
research campaign gates separate; a local app smoke does not pass Stage 0.

User decisions, 2026-10-24: use genuine PDFs with verifiable provenance for
UI/flow acceptance; do not generate PDF fixtures for those runs. Record the
source URL/origin and file hash. For each UI iteration, propose one visible
minor UI change so the user can identify the version. When testing, provide
clear screenshots of the actual live UI (min/full as relevant), including
observed failures.
