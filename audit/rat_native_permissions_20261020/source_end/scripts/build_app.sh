#!/usr/bin/env bash
# ==============================================================================
# scripts/build_app.sh — 1-Click Standalone Build Script for rat.app & rat.dmg
# ==============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

BUILD_MODE="${1:-}"
case "$BUILD_MODE" in
    ""|--check|--dmg-only) ;;
    --help|-h) echo "Usage: scripts/build_app.sh [--check|--dmg-only]"; exit 0 ;;
    *) echo "Unknown option: $BUILD_MODE" >&2; exit 2 ;;
esac

# Choose an interpreter and check prerequisites before touching previous outputs.
if [ -z "${PYTHON_BIN:-}" ]; then
    if [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
        PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
    else
        PYTHON_BIN="python3"
    fi
fi
if [ "$BUILD_MODE" == "--check" ]; then
    exec "$PYTHON_BIN" scripts/check_packaging.py --probe-qt
fi
if [ "$(uname -s)" != "Darwin" ]; then
    echo "The app/DMG build requires macOS. Use --check for offline preflight." >&2
    exit 1
fi
if [ "$BUILD_MODE" == "--dmg-only" ]; then
    if [ ! -d "dist/rat.app" ]; then
        echo "--dmg-only requires an existing dist/rat.app." >&2
        exit 1
    fi
else
    "$PYTHON_BIN" scripts/check_packaging.py --probe-qt
fi

echo "================================================================="
echo "  🚀 Starting 1-Click Standalone Build for rat on macOS"
echo "================================================================="

# 1. Clean previous build artifacts (unless --dmg-only is specified)
if [ "$BUILD_MODE" == "--dmg-only" ]; then
    echo "⏩ --dmg-only specified and dist/rat.app exists. Skipping rebuild, creating DMG directly..."
    rm -rf dmg_temp dist/rat.dmg
else
    echo "🧹 Cleaning previous build artifacts..."
    rm -rf build/rat dist/rat dist/rat.app dmg_temp dist/rat.dmg
fi

echo "🐍 Using Python: $PYTHON_BIN"

if [ "$BUILD_MODE" != "--dmg-only" ]; then
    # 2. Ensure rat.icns icon exists
    if [ ! -f "rat.icns" ]; then
        echo "🎨 Generating high-resolution rat.icns icon..."
        "$PYTHON_BIN" scripts/generate_icon.py
    fi

    # 3. Build rat.app using PyInstaller
    echo "📦 Packaging rat.app with PyInstaller..."
    "$PYTHON_BIN" -m PyInstaller rat.spec --clean --noconfirm

    if [ ! -d "dist/rat.app" ]; then
        echo "❌ Error: dist/rat.app was not created!"
        exit 1
    fi

    echo "✅ rat.app created successfully in dist/rat.app"

    # PyInstaller signs with the configured identity/entitlements. Do not replace
    # that signature with a second plain ad-hoc signing pass.
    echo "🔏 Verifying the final app signature..."
    codesign --verify --deep --strict --verbose=2 dist/rat.app
fi

# 5. Create DMG Installer with Applications drag-and-drop symlink & Gatekeeper Helper
echo "💿 Creating standalone rat.dmg disk image..."
mkdir -p dmg_temp
cp -R dist/rat.app dmg_temp/
ln -s /Applications dmg_temp/Applications

# Add 1-click Gatekeeper bypass and auto-installer helper for friends
cat << 'EOF' > "dmg_temp/Cài_Đặt_và_Mở_rat.command"
#!/bin/bash
# ==============================================================================
# rat — 1-Click Auto-Installer & Gatekeeper Bypass Helper for macOS
# ==============================================================================
clear
echo "====================================================="
echo "  🐭 rat — Trình Hỗ Trợ Cài Đặt 1-Click & Mở Ứng Dụng"
echo "====================================================="
echo ""

SOURCE_APP="$(dirname "$0")/rat.app"
DEST_APP="/Applications/rat.app"

if [ -d "$SOURCE_APP" ] && [ ! -d "$DEST_APP" ]; then
    echo "📦 Đang tự động sao chép rat.app vào thư mục /Applications..."
    cp -R "$SOURCE_APP" /Applications/
    echo "✓ Đã sao chép thành công!"
fi

if [ -d "$DEST_APP" ]; then
    echo "🔓 Đang gỡ bỏ cờ hạn chế của Apple (Gatekeeper Quarantine)..."
    xattr -cr "$DEST_APP" 2>/dev/null || true
    echo "✓ Đã gỡ bỏ cờ hạn chế cho $DEST_APP!"
    echo "🚀 Đang khởi chạy ứng dụng rat..."
    open "$DEST_APP"
elif [ -d "$SOURCE_APP" ]; then
    echo "🔓 Đang gỡ bỏ cờ hạn chế của Apple cho bản chạy tạm..."
    xattr -cr "$SOURCE_APP" 2>/dev/null || true
    open "$SOURCE_APP"
else
    echo "⚠️ Không tìm thấy rat.app. Vui lòng kéo rat.app vào Applications trước."
fi

echo ""
echo "✨ Hoàn tất! Cửa sổ này sẽ tự động đóng sau 3 giây..."
sleep 3
exit 0
EOF
chmod +x "dmg_temp/Cài_Đặt_và_Mở_rat.command"
cp "dmg_temp/Cài_Đặt_và_Mở_rat.command" "dmg_temp/Open_Rat_First_Time.command"
chmod +x "dmg_temp/Open_Rat_First_Time.command"

# Add friendly Vietnamese Quick Guide
cat << 'EOF' > "dmg_temp/HƯỚNG_DẪN_CÀI_ĐẶT.txt"
========================================================================
  🐭 CHÀO MỪNG BẠN ĐẾN VỚI RAT (Retrieval Augmented Tool)
  Trợ lý tìm kiếm tệp tin & quản trị lịch trình học tập trên macOS
========================================================================

CÁCH DÙNG NHANH NHẤT (DÀNH CHO BẠN BÈ / CLB):

👉 CÁCH 1: NHẤP ĐÚP VÀO FILE:
   "Cài_Đặt_và_Mở_rat.command" (hoặc "Open_Rat_First_Time.command")
   -> Script sẽ tự động chép rat.app vào Applications và mở app ngay lập tức!

👉 CÁCH 2: CÀI ĐẶT THỦ CÔNG:
   1. Kéo thả biểu tượng "rat.app" vào thư mục "Applications" bên cạnh.
   2. Vào Applications, nhấp chuột phải (Control + Click) vào rat.app -> Chọn "Open" -> Bấm "Open".
    (Nếu macOS Sequoia báo lỗi app không rõ nguồn gốc, mở Terminal gõ: xattr -cr /Applications/rat.app)

------------------------------------------------------------------------
🌟 PHÍM TẮT & TÍNH NĂNG CHÍNH:
------------------------------------------------------------------------
• Command + Shift + Space (⌘ ⇧ Space): Mở thanh tìm kiếm Spotlight AI siêu tốc.
• Icon chuột trên Menu Bar: Xem thống kê, quét lại file, hoặc mở Thời Khóa Biểu CLB.
• Ghép TKB nhóm: Bấm icon chuột trên Menu Bar -> Chọn "Thời khóa biểu CLB" để tìm khung giờ rảnh chung.

Chúc bạn tìm kiếm tài liệu và sắp xếp lịch học thật chill & hiệu quả!
========================================================================
EOF

hdiutil create -volname "rat — Smart File Finder" \
               -srcfolder dmg_temp \
               -ov -format UDZO \
               "dist/rat.dmg"

rm -rf dmg_temp

echo "================================================================="
echo "  🎉 BUILD COMPLETE!"
echo "  📂 Output App: $PROJECT_DIR/dist/rat.app"
echo "  💿 Installer DMG: $PROJECT_DIR/dist/rat.dmg"
echo "  ✨ Your friend can now download rat.dmg, drag it to Applications, and use it immediately!"
echo "================================================================="
