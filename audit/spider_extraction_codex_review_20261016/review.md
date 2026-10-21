# Spider extraction preparation — Codex acceptance

2026-10-16. **Accept staging và source-independent default RAT test path.**
Không xóa source, scratch hoặc archive. Chưa có repo/path đích được chốt.

## Kiểm chứng độc lập

- Cây gốc và staging pristine: 325/325 regular files, hashes và modes khớp.
- Trong bản sao tạm riêng, patch áp dụng thành công và TOML hợp lệ.
- `cargo metadata --offline --no-deps --format-version 1` ở bản patched standalone
  exit 0. Chưa compile release binary từ staging, không claim build đã hoàn tất.
- Tạo sandbox chỉ có RAT, Python hỗ trợ và tests; không có cây `spider/`,
  `scratch/build_spider` hoặc `rat/bin/spider`. Chạy Python isolated, import RAT
  từ sandbox đó, không trỏ về source checkout gốc: **93 passed in 17.52s**.
- Các tests dùng fake binary/scripted runtime và default gate; không chứng minh
  live web hay model routing. Web default-disabled vẫn là điều kiện chấp nhận.

## Các chỉ dẫn bàn giao đã đính chính

README staging ban đầu ghi sai adapter `rat/services/spider_adapter.py`, registry
`rat/work_context/registry.py`, asyncio và flags scrape. Đã sửa thành paths và
argv thực tế. Không sửa raw handoff/manifest cũ; lưu README trước sửa và hashes
đính chính riêng, nên hash README trong manifest bàn giao cũ không còn current.

Patch thực tế xóa ba dòng example registration sai chỗ, không chuyển chúng
ra bảng khác như handoff mô tả. File example vẫn được giữ. Đã sửa giải thích.
Lệnh build cũ bật default features khác binary HTTP tối giản đã dùng; README
mới ghi candidate command no-default-features và chưa tuyên bố release build pass.

Không đóng gói binary trong `rat.spec` không chứng minh app “100% offline”.
Đây là giới hạn packaging, đã ghi rõ. Xóa source 5.66 MB không tự giải phóng
scratch build 2 GB; cleanup scratch là việc riêng, chưa nằm trong bước source
migration đã bàn giao. Không xóa recovery/archive như routine cleanup.

## Bước tiếp theo

Chốt đích repo/path riêng. Transfer và verify pristine/license/local changes,
lưu build patch/provenance đúng giới hạn. Sau khi đích và recovery đạt điều kiện,
mới gỡ cây `spider/` khỏi RAT. Staging trong `work/` vẫn nằm trong repo gốc;
mức giảm LOC/disk hiện tại vẫn bằng 0.

DNS worker lifecycle (SPIDER-02) và per-hop network controls tiếp tục backlog
trước khi bật web thường lệ. Chúng không buộc giữ source Rust trong repo RAT.

Evidence: `verify_extraction.py`, `verification.json`, `without_source_tests.log`,
`cargo_metadata_stdout.json`, `cargo_metadata_stderr.txt`,
`staging_README_before.md`, `README_corrections.json`.
