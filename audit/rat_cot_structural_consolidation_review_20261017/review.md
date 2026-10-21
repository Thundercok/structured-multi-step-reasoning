# Review đề xuất gom cấu trúc RAT–CoT — 2026-10-17

Verdict: cần sửa phân tích và kế hoạch trước khi triển khai. Chưa có package reasoning/; đây là review đề xuất, không phải review refactor đã chạy. SHA256 cả bốn module khớp footprint.json, nên nhận xét không do source lõi đã đổi sau snapshot. Không thay đổi thuật toán/model/runtime trong review này.

## P1 — Thiếu cập nhật source provenance khi chuyển implementation

experiments/research_study.py:344 source_hashes() vẫn hash bốn file root cố định. Sau move thành shims, thay đổi implementation canonical sẽ không được phản ánh bởi các hash đó. Bổ sung toàn bộ module canonical và package initializer vào manifest/hash cùng shims; rà các source-pinned checks khác. Test meaningful: thay đổi chỉ một canonical source byte phải làm fingerprint thay đổi. Không sửa hoặc relabel raw run artifacts cũ.

## P1 — Mô tả tích hợp predictor/stopping vượt code thực tế

docs/rat_cot_structural_consolidation_20261017.md:45-61 mô tả routing/stopping như implementation tương tác đã nối. AST của rat/engine/meta_reasoner.py không có Name use của EntryPredictor/EntryChoice ngoài import; không instantiate/fit/predict predictor. __init__:83-85 tạo policy rồi gán tau cố định. Nhánh policy:335-347 dùng confidence cố định 0.58, so trực tiếp tau[0], sinh chuỗi đồng thuận 5/5; không gọi should_escalate hay chạy năm lần lấy mẫu tại đó. Comment pre-fitted không phải artifact chứng minh nguồn thresholds. Phải ghi rõ đây là heuristic/simulation ở lát cắt meta_reasoner, không suy rộng ra toàn bộ runtime RAT. Không tự triển khai predictor hoặc đổi policy trong structural refactor. RAT vẫn là implementation target chính của cùng hệ CoT; khoảng trống tích hợp là core backlog.

## P2 — Phân tích harness sai đường chạy và split

research_study.fit_policies():251-257 fit stopping trên calibration, predictor trên train bằng entry_training_data(). Không gọi collect_entry_training_data hoặc khởi tạo ReasoningEnv Gym loop trong entry point này; thu records rồi replay ladder_path/evaluate_records. OptimalStoppingPolicy.fit mặc định n_bootstraps=0; nghiên cứu entry point gọi fit không bật bootstrap=200. Không gộp API khả dụng trong module hoặc pipeline cũ thành hành vi entry point hỗ trợ.

## P2 — Star re-export chưa bảo đảm compatibility

Kế hoạch from reasoning.* import * không tái xuất tên underscore, ví dụ reasoning_strategies._eval_arith, và tạo module namespace riêng: monkeypatch binding ở shim không đổi globals của hàm canonical. Cần chọn compatibility có chủ đích, kiểm tra identity/circular imports/patch behavior và serialized module paths nếu có artifacts liên quan. Không tuyên bố 100% backward compatibility từ các test trước refactor. Package initializer phải nhẹ; import strategies không được kéo sklearn/Gym/Qt chỉ vì __init__ gom exports.

## P2 — Trạng thái và số đo cũ

DocAI đã gỡ, không khôi phục modules/docai. qwen_backend.py đã gỡ nhưng import_map vẫn tính nó là consumer reasoning_env. Counts và mẫu số cần timestamp, regenerate từ working tree hiện tại; giữ audit cũ làm lịch sử. 885 nonblank hiện khớp; footprint ghi 1035 dòng tổng trong khi tài liệu ghi 1039. Việc di chuyển có shims/__init__ sẽ thêm ít dòng/file, không thể cam kết delta vật lý bằng 0 trước khi đo. Không đồng nhất không đổi logic với không đổi LOC.

## Validation đọc được

Bản bàn giao có log 29 harness + 93 runtime tests pass trước refactor. Lượt cleanup sau đó của Codex có 131 tests pass. Không kết quả nào chứng minh package migration chưa thực hiện sẽ pass. Review này chỉ đọc code/AST/hash và viết tài liệu, không chạy lại tests không đổi source.
