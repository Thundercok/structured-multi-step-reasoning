# Shared image → captured text → translation contract

Trạng thái M5.7: source M5.5/M5.6 đã được gom cùng phần ổn định hóa/UI thu gọn;
đang chuẩn bị gói M5.7 và screenshot thật theo yêu cầu người dùng. Chưa nghiệm
thu trên máy người nhận. ZIP M5.4 không chứa thay đổi M5.5/M5.6/M5.7.

## Ranh giới tái sử dụng

`rat/kernel/input_context.py::ImageInput` không import Qt hoặc Mini. Nó giữ
snapshot bytes bất biến, ID cho từng lần nhập, origin, hash nội dung và hash
file gốc nếu có. Bytes không hiện trong repr và không đưa vào model arguments.
Hash file gốc là thông tin do adapter đầu vào ghi nhận; hash ảnh chuẩn hóa tính
trực tiếp trên snapshot. Hash không chứng minh nguồn ảnh đáng tin hay OCR đúng.

`rat/ui/image_input.py` là adapter Qt: đọc file có giới hạn, decode/chuẩn hóa
PNG, tạo ImageInput. Drop/file paste/pixel paste được ghi nguồn khác nhau.
Main dùng Qt có thể dùng lại adapter; client khác có thể tạo ImageInput riêng.
Tool boundary vẫn kiểm tra kích thước và khả năng đọc ảnh qua Pillow.

`rat/engine/capture_translation.py::run_capture_translation` là choreography
headless dùng chung. Client truyền adapter session có `execute` và `router`;
không import MiniSession, Qt, OCR provider hay HTTP provider. Nó gọi các tool
qua service, dùng artifact thực tế và revision chính xác, giữ callback events,
progress/cancel. Hủy sau OCR được đối chiếu trước bước dịch. Không lấy lại
Clipboard, đọc lại file hay tự thay source_ref khi chờ trả lời ngôn ngữ.

## Dataflow

1. UI chuẩn hóa ảnh → ImageInput trong trusted execution context.
2. `capture_text(mode=image)` kiểm tra bytes/ảnh → Apple Vision OCR.
3. Captured artifact: text, text hash, mode, timestamp, input provenance.
4. Result contract + CaptureVerifier đối chiếu cấu trúc/hash/giới hạn.
5. Workflow lấy artifact ID/revision rồi gọi `translate_text(source_ref)`.
6. Translation handler đối chiếu hash text hiện tại với artifact trước khi
   gọi provider; nguồn hết hạn hoặc lệch hash thì báo lỗi.
7. Translation artifact giữ `source_capture` (pin, text hash, provenance).
   TranslationVerifier kiểm tra hash/coverage và pin khớp requested source_ref.
8. Mini UI chỉ trình bày kết quả, thêm nhãn “Ảnh kéo thả”/“Ảnh đã dán”.

Workflow trả cả capture response và final response. Khi người dùng chủ động bật
acceptance recording, worker giữ riêng captured artifacts và capture verification
cùng translation artifacts/reports; không chỉ ghi báo cáo của bước cuối. Mặc định
không lưu ảnh hoặc bật recording. Metadata không chứa bytes ảnh hay đường dẫn file.

Hai checker là kiểm tra cấu trúc/toàn vẹn, **không** xác nhận chữ OCR đúng với
pixel hoặc bản dịch đúng nghĩa. Không có benchmark chất lượng model hay thay
đổi Stage 0. Registry/service có dây nối không phải bằng chứng vòng model chạy.

## Hiệu chỉnh OCR và retry (M5.6-dev)

- Callback `on_captured(artifact, translation_args)` chuyển snapshot OCR đã
  quan sát được về UI trước khi provider dịch hoàn tất. Chữ vẫn hiện nếu dịch
  lỗi, kèm nút thử lại. UI giữ bản OCR ban đầu và bản nháp đang sửa riêng nhau.
- `correct_captured_text(source_ref, text)` là tool trong translation capability,
  không model-visible và yêu cầu user_initiated. Nó đối chiếu nguồn cũ, tạo
  artifact **mới** có text_origin=user_edit, hash chữ mới, parent_ref/hash,
  root_source_ref/original_text_sha256 và edited_at. Không sửa artifact cha.
- `run_corrected_translation` là workflow headless qua service/dispatcher:
  ghi nhận correction → pin artifact mới → dịch. Mỗi lần sửa tiếp tục tạo
  artifact mới; bản OCR gốc và các lần sửa giữ được liên kết trong session.
- Chữ không đổi: retry chỉ gọi translate_text với source_ref hiện tại. Không
  OCR lại, không đọc lại ảnh/Clipboard. Chữ đổi: tạo correction rồi dịch.
- Nếu dịch lỗi sau correction, callback đã giữ nguồn sửa mới; lần retry tiếp
  theo dùng nguồn đó mà không tạo correction trùng chỉ vì lỗi mạng.
- Draft khác chữ đã gửi thì ẩn bản dịch/copy cũ cho đến khi dịch lại hoặc hoàn
  nguyên draft. Xem OCR ban đầu không ghi đè draft.
- Cancel/generation vẫn chặn tác vụ cũ thay kết quả mới. Nguồn hết hạn hoặc
  nguồn hết hạn cần nhập lại ảnh. M5.7 thay provider/session adapter vẫn dùng
  chung artifact store nên giữ được source_ref và chữ đang sửa. Finder UI pins
  được xóa và file actions tiếp tục kiểm tra scope mới. Đây là lịch sử trong
  session, chưa có lưu lịch sử bền vững.
- `CaptureCorrectionVerifier` kiểm tra text/hash/pin của lần sửa. Source capture
  và correction response được giữ riêng trong recording khi chủ động bật.

Main có thể gọi cùng correction tool/workflow; chưa nối UI main. Các cơ chế này
không tự huấn luyện hay học model từ phần người dùng sửa.

## Phần main chưa được nối

Main chưa có DropArea/clipboard ingress gọi workflow này. Cần composition/profile
đăng ký translation capability, adapter session/router và projection trạng thái
của main; không copy choreography trở lại UI. Chưa kiểm chứng main integration.

## AC để chạy khi người dùng yêu cầu test

- Ảnh thật đi từ drop/file paste/pixel paste tới cùng tools, giữ đúng origin.
- File gốc và PNG chuẩn hóa có digest riêng; bytes/path riêng tư không vào tool args.
- Source_ref/revision/hash khớp từ captured artifact tới translation artifact.
- Text bị sửa trong artifact hoặc nguồn hết hạn phải lỗi trước khi gọi provider.
- Hủy sau OCR không gọi dịch; hủy/thay input không hiển thị kết quả task cũ.
- Ảnh hỏng/quá lớn không đi tới OCR/cloud; không dùng Clipboard cũ thay thế.
- So sánh headless và UI trên cùng nguồn thật sau khi tích hợp main.
- OCR hiển thị trước khi mạng trả kết quả; lỗi mạng vẫn giữ bản gốc và draft.
- Sửa nhiều lần phải tạo chuỗi artifact mới, root/parent/hash đúng, bản gốc giữ nguyên.
- Retry chữ không đổi không gọi OCR/correction; retry sau lỗi mạng không nhân bản correction.
- Draft chưa gửi không hiển thị/copy bản dịch cũ như kết quả của draft mới.

Đây là danh sách kiểm chứng dự kiến, chưa phải kết quả chạy.

## Explicit screen region — source revision 2026-10-28

Người dùng chủ động chọn vùng qua macOS; `capture_text(mode=region)` tạo snapshot
`screen_region` với cùng giới hạn 12 MB / 25 triệu pixel. Callback trong trusted
execution context giữ snapshot trong bộ nhớ để UI xem ảnh sau khi capture được
kiểm tra; bytes không vào arguments gửi model hoặc artifact. Artifact chỉ giữ
provenance/hash và chữ OCR. OCR và dịch vẫn qua service, dispatcher và verifier
chung; verifier kiểm tra cấu trúc, không xác nhận nghĩa. Nếu hủy trước khi capture
thành công, Mini giữ phiên và draft cũ. Revision này chưa được chạy kiểm chứng.
