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

    def test_pal_solver_does_not_fill_missing_cpa_inputs(self):
        res = self.engine.solve("Sinh viên tích lũy 64 tín chỉ có CPA 7.20. Học kỳ này thêm 4 môn...")
        self.assertEqual(res.strategy, "PAL")
        self.assertEqual(res.verification_status, "unverifiable")
        self.assertIsNone(res.witness_proof)
        self.assertNotIn("7.4", res.answer)
        self.assertEqual(res.tokens, 0)
        self.assertEqual(res.confidence_kind, "not_estimated")

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

    def test_hi_inside_nhieu_does_not_turn_calculation_into_a_greeting(self):
        self.assertTrue(self.engine._is_conversational_query("hi"))
        self.assertFalse(self.engine._is_conversational_query("CPA 9.1 thì bao nhiêu?"))

    def test_entry_route_classification(self):
        # Conversational fast path
        self.assertEqual(self.engine.entry_route("chào bạn, bạn là ai"), "CONVERSATIONAL")
        # Quantitative calculation
        self.assertEqual(self.engine.entry_route("Tính CPA kỳ này với điểm 8.0"), "PAL")
        # Long query > 60 words routes directly to PAL
        long_q = " ".join(["từ"] * 65)
        self.assertEqual(self.engine.entry_route(long_q), "PAL")
        # Policy queries enter ladder
        self.assertEqual(self.engine.entry_route("Quy chế đào tạo về cảnh báo học vụ"), "POLICY_LADDER")

    def test_calibrated_thresholds_default(self):
        # Must reflect the research-calibrated Stage 0 empirical thresholds (Qwen3-8B)
        self.assertGreater(len(self.engine.policy.tau), 1)
        self.assertAlmostEqual(self.engine.policy.tau[0], 0.9963, places=3)
        self.assertAlmostEqual(self.engine.policy.tau[1], 0.9794, places=3)

    def test_two_level_strategy_path_and_execution_mode(self):
        res_conv = self.engine.solve("chào bạn")
        self.assertEqual(res_conv.strategy_path, ["DIRECT_CHAT"])
        self.assertEqual(res_conv.execution_mode, "fast_path_entry")

        res_esc = self.engine.solve("Quy chế học vụ về sinh viên song bằng bị cảnh báo")
        self.assertTrue(res_esc.escalated)
        self.assertEqual(res_esc.strategy_path, ["DIRECT", "SC"])
        self.assertEqual(res_esc.execution_mode, "escalated_optimal_stopping")


if __name__ == "__main__":
    unittest.main()
