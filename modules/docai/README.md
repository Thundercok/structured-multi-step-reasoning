# DocAI — module riêng, chờ tích hợp

Module hóa đơn/OCR được giữ độc lập trong repo NeSy. RAT hiện không đăng ký
`inspect_invoice`, không import package này và không cần dependencies của nó.
Đề tài reasoning và các gate NCKH giữ nguyên. Việc tích hợp vào RAT để sau.

## Chạy độc lập

Từ repo root:

```bash
cd modules/docai
python -m pip install -r requirements.txt
python -m nesy_docai /path/to/invoice.xml --output /path/to/NEW_review.json
python -m nesy_docai /path/to/invoice.png --output /path/to/NEW_review.csv --format csv
python -m pytest tests -q
```

Từ repo root, cài bằng `python -m pip install "./document_intake[vision]" ./modules/docai`
trong environment dành cho DocAI. `document_intake` là thư viện PDF/OCR dùng chung,
không import RAT hoặc solver. Apple Vision dùng PyObjC, không còn biên dịch Swift. API/UI cũ
ở `compatibility/` cần `requirements-ui.txt`; chúng là tài nguyên compatibility
chưa được xác nhận phù hợp để dùng thật.

CLI hỗ trợ XML, PDF có text, PNG/JPG, thư mục hoặc `--fields-json`. JSON giữ raw
fields, chữ/token đọc được và ứng viên Z3; CSV/Excel là bảng ứng viên tóm tắt.
Output luôn `review_required=true` và không ghi đè file có sẵn. Mã trả về 0 là
có nghiệm SAT cho mọi bản ghi; 2 là có bản ghi thiếu/không khớp/lỗi xử lý; 1 là
lỗi dependency hoặc output. SAT xác nhận một bộ số nhất quán với cấu hình
prototype, chưa xác nhận OCR đúng, nghiệm duy nhất hay hóa đơn xác thực.

Ảnh dùng Apple Vision/PyObjC hoặc Tesseract `vie+eng`. PDF scan chưa có renderer
độc lập trong module này; parser bảo toàn trường thiếu. Không gọi RAT, model
server, tạo persistent ledger hoặc tự duyệt hóa đơn trong luồng `service.py`.
Các mức thuế và dung sai là cấu hình prototype, chưa là xác nhận pháp lý.

## Nguồn và bằng chứng

- `README.upstream.md` giữ README nguyên bản với các claim chưa review.
- `compatibility/` giữ CLI/API/Streamlit/notebook/generators cũ.
- `fixtures/` là ảnh được tạo bằng PIL và một ZIP rỗng gắn nhãn CORD.
- `local_state/` giữ ledger/output cũ tại máy, được Git ignore.
- `tests/compatibility/` giữ tests gốc; `tests/test_inspection.py` kiểm tra facade
  headless bằng fixture/mock OCR và Z3 thật. Live OCR batch là opt-in.

Adapter Qwen-VL vẫn là stub. Các mẫu “CORD/MC-OCR” là dict viết sẵn và đã được
đánh dấu synthetic. Benchmark hiện báo `synthetic_smoke`, bỏ baseline/STP chưa
đo. Pipeline/visualizer/fraud/workbench cũ có các heuristic và approval labels
chưa được review; facade hỗ trợ không dùng những claim đó.

Kết quả chuyển repo và test nằm ở
`../../audit/repository_migration_20261012/validation.json`. Smoke OCR một ảnh
synthetic từ lượt trước được giữ nguyên làm lịch sử, không phải corpus accuracy.
