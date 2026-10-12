# NeSy-DocAI được gom vào dự án này

Ngày chuyển: 2026-10-12. Nguồn: `Thundercok/nesy-docai`, commit
`8e5533b6f376d32481dcfbc1762daf21bf260c65`. Thư mục nguồn là
`SoftwareEngineering2026`, với alias `nesy-docai`.

## Phạm vi đã chuyển

| Thành phần nguồn | Vị trí trong repo này |
| --- | --- |
| Toàn bộ thư viện Python và Swift OCR | `nesy_docai/` |
| Chín file tests gốc, chỉnh đường dẫn và cô lập output | `tests/nesy_docai/` |
| API, Streamlit, CLI cũ, notebook, generators | `integrations/nesy_docai/` |
| ZIP ảnh được tạo bằng PIL và ZIP rỗng gắn nhãn CORD | `integrations/nesy_docai/fixtures/` |
| README gốc với các claim chưa review | `integrations/nesy_docai/README.upstream.md` |
| Nguồn, commit, hash từng file và thay đổi khi chuyển | `integrations/nesy_docai/migration_manifest.json` |

55/58 file được theo dõi trong repo nguồn đã được chuyển. SQLite ledger và JSON
registry cũ không được mang vào: chúng là trạng thái cục bộ, không phải source
hay benchmark. `.gitignore` nguồn được thay bằng cấu hình repo đích. Repo nguồn,
alias và lịch sử Git vẫn còn để đối chiếu. Lượt chuyển không thay đổi remote,
không push và không archive/xóa repo GitHub.

## Luồng dùng được từ repo này

```bash
python -m pip install -r requirements-docai.txt
python -m nesy_docai /path/to/invoice.xml --output /path/to/NEW_review.json
python -m nesy_docai /path/to/invoice.png --output /path/to/NEW_review.csv --format csv
python -m nesy_docai /path/to/invoice.pdf --output /path/to/NEW_review.xlsx --format xlsx
python -m nesy_docai /path/to/invoice_directory --output /path/to/NEW_reviews.json
```

`python -m nesy_docai --help` chạy mà không cần Z3. Có thể kiểm tra các trường
đã trích xuất riêng bằng `--fields-json`; JSON đầu vào là một object chứa
`subtotal`, `tax`, `total`, `currency` (mặc định `VND`), và `line_items` tùy chọn.
Khi cung cấp dòng hàng, mỗi dòng cần `quantity`, `unit_price`, `amount`.

Output chỉ chứa **giá trị ứng viên cần review**. JSON giữ trường đầu vào, chữ đã
đọc, token OCR/bbox nếu có, SHA-256 của file và model Z3. CSV/Excel là bảng tóm tắt
ứng viên; dùng JSON khi cần toàn bộ evidence. Không ghi đè file output có sẵn.
Exit code 0 nghĩa tất cả bản ghi có một nghiệm SAT; 2 nghĩa có bản ghi cần xử lý
thêm (INCOMPLETE/UNSAT/TIMEOUT/OCR_FAILED/ERROR); 1 là lỗi dependency hoặc output.
Mọi trạng thái đều có `review_required=true`.

Luồng hỗ trợ không gọi model/server, không tạo audit ledger và không tự duyệt
hóa đơn. Ngưỡng Z3 mặc định 1.000 ms, file tối đa 25 MiB và PDF mặc định đọc 25
trang đầu. Output báo khi PDF bị giới hạn số trang. Khi có nhiều hóa đơn/nhãn
tổng tiền trong một file, parser văn bản để trường bị lặp ở trạng thái thiếu.

Ảnh dùng Swift + Apple Vision trên macOS, rồi Tesseract `vie+eng` làm fallback.
Tesseract executable và language data cần cài riêng nếu dùng fallback. PDF có
text dùng pypdf; PDF không trích được text trên macOS có thể dùng PDFKit/Vision
của RAT khi PyObjC có sẵn. PDF scan trên hệ khác và các trang scan xen kẽ text
chưa được xử lý đầy đủ. Lượt chuyển chưa đo chất lượng của các engine này.

## RAT

Capability `invoices` đăng ký thao tác `inspect_invoice` qua kernel đang có.
Người dùng tìm file bằng `search_documents`, rồi yêu cầu đọc/kiểm tra hóa đơn.
Thao tác cần một đường dẫn chính xác đã có trong chỉ mục; không quét toàn máy.
Kết quả có artifact `invoice_inspection` và view gồm trường đọc được, ứng viên,
ghi chú cần đối chiếu bản gốc. Đây là đăng ký công cụ và kiểm tra luồng thực thi;
chưa đo khả năng model chọn công cụ đúng trên câu hỏi thật.

Dependency được nạp khi gọi; import RAT/package không nạp Z3, model, Qt hay
ledger cho tính năng này. Máy chạy RAT cần cài `requirements-docai.txt` để giải
Z3. Chưa build/kiểm tra lại bản app đóng gói với dependency và Swift toolchain.

## Những giới hạn phát hiện ở nguồn

- Qwen-VL intake là stub, chưa có implementation trích xuất.
- `RealWorldDatasetLoader` trả hai dict viết sẵn; không tải release CORD/MC-OCR.
  Mẫu đã được gắn nhãn synthetic ở bản chuyển.
- Benchmark lặp cùng một bài toán, chèn baseline 78,5% và LCR 100% cố định.
  Bản chuyển bỏ baseline/STP chưa đo, tính LCR trên fixture và gắn nhãn
  `synthetic_smoke`. Timing chỉ gồm candidate generation và solver.
- Vision compatibility layer dựng một dòng hàng cùng bbox cố định. PDF dummy
  renderer vẽ ảnh minh họa. Luồng `service.py` dùng token thực được engine trả,
  giữ thiếu dữ liệu và không dùng các bbox/dòng hàng dựng sẵn đó.
- XML compatibility reader từng suy ra trường thiếu, đặt quantity/price mặc
  định và gắn `VERIFIED_XML_DIRECT`/confidence 1,0. Luồng mới chọn chế độ giữ
  trường gốc, không suy ra các tổng tiền còn thiếu, không xác thực chữ ký/schema.
- Lattice compatibility layer có fallback giữ amount khi không khớp quantity ×
  price. Luồng mới yêu cầu giao của amount và tích các giá trị ứng viên.
- SAT chỉ chứng minh tồn tại một bộ số thỏa các ràng buộc prototype. Chưa kiểm
  tra nghiệm duy nhất, chọn theo xác suất, tính đúng của OCR hay tính xác thực.
  Các mức thuế 0/5/8/10% và dung sai 2 VND là cấu hình prototype, không phải
  chứng nhận pháp lý/thuế. Currency ngoài VND và các số thập phân chưa hỗ trợ.
- Fraud score, test MST ngoại lệ và workbench approval cũ vẫn là code
  compatibility cần review riêng; chúng không được dùng bởi thao tác RAT mới.

API/dashboard cũ cần `requirements-docai-ui.txt` nếu tiếp tục phát triển.
Giữ chúng để tham khảo; luồng hỗ trợ hiện tại là CLI mới và capability RAT.

## Kiểm tra và quan hệ với NCKH

```bash
python -m pytest tests/test_docai_integration.py tests/nesy_docai tests/test_interaction_kernel.py tests/test_interaction_kernel_regressions.py -q
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Compatibility tests cô lập ledger/output trong tmp. Live OCR trên ảnh PIL
synthetic là opt-in (`NESY_RUN_LIVE_OCR=1`); Streamlit tests cần dependency riêng.
Kết quả smoke/pytest là kiểm tra phần mềm, không là độ chính xác OCR/model.
Xem `audit/nesy_docai_migration_20261012/validation.json` cho kết quả thực chạy.

OCR/DocAI phục vụ demo RAT. Entry point nghiên cứu vẫn là
`python -m experiments.research_study`; không nhập hóa đơn hay fixture DocAI vào
train/calibration/test của nghiên cứu reasoning. Không đổi RQ, Stage 0 hay gate
publication. Đánh giá DocAI trên tài liệu thật cần bộ dữ liệu và protocol riêng.
