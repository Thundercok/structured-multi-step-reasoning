# RAT Lite — kế hoạch mở rộng sau .26

Update after planning: the user authorized implementation of all 20 items, including
optional scope. See [the .27 source handoff](rat_lite_27_source_handoff_20261029.md)
for implementation and remaining live evidence. Proposal-only wording below records
the earlier planning state; main/M3 and research gates still apply.


Ngày 2026-10-29. Người dùng báo “okay it worked”, đồng ý mục đặt Quick Look gần
vùng chữ được chọn, rồi yêu cầu thêm nhiều hạng mục phát triển Mini/Lite.
Định hướng đặt gần vùng chọn đã được đồng ý; các mục mở rộng dưới đây là đề xuất
để review thành từng đợt. Đây là lượt lập kế hoạch, không triển khai hay chạy test.

Phản hồi tích cực xác nhận lượt người dùng vừa thử hoạt động; chưa có danh sách
nghiệm thu chi tiết để suy ra mọi app nguồn, mọi thao tác hay vòng model đã đạt.
Giữ .26 làm mốc đối chiếu. Bằng chứng lỗi/quan sát trước đó vẫn giữ nguyên.

## Trải nghiệm đích

`Bôi đen → gọi Lite → phản hồi cạnh nguồn → đọc/copy/hỏi tiếp → mở rộng khi cần`.

Một đầu Chuột nhỏ, một panel, một task hiện tại và một draft độc lập. Không quay
lại chọn mode, đổi mascot theo độ dài hoặc thay cả UI khi đọc kết quả. Những
mục đã có nền trong .26 được cải thiện đúng phần thiếu, không xây executor khác.
Không thêm animation để che việc di chuyển hoặc mất focus.

## 20 hạng mục

### 1. Quick Look cạnh selection — trọng tâm đã đồng ý

Capture lấy chữ và geometry tùy chọn từ cùng phần tử AX, cùng PID, cùng lần gọi.
Geometry gắn với snapshot/ref của nguồn và chỉ dùng làm presentation context.
Ưu tiên đặt bubble ngoài vùng chữ, trên cùng màn hình; tránh che selection nếu
còn chỗ đọc. Không lấy frame cả document/ô nhập làm frame chính xác của selection.
Không có geometry hợp lệ thì dùng góc đã nhớ. Lỗi geometry không làm mất chữ đã
capture hoặc chặn bản dịch. Không theo dõi selection nền.

Hoàn thành khi: vị trí lấy từ geometry quan sát thật, hoặc fallback rõ ràng; không
tuyên bố hỗ trợ app nào trước khi có quan sát thật trên app đó.

### 2. Neo ổn định suốt một lần gọi

Chọn anchor một lần lúc nhận nguồn; giữ qua processing/result/error. Kết quả dài
cuộn hoặc người dùng mở rộng. Drag điều chỉnh vị trí hiện tại; source mới chỉ
đổi anchor ở lần gọi chủ động tiếp theo. Thu gọn quay về anchor của task đó.

Hoàn thành khi: kết quả đến muộn, copy mới, thay provider hoặc đổi trạng thái
không tự kéo panel sang chỗ khác.

### 3. Nhiều màn hình và không gian đọc hẹp

Chọn màn hình chứa selection; đổi hệ tọa độ AX sang Qt một lần tại adapter.
Xét display origin âm, scale khác nhau và mép work area. Rewrap trước khi đổi
phía; không thu font dưới mức đã chốt chỉ để nhét nội dung. Màn hình nguồn mất
thì clamp sang work area hợp lệ. Không yêu cầu theo dõi Space/màn hình nền.

Hoàn thành khi: có policy thuần geometry dùng lại được; native multi-display
vẫn cần quan sát riêng, không suy ra từ bài toán tọa độ.

### 4. Phím tắt có cấu hình, trạng thái nhất quán

Cho đổi chord trong Settings; menu/hint/helper dùng chung giá trị đã xác nhận.
Đổi đăng ký theo một giao dịch: đóng owner cũ, đăng ký chord mới; nếu thất bại
thì giải thích và cố khôi phục chord cũ một lần, báo đúng trạng thái cuối. Giữ
một owner; không lưu cấu hình mới như đã chạy khi helper chưa nhận nó. Không
khôi phục tap/hold hoặc đưa thêm thời gian nhấn vào thao tác thông thường.

Hoàn thành khi: cấu hình, protocol và runtime khớp nhau; trường hợp xung đột
không để UI báo sẵn sàng giả. Không đổi chord hiện tại trong lượt lập kế hoạch.

### 5. Điều khiển bằng bàn phím liền mạch

Esc đóng menu/view trước rồi mới ẩn panel; Tab có thứ tự focus rõ. Enter gửi ở
composer, Shift+Enter xuống dòng, Enter trong danh sách file mở hit đang chọn.
⌘C ưu tiên selection đang đọc; chỉ copy toàn bộ khi người dùng chọn hành động
đó. Không giành focus khi tool hoàn tất hoặc khi nhận pending Clipboard.

Hoàn thành khi: hành động phụ thuộc focus thực, không dựa vào một mode ẩn; thao
tác copy không làm thay nguồn của request đang chạy.

### 6. Ghim để đọc cạnh app nguồn — đề xuất

Một toggle ghim trong More cho task hiện tại: giữ panel khi click app khác nhưng
không lấy keyboard focus. Mặc định vẫn là transient; Esc/Close luôn dùng được.
Ghim không bật Clipboard watcher, không tạo cửa sổ thứ hai, không tự lưu qua
khởi động. Đây là thay đổi tùy chọn đối với outside-click, chưa phải hành vi đã duyệt.

Hoàn thành khi: người dùng biết panel đang ghim và bỏ ghim được; background
completion vẫn không được mở một panel đã đóng.

### 7. Reader dài và copy chính xác

Hoàn thiện reader hiện có: thấy được dòng cuối, thanh cuộn khi overflow, giữ
selection/anchor khi mở rộng và quay lại. Copy phần chọn/toàn bộ có nhãn tách
bạch, copy đúng nội dung đang hiển thị. Hiển thị ngắn gọn trạng thái partial,
bản dịch trước khi sửa OCR hoặc nguồn hết hạn; không làm footer tràn panel.

Hoàn thành khi: bản dài đọc/copy đủ; chọn chữ, scroll và extent không mất draft.

### 8. Đối chiếu nguồn–kết quả nhẹ hơn

Tái sử dụng source view hiện tại: mở nguồn theo nhu cầu, side-by-side khi đủ
rộng, stacked/reversible khi hẹp. Hiện nguồn selection/Clipboard/OCR và app
nguồn nếu có thông tin đáng tin cậy. Chi tiết hash/ref/verification nằm ở More,
không biến màn hình đọc chính thành trang debug.

Hoàn thành khi: người dùng phân biệt được chữ gốc và kết quả, mọi thao tác
quay lại đúng task/revision. Nhãn app không suy ra đường dẫn tài liệu.

### 9. Điều chỉnh bản dịch trên cùng nguồn

Cho đổi ngôn ngữ đích và yêu cầu cách diễn đạt từ source_ref đang giữ; dùng lại
router/translation tool hiện có, không OCR/capture lại nếu nguồn còn hợp lệ.
Provider chỉ nhận tùy chọn nó hỗ trợ. Yêu cầu văn phong không được hiện như đã
thực hiện nếu backend xác định không hỗ trợ; Agent tùy chọn phải được nói rõ.

Hoàn thành khi: đổi ngôn ngữ/retry giữ đúng nguồn; đầu ra có backend/provenance
thật, không tuyên bố chất lượng hay văn phong chỉ từ việc đổi nhãn UI.

### 10. Sửa OCR ít bước hơn

Từ ảnh nguồn mở editor sẵn có, sửa → preview draft → dịch lại bằng correction
artifact. Giữ bản đầu và chuỗi parent/root/hash; retry dịch không chạy OCR lại.
Nguồn đã sửa phải được phân biệt với kết quả cũ. Chọn ảnh/region vẫn là ingress
chủ động, không dựng lại screen watcher hay hotkey screenshot đã hoãn.

Hoàn thành khi: lỗi mạng không mất chữ sửa; correction và bản dịch pin cùng revision.

### 11. Hỏi tiếp dựa trên nguồn đã nhận — mở rộng Agent được đề xuất

Composer có thể gửi “giải thích câu này”, “ý đoạn cuối là gì” với nguồn/ref rõ.
Session chọn tool hoặc yêu cầu model qua service chung; thiếu referent thì hỏi
một câu. Đầu ra phải phân biệt nội dung lấy từ nguồn với kiến thức/suy luận thêm.
Không giả lập hội thoại thông minh khi model đang tắt hoặc chưa cấu hình.

Hoàn thành khi: có trace nguồn → route/plan → observation → kiểm chứng phù hợp
→ public answer; đăng ký tool hoặc giữ chat text không đủ để gọi Agent đã nối.

### 12. Tóm tắt, thuật ngữ và giải thích — nhóm capability mới được đề xuất

Tách các operation có hợp đồng rõ cho summarize/explain/term-in-context nếu
được duyệt. Cùng registry, dispatcher, budget và source pin; không gọi LLM trong
QML. Một từ được giải thích trong ngữ cảnh đã cung cấp; không quảng cáo như từ
điển đã xác thực. Mỗi backend nói đúng khả năng của nó. Local LLM vẫn hoãn.

Hoàn thành khi: kiểm chứng cấu trúc/source grounding và giới hạn ngữ nghĩa được
nêu riêng; default LLM opt-in không bị bật ngầm để làm menu có vẻ hoạt động.

### 13. Yêu cầu nhiều bước trong một task — core Agent được đề xuất

Ví dụ “dịch rồi tóm tắt ba ý” chỉ chạy khi profile/backend thực sự hỗ trợ cả hai.
Plan có operation/args, budget, cancellation và điều kiện dừng; UI chỉ hiện tiến
độ công khai/kết quả quan sát được. Trả partial khi một bước thất bại; không
đổi thành pass vì bước đầu đã có artifact. Không lộ raw/private reasoning.

Hoàn thành khi: một run model thật có tool observations, verification, status và
chi phí được ghi đúng loại; không dùng acceptance này để thông qua Stage0.

### 14. Chuyển task có kiểm soát và khay phiên gần đây

Đề xuất một khay nhỏ, giới hạn khoảng5 task trong bộ nhớ để mở lại kết quả;
current result, next draft, pending input là ba thứ riêng. Đang busy thì người
dùng chọn dừng/chờ/giữ draft, không âm thầm xếp hàng execution. Ref hết hạn
không được giả hồi sinh từ nhãn lịch sử. Không tự lưu văn bản cá nhân ra đĩa.

Hoàn thành khi: recall là đọc lại, không phát sinh tool call; task switch không
mang selection/approval của task cũ sang task mới.

### 15. Finder nằm trong luồng chung

Cải thiện projection hiện có: số hit thật, coverage partial/timeout, chọn hit
bằng keyboard rồi open/reveal qua dispatcher. Cho hỏi tiếp về tên file đang
chọn khi được hỗ trợ; không tự đọc nội dung mọi hit, không thêm vector DB hay
personal-file indexing để làm UI có vẻ thông minh hơn.

Hoàn thành khi: mở đúng hit/ref được chọn; timeout không bị trình bày thành no-hit.

### 16. Folder Organizer dễ review và phục hồi

Giữ khả năng đã duyệt, cải thiện preview theo nhóm và chi tiết xung đột; Apply
và Undo vẫn là gesture riêng gắn đúng artifact/revision. Compact mở full plan
hoặc receipt, không giấu Apply trong một câu trả lời Agent. Nhật ký hiện có là
nguồn phục hồi; không sửa engine chuyển file trong UI.

Hoàn thành khi: preview không thay file; dừng/partial có receipt thật và đường
phục hồi; kiểm tra chỉ dùng bản sao được người dùng chọn khi có yêu cầu rõ.

### 17. Readiness và Settings theo ngữ cảnh

Phân biệt phím tắt, Accessibility, dịch offline, provider/quota và folder scope.
Mở đúng recovery cho operation vừa lỗi; cấp một quyền không được coi là cấp mọi
quyền. Kiểm tra sâu/hash chỉ khi người dùng bấm. Settings không làm mất nguồn,
draft hoặc task; cấu hình UI/runtime phải đọc cùng hợp đồng.

Hoàn thành khi: bộ phận thiếu không chặn toàn app; sửa cấu hình không tự gửi lại nguồn.

### 18. Lỗi có giải thích và thông tin hỗ trợ gọn

Phát triển journal hiện có thành phần trạng thái đọc được trong More: build,
helper lifecycle, key receipt, capture, dispatch, presentation; reason code có
cách khắc phục. Export báo cáo chỉ khi bấm, mặc định không chứa nguồn/Clipboard/
ảnh/tọa độ. Nếu cần dữ liệu nhạy cảm, cho xem nội dung export trước.

Hoàn thành khi: startup/registered không bị viết thành thành công của luồng;
report failure không phá tool result; không dùng thông báo dày đặc cho mọi bước.

### 19. Handoff và phân phối nhất quán

Tên/BUILD ở menu, bundle, helper và note khớp nhau. Một gói có một build identity;
giữ gói cũ làm recovery. Chỉ thay phiên đang chạy khi build/open được yêu cầu.
Tiếp tục dùng commit nhỏ và diff theo đợt. Việc rename bundle/notarization nếu
muốn làm phải thành hạng mục riêng, không đổi identity ký giữa chừng âm thầm.

Hoàn thành khi: mở đúng binary, phân biệt packaging/startup/user acceptance.
Không mở rộng sang tối ưu RAM/dung lượng đã hoãn.

### 20. Tái sử dụng trong RAT chính theo gate

Tách profile UI/anchor khỏi contracts, providers, dispatcher và execution. Viết
reuse map từ Lite sang main cho input/source lifecycle, keyboard/focus và result
projection. Main composition chỉ làm khi Lite + recipient M3 được chấp nhận và
có yêu cầu tích hợp. Không tự bật Organizer/model trong main chỉ vì source đã chung.

Hoàn thành khi: có bảng phần dùng chung/adapter riêng/chưa nối, cùng bằng chứng
thực; không coi UI integration là chất lượng nghiên cứu hay model equivalence.

## Thứ tự và phạm vi từng đợt

| Đợt | Phạm vi dự kiến | Điều kiện để đi tiếp |
| --- | --- | --- |
| .27 — Quick Look theo vị trí |1–5 và phần tối thiểu17–18 cho lỗi/fallback;6 là tùy chọn sau review| Giữ phần đang chạy được; user review geometry/focus và một luồng thật khi yêu cầu. |
| .28 — làm việc với nguồn/task |7–10,14–16 và phần còn lại17–18| Mỗi mục chỉ bổ sung khoảng trống của code hiện có; không đổi toàn bộ panel. |
| .29 — Agent theo nguồn |11–13 nếu được duyệt mở rộng capability/profile| Model opt-in cấu hình thật; kiểm chứng source/tool, budget và completion status riêng. |
| Xuyên suốt / sau gate |19–20| Phân phối đúng build; main/M3 và Stage0 vẫn là các gate độc lập. |

Đây là thứ tự đề xuất, không cam kết nhồi mọi mục vào một build. Hạng mục gây
regression ở phần đang dùng được được ưu tiên trước phần mới. Từng đợt hoàn
thiện source trước, chia commit theo concern và cho xem diff. “Mass” về khối
lượng một lượt không có nghĩa gom toàn bộ roadmap thành một cụm không review được.

## Chi tiết thiết kế mục đặt gần chữ

Source adapter hiện chỉ trả text; geometry chưa có. Phải mở rộng snapshot/capture
contract dùng chung và đường observation tới UI, không để QML tự đọc AX. Giữ
source PID/generation/ref liên kết; geometry lỗi hoặc stale không được đổi task.
Đọc range và bounds là optional capability của app nguồn. Không dùng bounds do
model tạo, tọa độ con trỏ hoặc frame cả cửa sổ để giả là exact selection.

Apple cung cấp [selected text range](https://developer.apple.com/documentation/applicationservices/kaxselectedtextrangeattribute?changes=l_1__1_8&language=objc)
và [bounds for range](https://developer.apple.com/documentation/applicationservices/kaxboundsforrangeparameterizedattribute).
Tài liệu bounds mô tả tọa độ màn hình theo pixel; adapter phải xác nhận scale/origin
và đổi sang Qt logical coordinates theo màn hình thực, không mặc định scale1.
App có thể không hỗ trợ thuộc tính hoặc trả không có giá trị; đó là fallback,
không phải lý do đọc lại toàn document hay mô phỏng Copy.

Geometry là context tạm cho presentation, không đi vào model args hoặc log mặc
định. Contract cần nói rõ phần nào chỉ ở bộ nhớ và phần nào có thể vào receipt
opt-in; không vô tình persist vị trí màn hình trong artifact history/export.

## Ranh giới triển khai và bằng chứng

Mục gần selection được người dùng đồng ý về hướng. Các mục mới, đặc biệt6,
11–14 và cấu hình chord, cần review phạm vi trước khi coi là capability đã duyệt.
Plan này không tự bật chúng. Không sửa source ứng dụng, build, mở app, chạy test,
UI acceptance hay chuỗi screenshot trong lượt lập kế hoạch này.

Khi người dùng yêu cầu kiểm tra, chọn một nhóm thay đổi và một luồng thật, giữ
prompt/public response/tool observation/lỗi và ảnh thật nếu được yêu cầu. Không
dùng fixture/canned answer. Trạng thái registry, UI projection và live Agent
loop phải được bàn giao riêng. Nghiên cứu, model-quality claims và Stage0 không đổi.
