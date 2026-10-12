#!/usr/bin/env bash
# ==============================================================================
# scripts/setup.sh — 1-Click Automated Setup for rat (macOS)
# Automates Python detection, virtual environment creation, dependency
# installation, self-verification, and shell command integration.
# ==============================================================================
set -e

# ANSI Color Codes
BOLD="\033[1m"
GREEN="\033[0;32m"
CYAN="\033[0;36m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
NC="\033[0m" # No Color

# Determine project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo -e "${CYAN}${BOLD}"
echo "================================================================="
echo "   🐭 rat (Retrieval Augmented Tool) — 1-Click Setup"
echo "   Trợ lý tìm kiếm tệp tin & quản lý lịch trình trên macOS"
echo "================================================================="
echo -e "${NC}"

# 1. Check Operating System
echo -e "🔍 ${BOLD}Bước 1/5: Kiểm tra hệ điều hành...${NC}"
OS_TYPE="$(uname -s)"
if [ "$OS_TYPE" != "Darwin" ]; then
    echo -e "${YELLOW}⚠️ Cảnh báo: rat được tối ưu hóa tốt nhất cho macOS (Apple Silicon & Intel).${NC}"
    echo -e "Hệ điều hành hiện tại: $OS_TYPE. Một số tính năng Apple Vision / PDFKit có thể tự chuyển sang fallback."
else
    ARCH="$(uname -m)"
    echo -e "${GREEN}✓ Phát hiện macOS ($ARCH). Sẵn sàng tối ưu phần cứng Apple!${NC}"
fi

# 2. Check Python 3 & Version (Requirement: >= 3.10)
echo -e "\n🔍 ${BOLD}Bước 2/5: Kiểm tra môi trường Python 3...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Không tìm thấy Python 3 trên máy của bạn!${NC}"
    echo -e "👉 Vui lòng cài đặt Python bằng lệnh sau trong Terminal:"
    echo -e "   ${CYAN}brew install python@3.12${NC}"
    echo -e "   (Hoặc tải từ https://www.python.org/downloads/)"
    exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="$(python3 -c 'import sys; print(sys.version_info.major)')"
PY_MINOR="$(python3 -c 'import sys; print(sys.version_info.minor)')"

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]); then
    echo -e "${RED}❌ Phiên bản Python hiện tại ($PY_VERSION) quá cũ. rat yêu cầu Python >= 3.10.${NC}"
    echo -e "👉 Hãy cập nhật Python bằng lệnh: ${CYAN}brew install python@3.12${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 đã sẵn sàng: phiên bản $PY_VERSION${NC}"

# Handle --check-only flag
if [ "$1" == "--check-only" ]; then
    echo -e "\n🧪 Chế độ kiểm tra nhanh hoàn tất thành công!"
    exit 0
fi

# 3. Create or Activate Isolated Virtual Environment (.venv)
echo -e "\n📦 ${BOLD}Bước 3/5: Thiết lập môi trường ảo độc lập (.venv)...${NC}"
VENV_DIR="$PROJECT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Tạo môi trường ảo tại $VENV_DIR (tuân thủ chuẩn bảo mật PEP 668 của macOS)..."
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Đã tạo .venv thành công.${NC}"
else
    echo -e "${GREEN}✓ Đã tìm thấy môi trường ảo .venv hiện hữu.${NC}"
fi

# Activate venv for installation and verification
source "$VENV_DIR/bin/activate"
PYTHON_BIN="$VENV_DIR/bin/python3"
PIP_BIN="$VENV_DIR/bin/pip"

# 4. Install Dependencies
echo -e "\n⬇️  ${BOLD}Bước 4/5: Cài đặt và cập nhật các thư viện cần thiết...${NC}"
"$PIP_BIN" install --upgrade pip --quiet

if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    echo "Đang cài đặt các gói phụ thuộc từ requirements.txt (PyQt6, FastEmbed, PyObjC, pynput)..."
    "$PIP_BIN" install -r "$PROJECT_DIR/requirements.txt" --quiet
else
    echo "Đang cài đặt các gói thư viện cơ sở..."
    "$PIP_BIN" install PyQt6 rich pynput watchdog fastembed numpy pypdf python-docx python-pptx openpyxl pillow pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-Quartz pyobjc-framework-ApplicationServices --quiet
fi
echo -e "${GREEN}✓ Cài đặt thư viện hoàn tất thành công!${NC}"

# 5. Sanity Verification & Smoke Test
echo -e "\n🧪 ${BOLD}Bước 5/5: Kiểm tra tính tương thích và tự chẩn đoán (Self-test)...${NC}"
"$PYTHON_BIN" -c "
import sys
modules = ['PyQt6', 'pynput', 'fastembed', 'rat.os.crash_shield', 'rat.main']
for mod in modules:
    try:
        __import__(mod)
    except Exception as e:
        print(f'❌ Lỗi nạp module {mod}: {e}')
        sys.exit(1)
print('✓ Tất cả module lõi hoạt động trơn tru!')
"
if [ $? -ne 0 ]; then
    echo -e "${RED}⚠️ Quá trình kiểm tra module phát hiện cảnh báo. Vui lòng thử chạy lại script.${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Tự chẩn đoán đạt 100% PASS!${NC}"

# 6. Shell Command Integration
SHELL_RC=""
if [ -f "$HOME/.zshrc" ]; then
    SHELL_RC="$HOME/.zshrc"
elif [ -f "$HOME/.bash_profile" ]; then
    SHELL_RC="$HOME/.bash_profile"
elif [ -f "$HOME/.bashrc" ]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [ -n "$SHELL_RC" ]; then
    RAT_ALIAS="alias rat=\"$PYTHON_BIN $PROJECT_DIR/main.py\""
    if ! grep -q "alias rat=" "$SHELL_RC" 2>/dev/null; then
        echo -e "\n⚙️  Tích hợp lệnh gõ 'rat' vào $SHELL_RC..."
        echo "" >> "$SHELL_RC"
        echo "# rat — Smart File Finder alias" >> "$SHELL_RC"
        echo "$RAT_ALIAS" >> "$SHELL_RC"
        echo -e "${GREEN}✓ Đã thêm lệnh 'rat' vào $SHELL_RC${NC}"
    fi
fi

# 7. Success & Quick Start Instructions
echo -e "\n${GREEN}${BOLD}================================================================="
echo "   🎉 CHÚC MỪNG BẠN! SETUP ĐÃ HOÀN TẤT 100%!"
echo "=================================================================${NC}"
echo -e "Bạn có thể sử dụng rat ngay bây giờ bằng các cách sau:\n"
echo -e "  1. ${BOLD}Khởi động giao diện AI Finder:${NC}"
echo -e "     ${CYAN}$PYTHON_BIN main.py${NC}  (hoặc mở Terminal mới gõ: ${CYAN}rat${NC})\n"
echo -e "  2. ${BOLD}Mở thanh tìm kiếm nhanh Spotlight HUD:${NC}"
echo -e "     Bấm tổ hợp phím: ${BOLD}${YELLOW}Option + Shift + Space${NC} (hoặc Command + Shift + Space)\n"
echo -e "  3. ${BOLD}Ghép thời khóa biểu nhóm / CLB:${NC}"
echo -e "     ${CYAN}$PYTHON_BIN main.py schedule${NC}\n"
echo -e "  4. ${BOLD}Tìm kiếm tệp từ dòng lệnh:${NC}"
echo -e "     ${CYAN}$PYTHON_BIN main.py search \"báo cáo tuần trước\"${NC}\n"

echo -e "${YELLOW}💡 LƯU Ý CHO LẦN ĐẦU SỬ DỤNG:${NC}"
echo -e "Khi ứng dụng mở lên lần đầu, một cửa sổ hướng dẫn nhỏ sẽ hỗ trợ bạn cấp"
echo -e "quyền ${BOLD}Accessibility${NC} (để phím tắt hoạt động) và ${BOLD}Full Disk Access${NC} (để tìm tệp)."
echo -e "Chúc bạn có trải nghiệm làm việc & học tập thật mượt mà! 🚀"
echo "================================================================="

if [ "$1" == "run" ]; then
    echo -e "\n🚀 Đang khởi chạy rat..."
    exec "$PYTHON_BIN" "$PROJECT_DIR/main.py"
fi
