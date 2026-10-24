# Kế hoạch kiểm RAT UI theo phạm vi thay đổi

Ngày: 2026-10-24, Asia/Saigon. Runner/reload và minor UI đầu đã triển khai;
đọc `rat_ui_dev_session.md` để tiếp tục. Phần dưới giữ kế hoạch và tiêu chí.
Không sửa các quyết định acceptance trong AGENTS.md. RAT–CoT vẫn là một hệ;
local UI acceptance không thay thế nghiên cứu hoặc vượt Stage 0.

Quyết định người dùng bổ sung cùng ngày: mỗi lượt phát triển UI cần một minor
change nhìn thấy được; có thể gộp diagnostics input/picker và kiểm Dừng vào
cùng lượt. Không chỉ chẩn đoán rồi tự hoãn mọi UI change. Ngân sách inference
vẫn theo đường bị đổi, giữ bằng chứng thật và giới hạn đã nêu.

## Vấn đề đã quan sát

- Một thay đổi placeholder đã khởi động lại native app/Ollama, chọn lại PDF,
  gửi một câu hỏi mới và sinh một bộ report riêng. Model request mất khoảng
  52.52 giây chỉ để trả 6 generated tokens; đây là một quan sát, không phải
  phép đo latency tổng quát.
- Nhiều script observer gần giống nhau trong work/. Việc đọc lại code/log,
  in AX tree dài, xử lý chọn file/timeout lặp lại làm tốn context Codex.
- ConversationHistory đang giữ các lượt trong RAM; chưa thấy API lưu/khôi phục
  phiên trong lớp này. Không giả định rằng restart tự giữ được hội thoại.
- Các test readiness/harness hiện có chứa doubles/fixtures, có ích cho hợp đồng
  được kiểm nhưng không là bằng chứng live UI/model acceptance.

Chi phí cần tách: context/tool output của Codex; thời gian và token model RAT;
thời gian người dùng phải mở khóa/đợi. Giảm output không tự chứng minh giảm
inference cost. Không ước lượng phần trăm tiết kiệm khi chưa đo.

## Chọn độ sâu trước khi chạy

| Thay đổi | Kiểm cần làm | Request model mới |
| --- | --- | --- |
| Chữ, màu, spacing, icon | Nhìn UI thật ở trạng thái bị ảnh hưởng; min/full khi liên quan; kiểm tràn/cắt/chồng | 0 khi giữ được phiên thật hiện có |
| Nút, phím tắt, selector, min/full | Thao tác desktop đúng control; kiểm draft/context và route; tìm/đọc bằng PDF thật | 0 nếu không đi qua assistant; tối đa 1 cho đường gửi assistant thay đổi |
| History, nguồn, routing, runtime, Dừng | Kiểm hợp đồng liên quan và các bước live bị ảnh hưởng; giữ lỗi/cancel thật | Ngân sách ban đầu 1–3, nêu rõ ca nào chưa quan sát |
| Chốt một nhóm thay đổi hoặc trước phát hành | Một luồng desktop hoàn chỉnh: mở PDF → hỏi → hỏi tiếp → đọc/copy nguồn → min/full; Dừng khi có request đang chạy | Ngân sách đề xuất 3–5, đặt trước khi chạy |

Ngân sách là trần, không phải số call phải dùng hết. Timeout/error cũng tính là
request đã thử; không tự chạy lại để tìm kết quả đẹp. Nếu thiếu trạng thái thật
để kiểm visual, chạy một lượt thật tạo trạng thái đó hoặc ghi rõ chưa kiểm.
Không nạp canned answer, không tiêm transcript cũ vào runtime rồi gọi là live.

Coverage nhắm tới mọi đường bị thay đổi, không đặt mục tiêu % dòng code chung.
Một screenshot không chứng minh route; một contract test không chứng minh đẹp;
một câu trả lời ngắn đúng không chứng minh hỏi tiếp hay toàn bộ chất lượng model.

## Công cụ dùng chung, không thêm một framework lớn

1. Trích observer hiện có thành một runner native dùng chung. Tham số gồm PDF,
   thư mục output mới, model, số call tối đa, nhãn phiên bản và case cần kiểm.
   Dùng production QML/controller/runtime; không đổi default model/prompt.
2. Preflight trước inference: PDF tồn tại/hash/provenance, model đã cài,
   daemon đang có hay do runner sở hữu, QML tải được. Không index tệp cá nhân.
   Nếu Mac khóa, chỉ báo một lần và chờ; không lặp thử hoặc bypass khóa.
3. Một phiên native cho một nhóm chỉnh sửa. Đề xuất reload riêng QML trong
   công cụ dev và giữ nguyên controller/hội thoại đang sống. Kết quả phải vẫn
   là kết quả model đã tạo trong phiên đó; reload không được phát sinh execution.
   Nếu Python/controller/runtime đổi thì restart và chọn mức kiểm phù hợp.
4. Reload là khả năng cần làm và kiểm, chưa có sẵn: kiểm lifecycle/focus/draft,
   connection không nhân đôi và module cache không giữ component cũ. Nếu không
   chứng minh được version đang render, dùng restart. Không xây persistence
   sản phẩm hoặc cơ chế replay transcript chỉ để tiết kiệm test.
5. Mỗi revision có source hash lúc nạp QML/capture, thời gian và model-call ID.
   Không dùng source hash cuối phiên để gán cho ảnh trước reload. Giữ bằng chứng
   từng revision; không chép raw artifact cũ thành run mới.

Đường nhập/bấm desktop tiếp tục dùng CUA. Runner chỉ khởi động/quan sát/log/chụp
cửa sổ; không dùng QTest/offscreen hoặc gọi submit trực tiếp thay thao tác user
để tuyên bố native acceptance. Headless checks có nhãn riêng.

## Giảm context Codex

- Một lần đọc hướng dẫn/runner; các lượt sau đọc manifest tóm tắt và diff liên quan.
- Đọc AX mới sau mỗi nhóm thao tác. Giữ cây đầy đủ trong log khi có cơ chế lưu;
  trả ra chỉ control cần dùng, draft, trạng thái, turn ID và lỗi. Không suy index
  từ cây cũ, không giấu lỗi để báo thành công.
- Gom thao tác CUA theo các bước xác định được từ state vừa đọc; dừng khi có
  trạng thái khác dự kiến. Không gọi công cụ riêng cho từng phím nếu gom được.
- Không đọc model-calls.json đầy đủ vào chat: giữ file gốc, chỉ in usage/error/
  request ID và public answer cần đánh giá. Không lưu private reasoning.
- Ảnh thường lệ: một ảnh min và một ảnh full khi cả hai bị ảnh hưởng. Ảnh lỗi
  bổ sung nếu xảy ra; không chụp/in mọi trạng thái trung gian.
- Một manifest/report sinh tự động cho run, một ghi chú iteration ngắn trong
  chỉ mục. Không viết lại toàn bộ lịch sử vào báo cáo mới.
- Theo dõi số tool calls, kích thước output, số inference requests và thời gian
  thực. Chỉ báo token Codex nếu có số đo trực tiếp, không đổi byte thành token thật.

## Ca kiểm và điều kiện dừng

- Visual: cùng câu trả lời thật, min/full không tràn, nguồn/control không chồng;
  toggle/reload không thêm request và không xóa draft.
- Phím gửi: Enter tìm từ khóa không gọi model; Command Enter gửi đúng một
  request, khóa khi busy, không nhân đôi do binding/reload.
- PDF: nguồn thật có hash; đọc/copy theo đúng file/trang, giữ raw quote. Không
  suy toàn văn từ đoạn 3.000 ký tự.
- History: hỏi tiếp dùng đúng cặp trước; đổi file/hash không mang câu trả lời
  tài liệu trước sang làm nguồn. Kiểm deterministic trước, live chỉ khi thay đổi
  đường context hoặc trong lượt chốt nhóm.
- Dừng: bấm khi request thực đang chạy; giữ cancelled và kiểm callback muộn
  không ghi đè lượt mới. Nếu request xong quá nhanh, ghi ca chưa quan sát thay vì
  tiêm độ trễ/đáp án giả để gọi là live model acceptance.
- Mỗi lần chạy giữ cả lỗi thật. Mac khóa hoặc model lỗi: xử lý trong giới hạn
  đã đặt; không chạy vòng lặp vô hạn hoặc nới timeout chỉ để lấy màu xanh.
- Kết thúc khi đường bị sửa đã kiểm đủ và không còn lỗi blocking của thay đổi.
  Dọn đúng app/daemon sở hữu; không dừng tiến trình người dùng.

## Thứ tự triển khai đề xuất

1. Gọn hóa runner/manifest và cách trả tool output; chưa đổi UI sản phẩm.
2. Làm dev reload giữ controller, kiểm không tạo request mới/không duplicate.
3. Dùng cơ chế đó cho minor UI tiếp: thay “Xem tiến trình” trong min mode bằng
   trạng thái công việc thật. Nếu cần quan sát trạng thái đang chạy, dùng một
   request thật; không tạo nội dung loading/câu trả lời giả.
4. Sau một nhóm 2–4 thay đổi cùng màn hình hoặc ngay khi đường hành vi đổi,
   chạy lượt live tương ứng; không trì hoãn kiểm hành vi đến cuối batch.

Không triển khai thêm UI/backend trong lượt lập kế hoạch này. Các raw artifacts
trước đây giữ nguyên; không xóa báo cáo cũ như một phần gọn hóa runner.
