# GSM8K query-only — hồ sơ chuẩn bị review, 2026-10-23

**Cập nhật 2026-10-24:** phần bên dưới là snapshot trước khi review nội dung.
Theo yêu cầu tiếp tục của người dùng, agent đã đọc và giải đủ 96 query trước
khi so gold: 93 khớp, 3 tranh luận; human sign-off vẫn pending. Xem
[review dữ liệu và provenance mới](../audit/gsm8k_candidate_agent_review_20261024/README.md).
Candidate gốc không đổi, chưa fit rule hoặc gọi model; budget vẫn 0.

Trạng thái: **chuẩn bị review, chưa cho chạy**. Inference/embedding budget = 0.
Không đọc nội dung câu hỏi, source solutions hoặc outcomes của candidate 48/48;
không fit candidate. Chỉ đối chiếu source, metadata và software evidence.
Bridge acceptance đã đóng, không mở lại. Checker dry-run thuộc phần Anti.
Tài liệu này không thay protocol hoặc execution freeze.

## Đối chiếu source

[Software acceptance](../audit/gsm8k_query_only_software_20261023/README.md)
ghi 81 tests pass trên authored fixtures. Cả năm source fingerprints trong
`evidence/verification.json` vẫn khớp tại lượt kiểm tra này: fitter, entry point,
routing tests, protocol và script tạo evidence. Không chạy lại tests khi chưa
có thay đổi implementation; số 81 là evidence đã lưu, không phải lượt test mới.
Fingerprint chi tiết ở
[metadata verification](../audit/gsm8k_review_readiness_20261023/verification.json).

`experiments/gsm8k_routing_baseline.py` thực hiện menu 27 rules, chọn rule và
fixed reference chỉ trên fitting, lưu selection trước validation. Measured
input guards yêu cầu 96 items/96 groups, 48/48 development roles, đúng model và
source revision. Guards không duyệt semantic gold, ownership hoặc prior exposure.

Candidate manifest khai báo 96 nhóm, loại 24 normalized identities cũ và không
dùng official test. Metadata này chưa phải tái kiểm nội dung hoặc semantic
duplicates. Hashing opaque file bytes chỉ kiểm tra toàn vẹn, không phải review
câu hỏi/gold. Không sửa manifest hoặc release lịch sử để hợp thức hóa thay đổi.

## Phiếu review dữ liệu cần hoàn tất trước collection

| Mục | Bằng chứng cần lưu | Trạng thái hiện tại |
| --- | --- | --- |
| Nguồn và quyền dùng | Source revision, LICENSE/README, provenance và người duyệt quyền sử dụng/phát hành | Có archive metadata; human review pending |
| Frame và exposure | Reproduce ranking seed 42; đối chiếu đủ 24 exclusions kể cả walking item; giữ original line IDs; ledger các nguồn đã xem | Manifest khai báo, chưa tái kiểm candidate |
| Semantic grouping | Đối chiếu paraphrases/biến thể giữa hai roles và với pilot đã lộ; ghi giới hạn của normalized identity | Pending |
| Query-derived gold | Giải độc lập từ query trước khi so source solution/gold; lưu phép tính, đơn vị, giả định và kết luận | Chưa mở 96 câu |
| Wording và parser | Kiểm đủ dữ kiện, cách làm tròn, đơn vị và contract bare-number; không đổi parser theo model outcomes | Pending |
| Human sign-off | Reviewer/date, từng item accept/exclude/revise và lý do trước generation | Pending |
| Release | Nếu retained frame đổi, tạo release mới và review lại protocol/48-48 guards trước collection | Chưa freeze |

Khi mở review, dùng ledger theo item: `id`, original source line/hash, role,
reviewer/date, independent query calculation, source-gold agreement, assumptions,
semantic-group/exposure references, decision và rationale. Review gold phục vụ
chất lượng dữ liệu; không đưa gold/solution vào feature hoặc model prompt.
Không tự coi human approval đã có khi mới có agent review. Không thay câu sau
khi thấy generation outcomes. Candidate validation là development, không phải
main-study test; vẫn giữ luật không dùng outcomes để sửa/chọn rule.

## Cấu hình cần pin cho phép đo

| Thành phần | Thiết kế hiện có | Việc cần review/pin |
| --- | --- | --- |
| Dataset | GSM8K train revision `3101c7d5072418e28b9008a6636bde82a006892c`, 48 fitting/48 validation | Reviewed release/hash và role/group counts thực tế |
| Model | `mlx-community/Qwen3-8B-4bit`, revision `545dc4251c05440727734bcd94334791f6ab0192` | Rehash local content và provenance ngay trước load; archive cũ không xác nhận content hiện tại |
| Recipes | DIRECT/COT/PAL, `english-math-v1`, temperature 0, thinking off, seed 42, cap 1.024/call | Exact suffix/template/tokenizer, backend/scoring/PAL helper hashes, packages/platform |
| Selection | 27 rules; utility weight 0,1; comparator fit cùng fitting, tie order theo protocol | Không đổi cutoff/lambda hoặc comparator từ validation |
| Validation | Một lần trên saved bank; 2.000 group-bootstrap draws seed 42 | Pin analysis source/protocol và selections trước khi xem validation scores |

Collector mặc định chỉ lấy **1 group mỗi stratum** và caps 96/1.024 nếu không
truyền overrides. Với frame 48/48 đã được duyệt, cấu hình dự kiến phải chỉ rõ
`--strategies DIRECT COT PAL --prompt-profile english-math-v1 --max-tokens 1024
--groups-per-stratum 48 --seed 42`, cùng backend/model/provenance/dataset cụ thể.
Đây là mô tả cấu hình cần duyệt, không phải lệnh đã được cấp quyền chạy. Không
dùng defaults hoặc lệnh pilot 23 câu cũ để thu phép đo này.

Trần kế hoạch: 96 × 3 = **288 generation calls**, tối đa **294.912 generated
tokens**, tối đa 96 PAL execution attempts, timeout helper 5 giây/lần. Không
model retry, embedding hoặc model download. 480 giây là tổng các timeout PAL
danh nghĩa, không phải trần wall-clock toàn run. Prompt tokens, loading và
overhead chưa có trần; đây chưa phải full inference cost/thời gian ước lượng.
Chi phí collection gồm cả ba arms; replay rule chỉ tính arm được chọn.
Các trần này là đề xuất review; ngân sách được cấp vẫn **0**.

## Collector: các điểm chưa được software acceptance trên fitter giải quyết

Đọc `experiments/research_pilot.py` cho thấy completed records được flush vào
`attempts.jsonl` sau `backend.run` và các kiểm tra record. Exception lưu failed
manifest; output cũ bị từ chối. Collector này chưa có resume cho partial run,
chưa ghi started-call journal trước inference, và không fsync từng record.
Vì vậy crash/lỗi giữa generation và append có thể để lại calls đã tốn chi phí
nhưng không có completed record. Không gọi đây là accounting/resume đã nghiệm thu.

Trước collection cần review cách ghi started/completed/failed attempts, xử lý
interruption và tổng ngân sách tính cả failed/unknown-cost calls. Chọn cách
dừng/khôi phục hoặc chấp nhận giới hạn bằng quyết định rõ ràng trước run;
không tự rerun toàn bank hoặc thêm retry ngoài ngân sách. Kiểm bằng authored
fixtures trước, không dùng candidate để thử collector. Đây là công việc
collector nghiên cứu, không phải mở lại bridge hoặc giao thêm việc checker.

Pilot report sẵn có chứa cả hai development roles. Chỉ đọc outcomes fitting để
chọn rule/comparator; không dùng report đó để chỉnh thiết kế. Analysis mode lưu
selection trước validation scoring, nhưng không ngăn người đọc report thủ công.
Cần quy trình giữ report/outcomes validation chưa xem cho đến khi selection
đã pin, kèm ledger access/exposure và người phụ trách review.

## Bản thảo và phối hợp công việc

Diễn giải được phép hiện tại: baseline query-only và kiểm tra phần mềm đã có;
chưa có kết quả measured development validation. Phép đo này là screening của
rule độ dài, không kiểm H1 entry-plus-stopping, không chứng minh tool gây ra lợi
ích, không thiết lập novelty hoặc độ vững nhiều seeds. CI có điều kiện trên
rule/seed, không gồm fitting uncertainty; CI chứa 0 không chứng minh tương đương.

SoL-Pi nằm ở RAT-EFF-01 trong [backlog](rat_backlog.md). Chuẩn bị thiết kế có thể
song song; không ghép compaction/action fusion vào collection routing này.
Nếu tối ưu runtime làm đổi context/prompt/cost contract, cần phép đo/source
freeze riêng. Giữ bridge đã đóng và phần checker của Anti độc lập. Bước tiếp
theo là hoàn tất phiếu data/config/collector review trên đây; chưa mở candidate,
thực thi model hoặc thay Stage 0 từ tài liệu này.
