"""
meta_controller.dataset — University Academic & Regulatory Reasoning Dataset.
Includes realistic multi-tier academic queries:
- Tier 1: Factual / Definition (Best solved by CoT or Direct Retrieval)
- Tier 2: Arithmetic / Credit & GPA calculation (Best solved by PAL)
- Tier 3: Cross-regulatory conflict & Dual-degree Policy (Best solved by ToT / ReAct)
"""

from __future__ import annotations

from typing import Any, Dict, List


def get_academic_reasoning_benchmark() -> List[Dict[str, Any]]:
    return [
        # --- Type 1: Arithmetic & GPA Calculation (Requires PAL - Python Execution) ---
        {
            "id": "ACAD_01",
            "domain": "academic_gpa_calculation",
            "query": "Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này học thêm 4 môn gồm 3 môn 3 tín chỉ đạt điểm 8.5 và 1 môn 2 tín chỉ đạt điểm 9.0. Hãy tính CPA mới chính xác sau kỳ này?",
            "ground_truth": "7.44",
            "optimal_action": "PAL",
        },
        {
            "id": "ACAD_02",
            "domain": "academic_gpa_calculation",
            "query": "Học phí tín chỉ lý thuyết là 650.000đ/tín chỉ, thực hành là 850.000đ/tín chỉ. Sinh viên đăng ký 12 tín chỉ lý thuyết và 6 tín chỉ thực hành, được giảm 15% học bổng khuyến khích. Tổng học phí phải nộp là bao nhiêu?",
            "ground_truth": "10965000",
            "optimal_action": "PAL",
        },

        # --- Type 2: Regulatory Tra cứu & Factual (Solved by CoT) ---
        {
            "id": "ACAD_03",
            "domain": "academic_regulations",
            "query": "Theo quy chế đào tạo TDTU, điều kiện tối thiểu để sinh viên được đăng ký học vượt tối đa 24 tín chỉ trong một học kỳ chính là gì?",
            "ground_truth": "Điểm trung bình học kỳ trước từ 7.0 trở lên",
            "optimal_action": "COT",
        },
        {
            "id": "ACAD_04",
            "domain": "academic_regulations",
            "query": "Chuẩn đầu ra ngoại ngữ tiếng Anh đối với sinh viên ngành Kỹ thuật Phần mềm (chất lượng cao) yêu cầu chứng chỉ TOEIC tối thiểu bao nhiêu điểm?",
            "ground_truth": "600",
            "optimal_action": "COT",
        },

        # --- Type 3: Multi-Policy & Cross-Degree Conflict (Requires ToT or ReAct) ---
        {
            "id": "ACAD_05",
            "domain": "dual_degree_policy",
            "query": "Sinh viên đang học song bằng Cử nhân CNTT và Thạc sĩ Khoa học Máy tính. Nếu sinh viên xin tạm hoãn nghĩa vụ học vụ ở bậc Thạc sĩ trong 1 học kỳ, liệu kết quả học phần bên bậc Đại học có bị đình chỉ liên đới hay không? So sánh các điều khoản liên quan.",
            "ground_truth": "Không bị đình chỉ liên đới",
            "optimal_action": "TOT",
        },
        {
            "id": "ACAD_06",
            "domain": "dual_degree_policy",
            "query": "Một học phần có mã tương đương giữa chương trình Đại học và Thạc sĩ (ví dụ Học máy nâng cao). Sinh viên đã đạt điểm B+ ở bậc Thạc sĩ có được công nhận miễn môn tương đương ở bậc Đại học không, và thủ tục bảo lưu điểm thế nào?",
            "ground_truth": "Được công nhận chuyển đổi điểm",
            "optimal_action": "REACT",
        },

        # --- Type 4: Complex Multi-step Logic ---
        {
            "id": "ACAD_07",
            "domain": "scholarship_eligibility",
            "query": "Sinh viên có ĐTB học kỳ 8.4 (hệ 10), điểm rèn luyện 88 điểm, nợ 1 môn Giáo dục thể chất chưa thi lại. Sinh viên có đủ điều kiện xét học bổng khuyến khích học tập loại Giỏi không?",
            "ground_truth": "Không đủ điều kiện do nợ môn",
            "optimal_action": "SELF_CONSISTENCY",
        },
    ]
