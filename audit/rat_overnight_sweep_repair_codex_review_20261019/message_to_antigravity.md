Tiếp tục repair theo independent review mới:
`audit/rat_overnight_sweep_repair_codex_review_20261019/review.md`.
Đọc raw evidence và giữ source/recovery/old audit nguyên vẹn. Đây vẫn là một hệ
RAT–CoT/NCKH, RAT là implementation chính. Không push/pull/reset/force/branch.

Đã xác minh độc lập 271/271 (265 cũ + 6 visual probes). Inventory đủ 132 files,
XML/logs khớp 1.685 pass / 19 fail. Không cần lặp full sweep vô ích. 12 record
model backend đã dùng ngân sách; **không phát sinh thêm real generation requests**
và không rerun scripts/run_native_performance_session.py trên model thật.

Làm tiếp toàn bộ phần software/offline được phép, ưu tiên:

1. **Startup blocker R1:** sửa f-string QSS brace trong rat/os/menu_bar.py, gồm
   QMenu::item/selected/separator. SystemTrayManager đang NameError padding;
   rat/os/app.py gọi constructor này trên đường resident startup. Giữ test
   test_system_tray_manager_shutdown; kiểm initialization fixtures với watcher,
   global hotkey và personal indexing vô hiệu. Không gắn nhãn fail này là legacy.
2. **V2 R2:** dùng nội dung đang render để quyết định bubble đã hiển thị answer,
   không dùng _copy_text làm bằng chứng visible. Reconcile card/bubble khi source
   detail/back, refresh, stream và thay status. Answer phải đọc được trên ít nhất
   một surface; giữ answer_lbl, copy buffer, source renderer/selection identity.
3. **V3 R3:** phân biệt /Applications/App.app và ~/Applications/App.app cùng
   basename/version. Tính distinguishing path theo toàn bộ candidates và xử lý
   collision trước wrap/elide; giữ full tooltip/payload và index dispatch.
4. Giữ nguyên và chạy test_followup_acceptance.py của review mới (5 ca) và 6 ca
   test_visual_acceptance.py cũ. Cần giữ cả controls, không xóa/đổi probe cho xanh.
   Chạy affected regressions; một consolidated regression cuối nếu source đổi.
5. Triage 19 failures đang active bằng raw logs đã có. Không mặc định cả 6 file
   là legacy vì ngoài bộ 265. Với parser/query/reranker/VGC, đọc contract/callers
   để phân biệt bug với stale expectation. Sửa lỗi được chứng minh trong scope;
   cập nhật test chỉ khi nêu rõ contract đúng và vẫn giữ assertion meaningful.
   Không thay research scoring/dataset freeze hoặc nới verification để lấy PASS.
   Nếu đổi harness/threshold/scoring behavior, đọc protocol và chạy bộ research
   checks bắt buộc; không suy model-quality từ software counts.
6. Sửa telemetry/provenance offline: host psutil.cpu_percent không phải process
   idle CPU; đặt đúng tên metric. Số chưa đo để null. Phân biệt backend RSS với
   resident app, document-prefix prefill với question-suffix (chưa đo riêng),
   generation wall time với decode-only, backend first token với displayed text.
   Warm range 4.635,92–47.359,53 ms, có thêm call 8 ở 31.830,36 ms. Các câu hỏi
   cold/warm khác nhau không chứng minh matched cache speedup. Font warning 203 ms
   là từ QApplication probe chưa tạo RAT window; chưa phải app paint benchmark.
7. Sửa native runner instrumentation bằng **fake backend**: append-only ledger,
   request-start checkpoint và flush trước mỗi attempt, không truncate lịch sử,
   resume/global budget guard đếm cả interrupted/failed attempts. Lock case plan
   và output mới, giữ ledger 12 records cũ. Không gọi model để kiểm runner.
   Ghi rõ 12 câu cùng tài liệu là real-model backend smoke; native GUI/cancel/
   changed-file/changed-document/outside-excerpt cases chưa được nghiệm thu.
   Dùng existing fake-backend tests cho phần lifecycle có thể kiểm offline;
   phần cần native display hoặc ngân sách model mới để not-run/blocked, không
   tự thay 12-cases queue bằng 12 fact questions rồi tuyên bố hoàn tất.
8. Sửa evidence map AST: ActionDispatcher thay UnifiedDispatcher; mô tả candidate
   buttons bằng QtViewRenderer thay class CandidateChoiceButton không tồn tại;
   xác minh actual app capability callable thay _execute_launch_app. Với mỗi
   shared/adapter/harness mapping, trỏ đúng call path và raw artifact; dữ liệu
   không đo không tự trở thành measured vì tests pass.

Tạo audit mới có source trước/sau, patch đúng delta, task status và raw checks.
Giữ bản failed của review và received_artifacts. Báo cáo từng hạng mục đã đóng,
failure đã triage, task blocked/not-run; không PASS/READY FOR INTEGRATION khi startup
còn crash hoặc answer bị ẩn mất. Các phần native chưa đo phải giữ trạng thái đó.
Không cần dùng thêm model budget để sửa ba lỗi UI/startup hoặc đính chính evidence.
