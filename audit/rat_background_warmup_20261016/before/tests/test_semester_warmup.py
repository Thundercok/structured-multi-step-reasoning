"""
tests/test_semester_warmup.py — Unit tests for Semester Document Content Warmup.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from rat.crawler.warmup import SEMESTER_DIR_PATTERN, SemesterWarmupWorker


class TestSemesterWarmup(unittest.TestCase):

    def test_semester_dir_regex(self) -> None:
        """Verify semester directory pattern matching."""
        self.assertTrue(SEMESTER_DIR_PATTERN.search("/Users/user/Documents/HK241/CS101"))
        self.assertTrue(SEMESTER_DIR_PATTERN.search("/Users/user/Documents/2024-2025/Mon_Hoc"))
        self.assertTrue(SEMESTER_DIR_PATTERN.search("/Users/user/Documents/Hoc_Ky_1"))
        self.assertTrue(SEMESTER_DIR_PATTERN.search("/Users/user/Documents/Semester_2"))
        self.assertFalse(SEMESTER_DIR_PATTERN.search("/Users/user/Documents/Photos/Vacation"))

    def test_warmup_worker_discovery_and_indexing(self) -> None:
        """Verify worker discovers matching academic files and calls indexer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            sem_dir = tmp_path / "HK242" / "501043_KienTrucMayTinh"
            sem_dir.mkdir(parents=True)

            slide_file = sem_dir / "Slide_Chapter1.pptx"
            slide_file.write_text("dummy presentation")
            pdf_file = sem_dir / "Lab1_Instruction.pdf"
            pdf_file.write_text("dummy pdf")
            other_file = sem_dir / "notes.txt"
            other_file.write_text("dummy txt")

            # Non-academic folder
            other_dir = tmp_path / "Personal"
            other_dir.mkdir()
            random_ppt = other_dir / "random.pptx"
            random_ppt.write_text("random")

            mock_db = MagicMock()
            worker = SemesterWarmupWorker(db=mock_db)
            worker.indexer = MagicMock()
            worker.indexer.index_single_file.return_value = True

            with patch("rat.config.config.indexed_directories", [tmpdir]):
                finished_counts = []
                worker.finished.connect(lambda count: finished_counts.append(count))
                worker.run()

                # Should have found slide_file and pdf_file (2 academic files)
                self.assertEqual(len(finished_counts), 1)
                self.assertEqual(finished_counts[0], 2)
                self.assertEqual(worker.indexer.index_single_file.call_count, 2)
                called_paths = [call[0][0] for call in worker.indexer.index_single_file.call_args_list]
                self.assertIn(str(slide_file.resolve()), called_paths)
                self.assertIn(str(pdf_file.resolve()), called_paths)
                self.assertNotIn(str(random_ppt.resolve()), called_paths)

    def test_warmup_worker_stop(self) -> None:
        """Verify worker stops gracefully when requested."""
        worker = SemesterWarmupWorker(db=MagicMock())
        worker.indexer = MagicMock()
        worker.stop()
        self.assertTrue(worker._stopped)
        worker.indexer.cancel.assert_called_once()


if __name__ == "__main__":
    unittest.main()
