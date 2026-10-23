# RAT min preview — real UI conversations, 2026-10-23

Người dùng yêu cầu không dùng canned answers/model giả cho UI/flow acceptance.
Lượt này nhập câu hỏi bằng CUA trên native QML, chạy AssistantWorker và model
Ollama local thật `qwen2.5:1.5b`. Model có sẵn; không tải model/cloud, không dùng
candidate dataset hoặc kích hoạt policy bundle chưa duyệt. Đây là assistant
lane mặc định của Quick Desk, không phải acceptance của online policy campaign
và không thay đổi Stage 0.

## Các sửa từ quan sát thật

- Min hiển thị đoạn trích mở đầu, tối đa ba dòng, metadata nguồn/xác minh;
  không gọi thêm model để tóm tắt. Câu trả lời gốc vẫn còn đầy đủ trong full.
  Kết quả đến giữ mode hiện tại và không xóa bản nháp mới gõ trong lúc chờ.
- Preview co theo nội dung thay vì luôn giữ chiều cao 112 px. Chat đã được
  nhận thì dọn câu vừa gửi khỏi composer; PDF search vẫn giữ từ khóa.
- AssistantWorker dùng progress_changed, trong khi reasoning worker dùng
  status_changed. Controller trước đó giả định cả hai có status_changed,
  làm lần gửi thật đầu tiên crash trước khi gọi model. Đã sửa nối signal.
- Context dành cho reasoning có artifact_refs/source_evidence/... không phải
  kwargs của AssistantRuntime.run. Đã chiếu các trường assistant hỗ trợ ở
  ranh giới worker; snapshot đầy đủ cho reasoning vẫn giữ nguyên.
- Đáp án thật bắt đầu bằng code làm preview trống: nay lấy ba dòng code đầu
  từ chính block trả về, giữ indent và đánh dấu cắt. Không tự viết đoạn code
  thay thế hoặc coi đoạn trích là kết luận đã xác minh.
- Cancel trước đó ghi turn mới cancelled nhưng preview vẫn trỏ turn cũ,
  khiến metadata hiển thị completed. Nay chuyển displayed turn về lượt đã
  dừng, không dùng đáp án cũ cho câu hỏi mới và không bật copy cho đáp án rỗng.
- Giữ các execution worker tới QThread.finished. Lần cancel thật đã gây
  `QThread: Destroyed while thread is still running` sau request timeout.
  Thêm bind_desk_close để ẩn cửa sổ ngay, chờ worker thật hoàn tất rồi mới
  đóng; không dùng terminate/kill thread hoặc giả vờ backend đã ngừng sinh.
- Busy chat có nhãn `Đang xử lý`, bỏ phần status lặp và chỉ hiện progress ở
  vùng đang sử dụng (paper khi full, composer khi min). Reset unread khi bắt
  đầu lượt mới. Các progress công khai từ assistant được chuyển tới UI;
  bỏ qua callback progress khi không còn worker hiện hành.
- Lỗi thực được giữ trong chi tiết/nhật ký, không chỉ một nhãn lỗi chung.

## Bằng chứng đã chạy và giới hạn

`work/rat_ui_min_preview_20261023/` giữ hai lượt hỏi/đáp native thật đầu tiên,
ảnh min/full, lỗi signal/kwargs và model-call metadata. Không sửa các đầu ra
model sai để làm demo đẹp hơn. Lần chạy bị gián đoạn khi đổi lượt chat không
có source-manifest cuối; không coi đó là source-stable final acceptance.

`work/rat_ui_live_followup_20261023/` giữ cuộc hội thoại mới qua UI thật:

1. Giải thích binary search trên [2,4,7,9,13], tìm 9: model trả lời quá ngắn,
   nói “vị trí thứ 3” mà không chỉ rõ index convention, chưa đáp ứng yêu cầu
   giải thích thuật toán.
2. Hỏi tiếp index bắt đầu từ 0: model trả lời 3, dùng được ngữ cảnh trước.
3. Xin Python + ví dụ tìm 9 và 6 + lý do left=mid+1: model tạo hàm binary_search
   đúng trong các check đã chạy, nhưng bỏ ví dụ target=6 và phần giải thích.
4. Request giải thích O(log n), rồi bấm Dừng với bản nháp mới đang nhập:
   history ghi cancelled và draft giữ, nhưng preview vẫn mang turn cũ.
   Backend request này timeout, sau đó Qt crash vì vòng đời thread.

Trong run này đã thao tác mở/thu paper, copy đáp án model thật rồi paste vào
composer, gửi tiếp trong full mode và kiểm bản nháp gõ lúc model đang chạy.
Source đầu run được lưu trong source-initial.json; sau crash không có final
manifest, vì thế run này là reproduction evidence, không phải pass cuối.

Hàm Python thực sinh ở lượt 3 được kiểm bằng AST chỉ cho phép toán tử, luồng
điều khiển và len; không chạy sample print hay code I/O của model. Tám check
cho tìm thấy/không thấy/rỗng/singleton/duplicate/biên đều đạt. Raw answer hash,
inputs/outputs và giới hạn nằm trong observed-code-check.json. Đây là kiểm
function quan sát được, không phải kết luận chất lượng model hay full prompt
compliance; helper ban đầu thiếu UnaryOp cho return -1, đã thêm đúng node đó.

Ba request thành công ở run followup: prompt counts 3417/3683/3916, generated
counts 36/21/171; thời gian request quan sát khoảng 32.5/31.9/60.4 giây.
Request thứ tư timeout sau khoảng 90 giây và không có token usage xác nhận;
metadata 0 ở call lỗi không có nghĩa là inference không tốn token. Các số này
không phải replay time, benchmark latency hoặc tổng chi phí hệ thống.

## Trạng thái source cuối — còn chờ native acceptance

`work/rat_ui_live_final_20261023/` chứa script dùng cơ chế close production,
source-initial.json và native window khởi động được. Sau các sửa code preview,
cancel và QThread cuối, CUA báo Mac đang khóa và yêu cầu người dùng tự mở khóa.
Chưa nhập request/inference nào trên source cuối này. Không thay bằng canned
answers hoặc phát lại câu trả lời cũ để ghi pass.

Các bước cần xác nhận khi mở khóa:
- Gửi yêu cầu code thật ở min: preview hiện code, không chung chung/rỗng.
- Mở full, hỏi tiếp thật: giữ context/mode, một progress và nhãn busy đúng.
- Gõ draft khi busy, bấm Dừng: cancelled metadata, draft giữ, callback muộn
  không thay kết quả và worker không bị hủy khi còn chạy.
- Đóng app khi request đang drain: cửa sổ ẩn, process thoát sau worker kết
  thúc, không có QThread fatal.

Đã py_compile các file Python sửa và git diff --check. Không chạy lại bộ test
canned/fixture trong lượt này theo quyết định người dùng. Không rebuild bản
app cài sẵn, không commit/push, không sửa research harness hoặc thresholds.

Sau khi Mac tiếp tục khóa, đã dừng đúng native test idle và Ollama server do
mình khởi động; không còn inference pending. blocked-manifest.json ghi hash
source cuối vẫn trùng source-initial.json, cửa sổ đã load được, số request
inference cuối = 0 và acceptance còn chờ mở khóa. Native process được dừng
chủ động (exit 143), không ghi lần này là crash hay pass. Cần mở lại phiên
live khi người dùng mở khóa; không tự vượt khóa máy.

## Cập nhật sau mở khóa — đã thực hiện desktop acceptance

Phần chờ mở khóa ở trên là mốc lịch sử. Người dùng chọn tiếp tục thao tác
**desktop**, từ chối đề xuất Qt mô phỏng; không chạy QTest/offscreen hay canned
answer để thay thế.

- `work/rat_ui_live_final_20261023/`: một request code thật hoàn tất phía
  Ollama nhưng content rỗng, không có tool_calls; runtime báo
  invalid_model_output. Request dùng 3416 prompt / 50 generated tokens,
  khoảng 44.7 giây. Không ghi thành công và không chèn đáp án cũ thay thế.
- Kiểm tra này cũng phát hiện đóng cửa sổ đang ẩn không phát lastWindowClosed,
  khiến process còn sống. bind_desk_close nay chỉ ẩn khi cần chờ worker và
  gọi QCoreApplication.quit sau drain. Đã kiểm lại bằng nút đóng native.
- Khi đối chiếu source thực tế, hai chỉnh sửa dọn câu đã gửi/co chiều cao
  preview bị thiếu. Đã áp lại, rồi bắt đầu một phiên mới; không dùng ảnh từ
  phiên trước để nhận là source cuối.

`work/rat_ui_live_acceptance_20261023/` là phiên source cuối đã kiểm qua CUA:

1. Câu hỏi binary search thật có đáp án; composer dọn câu đã gửi. Bản nháp
   gõ khi chờ vẫn giữ lúc trả lời; kết quả nằm trong min, không tự bung full.
2. Gửi bản nháp xin code qua UI. Mở full khi chờ: nhãn Đang xử lý và một
   progress, không còn nhãn Trong tài liệu/status/progress lặp. Thu về min,
   tiếp tục nhập draft mới. Request code timeout sau 90 giây; không có answer.
3. Gửi request thật tiếp, nhập draft mới, bấm Dừng: metadata Đã dừng · chưa
   hoàn tất, draft giữ, answer rỗng của đúng turn cancelled. Bấm đóng qua UI.
   Backend thực trả về sau khoảng 34.9 giây (40 generated tokens); runtime
   callback là cancelled, không thêm câu trả lời muộn vào history/UI. Process
   native kết thúc **exit code 0**, không QThread fatal như reproduction cũ.

`acceptance.json` ghi các checks trên artifacts thật, manual desktop checks,
phần chưa được chấp nhận và zero QML warnings. `source-manifest.json` xác nhận
cả năm file UI/bridge/worker/formatter/app không đổi giữa đầu và cuối phiên.
QML cuối: `a1ab33c8a96029263cef6fe5fbeb75074c899635397b1cf9435bb467b53b112f`.

`conversation-review.md` giữ nguyên câu hỏi/đáp án công khai cùng trạng thái
failed/cancelled và lỗi thực. Phiên có 1 completed / 1 failed / 1 cancelled;
không gọi toàn bộ cuộc hội thoại là pass về chất lượng. Prompt 1 dùng 3417
prompt / 33 generated tokens, khoảng 79.5 giây; request code timeout không có
usage xác nhận, không coi counts 0 là chi phí 0. `model-identity.json` ghi
Ollama 0.34.3 và digest model đã cài
`65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`.

Còn chưa nghiệm thu: preview code vì request code thật timeout; chất lượng
đáp án binary search ban đầu còn thiếu; Dừng UI chưa ngắt ngay HTTP generation
đang chạy. Source đã xử lý vòng đời worker và bỏ kết quả muộn, không khẳng
định inference bị hủy tức thì. Chưa test đầy đủ dark theme, IME hoặc nhiều màn
hình trong phiên cuối. Đây là smoke app/assistant lane, không phải Stage 0.

Sau test đã dừng server Ollama do mình khởi động. Không đổi model mặc định,
không tải model, không rebuild app cài sẵn, không commit/push. Chỉ kiểm static
py_compile và diff --check ngoài các thao tác native/model thật; không chạy lại
bộ fixture đáp án theo yêu cầu người dùng.


## Lượt backend và code preview tiếp theo

Xem [báo cáo cancel, cache và code preview](rat_backend_cancel_and_code_preview_20261023.md): kiểm desktop/model thật, giữ cả phản hồi sai; chưa nghiệm thu chất lượng model.
