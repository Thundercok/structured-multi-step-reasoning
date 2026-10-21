Đọc independent review mới tại
`audit/rat_overnight_sweep_codex_review_r3_20261019/review.md` cùng raw logs.
R1 startup và R2 answer navigation đã đóng trên bộ 289 pass. Giữ fixes đó;
không cần làm lại vòng full sweep hay model smoke để tăng số test.

Còn bốn P2 được tái hiện bằng fixtures, sửa hết phần software/offline trong
một lượt. Vẫn là cùng hệ RAT–CoT/NCKH. Giữ main/dirty work/recovery và mọi audit
cũ; không push/pull/reset/force/branch. Không gọi model thật: 12 requests trước
đã dùng ngân sách, ledger cũ phải giữ byte-identical.

1. **C1 — rational parser regression:** `_clean_cand` mới rút `... = 2/3` thành
   `2`, `x = 3/4` thành `3`. Chỉ rút khi toàn bộ conclusion đúng scalar grammar;
   nếu rational/expression thì giữ đúng giá trị/cấu trúc. Giữ placeholder và
   integer fixes. Không nới typed research scoring hoặc thay frozen labels.
2. **C2 — telemetry không được gán lịch sử vào phiên mới:** `--fake-backend`
   một call hiện vẫn ghi real_model_calls_executed=1, verified_12 status và bốn
   warm stats hardcode. Tách mode/session/model provenance từng request; fake
   phải 0 real calls. Tính stats từ ledger đúng session, không warm sample thì
   null/n=0. Status/gates dựa case plan và observed results. Giữ kết quả historical
   riêng; không thay load/RSS của phiên 12 calls bằng sample runner khác mà thiếu
   raw provenance/session ID. Các giá trị 27.542→1.258s và RSS 104.09→2221.72 MB
   trong bản mới cần truy nguồn hoặc giữ original + nêu phần chưa xác minh.
3. **C3 — budget resume:** `count_existing_attempts` đếm cả request_start và
   request_complete. Đếm unique request identity/start một lần, vẫn tính pending
   start là attempt và hỗ trợ legacy records. Không tăng max-budget để bù.
   Kiểm completed/pending/legacy/mixed + partial-run/resume bằng fake backend.
4. **C4 — candidate identity:** hai bundle cùng directory, cùng metadata name/
   version nhưng tên filesystem khác (`App.app`, `App copy.app`) vẫn trùng nhãn.
   Dùng full bundle path/basename khi parent suffix không đủ unique; giữ full
   tooltip/payload/index và phần phân biệt visible tại 420px.

Probe mới tại `audit/rat_overnight_sweep_codex_review_r3_20261019/test_remaining_probes.py`:
13 cases, đã có 8 fail / 5 pass trong hai lượt có log riêng. Không sửa assertions
cho xanh. Để kiểm artifact runner sau fix, chạy `--fake-backend --max-budget 1`
vào **output dir mới**, rồi đặt env `RAT_REVIEW_FAKE_OUTPUT_DIR` trỏ tới dir đó
khi chạy probe. Không ghi đè `fake_session/` của review hoặc ledger 12 real calls.
Giữ các old visual/navigation/startup probes nguyên vẹn.

Chạy affected parser checks (`test_reasoning_strategies.py`,
`test_qwen_mlx_backend_mocked.py`, `tests/test_research_scoring.py`) và bộ research
bắt buộc theo AGENTS khi đổi parser; giữ typed constraints/negative cases. Một
consolidated regression cuối cho source cuối nếu cần, tránh lặp full 132-file pass.

Đính chính nhỏ trong handoff/map: method thực của QtViewRenderer là
`_render_input_form`, không có `render_candidates`. Với 16 stale failures còn
lại, ghi đúng từng contract/status/tolerance/score change, không giải thích mọi
VGC failure bằng locale strings hoặc mọi query failure bằng keyword expansion.
Không nới verification để làm tests xanh. Native GUI queue vẫn not-run/blocked
nếu thiếu display/budget; không cần thêm inference để sửa bốn lỗi trên.

Audit mới phải có source trước/sau, delta, raw stdout/XML, fake request counts,
session-aware stats và status từng finding. Không tuyên bố tất cả resolved khi
artifact fake còn tự ghi real-model evidence hoặc kết luận phân số bị đổi giá trị.
