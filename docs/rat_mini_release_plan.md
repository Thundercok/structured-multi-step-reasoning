# RAT Mini → nghiệm thu → RAT chính

Quyết định người dùng 2026-10-27: triển khai từng bước theo plan đã chốt,
ưu tiên ổn định/dễ dùng cho người nhận, nghiệm thu Mini trước khi tích hợp main.
Người dùng yêu cầu screenshot thật của app hoàn thiện: mặc định, dịch ảnh,
sửa chữ/dịch lại và Finder. Không dùng mockup/canned response làm evidence.

## Bước 1–3: ứng viên M5.7

- Mặc định: chuột + composer; dịch xong ưu tiên bản dịch và Sao chép/Sửa chữ.
- Editor mở khi người dùng cần sửa, hoặc dịch lỗi/partial/thiếu input.
- Nhãn tiếng Việt dễ hiểu; provider/fallback ở menu Chi tiết bản dịch. Cảnh báo
  ảnh hưởng nội dung (ví dụ thay đổi chữ số) vẫn hiện ngay trên kết quả.
- Giữ chữ, nguồn và các correction artifacts khi retry hoặc đổi provider.
- Lỗi quota/auth/timeout/TLS/network được chuẩn hóa không kèm URL/chữ riêng tư.
- Cấu hình cũ sai kiểu được đưa về default an toàn; mở thêm gửi yêu cầu hiện app
  đang chạy qua IPC UI-only. Chưa được gọi là pass trước khi kiểm chứng thật.

## Bước 4: đóng gói và evidence hình ảnh

Gom các thay đổi vào một app/ZIP rõ version. Đóng gói trước, rồi chỉ thực hiện
các luồng thật cần cho bốn screenshot đã được yêu cầu. Giữ failures và raw
responses; không thay backend bằng fixture. Không chạy suite rộng. Đầu vào
screenshot công khai; Finder dùng file thật, PDF có provenance khi áp dụng.

Screenshot phải nêu đúng bản đang chạy. Nếu chỉ paste được mà chưa drag/drop
được thì ghi rõ cách nhập, không suy ra drop đã đạt. Nếu máy khóa hoặc backend
không chạy được thì ghi blocker, không tạo ảnh thành công giả.

Tiến độ live 2026-10-27: M5.8 đã OCR/dịch thật một ảnh dán từ Preview qua
MyMemory, rồi gặp quota ở lượt sau. Retry sau sửa OCR lộ lỗi hợp đồng kết quả;
M5.9 sửa bằng schema capture dùng chung và qua 2 regression hẹp, chưa tính là
UI acceptance. Công cụ Finder timeout nên thumbnail/drop vẫn chưa xác nhận.
Trace tìm file nhận `tm BEST-Route.pdf` do công cụ gõ mất dấu; cần thử lại tên
ASCII chính xác. Spotlight ngoài sandbox đang bật và tìm thấy PDF provenance.
Các ảnh chụp không khớp AX đã được đánh dấu, giữ raw và không dùng làm bằng
chứng thành công. Xem audit M5.8/live và M5.9 cho kết quả mới nhất.

## Bước 5: nghiệm thu trên máy người nhận

Máy M3 8 GB, ghi phiên bản macOS thật. Mở không cần Python/Terminal; screenshot
→ drop → dịch → sửa → dịch lại; Finder tìm/mở file thật; mất mạng/retry và
cancel/replace; ẩn/hiện/thoát/mở lại. Chỉ thử lại phần thất bại sau sửa.

Free translation còn quota/rate limits; key hoặc dịch vụ mặc định phải chốt
trước bàn giao. App đang ký ad-hoc/chưa notarize; không claim hết cảnh báo mở
lần đầu. Không nhúng key vào app. Người nhận dùng gói nghiệm thu cố định.

## Bước 6–7: tích hợp main rồi nghiệm thu lại

Tích hợp shared input contract, capture/correction/translation tools, workflow,
verifier và UI components. Gỡ phần phụ thuộc cấu hình Mini khi nối main;
đối chiếu tool Finder trùng chức năng, chọn implementation chuẩn. Nối session/
router adapter theo capabilities của main, giữ chức năng main hiện có.

Main UI chưa nối. Sau nghiệm thu Mini mới thực hiện integration và chạy lại
cùng dữ liệu thật trong main, cả gesture trực tiếp và hội thoại Agent thật.
Nêu rõ direct routing và real-model loop; không suy ra model đã đạt từ registry.
Không thay đổi Stage 0 hoặc dùng app acceptance làm kết quả chất lượng nghiên cứu.

## Kết quả hẹp M5.9 sau mở khóa

Tìm/mở PDF thật đã đạt trong phạm vi kết quả trả về; còn 2 scope timeout.
OCR ảnh dán và correction artifact/verification đã đạt trên UI thật. Cloud
dịch ban đầu/retry đều rate limited, draft còn nguyên. Native drop chưa được
xác nhận do Finder automation timeout; Mac khóa lại khi chuẩn bị screenshot
sau retry. Hai screenshot khớp (Finder/editor) và raw traces nằm tại
`audit/rat_mini_m59_20261027/live/`. Không gọi Mini stable hoặc chuyển sang main
trước khi đóng các gate còn lại; 0 LLM calls không chứng minh model loop.

## Quyết định miễn phí / plug-and-play, 2026-10-27

Người dùng chọn giữ miễn phí; cấu hình key chỉ là tùy chọn. M5.11 đóng kèm cặp
Anh↔Việt để không lệ thuộc quota web cho luồng cơ bản; cặp khác vẫn dùng online.
Không đòi người nhận cài runtime/model/server. Xem contracts/local_translation.md
và audit M5.11 cho số đo thật, provenance, lỗi ban đầu và trạng thái UI. M5.10
đã build checkpoint trước khi đổi hướng, chưa coi là bản bàn giao đã nghiệm thu.
