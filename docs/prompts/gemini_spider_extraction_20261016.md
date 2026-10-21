# Gemini / Antigravity — bước tiếp theo: tách Spider khỏi repo RAT

## Đích đã chốt — bổ sung 2026-10-16

Người dùng đã xác nhận repo đích là
`https://github.com/Thundercok/tdtu-timetable-compiler` để chứa Spider, không phải
một yêu cầu phát triển timetable trong RAT. Spider từ đây là dự án độc lập;
người dùng sẽ mass rework sau. Đọc `audit/spider_destination_prepare_20261016/`
trước khi làm tiếp: Codex đã chuẩn bị import commit trong checkout riêng,
chưa publish và chưa gỡ source gốc. Không chuẩn bị lại hoặc push song song.
Giữ bốn file có sẵn ở đích; Spider nằm trong `spider/` kèm metadata migration.
Git publish vẫn tuân theo AGENTS và yêu cầu push của người dùng.

## Mục tiêu và điểm dừng

Tách source upstream Spider thành một đơn vị độc lập, giữ adapter/binary contract
đã tái sử dụng cho RAT. Không mở rộng tính năng crawler. Người dùng chưa chỉ
định repo/path đích; **chuẩn bị và xác minh bản tách trước**, ghi rõ vị trí staging,
nhưng chưa xóa cây gốc, tạo/publish remote hoặc chọn một repo khác để ghi đè.
Nếu người dùng sau đó chỉ định đích, tiếp tục bước migration với đích đó; không
cần làm lại phần chuẩn bị đã được xác minh nếu hashes chưa đổi.

Đọc `AGENTS.md`, `docs/project_scope.md`, `docs/spider_reuse_audit_20261016.md`,
`audit/spider_rat_adapter_codex_review_round3_20261016/review.md` và manifest.
RAT là implementation chính CoT. Chat này dùng để debloat các repo ghép vào:
tái sử dụng phần hữu ích, để phần dư độc lập/backlog. Không thay research
harness, model, Stage 0, UI hoặc DocAI.

## Trạng thái đã được Codex kiểm tra

- 93 tests adapter/runtime/work-context pass ở snapshot review vòng 3.
- Web tool **tắt mặc định**; per-hop network controls chưa triển khai.
- DNS caller timeout đã sửa, nhưng worker đang chạy chưa bị ngắt; SPIDER-02
  là backlog riêng. Không cần sửa rộng adapter trong nhiệm vụ tách source này.
- Archive `scratch/spider_migration_bundle.tar.gz` khớp byte **325/325 file**;
  SHA256 `e883fcfa6f88325d0e80571956f21fb49006bc93855f9a1b6f671536f68ece0f`.
  Kiểm tra lại hiện trạng, không giả định archive vẫn mới khi source đổi.
- 269 tệp Rust tracked có 123,868 dòng không trống. 139,745 là số dòng mọi tệp
  tracked đọc như text, không cùng mẫu số. 325 regular files bao gồm ngoài tracked.
- Binary hiện ở `rat/bin/spider`, version 2.51.208, khoảng 20.7 MB. Cây build
  `scratch/build_spider` khoảng 1.9 GB; chưa được yêu cầu dọn trong bước này.

## A. Chuẩn bị bản tách có thể phục hồi

1. Ghi status/HEAD và hashes đầu lượt; xác định phần thay đổi của các chat khác,
   không stage/gom/sửa chúng. Làm trên `main`, không tạo branch hoặc worktree.
2. Inventory cây `spider/` gồm tracked/untracked/ignored, regular files,
   symlinks/permissions nếu có. Giữ cả `release.sh`, `cv_job_crawler.rs`, license
   và ghi nhận lỗi manifest local. Không chỉ dùng `git archive HEAD` vì nó bỏ
   thay đổi chưa commit và file ngoài Git.
3. Chuẩn bị bản sao độc lập trong staging đã ghi rõ và có thể truy cập. Chưa
   có đích cuối thì có thể dùng `work/spider-extraction-20261016/`; đây là staging,
   không được coi là đã chuyển source ra khỏi repo. Không tạo nested `.git` tại
   staging trong repo chính. Không ghi đè bản staging đã có; kiểm tra và tái dùng
   hoặc chọn thư mục mới có tên rõ. Không dùng symlink trỏ về cây nguồn gốc.
4. Lưu bản pristine đúng byte tách khỏi bất kỳ bản sửa để build. Nếu sửa cú pháp
   Cargo trong bản standalone, lưu patch riêng và README nguồn gốc/version;
   kiểm tra parity trên bản pristine trước, không tuyên bố bản đã sửa byte-identical.
5. Giữ nguyên archive phục hồi và kiểm thử restore trong thư mục tách biệt.
   So file sets, hashes, executable bits và symlinks phù hợp; không thực thi
   release script chỉ để xác minh sao chép. Lưu kết quả máy đọc được.

## B. Xác minh RAT không phụ thuộc source nhúng

1. Rà import/path/build/test references tới `spider/` và `scratch/build_spider`.
   Tách tham chiếu lịch sử/tài liệu khỏi runtime dependencies.
2. Kiểm tra trong bản sao hoặc sandbox staging không có source nhúng, không
   tạm rename/xóa cây gốc đang dùng chung với chat khác để thử.
3. RAT phải khởi động, registry mặc định không bật web, local-file flow và
   tests adapter/runtime liên quan vẫn pass khi không có cây Rust.
4. Test missing binary và binary identity/version theo contract. Smoke thật
   opt-in nếu cần phải ghi rõ điều kiện; không dùng nó để bật web mặc định.
5. Ghi build provenance đủ tái lập: nguồn/revision hoặc hash source snapshot,
   patches nếu có, Cargo.lock, toolchain/target, feature flags, binary hash và
   lệnh cài. Không yêu cầu runtime build từ một scratch path trên máy cá nhân.
6. Giữ MIT notices và nguồn phân phối binary đúng phạm vi. Nếu `rat.spec` chưa
   phân phối binary, ghi rõ giới hạn đóng gói, không claim app bundle có web.

## C. Chỉ gỡ cây gốc khi đích đã được xác nhận

Chưa có đích thì dừng sau A/B với `handoff_codex.md` và câu hỏi ngắn: repo/path
đích muốn dùng là gì? Không tự tạo remote repo hay push. Khi có đích:

- Chép/xác minh đích và các local modifications; giữ backup độc lập ngoài phần
  sắp gỡ. Nếu đường đích ngoài quyền filesystem, dùng luồng quyền phù hợp.
- Chỉ gỡ đúng cây `spider/` sau khi bản đích và restore đã kiểm chứng; không đụng
  `.migration-backups/`, shared worktrees, audit cũ hay scratch build.
- Cập nhật docs/backlog/build references; không thêm source copy mới tracked
  dưới tên khác trong repo RAT rồi gọi đó là debloat.
- Không commit, push/pull/reset/force trừ khi người dùng yêu cầu cụ thể; không
  dùng `git add .` để gom workspace. Ghi scoped diff để Codex review.

## Kết quả bàn giao

Lưu `audit/spider_extraction_20261016/`: manifest đầu/cuối, inventory, restore
verification, dependency-reference report, tests logs, footprint trước/sau và
`handoff_codex.md`. Dùng cùng quy tắc đếm source trước/sau; phân biệt product
code, tests/audit, binary dependency và scratch disk. Staging/archive nằm trong
repo không phải giảm disk. Nếu chưa gỡ source phải báo mức giảm thực tế là 0.

Báo ngắn: phần đã hoàn thành, staging/đích, parity/restore và tests, việc còn
chờ, số dòng/bytes thực sự đã chuyển. Không gọi nhiệm vụ này là cải thiện
accuracy/token hay kết quả nghiên cứu mới.
