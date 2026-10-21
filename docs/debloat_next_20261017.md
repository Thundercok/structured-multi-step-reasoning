# Debloat sau EVRP và watch bot — 2026-10-17

RAT sử dụng CoT; CoT được thể hiện bằng RAT. Runtime, phương pháp và harness là các vai trò trong một hệ.

## Snapshot trước khi gỡ DocAI (cùng ngày)

Inventory: `audit/codebase_scope_20261017/inventory.json`; scanner: `work/codebase-audit-20261017/scan.py`.
Theo phân loại cơ học hiện tại: hệ chính 361 source files / 86,477 dòng không trống; DocAI 53 / 5,195; legacy 32 / 5,541; audit 392 / 165,366.
Số dòng gồm comments/docstrings và tests, không phải độ phức tạp. Audit và legacy nằm ngoài mẫu số hệ chính; các nhóm theo đường dẫn không phải quyết định core/extension. Thay đổi đồng thời của chat khác khiến không thể coi chênh lệch tổng LOC là hiệu quả riêng của lần debloat này.

## Đã làm

- Gỡ watch bot sau đối chiếu archive 34/34 regular files, byte và mode. Recovery ở `scratch/rep_watch_bot_removal_20261017.tar.gz`.
- Đã gỡ DocAI theo yêu cầu tiếp theo sau khi đối chiếu archive 191/191 regular files, byte và mode. Recovery mới ở `scratch/docai_removal_20261017.tar.gz`; xem `audit/docai_removal_20261017/`. Chưa có destination import.
- Giữ `document_intake/` là nguồn PDF/OCR dùng chung. Export DocAI chưa tự chứa dependency này; khi chuyển phải cung cấp wheel/install source tương ứng.
- 95 regression tests pass sau watch bot; kết quả sau DocAI được ghi riêng ở audit/docai_removal_20261017/tests.log.

## Lát cắt cấu trúc tiếp theo

`rat/engine/meta_reasoner.py` và `experiments/research_study.py` cùng import EntryPredictor, OptimalStoppingPolicy và các cấu trúc từ reasoning_env. Đây là liên kết implementation thật, chưa chứng minh hai entry point có cùng hành vi.
Ưu tiên đối chiếu hợp đồng của entry_predictor.py, optimal_stopping.py, reasoning_env.py và reasoning_strategies.py; sau đó mới gom package và giữ compatibility imports khi cần. Không đổi model/prompt/policy trong structural cleanup.
Các file consumer đang có thay đổi đồng thời: không di chuyển hoặc viết lại hàng loạt trong lần gỡ module này. Handoff gọn ở docs/prompts/antigravity_debloat_next_20261017.md.
