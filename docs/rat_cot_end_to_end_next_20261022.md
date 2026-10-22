# Bàn giao cho Anti: hợp nhất RAT–CoT trên UI Quick hiện tại

Cập nhật 2026-10-22, Asia/Saigon. **Đây là nhiệm vụ triển khai đang có hiệu lực.**
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
3. Nếu có lợi, mở rộng lần lượt; giữ UI và research runner ổn định. Tập trung
   nguồn lực nghiên cứu vào dữ liệu được review, so sánh hợp lệ và bằng chứng
   cho routing/stopping. Việc core RAT triển khai các contract này vẫn tiếp tục.

**Kết luận spike:** SDK cắm được vào contract hiện tại nhưng wrapper này chưa
thay thế dòng production nào. `Tool.from_schema` của phiên bản thử bỏ qua
schema validation mặc định; validator RAT vẫn chịu trách nhiệm. Các ca hủy
chỉ kiểm biên thực thi/commit, chưa kiểm ngắt inference. Chưa đủ bằng chứng
để thay runtime hoặc thêm SDK vào requirements chính. MCP chưa được thử.

Nguồn probe: `scripts/dev/rat_agent_sdk_spike.py`. Raw results, dependency lock,
source hashes và giới hạn được ghi trong
`audit/rat_cot_quick_unification_20261022/independent_review/sdk_spike/README.md`.
Dependencies chỉ ở thư mục tạm; UI/runtime/harness không được sửa trong spike.
Ngân sách model thật vẫn 0 và Stage 0/data-review gate không đổi.
