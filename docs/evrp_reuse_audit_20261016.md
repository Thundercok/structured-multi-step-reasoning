# EVRP / SaigonRide — rà tái sử dụng để debloat

2026-10-16. Rà tĩnh, không chạy app, benchmark, model, payment hay data fetch.
RAT sử dụng CoT; việc tách ở đây nhằm bỏ dự án ghép vào không phục vụ hệ đó.

## Kết luận

**Chưa có implementation cần tái sử dụng ngay vào RAT–CoT.** Giữ dự án độc lập
và chuẩn bị đưa về repo riêng; không thêm .NET, database hoặc training PyTorch
vào môi trường RAT để tạo một integration không có nhu cầu cụ thể.

| Thành phần | Giá trị có thể giữ | Xử lý |
| --- | --- | --- |
| ASP.NET thuê xe, payment, ví, auth, kiosk, SignalR | Nghiệp vụ SaigonRide | Tách nguyên dự án, không tích hợp RAT |
| `EvrpSolverService.cs` | Haversine, greedy route construction, 2-opt và mô phỏng tải/pin | Giữ ở dự án tuyến đường; chưa có yêu cầu RAT dùng routing |
| Python `scripts/run_benchmark.py` | Generators VRPTW/EVRP, optimizers và benchmark legacy | Giữ để dùng sau; không đưa thành dữ liệu/đối chứng CoT hiện tại |
| Trạm sạc và script fetch | Dataset snapshot và công cụ riêng cho EVRP | Bảo toàn nguồn; không phải live availability |
| Các bản sprint/submission lặp | Lịch sử đồ án | Bảo toàn khi chuyển; dedup tại repo riêng sau |

Một bài toán tối ưu có thể trở thành một miền đánh giá reasoning trong tương
lai, nhưng đó là phạm vi nghiên cứu mới cần review, không phải lý do giữ cả
ứng dụng thuê xe trong main repo. Chưa có bằng chứng cải thiện CoT từ EVRP.

## Phát hiện cần giữ khi tách

- Git-visible source ở snapshot codebase: 247 tệp / 26,903 dòng không trống;
  exact-byte duplicate scan cho 10,974 dòng dư. Chỉ là số source theo quy tắc
  scanner, không phải toàn bộ dữ liệu nằm trên disk hoặc authored LOC.
- Cây thực có 448 regular files / 41,379,543 bytes khi rà. Có file ngoài mẫu số
  Git-visible, ví dụ Python scripts bị ignore và bytecode; inventory phải bao
  phủ toàn cây trước khi quyết định giữ/bỏ, không dùng mỗi `git ls-files`.
- `IMPORT.md` / `IMPORT_PROVENANCE.json`: nguồn `Thundercok/evrp-optimizer`,
  revision `2c8fa69f8f3cfeae475792159ff0ebcf20529044`, 104 commits được subtree
  import không squash. Giữ history, không rewrite imported commits để cleanup.
- README hiện trỏ `Thundercok/SaigonRide`. Chưa kiểm tra remote nào là đích hiện
  hành; không tự publish hoặc ghi đè một trong hai repo dựa trên tên.
- Provenance ghi 7 local extra files: hai scripts, ba tệp charging-station data,
  hai tệp benchmark results. Phải so current hashes và bảo toàn thay đổi mới.
- `run_benchmark.py` tạo procedural instances, dùng tên/BKS inputs có sẵn và
  seed từ Python `hash(instance_name)`. Không coi số đo cũ là chuẩn CoT hoặc
  benchmark tái lập được chỉ vì global seed bằng 42.
- Rà các Python/shell/TOML/spec ngoài module, không thấy tham chiếu EVRP trong
  runtime RAT, harness, shared intake hoặc tests đã tìm. Đây là static search,
  chưa phải sandbox acceptance khi không có module.

## Bước tiếp theo

Antigravity chuẩn bị inventory, archive/restore, bản tách độc lập và kiểm tra
RAT–CoT không cần module. Dùng repo gốc như ứng viên để đối chiếu; chốt đúng đích
trước publication/removal. Chưa xóa phần nào hoặc chạy code benchmark trong lượt
rà này. Không tính 26,903 dòng là đã giảm khi module vẫn còn.
