# 🕵️‍♂️ RepWatchBot - Enterprise Web Crawler & Alert System

**RepWatchBot** là hệ thống cào dữ liệu (web crawler), phân tích ngữ nghĩa thông minh và tự động phát cảnh báo cho tin đăng đồng hồ **Replica / Pass / Thanh lý** tại thị trường Việt Nam.

---

## 🌟 Tính Năng Nổi Bật (Features)

* **Multi-Source Scraping:** Cào dữ liệu đa nguồn từ Chợ Tốt API, các Web bán đồng hồ Rep chuyên biệt, và Facebook Marketplace (Playwright).
* **Smart Classification & Slang Detection:** Thuật toán phân loại thông minh nhận diện hơn 30+ mật mã lách từ (Clean Factory, VSF, Noob, Rep 1:1, Húp lót, Rô léx...).
* **Pydantic v2 Type Safety:** Mô hình dữ liệu chuẩn hóa với Pydantic v2 cho khả năng kiểm tra kiểu dữ liệu và serialization an toàn.
* **Storage & Export:** Quản lý chống trùng lặp bằng CSDL SQLite, hỗ trợ xuất báo cáo đa định dạng (`CSV`, `Excel`, `JSON`).
* **Telegram Instant Alerts:** Gửi thông báo ngay lập tức về Telegram khi phát hiện tin mới phù hợp tiêu chí.
* **Environment-Based Config:** Dễ dàng cấu hình thông qua `config.yaml` và file `.env`.

---

## 🚀 Hướng Dẫn Cài Đặt (Installation)

### 1. Yêu cầu hệ thống
* Python 3.9+
* Virtualenv / `uv` / Conda

### 2. Cài đặt Dependencies
```bash
cd rep_watch_bot

# Tạo môi trường ảo
python3 -m venv venv
source venv/bin/activate

# Cài đặt gói ở chế độ Editable (kèm Dev Dependencies)
pip install -e ".[dev]"
```

### 3. Cấu hình biến môi trường
Tạo file `.env` từ mẫu `.env.example`:
```bash
cp .env.example .env
```

---

## 💻 Hướng Dẫn Sử Dụng (Usage)

### 1. Cào 1 lần (Dry-run) và tự động xuất CSV
```bash
python main.py --once
```

### 2. Chế độ Giám sát Liên tục (Continuous Monitor)
Tự động lặp lại chu kỳ cào mỗi 15 phút (hoặc tùy chỉnh bằng `--interval`):
```bash
python main.py --monitor --interval 10
```

### 3. Xuất Báo Cáo Dữ Liệu
```bash
# Xuất CSV
python main.py --export csv

# Xuất Excel (.xlsx)
python main.py --export excel

# Xuất JSON
python main.py --export json
```

---

## 🧪 Chạy Automated Test Suite (Testing)

Dự án trang bị bộ Unit Test phủ toàn bộ Data Models, Slang Detector, SQLite Storage và Scraper Mocks:

```bash
pytest tests/
```

---

## 🏗️ Kiến Trúc Hệ Thống (Architecture)

```text
[ Sources (Chợ Tốt, WebRep, FB) ]
            │
            ▼
   [ BaseScraper Engine ]
            │
            ▼
 [ Slang & Price Classifier ]
            │
            ▼
   [ Pydantic WatchListing ]
            │
            ▼
[ SQLite Storage & Dedup Engine ] ──► [ Telegram Alert Bot ]
            │
            ▼
 [ Export Engine (CSV/Excel/JSON) ]
```
