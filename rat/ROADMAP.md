# Lộ trình RAT bản chính

RAT phải vui khi dùng, vui khi táy máy, và nhanh hơn Persona 5. Lấy cái P5 làm hay (mỗi lệnh một nút, không lục menu,
chi tiết nhỏ nào cũng có hồn), bỏ chỗ nó bắt người chơi chờ.

## Luật cho mỗi bước

1. Một bước đổi đúng một thứ thấy được, một commit, bỏ riêng được.
2. Hành động chạy ngay khi nhấn phím. Hiệu ứng chạy song song, dưới 120 ms, bị ngắt khi có thao tác mới.
3. Không có chức năng nào phụ thuộc vào phần táy máy.
4. Giữ chất giấy và con chuột, không dọn về tối giản. Lite đã chuyển sang repo `offline-tool-routing-agent`; từ đó chỉ lấy logic.
5. Có bằng chứng: phím thật qua giao diện, số đo hoặc ảnh và video. Duyệt xong mới sang bước sau.

## 0. Vá sau đợt kiểm tra 2026-11-03

Đã xong cả bước 0: 0.1, 0.2 và 0.4 ở `183ad498`, `442c35cb`, `7c40e42e`; 0.3 do người dùng bấm thử thật, cả hai phím đều chạy.

| # | Bước | Xong khi |
| --- | --- | --- |
| 0.1 | Nhận diện câu hỏi không bắt nhầm từ đầu câu: `ai`, `sao`, `do` | "AI ethics report", "sao chép file", "do an tot nghiep" đi vào tìm; "ai là tác giả" vẫn đi vào hỏi |
| 0.2 | `python -m rat.main --document x.pdf` và `--dark` mở bàn một cửa sổ như trước | Tham số không còn bị bỏ qua |
| 0.3 | Bấm thử thật ⌃⌥Space và ⌥⇧R | Bàn hiện/ẩn, đoạn bôi đen được dịch từ app khác |
| 0.4 | Hết crash khi chạy riêng `tests/test_quick_finder_flow.py` (lỗi trong `QQmlAnimationTimer`, có từ trước đợt sửa) | File chạy riêng đạt nhiều lần liên tiếp |

## 1. Nhanh: mỗi lệnh một phím

1.1 đã xong: `tools/measure_desk_latency.py`, số nền ở `tools/desk_latency_baseline.json`. Sau mỗi bước đổi giao diện, chạy với `--compare`.

| # | Bước | Xong khi |
| --- | --- | --- |
| 1.1 | Script đo độ trễ: gọi bàn đến lúc gõ được, Enter đến lúc mở | Có số nền, các bước sau không được làm tệ hơn |
| 1.2 | ⌘1, ⌘2, ⌘3 mở thẳng kết quả tương ứng | Chạy cả khi ô nhập còn chữ, số hiện ngay trên dòng |
| 1.3 | Gợi ý phím ở ô nhập dùng `KeycapBadge` | Thấy phím thật thay vì chữ `↵` |
| 1.4 | Esc luôn lùi đúng một bước | Từ mọi màn, không mất chữ đang gõ |

## 2. Thông minh hơn

| # | Bước | Xong khi |
| --- | --- | --- |
| 2.0 | Index đọc đúng tài liệu thật: bỏ qua repo code, ưu tiên PDF và Office, ghi dần ngay khi quét, dùng `config.indexed_directories` | Trên máy thật có PDF được index trong phút đầu (đo 2026-11-03: quét 63 giây mới bắt đầu, trần 5.000 file có 4.709 `.txt`, chỉ 14 PDF) |
| 2.1 | Công cụ tìm của Chuột dùng index theo nghĩa | "tiền cọc phòng trọ là bao nhiêu?" trả lời từ file có sẵn và chỉ rõ file |
| 2.2 | Ngăn tiếng Trung từ gốc, thử lại chỉ là lưới an toàn | Bộ câu tiếng Việt không còn kích hoạt thử lại |
| 2.3 | Dán đoạn văn vào ô nhập là dịch, dùng lại nhận diện đoạn văn của `goal_routing` | Đoạn tiếng Anh dài ra bản dịch, không qua model |
| 2.4 | Thả hoặc dán ảnh chụp để OCR rồi dịch, lấy `rat/ui/image_*.py` từ tag `rat-lite-0.6.0` | Ảnh chụp đoạn PDF ra bản dịch |
| 2.5 | Tiến độ index hiện ở dòng trạng thái | Biết đang đọc tới đâu, ẩn khi xong |

## 3. Có hồn: từng chi tiết

| # | Bước | Xong khi |
| --- | --- | --- |
| 3.1 | Thông báo và lỗi cùng một giọng Chuột | Hết kiểu "Đã vượt hạn mức ngân sách xử lý" |
| 3.2 | Nhấn có độ lún, sửa một chỗ trong `QuietButton` là lan khắp bàn | Đo vẫn trong ngân sách 1.1 |
| 3.3 | Nhãn "Ứng dụng" thành nhãn dán, đường dẫn gọn lại | Dòng kết quả hết giống bảng dữ liệu |
| 3.4 | Dòng đang chọn có nét gạch tay | Nhìn ra ngay, không che chữ |
| 3.5 | Tờ giấy nhích nhẹ khi có kết quả, mỗi lần lệch một chút | Không hai lần giống hệt, không làm chậm |

## 4. Táy máy

| # | Bước | Xong khi |
| --- | --- | --- |
| 4.1 | Kéo xấp giấy có độ nảy | Thả ra nảy, không lệch khỏi màn hình |
| 4.2 | Chọc chuột nhiều lần có phản ứng khác cú lắc hiện tại, chưa cần sprite mới | Bỏ qua vẫn dùng đủ |
| 4.3 | Ném tờ giấy đi để bỏ kết quả | Có phím tương đương |

## 5. Để sau

- Chuột đổi tư thế theo việc đang làm: chờ sprite vẽ xong. `MascotPose.qml` và `SpeechSurface.qml` còn ở tag `rat-lite-0.6.0`.
- Dọn các gói `astrology`, `divination`, `timetable` khỏi lúc khởi động.
- Đưa `structured_llm` vào RAT: khai báo trong `tests/test_repo_boundaries.py` khi tới lúc.
