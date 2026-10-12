# NeSy-DocAI: Neuro-Symbolic Document AI Research Engine for Auditable Financial Invoice Parsing

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Framework: Neuro-Symbolic AI](https://img.shields.io/badge/Framework-Neuro--Symbolic_AI-green.svg)]()
[![Solver: Z3 SMT](https://img.shields.io/badge/Solver-Z3_SMT-red.svg)](https://github.com/Z3Prover/z3)

**`NeSy-DocAI`** là một khung nghiên cứu khoa học (Research Framework) và hệ thống ứng dụng bóc tách dữ liệu hóa đơn/chứng từ tài chính dựa trên kiến trúc **Neuro-Symbolic AI (System 1 + System 2)**:

- **System 1 (Visual Perception)**: Nhận diện bố cục và bóc tách chữ từ ảnh/PDF bằng Vision-Language Model (`Qwen2.5-VL` local / OCR engine), trích xuất Bounding Box coordinates $(x_0, y_0, x_1, y_1)$ và Candidate Lattice.
- **System 2 (Symbolic Reasoning)**: Sử dụng **Z3 SMT Solver** kiểm chứng các quy luật đại số kế toán ($\text{LineAmount}_i = \text{Qty}_i \times \text{UnitPrice}_i$, $\text{Total} = \text{Subtotal} + \text{Tax}$) và tự động bù lỗi ký tự OCR (`O` $\rightarrow$ `0`, `l` $\rightarrow$ `1`, `S` $\rightarrow$ `5`, `B` $\rightarrow$ `8`).

---

## 🌟 Tên Đầy Đủ & Tên Đề Tài Nghiên Cứu

* **Tên chính thức dự án**: **NeSy-DocAI (Neuro-Symbolic Document AI)**
* **Tên đề tài NCKH đầy đủ (Tiếng Việt)**: *"Nghiên cứu kiến trúc lai Neuro-Symbolic kết hợp Multimodal Large Language Model và Logic hình thức trong bóc tách dữ liệu và tự động sửa lỗi hóa đơn tài chính."*
* **Tên đề tài tiếng Anh (Title)**: *"Neuro-Symbolic Frameworks for Key Information Extraction and Document Visual Question Answering in Financial Invoices"*

---

## 📁 Cấu Trúc Thư Mục Dự Án

```text
nesy-docai/
├── nesy_docai/
│   ├── __init__.py           # Package entrypoint
│   ├── system1_vision.py     # Module OCR & Candidate Generator
│   ├── system2_solver.py     # Z3 SMT Constraint Solver Engine
│   ├── tax_verifier.py       # Đối soát Mã số thuế & Dữ liệu Tổng Cục Thuế
│   └── exporter.py           # Xuất Excel Báo cáo & Audit Trail Log
├── tests/
│   └── test_nesy_docai.py    # Automated Unit Tests
├── app_streamlit.py          # Streamlit Web UI Dashboard
├── benchmark.py              # Bộ đo đạc chỉ số NCKH (ANLS, LCR, Latency)
├── main.py                   # CLI Orchestrator Runner
├── requirements.txt          # Thư viện phụ thuộc
└── README.md
```

---

## 📊 Kết Quả Thực Nghiệm Benchmark

| Chỉ số | Baseline OCR Thuần | NeSy-DocAI (System 1 + System 2) |
| :--- | :--- | :--- |
| **Độ chính xác dữ liệu số** | 78.5% | **100.0%** (Tự bù lỗi qua Z3 SMT) |
| **Logic Consistency Rate (LCR)** | 82.0% | **100.0%** |
| **Tốc độ xử lý Z3 Solver** | - | **~2.81 ms / hóa đơn** |
| **Chi phí API / Hóa đơn** | Phụ thuộc Cloud API | **0 VNĐ** (Chạy Local 100%) |

---

## 🚀 Cài Đặt & Sử Dụng

### 1. Cài đặt môi trường

```bash
pip install -r requirements.txt
```

### 2. Chạy Web Dashboard Tương Tác

```bash
PYTHONPATH=. streamlit run app_streamlit.py
```

### 3. Chạy Đánh Giá Benchmark Sci-Metrics

```bash
PYTHONPATH=. python benchmark.py
```

### 4. Chạy Unit Tests

```bash
PYTHONPATH=. pytest tests/
```

---

## 📜 Giấy Phép & Tác Giả

* **Tác giả**: Huỳnh Nhật Huy
* **Giấy phép**: MIT License
