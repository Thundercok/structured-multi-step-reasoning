# ADR-001: RAT tổ chức quanh yêu cầu và kết quả có thể tiếp tục thao tác

**Status:** Implemented foundation; execution and UI regressions reviewed on 2026-10-11. After trying the app, the user reopened the product design: it still feels like a smaller tool wrapper. [ADR-002](adr-002-rat-adaptive-interaction.md) proposes revised conversation and presentation control. Live-model task quality remains unvalidated for this migration; the foundation is not acceptance of the product experience.
**Date:** 2026-10-11
**Deciders:** Người dùng phụ trách sản phẩm RAT.

## Context

Người dùng muốn nói một yêu cầu, nhận kết quả ngay trong một bề mặt nhỏ, rồi
tiếp tục sửa bằng lời nói hoặc vài điều khiển trực tiếp. Lịch học, tìm tệp và
lá số cần cùng cách sử dụng này. Việc tiếp tục xây mỗi chức năng thành một
cửa sổ riêng không đáp ứng yêu cầu. Chỉ đưa cửa sổ đó vào một thẻ chat cũng
chưa giải quyết cách tổ chức chức năng.

Quan sát từ code hiện tại:

- `rat/engine/assistant_runtime.py` đã dùng model thật để chọn công cụ. Tuy
  nhiên, danh sách công cụ, dispatch thực thi và chuyển kết quả thành nguồn
  quan sát đều có nhánh riêng cho từng công cụ.
- `rat/ui/assistant_presenter.py` biết trực tiếp tài liệu, lịch và lá số.
  Kết quả lá số được biểu diễn bằng một nút mở cửa sổ.
- `rat/ui/omnibar.py::open_natal_chart` ẩn RAT và mở `NatalChartWindow`.
  `_submit_chat_prompt` luôn mở rộng giao diện khi gửi yêu cầu.
- `rat/ui/chat_stream.py::update_source_cards` thay toàn bộ widget kết quả
  sau mỗi cập nhật. Widget chưa phải một kết quả có định danh và phiên bản
  mà người dùng có thể tiếp tục chỉnh.
- `rat/engine/task_state.py` lưu mô tả công việc do model viết. Đây chưa phải
  trạng thái thực thi có thể bảo đảm một thao tác đã chạy hay dữ liệu còn hợp lệ.

Đây là đánh giá kiến trúc qua code, không phải kết quả đánh giá chất lượng model.

Ràng buộc: giữ bộ tính lá số và các dịch vụ đọc dữ liệu đã có; không gắn Qt
vào nghiên cứu headless; không đổi phạm vi nghiên cứu hay Stage 0. Các trace
development trước đây có lỗi chọn công cụ, tổng hợp và timeout. Thiết kế mới
không tự giải quyết các giới hạn đó.

## Decision proposed

Đơn vị sản phẩm là **một công việc của người dùng và các kết quả của nó**.
Một năng lực mới cung cấp thao tác trên dữ liệu, thay vì sở hữu thêm một
ứng dụng con và luồng điều hướng riêng.

Luồng chung:

```text
Yêu cầu / thao tác trên kết quả hiện có
    → model hiểu mục đích, tham chiếu kết quả, chọn thao tác
    → runtime kiểm tra đầu vào và thực thi
    → yêu cầu bổ sung dữ liệu hoặc tạo/cập nhật kết quả có định danh
    → một bề mặt chung hiển thị kết quả và điều khiển liên quan
```

### 1. Năng lực có hợp đồng chung

Mỗi capability đăng ký các operation, schema đầu vào, kiểm tra dữ liệu,
loại kết quả, và action hợp lệ trên kết quả. Thông tin trình bày bổ sung
gồm nhãn trường, nhóm thông tin cần thiết/nâng cao và điều khiển phù hợp.

Model chọn và phối hợp operation theo yêu cầu; runtime thực hiện. Không
thêm nhánh nhận diện từ khóa vào omnibar cho mỗi chức năng mới. Các quyết
định chuyên môn như tính tọa độ hành tinh vẫn thuộc bộ tính đã kiểm tra.

Đầu vào thiếu được biểu diễn bằng một `InputRequest` gắn với operation đang
chờ, bao gồm các trường thực sự còn thiếu và dữ liệu đã có nguồn xác nhận.
Người dùng có thể trả lời bằng lời nói hoặc nhập trực tiếp. Runtime tiếp tục
operation đó khi dữ liệu đủ; không bắt người dùng bắt đầu lại ở một màn hình
khác. Chuẩn bị đầu vào và kiểm tra kết quả là phần của hợp đồng capability,
không phải các câu trả lời cứu hộ viết sẵn thay model.

### 2. Kết quả là đối tượng dữ liệu, không phải widget

Một `Artifact` có định danh, loại dữ liệu, phiên bản, payload, đầu vào đã
dùng và nguồn tạo ra nó. Quan hệ với công việc và kết quả khác được lưu rõ.
Các widget chỉ là cách nhìn của artifact.

Ví dụ: lá số có đầu vào sinh và phiên bản tính; danh sách tệp có query và
tham chiếu tệp thật; lịch có ngày và nguồn dữ liệu. Nguồn quan sát phục vụ
kiểm chứng được giữ riêng với kết quả trình bày cho người dùng.

Khi người dùng nói “đổi giờ thành 9:30”, model tham chiếu lá số đang được
thảo luận, rồi đề xuất action cập nhật đầu vào. Runtime tính lại và tạo một
phiên bản mới. Phiên bản cũ còn trong lịch sử; bề mặt hiện tại cập nhật rõ.
Nếu đang có nhiều lá số và tham chiếu không rõ, hỏi người dùng chọn.

### 3. Một bộ thành phần trình bày dùng chung

Bề mặt chung hỗ trợ văn bản ngắn, danh sách, bảng, dòng thời gian, hình/vector,
xem trước tài liệu, nhập dữ liệu, action và vùng chi tiết có thể mở thêm.
Khả năng mới mô tả dữ liệu và cách sử dụng các thành phần này. Bộ trình bày
chịu trách nhiệm bố cục, kích thước, bàn phím, trạng thái và hành vi thống nhất.

Model có thể chọn nội dung và mức nhấn mạnh trong phạm vi hợp đồng. Không
cần model sinh Python/Qt hoặc thiết kế lại giao diện ở mỗi lượt. Các nút
đơn giản gọi action đã đăng ký trực tiếp, không qua một vòng suy luận thừa.

Một hình chuyên môn như vòng lá số vẫn cần renderer chuyên môn. Renderer
trả SVG và thông tin tương tác cho bề mặt chung; không sở hữu cửa sổ, form,
lịch sử hội thoại và vòng đời ứng dụng riêng.

Mặc định hiển thị lượng thông tin cần để đáp ứng yêu cầu. Người dùng có thể
mở thêm chi tiết hoặc phóng lớn rõ ràng. Gửi một câu hỏi hoặc chạy tool không
tự chuyển sang ứng dụng con hay ép mở toàn bộ giao diện.

### 4. Trạng thái thực thi tách khỏi lời model mô tả

Runtime lưu công việc đang chờ, artifact đang được tham chiếu và sự kiện
thực tế: cần đầu vào, bắt đầu thao tác, thao tác thất bại, kết quả được tạo,
kết quả được cập nhật, lượt kết thúc. Mô tả mục tiêu do model viết vẫn hữu
ích nhưng không thay thế trạng thái này.

Thao tác có kết quả thật có thể hiển thị ngay khi hoàn tất. Không chờ model
viết xong một đoạn giải thích mới cho người dùng thấy lá số hoặc tệp đã tìm
được. Một lượt tổng hợp thất bại không xóa kết quả thật đã tạo và không được
ghi thành một câu trả lời thành công.

## Options considered

| Phương án | Độ phức tạp | Chi phí lượt tương tác | Mở rộng | Quan hệ với code hiện có |
| --- | --- | --- | --- | --- |
| Thu nhỏ từng app hoặc nhúng từng widget riêng vào chat | Thấp ban đầu, tăng theo số chức năng | Ít thay đổi inference | Mỗi chức năng vẫn có luồng riêng | Tận dụng UI nhiều nhất |
| Hợp đồng capability + artifact + bộ trình bày chung | Vừa/cao ở nền tảng ban đầu | Không cần lượt model riêng để dựng UI; cần đo thực tế | Thêm adapter và operation, dùng lại vòng đời tương tác | Tận dụng engine, thay ranh giới runtime/UI |
| Model tự sinh mã giao diện và thực thi tùy ý | Cao, khó kiểm tra và duy trì nhất | Thêm generation và kiểm tra; chưa có số đo | Linh hoạt về hình thức, hành vi khó nhất quán | Đòi hỏi cơ chế mới vượt quá nhu cầu hiện tại |

Đề xuất triển khai phương án thứ hai và chuẩn bị các ranh giới để mở rộng
sang phương án thứ ba. Phương án thứ hai xử lý cả ba loại yêu cầu bằng cùng
một mô hình tương tác, trong khi giữ các bộ tính và dữ liệu có thể kiểm tra.
Phương án thứ ba trong tương lai vẫn dùng các hợp đồng và trạng thái đó;
không trở thành một kiến trúc ứng dụng độc lập cần viết lại từ đầu.

## Extension path: phương án 2 làm nền cho phương án 3

Theo yêu cầu tiếp theo của người dùng, cần vừa làm nền tảng có thể sử dụng
hiện tại, vừa tránh khóa đường đến giao diện và năng lực do AI tạo trong
tương lai. Chuẩn bị ở đây là chọn ranh giới đúng và ghi rõ hợp đồng, chưa
xây runtime sinh mã hoặc thêm lượt inference vào đường sử dụng hiện tại.

### Các ranh giới cần có ngay từ phương án 2

| Ranh giới | Trách nhiệm hiện tại | Phần có thể thay/mở rộng sau này |
| --- | --- | --- |
| `CapabilityRegistry` | Công bố operation và action đã đăng ký; schema kiểm tra đầu vào; adapter thực thi | Năng lực mới có thể được đề xuất và kiểm tra trước khi đăng ký |
| `ArtifactStore` | Dữ liệu kết quả, định danh, phiên bản và nguồn; độc lập với widget | Giao diện mới vẫn đọc và cập nhật cùng artifact, giữ lịch sử |
| `ViewProvider` | Chuyển artifact và nhu cầu hiển thị thành `ViewSpec` có phiên bản | Provider do model đề xuất cách ghép các thành phần đã có |
| `ViewRenderer` | Vẽ `ViewSpec` bằng các thành phần đã hỗ trợ; độc lập với provider | Thêm thành phần chuyên môn hoặc một renderer khác mà không đổi trạng thái công việc |
| `ActionDispatcher` | Kiểm tra action, artifact đích và phiên bản trước khi chạy operation | Giao diện do AI tạo gửi cùng yêu cầu action; không tự sở hữu đường thực thi |

Các tên này là hợp đồng thiết kế đề xuất, chưa phải module đã được tạo trong
repo. Chỉ cần registry trực tiếp và provider hiện tại; chưa cần discovery,
hot loading hay một hệ plugin phân tán.

Một `ViewSpec` gồm phiên bản hợp đồng, tham chiếu artifact và cây thành phần
được hỗ trợ. Nội dung và action cần gắn với dữ liệu thật. Ví dụ minh họa hợp
đồng, không phải output đã chạy:

```json
{
  "schema_version": 1,
  "artifact": {"id": "chart-42", "revision": 2},
  "blocks": [
    {"type": "vector", "resource": "wheel"},
    {"type": "summary", "fields": ["sun", "moon", "ascendant"]},
    {"type": "actions", "action_ids": ["edit_birth", "export"]},
    {"type": "details", "fields": ["positions", "houses", "aspects"]}
  ]
}
```

`wheel`, các field và các action trong ví dụ phải được artifact/capability
thực tế công bố. Provider không được tạo tọa độ hành tinh, đường dẫn tệp
hoặc action chưa tồn tại để làm đầy giao diện. Renderer chỉ đọc tham chiếu
đã kiểm tra. Khi schema/field/action không hợp lệ, từ chối đề xuất trình bày
đó và giữ giao diện chuẩn của dữ liệu thật; ghi lỗi provider rõ ràng. Đây là
xử lý một lỗi trình bày, không ghi thay một câu trả lời model thất bại.

### Lộ trình mở rộng

1. **Phương án 2: nền tảng hoạt động.** Capability được viết và kiểm tra;
   provider chuẩn tạo giao diện từ hợp đồng. Model hiểu yêu cầu và chọn/phối
   hợp thao tác. Nút chỉnh trực tiếp đi qua dispatcher, dùng chung artifact
   với câu nói tiếp theo. Đường sử dụng thường không cần model thiết kế UI.
2. **AI đề xuất giao diện khai báo.** Sau khi nền tảng ổn định, một provider
   tùy chọn chọn thành phần, thứ tự và mức chi tiết từ tập đã hỗ trợ. Đề xuất
   qua cùng validator và renderer. So sánh với provider chuẩn về mức hoàn
   thành công việc, tính dễ dùng, lỗi và độ trễ; chỉ triển khai nếu có ích.
3. **Phương án 3: AI đề xuất thành phần hoặc năng lực mới.** Chỉ thử sau khi
   có nhu cầu thật mà các thành phần/operation hiện tại chưa đáp ứng. Mã đề
   xuất chạy trong môi trường thực thi riêng với quyền truy cập được xác
   định, không trực tiếp trong process Qt. Kiểm tra output, action và hợp
   đồng trước khi cho kết nối vào runtime chung. Cách ly mã không tự chứng
   minh công thức hay kết quả chuyên môn đúng; vẫn cần kiểm chứng lĩnh vực.

Tạo cách trình bày mới và tạo một năng lực thực thi mới là hai mức khác nhau.
Mốc thứ hai không được báo cáo là đã đạt mốc thứ ba. Không có cam kết rằng
model đang chạy cục bộ hiện nay có thể thực hiện tốt một trong hai mốc đó.

### Điều kiện để tránh phải viết lại sau này

- Capability và artifact không trả Qt widget hay phụ thuộc vào một cửa sổ.
- View không chứa logic tính chuyên môn, đường dẫn tùy ý hoặc mã thực thi.
- Cả nút bấm và yêu cầu bằng lời nói tham chiếu cùng action/artifact. Action
  kèm phiên bản đích; kiểm tra phiên bản trước khi áp dụng để tránh một điều
  khiển cũ sửa nhầm kết quả mới.
- Hợp đồng có phiên bản và kiểm tra tương thích. Một schema chưa hỗ trợ không
  âm thầm được hiểu như schema hiện tại.
- Đổi provider trình bày không làm mất công việc đang chờ, dữ liệu người dùng
  đã cung cấp hoặc lịch sử kết quả. Lưu state ở kernel thay vì trong widget.
- Thêm một capability bình thường không cần thêm nhánh nhận diện yêu cầu
  trong omnibar hoặc đổi bộ trình bày trung tâm. Chỉ thêm renderer nếu thật
  sự cần một loại hình/điều khiển chưa có.

### Kiểm tra nền tảng trước khi mở rộng

Ngoài các tình huống sản phẩm bên dưới, cần kiểm tra khả năng đổi provider
cho cùng artifact mà không đổi kết quả, action hoặc trạng thái. Một provider
sai tham chiếu/action/schema phải bị từ chối; artifact thật vẫn còn. Một
action từ phiên bản cũ phải được phát hiện, không ghi đè phiên bản mới.
Một capability thử nghiệm phải đi qua cùng registry và luồng tương tác mà
không thêm nhánh UI theo tên chức năng.

Đây là điều kiện kiểm tra kiến trúc đề xuất. Chưa có triển khai hay kết quả
đo cho provider do AI sinh, runtime cách ly hoặc năng lực do AI tạo.

## Trade-off analysis

Nền tảng này vẫn là phần mềm bao quanh model và công cụ. Có schema, renderer
hay registry không chứng minh AI mạnh hơn. Phần cần thực sự do model làm là
hiểu mục đích mới, phối hợp năng lực, chọn dữ liệu liên quan và giải quyết
tham chiếu trong hội thoại. Các hành vi đó phải được đánh giá riêng.

Không thể hứa mọi năng lực tương lai đều không cần code. Truy cập dữ liệu
mới, công thức chuyên môn và biểu đồ đặc thù vẫn có thể cần adapter hoặc
renderer. Điều tránh được là dựng lại một app con và nối thêm logic vào
omnibar/presenter mỗi lần mở rộng.

Hợp đồng quá tổng quát có thể làm mất chi tiết chuyên môn; hợp đồng quá
đặc thù sẽ tái tạo các nhánh chức năng hiện nay. Ranh giới cần kiểm tra là:
domain chịu trách nhiệm dữ liệu và thao tác đúng; kernel chịu trách nhiệm
thu thập đầu vào, tiếp tục công việc, định danh/phiên bản kết quả và tương tác.

Một form sinh từ toàn bộ schema vẫn có thể rất rườm rà. Vì vậy chỉ các trường
còn thiếu và cần thiết mới xuất hiện mặc định; tùy chọn chuyên môn mở thêm
khi người dùng cần. Kích thước nhỏ không được làm mất khả năng đọc kết quả.

## Consequences

- Công việc nhiều bước có thể phối hợp lịch và tìm tài liệu trong một lượt,
  thay vì người dùng tự chuyển giữa màn hình chức năng.
- Điều khiển trực tiếp và câu nói tiếp theo cùng thao tác trên một kết quả.
- Thêm năng lực ít phải sửa lớp giao diện trung tâm hơn.
- Cần quản lý rõ tham chiếu, phiên bản, trạng thái đang chờ và cập nhật UI;
  đây là phần đầu tư lớn hơn việc thêm một thẻ chat.
- Độ đúng và độ trễ của model vẫn là giới hạn độc lập. Không triển khai thêm
  lượt planning/presentation chỉ để kiến trúc trông giống agent hơn.
- Pipeline NCKH, tập dữ liệu và các claim nghiên cứu không thay đổi bởi ADR này.

## Action items before implementation

1. [ ] Chốt luồng sản phẩm chung qua ba tình huống bên dưới và một tình huống
   phối hợp chưa được viết thành tính năng riêng.
2. [ ] Chốt hợp đồng tối thiểu `Capability`, `InputRequest`, `Artifact`,
   `ArtifactAction`, `ViewSpec` và sự kiện runtime; không xây hệ plugin lớn
   trước khi cần.
3. [ ] Lập kế hoạch chuyển đổi engine và UI hiện có sang hợp đồng đó. Giữ các
   backend tính/đọc dữ liệu, thay cách điều phối và trình bày.
4. [ ] Sau khi hướng thiết kế được thống nhất, triển khai một lát cắt đi xuyên
   qua kernel để kiểm tra ranh giới; chưa mở rộng nhiều chức năng cùng lúc.
5. [ ] Đánh giá hành vi model thật và trải nghiệm riêng. Passing test phần mềm
   không phải bằng chứng đã hiểu và hoàn thành yêu cầu người dùng.
6. [ ] Kiểm tra thay provider trên cùng artifact và từ chối schema/action/
   tham chiếu không hợp lệ trước khi thử provider trình bày do model đề xuất.

## Scenarios to judge the design

| Yêu cầu | Kết quả và lần tương tác tiếp theo cần đạt |
| --- | --- |
| “Tra giúp tôi bản đồ sao” | Chỉ hỏi dữ liệu sinh còn thiếu trong bề mặt hiện tại; khi đủ thì trả lá số thật, có chỉnh và mở chi tiết |
| “Đổi giờ sinh thành 9:30” | Cập nhật đúng lá số đang được nói tới, tính lại và giữ lịch sử; không tạo luồng nhập từ đầu |
| “Mai tôi học gì?” | Trả những ca liên quan ngay tại chỗ; hỏi phòng hoặc tài liệu tiếp theo dựa trên ca đó |
| “Tìm slide về TCP” | Trả tệp thật liên quan; mở hoặc yêu cầu đọc/tóm tắt từ đúng tệp, phân biệt đã tìm với đã đọc |
| “Mai học gì, lấy tài liệu cần ôn rồi xếp lúc rảnh giúp tôi” | Phối hợp lịch, tài liệu và khoảng trống theo dữ liệu thật; giữ kết quả liên quan trong một công việc |
| Hai lá số đang được thảo luận, rồi “đổi giờ của cái đó” | Làm rõ tham chiếu trước khi sửa; không đoán một kết quả để cập nhật |

Khi đánh giá, ghi số lần phải cung cấp lại dữ liệu, số chuyển màn hình,
thời gian đến kết quả hữu ích đầu tiên, việc cập nhật đúng đối tượng và mức
hoàn thành yêu cầu được review. Chưa đặt ngưỡng chất lượng hay độ trễ chưa
có căn cứ. Chưa có kết quả đo nào cho kiến trúc đề xuất.

## Implementation Status (2026-10-11)

Option 2 has been implemented with architectural preparation for Option 3:
1. **Headless Kernel Contracts (`rat.kernel.contracts`, `rat.kernel.registry`, `rat.kernel.dispatcher`)**:
   - `InputRequest`: Carries supplied inputs, missing fields, candidate choices, and resumes operations without central keyword routing.
   - `Artifact` and `ArtifactStore`: Stable UUIDs, revisions, payload, inputs, provenance; list and revision history without database bloat.
   - `ArtifactAction` and `ActionDispatcher`: Direct UI controls and model decisions dispatch through the same registered capability handlers with stale revision status (`stale_revision`) and ambiguous reference clarification through `InputRequest`.
   - `CapabilityRegistry`: Registers operations, input schemas, result contracts, and exports native tool definitions dynamically (`registry.to_tool_definitions()`).
   - Zero Qt dependencies: Verified headless isolation.
2. **Standard Declarative Presentation & Validation (`rat.kernel.view_spec`, `rat.ui.view_renderer`)**:
   - `ViewSpec`, `ViewBlock`, `StandardViewProvider`: Pure Python dictionary/dataclass schema version 1.
   - Strict validation: Rejects unknown schema versions, unknown block types, invalid field references, and invented actions.
   - `QtViewRenderer`: Renders `ViewSpec` into native RAT widgets with warm paper/gold styling, responsive wheel rendering, candidate place buttons, and stale action disabling.
3. **Capabilities Migrated (`rat.kernel.capabilities`)**:
   - `natal`: `search_birth_places`, `create_natal_chart` (returns `InputRequest` on missing inputs or place ambiguity), `update_birth_data`, `export_natal_chart`. Headless export factored to `rat.astrology.export`.
   - `timetable`: `get_schedule`, `locate_room`, `get_group_availability`.
   - `documents`: `search_documents`, `read_document` (distinguishing finding from reading).
4. **Integration (`rat.engine.assistant_runtime`, `rat.ui.omnibar`, `rat.ui.assistant_presenter`)**:
   - `AssistantRuntime`: Executes tools through `ActionDispatcher`, produces versioned artifacts, maintains truthful execution states.
   - `OmnibarWindow`: Direct navigation to Natal switches to home section and renders inline `InputRequest` within the conversational surface; no standalone `QMainWindow` or hiding RAT.
5. **Option 3 Boundaries & Future Work**:
   - View provider is swappable (`ViewProvider` protocol) without modifying artifacts or actions.
   - Arbitrary AI code execution, sandbox execution, AI view synthesis, and runtime plugin discovery remain strictly future work and are not implemented.


## Codex review follow-up (2026-10-11)

The first implementation's nine fixture tests did not establish complete native
or Qt interaction behavior. Follow-up review corrected partial-call validation,
native target references, export/read artifact corruption, no-op time controls,
loss of drafts during progress, weak action/resource validation, timestamp ID
collisions and late commits after chat reset. Registered operations now own view
factories and action declarations; Qt resources have a renderer registry.

The follow-up includes actual Qt control and worker regressions, manual-coordinate
and repeated-hour input, complete chart tables, and inspection of stored revisions.
Evidence and remaining limitations are recorded in
`audit/rat_interaction_kernel_codex_review_20261011/REPORT_FOR_CODEX.md`.
These are software checks with fixtures; no new live-model evaluation, controller
training, Stage 0 advancement, or AI-generated view implementation is claimed.
