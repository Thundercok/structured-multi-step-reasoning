# Audit: Retirement of Legacy QtWidgets Monolith

**Date:** 2026-10-25
**Scope:** Complete transition of RAT UI to QtQuick / QML.
**Retired Files:** 27 files, **23976 lines of code**.

## Rationale
To support the heavy ML reasoning core (MLX, Ollama, Qwen, PyTorch) with minimal overhead, the CPU-bound QtWidgets architecture (with software rasterization and heavy pixmap caching) has been completely retired in favor of the hardware-accelerated **QtQuick Scenegraph (Apple Metal RHI)**.

## Archived Manifest
- `omnibar.py`: 5585 lines, SHA256: `e3cb8439dd79f5c0f09428d7b987abf9ab07d4407c75e0a82c6b5f094bbf9f29`
- `workbench_scene.py`: 4084 lines, SHA256: `8d4ca7b5143f5b5213a17ddb8fb851b906f0011274bd7359a14374a38526d7fc`
- `schedule_window.py`: 1823 lines, SHA256: `ab133f80e04899eb95e2eabdad194ccad18ccb39c9dba7b71840471701ecab00`
- `workbench.py`: 1735 lines, SHA256: `3c1d204ce5d97842e90ef5cf4d84dc87f78151cccdf8c81fc24acc2a8f195211`
- `claude_widget.py`: 1148 lines, SHA256: `d1904db666c64aff1788014c7b996f76aad11015656176599fa82890079887c9`
- `chat_stream.py`: 1070 lines, SHA256: `137ca5978d1d95511968fc46f133256b9c38235edb9c2636b72a39aa85c8a5cb`
- `spotlight_window.py`: 1009 lines, SHA256: `dfc3c9d41d0df2553df28268ae1b991339d6d7b6d589a8415c4e922dc5746917`
- `finder_window.py`: 867 lines, SHA256: `ffb1dab382e6b4bc5aeb1f619c208db567ae6fdffe794bf95cc2c26e352e3709`
- `preview_panel.py`: 789 lines, SHA256: `5b56c3f2519d32aa850da0057aab90455885287a25251f9dbc731645718f7799`
- `turn_notes_preview.py`: 686 lines, SHA256: `1830e229c2d5e2a9a0aa6ff7407ea430d84f0fa8428fd0850d249bab93d3c786`
- `turn_notes.py`: 641 lines, SHA256: `93d8706a27c15f8f0be5664bf80586cfb8109b38da9689f32aeefd8f50e1b59c`
- `natal_chart.py`: 675 lines, SHA256: `d3398f6db1c333fa356fd579cc095a8a695d2f6fc2870241e4b9976a86c3acd7`
- `view_renderer.py`: 665 lines, SHA256: `34abd8ec999a0aaa4e8f10d610acb6cbd0f56c6787df9aa95e542e8f5e48a0b8`
- `naming_dialog.py`: 500 lines, SHA256: `252ef4d1d9af0d251cea0dd2b94b6a9132e7a23a1ea6d6fbf16ef0b2624dbe94`
- `settings_dialog.py`: 416 lines, SHA256: `b6952f2a60b1bcfcf9325233bc064462f18fcecc07f6310001018800fda5f9ac`
- `onboarding_dialog.py`: 311 lines, SHA256: `1ebfe249bc16cbe1ff4e7b8fcb71d42beffe46d53bcf6ca1ae2e9c1a21547dc2`
- `work_context.py`: 267 lines, SHA256: `f264c940fbd6ffee1673b197e5db23e6b89661a611c894d74842b81a680bb3d1`
- `compact_cot.py`: 245 lines, SHA256: `8c8fdc825f91a57b1c9db993886ae6b15ef4155df747aa50947866214eef75cc`
- `surface_layout.py`: 228 lines, SHA256: `58e5f7404f8aa1fac57f9f2758b22f8bad3bc6023e920e5b35ca65b26fcfcb48`
- `assistant_presenter.py`: 225 lines, SHA256: `7b6c1b1968084379b46cb2bf0bbe5127f09706feea5f89523dc3bf836769e5fa`
- `action_menu.py`: 209 lines, SHA256: `c8dd542145ce23325b2eb61cba977e275e01390b0ca12b68bf34da4f663ef9e0`
- `compact_results.py`: 165 lines, SHA256: `4bc4edf272c4be9af706f552437f06ab292288f2ee58317086fbd4816a0fff73`
- `live_companion.py`: 155 lines, SHA256: `bcc18fe718935bf2e5dcb0fa45d2fa34d943ed4bd1f4461ef3eeaf927a8b8f13`
- `execution_flow.py`: 139 lines, SHA256: `92b80f514be6adeca17942721346eb2af49cfd6c19852cf29822870c3655535c`
- `apple_item_delegate.py`: 193 lines, SHA256: `bf11342a4a041a63a0c7f0de852e86cf9c652358f513a917cb047c6823747c3c`
- `artifact_resources.py`: 93 lines, SHA256: `0f37cdca682915f4f6a3f46cd25b66eef6d227384404288d853eb9f5f820071b`
- `feedback.py`: 53 lines, SHA256: `58a0842e8caa3f04a06fb9be2f212e37b44fb7075f20b90138f5591d5bbd4ecc`

## Recovery
To restore any of these legacy files for historical inspection or reference:
```bash
cp audit/ui_widgets_retirement_20261025/legacy_widgets/<filename> rat/ui/
```
