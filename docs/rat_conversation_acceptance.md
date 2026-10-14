# RAT: một công việc đi xuyên cuộc trò chuyện

**Ngày:** 2026-10-13, Asia/Saigon.
**Trạng thái:** Bộ mẫu thiết kế đã chuẩn bị; chưa có run model/native cho bộ này.
**Vai trò:** Codex chuẩn bị trải nghiệm và tiêu chí; Anti sửa core. UI/copy còn là
đề xuất để duyệt sau core. Nội dung dưới là hội thoại minh họa do người viết soạn,
không phải transcript RAT đã chạy.

## Vấn đề

Người dùng muốn Chuột nhận việc, dùng tiếp ngữ cảnh và trả kết quả trong một chat.
Các kiểm tra contract giúp giữ dữ liệu đúng nhưng chưa chứng minh trải nghiệm đó
đáng dùng: trả lời đúng nguồn, hiểu câu hỏi tiếp và thực hiện phần ghi/sửa đã nhờ.
Ta cần một luồng có thể nghiệm thu xuyên suốt, với dữ kiện và thất bại quan sát được.

Ví dụ DSA phục vụ luồng chung; cùng cách làm áp dụng cho tài liệu, lịch hoặc kết
quả khác. Không tạo chế độ học DSA. Kế hoạch này tiếp nối
[ví dụ DSA](rat_conversation_dsa_example_plan.md) và
[ADR-003](adr-003-rat-completion-reconciliation.md).

## Mục tiêu

1. Đi qua tìm → đọc → giải thích → ghi → sửa → xem bản trước → hỏi tiếp trên cùng
   công việc, với nguồn và đối tượng đúng ở cả bảy lượt.
2. Mọi câu xác nhận lưu/sửa có event thật; 0 xác nhận giả khi lưu thất bại.
3. Sửa đúng một note/revision; 0 thay đổi ngoài yêu cầu, 0 sửa ngược lịch sử.
4. Đổi full/compact giữ chat, draft và dữ liệu; 0 executions phát sinh chỉ vì toggle.
5. Chuột có giọng thân thiện, vui nhẹ; tương tác trực tiếp với nhân vật chỉ emote.

Các mục này là điều kiện demo cần đạt, chưa là metric model đã đo. Tỷ lệ hoàn
thành/latency tổng quát cần baseline riêng, không suy từ bảy lượt cùng conversation.

## Phạm vi

Bộ chuẩn bị gồm [scenarios.json](../data/rat_conversation_acceptance_v1/scenarios.json),
ba nguồn Markdown gốc do người viết soạn, sáu tình huống/15 lượt user và ba
paraphrases development. Runtime không nạp đáp án mẫu từ bộ này.

Giữ một composer; kết quả và notes thuộc lượt đang làm. Giữ Chuột bên trái,
canvas trong suốt và các emote đã chốt. Các source ngắn là fixtures, source dài
giúp chỉ ra giới hạn; chưa index vào personal DB hoặc mở app thật.

Không đổi default model, thêm tools/route keyword, dựng khóa học, panel notes,
toolbar gợi ý hoặc memory qua restart. Không tích hợp DocAI. Bộ này độc lập
pipeline NCKH và không đổi Stage0/splits/publication claims; toàn bộ examples đã
lộ để thiết kế, không là held-out data.

## Câu chuyện người dùng

- Là người đang đọc một tài liệu khó, tôi muốn hỏi “bước đó” để tiếp tục đúng
  ví dụ mà không nhập lại dữ kiện.
- Tôi muốn cất ba ý rồi sửa một ý; bản cũ vẫn xem được và ghi rõ đã được thay.
- Khi việc ghi thất bại hoặc tôi dừng, tôi muốn biết phần nào đã làm và giữ được
  kết quả trước đó để tiếp tục.
- Khi có hai ghi chú phù hợp, tôi muốn Chuột hỏi đúng đối tượng cần sửa một lần.

## Hội thoại chính

Nguồn là tài liệu giả [binary-search-basics.md](../data/rat_conversation_acceptance_v1/sources/binary-search-basics.md).
Mảng [1,4,7,9,12,16,20], chỉ số từ0, khoảng inclusive. Tìm16 xét mid3 rồi mid5,
trả index5; tìm9 dừng ở mid3 trong lần xét đầu.

Các câu của Chuột dưới đây minh họa nhịp nói, không bắt model chép nguyên văn.

| Lượt | Người dùng | Chuột và kết quả trong chat |
| --- | --- | --- |
| 1 | “Tìm tài liệu binary search ngắn giúp tôi.” | Trả hai nguồn có đường dẫn thật trong fixture; nguồn đầu là bản ngắn. Dòng nguồn cho biết mới tìm thấy, chưa đọc toàn nội dung. |
| 2 | “Đọc tài liệu đầu rồi giải thích cách tìm16 bằng ví dụ trong đó. Đừng đưa code vội.” | “Xét giữa mảng trước: index3 có giá trị9, nhỏ hơn16 nên giữ đoạn từ index4. Lần tiếp theo, index5 có giá trị16. Tìm được ở index5, sau hai lần xét.” |
| 3 | “Sao phải cộng1, giữ nguyên mid được không?” | “Phần tử giữa là9 và đã nhỏ hơn16. Nó đã được xét nên không còn là ứng viên; đoạn mới bắt đầu ngay sau nó. Giữ mid có thể khiến đoạn tìm kiếm không thu nhỏ.” |
| 4 | “Ghi lại ba ý quan trọng, ngắn thôi.” | Sau event lưu: “Đã ghi bản nháp ba ý bên dưới.” Ba dòng note nhẹ nằm ngay dưới lượt này. Có thể thêm một câu đùa ngắn khi phù hợp. |
| 5 | “Ý thứ hai dài quá, sửa ngắn lại.” | Sau event sửa: “Đã rút gọn ý thứ hai: ‘Xét giữa, rồi giữ nửa có thể chứa đích.’” Note revision2 thuộc lượt sửa; note revision1 ở lượt4 dẫn sang bản mới. |
| 6 | “Cho tôi xem bản trước.” | Trả nội dung revision1 đã lưu và link tới lượt4; active revision2 giữ nguyên. Không viết lại một bản cũ theo trí nhớ. |
| 7 | “Tìm9 trên mảng đó thì sao?” | “Gặp ngay ở lần xét đầu: mid=3, giá trị cũng là9. Dừng tại đây, kết quả là index3.” Không tự sửa note vì user chưa nhờ lưu. |

Bản nháp note mẫu:

1. Mảng cần được sắp xếp trước khi tìm.
2. Mỗi bước xét phần tử giữa rồi loại nửa không thể chứa đích; phần tử giữa đã
   xét cũng được loại.
3. Gặp đúng đích thì dừng; đoạn tìm kiếm rỗng thì không tìm thấy.

Bản sửa chỉ thay ý2 bằng “Xét giữa, rồi giữ nửa có thể chứa đích.”
Nội dung model thực tế có thể khác; bài chấm lookback phải so với revision1
thật trong run đó, không so với wording mẫu này.

## Khi công việc không chạy suôn sẻ

| Tình huống | Điều Chuột cần làm |
| --- | --- |
| Lưu note thất bại | Giữ ba ý vừa viết, nói “Phần ghi chú chưa lưu được.” Lượt “thử ghi lại” dùng nguồn cũ và execution mới, không sửa một note giả đã lưu. |
| Hai note, user nói “rút gọn ghi chú” | Hỏi một câu có hai đối tượng thật: ví dụ mảng hay đệ quy. Chưa sửa trước khi user chọn; không hỏi lại dữ liệu đã có. |
| User dừng sau khi đã đọc nhưng trước commit sửa note | Giữ kết quả đọc và bản ngắn đã commit. Old execution cancelled; callback muộn bị chặn. Hỏi tiếp tìm9 dùng mảng cũ, không tự rollback note. |
| File tìm thấy nhưng đọc không được | Giữ nguồn đã tìm, nói chưa đọc được nội dung. Không kể ví dụ “trong file” dựa vào tên/snippet rồi gọi là đã đọc. |
| File dài, chỉ đọc được một phần hoặc nguồn note vượt giới hạn | Nêu phạm vi đã đọc và phần chưa lưu được; không tự cắt nguồn ngầm để báo hoàn tất toàn tài liệu. Ghi capability gap riêng với lỗi suy luận model. |

Các fault được setup ở fixture/adapter của harness phát triển, không nằm trong
runtime policy và không kích hoạt theo câu user. Không tiêm model decisions vào
live evaluation rồi chấm đó là model chọn đúng.

## Yêu cầu và điều kiện nghiệm thu

### P0 — Luồng và sự trung thực

| Yêu cầu | Given/When/Then |
| --- | --- |
| Tìm khác đọc | Khi mới có search hit, chỉ xác nhận tìm thấy; claim về toàn nội dung cần successful read đúng file. |
| Tham chiếu đúng | Sau lượt2, “bước đó”/“mảng đó” dùng đúng array/step/source. Khi target unique, không hỏi nhập lại; khi hai target thật sự mơ hồ, hỏi trước mutation. |
| Ghi/sửa theo lượt | Lượt4 tạo một draft note có nguồn; lượt5 dùng đúng ID/revision trước, giữ hai ý còn lại và tạo revision mới. |
| Proposed khác confirmed | Model paraphrase từ tài liệu giữ proposed/nháp nếu chưa có checker phù hợp hoặc user xác nhận. Lưu draft có thể thỏa nghĩa vụ “ghi bản nháp”; không gọi nó là nội dung đã kiểm chứng. |
| History bất biến | Lượt6 xem bản thực đã lưu, không mutation. Notes thay thế giữ owner/source/proof cũ và link mới. |
| Partial/cancel | Thiếu event không được xác nhận lưu. Cancel giữ committed effects, chặn old execution và cho phép tiếp tục ở execution mới. |
| Một bề mặt | Full/compact dùng cùng composer/context; toggle không gọi model, không xóa draft. Click Chuột chỉ emote, không mở notes/trace, scroll hay đổi focus/data. |
| Claims có phạm vi | DSA prose được review ngữ nghĩa bằng người chấm; PASS số học hay source-copy không tự chứng minh algorithm/workflow/intent đúng. |

### P1 — Cách trình bày và personality

Kết quả hữu ích xuất hiện trước phần giải thích dài. Source link gọn; notes là
dòng chữ nhẹ và chỉ thành edit frame khi user sửa. Bản cũ có nhãn đã thay và
link tới bản mới. Trace giải thích các việc đã quan sát: nguồn nào đọc, dữ liệu
nào đổi, phần nào đã được checker đối chiếu. Không tạo một câu chuyện suy nghĩ
giả hoặc hứa đã kiểm tra khi chưa có report.

Chuột nói như một người bạn đang giữ việc giúp: ngắn, rõ, tếu vừa. Humor tùy
tình huống, không chọc user đang bực hoặc gặp lỗi. Ví dụ sau lưu thành công:
“Gọn đủ để đỡ đánh nhau với mid.” Khi thất bại, nói thẳng phần chưa làm được.
Phản ứng vui/ghi chép đi cùng trạng thái thật, không làm mắt user phải theo một
loạt chuyển màn hình.

Copy là đề xuất cho phase duyệt UI; chưa chỉnh persona/prompt/component production.

### P2 — Theo dõi nhu cầu sau lát cắt

Nguồn note từ đoạn cụ thể của tài liệu dài, persistent memory và checker DSA
chuyên môn cần đánh giá riêng. Các nhu cầu này không được tự mở scope hiện tại.
Kết quả của C06 dùng để xác định giới hạn binding, không đặt điều kiện phải
triển khai DocAI hay một extractor mới để làm demo đậu.

## Chấm kết quả

Chấm riêng bốn phần cho từng lượt: content, references, effects/completion, surface.
Mỗi phần có PASS/FAIL/UNKNOWN/not_observed cùng bằng chứng; không dùng một điểm
chung để che thao tác chưa làm hoặc quality chưa chấm.

Các leading checks đề xuất cho demo:

- Bảy lượt chính dùng đúng source/array/note/version; nội dung DSA review đúng.
- 0 false save/update/verification claims; lưu draft được mô tả đúng là draft.
- 0 mutation ngoài yêu cầu, ghi muộn sau cancel, mất draft hoặc executions do toggle.
- Câu hỏi làm rõ xuất hiện ở ambiguity thật; không lặp yêu cầu nhập nguồn/array đã có.
- 100% lượt run có raw answer, operation receipts, note versions, declared outcomes,
  proof scopes và timings/counters còn thiếu được ghi rõ.

Ghi client time đến kết quả hữu ích đầu tiên và cuối lượt, planning/calls/tools/
verifier theo scope; prompt/completion known/unknown. Chưa đặt ngưỡng latency
giây hoặc tỷ lệ model success tổng quát khi chưa có baseline đúng cấu hình.
Đo waiting experience riêng với độ trễ inference; một animation sớm không làm
thời gian hoàn thành công việc ngắn hơn.

Lagging check sau khi có native thử thật: user có tiếp tục được công việc mà
không phải nhớ tool names, cung cấp lại dữ kiện hoặc chuyển màn hình không.
Ghi nhận bằng task completion và feedback cụ thể, chưa gán retention/NPS giả.

## Nguồn và giới hạn kỹ thuật đã đọc

Document capability hiện có search/read tạo document_search/document_content;
read trả content/total_chars/truncated. Fixtures ngắn giữ content dưới500 ký tự
để source_result.content có thể bind bằng contract notes hiện tại. Ghi chú
diễn giải vẫn proposed, không thêm source-document verifier giả.

Source dài hơn3000 ký tự, với điều kiện “tìm lần xuất hiện đầu tiên” ở cuối.
Default read3000 có thể bỏ sót điều kiện này; read tối đa và scalar-note limit500
là hai ranh giới khác nhau. C06 phải log scope/binding gap, không dùng một mock
“content đã rút gọn” rồi giả nguồn toàn văn. Source fixtures không chứng minh
retrieval quality trên personal index hoặc tài liệu thực tế.

## Timeline và trách nhiệm

1. **Chuẩn bị đã thực hiện:** spec, stimuli/source data và sanity check nội dung.
   Không có model calls/Qt/native runs hoặc sửa core ở lượt này.
2. **Anti:** tiếp tục core theo review reconciliation còn mở. Bộ mẫu này không
   thay task sửa gates bằng việc thêm màn hình/feature.
3. **Sau core review:** user duyệt copy/cách đọc notes trên cùng chat; Anti nối
   UI nhỏ đã chốt. Không xây suggestions bar hoặc popup app mới.
4. **Sau budget live riêng:** harness dùng stimuli JSON và sources, reset giữa
   scenarios, record scope/source/model config, chấm manual từ raw traces.
   Live run không đọc reply_example/specimen_notes làm đáp án hay instructions.
5. **Native acceptance:** thử một conversation ở full/compact, note editing/
   history và Stop. Kết quả thật còn chờ; không tự công bố “seamless đã đạt”.

Không có deadline hoặc budget model mới được cấp bởi tài liệu này.

## Câu hỏi còn mở

- **Engineering, không chặn việc chuẩn bị:** Binding excerpt của nguồn dài nên
  nối vào contract nguồn chung thế nào? Giải qua ADR riêng nếu C06 chứng minh cần.
- **Engineering, trước live run:** Native proposal encoding/gates đã qua review
  chưa, config/call budget và collector đọc stimuli JSON có được chốt chưa?
- **Product/design, phase UI:** Nhịp phản hồi và độ tếu mẫu có hợp khi đọc cả
  conversation không? User review trên artifact/native khi phase đó tới.

Không cần user chọn class names, storage format hay từng câu chữ ngay lúc Anti
đang sửa core. Những câu hỏi này không làm dừng task chuẩn bị đã được giao.
