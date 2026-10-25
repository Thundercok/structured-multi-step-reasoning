# RAT — bỏ QtWidgets khỏi runtime ứng dụng

Ngày: 2026-10-25. Build nhìn thấy: **2026.10.25.24 · Qt Quick**.

Đã thay `QApplication` bằng `QGuiApplication` trong startup, resident app,
clipboard/context bridge, diagnostics và crash shield. Icon provider dùng
`QAbstractFileIconProvider` của QtGui. Status menu macOS dùng AppKit/NSStatusItem,
với QAction làm model; không dùng QMenu/QSystemTrayIcon hoặc fallback QtWidgets.
Cửa sổ ứng dụng dùng QML/Qt Quick. Menu hệ điều hành là native AppKit.

Spec đóng gói bỏ hidden imports của các cửa sổ đã retirement và exclude
`PyQt6.QtWidgets`. Chưa build/cài lại bundle `rat.app`; không tuyên bố bundle
đã được kiểm tra. Recovery và các thay đổi nghiệp vụ khác được giữ nguyên.

Kiểm tra cuối: **23 tests runtime/lifecycle/packaging pass**, **40 tests QML/PDF/
answer pass**, **29 tests research pass**. Có subprocess chặn import QtWidgets
khi tạo production Desk và native action model. QtTest trong test process tự
nạp QtWidgets; điều đó không thuộc dependency của production entry point.

Smoke native xác nhận `platform=cocoa`, `GraphicsApi.MetalRhi`,
`widgets_loaded=false`; status item AppKit và callback QAction hoạt động.
Hội thoại live qua composer dùng Ollama `qwen3:4b-instruct` đã cài, PDF arXiv
gốc có provenance/hash, một call được ghi lại, answer tiêu đề đúng. Có ảnh
actual full/compact và ảnh lỗi nguồn. Không dùng fixture làm acceptance live.

Giới hạn: thẻ trang nguồn vẫn có trường hợp không hiện excerpt; các lượt kiểm
tra gộp ban đầu có crash/hang và lỗi domain/Finder được giữ trong raw logs.
Không xác nhận toàn bộ tests hoặc feature parity. Status menu ngoài macOS chưa
có backend. Hiệu năng, toàn bộ reasoning agentic và Stage 0 không được suy ra
từ việc đổi framework. Xem [thiết kế execution](rat_agentic_execution_redesign_20261025.md).

Bằng chứng và phạm vi chính xác: [artifact README](../artifacts/qtquick_only_20261025/README.md).
