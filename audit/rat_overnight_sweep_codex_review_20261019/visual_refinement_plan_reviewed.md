# Updated Visual Specimens (Milestone B / D) & Visual Refinement Plan

> [!NOTE]
> **Capture Provenance**: All specimens below were freshly generated from the post-review-fix codebase using deterministic Qt fixture replay (`QWidget.grab()`, `qpa_platform=offscreen`, `RAT_WORKBENCH_SCENE=1`, `RAT_WORKBENCH_FINDER=1`, `RAT_REDUCE_MOTION=1`). No production files in `rat/` or `tests/` were modified during specimen generation so your ongoing review checks remain untouched.

---

## 1. Fresh Milestone B / D Visual Specimens (`qpa_platform=offscreen`)

````carousel
![Desktop Light — Natural Finder Interpretation Chips, 3-Dot Thought Trail & Filtered Hits (620×433, qpa_platform=offscreen)](/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/specimen_1_desktop_light_finder_offscreen.png)
<!-- slide -->
![Narrow 420px Light — Reflowed Compact Workbench, 4 Visible File Action Buttons & Bottom Composer Anchor (420×513, qpa_platform=offscreen)](/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/specimen_2_narrow_420px_light_offscreen.png)
<!-- slide -->
![Desktop Light (Top of Desk) — Observed Source Card, Excerpt Card & Grounded Relationship Strip (652×600, qpa_platform=offscreen)](/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/specimen_3a_desktop_light_sources_top_offscreen.png)
<!-- slide -->
![Desktop Light (Bottom of Desk) — Committed Result Answer & Expanded Grounded Reasoning Trace (652×600, qpa_platform=offscreen)](/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/specimen_3b_desktop_light_trace_bottom_offscreen.png)
<!-- slide -->
![Desktop Dark — App Disambiguation (`mở Liên Minh`) & Grounded Waiting Trace (620×489, qpa_platform=offscreen)](/Users/thundercock2/.gemini/antigravity/brain/1543d8ec-005e-4709-a052-c585c9fd7d2a/specimen_4_desktop_dark_disambiguation_offscreen.png)
````

### Specimen Telemetry Summary

| Specimen | File | `qpa_platform` | Dimensions | Theme | Key Verified Elements |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Desktop Light (Finder)** | `specimen_1_desktop_light_finder_offscreen.png` | `offscreen` | `620 × 433` | Light | `rat.` compact chrome (no duplicate hero title), interpretation chips (`Từ khóa: DSA · Loại: Slide… · Thời gian: Tuần trước`), 2 filtered rows, 3-dot thought trail |
| **2. Narrow 420px (Finder)** | `specimen_2_narrow_420px_light_offscreen.png` | `offscreen` | `420 × 513` | Light | `is_narrow=True`, all 4 file action buttons (`Hỏi` `32×18`, `Mở` `30×18`, `Xem` `37×18`, `↗` `23×18`) have non-empty `visibleRegion`, full-width composer at bottom |
| **3a/3b. Desktop Light (Grounded Trace & QA)** | `specimen_3a_...` / `specimen_3b_...` | `offscreen` | `652 × 600` | Light | `SourceCardWidget` + `ExcerptCardWidget` + `GroundedRelationsWidget` (`↳ Nguồn → Đoạn đã đọc`) + `ResultDeskCard` + expanded `SceneTraceBox` (`[Đã đọc]`, `[Đã xong]`, `[Kiểm tra đạt]`) |
| **4. Desktop Dark (Disambiguation + Trace)** | `specimen_4_desktop_dark_disambiguation_offscreen.png` | `offscreen` | `620 × 489` | Dark | Dark palette (`#272a25`), 2-candidate `InputRequest` card for `mở Liên Minh`, grounded trace (`[Đã tìm thấy]` → `[Chờ chọn]`), 3-dot thought trail |

---

## 2. Visual Inspection Findings & Refinement Plan

Inspecting the rendered pixels across all 5 views surfaced **6 concrete, low-risk visual issues** that we can polish once your current check run completes:

### V1 — [High Impact / Bug] Invalid QSS Object-ID Selector Breaks `SourceCardWidget` Styling
- **Where**: [`SourceCardWidget.__init__`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench_scene.py#L1537) and [`SourceCardWidget._apply_style`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench_scene.py#L1654-L1699)
- **What happens**: `self.setObjectName(f"SceneSourceCard_{node.node_id}")` embeds `node.node_id` (e.g., `source:file:/var/folders/.../so_tay_sinh_vien_2026.txt`) directly into the widget's `objectName`. Because it contains colons (`:`), slashes (`/`), and dots (`.`), `QFrame#{self.objectName()}` is parsed by Qt as an invalid CSS pseudo-state (`:file`), causing Qt to **discard the entire stylesheet block** on `SourceCardWidget`.
- **Visual symptom (seen in Slide 3)**:
  - The top `SourceCardWidget` (`THAM CHIẾU so_tay_sinh_vien_2026.txt`) has no card border or background.
  - Its `Mở tệp` button (`SceneSourceOpenBtn`) falls back to an unstyled **pitch-black rectangle** (`#000000`).
  - In Dark Mode, the unstyled card text turns dark-on-dark and becomes illegible.
- **Planned change**: Sanitize `objectName` (e.g., `re.sub(r'[^A-Za-z0-9_]', '_', node.node_id)`) so `SourceCardWidget`, `SceneSourceBadge`, and `SceneSourceOpenBtn` render with their intended paper/soft card frame and sage badge styling.

### V2 — [High Impact / Layout] Eliminate Triple Excerpt & Short-Answer Duplication in Level-1 (`overview`) Document QA
- **Where**: [`WorkbenchScene.apply_snapshot`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench_scene.py#L3584-L3610), [`ResultDeskCard.update_result`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench_scene.py#L1969-L2032), and [`OmnibarWindow`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/omnibar.py)
- **Confirmed Decision**:
  1. **Source-Read Artifacts**: When `mode == "overview"` and an artifact is a pure source-read artifact (`document_content`, `book_page_content`, `document_search`, `book_page_search`) already projected as a `SourceCardWidget` + `ExcerptCardWidget`, keep its `QtViewRenderer` hidden in `overview` (retaining it in `artifact_panel.renderers` so clicking the source card borrows it into Level 2 `source_detail` without re-creating it).
  2. **Truncated / Interactive Result Card Only**: When Chuột's speech bubble (`WorkbenchRatBubble`) already displays the full, untruncated reply (`not rat_bubble._truncated`) and there are no interactive/non-source artifacts or revision transitions on the desk, keep `ResultDeskCard` compact/hidden in `overview` (while keeping `answer_lbl` populated for streaming selection probes and showing `ResultDeskCard` whenever the answer is truncated in `WorkbenchRatBubble`, streaming, or backed by an interactive artifact such as `input_request`, `natal_chart`, `result_table`, or `schedule`).

### V3 — [Medium Impact / Clipping] Prevent Right-Edge Clipping on Disambiguation Choices & Long Paths
- **Where**: [`QtViewRenderer`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/view_renderer.py), [`applications.py`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/kernel/capabilities/applications.py), and [`build_reasoning_flow`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/work_trace.py#L328-L344)
- **What happens (seen in Slide 5 — Dark Mode)**:
  - Long bundle paths in candidate choice buttons (`League of Legends · /private/var/folders/.../Applications/League of Legends.app`) force `QtViewRenderer` wider than the scroll viewport, clipping the right side of the prompt text (`...hoặc bản cài đ`) and the right border of the choice buttons.
  - Long raw paths inside `SceneTraceDetail` also push the trace label width to the right edge.
- **Planned change**:
  - Format disambiguation candidate labels and trace details using concise distinguishing paths (e.g., `~/...` or `.../Applications/League of Legends.app` vs `.../Riot Games/League of Legends.app`, keeping the full path in the button tooltip and payload).
  - Set `setMinimumWidth(0)` and `QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred` on `SceneTraceDetail` and `QtViewRenderer` text/choice widgets so they wrap or elide within the card width.

### V4 — [Medium Impact / Finder Polish] De-duplicate Interpretation Chips vs. Scope Banner & Surface Structured Finder Trace
- **Where**: [`parse_finder_intent`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/engine/finder_intent.py), [`FinderSuggestionsWidget`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench_scene.py#L2463-L2492), and [`WorkbenchScene._sync_trace_ui`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench_scene.py#L3220-L3226)
- **What happens (seen in Slides 1 & 2)**:
  - The top chip label says `Loại: Slide (.pptx/.ppt/.key hoặc PDF slide/bài giảng)` and the banner immediately below says `Quy tắc Slide: ưu tiên .pptx/.ppt/.key; chỉ nhận .pdf có tên hoặc tóm tắt chứa dấu hiệu slide/bài giảng.` — repeating the same parenthetical twice and causing the top header to wrap onto 2–3 lines.
  - `_sync_trace_ui` hides `trace_box` whenever `phase == "empty" and finder_box.isVisible()`, even when `finder_intent.has_structured_constraints` has generated a grounded 2-step reasoning flow (`Hiểu yêu cầu tìm kiếm → Lọc ứng viên trong chỉ mục`).
- **Planned change**:
  - Keep the header chip concise (`Loại: Slide / bài giảng`) while letting the subtle notice banner below explain the PDF/PPTX rule when relevant.
  - Show the quiet 1-line `SceneTraceBox` toggle (`▸ Nhật ký thao tác (2 bước) · Hiểu yêu cầu tìm kiếm → Lọc ứng viên trong chỉ mục`) below `finder_box` whenever `finder_intent` has structured constraints.

### V5 — [Low/Medium Impact / Theme & Contrast] Strengthen 3-Dot Thought Trail in Light Mode & Dark-Mode `QtViewRenderer` Tokens
- **Where**: [`WorkbenchThoughtTrail.paintEvent`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/workbench.py#L591-L616) and [`QtViewRenderer._apply_theme`](file:///Users/thundercock2/Documents/Github/multi-step-structured-reasoning/rat/ui/view_renderer.py)
- **What happens**:
  - In Light Mode (Slides 1–3), the 3 ascending thought-bubble dots use `tokens.line` (`#e4e7dc`) at `1.0px` stroke on `#fffefa` fill, which is very faint (~1.15:1 contrast against light backgrounds).
  - In Dark Mode, `QtViewRenderer` still has a few hardcoded light-mode colors (`#3B312B` title text next to the `TXT` badge), making artifact titles hard to read on `#272a25`.
- **Planned change**:
  - Use `tokens.user_line` (`#d4ddc7` in light mode, `#566649` in dark mode) with `1.35px` pen width and slightly clearer radii (`2.2px`, `3.3px`, `4.6px`) for the 3-dot thought trail.
  - Bind `QtViewRenderer` title/subtitle colors to `WorkbenchTokens.get()` in `_apply_theme()`.

### V6 — [Low Impact / Startup Latency] Eliminate `"Sans Serif"` Font Alias Lookup (`~110–220ms` Startup Cost)
- **Where**: Residual stylesheet strings in `rat/ui/` (`omnibar.py` / `preview_panel.py` / `theme.py`)
- **What happens**: Qt logs `qt.qpa.fonts: Populating font family aliases took 207 ms. Replace uses of missing font family "Sans Serif" with one that exists to avoid this cost.` on startup.
- **Planned change**: Replace any remaining `"Sans Serif"` / `"sans-serif"` QSS font-family declarations with `FONT_FAMILY` (`.AppleSystemUIFont` on macOS).
