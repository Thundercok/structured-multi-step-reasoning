# Gemini 4 Argon — thử nghiệm Workbench thể hiện công việc đang thành hình

Trạng thái: kế hoạch và prompt bàn giao, chưa triển khai trong lượt lập kế hoạch.
Bạn là coding agent trong Antigravity, không phải model mặc định của RAT.
Hoàn thành lát cắt native nhỏ dưới đây để người dùng trực tiếp đánh giá.

## 1. Mục tiêu và giới hạn

Người dùng muốn RAT có cảm giác như một người bạn đang làm việc trên bàn:
tìm được tài liệu → mở phần liên quan → đặt dữ kiện cạnh nhau → tạo kết quả.
Đề xuất timeline/log trước đó bị đánh giá là chưa “wow”. Không lấy nó làm
thiết kế chính; chỉ giữ nhật ký làm chi tiết phụ khi cần.

Giữ bố cục Workbench đã duyệt: canvas giấy phía trên, Chuột nổi bật ở dưới
bên trái, lời RAT bên cạnh, ô nhập xanh ở dưới. Một composer xuyên suốt.
Giữ PyQt6; chuyển Qt Quick/QML vẫn ở cuối backlog. Không làm canvas vô hạn,
graph editor, framework mới, webview, hệ memory hay hệ agent mới.

Bản đầu chỉ có hai mức: **tổng quan công việc ↔ đi sâu vào một nguồn**.
Bật thử bằng một cờ môi trường, ví dụ `RAT_WORKBENCH_SCENE=1`, để đối chiếu
với giao diện hiện tại. Không thêm nút chọn tính năng vào trải nghiệm mặc định.

## 2. Repository và phần được sửa

Đọc `AGENTS.md`. Đường dẫn `~/github/nesy-docai` hiện resolve tới
`/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Tự xác nhận lại root, branch và HEAD trước khi làm. Không đổi remote, di chuyển
repo hoặc sửa nhiều checkout để giải quyết tên khác nhau. Làm trên `main`.
Không commit, push, pull, reset, tạo branch hoặc xóa tài liệu recovery.

Working tree đang có thay đổi của người dùng/Gemini. Ghi baseline và hash các
tệp UI liên quan; đọc lại ngay trước khi sửa. Giữ toàn bộ thay đổi ngoài scope.
Nếu phát hiện cùng tệp đang được sửa đồng thời, làm phần component riêng trước
và báo seam tích hợp cụ thể, không ghi đè bản đang thay đổi.

Ưu tiên component mới nhỏ, ví dụ `rat/ui/workbench_scene.py`, và test tương ứng.
Chỉ nối tối thiểu vào Workbench/Omnibar. Không sửa runtime, transport, model,
planner, tool schemas, research, Stage 0 hoặc tích hợp DocAI.
Không cần Gemini API key để chạy fixture UI; không thêm key/config/API calls.

## 3. Tham khảo và dữ liệu hiện có

- [Sensecape](https://sensecape.github.io/): học cách chuyển từ tổng quan sang
  một tầng thông tin sâu hơn; paper/video công khai đủ cho việc tham khảo.
- [Graphologue](https://arxiv.org/abs/2305.11473): học cách làm rõ quan hệ giữa
  các phần nội dung khi chúng xuất hiện, không sao chép một graph dày đặc.
- [Manus Browser Operator](https://manus.im/blog/manus-browser-operator): học
  cách cho người dùng nhìn vào nơi công việc diễn ra.
- `docs/design/rat_workbench_20261015/approved-desktop.png` và
  `docs/rat_workbench_design_20261015.md`: tham khảo bố cục đã duyệt.
  Không dump HTML chứa base64 hoặc toàn bộ lịch sử audit vào context.

Các seam cần đọc có chọn lọc:
`rat/ui/work_context.py:WorkTracePane`, `rat/engine/work_trace.py:summarize_step`,
`rat/engine/assistant_runtime.py:AgentStep`, callbacks progress/step/response/stop
trong `rat/ui/omnibar.py`, cùng presenter và renderer artifact hiện có.
Số dòng có thể đã đổi; tìm theo tên hàm. Tận dụng store, execution/turn ID,
generation và revision sẵn có. Không tạo nguồn trạng thái công việc thứ hai.

## 4. Trải nghiệm cần đạt

### Tổng quan

Canvas giữ tối đa khoảng 5 vật thể chính dễ đọc: các nguồn đã quan sát,
phần đang được chú ý và kết quả đang hình thành. Nguồn dư gộp thành một nhóm
có thể mở xem; không làm mất dữ liệu. Giữ vị trí vật thể ổn định khi có cập nhật.
Không bắt người dùng đọc log trước khi thấy kết quả.

Khi có nguồn mới, thẻ nguồn đi vào vị trí của nó. Khi có trích đoạn thật, đoạn
đó xuất hiện gắn với nguồn/trang. Khi có kết quả được commit, kết quả xuất hiện
và các nguồn liên quan thu về vị trí tham chiếu. Chuyển động diễn tả thay đổi
dữ liệu, không trì hoãn nguồn/kết quả đã dùng được để hoàn thành animation.

Chỉ vẽ quan hệ có căn cứ: file chứa đoạn/trang, artifact dẫn xuất từ ref thật,
hoặc revision mới thay thế revision cũ. Cùng xuất hiện trong một lượt chat
không chứng minh quan hệ nhân quả hoặc việc một kết luận được nguồn hỗ trợ.
Thiếu quan hệ thì dùng cách nhóm trung tính, không tự vẽ đường suy luận giả.

### Đi sâu vào nguồn

Chọn thẻ nguồn hoặc nói rõ nguồn trong ô chat để xem phần/trang đã đọc bằng
renderer hiện có. Giữ được vị trí quay lại tổng quan. Tương tác xem nguồn
không được tự gọi model, đọc thêm tệp, submit lại hoặc thay đổi tác vụ.
Thao tác đọc thêm thật vẫn đi qua workflow và quyền hiện có.

Không dùng raw `thought`, `raw_completion`, `model_input`, prompts hoặc đầy đủ
tool args/results để tạo màn hình “bộ não”. Dùng tóm tắt công khai, artifact
refs và phạm vi đọc quan sát được; sanitize lỗi/đường dẫn trước khi hiển thị.
Lời giải toán/thuật toán vẫn là nội dung kết quả, không phải log tool calls.

### Chuột và lời thoại

Chuột ở vùng dưới, phản ứng theo việc thật: nhận việc, có nguồn, chờ người dùng,
có kết quả, lỗi hoặc dừng. Lời thoại ngắn, không đọc lại toàn bộ canvas.
Không vẽ lại tài sản nhân vật; artist sẽ tiếp tục phần animation sau.

### Geometry và motion

Giữ chiều rộng compact khoảng520, detail khoảng640 logical px nếu màn hình
cho phép. Với nội dung <=450px, dùng reflow hẹp hiện có; không ép ba cột.
Không tự phóng to cửa sổ chỉ để chứa một sơ đồ. Nội dung dài dùng bố cục có
giới hạn và cuộn sẵn có; không tạo một panel trống khổng lồ.

Giữ editor ở cùng tọa độ màn hình khi đủ chỗ; tăng nội dung lên phía trên.
Giữ draft, selection, IME tiếng Việt, focus và vị trí đọc. Không thay composer
hoặc renderer artifact đang có thao tác/draft. Chọn nguồn không được phá draft.

Transition gợi ý 160–240ms, ease-out, chỉ khi trạng thái có thay đổi. Reduced
motion đổi trực tiếp; khi ẩn cửa sổ không có animation/polling nền mới.
Không animate từng token, tạo force simulation chạy liên tục, hoặc thêm lượt
gọi model để kể lại tiến trình. Không làm bước UI phải chờ model/index/OCR.

## 5. Thứ tự thực hiện

1. **Baseline:** ghi source hashes và chạy các test UI liên quan trước sửa.
   Phân biệt lỗi sẵn có với hồi quy. Chỉ đọc file cần thiết, không audit cả repo.
2. **Projection:** ánh xạ sự kiện/artifact hiện có sang dữ liệu trình bày nhỏ,
   có ownership/revision. Progress hiện là chuỗi pha, không phải tool-start
   stream; không suy diễn tool đang chạy từ bước vừa hoàn tất. Không bịa %,
   ETA, kế hoạch tương lai hoặc nhiều nhánh song song.
3. **Native scene:** làm tổng quan/nguồn sâu, nối vào `OmnibarWindow` sau cờ thử.
   Demo fixture riêng phải ghi rõ. Không dừng ở HTML hoặc các widget ghép ngoài
   app; cửa sổ tích hợp phải nhận được sự kiện thật của luồng hiện có.
4. **Kiểm chứng:** sửa lỗi trong phạm vi; bàn giao app chạy được, ảnh và số đo.
   Không mở rộng sang tối ưu model hoặc đổi framework nếu gặp vấn đề UI.

## 6. Hai hành trình để thử Argon

**Tệp thật:** dùng tài liệu vô hại có thật trên máy, hoặc fixture ghi xuống đĩa
được ghi nhãn rõ. Đi qua dispatcher/store/presenter thật: nguồn xuất hiện,
phạm vi đã đọc hiện đúng, mở nguồn, quay lại tổng quan, nhận kết quả. Click/Enter
mở đúng path đã quan sát; không auto-open. Không hardcode một bài DSA, study
plan, tên file hoặc số trang mẫu vào production.

**Sửa kết quả:** dùng một phép tính hoặc artifact dẫn xuất đã đăng ký, tạo kết
quả rồi đổi một đầu vào. Cùng artifact/revision được cập nhật, không nhân đôi
composer/renderer hoặc đánh tráo với lượt trước. Nếu chưa có derivation refs
thì hiển thị dữ liệu thật hiện có, không tự thêm backend để làm đẹp đồ thị.

Cả hai thử thêm: dữ liệu thiếu, lỗi một phần, dừng rồi callback muộn, yêu cầu
mới sau dừng, long text, hide/show và reduced motion. Giữ công việc đã hoàn tất
khi dừng. Phản hồi muộn không được thêm thẻ/đường nối vào công việc mới.

## 7. Nghiệm thu và cách chấm

Thêm test có ý nghĩa cho projection/ownership, reference thiếu hoặc stale,
focus/draft khi xem nguồn, quan hệ chỉ xuất hiện khi có ref, và callback muộn.
Test vùng nhìn thấy phải đo clipping, không chỉ `isVisible()`.

Chạy suite hiện có, thêm tệp test mới vào command:

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest tests/test_rat_magic_ui.py tests/test_rat_one_box_ui.py tests/test_work_context_ui.py tests/test_rat_chat_session.py tests/test_rat_verification_ui.py tests/test_work_context.py tests/test_omnibar.py -q
```

Nếu interpreter thiếu dependency, dùng môi trường đã có phù hợp; không cài
hàng loạt package hoặc chạy research suite để tăng số test trong báo cáo.

Chạy một native smoke từ source mới, xác nhận PID/path dùng source đã sửa.
Chụp ít nhất tổng quan, xem nguồn, cập nhật kết quả và trạng thái dừng; kiểm tra
thêm narrow/light/dark. Phân biệt rõ Qt offscreen replay và cửa sổ Cocoa thật.
Chưa chạy Windows/Linux thì báo chưa kiểm chứng, không tuyên bố đã cross-platform.

Chấm thử bằng các tiêu chí tách biệt, không dùng một điểm chất lượng model:

- **Hiểu được:** nhìn thấy nguồn nào và phần nào đang được chú ý, kết quả nằm đâu.
- **Liền mạch:** vật thể giữ danh tính/vị trí; xem chi tiết rồi quay lại dễ dàng.
- **Đúng dữ liệu:** không có nguồn, quan hệ, xác nhận hoặc tiến trình giả.
- **Nhanh:** không thêm model call; input không bị chặn. Ghi thời gian cập nhật
  presentation, số vật thể và CPU khi ẩn nếu đo được; không hứa60FPS khi chưa đo.
- **Không hồi quy:** editor, file opening, artifact revisions, stop và luồng cũ
  tiếp tục hoạt động khi cờ bật và tắt.

Bàn giao ngắn: changed files, lệnh test + kết quả thật, native screenshots,
giới hạn và cách bật/tắt. Giữ raw/private file content khỏi bằng chứng chia sẻ.
Nếu chỉ có fixture replay, ghi đúng như vậy; không gọi đó là model acceptance.

Lát cắt đạt yêu cầu khi người dùng có thể thử hai hành trình trong app thật và
đánh giá trải nghiệm. Việc bật mặc định hoặc mở rộng toàn bộ chức năng là bước
sau khi xem kết quả này. Không push.
