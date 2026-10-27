# Phạm vi dự án và vai trò RAT — quyết định người dùng

Cập nhật: 2026-10-16, Asia/Ho_Chi_Minh.

Bổ sung người dùng 2026-10-25: **“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING
AGENTIC.”** Mọi khả năng nghiệp vụ là Reasoning Tools trong hệ điều phối của
Agent; không phát triển utility độc lập. UI và Agent dùng chung hợp đồng thực
thi/kết quả/kiểm tra. Xem `AGENTS.md`; khi bàn giao phải phân biệt tool đã đăng
ký, UI projection và vòng lập kế hoạch/suy luận đã thực sự được nối. Nguyên tắc
này không thay research gates hay biến mọi domain thành đóng góp nghiên cứu.

Bổ sung người dùng 2026-10-26: **RAT Mini là vertical slice của RAT chính để
tái sử dụng về sau**, không phải tiện ích riêng làm riêng cho bạn người dùng.
Mini giới hạn hai capabilities, giữ trọn luồng yêu cầu → điều phối tool → quan
sát/kiểm chứng → UI. UX dùng một ô nhập, không bắt chọn mode Tìm file/Dịch.
Quyết định và trạng thái triển khai: [RAT Mini vertical slice](rat_mini_vertical_slice.md).

## Quyết định áp dụng cho mọi chat

**Câu chốt của người dùng: RAT SỬ DỤNG CoT; CoT ĐƯỢC THỂ HIỆN BẰNG RAT.**
Khi visualize hoặc debloat, gom runtime, phương pháp, hạ tầng và harness thành
các vai trò trong cùng một hệ; không đặt RAT và CoT thành hai dự án ngang hàng.

Người dùng xác nhận (2026-10-25): **“TẤT CẢ CHỨC NĂNG ĐỀU ĐI THEO REASONING AGENTIC.”**
Không xây dựng bất kỳ tính năng nào dưới dạng tiện ích độc lập (isolated dumb utility).
Mọi khả năng trong RAT (tìm tệp/ứng dụng, đọc trích đoạn, tính toán, kiểm chứng số học)
đều là các công cụ (Agentic Tools) được điều phối và kiểm soát trong vòng lặp suy
luận có cấu trúc (Structured Reasoning / CoT Loop):
`[Mục tiêu / Yêu cầu]` → `[CoT phân rã & Lập kế hoạch]` → `[Điều phối Tool]` →
`[Quan sát thực tế (Observation)]` → `[Đối chiếu kiểm chứng (Verification & Grounding)]` →
`[Dừng tối ưu (Optimal Stopping)]` → `[Kết luận / Hành động có bằng chứng]`.

Người dùng xác nhận: **“RAT là implementation chính của CoT.”** Đây là đính
chính cho cách diễn giải trước đó coi toàn bộ RAT là demo phụ, chỉ làm sau
nghiên cứu. Các chat tiếp theo phải dùng định hướng này khi lập kế hoạch,
phân loại mã, đề xuất thu gọn hoặc đánh giá công việc.

CoT/structured reasoning là phương pháp đang nghiên cứu; RAT là ứng dụng chính
để triển khai và sử dụng phương pháp đó. Pipeline headless là môi trường đánh
giá tái lập; bài NCKH trình bày câu hỏi, phương pháp, bằng chứng và giới hạn.
Đây là các thành phần của cùng dự án, không phải hai dự án CoT và RAT độc lập.

Vai trò implementation chính là định hướng đã chốt, **không phải xác nhận** mọi
chiến lược/controller trong harness đã được nối vào RAT hoặc chạy tương đương.
Cần đọc code, đối chiếu hợp đồng và đo hành vi trước khi khẳng định trạng thái.

## Phân biệt core và phần mở rộng

| Nhóm | Vai trò và cách ưu tiên |
| --- | --- |
| Suy luận CoT/structured reasoning trong RAT | Core: triển khai cách suy luận và đầu ra phục vụ công việc thực. |
| Chọn chiến lược, kiểm tra, tiếp tục/dừng và ngân sách | Core khi thực hiện phương pháp đã chọn; trạng thái triển khai phải được kiểm tra. |
| Tool execution, ngữ cảnh và hợp đồng kết quả | Nền tảng core khi cần cho thực thi phương pháp và kết quả có thể kiểm tra. Không mặc định mọi tool là đóng góp nghiên cứu. |
| Nguồn, artifact, lỗi và trạng thái thực thi trong UI | Có thể cần cho core và acceptance. Phân biệt hành động dự định với hành động đã chạy; không hiển thị raw/private reasoning. |
| Pipeline headless và verifiers | Đo phương pháp, so sánh và kiểm tra tái lập; không cần Qt hay lập chỉ mục tệp cá nhân để chạy nghiên cứu. |
| Animation, mascot, lịch, astrology và tiện ích riêng | Mở rộng; không tự trở thành nghiên cứu CoT chỉ vì nằm trong RAT. |
| PDF/OCR dùng chung | Hạ tầng tái sử dụng đã hợp nhất trong `document_intake/`; không phải bằng chứng cải thiện CoT. |
| DocAI hóa đơn/XML/Z3 | Đã gỡ `modules/docai/` ngày 2026-10-17 sau khi tái sử dụng PDF/OCR. Giữ recovery để dùng sau; chưa tích hợp nghiệp vụ hóa đơn vào RAT hoặc harness. |
| Spider, EVRP và watch bot | Đánh giá theo nhu cầu cụ thể; không tự đưa vào core hoặc tính là mã nhóm phát triển chỉ vì nằm cùng repo. |

## Quy tắc khi thu gọn

1. Không xếp toàn bộ `rat/` là mã ngoài bài hoặc đóng băng toàn bộ RAT vì NCKH.
2. Import closure của `experiments.research_study` chỉ mô tả phụ thuộc kỹ thuật,
   không định nghĩa toàn bộ phạm vi nghiên cứu hay danh sách mã được xóa.
3. Trước khi gỡ mã, xác định vai trò, nơi gọi, implementation thay thế và kiểm
   tra hành vi phù hợp. Trùng chức năng không đồng nghĩa hai bản tương đương.
4. Ưu tiên hợp nhất phần trùng thật sự; giữ một nguồn implementation khi hợp lý.
   Không ép UI hoặc phụ thuộc cá nhân vào harness chỉ để trông như dùng chung.
5. Giữ raw artifacts, tests cần thiết, lịch sử và recovery material theo AGENTS.
   Phân biệt giảm mã cần bảo trì với giảm dung lượng ổ đĩa hoặc tổng LOC repo.

## Quan hệ implementation và bằng chứng

Khi chuyển phương pháp hoặc kết quả giữa harness và RAT, ghi rõ model/version,
prompt, chiến lược, ngữ cảnh/tool, verifier, quy tắc dừng, ngân sách và cách tính
chi phí. Nêu phần dùng chung, phần adapter khác và phần chưa được kiểm chứng.
Không suy ra tương đương chỉ từ tên CoT hoặc tên controller.

Tests phần mềm xác nhận hợp đồng/hành vi được kiểm tra. Acceptance trong RAT
xác nhận luồng ứng dụng trong điều kiện đã thử. So sánh chất lượng mô hình cần
dữ liệu đã review, split hợp lệ và run artifacts đúng protocol. Không dùng một
loại bằng chứng để thay thế loại khác. Không suy ra cải thiện accuracy, chi phí
hay latency từ việc tích hợp UI hoặc tái sử dụng thư viện.

Điểm vào nghiên cứu vẫn là `python -m experiments.research_study`. Giữ tách
train/calibration/test, phân biệt synthetic/development/held-out, generated-token
cost/full inference cost và replay time/online latency. Stage 0, dataset review,
ngân sách và execution freeze không thay đổi do đính chính định hướng này.

## Cách bàn giao cho chat khác

Đọc `AGENTS.md`, tài liệu này và tài liệu protocol liên quan trước khi đổi phạm
vi. Trong bàn giao, nêu: mục tiêu RAT/CoT, phần đã triển khai, phần mới đề xuất,
bằng chứng đã có, giới hạn và bước tiếp theo. Nếu tài liệu/snapshot cũ gọi RAT
là “secondary demonstration” hoặc chỉ cho làm RAT sau bài báo, dùng quyết định
2026-10-16 này để diễn giải lại; không sửa raw artifacts lịch sử để xóa dấu vết.

Các điểm vào đã đồng bộ: `AGENTS.md`, `README.md`, `docs/research_plan.md`,
`docs/research_protocol.md`, `docs/rat_backlog.md`. Bản kiểm kê codebase ngày
2026-10-14 giữ số đo lịch sử, kèm đính chính phạm vi; hình treemap cũ chưa phải
phân loại core/mở rộng theo quyết định mới.


## Spider — repo đích và ranh giới đã chốt, 2026-10-16

Người dùng xác nhận `https://github.com/Thundercok/tdtu-timetable-compiler` là
repo đích để chuyển **Spider**, dù tên repo hiện nói về timetable. Đây là dự án
độc lập ngoài phạm vi RAT/CoT; người dùng sẽ mass rework tại đó sau. Không suy
ra yêu cầu tích hợp timetable từ tên repo. Adapter Python tùy chọn đã giữ lại
vẫn default-disabled; mở rộng Spider không còn là ưu tiên main project.

Bản import được chuẩn bị trong checkout riêng, giữ nguyên bốn tệp hiện có của
repo đích và bảo toàn snapshot 325 file cùng license/patch/provenance. Trạng thái
publication/removal phải đọc từ `audit/spider_destination_prepare_20261016/`;
không gọi việc đã chọn đích hoặc chuẩn bị local commit là đã push hoặc đã xóa
cây nguồn. Chỉ gỡ cây gốc sau khi import remote và recovery được xác minh.


## Bản đồ hiện tại sau Spider

Xem [snapshot hệ RAT–CoT ngày 2026-10-16](codebase_scope_20261016.md). Mã app,
reasoning, hạ tầng, harness và tests được gom vào một hệ. Dự án riêng và audit
được hiển thị ngoài mẫu số mã sản phẩm chính; không dùng import closure để
xếp toàn bộ RAT ra ngoài đề tài.


## EVRP — đã gỡ ngày 2026-10-17

Người dùng chọn xóa `modules/evrp/`, không chuyển repo, có thể làm lại từ đầu
sau này. Không còn là integration hay migration đang chờ. Giữ recovery archive,
Git history bundle và audit; không tự nhập lại vào RAT–CoT. Số đo ở
`audit/evrp_removal_20261017/`. Snapshot visualization 2026-10-16 là trạng thái
trước lần gỡ này, không phải inventory hiện tại.


## Watch bot — đã gỡ ngày 2026-10-17

Theo yêu cầu người dùng, đã gỡ `rep_watch_bot/`; không thuộc hệ RAT–CoT.
Bản phục hồi đã kiểm tra byte và quyền tệp nằm trong
`scratch/rep_watch_bot_removal_20261017.tar.gz`; xem
`audit/watchbot_removal_20261017/`. Không tự nhập lại vào startup hoặc dependencies.
DocAI sau đó đã được gỡ theo yêu cầu ngày 2026-10-17; xem
`audit/docai_removal_20261017/`. Giữ `document_intake/` dùng chung và recovery;
không có chuyển repo hoặc tích hợp XML/Z3 trong lần này.


## Mã cũ không còn dùng — gỡ ngày 2026-10-17

Đã gỡ crawler `legacy/V1`, `legacy/V2`, backend cũ `qwen_backend.py` và
`generate_history.py` sau khi kiểm tra nơi gọi và archive đầy đủ. Backend
nghiên cứu `qwen_mlx_backend.py`, các mock còn được dùng và runner lịch sử có
manifest dẫn chiếu vẫn giữ. Xem `audit/unused_source_removal_20261017/`.
Không khôi phục các bản crawler cũ vào runtime RAT. Recovery, legacy checkout
và shared worktrees độc lập vẫn được giữ theo AGENTS.
