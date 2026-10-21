# Tóm tắt cho Claude — từ câu trả lời về giả định 2/12 nhạy biên

Snapshot kiểm tra: **13/10/2026, 15:43 giờ Việt Nam** (08:43 UTC).
Phạm vi là nhánh CoT restart / matched A-F-CONT trong chat này. Trạng thái draw
thứ hai có thể tiếp tục thay đổi; đọc manifest/journal hiện tại trước khi hành
động. Đây là bản bàn giao cho người dùng chuyển sang Claude, chưa tự gửi đi.

Repo đang dùng:
`/Users/thundercock2/Documents/Github/multi-step-structured-reasoning`.
Đọc `AGENTS.md`, `docs/research_plan.md` và `docs/research_protocol.md` trước khi
đổi nghiên cứu. Bài báo NCKH là ưu tiên; Stage 0 không đổi. RAT có chỉnh sửa đồng
thời từ chat khác, ngoài phạm vi bản bàn giao này. DocAI integration vẫn deferred.

## 1. Giữ nguyên nguyên tắc báo cáo ban đầu

M tại cap đăng ký L_i là điểm chính. Các điểm L_i-8 và L_i+8 chỉ là độ nhạy mô
tả trên cùng câu và cùng draw; mỗi arm của một câu phải dùng cùng cap. Không bỏ
câu nhạy biên, chọn cap đẹp hơn, gộp cap thành quan sát độc lập hoặc tự tăng cap
riêng một arm. Nếu thiếu trace thì không ước lượng được điểm đó.

**2/12 trong trao đổi trước là giả định, không phải số đo của run mới.** Draw
đầu đã hoàn tất có **0/12 câu đổi correctness và 0/12 đổi finish reason** tại
M +/-8. Các replay rows lưu correctness, finish reason và parse status ở từng
cap. Chưa chốt delta_prac/lambda hay bật trạng thái GO/NO-GO cho pilot này.

## 2. Hoàn thiện token replay và kiểm tra lịch sử

- Future collection lưu prompt/completion token IDs gốc, terminal EOS,
  finish_reason, seed, decoding config, tokenizer assets và backend identity.
- Seed dùng f(item, arm, call), không phụ thuộc cap/budget. Mock đã cắt text
  thật; replay dựng prefix_text + cut rồi chấm lại bằng parser/verifier hiện có.
- T1-T4 đạt; T3 có 1.200 trường hợp mock ngẫu nhiên, 0 mismatch text/finish/parser.
- T5 audit 136 completion cũ: roundtrip text 136/136, token count literal 59/136,
  sau giả định EOS 122/136; vẫn mismatch 14. Phiên bản backend lịch sử không được
  ghi. Vì vậy không dựng lại IDs rồi gọi đó là IDs gốc, và không ghép A/F cũ với
  CONT mới để tạo contrast M/D. Arm cũ giữ cap gốc.

Mã chính: `experiments/cot_restart_replay.py`, các collector pilot/addendum,
`scripts/audit_cot_restart_tokens.py`. Bằng chứng:
`audit/cot_restart_replay_readiness_20261013/`.

## 3. Draw đầu: đã chạy model thật, audit/replay xong

Người dùng chọn F q_requested=0.50 trong menu prefix được snap theo câu, rồi
duyệt batch 36 calls. A không giữ rationale; F giữ prefix đó; CONT giữ toàn bộ
rationale cũ trước answer block. Dùng cùng 12 câu development đã lộ và base
traces cố định, không chọn subset theo đúng/sai và không sinh lại base.

Model: `mlx-community/Qwen3.5-4B-MLX-4bit`, revision
`32f3e8ecf65426fc3306969496342d504bfa13f3`; temp=0.6, top_p=0.95,
native thinking tắt, cache mới, không stop strings/logits processors/draft.

M: W=2048, L_i=2048-P_i_CONT cho mọi arm của câu đó.
D: T*=2560, w=0/1; cap=T*-base_completion-w*(base_prompt+arm_prompt).
Mỗi call thu H=max(L_i+8, D_w0, D_w1), nên cả CONT cũng có đủ trace +/-8.

36/36 real calls hoàn tất, 0 failed inference. Dùng 19.715 completion tokens
gồm EOS và 14.125 prompt tokens, tổng 33.840 token mới; active collection
khoảng 32 phút. Đây không phải online latency tại các cap M/D đã replay.

| Điểm | A | F | CONT |
| --- | ---: | ---: | ---: |
| M-8 / M / M+8 | 6/12 | 9/12 | 8/12 |
| D(w=0) | 7/12 | 9/12 | 8/12 |
| D(w=1) | 7/12 | 9/12 | 7/12 |

Tại M, paired F-A: b=5, c=2, Delta=+25,0 pp; nominal Tango CI 95%
[-18,8; +59,7] pp. F-CONT: +8,3 pp, CI [-24,4; +39,7]. CONT-A: +16,7 pp,
CI [-18,9; +48,5]. Mọi CI của M/D đều chứa 0, không có superiority claim.
CI là mô tả/asymptotic và chưa hiệu chỉnh đa so sánh, n=12.

Rescue/harm so với historical base (5 sai, 7 đúng), tại M:
A cứu 2/5, hại 3/7; F cứu 3/5, hại 1/7; CONT cứu 1/5, hại 0/7.
Đây là chẩn đoán subset theo base outcome, không phải treatment effect quần thể.
CP intervals và case review đã lưu. F's harm là phép nhân cuối sai 90;
CONT's sole rescue là G24 base bị length, cũng được cả A và F cứu. Chưa tách
được cơ chế retained prefix, format repair hay loại bỏ erroneous tail.

Artifacts draw đầu:

- `audit/cot_restart_matched_plan_20261013/` — plan đã duyệt.
- `audit/cot_restart_matched_real_20261013/` — raw manifest/journal/records.
- `audit/cot_restart_matched_analysis_20261013/` — M/D, per-cap rows, hashes.
- `audit/cot_restart_matched_diagnostics_20261013/` — rescue/harm CP và observables.
- `audit/cot_restart_matched_case_review_20261013.md` — kiểm tra 3 rescues/1 harm F.
- `audit/cot_restart_matched_review_20261013.json` — tổng kiểm chứng.

## 4. Draw thứ hai: đã bàn giao, đang thu real outputs

Đã chuẩn bị replication với **call/draw index 1**, giữ base seed 42, q=0.50,
model, prompt text/IDs/order, sampling và tất cả caps. Chỉ seed/draw provenance
đổi; cả 72 seed của hai draw khác nhau. Không sửa frozen generation sources;
helper chuẩn bị/protocol mới được hash riêng trong plan.

Plan: `audit/cot_restart_replication_plan_20261013/`.
Plan SHA-256:
`132f850d304de9e7026a5cc42ac65691ac3249e3d4eb4315f9c1a28436925bd6`.
58 tests qua, mock đủ 36 calls/180 replay cells. Completed resume giữ nguyên raw
records/journal; collector hiện tại cập nhật timestamp trong manifest khi resume.

Ngân sách: 36 attempted calls, 72.996 completion tokens gồm EOS, 14.125 prompt
tokens, tổng trần 87.121 tokens. Refuse new calls sau tám active hours; thất bại
giữ reservation, không tự thêm retry vượt trần. User đã nói cho Antigravity chạy;
handoff nằm ở `audit/cot_restart_replication_plan_20261013/handoff_antigravity.md`.

Trạng thái trực tiếp tại snapshot 15:43:

- `audit/cot_restart_replication_real_20261013/manifest.json`: `running`;
  bắt đầu 15:32 giờ Việt Nam.
- Journal có **21 completed / 22 started calls**; call đang chờ là
  `order_0027_en_orig`, arm A. Đã kiểm tra hash chain 43 entries và prompt/seed/
  cap/call_index của tất cả completed entries so với plan.
- Completed calls đã ghi 6.071 completion tokens và 13.144 prompt+completion
  tokens. Chưa gồm token của call đang thu, nên không gọi đó là final cost.
- Chưa có `records.json` hoàn tất hay thư mục analysis draw thứ hai.
- `failed_attempts=1` trong manifest này là started-minus-completed, đi kèm
  in_flight_call. Khi status còn running, nó **chưa chứng minh inference failed**.
- Hai plan, nguồn generator/runtime và hash output analysis draw đầu vẫn đạt.
  Lần review này không khởi chạy thêm model hoặc can thiệp collector đang thu.

Snapshot máy đọc được: `audit/cot_restart_claude_status_20261013.json`.
Nếu trạng thái mới hơn khác, lấy journal/manifest mới làm căn cứ.

## 5. Việc còn lại

Để collector hiện tại hoàn tất; không chạy song song hoặc tự sửa generation
sources/plan trong lúc đang thu. Sau completion, dùng lệnh offline audit và
rescue diagnostics đã ghi trong handoff Antigravity. Giữ failed/partial artifacts
nếu có lỗi và kiểm tra journal trước mọi resume, không tự tái cấp 36 calls.

Sau hai draw đầy đủ, report từng draw riêng, rồi average correctness/tokens
trong từng câu trước paired bootstrap original groups: 2.000 samples,
bootstrap seed 20261013, giữ mọi arm/câu/draw trong group. Vẫn **12 câu/12 groups**,
không phải 24 câu độc lập hay 36 quan sát từ ba cap. Không dùng binary Tango cho
fractional seed means. Aggregator riêng cho schema matched này chưa được xây
và chưa chạy; không mặc định aggregate main-study nhận được các artifacts đó.

D vẫn có thành phần historical base counts chưa xác minh EOS. Token counts
không phải FLOPs/billing/full inference cost, và replay time không phải online
latency. Dataset đã lộ, q không phải q tối ưu, chưa có learned locator/probe,
formal GO/NO-GO, held-out result hoặc Stage 0 pass. Nghiên cứu lớn hơn cần fresh
reviewed groups, preregistered decision/cost scope và power assessment riêng.

Không push/pull/reset/force Git nếu user không yêu cầu trong cùng message.
Không đụng các thay đổi RAT/DocAI ngoài scope. Nếu sửa harness/threshold, chạy
required research suite trong AGENTS.md. Các lệnh collection dùng entry point
`python3.12 -m experiments.research_study`; exact interpreter/runtime ở handoff.
