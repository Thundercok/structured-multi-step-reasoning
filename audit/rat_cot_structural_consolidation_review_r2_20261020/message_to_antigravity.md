# Follow-up structural consolidation review r2 — 2026-10-20

Đọc `audit/rat_cot_structural_consolidation_review_r2_20261020/review.md` trước.
Code package/aliases/source hashing đã qua kiểm tra độc lập. Không cần viết
lại canonical package hay thay thuật toán để giải quyết review này.

Còn hai đính chính hồ sơ P2:

1. `tests.log` được transcript ghi đè bằng echo bốn dòng pass summaries. Giữ
   nó như manual summary, không gọi là log pytest đầy đủ. Dẫn raw command/env/
   exit-code/JUnit thật, với ngày và source hashes tương ứng. Reviewer đã có
   raw run mới: 29 research + 53 core + 24 backend pass / 2 skip + 93 runtime;
   thêm 5 package probes pass. Không relabel thành run 17/10 hoặc tự viết thêm
   các dòng pass bằng echo. Không cần chạy model thật cho phần này.
2. Footprint tài liệu/handoff không khớp JSON snapshot 17/10. Historical JSON
   đúng canonical=43,870 bytes / 905 non-blank, shims=1,832 bytes; net=+2,550
   bytes / +60 non-blank / +73 total lines. Tài liệu đang ghi 43,647 / 891 /
   1,772 / +2,267 / +46. Thống nhất theo snapshot/hash; đừng lấy current delta
   +104 lines / +86 non-blank / +4,193 bytes để gán cho move ngày 17.

Reviewer đã xác minh baseline hashes bằng HEAD và reconstruct canonical 17/10
trong audit copy: cả 4 hashes khớp footprint, AST ngoài imports tương đương.
Current parser và Isotonic shape có các sửa sau này; giữ nguyên chúng. Không
restore snapshot cũ lên production để làm claim algorithm unchanged khớp.

Ghi chú P3: import_map.modules.*.file còn root shims vì generator copy nguyên
prev.modules. Khi xuất map mới, ghi cả canonical implementation path và root
compatibility entry; giữ historical map với ngày/hash rõ ràng. Các số đếm
current chỉ dùng trong báo cáo mới, đừng ghi đè audit cũ vì khác ngày.

Sửa living docs/handoff và tạo evidence snapshot mới nếu cần, giữ raw artifacts
và recovery. Main, không commit/branch/push/pull/reset, không thêm model budget,
không đổi prompt/policy/data/scoring/Stage 0. Đây là review structural
consolidation, không phải nghiệm thu repair G1 của overnight runner.
