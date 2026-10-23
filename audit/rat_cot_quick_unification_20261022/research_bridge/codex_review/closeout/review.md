# Nghiệm thu bridge trong phạm vi đã review — 2026-10-23

**R1/R2/R3 CLOSED trong phạm vi software contracts đã giao.** Reviewer chạy
độc lập **79 passed in 11.04s**, không failure/error/skip. Source hashes ổn
định từ đầu đến cuối kiểm tra. Không gọi model thật, không sửa production,
không dùng kết quả này để approve policy/dữ liệu/model hoặc mở campaign.

| Hạng mục | Kết quả độc lập |
| --- | --- |
| Positive approved-metadata unit control | Artifact/bundle `l2_unit`, route CoT như harness |
| Caller cố đổi sang raw | Reject bằng ValueError |
| Bundle khai raw, artifact khai unit | Reject bằng BundleValidationError |
| Bundle thiếu khai báo, artifact khai unit | Reject bằng BundleValidationError |
| Fixture gold/correct isolation | Không còn hai loại label trong execution double |
| Regression runtime/bundle/calibration/harness | 79 pass |
| XML Anti online / online+research | 29 / 58 cases đúng breakdown, không failure/error |

R1 được đóng cho normalization profile có khai báo, authoritative-artifact
binding và các conflict paths đã tái hiện. Các positive và raw legacy controls
của module online vẫn pass. Không diễn giải thành chứng minh mọi bundle hoặc
mọi execution state của toàn ứng dụng đều được kiểm.

R2 đóng trong phạm vi fixture: whitelist execution fields được giữ, labels
không có trong trạng thái backend double; không suy chất lượng model.

R3 đóng cho việc làm rõ mapping và link log mới: giữ XML22 như historical,
XML29 và XML58 mô tả các suites mới tương ứng. UI55 vẫn Anti-reported, reviewer
không chạy lại UI trong nghiệm thu này. Tổng 113 của các nhóm được báo không
phải một fresh full-repo run do reviewer thực hiện.

`binding_probe.json/.txt` là lần chạy mới của cùng source probe, với `OUT` được
chuyển sang folder closeout để không ghi vào kết quả nhận bàn giao. Ba conflict
cases trả rejected=true; positive control thành công. Đây là authored fixture
mô phỏng approved metadata, không phải một phê duyệt policy thật.

`source_start.json` và `checks.json` lưu fingerprints/breakdown; `regression.txt`
và `regression.xml` là raw run mới. Files runtime, bundle và online tests khớp
hash trong probe và đầu/cuối lần kiểm.

Lệnh suite:

```bash
.venv/bin/python -m pytest tests/test_online_reasoning.py tests/test_policy_bundle.py tests/test_policy_calibration_binding.py tests/test_research_study.py test_optimal_stopping.py test_entry_predictor.py -q
```

Đường đi tiếp là review development data và chốt một phép đo có giới hạn,
dùng [gói checker đã chuẩn bị](../../../independent_review/stopping_signals/README.md).
Giữ human/source review, Stage 0 và model budget theo phạm vi hiện hành;
software acceptance này không tự mở quyền inference hoặc xác nhận lợi ích
của checker-gated stopping. Không có native UI/model-quality acceptance mới.
