# Review bản xem turn notes, giai đoạn 1

2026-10-12, Asia/Saigon. Review source và 4 ảnh trạng thái do Antigravity tạo,
chạy lại các tests UI và thử thêm các tình huống tương tác. Chưa sửa code app
hoặc prototype; chưa duyệt để chuyển giai đoạn 2.

## Quyết định mới đã chốt với người dùng

**Ghi chú là dòng chữ nhẹ liền với phản hồi, chỉ mở khung khi sửa.** Giữ lựa
chọn trước: bản cũ giữ nội dung, nhãn đã thay thế/link tới bản mới; Chuột lớn
bên trái và chuyển động vui vừa; chạm Chuột emote và dẫn tới ghi chú.

## Kết luận

Bản xem làm đúng việc đặt note trong từng lượt và minh họa link giữa các
revision, editor, tombstone/undo và proposal. Dữ liệu được ghi rõ là fixture.
Tuy nhiên, note còn là các hộp nền/viền riêng và compact rộng gần bằng full,
nhiều khoảng trống. Cần tinh chỉnh đúng lựa chọn mới và sửa các ca UX dưới
đây trước khi duyệt chuyển bước.

15 file implementation trong manifest của đợt companion trước khớp SHA256.
Prototype dùng các file mới riêng; app chính vẫn dùng NotebookPane. Kết quả
này không xác thực việc bảo toàn 100% mọi file trong toàn working tree.

## Kết quả kiểm tra và giới hạn

`tests/test_turn_notes_preview.py tests/test_work_context_ui.py`: **17 passed**.
Log riêng của reviewer: `tests.txt`. Chưa chạy lại 29 research tests vì review
không đổi research harness. Không xác nhận lại con số tổng 46 trong báo cáo
Antigravity. Tests/fixture không chứng minh năng lực model hoặc Stage 0.

`reproduce.py` dùng widget prototype thật với fixture; output `reproduce.txt`.
Không gọi Ollama, không index tệp cá nhân, không sửa state của RAT đang chạy.

| Finding đã tái hiện | Mức độ | Cần sửa |
| --- | --- | --- |
| Mở editor lượt 2, gõ draft, chuyển compact: text còn nhưng editor bị ẩn và mất focus | P2 | Giữ lượt đang sửa được reveal, editor/focus/caret/selection và đường quay lại; toggle không làm đổi đối tượng đang sửa. |
| Bấm “Sửa bản mới” trên note cũ chỉ điều hướng, editor bản mới không mở | P2 | Tách intent xem/sửa; action sửa điều hướng và mở editor đúng bản đang dùng. |
| Sửa note 30→35, link ở note cũ vẫn ghi “20 → 30 phút” | P2 | Snapshot cũ giữ 20; metadata/link tới bản đang dùng phản ánh đúng revision/value mới. |
| `ratReduceMotion=True` nhưng highlight animation vẫn Running | P2 | Tôn trọng motion setting cho highlight; giữ dấu nhận biết tĩnh, không chạy animation. |

Source liên quan:

- `rat/ui/turn_notes_preview.py:497`: toggle xóa revealed turn rồi chọn lượt cuối.
- `rat/ui/turn_notes.py:441`: sửa note replaced chỉ emit navigate rồi return.
- `rat/ui/turn_notes_preview.py:586`: save mutate note hiện tại, không refresh
  metadata forward link của predecessor.
- `rat/ui/turn_notes.py:309`: highlight luôn start animation.

Hai test highlight (`tests/test_turn_notes_preview.py:75` và `:158`) có nhánh
`highlight_ratio >= 0.0`: giá trị ban đầu là 0 nên assertion có thể pass dù
không highlight. Cần kiểm tra đúng target và visibility/reading position;
animation/static cue tùy motion setting. Test mode đang kiểm tra visibility
ở trạng thái không sửa, chưa kiểm tra editor/focus khi toggle.

## Feedback về thiết kế

| Khía cạnh | Quan sát | Hướng tinh chỉnh |
| --- | --- | --- |
| Thứ tự đọc | Reply → note → trace phù hợp; note nằm cùng scroll của chat. | Giữ thứ tự, giảm nền/viền và số lớp hộp theo lựa chọn người dùng. |
| Mật độ | Note có tag, hộp, link và controls luôn cạnh nhau; debug dock chiếm hàng lớn. | Dòng nhẹ, metadata mở tại chỗ; controls vẫn truy cập bằng bàn phím; dock QA ẩn/collapsible khi duyệt UI. |
| Compact | Ảnh compact rộng 900px, full 980px; nội dung ngắn nhưng cửa sổ cao và trống nhiều. | Preview dùng shell/composer và kích thước gần RAT thật; grow theo nội dung, có giới hạn màn hình. |
| Lịch sử | Text cũ giữ nguyên nhưng gạch ngang gợi cảm giác bị bỏ. | Đề xuất giữ text đọc được, dùng nhãn đã thay thế/link; tình trạng bỏ ghi chú dùng tombstone riêng. |
| Chuột | Vị trí/chạm dẫn tới active note hợp với lựa chọn đã chốt. | Giữ; lời phản hồi dùng nội dung dễ hiểu, bỏ ID kỹ thuật khỏi UI. |
| Typography | `**…**` trong reply đang hiện thô; footer chạm Chuột in `note-tcp-time-v2`. | Reply render Markdown như app; note/user text hiển thị PlainText; ID chỉ ở debug/log. |
| Bàn phím/motion | Editor có Apply/Cancel shortcuts; phát hiện mất focus và motion chưa được tôn trọng đầy đủ. | Test thao tác thực và cả editor ở lượt cũ, không chỉ gọi method nội bộ. |

Đây là critique prototype; chưa audit WCAG/contrast định lượng và chưa kiểm
tra cửa sổ native. Chưa có composer thật trong preview nên các claims về giữ
draft của ô chat chưa được kiểm tra qua bản xem này.

Stale hiện là thông báo fixture được bật bằng nút QA. Revision validation và
lịch sử event thật thuộc giai đoạn 2; không gọi cảnh báo này là bằng chứng
backend đã từ chối stale write. Schema TurnNoteItem/IDs fixture cũng cần được
adapter sang note_id ổn định + revision trong contract thật ở giai đoạn 2.

## Yêu cầu gửi lại Antigravity

Tinh chỉnh giai đoạn 1, chưa chuyển backend:

1. Đổi note bình thường thành dòng nhẹ cùng nền chat, chỉ có khung lúc sửa;
   giữ nguồn/proposal/old→new/remove/undo trong cùng lượt, metadata mở tại chỗ.
2. Preview đúng shell có composer, compact/full và reading space gần RAT
   thật. Tách QA controls khỏi bề mặt duyệt; giữ nhãn fixture rõ ràng.
3. Sửa 4 lỗi đã tái hiện và bổ sung tests meaningful cho các thao tác đó;
   thay assertions highlight luôn đúng bằng kiểm tra target/visibility/cue.
4. Render Markdown reply, PlainText note/user values; không hiện ID nội bộ
   như lời nói của Chuột. Kiểm tra note dài/link dài/màn hình hẹp.
5. Xuất ảnh vào audit iteration mới, giữ ảnh/report cũ. Báo đúng phạm vi tests
   và fixture; không sửa runtime note model hoặc nghiên cứu ở iteration này.
6. Trình lại để người dùng duyệt UX trước giai đoạn 2. Giữ working tree khác,
   model mặc định và Stage 0; không push/pull/reset/force git.
