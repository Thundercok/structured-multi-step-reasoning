# 🧠 Designing Large Language Models for Structured Multi-Step Reasoning
> **Đề tài Nghiên cứu Khoa học Sinh viên (NCKHSV) — Năm học 2026–2027**  
> **Khoa Công nghệ Thông tin — Trường Đại học Tôn Đức Thắng (TDTU)**  
> **GVHD**: ThS. Trần Lương Quốc Đại  
> **Sinh viên thực hiện**: Huỳnh Nhật Huy (523C0012) & Linn Pyae Phyoe (525K0025)  

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Thundercok/structured-multi-step-reasoning/blob/main/structured_reasoning.ipynb)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 🔬 1. Lõi Nghiên Cứu (Core Research Framework & Notebook)
Trọng tâm nghiên cứu của đề tài nằm tại file Jupyter Notebook độc lập, được thiết kế để chạy trực tiếp 1-click trên Google Colab (GPU T4 miễn phí) hoặc trên máy tính cục bộ:
👉 **[`structured_reasoning.ipynb`](structured_reasoning.ipynb)** (Bấm nút `Open In Colab` ở trên để mở ngay).

### 🚀 Kiến trúc Suy luận 4 Pha (4-Phase Structured Reasoning Pipeline)
$$\text{Query} \xrightarrow[\text{Phase 1}]{\text{Decompose}} \{\text{Sub-Goals}\} \xrightarrow[\text{Phase 2}]{\text{Step Execution}} \text{Candidate Step} \xrightarrow[\text{Phase 3}]{\text{Sufficiency Verification}} \begin{cases} \text{PASS} \rightarrow \text{Next Step} \\ \text{FAIL} \xrightarrow[\text{Phase 4}]{\text{Self-Correct}} \text{Refined Step} \end{cases}$$

1. **Phase 1: Problem Decomposition** — Phân rã bài toán phức tạp thành các sub-goals có cấu trúc JSON.
2. **Phase 2: Atomic Step Deduction & Trace** — Thực thi từng bước kèm cấu trúc minh bạch `Thought -> Action -> Observation`.
3. **Phase 3: Process-Level Verification** — Tự đánh giá tính đầy đủ và logic của bước trung gian trước khi chuyển sang bước tiếp theo.
4. **Phase 4: Targeted Self-Correction** — Tự động kích hoạt cơ chế sửa sai và backtracking khi độ tin cậy dưới ngưỡng.

---

## 🖥️ 2. Môi Trường Thử Nghiệm Thực Tế Trên Thiết Bị (On-Device Testbed: `rat`)
Mã nguồn ứng dụng `rat` (Retrieval Augmented Tool) đóng vai trò là môi trường thử nghiệm thực tế (on-device testbed) trên macOS nhằm đánh giá độ trễ và khả năng suy luận cục bộ không cần đám mây.


## ⚡ Hướng Dẫn Cài Đặt Siêu Nhanh (Dành Cho Bạn Bè)

Bạn có thể chọn 1 trong 2 cách cài đặt cực kỳ đơn giản dưới đây:

### 💿 CÁCH 1: Dùng Bộ Cài Đặt `rat.dmg` (Khuyên Dùng cho Người Dùng Phổ Thông)
1. Tải file **`rat.dmg`** từ đường dẫn chia sẻ của nhóm.
2. Mở file DMG, bạn sẽ thấy 2 mục chính:
   - **Kéo `rat.app` vào thư mục `Applications`** bên cạnh.
   - **Nhấp đúp vào file `Cài_Đặt_&_Mở_rat.command`**: File này sẽ tự động gỡ bỏ cờ hạn chế của Apple (Gatekeeper Quarantine) và khởi chạy app ngay lập tức!
3. Cấp quyền **Accessibility** (để phím tắt hoạt động) và **Full Disk Access** (để quét tệp) theo hướng dẫn trên màn hình.

---

### 💻 CÁCH 2: Cài Đặt 1-Click Bằng Mã Nguồn (Dành Cho Dân Dev / Sinh Viên)
Mở Terminal, đi vào thư mục dự án và gõ đúng **1 lệnh**:

```bash
./setup.sh
```

*(Hoặc: `bash scripts/setup.sh`)*

Script sẽ tự động 100%:
- ✅ Kiểm tra macOS và phiên bản Python (>= 3.10).
- ✅ Tự tạo môi trường ảo `.venv` độc lập (tuân thủ chuẩn bảo mật PEP 668).
- ✅ Cài đặt toàn bộ thư viện cần thiết từ `requirements.txt`.
- ✅ Chạy tự chẩn đoán (Self-test) đảm bảo mọi tính năng hoạt động trơn tru.
- ✅ Tích hợp phím tắt lệnh `rat` vào `~/.zshrc` (chỉ cần gõ `rat` ở bất cứ đâu để mở app).

---

## 🌟 Tính Năng Nổi Bật & Phím Tắt

| Tính Năng | Thao Tác / Phím Tắt | Mô Tả |
| :--- | :--- | :--- |
| ⚡ **Spotlight HUD Nổi** | **`Option + Shift + Space`** | Tìm kiếm tệp tức thì (< 25ms), không chiếm diện tích màn hình. |
| 🗂️ **AI Finder Đầy Đủ** | Mở app trực tiếp | Xem trước văn bản, slide, ảnh OCR, tóm tắt và hỏi đáp nội dung. |
| 📅 **Ghép TKB CLB / Nhóm** | Menu Bar $\rightarrow$ **Thời khóa biểu CLB** | Nhập lịch các thành viên, ma trận tự động phát hiện **Khung giờ vàng** rảnh chung và xuất `.ics`. |
| 🖱️ **Trạng Thái Menu Bar** | Icon chuột trên thanh Top Bar | Quét lại tệp, kiểm tra số lượng vector, tùy chỉnh phím tắt và thư mục. |

---

## 🛠️ Yêu Cầu Hệ Thống
- **Hệ điều hành**: macOS 12 Monterey trở lên (Tương thích hoàn hảo Apple Silicon M1/M2/M3/M4 & Intel).
- **RAM**: Tối thiểu 4GB RAM (Khuyên dùng 8GB RAM trở lên).
- **Quyền hạn macOS**:
  - `Accessibility`: Lắng nghe phím tắt toàn cục.
  - `Full Disk Access`: Đọc và trích xuất nội dung tài liệu.
