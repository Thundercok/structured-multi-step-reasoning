"""
tests/test_vgc_cascade.py — Verification tests for Verified Generation Cascade (VGC) in RAT.
"""

import unittest
from rat.engine.vgc import (
    VGCCertificate,
    VGCVerificationStatus,
    VGCVerifier,
    VGCCascadeEngine,
)


class TestVGCVerifier(unittest.TestCase):

    def test_verify_calculation_exact(self):
        cert = VGCCertificate(claim="480", witness="480")
        res = VGCVerifier.verify_calculation(cert, "120 * 4")
        self.assertEqual(res.status, VGCVerificationStatus.VALID)
        self.assertIn("verified", res.reason.lower())

    def test_verify_calculation_float_tolerance(self):
        # 10 / 3 = 3.3333333333333335
        cert = VGCCertificate(claim="3.3333", witness=3.333333)
        res = VGCVerifier.verify_calculation(cert, "10 / 3")
        self.assertEqual(res.status, VGCVerificationStatus.VALID)

    def test_verify_calculation_mismatch_fails_closed(self):
        # Claimed 500 but 120 * 4 is 480
        cert = VGCCertificate(claim="500", witness="500")
        res = VGCVerifier.verify_calculation(cert, "120 * 4")
        self.assertEqual(res.status, VGCVerificationStatus.INVALID)
        self.assertIn("mismatch", res.reason.lower())

    def test_verify_calculation_division_by_zero(self):
        cert = VGCCertificate(claim="0", witness="0")
        res = VGCVerifier.verify_calculation(cert, "10 / 0")
        self.assertEqual(res.status, VGCVerificationStatus.INVALID)

    def test_verify_calculation_sandboxed_python(self):
        code_good = "x = 15\ny = 3\nresult = x * y\n"
        cert_good = VGCCertificate(claim="45", witness="45", raw_code=code_good)
        res_good = VGCVerifier.verify_calculation(cert_good, "15 * 3")
        self.assertEqual(res_good.status, VGCVerificationStatus.VALID)

        # Code with bug
        code_bad = "result = 10 / 0\n"
        cert_bad = VGCCertificate(claim="0", witness="0", raw_code=code_bad)
        res_bad = VGCVerifier.verify_calculation(cert_bad, "0")
        self.assertEqual(res_bad.status, VGCVerificationStatus.INVALID)

    def test_verify_document_fact_grounded(self):
        source = "Theo quyết định 1234/QĐ-ĐHTĐT, sinh viên được đăng ký tối đa 24 tín chỉ trong học kỳ chính."
        claim = "Sinh viên được đăng ký tối đa 24 tín chỉ theo quyết định 1234."
        cert = VGCCertificate(claim=claim, witness=claim, source_snippet=source[:50])
        res = VGCVerifier.verify_document_fact(cert, source)
        self.assertEqual(res.status, VGCVerificationStatus.VALID)

    def test_verify_document_fact_catches_hallucinated_numbers(self):
        source = "Học phí học kỳ 1 là 15.000.000 VNĐ cho 14 tín chỉ."
        # Model hallucinates 25.000.000 VNĐ
        claim = "Học phí phải nộp là 25.000.000 VNĐ."
        cert = VGCCertificate(claim=claim, witness=claim)
        res = VGCVerifier.verify_document_fact(cert, source)
        self.assertEqual(res.status, VGCVerificationStatus.INVALID)
        self.assertIn("hallucination detected", res.reason.lower())

    def test_verify_document_fact_catches_missing_entity(self):
        source = "Quy định áp dụng riêng cho ngành Kỹ thuật Phần mềm."
        claim = "Quy định áp dụng cho ngành Dược học."
        cert = VGCCertificate(claim=claim, witness=claim)
        res = VGCVerifier.verify_document_fact(cert, source, required_entities=["Dược học"])
        self.assertEqual(res.status, VGCVerificationStatus.INVALID)
        self.assertIn("contradiction", res.reason.lower())


class TestVGCCascadeEngine(unittest.TestCase):

    def setUp(self):
        self.engine = VGCCascadeEngine()

    def test_cascade_solve_quantitative_verified_fast(self):
        res = self.engine.solve_quantitative("tính 25 * 4", "25 * 4")
        self.assertEqual(res.verification.status, VGCVerificationStatus.VALID)
        self.assertFalse(res.escalated)
        self.assertIn("100", res.answer)
        self.assertIn("Verified", res.strategy)
        self.assertGreater(res.confidence, 0.95)

    def test_cascade_solve_document_fact_grounded_citation(self):
        doc = "Phòng thực hành C302 nằm tại tầng 3, tòa nhà C của trường ĐH Tôn Đức Thắng."
        res = self.engine.solve_document_fact(
            query="phòng C302 ở đâu",
            doc_text=doc,
            file_path="/tmp/so_tay_sinh_vien.pdf",
            page_num=3,
        )
        self.assertEqual(res.verification.status, VGCVerificationStatus.VALID)
        self.assertFalse(res.escalated)
        self.assertEqual(len(res.citations), 1)
        self.assertEqual(res.citations[0]["page"], 3)
        self.assertEqual(res.citations[0]["file_name"], "so_tay_sinh_vien.pdf")


if __name__ == "__main__":
    unittest.main()
