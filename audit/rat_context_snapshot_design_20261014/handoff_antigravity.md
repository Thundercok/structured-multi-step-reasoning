# Handoff B — design đã review, chờ chốt phase triển khai

Đọc [ADR-004](../../docs/adr-004-rat-context-snapshot.md),
[schema/examples](README.md), [provenance](provenance.json) và
[review handoff A](../rat_context_handoff_review_20261014/review.md).
Đây là **Proposed**, chưa authorise implementation B thay người dùng. User
đã yêu cầu duyệt từng phase, core trước và UI riêng. Brief chỉ chuẩn bị local;
Codex không gửi bằng tool sang Anti và chưa sửa runtime trong lượt này.

## Sửa cách diễn đạt audit A

Giữ raw A và report Codex hiện có, không overwrite. Dùng đúng units/aggregation:
12 cases,20 runtime turns,41 scripted port calls (34actor/7planner).20 turns
không chứng minh20 registry initializations độc lập.58,72% là mean per-call
tools share;53,26% là ratio sums; range toàn actor25,24–75,06%. C01 request
cuối34.599 canonical chars; bảng pasted12.044→21.441 không tái lập từ raw.
Registry/prefix stable trong captures không là cache savings. Historical
server-time shares không chứng minh tools schema gây latency. A chưa đo token,
server duration, model quality hay UI.

## Khi user chốt B, implementation scope

1. Thêm một **headless projection compiler**, dự kiến
   `rat/engine/context_snapshot.py`. Nhận copied canonical inputs: boundary
   identity/generation, request/history refs, proposal, current contract,
   journal, artifact/note versions/cursor, pending input và native trajectory.
   Không import Qt/index personal files, không tạo context store/controller mới.
2. Build một entity body cho mỗi typed identity/revision. Registered projector
   metadata quyết định payload slots; raw fallback cho operation chưa hỗ trợ.
   Không if/else theo text query, calendar/natal/DSA intent hay fixture wording.
   Giữ canonical raw records trong stores/journal, metadata authority đúng issuer.
3. Reuse canonical contract JSON export/validation và completion matchers.
   Đưa actual obligations/freeze/errors/intent_coverage cho actor trước decision;
   planner mới giữ `not_declared`. Không tự bổ sung expected args/source/target
   hay infer constraints từ user text. Notes do model viết vẫn proposed.
4. Scoped receipts/proof state riêng với model proposal. Progress trước final
   là provisional; chưa response thì pending_response. Không thêm repair loop,
   extra required model call hay đổi budgets/controller/response formats.
5. Giữ current query một instruction message, history roles/order/window,
   static persona và runtime clock/member. Một versioned static protocol clause
   giải thích authority/refs. Snapshot là data; source/note/model text không vào
   system instructions. Native assistant/tool calls giữ name/IDs/order và native
   batching; tool result refs chỉ dùng khi body inline. Error/check feedback giữ
   scope/candidate hash. Finish-only tool availability giữ nguyên.
6. Full old/current note text và lossless fields phải inline. `inspect_artifact`
   chưa đọc notebook; không ID-only old notes, không thêm resolver trong B.
   Exact source quote có thể dùng ref cùng source/revision/field; khác authority
   thì giữ riêng. Literal expected values không tham chiếu mutable outputs.
7. Ref validator kiểm duplicates/cycles/pointers, namespace và native bindings.
   Decode `$value_ref` chỉ ở registered projection slots; raw user JSON có key
   này là data. Missing body có explicit unavailable reason; optional unmodeled
   data giữ raw. Mandatory control export failure phải explicit, không fallback
   context thiếu obligations. Không mới cap/summary/truncation.
8. Coherence: copy/stamp/cursor + selected membership/current revisions, bounded
   retry (tối đa2), không chỉ check artifact generation. Generation hiện chỉ đổi
   khi clear. Rebuild sau mutation/cancel; late results không authorize write
   qua guards hiện có. Không rollback committed effect khi context build lỗi.
9. Một compiler cho planner/actor/verified repair/finish, views theo phase thật.
   Với cùng scripted decisions, calls/effects/proofs/version/lifecycle không đổi.
   Raw A không có capture verified repair/finish channel đầy đủ; cần thêm fixtures
   cho B, không giả A đã cover chúng.

## Review gates sau code

- Preserve33 historical probes,227 selected regressions,32 boundary tests
  của packet core fix. Exact command ở
  [test_run.json](../rat_core_reconciliation_fix_20261013/test_run.json).
  Chạy với `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider` như packet.
- Adapt6 audit tests với versioned projection; không xóa scope/unit assertions
  chỉ để pass. Reuse capture client và blocked inference/network audit runner.
- Thêm meaningful fixtures: generic artifact và no-artifact operation result;
  note create/update/lookback/remove/restore; same wording different source/
  authority; literal expected args; invalid contract; missing body/raw fallback;
  forged `$value_ref` in raw data; old generation proof; concurrent note/artifact/
  cancel; native multi-tool pairs; repair candidate hash; finish-only no-tool.
- Core C01 phải thấy declared outcome IDs ở actor, provenance giữ lossless,
  revisions/links resolve. Không biến fulfillment of draft storage thành formal
  correctness of document prose. Giữ pending input/error/cancel boundary thật.
- Fresh audit B folder, start/end source hashes, raw before/after cùng fixtures/
  scripted decisions. Report payload chars/bytes theo components, ghi rõ added
  obligations/provenance. Không bắt every call nhỏ hơn baseline đang thiếu info.
  No token/latency/cache/model-quality claims từ JSON chars hoặc pass pytest.
- Handoff source diff, fixture evidence, native channel captures và test logs
  cho Codex review. Chưa UI redesign, default live model/planner change,
  C sorting/pruning, D one-call experiment, learned policy, DocAI hoặc Stage0.

## Design validation hiện có

[validation.json](validation.json) chỉ kiểm consistency của schema và authored
examples; không là regression log của production B. Primary example adapts
contract của A, expected_args/target_ref null. Stronger declared_args example
chỉ minh họa cách giữ literal values khi có declaration thật. Không copy
authored receipt/coherence/progress assertions vào runtime làm fake evidence.
