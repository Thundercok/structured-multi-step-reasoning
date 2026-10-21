# Gửi Antigravity: triển khai core theo contract đã review

Người dùng đã chốt: **core trước, duyệt UI sau; Codex suy nghĩ và review,
Antigravity làm code**. Triển khai theo docs/adr-003-rat-completion-reconciliation.md
và review.md trong folder này. Phase core đã được duyệt; live model budget và
thay đổi trình bày UI chưa được duyệt. Không chờ duyệt lại cùng thiết kế này.

1. Định nghĩa rõ outcomes ở planner ON/OFF, freeze trước effect đầu; model không
   được xóa nghĩa vụ sau thực thi. Contract sai/vắng giữ unchecked. Coverage intent
   là model_proposed; omit cả outcome chưa thể được gọi “đã xử lý triệt để”.
2. Reuse NoteEvent, DispatchResult/ExecutionEvent, artifacts và VerificationReport.
   Trusted request journal phát hành snapshots có conversation/execution/generation/
   call IDs, before/after revisions và refs. Không tin receipt dict từ model;
   không tạo NoteReceipt thiếu dữ liệu hơn NoteEvent hiện có.
3. Matching phải nối output producer với nguồn note consumer; calculate 324 rồi
   save 126 không được đậu. Không dùng receipt mutation cũ như một mutation mới.
4. Tách lifecycle, completion trong declared scope, intent coverage và scoped quality.
   Proof bắt buộc thiếu/UNKNOWN thì unresolved; UNKNOWN ngoài scope không tự chặn
   mọi search/read/hội thoại. Giữ needs_input. Note proposal thỏa hay chưa tùy
   obligation đã khai, không ép confirm tất cả để demo đậu.
5. Thêm omnibar vào projected wiring: AgentResponse → TurnSnapshot/turn refs →
   full/compact/history cùng reconciliation. Câu “đã ghi” không được tiếp tục hiện
   như xác nhận hoàn tất khi receipt thiếu. Raw candidate giữ ở audit; bounded
   resynthesis/grounded status dùng budget hiện có. Receipt matching chưa chứng minh
   mọi prose đúng; ghi rõ semantic limitation.
6. Reconciler chung theo registered effects/scopes, không switch theo các feature.
   Đặt schema/pure matcher trong completion.py nhỏ; không dồn thêm engine vào run().
   Giữ Chuột, composer, inline notes và layout. Review copy riêng; receipt là trace,
   không dùng câu “đối chiếu biên nhận” trên bề mặt sản phẩm.
7. Cancel sau calculate commit và HTTP timeout probe là hai fixtures khác nhau.
   Giữ artifacts commit trước cancel; tiếp tục bằng execution mới, không đổi turn cũ.
8. Budget A/B chưa được duyệt. Hai arms cần hai conversations và cap tổng calls
   thực thi tại client (planner/repair/cancel cũng đếm), timeout/wall cap/model.
   Model-call wall khác server generation; nested note check không double count.
   Không tự chạy model, đổi default hay dùng script max_steps làm total-call cap.

Bổ sung fixtures ở ADR, đặc biệt omitted-outcome, wrong-source producer/consumer,
receipt cross-execution, downgrade contract, pending input và unresolved history/UI.
Làm một lát cắt core/fixtures trước. Wiring reconciliation vào history/turn refs
là phần correctness của core; không thay layout, copy/badge hay chuyển trạng thái
hiển thị trong phase này. Ghi rõ phần consumer UI còn chờ; chưa công bố end-to-end
native acceptance. Live/native và copy acceptance là phase tiếp. Không tính 206
tests mốc cũ thành validation của code mới. Không push/pull/reset/force nếu user
không yêu cầu trong cùng message.
Giữ nguyên research/DocAI và mọi audit cũ. Báo diff thật thay vì line-count ước tính.

## Bàn giao lại để Codex review

Folder audit mới chứa diff thật, source hashes trước/sau, command và test logs,
fixture transcripts có outcomes/receipts/matched/unmet IDs, cùng giới hạn còn lại.
Tách tests phần mềm khỏi model quality. Giữ các ca thất bại và contract bị bỏ sót.
Nếu native decision encoding cần thêm calls, ghi chính xác đường planner ON/OFF
và cost; không gọi một schema cố định là proof model hiểu intent. Chưa chạy live
ablation khi chưa có budget được user duyệt. Báo phần core đã làm và phần UI chưa
tiếp nhận reconciliation để Codex review trước khi sang phase UI.
