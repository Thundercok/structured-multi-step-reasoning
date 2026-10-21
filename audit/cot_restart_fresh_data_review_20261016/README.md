# Việc làm ngay: duyệt dữ liệu cho đợt CoT restart mới

Đã xuất **71 câu ứng viên / 70 nhóm**, chưa có câu nào
được gói này chứng nhận đã qua human review; model calls mới = 0.

1. Gửi bản sao [gói câu hỏi và gold](review_packet.md) cho reviewer độc lập để
   ghi lập luận, nguồn, lịch sử sử dụng và quyết định từng câu; giữ nguyên bản xuất này.
2. Đối chiếu hồ sơ review với [frame nhóm](candidate_frame.json), ghi mọi sửa/loại
   trước khi xem model output; nếu sửa nội dung thì tạo release mới cùng hash mới.
3. Dùng frame đã duyệt để chốt protocol và power cho F−CONT, F−O, rồi mới freeze
   nguồn/code/luật quyết định và chuẩn bị ngân sách chạy cụ thể.

**Đã kiểm bằng CPU:** hash bundle gốc, nguyên trạng query/gold/metadata so với
nguồn, identity chuẩn, nhóm không qua split, và trùng canonical với tuning pool,
pilot CoT restart 12 câu, hai pilot ordering 2/8 câu; các đối chiếu này có 0 nhóm trùng.
Đây là kiểm trùng có phạm vi, chưa xác minh toàn bộ lịch sử chạy hoặc pretraining.
Mã identity hiện có thêm hỗ trợ clue gap so với bản tạo bundle; đã đối chiếu
diff và tính lại identity trên toàn bộ 179 câu, giữ đúng group ID đã lưu.
Nội dung câu/gold được xuất bằng chương trình; chưa được agent duyệt ngữ nghĩa
trong bước này. Mức generator không phải độ khó thực nghiệm đã được kiểm chứng.

**Thiết kế đề xuất:** giữ q yêu cầu = 0,50; một draw chính mỗi câu cho F và CONT,
O là đáp án base mới dùng chung; A là ablation phụ. Mỗi nhóm tối đa một câu trong
phân tích chính, đại diện đề xuất chọn bằng item ID trước mọi kết quả. Mọi base
mới phải lưu prompt/completion IDs và EOS ngay từ đầu. Không dùng lại số token
base lịch sử chưa xác minh. Báo riêng prompt, completion và toàn đường suy luận;
latency triển khai cần đo online riêng.

**Phần còn phải làm trước chạy thật:** runner hiện tại khóa đúng 12 câu lịch sử
(`experiments/cot_restart_matched.py`); cần adapter thu base và arm cho frame mới,
được kiểm bằng mock qua entry point `python -m experiments.research_study`.
Cần chốt cap/cost scope, δ_prac (và λ nếu dùng utility), n/power và code quyết định;
70 nhóm ở đây là lượng ứng viên hiện có, không phải cỡ mẫu đã chứng minh đủ power.
Chọn m=1 cho thống kê chính; các mở rộng cluster/betting giữ ở nhánh phương pháp
synthetic. Đây là đề xuất, chưa là preregistration hoặc phê duyệt inference.

Gói này không thay đổi split, dữ liệu nguồn, runner, kế hoạch đã hash hoặc Stage 0.
Để tái lập sang thư mục mới:

```bash
python3.12 audit/cot_restart_fresh_data_review_20261016/prepare_review.py --output /tmp/cot_restart_review_copy
```
