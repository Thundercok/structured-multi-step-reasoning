Tiếp tục assignment overnight RAT–CoT đã được giao, dựa trên independent review
mới ở `audit/rat_overnight_sweep_codex_review_20261019/review.md`. Đọc report,
`validation.json`, `evidence_checks.json`, các raw logs và probe mới trước khi sửa.
Giữ `docs/prompts/antigravity_overnight_rat_cot_sweep_20261019.md` làm scope gốc;
brief này chỉ chỉ rõ phần chưa hoàn tất, không thay đổi research gate/ngân sách.

Kết quả đã được xác nhận độc lập: 265/265 regression pass, bao gồm F2 vòng 3.
Không mở lại các lỗi cũ khi không có regression mới. Có 4 failing visual cases
thuộc 3 yêu cầu V2/V3/V4, kèm 2 controls pass. Nguồn thực khớp 37-file source_end
manifest của final; dùng actual hashes, đừng chép hash trong prose.

Làm hết phần có thể chạy trong một lượt theo scope gốc, không dừng ở một báo cáo
265 tests nữa:

1. Sửa V2: khi bubble hiện đủ short answer, overview không có interactive artifact
   hoặc revision transition, ẩn/thu gọn ResultDeskCard nhưng vẫn populate answer_lbl.
   Hiện card khi streaming/truncated/interactive/revision cần nó. Nối trạng thái
   bubble vào quyết định thực tế. Giữ source renderer identity, detail/back state.
2. Sửa V3: candidate button phải thể hiện phần phân biệt giữa các bản cài, không
   nối raw full path vào nhãn một dòng rồi chỉ co widget. Giữ full tooltip/payload
   và index dispatch. Kiểm desktop/420px, light/dark và actual readable label.
3. Sửa V4: phase empty không được ẩn trace khi Finder có grounded structured flow;
   hiển thị collapsed toggle. Bare query tiếp tục không tạo trace giả.
4. Chạy 6 probe mới nguyên vẹn ở
   `audit/rat_overnight_sweep_codex_review_20261019/test_visual_acceptance.py`.
   Giữ nguyên raw lần fail của review. Nếu test cũ yêu cầu cả short answer luôn
   visible, cập nhật đúng expectation theo spec V2, đồng thời giữ kiểm dữ liệu,
   selection/streaming/truncation và khả năng truy cập câu trả lời; không xóa test
   hoặc làm yếu assertion cho xanh. Test candidate cũ tìm full path trong button.text
   cần chuyển sang tooltip/payload đúng spec V3, kèm assertion visible labels vẫn
   phân biệt được từng bản cài và click vẫn chọn đúng path. Snapshot source trước/sau.
5. Hoàn tất inventory 132 active test files theo scope gốc, status riêng từng
   file/nhóm, timeout hữu hạn, log/JUnit, tiếp tục sau collection/import failure.
   Không cộng trùng case giữa targeted regression và full sweep. Kiểm interpreter
   và dependencies thật: ở lượt Codex review, psutil 7.2.2 import được từ user site;
   không tự coi thông báo missing cũ là blocker hiện tại, không cài thêm dependency.
6. Hoàn tất native/performance phần scope đã cho phép hoặc ghi blocker cụ thể.
   Scope gốc đã cho phép native cases và tối đa 12 real generation requests;
   không cần một yêu cầu review mới để thực hiện phần đã được giao. Kiểm call ledger
   của assignment trước khi dùng ngân sách còn lại, ghi mọi attempt trước request,
   vẫn giữ <=640 output tokens, <=90s/request, thinking=False, chỉ checkpoint local
   đã cấu hình. Không chạy research campaign, download hay dùng provider khác.
   Không dùng hết budget chỉ để lấy số. Không gọi fixture replay là native.
7. Sửa performance evidence: không gán số 0 và passed_all_gates như phép đo.
   Giữ bản nhận được làm lịch sử; tạo artifact mới. Thu raw Qt warnings, font resolve
   thực, marker paint, current RSS/peak RSS/idle CPU và phase samples khi đo được.
   Không đo được thì null + lý do. Chỉ so before/after khi matched; 5 processEvents
   không định nghĩa first paint, vắng warning không chứng minh font cost 0 ms.
8. Viết lại evidence map theo actual symbols/call paths. Bỏ claim receipt dừng
   decode/giảm token/confidence saturation khi chưa triển khai và đo; phân biệt
   one-call budget, runtime reconciliation, harness stopping và adapters chưa nối.
   Bỏ “100% recall” từ hai unit probes. RAT và headless vẫn thuộc cùng dự án;
   map trung thực phần shared / adapter khác / chưa nối / chưa đo. Giữ synthetic
   smoke label, Stage 0 không đổi và không suy model quality từ test counts.

Lưu queue/progress/logs/call ledger/ảnh/provenance vào thư mục audit mới, không
ghi đè bằng chứng cũ. Có thể dùng snapshot received_artifacts và reviewed_source
trong report để đối chiếu. Không sửa/xóa các probe cũ hoặc recovery material.
Giữ main và mọi dirty work; không push/pull/reset/force, không tạo branch.

Báo cáo cuối phải có status từng V1–V6, từng nhóm full sweep, native cases và
performance metrics, nêu rõ blocked/timeout/not-run, không gộp thành “hoàn tất”
khi còn thiếu bằng chứng. Một regression cuối trên source cuối cùng khi cần;
không rerun lặp các nhóm không bị ảnh hưởng chỉ để tăng số test.
