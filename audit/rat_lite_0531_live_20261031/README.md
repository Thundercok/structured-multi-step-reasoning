# RAT Lite `0.5.31` Live Cocoa Verification Report

- **Date**: 2026-10-31
- **Target**: RAT Lite `0.5.31` (Build `20261031.1`)
- **Platform**: macOS 14+ (Apple Silicon arm64, native Cocoa window, no offscreen/mocking)
- **Status**: **PASS (4 / 4 Core User Journeys Verified)**

---

## 1. Executive Summary

All four core user journeys were executed against the live Cocoa window using real native services (`rat-hotkey`, Carbon event loops, local CTranslate2 translation models, and Spotlight file search) with zero canned assistant responses:

1. **Setup / Welcome (`auxiliary`)**:
   - Window opens centered on screen (`580×360`), showing the standalone welcome view.
   - Mascot is hidden (`mascotCrop.visible == false`).
   - Clicking `"Bắt đầu"` (`completeSetup()`) transitions cleanly into the active rat companion and composer without requiring Accessibility permissions for typed input.
   - **Artifact**: `journey1_welcome_auxiliary.png`.

2. **Hotkey Helper Connection (`rat-hotkey`)**:
   - The Carbon hotkey helper binary (`rat/bin/rat-hotkey`) spawned and registered the default `⌥⇧Space` chord with identity check `READY SELECT2 20261031.1 49 2560`.
   - The `"Phím tắt chưa sẵn sàng"` warning banner in composer remained dismissed (`hotkeyStatus == ""`).
   - Rat companion is cleanly anchored at optical size `144×144`.
   - **Artifact**: `journey2_composer_hotkey_ready.png`.

3. **Spotlight File Finding (`find_files`)**:
   - Querying `Tìm project_scope.md` invoked the genuine `find_files` operation over scoped roots.
   - Hit returned: `project_scope.md` (`/Volumes/NO NAME/project_scope.md`).
   - Layout strictly conforms to the anchored UX: `resultSheet` rendered **above** `composer` (`composer.y == 200.0`), with the rat companion anchored beside.
   - Keyboard navigation (`↑`/`↓`) updated `selectedFinderIndex` cleanly.
   - **Artifact**: `journey3_finder_results.png`.

4. **Offline Translation (`translate_text`)**:
   - Input: `"Dịch: The little rat is reading a book."`
   - Real local CTranslate2 neural MT translated the snippet to `"Con chuột nhỏ đang đọc sách."` without any LLM or network dependency.
   - Result bubble is rendered in compact extent (`interactionExtent: "compact"`) above composer.
   - Resizing toggle between `compact` and `expanded` functions cleanly while keeping `mascotCrop` anchored at `144×144`.
   - **Artifacts**: `journey4_offline_translation_compact.png`, `journey4_offline_translation_expanded.png`.

---

## 2. Screenshot Manifest

| Journey | State | File | Dimensions |
| :--- | :--- | :--- | :--- |
| Journey 1 | Welcome Sheet (`auxiliary`) | `journey1_welcome_auxiliary.png` | 580 × 360 |
| Journey 2 | Companion + Composer (`rat-hotkey` READY) | `journey2_composer_hotkey_ready.png` | Anchored 144×144 rat + composer |
| Journey 3 | Finder Hits Sheet (Above Composer) | `journey3_finder_results.png` | 580 × (Sheet + Composer) |
| Journey 4 | Offline Translation (Compact) | `journey4_offline_translation_compact.png` | Compact speech bubble |
| Journey 4 | Offline Translation (Expanded) | `journey4_offline_translation_expanded.png` | Expanded view |

Full JSON metrics: [verification_report.json](verification_report.json).
