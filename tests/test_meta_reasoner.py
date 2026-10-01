"""
tests/test_meta_reasoner.py — Unit Tests for Runtime Meta-Reasoner Engine.
Verifies query classification, PAL calculation, policy escalation,
and structured reasoning traces.
"""

import unittest

from rat.engine.meta_reasoner import MetaReasonerEngine, meta_reasoner


class TestMetaReasonerEngine(unittest.TestCase):
    def setUp(self):
        self.engine = MetaReasonerEngine(lam=0.02)

    def test_is_reasoning_query_detection(self):
        # Academic reasoning queries
        self.assertTrue(self.engine.is_reasoning_query("Tính CPA tích lũy sau kỳ này"))
        self.assertTrue(self.engine.is_reasoning_query("Học phí kỳ này bao nhiêu tiền"))
        self.assertTrue(self.engine.is_reasoning_query("Quy chế học vụ về sinh viên song bằng"))
        self.assertTrue(self.engine.is_reasoning_query("Điều kiện đăng ký học vượt là gì?"))

        # Simple file queries or basic math should NOT trigger reasoning engine
        self.assertFalse(self.engine.is_reasoning_query("tính 120 * 4"))
        self.assertFalse(self.engine.is_reasoning_query("45 + 55"))
        self.assertFalse(self.engine.is_reasoning_query("slm.py"))
        self.assertFalse(self.engine.is_reasoning_query("Poster NCKH"))

    def test_pal_solver_cpa(self):
        res = self.engine.solve("Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này thêm 4 môn...")
        self.assertEqual(res.strategy, "PAL")
        self.assertIn("PAL", res.badge)
        self.assertIn("7.4", res.answer)
        self.assertGreaterEqual(res.confidence, 0.9)
        self.assertGreater(len(res.steps), 1)

    def test_ladder_escalation_policy(self):
        res = self.engine.solve("Quy chế đào tạo: sinh viên học song bằng thạc sĩ có bị đình chỉ không?")
        self.assertTrue(res.escalated)
        self.assertIn("ESCALATED", res.badge)
        self.assertIn("song bằng", res.answer.lower())
        self.assertGreaterEqual(res.confidence, 0.9)
        self.assertGreater(len(res.steps), 2)

    def test_singleton_cache(self):
        q = "Điều kiện nhận học bổng khuyến khích học tập loại Giỏi?"
        res1 = meta_reasoner.solve(q)
        res2 = meta_reasoner.solve(q)
        self.assertIs(res1, res2)


if __name__ == "__main__":
    unittest.main()
