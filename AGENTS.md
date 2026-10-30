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

- Never git pull/reset/force unless the user says so in the same message.
  User decision 2026-10-29 (also in README): RAT Lite development has standing
  authorization for small, coherent commits and normal pushes to `main`. Commit
  and push reviewable steps regularly instead of accumulating a large diff.
  Preserve unrelated edits; no blanket authorization for other project work.


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

# RAT Mini — vertical slice tái sử dụng, quyết định 2026-10-26

Chốt tên gọi tương lai, 2026-10-28: người dùng đặt tên RAT Mini là **RAT Lite**
(“Lite”). Đây vẫn là cùng vertical slice của RAT–CoT, không phải dự án mới.
Áp dụng tên khi tiếp tục phát triển sau này; quyết định này không yêu cầu đổi
ngay identifiers, đường dẫn, bundle hoặc bản build. Mini hiện được tạm gác vì
chưa phát triển xong; không tự tiếp tục chỉ vì có quyết định tên gọi.

Mini là vertical slice end-to-end của RAT chính, cùng hệ RAT–CoT; bản gửi bạn
người dùng là một mốc thử nghiệm của slice, không phải ứng dụng tiện ích riêng
hay nhánh code dùng xong bỏ. Thiết kế contracts, routing, execution, verification
và UI để dùng lại trong RAT chính. Mini chỉ giới hạn capability bằng profile.

UX đã chốt: UI RAT cũ, **một ô nhập và một nút gửi, không bắt chọn mode Tìm
file/Dịch**. Bộ điều phối chọn tool theo yêu cầu/ngữ cảnh; thiếu dữ kiện thì hỏi
một câu trong luồng. Nhánh xác định vẫn qua service/dispatcher chung, không
thực thi nghiệp vụ trong UI. Clipboard/cài đặt là thao tác phụ. Không tuyên bố
Agent/model đã chạy thật chỉ vì có router hoặc tool registry.

Phạm vi hiện tại: Spotlight và dịch snippet; hoãn vector DB, embedding, local
LLM, Swift Translation và tối ưu dung lượng/RAM. Quyết định mới ngày 2026-10-30:
người dùng cho phép chủ động chạy test, build và kiểm tra UI thật cần thiết để
làm RAT Lite hoạt động; quyết định này thay thế lệnh cấm tự kiểm thử trước đây.
Ghi kết quả thực tế, giữ lỗi và không dùng kết quả lịch sử để claim thay đổi mới.
M3 có các nút mode là trạng thái triển khai cũ, chưa được chấp nhận về UX seamless.
Xem `docs/rat_mini_vertical_slice.md` để tiếp tục đúng hướng.

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

# RAT Mini M5.15 — scope extension, 2026-10-27

User approved the ten-point iteration including a shared Folder Organizer
capability (preview / explicit Apply / journal / explicit Undo), first-launch
Hello readiness and minor UI refinements. See docs/rat_mini_m515_handoff.md and
docs/contracts/rat_mini_organization.md. This extends the earlier two-capability
Mini profile for this milestone; do not enable the new capability in main before
Mini acceptance and the real recipient M3 gate. The approved iteration permits
one bounded final verification batch after source completion. The 2026-10-30
decision permits appropriate Lite verification on later turns. Main integration, live Agent model planning and M3 acceptance must still
be reported separately from tool registration or software tests.

# RAT Mini — manual acceptance preference, 2026-10-27

The earlier preference for user-only testing was superseded on 2026-10-30:
perform appropriate tests and live UI checks while developing RAT Lite, and
show the intended app to the user. User-provided screenshots are acceptance
observations, not blanket approval of all features.
Mini remains an indev vertical slice of main; main UI integration remains gated.
