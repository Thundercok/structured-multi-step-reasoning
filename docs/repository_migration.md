# NeSy là repo chính — chuyển cục bộ ngày 2026-10-12

Người dùng chốt dùng `Thundercok/nesy-docai` làm repo chính. Phạm vi hiện tại là
chuyển structured reasoning và RAT sang NeSy, giữ DocAI riêng để tích hợp sau.

## Nơi làm việc

- Canonical alias: `/Users/thundercock2/Documents/Github/nesy-docai`.
- Checkout thật: `/Users/thundercock2/Documents/Github/SoftwareEngineering2026`.
- Nhánh chuẩn bị: `codex/nesy-primary-migration`.
- Repo đích: `https://github.com/Thundercok/nesy-docai`.
- Source repo: `https://github.com/Thundercok/structured-multi-step-reasoning`.

`experiments/`, `meta_controller/`, `rat/`, `data/`, `prereg/`, `docs/` và raw
artifacts ở repo root. `modules/docai/` giữ invoice/OCR package, dependencies,
compatibility assets và tests riêng. RAT không đăng ký công cụ invoice và không
import DocAI. Entry point nghiên cứu vẫn `python -m experiments.research_study`.
RQ, train/calibration/test và Stage 0/publication gates không đổi.

## Lịch sử và trạng thái làm việc

Commit NeSy gốc `8e5533b6f376d32481dcfbc1762daf21bf260c65` và reasoning gốc
`835cbda946dd0acde7a77e35ac08efb86d50dbc9` được nối bằng merge giữ hai lịch sử.
Các branch reasoning cũ giữ dưới `codex/legacy-reasoning/`; tags được giữ cả tên
gốc và namespace `reasoning/`. Hidden refs và worktree heads giữ dưới
`refs/archive/reasoning/`. Đây là refs cục bộ, chưa được publish.

Snapshot working tree bao gồm file đã theo dõi và file chưa commit, có SHA-256.
Ignored state cần giữ (runs, outputs, fixture DB, logs) được chép cục bộ nhưng
không đưa vào commit công khai. Ledger/Excel cũ của DocAI nằm ở
`modules/docai/local_state/`, được ignore. `build/`, `dist/`, environment và
cache có thể tái tạo được không chép lại.

Backup đầy đủ cho cả lịch sử và snapshot ở `.migration-backups/20261012/`,
được Git ignore. `structured-reasoning.bundle` và `nesy-before-migration.bundle`
đều là self-contained bundles đã qua `git bundle verify`. Hai manifest backup
chỉ ra từng file/hash. Source checkout và 11 worktree liên quan vẫn còn; không
xóa thư mục Git dùng chung trong lượt chuyển này.

Bản đồ chuyển và kết quả kiểm tra ở `audit/repository_migration_20261012/`.
Các số pytest/smoke chỉ là kiểm tra phần mềm, không thay bằng chứng NCKH.

## Publish và xóa repo cũ

Hiện mới chuẩn bị cục bộ. Chưa push hay xóa repo GitHub. `AGENTS.md` yêu cầu
người dùng nói rõ push trong chính message cho phép bước đó. Sau khi được cho
phép: publish trạng thái đã kiểm tra vào NeSy, kiểm tra commit/ref trên remote,
rồi mới xử lý xóa repo GitHub cũ theo quyết định đã chốt. Giữ backup cục bộ và
các worktree vì chúng có thể còn công việc chưa được nhập vào main.
