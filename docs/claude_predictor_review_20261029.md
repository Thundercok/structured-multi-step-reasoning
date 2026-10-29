# Review mã và dữ liệu Claude — 2026-10-29

## Kết luận

Path migration đã có trong repo tại `c7fb0ee0` và commit trước đó. Không chạy lại
script rename được dán: nó kỳ vọng đúng một occurrence cũ và sẽ refuse các file
đã sửa. Hai root paths trong `legacy_implementation()` của
`scripts/review_tuning_sweep.py` dùng `git show` ở pinned historical commit;
giữ nguyên, không đổi đồng loạt như gợi ý MANUAL của script.

Đánh giá: **cần sửa evaluator trước khi dùng để báo cáo kết quả nghiên cứu**.
Kết quả synthetic có ích như chẩn đoán; không xác nhận cải thiện model thật,
không đổi Stage 0 và không đủ để chốt PCA16 hay PCA32.

## Dữ liệu đã đọc

Nguồn là hai attachment người dùng cung cấp: JSON 120 records và source
`entry_eval.py`. Raw copies và SHA256 được giữ tại
`audit/claude_predictor_review_20261029/`; evaluator lưu dạng `.py.txt`, chưa
đưa thành runnable research entry point. Synthetic generator và telemetry
script được dán trong tin nhắn; không chạy các script đó.

JSON đủ 6 seeds × 2 N (90, 180) × 2 SNR (0.12, 0.30) × 5 configurations,
không trùng/mất ô. Metric hữu hạn; `regret = oracle - util` và
`gain_vs_fixed = util - best_fixed` khớp các dòng đã cung cấp. Không rerun training.

| Config | Mean utility | Mean log-loss | Mean secs theo dữ liệu cung cấp |
| --- | ---: | ---: | ---: |
| old | 0.581590 | 1.195077 | 0.282890 |
| scaler_only | 0.626619 | 0.566053 | 12.550545 |
| pca16 | 0.649087 | 0.543857 | 14.790738 |
| pca32 | 0.645372 | 0.548250 | 16.983577 |
| pca64 | 0.636316 | 0.560024 | 19.658976 |

Đây là trung bình mô tả có trọng số bằng nhau trên grid synthetic. Utility dùng
true synthetic probabilities (`tp`) và lambda 0.1 trong generator, không phải
observed accuracy của model. Không so trực tiếp với demo evaluator có lambda
mặc định 0.02. Các timing không phải benchmark trên máy hiện tại hay latency RAT.

PCA32 cao hơn old trong 24/24 cells, mean difference +0.063782; cao hơn
scaler_only trong 22/24 cells, +0.018753. PCA16 cao hơn PCA32 trong 18/24 cells,
+0.003715. Không dùng 24 cells như 24 independent replications: cùng seed được
tái sử dụng qua N/SNR, và cả grid đều dùng cùng thiết kế synthetic. Không suy ra
statistical significance từ số ô thắng. Source `/tmp/entry_predictor.py`, package
versions và environment của các lượt gốc chưa có fingerprint trong JSON.

## Evaluator cần sửa gì

1. **Base-rate reference không out-of-fold.** Biến `base` dùng mean accuracy của
   toàn N, bao gồm các nhãn của validation fold. Fit base rates trên mỗi outer
   training fold rồi dự đoán fold còn lại, giống predictor. Không dùng reference
   hiện tại để khẳng định held-out predictor kém hơn bỏ qua query.
2. **Thiếu group/split/provenance.** NPZ chỉ có embed/complexity/accuracy/cost;
   random row folds không bảo vệ paraphrase/original groups hoặc lặp generation
   seeds. Cần group IDs và metadata về source, splits, label construction,
   token scope, backend/prompt và hashes. Cả inner CV tuning và outer evaluation
   phải tôn trọng groups nếu dữ liệu có groups. Không trộn held-out test vào
   development CV hoặc chọn PCA sau khi xem test.
3. **LADDER leakage phụ thuộc nơi tạo dữ liệu.** Supported harness
   `experiments/research_study.py:fit_policies` fit stopping trên calibration rồi
   tạo router targets trên train; không phải shared-sample construction như
   warning khẳng định. Legacy `pipeline.py:fit_full_policy` dùng cùng train cho
   stopping và entry targets. NPZ không phân biệt được hai nguồn này. Nếu đánh
   giá end-to-end bằng outer CV, không fit stopping policy bằng nhãn outer-test;
   cần independent calibration hoặc fit/cross-fit đúng bên trong training fold.
   Không tự thay thuật toán của supported harness vì warning chung trong script.
4. **CI chưa bao quát uncertainty của fitting/CV.** Resample row utilities đã
   tính sẵn không refit model và không xử lý shared-training-fold dependence.
   Đặt tên là exploratory conditional intervals; dùng đúng independent group
   unit và protocol phù hợp trước khi khẳng định significance.
5. **Comparator trong hindsight chỉ mô tả.** `bf` được chọn bằng outcomes toàn
   bộ evaluation data. Có thể giữ làm hindsight reference đã ghi nhãn, nhưng
   không coi là deployable baseline được chọn trước. Paired bootstrap hiện giữ
   cố định lựa chọn đó; không bao quát uncertainty từ selection. Nếu chọn cấu
   hình bằng kết quả CV, cần evaluation độc lập sau selection.
6. **Kết quả giữa repeats chưa nhất quán.** Utility/accuracy/cost lấy trung bình
   qua repeats, log-loss và route mix chỉ dùng repeat 0. Ghi nhãn rõ hoặc báo
   per-repeat metrics rồi aggregate nhất quán; log-loss của averaged probability
   là endpoint khác mean per-repeat log-loss. JSON hiện không lưu đầy đủ fold
   indices, OOF predictions, provenance hoặc CI cho accuracy/cost.
7. **Fail-closed inputs/output.** Kiểm tra finiteness, binary labels, nonnegative
   costs, matching dimensions, valid configs, 2<=folds<=N và repeats>=1 bằng
   exceptions rõ ràng. `--configs old` hiện không chọn được `main`.
   `--demo` phải ghi `synthetic` vào output JSON; không chỉ ghi ở help. Chặn
   overwrite và đường dẫn output trùng input. Không sửa collector để chạy thêm
   model calls chỉ nhằm tạo NPZ.

## Script telemetry cần sửa trước khi chạy thật

- `prod(shape)>1000` không chứng minh full vocabulary. So với output vocabulary
  dimension thực của model/head và xác nhận một next-token distribution; không
  chỉ so với tokenizer length vì có thể có padded/added tokens.
- Reject raw stream rỗng; hiện vòng A có thể không chạy check nào.
- Kiểm tra missing/nonfinite signals trước khi format `:.3f`; không để check
  script crash mà thiếu failure report. Validate nonfinite logprobs, sampled
  token index, coverage và kết thúc stream.
- Dùng constructor `strict_telemetry=True` hiện đã có. Ghi exact local snapshot,
  package versions, source hashes, seed/decoding, prompt/generated tokens và
  failure artifacts. Confidence >0 không chứng minh calibrated confidence hoặc
  câu trả lời đúng.
- Không mặc định tải model từ repo alias `main`. Chạy local reviewed snapshot,
  giới hạn số calls/tokens và chỉ chạy khi user yêu cầu rõ. Nếu snapshot thiếu,
  báo thiếu thay vì tự download.

Không chạy tests, training, model inference hoặc download trong review này.
Không sửa frozen manifests, active model behavior, Lite hay production defaults.
Phần tiếp theo nên là evaluator offline có provenance/group contracts dùng lại
recorded research outputs, thay vì đưa các script chưa sửa vào campaign thật.
