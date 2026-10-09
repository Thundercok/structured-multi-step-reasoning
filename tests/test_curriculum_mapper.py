"""
tests/test_curriculum_mapper.py — Unit tests for Curriculum Code & Course Alias Expansion.
"""

import unittest
from rat.engine.curriculum_mapper import curriculum_mapper
from rat.engine.context_parser import ContextParser
from rat.engine.reranker import Reranker


class TestCurriculumMapper(unittest.TestCase):

    def test_curriculum_code_expansion(self) -> None:
        """Verify code 501043 expands to CO2003 and Kiến trúc máy tính."""
        aliases = curriculum_mapper.expand("501043")
        self.assertIn("CO2003", aliases)
        self.assertTrue(any("Kien truc" in a or "Kiến trúc" in a or "KienTruc" in a for a in aliases))

    def test_reverse_expansion(self) -> None:
        """Verify title or alt code expands back to primary course code."""
        aliases_by_alt = curriculum_mapper.expand("CO2003")
        self.assertIn("501043", aliases_by_alt)

        aliases_by_title = curriculum_mapper.expand("Kiến trúc máy tính")
        self.assertIn("501043", aliases_by_title)
        self.assertIn("CO2003", aliases_by_title)

    def test_context_parser_integration(self) -> None:
        """Verify ContextParser extracts course_aliases and short code keywords."""
        ctx = ContextParser.parse_query("501043 bài giảng")
        self.assertTrue(len(ctx.course_aliases) > 0)
        self.assertIn("CO2003", ctx.keywords)
        self.assertIn("CO2003", ctx.course_aliases)

    def test_reranker_alias_directory_boost(self) -> None:
        """Verify that folder with CO2003 gets course_code_dir boost for query 501043."""
        ctx = ContextParser.parse_query("501043 Slide")
        reranker = Reranker()

        doc_with_alt_code_dir = {
            "file_path": "/Users/student/Documents/HK241/CO2003_ComputerArchitecture/Slide1.pptx",
            "file_name": "Slide1.pptx",
            "file_ext": ".pptx",
            "content_text": "Slide bài giảng",
            "modified_at": 1728000000.0,
            "vector_similarity": 0.8,
        }

        score, reasons = reranker.compute_heuristic_score(doc_with_alt_code_dir, ctx)
        self.assertIn("course_code_dir", doc_with_alt_code_dir["_feats"])
        self.assertEqual(doc_with_alt_code_dir["_feats"]["course_code_dir"], 30.0)
        reasons_text = " ".join(reasons)
        self.assertIn("mã học phần", reasons_text)

    def test_generate_acronym(self) -> None:
        """Verify acronym generator creates accurate initials."""
        from rat.engine.curriculum_mapper import generate_acronym
        self.assertEqual(generate_acronym("Phân tích thiết kế hệ thống"), "pttkht")
        self.assertEqual(generate_acronym("Kỹ thuật lập trình"), "ktlt")
        self.assertEqual(generate_acronym("Xác suất thống kê"), "xstk")
        self.assertEqual(generate_acronym("An ninh mạng"), "anm")
        self.assertEqual(generate_acronym("Hệ thống nhúng"), "htn")

    def test_acronym_query_expansion(self) -> None:
        """Verify acronym tokens expand to related full course codes and titles."""
        aliases_pttkht = curriculum_mapper.expand("pttkht")
        self.assertIn("CO3007", aliases_pttkht)
        self.assertIn("502048", aliases_pttkht)
        self.assertTrue(any("Phân tích thiết kế" in a for a in aliases_pttkht))

        aliases_ktlt = curriculum_mapper.expand("ktlt")
        self.assertIn("CO1009", aliases_ktlt)
        self.assertIn("501004", aliases_ktlt)

    def test_reranker_acronym_match_boost(self) -> None:
        """Verify that document matching acronym gets +60 boost."""
        ctx = ContextParser.parse_query("pttkht bài tập")
        reranker = Reranker()

        doc_matching_acronym = {
            "file_path": "/Users/student/Documents/HK241/PTTKHT_Lab/Lab1.docx",
            "file_name": "Lab1.docx",
            "file_ext": ".docx",
            "content_text": "Bài tập phân tích hệ thống",
            "modified_at": 1728000000.0,
            "vector_similarity": 0.5,
        }

        score, reasons = reranker.compute_heuristic_score(doc_matching_acronym, ctx)
        self.assertIn("acronym_match", doc_matching_acronym["_feats"])
        self.assertEqual(doc_matching_acronym["_feats"]["acronym_match"], 60.0)
        reasons_text = " ".join(reasons)
        self.assertIn("viết tắt môn học", reasons_text)

    def test_damerau_levenshtein_le_1(self) -> None:
        """Verify Damerau-Levenshtein <= 1 detector handles adjacent swaps and single-char typos."""
        from rat.engine.curriculum_mapper import damerau_levenshtein_le_1
        self.assertTrue(damerau_levenshtein_le_1("pttkth", "pttkht"))  # transposition
        self.assertTrue(damerau_levenshtein_le_1("kttl", "ktlt"))      # transposition
        self.assertTrue(damerau_levenshtein_le_1("ptkht", "pttkht"))   # deletion
        self.assertTrue(damerau_levenshtein_le_1("pttkhtt", "pttkht")) # insertion
        self.assertTrue(damerau_levenshtein_le_1("pttkmt", "pttkht"))  # substitution
        self.assertFalse(damerau_levenshtein_le_1("pttkxx", "pttkht")) # 2 substitutions

    def test_typo_tolerant_query_expansion(self) -> None:
        """Verify transposed query 'pttkth' expands to CO3007 and 502048."""
        aliases_pttkth = curriculum_mapper.expand("pttkth")
        self.assertIn("CO3007", aliases_pttkth)
        self.assertIn("502048", aliases_pttkth)
        self.assertTrue(any("Phân tích thiết kế" in a for a in aliases_pttkth))

    def test_reranker_typo_acronym_match(self) -> None:
        """Verify that transposed query 'pttkth' boosts PTTKHT directory (+55 pts)."""
        ctx = ContextParser.parse_query("pttkth bài tập")
        reranker = Reranker()

        doc_typo = {
            "file_path": "/Users/student/Documents/HK241/PTTKHT_Lab/Lab1.docx",
            "file_name": "Lab1.docx",
            "file_ext": ".docx",
            "content_text": "Bài tập phân tích hệ thống",
            "modified_at": 1728000000.0,
            "vector_similarity": 0.5,
        }

        score, reasons = reranker.compute_heuristic_score(doc_typo, ctx)
        self.assertIn("acronym_match", doc_typo["_feats"])
        self.assertEqual(doc_typo["_feats"]["acronym_match"], 55.0)
        reasons_text = " ".join(reasons)
        self.assertIn("Khớp viết tắt môn học", reasons_text)


if __name__ == "__main__":
    unittest.main()
