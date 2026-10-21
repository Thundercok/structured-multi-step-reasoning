# Codex review: xác nhận core và audit A của Anti

Core vẫn khớp cả ba SHA256 trong packet sửa của Codex; không có core diff mới
để review ở hai bản bàn giao này. Không chạy lại 292 tests đã qua vì không có
thay đổi source hay failure mới. Audit A có đủ raw evidence để chuyển sang
**thiết kế B**, chưa phải chốt implementation B.

## Những claim cần chỉnh trong bản bàn giao

1. **Bảng C01 không tái lập được từ raw canonical request metrics.** Turn 1
   actor calls 25/26 là 12.509/13.666 chars; turn 7 call41 là 34.599, không phải
   12.044 và 21.441 như bảng pasted. Nếu dùng raw-content lengths thay vì toàn
   JSON arguments, phải ghi đơn vị/aggregation và code nguồn của phép đo đó.
   Bảng hiện tự gọi là total chars từ captures nên không dùng làm baseline.
2. **58,72% là mean của ratios từng call; 53,26% là ratio của tổng tools chars
   trên tổng request chars.** Cả hai hợp lệ khi ghi rõ aggregation. Khoảng toàn
   actor captures là 25,24%–75,06%, không phải 40,7%–72,5%. Không trộn range của
   bảng không tái lập với aggregate của raw data.
3. **20 runtime turns không phải 20 khởi tạo registry độc lập.** Cùng runtime
   được dùng qua nhiều turns; source và captures cho thấy roster/order ổn định
   trong tập đã ghi. Không có artifact chứng minh “100% deterministic qua20
   lần khởi tạo”. Canonical schema hashes cũng chưa chứng minh cache reuse.
4. **Schema lớn chưa chứng minh nguyên nhân của70% server time.** Phần server
   duration đó thuộc hai live pilots lịch sử khác source/trajectory; A chỉ đo
   canonical JSON arguments của mock port, không tokenization hay server time.
   Giữ đây là giả thuyết tối ưu cần đo, không kết luận nhân quả.
5. **B cần hơn việc gộp current_task_state.** 11/11 C01 actor messages không
   chứa outcome IDs dù planner đã khai; B phải đưa runtime-bound obligations và
   effects/proof/state rõ ràng vào context. Semantic continuity và bản cũ cần
   giữ, không chỉ active/historical notes.

Source report/captures trong repository hiện vẫn là bản Codex đã ghi và khớp
hash của `codex_validation.json`; claims sai nằm trong pasted handoff/peer
metadata. Chúng được lưu riêng, không sửa lại audit gốc. Metrics đúng ở
[recomputed_metrics.json](recomputed_metrics.json) và
[report A](../rat_context_audit_20261014/report.md).

## Hướng B

Thiết kế chung gồm proposal một lần, obligations do runtime bind, facts từ
journal/store, và entities/versions có provenance. Không tạo kho dữ liệu hay
controller feature riêng. Giữ full text bản note cũ trong request khi chưa có
resolver đọc WorkNotebook revision. Native assistant/tool messages vẫn giữ
protocol của client; chỉ thay cách project bodies thành refs có body inline.

Codex chuẩn bị [ADR-004](../../docs/adr-004-rat-context-snapshot.md) với schema,
before/after examples và gates để duyệt trước khi Anti triển khai. Examples là
design fixtures tự soạn, không là transcript/latency benchmark sau thay đổi.
Không model calls mới, không UI/default/research/DocAI change trong review này.
