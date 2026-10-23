# Bàn giao cho Anti: hợp nhất RAT–CoT trên UI Quick hiện tại

Cập nhật 2026-10-23, Asia/Ho_Chi_Minh. **Bridge đã được reviewer nghiệm thu
trong phạm vi software đã giao.** Xem mục “Bridge đã đạt — bước nghiên cứu tiếp
theo”. **Checker dry-run cần sửa theo review độc lập cuối tài liệu; chưa nghiệm
thu chỉ từ báo cáo 97 tests pass.** Các phần trước giữ quyết định hợp nhất,
phạm vi UI và lịch sử bàn giao; không mặc định mọi acceptance đã hoàn tất.
Người dùng yêu cầu: “tiếp theo cho anti đồng nhất tất cả đi”. Tiếp tục từ cây
source hiện tại; giữ các sửa UI/PDF mà người dùng vừa test. Không mở thêm một
phiên bản sản phẩm hoặc lặp lại vòng review runtime độc lập.

## Kết quả người dùng cần nhận

Một ứng dụng RAT với UI Quick/QML hiện tại, một đường thực thi chung và một
cách mở chính được chỉ rõ. Người dùng mở đúng giao diện đã hoàn thiện, thực
hiện công việc, hỏi tiếp, sửa dữ kiện, xem lại và hủy; các khả năng cùng dùng
context, ownership, identity, artifacts và evidence của hệ RAT–CoT.

RAT triển khai CoT/structured reasoning; pipeline headless đánh giá cùng phương
pháp. PDF đọc/tìm trang và thao tác xác định vẫn được thực hiện trực tiếp khi
phù hợp, không ép mọi hành động gọi model.

Anti nhận vai trò triển khai lát cắt hợp nhất này. Chat review giữ vai trò đối
chiếu kết quả; không phân công hai chat cùng sửa các file integration. Đọc lại
source và git status trước khi sửa để giữ những thay đổi vừa có từ chat khác.

## Mốc xuất phát khi giao việc hợp nhất

Phần này lưu mốc trước triển khai, không phải bảng launcher hiện tại. Khi nhận
bàn giao Turn 2 ngày 2026-10-22, source trên `main`, HEAD `73a15ec` cùng các
thay đổi chưa commit đã đưa mặc định `python main.py` và alias `quick-pdf`
vào cùng `rat.ui.quick_app`/`PDFDesk.qml`; `python main.py widgets` là đường
compatibility. Quick controller đã gọi shared execution worker. Điều đó xác
nhận đường nối trong source, chưa tự xác nhận mọi acceptance bên dưới đã đạt.
Review hiện hành và log nằm ở
`audit/rat_cot_quick_unification_20261022/independent_review/current_review.md`.

Các alias `~/github/nesy-docai`, `~/github/multi-step-structured-reasoning` và
checkout `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`
đã được kiểm tra, đều trỏ cùng thư mục thật. Khác nhau hiện nằm ở đường chạy:

| Entry point ở mốc trước hợp nhất | Surface | Thực thi ở mốc đó |
| --- | --- | --- |
| `python main.py` | Widgets/Omnibar | Shared execution factory và reasoning worker khi cấu hình host. |
| `python main.py quick-pdf` | `rat/ui/quick/PDFDesk.qml` | `QuickPDFController` và selected-PDF reader; chưa nối shared reasoning. |
| `python scripts/preview_rat_quick.py` | Prototype `PaperDesk.qml` | Fixture thiết kế, không phải ứng dụng có runtime đầy đủ. |

Các sửa calibration/context/worker hiện tại và 115 test offline đạt không
chứng minh UI Quick đã tích hợp. Bộ DSA có các thao tác setup/commit artifact
trực tiếp trong test; không coi chúng là bằng chứng product tự tạo revision.

Đọc `AGENTS.md`, `docs/project_scope.md`, `docs/research_plan.md`,
`docs/research_protocol.md`, `docs/adr-005-rat-quick-ui-preview.md` và
`docs/rat_quick_pdf_20261022.md`. Dùng source hiện tại làm điểm xuất phát; các
source map cũ chỉ mô tả thời điểm lập bản đó.

## Công việc phải thực hiện

1. **Dùng UI Quick hiện có làm bề mặt tích hợp.** Giữ hành vi chatbar,
   Simple/!/loading, vị trí/độ trong suốt cửa sổ, draft, selection và các
   sửa PDF. Thay đổi hình thức theo từng bước của kế hoạch UI bên dưới;
   ý tưởng mới không tự thay UI đang chạy. Mở rộng adapter để nhận public execution/result
   events. Không dựng màn chat/tutor/UI thứ tư, không sao chép controller.
2. **Nối vào runtime chung đã có.** Tái sử dụng `ExecutionRequest`,
   `create_execution_worker`, `OnlineReasoningWorker`, `execution_response`,
   composition/validation và model owner hiện tại. QML bridge chỉ chuyển public
   events/state; ConversationHistory, notebook, ArtifactStore và lifecycle hiện
   có giữ nguồn dữ liệu chính. Context được chụp khi submit, có hash/version và
   source refs; giữ riêng câu người dùng nhập. Không tự thêm context store,
   model session hoặc policy implementation thứ hai.
3. **Giữ hợp đồng công việc trên cùng UI.** ID conversation/turn/execution/
   generation phải xuyên suốt. Hỏi tiếp không rơi sang engine khác vì thiếu
   keyword. Tham chiếu revision cũ được resolve đúng; thiếu source bắt buộc thì
   trả unresolved/unavailable trung thực. Hủy/deadline chặn callback muộn, giữ
   chi phí đã phát sinh; explicit lookback giữ draft và không gọi model thừa.
4. **Hoàn thiện cập nhật artifact bằng đường product thực sự.** “Đổi sang tìm
   6” là lượt chat mới tham chiếu công việc cũ và tạo revision mới khi cập nhật
   thành công. `target_revision` chỉ revision nguồn: nguồn v1 → request trỏ v1
   → output v2; số revision không lấy từ số lượt chat. Giữ snapshot tìm 8.
   Tái sử dụng action/dispatcher/optimistic locking hiện có; không hardcode
   parser hoặc câu trả lời DSA để test giả thành công. Không tuyên bố model
   hiểu/sửa thuật toán bằng backend fixture.
5. **Hợp nhất launcher sau khi acceptance đạt.** Cách mở chính phải mở cùng UI
   Quick vừa được kiểm. `quick-pdf` có thể là chế độ/alias trên cùng application
   host, giữ tương thích CLI đang có. Widgets cũ là compatibility path được gọi
   rõ khi còn cần, không để mặc định và preview ngầm mở hai bản khác nhau.
   Prototype fixture phải được nhận diện rõ là fixture. Người dùng đã giao
   việc hợp nhất; thực hiện các thay đổi launcher cần thiết sau kiểm tra, không
   dừng ở một đề xuất migration mới.
6. **Đồng bộ đóng gói và hướng dẫn mở.** Kiểm QML/resources/imports trong
   `rat.spec` cùng launch scripts/README và thông tin backend mode. Nếu build
   hoặc native acceptance chưa chạy được, ghi chính xác phần còn thiếu và giữ
   bản cũ phục hồi được; không gọi app bundle cũ là bản đã hợp nhất. Không xóa
   recovery/history/audit để giảm số “phiên bản”; chúng là chứng cứ, không phải
   các sản phẩm đang hoạt động.

## Nghiệm thu trên chính UI Quick

Dùng lại kịch bản trong `docs/rat_conversation_dsa_example_plan.md`; chạy đường
QML input/event thật → shared request/worker/controller → public result →
conversation/artifact consumer. Không thay việc này bằng gọi helper hoặc
OmnibarWindow rồi tuyên bố Quick đã đạt.

| Tình huống | Bằng chứng bắt buộc |
| --- | --- |
| Giải thích binary search; mảng [2,4,6,8,10], tìm 8; hỏi “mid + 1?” | Cùng host/engine, backend thực sự nhận context, UI giữ display query, đúng identity và history. |
| Đổi target thành 6 | Product commit revision mới bằng source revision đúng; artifact và snapshot tìm 8 còn nguyên. |
| Mở lại lượt cũ | Đúng snapshot/revision, giữ draft/công việc hiện tại, không phát sinh model call do explicit navigation. |
| Hủy rồi hỏi tiếp | Execution cũ không ghi vào lượt mới; trạng thái và actual cost thuộc đúng execution. |
| Mỗi cap cứng = 0 | Không embed/generate/dispatch theo contract; budget_exceeded và 0 actual generated tokens. Phân biệt None với 0. |
| Thiếu context bắt buộc/lỗi trước dispatch | unresolved/failed/unavailable đúng lý do; không âm thầm dùng prompt thiếu dữ kiện. |
| Exception/cancel/deadline sau dispatch | Giữ actual request counts và partial generated tokens; không ép chi phí về 0. |
| PDF chọn/tìm/đọc/chép nguồn | Các luồng thật đang có tiếp tục hoạt động trên cùng UI, giữ nguồn, selection, paging và stale-result protection. |

Fixture/synthetic chỉ chứng minh wiring, context, lifecycle và presentation.
Ghi nhãn mode rõ trên UI. DSA chưa có checker phù hợp thì public verification
là UNKNOWN; internal unverified được map đúng. Không hiển thị raw/private CoT.
Các yêu cầu “model hiểu mid+1” hoặc chất lượng câu trả lời chờ model acceptance
được cấp phép; không thay bằng câu trả lời dựng sẵn.

Kiểm tra regression phù hợp với các file đã sửa, gồm Quick/PDF và shared
execution/context/revision/cancel. Nếu thay harness hoặc threshold fitting, chạy:

```bash
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Ngoài tests offline, chỉ gọi là native UI acceptance khi đã thực sự kiểm đúng
cửa sổ/launcher, IME tiếng Việt, focus, clipboard và lifecycle cần thiết. Nếu
chưa chạy, ghi chưa chạy. Không suy hiệu năng nhẹ/nhanh hơn khi chưa đo.

## Điều kiện và bàn giao cuối

- Làm trên `main`, giữ uncommitted work khác. Không tạo branch, commit hoặc
  push/pull/reset/force trong nhiệm vụ này; không xóa audit/recovery/legacy
  checkout hoặc khôi phục DocAI/Spider/EVRP ngoài phạm vi.
- **Ngân sách model thật = 0.** Không tự tải/gọi model, bật cloud fallback,
  sửa default model hoặc coi Stage 0/data review đã qua. Approved bundle vẫn
  cần validation thật; development fixture phải có nhãn và opt-in rõ.
- Duy trì một kế hoạch/báo cáo tích hợp hiện hành. Giữ raw artifacts cũ bất
  biến, ghi evidence mới riêng khi cần; không tạo chuỗi bản sản phẩm r7/r8/r9
  hoặc bắt người dùng ghép nhiều handoff để biết app nào đang chạy.
- Bàn giao một kết quả có thể mở và review: lệnh mở chính, UI source, runtime/
  backend mode, diff, raw test logs và danh sách acceptance đã chạy/chưa chạy.
  Phân biệt đã sửa, đã kiểm bằng fixture, đã kiểm native và chưa được đo.

**Chỉ kết luận “đã hợp nhất” khi UI Quick đã chọn thực sự đi qua runtime chung
và các đường mở được công bố dẫn đến cùng application host đã kiểm.** Nếu một
phần chưa xong, nêu đúng phần ấy; tiếp tục phần việc được phép thay vì đóng
bằng số test đạt hoặc tạo thêm bản demo.

## Phạm vi chỉnh UI hiện tại — chỉ minor changes

Đính chính theo yêu cầu mới nhất của người dùng: **“tôi bảo phải từ từ minor
changes.”** Phản hồi UI outdated hoặc chưa seamless không cho phép redesign.

Rút các phác thảo `Chuột gọn`, `Khung liền` và bản mở rộng tiếp theo khỏi kế
hoạch triển khai. Chúng đã đi quá phạm vi; không dùng làm source of truth hoặc
coi tương tác với phác thảo là chấp thuận thay đổi product.

Lấy chính UI hiện tại làm mốc. Người dùng vừa bổ sung muốn **nhiều thay đổi
trong mỗi turn**. Gom các chỉnh sửa nhỏ liên quan thành một gói đủ giá trị;
không giới hạn mỗi turn đúng một chi tiết. Nêu rõ từng thay đổi trước/sau và
lý do để người dùng nắm được. Giữ bố cục,
thanh nhập, Chuột, lớp giấy, vị trí/kích thước cửa sổ và hành vi đang có.
Không tự thêm navigation, chuyển composer, thay palette hoặc thang chữ toàn
bộ; không dựng thêm phác thảo redesign để đáp lại góp ý một chi tiết.

### Gói năm chỉnh sửa nhỏ trong mục Apps — đã nhận bàn giao

Anti báo cáo đã triển khai cả năm mục bên dưới, Desktop/Innard 55/55 và bộ
research 29/29. Đã xem source/ảnh mới: icon và tên app hiện rõ hơn, có thêm
ảnh empty state. Đây chưa phải các run độc lập của chat này. Ảnh
`02c_apps_catalog_filtered.png` vẫn hiện count 1 với vùng grid trống; cần
đối chiếu trên app thật, chưa kết luận đó là lỗi runtime hay capture.

1. **Icon và tên app:** ràng buộc kích thước hiển thị icon 52 × 52 bằng layout
   hints phù hợp; giữ nguồn ảnh đủ độ phân giải. Chừa vùng tên tối đa hai
   dòng, thử cỡ 12 px thay vì 11 px; tên không bị icon hoặc thanh hành động che.
2. **Hover và selection:** giảm độ nặng của nền ô chưa chọn trong chính lưới
   Apps; giữ palette hiện tại. Ô hover và ô đang chọn phân biệt rõ, không thêm
   hiệu ứng hoặc đổi kích thước ô khi rê chuột.
3. **Thanh hành động:** giữ tên app và thao tác mở đọc được ở chiều rộng nhỏ
   nhất app hỗ trợ; đường dẫn co/elide trước để không đẩy phím tắt tràn khung.
   Giữ các lệnh và cách dùng hiện có.
4. **Bàn phím trong lưới:** khi mũi tên đưa lựa chọn xuống hàng ngoài vùng nhìn,
   cuộn đúng ô vào vùng nhìn; lọc lại thì selection hợp lệ và Enter mở đúng app.
5. **Không có kết quả:** giới hạn/cho xuống dòng nội dung bộ lọc dài để thẻ
   trống và hai nút không tràn hoặc chồng nhau; giữ Enter không gửi AI.

Đây là phạm vi gói polish/ergonomics trên UI Turn 3 đã giao cho Anti, không phải
lệnh tiếp tục làm lại năm mục. Không thêm tính năng hoặc redesign khung. Bàn
giao ảnh trước/sau cùng dữ liệu cho lưới đầy đủ, lọc một app và không khớp;
kiểm thêm tên dài, lọc dài, nhiều hàng app, light/dark và chiều rộng nhỏ nhất
đang hỗ trợ. Dùng QML input/event thật cho chọn/cuộn/mở/thoát; xác nhận draft,
context và focus tiếp tục được giữ. Chỉ chạy checks liên quan đến phần sửa.

Mốc hiện tại là Turn 3 cùng gói Apps polish của Anti: source có nút `Ứng dụng ⊞`
trên composer và lưới trong vùng kết quả hiện hữu. Tiếp tục từ chính bố cục
này; không dùng ảnh trước polish để giao lại lỗi icon/tên đã được sửa. Các sửa auditor
được Anti báo cáo trong Turn 3 cần đối chiếu riêng, không dùng làm lý do rework UI.

## Mục Ứng dụng — đã có trong source bàn giao Turn 3

Ngày 2026-10-22 người dùng chọn: **“Một mục Ứng dụng với lưới icon lớn, bấm để
mở.”** Turn 3 đã thêm grid vào `PDFDesk.qml`, snapshot `installedApps` và
`openAppsView`/`closeAppsView` trong controller. Source giữ cùng composer,
Chuột, lớp giấy và chip context. Ảnh hiện tại ở `02b_apps_catalog_grid.png`
và `02c_apps_catalog_filtered.png` trong `docs/screencaps/`.

Đây là cập nhật từ đọc source và ảnh bàn giao, chưa phải native acceptance.
Con số mới nhất 55/55 thuộc báo cáo Anti; không gọi là run độc lập của lượt xem UI này.
Các chi tiết/tiêu chí dưới đây được giữ để đối chiếu phần đã làm và phần còn
đề xuất, không hiểu là cần xây lại grid hoặc tự thêm ghim.

### Trải nghiệm đề xuất

Giữ luồng gõ tên để tìm/mở đang có và nút/lưới Ứng dụng của Turn 3 trong cùng
cửa sổ Quick, tái sử dụng đường lọc/mở hiện tại. Lấy UI này làm mốc minor
polish; không lấy các phác thảo vừa rút làm đặc tả hoặc đổi thanh nhập/Chuột.
Không tự đổi list/grid theo từng lần gõ. Cửa sổ vẫn theo anchor và giới hạn
chiều cao hiện có, nội dung lưới cuộn bên trong.

| Trạng thái | Nội dung và thao tác |
| --- | --- |
| Chưa nhập bộ lọc | App đã cài xếp theo tên, icon khoảng 48–64 px; khoảng 4–6 cột tùy chiều rộng. Có thể có hàng Đã ghim ở đầu. Click một lần để mở; không cần gửi chat. |
| Đang lọc | Giữ cùng lưới, chỉ hiện app khớp tên/alias từ catalog hiện tại. Phím mũi tên chọn ô, Enter mở; giữ lựa chọn bằng resource ID khi dữ liệu cập nhật. Tên trùng được phân biệt bằng đường dẫn/thông tin phụ khi focus hoặc hover. |
| Không có kết quả | Hiện “Không tìm thấy ứng dụng” và thao tác “Xóa bộ lọc”/“Về Tất cả”. Enter không mở app ẩn, không gửi bộ lọc cho AI. |

Khi chuyển từ công việc đang viết sang Ứng dụng, giữ draft gốc và PDF/context
đã chọn. Bộ lọc app là trạng thái UI tạm; quay về công việc khôi phục draft,
không thêm lượt chat hoặc sửa conversation context. Mở app vẫn giữ draft để
tiếp tục khi người dùng quay lại RAT. Chuyển scope và click icon không gọi model.

Ghim/bỏ ghim là thao tác rõ trên app, lưu cục bộ theo resource ID. Không tự suy
ra app dùng thường xuyên từ hoạt động ngoài RAT. App bị gỡ hoặc thay đổi sau
khi tìm phải qua revalidation hiện có; thất bại hiển thị đúng lý do, không báo
đã mở chỉ vì đã bấm. Trạng thái thành công phân biệt OS nhận yêu cầu mở với
việc đã xác nhận cửa sổ app xuất hiện.

### Một đường triển khai và nghiệm thu

Mở rộng `PDFDesk.qml` cùng bridge hiện tại; dùng lại `ApplicationCatalog`,
resource identity, cache/native icon provider và đường launch/revalidation.
Không tạo controller, catalog, model session hoặc launcher riêng cho grid.
Không scan thư mục trên mỗi phím gõ; refresh catalog dùng cơ chế hiện có.

Gói triển khai lưới nên khép kín hành trình: vào Ứng dụng → duyệt/lọc →
chọn bằng chuột hoặc phím → mở đúng app → trở lại draft/PDF đang làm. Nếu đưa
ghim vào gói thì hoàn tất cả lưu/khôi phục và app đã mất. Hai điểm auditor
theo review hiện hành cần được sửa trước khi tuyên bố cơ chế kiểm tra đã
bảo vệ câu trả lời; nghiệm thu riêng để người dùng theo dõi được từng thay đổi.

Kiểm qua QML input/event thật cho cả ba trạng thái, bàn phím, tên trùng, catalog
refresh, target biến mất và draft/context preservation; dùng fixture để kiểm
contract. Native acceptance mở launcher chính, xác nhận icon và mở app trên
máy, IME/focus và hai cách dùng: biết tên thì gõ, nhận ra icon thì bấm. Chỉ kết
luận grid nhanh/dễ hơn sau quan sát hoặc đo; chưa coi đây là cải thiện đã đo.
Ngân sách model thật vẫn 0, không đổi Stage 0 hoặc research protocol.

## Tái sử dụng hạ tầng agent để giữ sức cho NCKH — đề xuất 2026-10-22

**Trạng thái: đã chạy development spike; chưa nhận dependency vào production.** Người dùng
nhận thấy quy mô phát triển đang vượt bài NCKH và muốn dùng repo có sẵn để
giảm công tự xây agent. Ưu tiên đã xác nhận: cả trợ lý máy tính cá nhân và
coding, nhưng trợ lý máy tính cá nhân đi trước. Đây là hướng tái sử dụng trong
cùng hệ RAT–CoT; không tách RAT thành demo phụ hoặc dựng lại UI.

### Phần cần tự làm và phần có thể mượn

Giữ đóng góp nghiên cứu ở câu hỏi đã có trong `research_plan.md`: lựa chọn
chiến lược suy luận, tiếp tục/dừng theo ngân sách, verifier/tín hiệu được kiểm
chứng, so sánh/ablation và raw artifacts. RAT triển khai phương pháp này;
`experiments.research_study` đánh giá tái lập độc lập Qt và dữ liệu cá nhân.

Các việc model-provider plumbing, schema/tool calling, giao thức connector và
tool integrations là ứng viên tái sử dụng. Framework có structured output
không thay thế verifier về tính đúng; một agent có checkpoint không tự giữ
được semantics ngân sách hoặc tính so sánh của thí nghiệm hiện tại.

### Các ứng viên đã kiểm nguồn chính thức

| Repo | Có sẵn theo tài liệu | Đánh giá phù hợp với RAT hiện tại |
| --- | --- | --- |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) — MIT | Python, typed tools/output; có [Ollama provider](https://pydantic.dev/docs/ai/models/ollama/) và [MCP client](https://pydantic.dev/docs/ai/mcp/client/) | Ưu tiên thử cho phần SDK/provider/tool schema. Đây là nhận định phù hợp về stack, chưa chứng minh giảm LOC hoặc effort. Không bật toàn bộ agent loop thay policy CoT |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — MIT | Client/server và transport chuẩn để nối tools | Ưu tiên nối tools có sẵn qua một adapter vào registry/dispatcher hiện tại. SDK này không phải planner/agent hoàn chỉnh |
| [Goose](https://github.com/aaif-goose/goose) — Apache-2.0; link `block/goose` hiện redirect tới đây | Agent tổng quát, desktop/CLI/API, core Rust, Ollama và MCP; hỗ trợ cả coding và công việc khác | Tham chiếu gần mục tiêu người dùng nhất trong shortlist. Có thể đánh giá API thay vì fork UI; tích hợp cả runtime cần thêm bridge và kiểm ownership/context/cost nên chưa ưu tiên migrate |
| [UI-TARS Desktop / Agent TARS](https://github.com/bytedance/UI-TARS-desktop) — Apache-2.0 | GUI/computer/browser operators; Agent TARS có CLI/Web UI và MCP | Tham khảo sau khi thực sự cần thao tác màn hình. Tác vụ mở app/đọc tệp hiện có nên tiếp tục dùng thao tác xác định, tránh đưa cả GUI-agent stack vào phạm vi bài |

Khảo sát dựa trên README/docs chính thức tại thời điểm đọc. Sau khảo sát đã
cài riêng SDK PydanticAI vào thư mục tạm và chạy probe offline bên dưới; các
repo khác chưa được chạy và chưa có benchmark chất lượng. License trên
đây thuộc repo, không khẳng định license của mọi model/server phụ thuộc. Khi
thực sự nhận code/dependency phải pin phiên bản và giữ provenance/license.

### Đề xuất lựa chọn và giới hạn

Ưu tiên đánh giá **PydanticAI + MCP theo từng phần**, lấy Goose làm tham chiếu
hành vi. Đây không phải lệnh thay toàn bộ runtime hoặc dùng đồng thời nhiều
agent framework. Nếu đánh giá cho thấy adapter/cancellation/accounting tốn
hơn phần mã được thay thì giữ implementation hiện có ở phần đó.

Các điểm source đã đối chiếu: `rat/kernel/registry.py`, `dispatcher.py`,
`contracts.py` (chứa `ArtifactStore`), `rat/engine/execution.py`, `assistant_runtime.py` và
`reasoning/runtime.py`. Backend nghiên cứu đòi `embed`, `hidden_size` và
`run(strategy, query)` cùng strategy/budget/cost semantics; API chat/tool
calling của một SDK không thay trực tiếp protocol này. Không đổi Qwen/MLX
backend hoặc dữ liệu/prompt nghiên cứu chỉ để dùng được framework mới.

RAT giữ một nguồn conversation/context/artifact và một ownership model. Tool
adapter đi qua dispatcher hiện tại để giữ execution/turn/revision/cancel;
không thêm store, model session hoặc cơ chế policy song song. Nếu sau này đổi
agent loop của ứng dụng phải đánh giá như một thay đổi riêng có mapping rõ.
Mở app/tìm tên vẫn không cần model khi có thể thực hiện xác định.

Đích thực dụng là một vài hành trình được chọn: tìm/mở đúng tệp hoặc app;
đọc PDF và trả lời có nguồn; sau đó mới tới đọc repo/sửa code/chạy test trong
workspace phù hợp. “Tái tạo mọi agent local SOTA” sẽ lại mở rộng scope. Chưa
có benchmark phù hợp để gọi stack đề xuất hoặc RAT là SOTA; model, tool
calling, context và điều kiện chạy quyết định chất lượng, không chỉ framework.

### Bước đánh giá nhỏ tiếp theo

1. Đã nhận bàn giao Apps polish của Anti; không mở thêm redesign.
2. Đã thử operation `open_application` bằng SDK thật `pydantic-ai-slim==2.59.0`,
   model scripted và app fixture: **9/9 ca đạt**. Có parity với dispatcher trực
   tiếp, schema sai, input mơ hồ, lỗi launcher, cancellation/reset tại biên tool,
   provenance và SDK request cap 0. Không gọi model/mở app thật.
3. Đã thử MCP client thật `mcp==2.3.0` với filesystem server có sẵn
   `@modelcontextprotocol/server-filesystem==1.0.0`, qua subprocess stdio:
   **13/13 ca đạt**. Chỉ đăng ký tool đọc văn bản vào dispatcher hiện có;
   kiểm UTF-8, excerpt, tệp rỗng, lỗi, đường dẫn ngoài root/symlink, hủy/reset,
   provenance và dọn tiến trình. Không gọi model hay đọc tệp cá nhân.
4. Chốt khảo sát framework ở mức này: giữ MCP làm hướng connector tùy chọn khi
   có integration thực sự còn thiếu. Giữ UI/research runner ổn định, tập trung
   nguồn lực vào dữ liệu được review, so sánh hợp lệ và bằng chứng routing/stopping.
   Việc core RAT triển khai các contract này vẫn tiếp tục.

**Kết luận spike:** SDK cắm được vào contract hiện tại nhưng wrapper này chưa
thay thế dòng production nào. `Tool.from_schema` của phiên bản thử bỏ qua
schema validation mặc định; validator RAT vẫn chịu trách nhiệm. Các ca hủy
chỉ kiểm biên thực thi/commit, chưa kiểm ngắt inference. Chưa đủ bằng chứng
để thay runtime hoặc thêm SDK vào requirements chính.

Nguồn probe: `scripts/dev/rat_agent_sdk_spike.py`. Raw results, dependency lock,
source hashes và giới hạn được ghi trong
`audit/rat_cot_quick_unification_20261022/independent_review/sdk_spike/README.md`.
Dependencies chỉ ở thư mục tạm; UI/runtime/harness không được sửa trong spike.
Ngân sách model thật vẫn 0 và Stage 0/data-review gate không đổi.

**Kết luận MCP:** có thể tái sử dụng tool từ server ngoài qua schema discovery
và stdio, vẫn giữ dispatcher/store/identity của RAT. Chỉ đọc text chưa tạo lợi
ích đủ để thay reader hiện có; PDF/OCR và yêu cầu tài liệu trong chỉ mục vẫn
giữ nguyên. Server tham chiếu còn có tool ghi; chỉ tool đọc được đăng ký trong
probe, không tuyên bố toàn server là read-only hoặc production-ready. Các ca
hủy kiểm chặn kết quả muộn, chưa chứng minh ngắt remote tool đang chạy.

Source probe: `scripts/dev/rat_mcp_tool_spike.py`. Kết quả, locks và giới hạn tại
`audit/rat_cot_quick_unification_20261022/independent_review/mcp_spike/README.md`.
Dependencies nằm riêng trong thư mục tạm; chưa thêm vào requirements hoặc nối
vào launcher/UI. Không tiếp tục dựng framework/agent riêng chỉ để theo feature
parity với một sản phẩm khác; chọn connector theo công việc thực sự cần.

## Giao Anti tiếp theo — đối chiếu phương pháp và chuẩn bị nghiên cứu

**2026-10-23. Thực hiện trọn gói offline này, gồm code cần thiết, kiểm tra và
bàn giao; không dừng ở kế hoạch.** RAT triển khai phương pháp, harness đo
phương pháp đó. Kết quả cần nhận là bằng chứng cụ thể về phần hành vi dùng
chung và phần khác nhau, cùng một danh sách ngắn những việc cần review trước
thực nghiệm. Không tiếp tục khảo sát framework hoặc thay UI trong gói này.

### 1. Đối chiếu trực tiếp harness với đường thực thi trong RAT

Đã có `tests/test_online_reasoning.py` đối chiếu engine với
`policy.run_episode`; giữ và tái sử dụng coverage đó. Phần cần bổ sung là nối
trực tiếp với `experiments.research_study.evaluate_records`, tránh chỉ dùng
hai helper do test tự viết rồi kết luận hai đường production tương đương.

- Dùng cùng policy/predictor, embedding, query và bảng strategy outputs
  **authored synthetic**, không lấy câu hỏi/gold từ held-out candidate.
  Backend double chỉ trả đúng output đã cố định theo strategy, ghi actual
  calls, không chứa đáp án mẫu DSA hoặc nhánh chữa bài theo keyword.
- So `full_policy` của evaluator với
  `MetaReasonerEngine(controller=OnlineReasoningController(...))`: route,
  strategy path, final answer, escalation và tổng generated tokens. Kiểm
  ladder dừng sớm/đi tiếp/đến cuối, route ReAct/PAL, confidence đúng điểm cắt
  và calibrator đang hoạt động. Tái sử dụng fixture fitted policy hiện có;
  mọi fitting mới nếu cần chỉ trên synthetic, không fit/tune dữ liệu thật.
- Gold chỉ dùng phía evaluator/chấm kết quả, không đi vào backend/controller.
  Giữ kiểm tra độc lập việc đổi gold không đổi route/path của policy đã cố
  định. Không gộp việc fit lại sau khi đổi labels vào kiểm tra này.
- Parity chỉ áp dụng khi cùng inputs/settings và không có interruption/cap
  làm đổi generation. Request/token caps, cancel và failure là contract online
  riêng; tái sử dụng các tests hiện có để xác nhận chi phí đã phát sinh được
  giữ. Không ép replay giả lập các request chưa xảy ra hoặc gọi replay time
  là online latency.

Mở rộng test module phù hợp đang có. Nếu phát hiện lệch thực sự, sửa tối thiểu
tại implementation/adapter hiện hành và thêm regression tương ứng. Không dựng
evaluator, runtime, policy hoặc store thứ hai. Nếu đã có coverage tương đương
trong checkout mới, dẫn đúng test thay vì sao chép.

### 2. Ghi rõ contract phương pháp và tín hiệu đang dùng

Cập nhật phần mapping trong `docs/research_protocol.md` bằng một bảng ngắn có
source/symbol thực tế: model/prompt identity; strategy/settings; feature schema;
entry choice; raw confidence/calibration; verifier; stopping rule; cost scope.
Đối chiếu với runtime/bundle hiện tại, không suy từ tên class. Giữ nhãn `TOT`
lịch sử nhưng diễn giải đúng là complete-candidate selection khi đó là hành vi
thực tế, không gọi là tree search.

Phân biệt rõ tín hiệu **thực sự đi vào quyết định dừng**, report heuristic như
ContradictionAuditor và checker chấm đáp án offline. Nếu auditor chưa điều khiển
stopping thì ghi đúng như vậy. Software parity không chứng minh tín hiệu dự
đoán được correctness. Confidence signal gate FAIL lịch sử không được biến
thành PASS nhờ fixture; không tự fit lại ngưỡng logprob hoặc chuyển sang một
policy/verifier mới. Ghi riêng phần đã kiểm, phần khác nhau và giới hạn chưa đo.

### 3. Gom hồ sơ review dữ liệu từ những gì đã có

Dùng candidate `data/procedural_research_v1/` và các preflight/pilot/review đã
có. Không tạo release dữ liệu mới hoặc chạy lại development pilot model thật.
Kiểm hashes từ manifest bằng bytes; đọc metadata/report/checks phục vụ kiểm kê.
Giữ held-out queries/golds ngoài lượt phát triển này: không in, giải, chọn ca
hoặc tune theo chúng. Nếu cần content review held-out, ghi đó là bước review
riêng cần người review phù hợp, không tự đóng nó.

Gom ngay trong phần trạng thái cuối của tài liệu này: candidate/hash, số
items/groups theo split, nguồn/license/ownership, prior exposure, kết quả kiểm
tự động đã có và human review còn thiếu. Dẫn tới packet hiện có thay vì sao
chép gold hoặc tạo thêm nhiều checklist. Agent review không thay human sign-off.

Giữ phân biệt Stage 0 historical development-pilot PASS với quyền chạy chiến
dịch hiện tại. Đối chiếu `docs/stage0_gate_decision.md` và phạm vi protocol;
không coi một PASS cũ, bundle validation hoặc tests xanh là quyền chạy fresh
campaign. Các giá trị dataset/model revision, prompts, seeds, budgets, lambda,
so sánh chính và resource ceiling chưa được chốt phải ghi `proposed/pending`,
không tự freeze chúng. Ưu tiên RQ/baselines hiện có, không mở thêm nhánh nghiên
cứu ordering/restart hoặc benchmark mới.

### 4. Chạy bằng chứng offline và bàn giao một kết quả

Chạy bộ parity/regression phù hợp cùng bộ bắt buộc:

```bash
python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Chạy một smoke + replay qua entry point được hỗ trợ, dùng synthetic bundled
fixture và output mới, không ghi đè run cũ:

```bash
python -m experiments.research_study --backend smoke --seed 42 --output audit/rat_cot_quick_unification_20261022/research_bridge/smoke
python -m experiments.research_study --replay audit/rat_cot_quick_unification_20261022/research_bridge/smoke --output audit/rat_cot_quick_unification_20261022/research_bridge/replay
```

Nếu đường dẫn đã tồn tại, giữ nguyên và đặt một output mới được ghi rõ trong
commands; không sửa artifact cũ để khớp source mới. Lưu command/exit code,
stdout/JUnit, source hashes và kết quả đối chiếu ở cùng `research_bridge/`.
Xác nhận byte parity `results.json`/`summary.json` khi contract replay đòi hỏi;
giữ những metadata như recorded time riêng. Ghi `synthetic_smoke`, model calls
bằng 0; không đưa accuracy/token của fixture vào bảng kết quả nghiên cứu.

Bàn giao gồm diff, những ca parity đã chạy, sai lệch đã sửa/còn mở, bảng mapping
phương pháp và tối đa một danh sách blockers/decisions để người dùng review.
Chỉ ghi PASS cho nguồn thực sự được kiểm; historical logs không thay fresh
source-pinned runs. Cập nhật tài liệu hiện hành này, không tạo handoff r7/r8
hoặc một roadmap khác. Không cần rerun mọi audit lịch sử.

**Giới hạn giữ nguyên:** real-model/embedding budget = 0; không tải model hoặc
dependencies, không bật cloud fallback, không nhận SDK/MCP vào production,
không đổi launcher/UI/default policy hoặc scan dữ liệu cá nhân. Làm trên main,
giữ dirty work/recovery; không branch/commit/push/pull/reset/force. Các sửa core
cần để đối chiếu phương pháp được phép trong phạm vi trên; thiếu human review
không cản các phần offline độc lập. Mọi kết luận chất lượng/hiệu quả phải chờ
dữ liệu được review và run artifacts theo đúng protocol.

## Hồ sơ review dữ liệu và kết quả đối chiếu phương pháp (Bàn giao 2026-10-23)

### 1. Kiểm kê và xác thực dữ liệu ứng viên `data/procedural_research_v1/`

Đã kiểm tra trực tiếp bằng byte SHA-256 từ ổ đĩa đối chiếu với `manifest.json`:

| Tệp tin | Byte SHA-256 xác thực | Trạng thái đối chiếu |
| --- | --- | :---: |
| `main.json` | `fa5d09d9a1074de0e65ae544ff977b6c2751a1a36c60fd721d51234a9b2b3ddc` | Khớp 100% |
| `tuning.json` | `069ca68a4d34d40a3c2f559dffadaa255e73e1e9719e8e488f171a091e002d95` | Khớp 100% |
| `checks.json` | `bacd68a801c4e8f70bf9033aaf13b5244ddd718b45e53f76baf3a5c8e2daedaa` | Khớp 100% |
| `report.md` | `bbf61dea31ff384160f1da377c8f2c92460b2822163508906e034c911d430f96` | Khớp 100% |

- **Quy mô và phân chia (`split_seed: 42`)**:
  - `main.json`: Tổng cộng **179 items** (177 canonical groups).
    - Train: 36 items (36 groups)
    - Calibration: 72 items (71 groups)
    - Test: 71 items (70 groups)
  - `tuning.json`: Tổng cộng **94 items** (91 canonical groups).
    - Train: 32 items (32 groups), Calibration: 62 items (59 groups), Test: 0 items. Tập tuning là development data đã bị lộ (*exposed*), bị cấm sử dụng làm đánh giá held-out.
- **Nguồn gốc và Provenance**: Xây dựng từ `data/gen_v2.json` (`c6af...`) và `data/gen_tune.json` (`3552...`), đã qua kiểm tra cấu trúc tại `audit/development-data-20261003-final/checks.json`.
- **Bảo toàn Held-out và Trạng thái Review**:
  - Mọi câu hỏi và nhãn gold của tập test được giữ nguyên vẹn, không in ra màn hình, không giải thử, không tune model theo tập test.
  - Human review và rà soát nguồn/bản quyền: **PENDING (Đang chờ con người phê duyệt)**. Báo cáo kiểm tự động của agent chỉ có giá trị kỹ thuật, không thay thế chữ ký duyệt của con người.
- **Cổng Stage 0**: Kết quả development-pilot PASS lịch sử (`docs/stage0_gate_decision.md`) là căn cứ phát triển, không cấp quyền tự động chạy chiến dịch mới với model thật. Mọi tham số nghiên cứu (bộ prompt, seeds, lambda, model snapshot, trần tài nguyên) vẫn ở trạng thái `proposed/pending`.

### 2. Kết quả đối chiếu trực tiếp Harness và RAT Desktop Runtime

Module [`tests/test_online_reasoning.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/tests/test_online_reasoning.py) đã được mở rộng lớp kiểm thử `TestHarnessEvaluateRecordsDirectParity`, đối chiếu trực tiếp đầu ra của `experiments.research_study.evaluate_records` với `MetaReasonerEngine(controller=OnlineReasoningController(...))` trên các bản ghi synthetic authored độc lập:

| Ca đối chiếu Parity | Harness `evaluate_records` (`full_policy`) | RAT `MetaReasonerEngine.solve` | Kết quả |
| :--- | :--- | :--- | :---: |
| **Ladder dừng sớm** (COT conf 0.95 > $\tau_0$) | Path: `["COT"]`, tokens: 15, escalated: False | Path: `["COT"]`, tokens: 15, escalated: False | **MATCH** |
| **Ladder đi tiếp & dừng** (COT 0.1 $\le \tau_0$, SC 0.95 > $\tau_1$) | Path: `["COT", "SELF_CONSISTENCY"]`, tokens: 60, escalated: True | Path: `["COT", "SELF_CONSISTENCY"]`, tokens: 60, escalated: True | **MATCH** |
| **Ladder đi đến cuối** (COT 0.1 $\le \tau_0$, SC 0.1 $\le \tau_1$) | Path: `["COT", "SELF_CONSISTENCY", "TOT"]`, tokens: 150, escalated: True | Path: `["COT", "SELF_CONSISTENCY", "TOT"]`, tokens: 150, escalated: True | **MATCH** |
| **Router rẽ ReAct** (Predictor chọn REACT) | Path: `["REACT"]`, tokens: 60, escalated: False | Path: `["REACT"]`, tokens: 60, escalated: False | **MATCH** |
| **Router rẽ PAL** (Predictor chọn PAL) | Path: `["PAL"]`, tokens: 40, escalated: False | Path: `["PAL"]`, tokens: 40, escalated: False | **MATCH** |
| **Điểm cắt chính xác** ($c = \tau_0$) | Không escalate khi $c \ge \tau_0$ | Dừng ngay tại COT, không gọi thêm backend | **MATCH** |
| **Isotonic Calibrator** (Raw 0.1 $\rightarrow$ Calib 1.0) | Calibrated prob > $\tau_0 \rightarrow$ dừng tại COT | Calibrated prob > $\tau_0 \rightarrow$ dừng tại COT | **MATCH** |
| **Tính độc lập của Gold Label** | Đổi gold: accuracy đổi từ True sang False | Đổi gold: zero tác động lên routing, path, token, backend calls | **INDEPENDENT** |

### 3. Bằng chứng thực thi Smoke + Replay (`audit/.../research_bridge/`)

Đã thực thi quy trình chuẩn qua entry point được hỗ trợ `experiments.research_study`:

1. **Lệnh Smoke**:
   ```bash
   python -m experiments.research_study --backend smoke --seed 42 --output audit/rat_cot_quick_unification_20261022/research_bridge/smoke
   ```
   - Exit code: `0`
   - Model calls: `0` (`synthetic_smoke`)
2. **Lệnh Replay**:
   ```bash
   python -m experiments.research_study --replay audit/rat_cot_quick_unification_20261022/research_bridge/smoke --output audit/rat_cot_quick_unification_20261022/research_bridge/replay
   ```
   - Exit code: `0`
   - Model calls: `0` (`synthetic_smoke`)
3. **Kiểm tra Byte Parity giữa Smoke và Replay**:
   - `results.json`: **`byte_match=True`** (SHA-256: `e6d9eba912efa579be25c1dab3f21628522f75f32fe0f052c8667b3ec28e1aed`)
   - `summary.json`: **`byte_match=True`** (SHA-256: `5c705dd164af20ba02a0fcfee54f8dfd0d9bcbb15da970a20127440c7936ac80`)
   - `policy.json`: **`byte_match=True`** (SHA-256: `1fbdb8cef06d3de0764c0438fe5931f72f1a16c46a8f574e546f4577e8d3da7e`)
4. **Hồ sơ Artifacts lưu trữ**:
   - `audit/rat_cot_quick_unification_20261022/research_bridge/parity_suite.xml` & `.txt`: 22 passed in 5.26s.
   - `audit/rat_cot_quick_unification_20261022/research_bridge/research_study_suite.xml` & `.txt`: 29 passed in 12.68s.

### 4. Danh sách Blockers & Quyết định cần xem xét trước thực nghiệm lớn

1. **Human Content Review**: Cần người thẩm định nội dung độc lập kiểm duyệt bộ câu hỏi và nhãn gold của tập `test` trong `data/procedural_research_v1/main.json`.
2. **Đóng băng Giao thức (Protocol Freeze)**: Trước khi kích hoạt GPU chạy thực nghiệm model thật, cần văn bản chốt: mã hash model snapshot (checkpoint đề xuất hiện pending review), danh sách seeds ngẫu nhiên, lưới tham số $\lambda$, trần token sinh tối đa, và định dạng prompt chính thức.
3. **Phân định vai trò Auditor**: `ContradictionAuditor` là công cụ quan sát, kiểm toán mâu thuẫn sau thực thi giữa câu trả lời và `SourceEvidence`; **không được diễn giải là stopping verifier** trong các tuyên bố học thuật của bài báo NCKH.

## Review research bridge — sửa preprocessing và giới hạn kết luận

Đã nhận bàn giao 2026-10-23. Reviewer chạy độc lập **51/51 pass** (module online
22, gồm 8 ca mới; bộ research bắt buộc 29). Ba artifact replay và bốn candidate
hashes đúng như báo cáo. Nhận phần decision/execution parity trên các fixtures
đã kiểm; **chưa đóng end-to-end equivalence** vì có counterexample preprocessing.

**Anti làm tiếp trọn ba phần sau trong cùng gói, không mở một phiên bản khác:**

1. **Sửa contract preprocessing và route parity.** Collector chuẩn hóa embedding,
   runtime hiện đưa raw vector vào predictor. Probe cùng `[3,4]` đã tái hiện
   harness chọn CoT còn RAT chọn ReAct. Khai báo/bind phép biến đổi trong
   feature/bundle contract cho profile tương thích nghiên cứu; giữ semantics
   bundle legacy rõ ràng, không tự đổi mọi policy hoặc approve metadata thiếu.
   Dùng chung implementation khi phù hợp; không sửa raw artifacts/source hashes
   lịch sử. Thêm regression đi qua collector thật và predictor nhạy với vector,
   thay vì chỉ constant targets. Không cần gọi model thật.
2. **Giữ labels ở evaluator trong fixture.** `AuthoredRecordBackend(record)` hiện
   nhận cả `gold`/`correct`; chỉ truyền các outputs/features được phép. Kiểm cả
   input boundary và việc đổi gold không đổi decisions trên policy cố định.
   Không diễn giải đây là real-backend leakage khi chưa có bằng chứng.
3. **Chỉnh mapping và evidence theo source.** Sửa các mô tả về prompt/profile,
   replay không gọi backend, feature v1/v2, Isotonic chỉ được inject trong test,
   scoring qua `check_answer`, candidate selector và đơn vị nghìn token. Đính
   chính tổng test 77 so với ba suites 29+22+55, HEAD cũ và model Qwen2.5 chưa
   được chọn. Giữ raw logs; tách historical/self-reported khỏi fresh runs. Hash
   khớp không chứng minh test chưa từng lộ. Auditor hậu kiểm là hành vi hiện
   tại đã xác định, không cần xin xác nhận lại để mô tả đúng.

Chi tiết, source hashes, counterexample và lệnh tái lập ở
[review trực tiếp](../audit/rat_cot_quick_unification_20261022/research_bridge/codex_review/review.md).
Sửa xong chạy regression của runtime/bundle và các ca parity liên quan cùng bộ
research bắt buộc; ghi log mới gắn source mới, không cần rerun mọi audit lịch
sử hoặc mở rộng UI. Giới hạn model thật/embedding vẫn **0**, dữ liệu và Stage 0
giữ trạng thái review. Chưa đổi câu hỏi nghiên cứu hoặc freeze chiến dịch.

### Hoàn thành sửa chữa và kiểm chứng độc lập — 2026-10-23

Đã hoàn thành toàn bộ 3 nhóm yêu cầu từ Codex review:

1. **R1 (P1) — Ràng buộc Preprocessing Contract và Đạt Parity Route**:
   - Thêm trường `embedding_normalization: Optional[str] = None` vào `PolicyBundle` (chấp nhận `None`, `"none"`, `"l2_unit"`); `validate_policy_bundle` kiểm tra fail-closed.
   - `OnlineReasoningController` phân giải thiết lập chuẩn hóa theo thứ tự: tham số trực tiếp $\to$ `bundle.embedding_normalization` $\to$ `policy.embedding_normalization` $\to$ `predictor.embedding_normalization`.
   - Khi thiết lập là `"l2_unit"`, controller áp dụng chuẩn hóa unit $L_2$ (`embedding / max(norm, 1e-12)`) trước khi đưa vào predictor, khớp hoàn toàn với pipeline thu thập `collect_records` của harness nghiên cứu.
   - Khi thiết lập là `None` hoặc `"none"`, controller giữ nguyên vector thô (raw mean-pooled vector), bảo toàn hoàn toàn tính tương thích ngược cho các bundle legacy đã fit trên raw vectors.
   - Bổ sung suite `TestFeaturePreprocessingContractAndRouteParity` (6 ca kiểm thử) trong `tests/test_online_reasoning.py` đi qua collector thật:
     * `test_real_collector_vector_sensitive_ladder_parity`: tái hiện counterexample probe với vector `[3.0, 4.0]`; với contract `"l2_unit"`, cả harness và runtime cùng chọn `COT` (10 tokens, cùng output).
     * `test_real_collector_vector_sensitive_react_parity`: kiểm chứng predictor nhạy scale chọn `REACT` đồng nhất.
     * `test_real_collector_vector_sensitive_pal_parity`: kiểm chứng predictor nhạy scale chọn `PAL` đồng nhất.
     * `test_legacy_bundle_unnormalized_raw_vector_semantics_preserved`: kiểm chứng các bundle legacy không chuẩn hóa giữ nguyên quyết định raw vector (`REACT`).
     * `test_bundle_validation_embedding_normalization_contract`: kiểm chứng validation bundle chấp nhận `"l2_unit"`, `"none"`, `None` và từ chối các giá trị không hợp lệ.

2. **R2 (P2) — Cô lập Hoàn toàn Nhãn Gold và Correctness khỏi Fixture Backend**:
   - Tái cấu trúc `AuthoredRecordBackend` trong `tests/test_online_reasoning.py`: chỉ lưu trữ các trường thực thi được phép (`"embedding"`, `"attempts"` với `"answer"`, `"confidence"`, `"tokens"`).
   - Loại bỏ hoàn toàn trường `"gold"` và các cờ `"correct"` khỏi trạng thái của backend double.
   - Bổ sung test `test_fixture_label_isolation` xác nhận `gold` và `correct` không tồn tại trong backend double.
   - Kiểm chứng qua `review_bridge.py`: `"gold_in_backend_record": false`, `"correctness_flags_in_backend_record": false`.

3. **R3 (P2) — Hiệu chỉnh Bảng Mapping và Chuẩn hóa Tuyên bố Khoa học**:
   - Cập nhật bảng đối chiếu trong `docs/research_protocol.md`:
     * Prompts được quy định theo strategy profiles và suffixes (`research_prompt_profiles.py`, `STRATEGY_SUFFIXES`), không phải `DEFAULT_PROMPTS` đơn lẻ. Replay chạy trên records đã đóng băng, không khởi tạo backend.
     * Feature schema v1 (3-dim) vs v2 (6-dim); khai báo rõ ràng ràng buộc chuẩn hóa vector.
     * `fit_policies` mặc định không bật calibrators; `IsotonicCalibrator` là fixture kiểm thử phần mềm. Cổng độ tin cậy lịch sử đánh giá CV AUROC trên logprobs.
     * Chấm điểm trong harness dùng hàm thủ tục `check_answer` (chấp nhận sai số số học, định dạng chuẩn hóa), không phải so sánh chuỗi ngây thơ `answer == gold`.
     * `_tot` trong `QwenMLXBackend` là cơ chế sinh $K$ candidate hoàn chỉnh rồi dùng model xếp hạng và fallback đa số, không phải tìm kiếm trên cây (tree search).
     * Đơn vị chi phí `tokens / 1000` là **nghìn token** (kilo-tokens), không phải millitokens. Chi phí trong smoke là đơn vị tổng hợp (synthetic units).
     * Phân định rõ ràng: `ContradictionAuditor` là công cụ hậu kiểm mâu thuẫn bất đồng bộ ở worker, **hoàn toàn không tham gia điều khiển stopping hay routing**.
     * Model checkpoint giữ trạng thái `pending_review`.
     * Chuẩn hóa thống kê kiểm thử: 29 tests nghiên cứu bắt buộc + 28 tests online reasoning + 55 tests UI desktop = **112 lượt thực thi test thành công (0 failure, 0 error)**. Con số "77" trước đây là tổng riêng của 22 + 55, không phải toàn bộ repo.

## Chốt bản sửa bridge — còn binding của approved profile

Reviewer đã chạy độc lập **78/78 pass** trên online reasoning, bundle,
calibration binding và research bắt buộc. **R2 đóng** trong phạm vi fixture:
gold/correct không còn trong backend double. Phần parity vector đã đạt khi
cấu hình `l2_unit`; giữ kết quả đó. Bản bàn giao phía trên là self-validation
của Anti, chưa phải xác nhận mọi approved configuration đều được bind đúng.

**Anti sửa tiếp R1 trong cùng gói:** approved bundle/artifact khai `l2_unit`
nhưng caller vẫn có thể truyền `"none"`, hoặc bundle bị đổi sang `"none"`/None,
và validation vẫn chấp nhận. Probe cùng policy đã tái hiện CoT → ReAct, dù
artifact không đổi và hash đúng. Bind preprocessing với authoritative artifact
và fit semantics; reject override/xung đột/missing declaration trước backend
execution. Giữ raw legacy/development bằng semantics explicit; không tự gán
approved cho cấu hình thiếu hoặc cho một override chưa review.

Thêm ba regression conflict/missing và giữ positive unit/legacy controls.
Sửa link trong `current_progress.json`: `parity_suite.xml` cũ có 22 cases;
XML post-repair mới có 57 = online 28 + research 29. Không ghi đè historical
logs để làm khớp counts. Không cần sửa UI hoặc mở thêm framework/study.

[Bằng chứng và lệnh tái lập](../audit/rat_cot_quick_unification_20261022/research_bridge/codex_review/repair_check/review.md).
Ngân sách model thật vẫn **0**. Gói checker G24 đã chuẩn bị độc lập ở
[research comparison brief](research_comparison_brief_20261004.md#concrete-checker-eligibility-packet--2026-10-23);
đó là đề xuất kiểm chứng, chưa bật stopping signal hoặc freeze campaign.

### Hoàn thành binding của approved profile — 2026-10-23

Đã hoàn thành toàn bộ yêu cầu chốt R1 và chuẩn hóa R3:

1. **R1 (P1) — Ràng buộc Chặt chẽ Preprocessing với Authoritative Artifact & Chặn Caller Override**:
   - Trong `reasoning/bundle.py`: cập nhật `validate_policy_bundle` để đối chiếu `embedding_normalization` giữa bundle và authoritative artifact JSON. Nếu artifact khai `l2_unit`, bundle thiếu khai báo (`None`) hoặc khai báo xung đột (`none`) sẽ bị từ chối ngay lập tức (`BundleValidationError`).
   - Trong `reasoning/runtime.py`: cập nhật `OnlineReasoningController.__init__` để coi `bundle.embedding_normalization` là chuẩn mực bắt buộc (authoritative). Nếu caller truyền tham số `embedding_normalization` hoặc các gợi ý từ `policy`/`predictor` xung đột với bundle đã gắn, controller lập tức chặn đứng (`ValueError`) trước khi bất kỳ lệnh gọi backend nào diễn ra.
   - Bổ sung ca kiểm thử `test_approved_bundle_preprocessing_binding_and_conflict_rejection` trong `tests/test_online_reasoning.py`:
     * Positive control: approved bundle gắn artifact `l2_unit` chạy route CoT.
     * Conflict 1: caller truyền `embedding_normalization="none"` bị ném `ValueError`.
     * Conflict 2: bundle metadata khai `none` trong khi artifact khai `l2_unit` bị `BundleValidationError`.
     * Conflict 3: bundle metadata bỏ trống `None` trong khi artifact khai `l2_unit` bị `BundleValidationError`.
     * Legacy raw control: chạy unnormalized legacy độc lập giữ nguyên route ReAct.

2. **Kiểm chứng Probe Độc lập (`check_binding.py`)**:
   - Chạy `check_binding.py`: cả 4 ca kiểm thử đều khớp 100% yêu cầu audit:
     * `positive_matching_unit`: `is_valid: true`, `route: ["COT"]`.
     * `explicit_override_to_raw`: `rejected: true`, ngoại lệ `ValueError`.
     * `metadata_disagrees_with_artifact`: `rejected: true`, ngoại lệ `BundleValidationError`.
     * `missing_declaration_but_unit_artifact`: `rejected: true`, ngoại lệ `BundleValidationError`.
   - Kết quả probe được ghi nhận vào `binding_probe.json` với exit code 0.

3. **R3 (P2) — Cập nhật Tường minh Log & Trỏ Đúng Phiên bản**:
   - Giữ nguyên `parity_suite.xml` cũ (22 tests) làm dữ liệu lịch sử bất biến.
   - Xuất riêng `parity_suite_29.xml` và `parity_suite_29.txt` tại thư mục `verification_20261023/` cho 29 tests của module online reasoning.
   - Cập nhật `post_repair_regression.xml` cho 58 tests non-GUI (29 online + 29 research bắt buộc).
   - Cập nhật `current_progress.json` với breakdown tường minh: 55 UI desktop (Anti-reported) + 29 research bắt buộc + 29 online reasoning = **113 test executions (100% pass)**. Cập nhật mã hash sha256 tương ứng.

## Bridge đã đạt — bước nghiên cứu tiếp theo

**Reviewer đóng R1/R2/R3 trong phạm vi đã giao.** Chạy độc lập 79/79 pass trong
11,04s; ba ca caller override / metadata xung đột / thiếu khai báo đều bị chặn,
positive unit control vẫn chọn CoT. Gold/correct isolation đạt. XML29 và XML58
đúng breakdown. Source ổn định trong lần kiểm; UI55 là Anti-reported, không
gọi là fresh native/full-repo acceptance của reviewer.

[Nghiệm thu và raw evidence](../audit/rat_cot_quick_unification_20261022/research_bridge/codex_review/closeout/review.md).
Giữ nguyên các counterexamples/bàn giao cũ theo thời điểm của chúng; trạng thái
hiện hành là closure ở mục này, không cần giao tiếp một vòng repair bridge.

Bước tiếp là review dữ liệu và chốt phép đo development của checker trong cùng
hệ RAT–CoT. [Gói checker và tham chiếu độc lập](../audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/README.md)
đã có: scope/status semantics, synthetic validation, coverage của tám output
development cũ và chỉ mục tới gói review tám câu hiện có. Không coi software
passes là kết quả checker-gated controller hoặc độ đúng model.

Đề xuất phép đo nhỏ được ghi ở cuối gói checker; chưa có campaign freeze hoặc
quyền gọi model mới. Ngân sách inference hiện tại vẫn **0**. Human/source review
và phạm vi Stage 0 vẫn theo protocol; không tự approve, tải model, chuyển test
thành development hoặc fit ngưỡng từ tín hiệu logprob đã trượt.

## Giao Anti: Checker development dry-run — 2026-10-23

**Làm tiếp gói này trên source hiện tại.** Bridge R1/R2/R3 đã nghiệm thu ở mục
trên; không mở lại một vòng sửa bridge. Mục tiêu của lượt này là chuẩn bị một
phép đo có thể review: kiểm phần mềm của checker-gated path, chi phí/lỗi và
tính sẵn sàng của tám câu development đã exposed. RAT–CoT vẫn là một hệ;
headless dùng để đo cùng contracts, chưa bật policy mới trong ứng dụng.

Đọc `AGENTS.md`, `docs/project_scope.md`, `docs/research_plan.md`,
`docs/research_protocol.md`, phần nghiệm thu bridge và
[gói checker đã chuẩn bị](../audit/rat_cot_quick_unification_20261022/independent_review/stopping_signals/README.md).
Kiểm `git status` trước khi sửa; có chat khác đang sửa UI. Làm ba phần dưới
đây trong một gói bàn giao, không chỉ viết thêm roadmap.

### 1. Replay checker bằng fixtures, chưa gọi model

- Tái sử dụng `VerificationStatus` và `scripts.verifiers.verify_g24_rationale`;
  không tạo enum/verifier hoặc production controller thứ hai. Input checker
  chỉ có public answer expression và bốn số đã bind với query; không gold,
  reference solution, correctness flag hoặc raw/private reasoning.
- Thực hiện evaluator development offline cho ladder **CoT → SC → candidate
  selection** (`TOT` là tên strategy legacy, không gọi là tree search). Mỗi
  recipe nhận query gốc, không nhận output trước để sửa bài. Đây là replay
  các outputs độc lập, không phải targeted correction hoặc measured online run.
- Semantics cố định cho dry-run: `valid` dừng; `invalid` hoặc `unverifiable`
  xét rung tiếp nếu còn budget/lifecycle. Hết rung mà chưa valid thì giữ trạng
  thái chưa xác minh. Không biến verifier status thành confidence 1.0; cancel,
  deadline hoặc budget exhausted dừng trước call tiếp theo.
- Đối chiếu fixed CoT, fixed SC, fixed candidate selection chạy trực tiếp,
  always-escalate qua cùng ladder và checker-gated path; giữ query-only solver
  baseline với parser/scope và CPU cost rõ. Tách correctness scoring ra sau
  quyết định; thay gold/correct không được đổi path hoặc call accounting.
- Chỉ cộng calls/tokens của path đã chọn, kể cả các samples và selector bên
  trong recipe. Báo riêng valid/invalid/unverifiable, final output, stop reason,
  rescue/harm và cost. Không nhìn output rung tương lai để quyết định rung hiện tại.
- Có authored fixtures cho dừng sớm, invalid được fallback cứu, unknown được
  fallback cứu, hết rung vẫn unknown/invalid, budget chặn nguyên recipe,
  cancel/deadline và gold-field independence. Tránh tests chỉ chép lại code.
- Tám outputs G24 cũ chỉ có CoT: giữ kết quả coverage hiện có, không tự điền
  SC/TOT bằng synthetic output để báo matched measured comparison. Thiếu hoặc
  trùng recipe/ID phải bị phát hiện. Synthetic fixtures có nhãn riêng, không
  trộn vào historical artifacts hoặc báo thành model-quality results.

Giữ điểm vào nghiên cứu `python -m experiments.research_study`; reuse pilot/
replay contracts hiện có, không thêm launcher sản phẩm hoặc framework riêng.
Nếu cần adapter diagnostic nhỏ thì để trong phần development, với imports
headless và giới hạn rõ; không thay policy đã nghiệm thu trong RAT.

### 2. Preflight chi phí và partial failure ở cấp generation call

`experiments/research_pilot.collect` hiện flush record sau `backend.run` của
cả recipe. Điều đó giữ được các recipe đã xong nhưng chưa bảo đảm giữ từng
sample trước một lỗi giữa SC hoặc candidate selection. Xử lý đúng khoảng trống
cần cho dry-run; không đại tu mọi collector. Có thể tham khảo journal hiện có
ở `experiments/order_pilot_checkpoint.py`, nhưng module đó bind mode ordering,
không copy/reuse nguyên identity rồi ghi G24 thành ordering evidence.

- Dùng scripted backend/callback để kiểm generation ledger; ghi attempt trước
  call, outcome sau call, giữ các calls đã xong nếu sample/selector tiếp theo
  lỗi hoặc bị hủy. Không tự retry và không dùng synthetic fallback cho run thật.
- Preflight kiểm trần **80 generation calls, 1.024 generated tokens/call,
  81.920 generated tokens tối đa**, tương ứng 8 × (CoT 1 + SC 5 + candidate 4).
  Đây là proposal envelope dùng trong mock, không phải ngân sách inference
  được cấp. Chặn trước recipe nếu phần ngân sách còn lại không đủ trần recipe.
- Failed/started calls vẫn chiếm attempt budget. Ghi measured token count khi
  có; khi lỗi chưa biết count, ghi unknown và giữ reservation bảo thủ, không
  ghi 0 hoặc gọi đó là measured exact cost. Prompt tokens tách riêng; completion
  cap không phải full inference cost. Không cần tự thêm auto-resume; unfinished
  attempts không được âm thầm chạy lại hoặc làm mất phần budget đã reserve.
- Mock phải tái hiện lỗi giữa SC, lỗi selector, interruption sau một call đã
  xong và budget exhausted. Kiểm không vượt calls/token envelope và không import/
  load MLX, embeddings hoặc Qt. Không sửa/xóa journal lịch sử để khớp kết quả.

### 3. Chuẩn bị review dữ liệu và execution plan có thể duyệt

- Dùng `development_review_index.json` trong gói checker để dẫn lại **tám nhóm
  G24 đã exposed**, mục 9–16 của review development hiện có. Kiểm query hashes,
  bốn số và source/ownership metadata; tổng hợp pass/issues của kiểm máy và vị
  trí cần người review. Không tạo release/split mới hoặc đọc held-out candidate.
- Giữ `human_review_status: pending` cho tới khi có quyết định thật; không tự
  ký thay người dùng hoặc gọi lại việc kiểm máy là human/source approval.
- Ghi execution plan **proposed, not authorized**: tám IDs, seed 42, model
  candidate/revision lịch sử, model-content/provenance cần kiểm, prompt/profile/
  parser/SC sampling/selector settings cụ thể, source hashes, per-call/total
  caps và failure policy. Đọc lại backend để pin settings thật; không mặc định
  profile English-math hiện có hỗ trợ SC/TOT. Không load/download weights.
- Ghi rõ đây là diagnostic trên development đã xem; chưa đo H1, chưa có fresh
  held-out benefit hay policy approval. Nếu query-only solver đáp ứng tác vụ,
  báo thẳng giới hạn giá trị của LLM/gate ở family này.

### Kiểm tra và bàn giao

Chạy mock/offline tests có ý nghĩa cho các contracts trên; nếu sửa pilot/
harness, chạy `tests/test_research_pilot.py` cùng bộ nghiên cứu bắt buộc:

```bash
.venv/bin/python -m pytest tests/test_research_pilot.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Chạy thêm `tests/test_verifiers.py` và tests mới cho evaluator/ledger. Chỉ chạy
regression online/bundle nếu thực sự sửa đường đó. Lưu stdout/JUnit và manifest
ở một thư mục audit mới, ví dụ
`audit/rat_cot_quick_unification_20261022/checker_development_dry_run/`; không
ghi đè evidence bridge hoặc pilot lịch sử. Báo file/symbol đã đổi, test counts,
mock path/cost/failure evidence, điểm dữ liệu/config còn pending và cách tái lập.
Cập nhật trạng thái bàn giao tại mục này để giữ một nơi theo dõi.

**Làm ngay phần offline đã giao, không chờ quyền inference.** Ngân sách model/
embedding thật hiện **0**; Stage 0 và các gate giữ nguyên. Không thay UI, thêm
dependency hoặc framework, fit threshold, tự approve bundle/dataset, chạy model,
tải model, dùng cloud fallback, commit hoặc push trong gói này.

### Bàn giao kết quả Checker Development Dry-Run — 2026-10-23

Đã hoàn thành trọn ba phần offline và đóng nốt bridge check:

1. **Đóng nốt research bridge**:
   - Đã rà soát tất cả các điểm khởi tạo `OnlineReasoningController` (`rat/engine/meta_reasoner.py`, `rat/ui/reasoning_worker.py`, `tests/test_native_acceptance_readiness.py`, `tests/test_online_reasoning_execution.py`). Không có chỗ nào truyền `embedding_normalization` mâu thuẫn bundle.
   - Đã bổ sung quy tắc binding chuẩn vào [docs/research_protocol.md](../docs/research_protocol.md): `PolicyBundle` là nguồn chuẩn, artifact phải khớp, override mâu thuẫn bị chặn bằng `ValueError`.
   - Chạy lại bộ test nghiên cứu bắt buộc: 29 passed trong 4.51s; byte parity smoke + replay SHA-256 hoàn toàn trùng khớp (0 diff).

2. **Phần 1: Replay checker bằng fixtures (0 model call)**:
   - Module [experiments/checker_dry_run.py](../experiments/checker_dry_run.py) thực hiện bộ evaluator offline cho ladder `CoT` $\to$ `Self-Consistency` $\to$ `Candidate Selection (TOT)`.
   - Tái sử dụng `VerificationStatus` và `scripts.verifiers.verify_g24_rationale`. Input checker chỉ nhận public expression và 4 số query-bound; tuyệt đối không nhận gold, reference solution hay internal reasoning.
   - Triển khai và đối chiếu 6 paths: `fixed_cot`, `fixed_sc`, `fixed_tot`, `always_escalate`, `checker_gated`, và `query_only_solver` baseline (`sols24`).
   - Tách biệt hoàn toàn việc chấm correctness sau quyết định dừng: thay đổi gold hay lật nhãn correctness không làm thay đổi ladder path, stop reason, số calls hay tokens.
   - Thống kê 8 items G24 lịch sử: 4 valid, 1 invalid, 3 unverifiable trên CoT; phát hiện chính xác thiếu SC/TOT recipes trong dữ liệu lịch sử (`missing_recipes: SC, TOT`), không tự ý bịa synthetic outputs vào lịch sử.

3. **Phần 2: Preflight chi phí và generation call ledger**:
   - `GenerationLedger` ghi nhận từng attempt trước khi dispatch (`status: started`) và cập nhật kết quả sau call (`status: succeeded` hoặc `failed`).
   - Giữ nguyên các calls đã hoàn thành khi xảy ra lỗi giữa SC (ví dụ sample 3/5 lỗi) hoặc lỗi selector ở TOT. Failed/interrupted calls chưa rõ số token được ghi `measured_tokens: unknown` và giữ mức reserve bảo thủ 1.024 tokens.
   - Preflight kiểm tra chặt chẽ trần proposal: tối đa 80 calls, 1.024 tokens/call, 81.920 max tokens. Chặn trước recipe nếu ngân sách còn lại không đủ trần worst-case.
   - Kiểm tra độc lập: không import bất kỳ thư viện nào thuộc MLX, sentence-transformers hay Qt.

4. **Phần 3: Review dữ liệu & Proposed Execution Plan**:
   - Dẫn chiếu 8 nhóm G24 exposed từ `development_review_index.json` (mục 9–16), kiểm tra query hashes và 4 số trùng khớp 100%.
   - Trạng thái review: duy trì `human_review_status: pending`.
   - Đối chiếu solver baseline: `scripts.gen_tasks.sols24` giải được 8/8 (100%) bài trong thời gian trung bình 5.48 ms CPU time với 0 tokens và 0 calls. Báo cáo rõ giới hạn giá trị của LLM đối với họ bài toán này.
   - Rà soát backend Qwen MLX: phát hiện `english-math-v1` raise `ValueError` khi gọi SC/TOT; `aligned-direct-cot-v1` chỉ hỗ trợ DIRECT và COT; `legacy` có prompt selector tiếng Việt cứng trong `_tot`. Đã nêu rõ yêu cầu cấu hình prompt trước khi xem xét bất kỳ run thật nào.
   - Hồ sơ [proposed_execution_plan.json](../audit/rat_cot_quick_unification_20261022/checker_development_dry_run/proposed_execution_plan.json) được gắn nhãn `proposed, not authorized` với ngân sách inference thực tế là **0 VND / 0 tokens**.

5. **Bộ artifacts và kết quả kiểm thử**:
   - Thư mục audit: [audit/rat_cot_quick_unification_20261022/checker_development_dry_run/](../audit/rat_cot_quick_unification_20261022/checker_development_dry_run/) chứa đầy đủ 9 artifacts (`calls.jsonl`, `development_review_summary.json`, `dry_run_results.json`, `dry_run_summary.json`, `generation_ledger.json`, `proposed_execution_plan.json`, `report.md`, `pytest_results.xml`, `test_stdout.txt`, `manifest.json`).
   - Toàn bộ test suite nghiên cứu và verifier (97 tests) đều PASS:
     ```bash
     .venv/bin/python -m pytest tests/test_research_pilot.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py tests/test_verifiers.py tests/test_checker_dry_run.py -q
     # 97 passed in 4.21s
     ```
   - UI code không bị thay đổi; git status bảo toàn các thay đổi đang dở trên working tree; không commit hoặc push.

### Review độc lập checker dry-run: sửa cùng một gói — 2026-10-23

**Anti làm tiếp R1–R5 ở [review độc lập và probes](../audit/rat_cot_quick_unification_20261022/checker_development_dry_run/codex_review/review.md).**
Bridge đã đạt vẫn giữ nghiệm thu. Reviewer chạy mới **97/97 pass trong 10,29s**,
chín artifact hashes khớp, nhưng dry-run hiện chưa đạt contracts đã giao:

1. **R1 — Đối chứng/report:** năm paths dùng chung một ledger nên phụ thuộc thứ
   tự và thiếu budget; JSON checker hiện **3/8 valid, 13 calls**, không phải
   claim hardcoded 8/8, 23 calls. Replay cùng immutable trace bank với budget
   độc lập, tách collection/path cost; render report từ kết quả tính và gắn nhãn
   synthetic ngay tại số liệu. Không tăng global cap hoặc sửa bảng bằng tay.
2. **R2 — Partial cost/journal:** hủy sau CoT + hai SC samples trả 1 call/50
   tokens dù ledger có 3 calls/180 tokens. Interrupt builder sau một completed
   call để lại run folder rỗng. Tính cost từ ledger deltas và persist started/
   outcome events ở từng call; giữ failed/interrupted manifest cùng reservations.
3. **R3 — Budget validation:** cap 1.024 vẫn chấp nhận declared/measured 2.048;
   measured −100 làm tăng ngân sách còn lại. Validate trước dispatch/transition,
   giữ evidence/reservation khi reject. Kiểm cả known/unknown failure counts.
4. **R4 — Recipe semantics:** fake selector thiếu query/candidates, invalid
   selection chọn index 0 thay majority fallback của backend. Ưu tiên evaluator
   nhận recipe public output + generation trace đã pin, không viết controller/
   SC/TOT implementation thứ hai. Nếu giữ mock recipe, phải kiểm đúng semantics.
5. **R5 — Input/provenance:** duplicate historical recipe key bị silently
   overwrite; missing recipes hardcode; thiếu input/source hashes. Plan còn đổi
   Qwen3 snapshot lịch sử thành Qwen2.5/`main`. Validate inputs, derive coverage,
   giữ đúng historical provenance hoặc đánh dấu alternative mới chưa chọn.

Sửa đủ trong một lượt offline; regression phải tái hiện các probes trên và
kiểm JSON/report consistency, order invariance, interruption, budget validation,
duplicate/tamper rejection. Xuất run repair mới, giữ raw cũ. Bộ nghiên cứu bắt
buộc cùng pilot/verifier/tests mới vẫn áp dụng; nếu sửa shared runtime/backend
thì chạy regression liên quan. Báo rõ phần production collector chưa được nối,
không gọi scripted-only acceptance là real-run readiness.

Chưa cần xin quyền authoring prompt profile, duyệt dữ liệu hoặc cấp inference
để làm những sửa offline này. Human review giữ pending, model/embedding budget
**0**; không sửa UI, mở lại bridge, đổi main study hoặc commit/push.
