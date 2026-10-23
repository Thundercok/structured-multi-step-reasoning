# Review bàn giao research bridge — 2026-10-23

**Cần sửa trước khi kết luận tương đương end-to-end.** Nhận 8 ca parity mới
trong module 22 tests; kiểm độc lập cả module và bộ research bắt buộc:
**51 passed in 19.20s**, không skip/failure/error. Có counterexample mới làm
đổi route do feature preprocessing. Reviewer không sửa production/test của
Anti và không gọi model thật; fitting trong probe chỉ dùng authored synthetic.

## R1 — P1: embedding khác preprocessing có thể làm đổi route

`experiments/research_study.py:188` chuẩn hóa vector:
`embedding / max(norm(embedding), 1e-12)`. Nhưng
`reasoning/runtime.py:234–242` đưa trực tiếp `backend.embed(query)` vào
predictor. Protocol backend chỉ yêu cầu mean-pooled hidden state, không cam kết
unit norm; `qwen_mlx_backend.py:122` cũng trả mean-pooled vector chưa chuẩn hóa.

Probe đi qua **collector thật**, `evaluate_records`, `OnlineReasoningController`
và `MetaReasonerEngine`, dùng cùng predictor và cùng backend trả `[3, 4]`:

| | Harness | Runtime |
| --- | --- | --- |
| Embedding predictor nhận | `[0.6, 0.8]` | `[3, 4]` |
| Path | `COT` | `REACT` |
| Generated tokens, synthetic | 10 | 10 |

Predictor được fit trên 100 authored synthetic unit vectors và targets chi phí
phụ thuộc vector. Không dùng real data hoặc candidate questions/golds. Các ca
mới của Anti dùng constant performance targets và constant costs, nên không
phát hiện việc scale đầu vào predictor khác nhau. Việc cung cấp sẵn cùng vector
cho cả hai đường chỉ kiểm decision/execution sau feature preparation.

**Sửa cần thiết:** khai báo/bind preprocessing của research-compatible profile
trong feature/bundle contract và dùng đúng cùng phép biến đổi khi collect,
train/replay và online inference. Giữ rõ semantics của bundle legacy nếu từng
fit trên raw vectors; không đổi ngầm mọi policy hoặc gán approved cho metadata
thiếu. Không sửa producing hashes hoặc raw outputs lịch sử để che source drift.
Thêm regression qua collector thật với predictor nhạy feature scale, rồi kiểm
lại ladder/ReAct/PAL. Không cần model thật để sửa và kiểm gap này.

## R2 — P2: gold-independence fixture vẫn truyền labels vào backend double

`AuthoredRecordBackend(record)` giữ nguyên record, gồm `gold` và từng
`attempt['correct']`. `run()` hiện không dùng các trường này, nhưng test không
thỏa contract đã giao là gold chỉ ở phía evaluator. Nó chứng minh nhãn không
được dùng trong các lần chạy đó, chưa chứng minh nhãn không đến backend.

Chỉ truyền query/features và whitelisted answer/confidence/token outputs cho
double; giữ gold/correct ở evaluator. Kiểm boundary input và outcome-independence
riêng, trên policy đã cố định. Đây là vấn đề fixture, **không phải bằng chứng
backend model thật đang nhận gold**; collector hiện chỉ gửi query/format metadata.

## R3 — P2: mapping và báo cáo đang vượt bằng chứng

Bảng mới trong `docs/research_protocol.md` cần chỉnh theo source:

- Prompts hiện do backend/profile và suffixes quy định; không có một
  `DEFAULT_PROMPTS` chung được kiểm ở các source đã dẫn. Replay không tạo
  `MockDemoBackend` hoặc gọi backend. Matching prompt/settings cần được chứng
  minh theo profile, không suy từ protocol `embed/run/hidden_size`.
- Harness dùng complexity schema v1; runtime có thể nhận bundle v2 (6 features).
  Không ghi mọi feature input đều identical, nhất là khi R1 đang mở.
- `fit_policies` dùng `OptimalStoppingPolicy(lam).fit(...)` mặc định không bật
  Isotonic. Test inject Isotonic là một ca software, không phải quy trình fit
  mặc định của harness. Confidence gate lịch sử đánh incremental CV AUROC,
  không phải một phép kiểm calibration xác suất tổng quát.
- Evaluator dùng `check_answer`: procedural checkers, normalized text/aliases
  hoặc numeric tolerance; không chỉ `answer == gold`.
- Qwen `_tot` lấy complete candidates rồi gọi model chọn index, invalid index
  thì majority fallback; mô tả chung là consistency scoring chưa chính xác.
- `tokens / 1000` là **nghìn token**, không phải millitokens. Cost smoke là
  synthetic units; không gọi là actual measured generated tokens.
- Báo cáo liệt kê research 29, online module 22 và UI 55 nhưng ghi tổng 77.
  Các file suites được liệt kê là tách biệt, tổng là 106 lượt thực thi; 77 có
  thể mô tả riêng 22+55 nhưng không phải cả ba hay toàn repo. Reviewer xác
  nhận được raw JUnit của 22+29; không chạy lại UI hoặc xác nhận full-repo 77.
  `current_progress.json` còn ghi HEAD `73a15ec`, checkout là `11c8496`.
- Chưa có quyết định chọn `Qwen2.5-7B-Instruct` trong gói này. Bỏ ví dụ đó khỏi
  vị trí trông như checkpoint đã chọn; giữ model/revision pending, dẫn đúng
  provenance khi có quyết định. Byte hashes không chứng minh tập test chưa từng
  bị lộ; rộng hơn phạm vi lần này vẫn review-pending.

Vai trò hiện tại của ContradictionAuditor là hậu kiểm ở worker, không điều
khiển routing/stopping. Đây là sự thật implementation có thể ghi ngay, không
cần đặt thành một câu hỏi xin human xác nhận lại. Chất lượng checker là vấn đề
khác, chưa được suy ra từ parity tests.

## Phần được xác nhận và hồ sơ tái lập

- `results.json`, `summary.json`, `policy.json` smoke/replay khớp từng byte và
  đúng ba hashes Anti báo cáo. Manifest declared hashes và source hashes hiện
  khớp. Đây là replay consistency của synthetic run.
- Bốn candidate artifact hashes khớp release manifest. Chỉ hash bytes;
  không parse, in hoặc giải held-out queries/golds. Không đóng human/source/
  exposure review hoặc Stage 0/fresh campaign budget từ kiểm tra này.
- `checks.json` giữ source hashes nhận bàn giao, run integrity, JUnit counts,
  fixture label exposure và counterexample. `received_regression.txt/.xml`
  là fresh run của reviewer; các logs Anti trong thư mục cha giữ nguyên.
- Reviewer chỉ tạo hồ sơ review và cập nhật kế hoạch hiện hành; không sửa
  runtime, harness, fixture tests hoặc báo cáo gốc trong Antigravity brain.

Chạy từ repository root, trên source hashes trong `checks.json`:

```bash
.venv/bin/python -m pytest tests/test_online_reasoning.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q --junitxml=audit/rat_cot_quick_unification_20261022/research_bridge/codex_review/received_regression.xml
.venv/bin/python audit/rat_cot_quick_unification_20261022/research_bridge/codex_review/review_bridge.py
```

Probe ghi findings và trả exit 0 khi đã chạy xong; `route_mismatch=true` là
counterexample được tái hiện, không phải một ca parity pass. Khi sửa source,
lưu lần kiểm mới riêng; không ghi đè logs/hashes nhận bàn giao để làm như lần
trước đã pass. Timings là test/probe wall time, không phải latency online.
