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

## Hiện trạng cần hợp nhất

Các alias `~/github/nesy-docai`, `~/github/multi-step-structured-reasoning` và
checkout `/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`
đã được kiểm tra, đều trỏ cùng thư mục thật. Khác nhau hiện nằm ở đường chạy:

| Entry point hiện tại | Surface | Thực thi |
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

1. **Dùng UI Quick hiện có làm bề mặt tích hợp.** Giữ thiết kế Chuột/chatbar,
   Simple/!/loading, theme, vị trí/độ trong suốt cửa sổ, draft, selection và các
   sửa PDF. Mở rộng adapter của surface này để nhận public execution/result
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
