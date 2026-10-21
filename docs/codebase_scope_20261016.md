# RAT–CoT: một hệ thống, snapshot sau khi tách Spider

Ngày đo: 2026-10-16. **RAT sử dụng CoT; CoT được triển khai và thể hiện bằng RAT.**
Bản đồ vai trò không tách ứng dụng và phương pháp thành hai dự án. Harness là
công cụ đánh giá cùng phương pháp; tests và giao diện có vai trò trong hệ đó.

## Số đo hiện tại

| Phạm vi | Tệp source | Dòng không trống |
| --- | ---: | ---: |
| Hệ RAT–CoT: app, reasoning, hạ tầng, scripts, harness và tests | 359 | 85,561 |
| Dự án riêng còn nhúng: EVRP, DocAI, watch bot | 314 | 33,083 |
| Mã sản phẩm trong snapshot | 673 | 118,644 |
| Bản sao audit, mã cũ và thiết kế | 403 | 146,932 |
| Toàn bộ source Git-visible theo quy tắc đo | 1,076 | 265,576 |

Trong hệ RAT–CoT, phân nhóm theo vai trò:

| Vai trò | Dòng không trống |
| --- | ---: |
| Tương tác RAT (UI / OS / CLI) | 22,226 |
| Suy luận & điều phối (engine và reasoning nền) | 13,810 |
| Công cụ & đọc nguồn (kernel / crawler / PDF-OCR chung) | 5,314 |
| Chạy, scripts hỗ trợ & đánh giá | 21,786 |
| Tests hệ thống | 20,684 |
| Tiện ích lịch / astrology trong RAT | 1,737 |
| Thiết lập | 4 |

Đây là phân loại quản lý theo path/import heuristics, không xác nhận mọi file
thuộc đóng góp paper hay mọi policy trong app và harness đã tương đương.
`rat/ui/omnibar.py` có đường gọi `rat.engine.meta_reasoner.meta_reasoner.solve`;
`meta_reasoner.py` import `EntryPredictor` và `OptimalStoppingPolicy`. Đó là
kết nối triển khai quan sát trong source, không phải đo chất lượng model.

Spider đã được gỡ khỏi cây source: 269 file Rust / 123,868 dòng không trống,
321 file tracked và 325 regular files. Đây là mức gỡ gross của cây Spider, không
phải net delta của toàn repo giữa hai ngày. Các chat khác đã thêm source/tests
và nhiều bản lưu trong audit; vì vậy tổng dòng source trên đĩa có thể lớn hơn
snapshot 2026-10-14 dù Spider đã ra khỏi repo. Không dùng tổng đó để kết luận
implementation chính tăng tương ứng hoặc đợt tách không có tác dụng.

## Cách đo và giới hạn

Đếm tệp regular tồn tại trong `git ls-files --cached --others --exclude-standard`,
không đếm tệp đã gỡ dù deletion chưa commit. Đếm dòng vật lý không trống, gồm
comments/docstrings; không phải authored LOC, độ phức tạp hoặc thời gian cần làm.
Loại `work/`, `.migration-backups/`, outputs, môi trường/build/cache bị ignore,
vendor `wwwroot/lib`, minified JS/CSS và riêng `scratch/build_spider/`.

Build scratch này chứa thêm bản sao source và khoảng 2.01 GB generated material;
không tính nó thành source sản phẩm lần nữa. Binary Spider khoảng 20.7 MB,
recovery bundle và staging vẫn giữ riêng. Không tuyên bố đã dọn disk/cache.
`audit/` riêng có 141,058 dòng source, chủ yếu bằng chứng/source snapshots; giữ
trong mục evidence, không coi là mã ứng dụng cần refactor. 5,541 dòng legacy
phải rà từng dependency: `pipeline.MockDemoBackend` vẫn dùng trong smoke.
333 dòng HTML dưới docs là thiết kế, không phải product runtime.

Scanner phân tích 824 Python files trong snapshot, không có syntax parse failure.
Exact-byte duplicate scan phát hiện 10,974 dòng copy dư trong EVRP. Không suy ra
các phần giống chức năng là byte-identical hoặc có thể xóa mà không kiểm tra.

## Hướng gom gọn tiếp — đề xuất, chưa di chuyển mã

1. **EVRP:** 247 file source / 26,903 dòng, dự án riêng lớn nhất còn nhúng. Rà
   phần có ích cho RAT nếu có, bảo toàn local changes, rồi tách repo. Không nhận
   bảo trì các bản coursework lặp trong main project.
2. **DocAI:** 53 file / 5,195 dòng; nghiệp vụ hóa đơn standalone/backlog. Giữ
   `document_intake/` dùng chung, không mang hóa đơn/Z3 vào RAT theo quán tính.
3. **Watch bot:** 14 file / 985 dòng; xử lý theo cùng quy trình tách.
4. **Trong hệ RAT–CoT:** làm rõ một đường đi từ request → reasoning/controller →
   tools/verifier → kết quả; đánh giá bằng harness. Có thể gom các reasoning
   primitives rải ở root về namespace chung trong tương lai, nhưng phải rà
   imports, serialization và harness contracts trước khi đổi path. Không tạo
   implementation CoT thứ hai chỉ để đổi cấu trúc folder.
5. **Evidence:** giữ một chỉ mục rõ tới artifacts và snapshots, không xóa raw
   evidence để giảm LOC. Việc lưu trữ dài hạn hay chuyển archives cần kế hoạch
   riêng giữ khả năng tái lập; không trộn với dọn product source.

Không sửa runtime, chạy campaign model, đổi Stage 0 hoặc Git publish trong đợt
visualize này. Scanner/data và browser verification nằm trong
`audit/codebase_scope_20261016/`; script hỗ trợ ở `work/codebase-audit-20261016/`.
