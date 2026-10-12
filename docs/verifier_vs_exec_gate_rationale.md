# Verifier gate, exec-only gate và symbolic baseline

Status: DEVELOPMENT RATIONALE, NOT A CONFIRMATORY RESULT. Corrected 2026-10-08.

Luận điểm hiện tại là một câu hỏi thực nghiệm: **kiểm tra witness có cải thiện
độ đúng của đáp án cuối cùng, với chi phí nào, so với chỉ kiểm tra execution?**
Tên và tính mới của bài báo vẫn là đề xuất, chưa phải đóng góp đã chứng minh.

## 1. Giới hạn quan trọng nhất: verifier và solver dùng chung parser

`solve_order_query` là baseline triển khai được, chỉ nhận query, không nhận gold.
Nó dùng cùng parser template nghiêm ngặt với verifier. Kết quả development
31/31 được ghi trong [development audit](../audit/ordering_development_audit_20261008.md).
Không gọi baseline này là oracle hoặc upper bound: nó có thể abstain trên câu
không được parser hỗ trợ, mâu thuẫn hoặc đáp án tại vị trí hỏi không duy nhất.

Ngoài grammar hỗ trợ, **cả solver lẫn verifier đều bị giới hạn**. Chưa có thí nghiệm
ngôn ngữ mở để định lượng parse rate hay chứng minh verifier tổng quát hơn.
Zero model tokens không có nghĩa zero compute: phải báo cáo thời gian CPU riêng.

Verifier mặc định `generic_with_uniqueness_check` còn chạy exact solver để kiểm
tra người ở vị trí hỏi có duy nhất hay không. Nó không phải cổng witness-only rẻ.
Nếu solver thống trị trên release được review, phải trình bày kết quả đó; không
loại baseline để làm cascade trông có lợi hơn.

## 2. Hai gate kiểm tra hai hợp đồng khác nhau

W-certificate nhận kết quả certificate PAL khi execution thành công, output
khác rỗng/`None`, và generation không bị cắt cụt. Nó không kiểm tính đúng của
clues. Một chương trình chạy được vẫn có thể trả đáp án sai.

Verified-certificate kiểm actual execution payload: đủ `order`/`answer`, hoán vị
runner hợp lệ, tất cả clues đã parse, đáp án khớp vị trí hỏi, và tính duy nhất
trong mode hiện tại. Unsupported/invalid/runtime-failed/truncated thì escalation.
Sự bảo đảm này phụ thuộc vào parser, verifier và contract; không phải an toàn
tuyệt đối trên ngôn ngữ mở. Python execution helper không phải security boundary.

Để cô lập tác động của gate, W-certificate và Verified-certificate phải dùng
**cùng một PAL output và cùng fallback**. W-answer thay đổi cả prompt/output
contract, nên là một so sánh combined intervention riêng.

## 3. Hai item được báo trong chat: chưa có raw pilot để xác minh

Thư mục real pilot được nhắc tới (`audit/order_certificate_pilot_dev8_20261008`)
không có trong workspace tại lần kiểm tra này. Các số dưới đây chỉ là
**reported, unverified development telemetry**, không phải measured artifacts
đã review. Không dựng lại certificate hay gán nguyên nhân phần cứng từ stdout.

| Item | PAL answer/gold theo log | Gate theo log | PAL tokens | Fallback tokens | Verified path tokens |
| --- | --- | --- | ---: | ---: | ---: |
| `order_0000_en_orig` | Carol / Carol | VALID | 318 | 3,741 | 318 |
| `order_0001_en_orig` | Frank / Frank | INVALID | 373 | 4,015 | 4,388 |

Nếu các số và fallback rỗng trong log chính xác:

- Item 2 không phải incorrect-answer false accept của W: Frank khớp gold.
  Witness có thể invalid dù answer đúng. Reject đó đúng theo certificate
  contract nhưng là false reject theo **độ đúng answer**; fallback rỗng làm harm.
- Verified tổng chi phí là `318 + 373 + 4,015 = 4,706`, so với fixed candidate
  `3,741 + 4,015 = 7,756`. Ratio là **0.607**, không phải 0.088 hay giảm 91%.
- Verified đúng 1/2; W-certificate đúng 2/2; fixed candidate đúng 0/2 theo log.
  Đây là phép tính điều kiện trên hai item đã báo, không phải estimate có thể
  khái quát hay bằng chứng pass một decision gate.

## 4. Những gì phải đo tiếp

Tách rõ certificate validity, first-stage answer correctness và final policy
accuracy. Báo false accept/reject theo answer, rescue/harm, abstention và chi phí
tất cả stages kể cả fallback sai/cắt cụt. Không dùng correctness của fallback
để gán nhãn confusion cho first-stage gate.

Development collector đã có regression tests và mock artifacts; mock dùng
fixture biết gold và token giả, chỉ kiểm phần mềm. Chưa có raw real pilot được
xác minh từ collector đã sửa. Xem [protocol](order_certificate_study_protocol.md)
và [draft addendum](../prereg/decision_rule_verified_pal_order_v2.md).

Chưa đủ bằng chứng để claim Pareto superiority, loại bỏ mọi silent false accept,
độ an toàn tối đa, power 80% hoặc lợi ích confirmatory. Bước tiếp theo là review
adapter/token accounting và một pilot development có raw artifacts; chỉ sau
đó mới chốt protocol, statistical method và các gate liên quan.
