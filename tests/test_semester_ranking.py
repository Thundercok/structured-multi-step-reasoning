"""
tests/test_semester_ranking.py — Unit tests for Semester & Slide-Aware Ranking.
"""

import unittest
from rat.engine.context_parser import ContextParser
from rat.engine.reranker import Reranker


class TestSemesterRanking(unittest.TestCase):

    def setUp(self) -> None:
        self.reranker = Reranker()

    def test_semester_and_slide_boost(self) -> None:
        """Verify that slides in semester/course folders receive significant score boosts."""
        query = "501043 Kiến trúc máy tính"
        context = ContextParser.parse_query(query)

        slide_doc = {
            "file_path": "/Users/student/Documents/HK241/501043_KienTrucMayTinh/Slide_Chuong1.pptx",
            "file_name": "Slide_Chuong1.pptx",
            "file_ext": ".pptx",
            "content_text": "Kiến trúc máy tính chương 1 tổng quan pipeline cache",
            "modified_at": 1728000000.0,
            "vector_similarity": 0.85,
        }

        random_doc = {
            "file_path": "/Users/student/Downloads/random_notes.txt",
            "file_name": "random_notes.txt",
            "file_ext": ".txt",
            "content_text": "ghi chú linh tinh",
            "modified_at": 1728000000.0,
            "vector_similarity": 0.20,
        }

        slide_score, slide_reasons = self.reranker.compute_heuristic_score(slide_doc, context)
        random_score, random_reasons = self.reranker.compute_heuristic_score(random_doc, context)

        # Verify mathematical identity of raw scores
        self.assertAlmostEqual(5.0 + sum(slide_doc["_feats"].values()), slide_doc["_raw_score"], places=7)
        self.assertAlmostEqual(5.0 + sum(random_doc["_feats"].values()), random_doc["_raw_score"], places=7)

        # Verify feature activations
        self.assertEqual(slide_doc["_feats"]["study_doc"], 25.0)
        self.assertEqual(slide_doc["_feats"]["sem_dir"], 35.0)
        self.assertEqual(slide_doc["_feats"]["course_code_dir"], 30.0)
        self.assertEqual(slide_doc["_feats"]["slide_lecture"], 30.0)

        # Verify slide score dominates random file
        self.assertGreater(slide_score, random_score)
        self.assertEqual(slide_score, 100.0)

        # Verify human-readable reasons
        reasons_text = " ".join(slide_reasons)
        self.assertIn("Tài liệu học tập", reasons_text)
        self.assertIn("học kỳ", reasons_text)
        self.assertIn("mã học phần", reasons_text)
        self.assertIn("Slide", reasons_text)


if __name__ == "__main__":
    unittest.main()
