# Review bàn giao Turn 2 và hướng tiếp theo trên cùng UI Quick

2026-10-22, Asia/Saigon. Đã nhận bàn giao High-Density Turn 2 của Anti.
Review này không sửa production, Git history hoặc raw artifacts cũ. Chỉ cập
nhật ghi nhận review và kế hoạch chung; chưa nghiệm thu auditor về ngữ nghĩa.

## Mốc đã bắt kịp

HEAD hiện tại `73a15ec` trên main. Các commit trước đó đã đưa app sang Quick,
nối Finder vào composer, cải thiện keyboard/open/QuickLook/reveal, cache catalog,
action bar/section headers/smart-AI card, context chip và SourceEvidence. Đã có
ảnh/video showcase. Không khởi động lại kế hoạch từ trạng thái Widgets cũ.

Gói Turn 2 thêm native app icons qua NSWorkspace/QQuickImageProvider, SVG,
selection/keycaps/breadcrumbs/smart-AI card và ContradictionAuditor. Các file
liên quan còn uncommitted; giữ Anti làm người triển khai, không sửa chồng.
Ảnh showcase `docs/screencaps/02_finder_apps.png` đã có icon Terminal, Safari,
Calculator; đây vẫn là ảnh showcase, không thay thế native acceptance từ
launcher chính. Source có đường lấy icon AppKit; chưa có bằng chứng mọi app
đều trả icon 1024x1024 như báo cáo. Test non-null cũng có thể đạt bằng fallback.

Đã chạy độc lập đúng bộ Anti báo cáo: **38 passed in 15.57s**. Log nằm tại
`turn2_received_suite.txt`, JUnit tại `turn2_received_suite.xml`. Gồm
`test_turn2_innard_and_icons`, `test_epistemic_grounding`,
`test_quick_finder_flow`, `test_quick_pdf`, `test_quick_unified_flow`.
Chạy offscreen/software, không gọi model thật; đây là kiểm thử phần mềm,
không phải kết quả chất lượng model hoặc thời gian online của ứng dụng.
Chín file review khớp hash trước/sau run (`turn2_received_hashes.json`).

Lần 60 passed in 11.00s thuộc snapshot trước. Ba probe Qt boundary cũ chưa
được thực thi do lỗi hạn mức bộ duyệt tự động ở lần trước; lần 38-test này
đã được duyệt và chạy thành công. Không ghi các probe chưa chạy thành failure.

## Hai điểm cần sửa/giới hạn trước khi chốt ContradictionAuditor

**1. Đầu vào audit hiện là nhật ký thực thi, chưa phải các claim của câu trả lời.**
`rat/ui/reasoning_worker.py:205` gọi `audit_trace(res.steps, evs)`. Trong nhánh
composed policy, `MetaReasonerEngine.solve` tạo steps dạng `Executed COT: ...
generated tokens.` và để câu trả lời tại `res.answer`. Vì vậy báo cáo passed
trên steps này không kiểm được một câu trả lời trái nguồn. Probe pure-Python
với một operational step và nguồn TOEIC trả passed=true; đây là kiểm tra độ
bao phủ đầu vào, không phải bằng chứng kiểm tra được câu trả lời model.

Cần nối explicit public claims/structured facts cần kiểm với SourceEvidence,
phân biệt execution events với claims. Không xuất hoặc yêu cầu raw/private CoT.
Nếu không có claim/khả năng kiểm phù hợp, báo not_evaluated/unknown với scope rõ;
không diễn giải không bắt được lỗi là đã chứng minh nhất quán. Giữ public
verification UNKNOWN khi chưa có checker được xác nhận cho tác vụ.

**2. Numeric collision đang gộp các đại lượng/chủ thể khác nhau.**
`contradiction_auditor.py:279–299` lấy số đầu tiên theo topic rồi so khác nhau.
Hai ca authored, hợp lệ đã bị gắn numeric_collision:

- Nguồn nói tối thiểu TOEIC 600; claim nói sinh viên đạt TOEIC 650, cao hơn mức
  tối thiểu 600. Đây là threshold và observed score.
- An có TOEIC 650; Bình có TOEIC 700. Đây là hai chủ thể.

Cần ràng buộc cùng entity, metric, quan hệ/bound và phạm vi trước khi kết luận
mâu thuẫn. Khi thiếu thông tin thì ghi chưa kiểm được hoặc cảnh báo heuristic,
không dùng severity blocking như một verifier đã được kiểm chứng. Thêm cả hai
negative controls trên và positive control mâu thuẫn thật trong cùng phạm vi.
Các ví dụ chỉ là fixture, không khẳng định một quy chế/ground truth thực tế.

Bằng chứng lúc đang phát triển: `turn2_work_in_progress_observations.json`
vẫn giữ nguyên. Đã chạy lại ba ca trên source bàn giao, kết quả tương tự tại
`turn2_received_observations.json`; hash auditor vẫn là cùng bản. Không dùng
Qt, không gọi model. Tình trạng được ghi trong `current_progress.json`.

Vì hai điểm này, chưa chấp nhận tuyên bố auditor đã "chặn mâu thuẫn" của câu
trả lời. Đường hiện tại thêm report/đổi verification_status và vẫn có thể báo
done; không phải guard đã được kiểm chứng để dừng thực thi. Cần sửa đầu vào,
scope và coverage, rồi bổ sung ca end-to-end qua worker với câu trả lời trái
nguồn nhưng execution log trung tính, cùng các negative/positive controls số.

## Phần cần xác nhận sau khi source ổn định

Các boundary ở Quick controller vẫn cần kiểm trực tiếp: source artifact của
lượt mới phải lấy từ response hiện tại (không từ telemetry lượt trước); status
callback phải gắn execution/generation; close phải giữ/quản lý worker đang chạy
và báo đúng trạng thái shutdown. Source hiện còn các mẫu cần kiểm, nhưng ba
probe Qt chưa chạy nên đây chưa phải các failure có log xác nhận.

Với native app icons: kiểm qua launcher dùng QGuiApplication thực tế và app
bundle trên máy, ngoài tests tạo QApplication/provider. Non-null fallback
pixmap không tự chứng minh đã lấy đúng app icon. Ghi nguồn/version/license của
icon pack đã nhập để xác nhận provenance của tuyên bố "Lucide chính thức".
Đây là giới hạn bằng chứng, chưa kết luận gói icon đang chạy lỗi.

## Kế hoạch trải nghiệm tiếp theo

Người dùng đã chọn một mục **Ứng dụng với lưới icon lớn, bấm để mở**. Thiết kế
ba trạng thái và phạm vi triển khai được thêm vào chính
`docs/rat_cot_end_to_end_next_20261022.md`, không tạo UI/launcher hoặc bản kế
hoạch sản phẩm thứ hai. Chưa sửa code UI cho grid. Giữ tìm theo tên đang tốt;
lưới là cách duyệt thêm trong cùng Quick, dùng lại catalog và đường mở app.

Sau khi Anti hoàn tất, nghiệm thu một gói trên cùng UI Quick: tìm app với icon
thật → chọn tệp/context → hỏi tiếp → nhận public claims/source evidence và đúng
trạng thái kiểm tra → hủy/đóng an toàn. Tách fixture, native UI và model-quality
evidence. Ngân sách model thật vẫn 0, Stage 0/data review không đổi.
