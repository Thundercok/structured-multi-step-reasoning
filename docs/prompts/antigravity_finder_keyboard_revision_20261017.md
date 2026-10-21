# Antigravity — chốt phần bàn phím của finder sau review vòng 2

Người dùng đã giao thêm phần nối native Hỏi tệp sau revision này. Gói bàn giao
đầy đủ, thứ tự thực hiện và acceptance nằm ở
`docs/prompts/antigravity_keyboard_and_native_qa_handoff_20261017.md`.
Các giới hạn dưới đây áp dụng cho bước sửa bàn phím; bước tích hợp tiếp theo
tái sử dụng backend MLX đã có, không viết lại engine.

Codex đã kiểm chứng bản sửa mới. **Bảy vấn đề trước đã được sửa theo các probe
cũ; regression rộng đạt 185 passed + 3 subtests**, gồm selected-document UI và
active-detail probe. Không sửa lại bố cục thought bubble, backend hoặc model.
Giữ main và thay đổi đồng thời; không commit/push/pull/reset/tạo branch.

Còn bốn P2 trong nhánh bàn phím vừa nối, đều có probe tái hiện:

1. **Enter khi focus nút Hỏi lại mở file.** `OmnibarInputFilter` trả False cho
   QPushButton Return/Enter; Qt button không kích hoạt click trong trường hợp
   này, event tiếp tục lên row và bị nhánh Enter chung gọi `open_file_default`.
   Probe đã thấy call mở `beta.txt` thay vì chọn nguồn để hỏi. Space hoạt động.
   Xử lý Enter/Space của action button một cách rõ ràng và consume event sau
   action, không để nó chạy tiếp sang hành động mặc định của row. Kiểm tra đủ
   Hỏi/Mở/Xem/Hiện trong Finder; không tạo model call hay chat turn khi chỉ Hỏi.
   Vị trí: `rat/ui/omnibar.py:487–493` trong snapshot review.
2. **Tab sang row thứ hai rồi Cmd+Enter vẫn reveal file của row đầu.** Focus
   đã ở nút Hỏi của beta, nhưng `current_hit()` vẫn alpha vì Tab/focus không
   đồng bộ selection. Nối focus row/action về đúng resource_id, đồng nhất
   highlight và shortcut target. Kiểm tra bằng Tab thật qua các nút, không chỉ
   gọi `set_selected_id()` trước test. Vị trí: `omnibar.py:482–485` cùng luồng
   focus của `FinderHitRow`/`FinderSuggestionsWidget`.
3. **Shift+Down bị finder chiếm phím.** Nhánh Down chỉ loại Control/Meta, vẫn
   bắt Shift khi caret ở dòng cuối. Với `fixture`, caret 2: native ChatComposer
   chọn tới vị trí 7; cửa sổ tích hợp giữ caret 2 và chuyển focus sang finder.
   Chỉ chuyển sang gợi ý với tổ hợp điều hướng đã định nghĩa; giữ Shift và các
   modifier chỉnh sửa văn bản. Down thuần ở giữa draft nhiều dòng hiện đã đúng,
   phải giữ nguyên. Vị trí: `omnibar.py:376–393`.
4. **Snapshot cùng query làm mất focus action đang duyệt.**
   `FinderSuggestionsWidget.set_snapshot()` xóa/tạo lại mọi row. Resource_id
   còn đúng nhưng focus trên Hỏi của beta mất sau update. Ưu tiên reconcile
   rows theo id, hoặc capture/restore vai trò action + resource_id và scroll;
   không lấy focus khỏi composer nếu người dùng đang gõ. Đây là hợp đồng của
   progressive update, chưa phải bằng chứng UI đang chạy semantic provider
   thật. Vị trí: `workbench_scene.py:2196–2222`.

```sh
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest \
  audit/rat_finder_codex_review_r2_20261017/test_keyboard_followups.py -q
```

Hiện **4 failed, 2 passed**. Hai case đúng là Space trên Hỏi và Down thuần trong
draft nhiều dòng. Probe mock mọi hành động mở/reveal nên không mở file thật.
Giữ nguyên assertions hoặc giải thích thay đổi hợp đồng nếu cần sửa test; không
xfail/nới test cho xanh. Sau sửa chạy lại 12 probe cũ và các regression đã yêu
cầu trong handoff trước, lưu XML cùng source hashes.

Ảnh mới khớp hash source và đủ bốn nút ở 620px/420px. Tuy nhiên session metadata
ghi `qpa_platform=offscreen`. Ghi đúng là Qt offscreen fixture/widget capture;
chưa thay thế acceptance Cocoa/IME hoặc model thật. Backend MLX startup mà
Codex vừa chuẩn bị vẫn nguyên hash; không chạm vào phần đó trong revision này.

Bằng chứng đầy đủ: `audit/rat_finder_codex_review_r2_20261017/`.
