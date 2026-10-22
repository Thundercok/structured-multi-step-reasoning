# Handoff triển khai lát cắt RAT–CoT nhiều lượt

Ngày 2026-10-22. Đây là quyết định/spec sau review hai handoff, **chưa phải báo cáo đã triển khai**. Bám `docs/project_scope.md`, `docs/rat_cot_end_to_end_next_20261022.md` và kịch bản DSA đã chọn. RAT triển khai phương pháp; headless pipeline đo bằng chứng của cùng hệ.

## Phạm vi cụ thể

1. Sửa dứt R5: live calibration state phải khớp authoritative artifact hoặc bị từ chối. Dùng probe finite-mutation và uncalibrated positive control ở thư mục review này; không đóng finding chỉ bằng kiểm NaN.
2. Nối context snapshot qua `ExecutionRequest` → factory/worker → controller/backend, dùng đường thực thi hiện có. Snapshot lấy từ conversation/task/artifact sources, có turn/revision nguồn, không đọc lại widget gần nhất để đoán state. Giữ query người dùng để hiển thị. Snapshot phải độc lập với mutation xảy ra sau submit; ghi schema/prompt-adapter version để tái hiện.
3. Gắn composition host bằng factory và model owner hiện có. Development có thể inject synthetic engine với nhãn rõ, không ngầm bật. Khi muốn reasoning mà policy không hợp lệ/chưa có, trả trạng thái unavailable trung thực; không gắn nhãn online_policy cho fallback khác. Production chưa được kích hoạt trong review này.
4. Mở rộng test composer/worker có sẵn thành chuỗi nhiều lượt và các nhánh lỗi bên dưới. Context adapter phải dùng được ngoài DSA; không tạo tutor screen, algorithm renderer, keyword router hay controller thứ hai.

Không cần chờ ngân sách model để làm và kiểm 4 bước phần mềm này. Native model acceptance là giai đoạn sau, phụ thuộc gate và quota. Không tự đổi singleton/default model, chạy model hoặc bỏ Stage 0.

## Lượt mới và revision mới cùng tồn tại

Bước “đổi sang tìm 6” tạo một lượt mới với `target_turn_id` trỏ lượt nguồn chứa artifact tìm 8 và `target_artifact_id` đúng. `target_revision` là revision nguồn đã đọc. Store commit tạo revision kế tiếp sau khi kiểm tra source revision và conversation generation. Revision không lấy từ số thứ tự lượt chat.

Ví dụ minh họa: turn-2 giữ artifact A@v1 tìm 8; turn-4 tham chiếu A@v1 với `target_revision=1`, tạo A@v2 tìm 6 khi commit thành công. Snapshot turn-2 vẫn chỉ A@v1. Nếu artifact hiện tại đã đổi khỏi source revision, trả stale/conflict hoặc dùng quy trình chọn lại target có sẵn; không sửa lịch sử để lách optimistic locking. Không báo revision mới đã commit khi execution bị hủy hoặc thất bại.

Cơ sở source: `rat/ui/chat_session.py` (begin_turn/snapshots), `rat/engine/work_notes.py` (TurnRef), `rat/kernel/dispatcher.py:165,186`, `rat/kernel/contracts.py:173–183`. Tái sử dụng lifecycle/revision store hiện có; không thêm DSA state store song song.

## Ma trận chấp nhận trên cùng luồng app

| Bước | Tương tác | Quan sát bắt buộc bằng fixture / app flow |
| --- | --- | --- |
| 1 | Giải thích binary search bằng ví dụ, chưa đưa code | Composer tới đúng composed engine; snapshot giữ yêu cầu, mode/provenance rõ; response đúng conversation/turn/execution/generation. Fixture có thể trả authored answer để kiểm presentation; không tuyên bố model tuân thủ. |
| 2 | Mảng [2,4,6,8,10], tìm 8 | Backend input nhận chủ đề và dữ kiện nguồn. Task/artifact evidence có source IDs/revision; UI vẫn hiển thị câu người dùng. |
| 3 | “Sao phải dùng mid + 1?” | Backend input chứa dữ kiện target 8 và lượt/artifact được tham chiếu; không bắt người dùng nhập lại. Kiểm transport thực tế, không chỉ kiểm request có trường context. |
| 4 | “Đổi sang tìm 6” | Lượt mới, source ref đúng, output revision mới sau commit; turn/snapshot cũ và target 8 giữ nguyên. Request dùng source revision, output có committed revision riêng. Kiểm cả stale source và revision khác v1. |
| 5 | Mở lại lượt giải thích mid+1 | Điều hướng tới đúng snapshot lịch sử; giữ draft/công việc hiện tại; explicit navigation không dispatch thêm. Câu hỏi mới về lượt cũ dùng context adapter chung khi cần model. |
| 6 | Hủy rồi hỏi tiếp | Hủy đúng execution, callback muộn không cập nhật lượt mới; giữ kết quả đã commit/draft theo lifecycle; execution mới có ID/generation riêng. Cost của execution cũ không biến mất. |
| 7a | Quota cứng bằng 0 | Không embed/generate nếu contract cấm mọi model work; 0 dispatched/0 generated tokens; budget_exceeded, public verification UNKNOWN. Tách rõ từng cap=0 với unset=None. |
| 7b | Thiếu/không đọc được context bắt buộc hoặc failure trước dispatch | unresolved/failed theo contract hiện có; không tự trả lời bằng prompt thiếu dữ kiện; 0 dispatched/0 tokens nếu thực sự chưa có model work. Context tùy chọn vắng mặt không được làm hỏng standalone query. |
| 7c | Exception sau khi dispatch | failed/unresolved theo lớp kết quả; giữ actual dispatched, failed/succeeded và partial generated tokens. Không suy chi phí từ chuỗi exception hoặc ép về 0. |
| 7d | Hủy/deadline khi đang chạy | cancelled/timeout đúng execution; giữ chi phí thực tế và chặn stale callback; không báo completed hoặc verified giả. |

Các trạng thái cancellation ở signal/event có thể có tên khác status trong result (`cancel` so với `cancelled`); kiểm đúng mapping hiện có, không đòi cùng literal trên mọi lớp. Tương tự internal verification `unverified` phải map đúng public `UNKNOWN` khi không có checker phù hợp.

## Evidence cần trả lại khi triển khai

- Source snapshot/diff đủ để review; chỉ sửa phạm vi đã mô tả và giữ uncommitted work khác.
- Test đi từ composer thật qua request/factory/worker/controller đến consumer/history; synthetic backend ghi observed input và controls. Dùng assertions về facts/refs/identity, tránh buộc một exact prompt string.
- Với mỗi execution: display query, context snapshot/schema/hash và source refs, execution/turn/generation, bundle/backend/prompt/adapter identity, strategy path/status, actual cost ledger, public verification scope và committed output revision nếu có. Không xuất raw/private reasoning.
- Raw stdout/JUnit và artifact manifest mới riêng; version fixture khi seam thay đổi. Không chạy runner cũ ghi đè audit lịch sử. Thời gian pytest là thời gian kiểm tra phần mềm; token fixture là synthetic, prompt/full inference cost chưa đo thì ghi chưa đo.
- Sau khi sửa harness/threshold fitting, chạy suite bắt buộc theo AGENTS: `python -m pytest tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q`. Với thay đổi này, thêm các execution/composer/context/revision/cancel cases phù hợp; không lặp toàn repo nếu không có thay đổi/rủi ro mới.

Điều kiện hoàn tất lát cắt phần mềm: R5 được sửa hoặc calibrated mode chưa hỗ trợ bị từ chối rõ; context thực sự tới backend; host dev có cách cấu hình được kiểm; chuỗi trên giữ refs/lifecycle/cost và UI trung thực. Chưa dùng software acceptance để tuyên bố chất lượng DSA, cải thiện accuracy/latency/cost hoặc tương đương model behavior với harness. Nếu adapter làm prompt/context khác harness, ghi rõ phần khác và giới hạn so sánh. Ngân sách model thật vẫn 0.
