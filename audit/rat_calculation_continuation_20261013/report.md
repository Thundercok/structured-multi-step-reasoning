# RAT: calculator và notes trong cùng hội thoại

Ngày 2026-10-13, Asia/Saigon. Phạm vi bằng chứng: contract phần mềm bằng quyết định được tiêm sẵn và Qt offscreen. Không gọi model mới; chưa đo chất lượng model hoặc latency inference.

## Kết quả

- Calculator lưu kết quả có ID/revision và ownership trong artifact store hiện có.
- `record_work_note` nhận nguồn kết quả thật, kiểm tra ID/revision/field; dùng cùng notes/event/version.
- Notes từ tool có authority `observed_result`; sao chép nguồn không biến thành dữ kiện user hoặc xác nhận semantic correctness. Paraphrase vẫn proposed.
- Note cũ giữ nội dung và nguồn, dẫn tới phiên bản thay thế. Dừng giữ artifact đã commit và chặn ghi muộn; execution tiếp theo đọc/ghi lại được.
- `present_result=False` dùng câu trả lời/trace để trình bày observation được giữ. Presenter không tự thêm data card; deliverable khác vẫn hiện.

## Kiểm tra

Baseline: **2 failed / 11 passed** trong contract mới: calculator không lưu artifact và notes chưa nhận nguồn result. Xem `baseline.json` và `before_source/`.

Bản cuối: **186 headless tests passed** (6,01s), **53 Qt tests passed** (12,31s). Logs: `headless_tests.txt`, `qt_tests.txt`. Đây là thời gian chạy tests, không phải latency model.

Qt sandbox abort vì không đọc được NEON; chạy cùng bộ test offscreen ngoài sandbox thành công. Chưa nghiệm thu native full/compact bằng thao tác thật.

`contract_transcript_final.json` lưu 6 lượt fixture: 126 → ghi → 162/revision 2 → chênh 36 → dừng sau khi commit 324 → ghi tiếp thành revision 3. Model decisions được tiêm sẵn để kiểm tra wiring. PASS số học không chứng minh diễn giải yêu cầu hoặc lời khẳng định hoàn tất.

`source_test_start.json`, `tested_source/` và `validation.json` ghi source/hash, câu lệnh và scope. Diff whitespace của source được sửa trong mốc này qua. Các thay đổi khác trong working tree nằm ngoài phạm vi lượt này.

## Cần làm tiếp

1. Review bàn giao Antigravity trên snapshot riêng. Giữ nguyên raw DSA smoke; không dùng chúng làm evidence cho contract mới.
2. Development smoke bằng model thật với cách diễn đạt mới: chấm tool selection, dữ kiện, note events, revision và nội dung riêng với phần mềm.
3. Đo model calls, prompt/completion tokens, online latency và overhead planner trước khi đổi cấu hình mặc định.
4. Nghiệm thu native compact/full, notes inline và cùng composer.

Lượt này không thay model mặc định, controller/pipeline NCKH, Stage 0 hay tích hợp DocAI. [Contract chi tiết](../../docs/rat_result_notes_contract.md).
