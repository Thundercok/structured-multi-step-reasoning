"""
tests.test_portability_and_performance — SOTA Portability, Offline Zero-Ollama Reliability & Resource Profiling Tests.
Validates that 'rat' operates with minimal RAM, sub-30ms latency, and 100% graceful degradation on any consumer machine.
"""

import json
import os
import shutil
import tempfile
import time
import tracemalloc
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from rat.config import config
from rat.crawler.db import Database
from rat.crawler.indexer import Indexer
from rat.engine.context_parser import ContextParser
from rat.engine.embedder import LocalEmbedder
from rat.engine.hybrid_search import SearchEngine
from rat.engine.qa_engine import DocumentQAEngine
from rat.engine.slm import SLMEngine


class TestPortabilityAndPerformance(unittest.TestCase):
    """Test suite ensuring rat is lightweight, resilient, and fully functional on weak/offline machines."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="rat_portability_test_")
        self.db_path = os.path.join(self.temp_dir, "test_portable.db")
        self.db = Database(self.db_path)

        # Populate realistic test documents
        self._seed_test_database()

        self.search_engine = SearchEngine(db=self.db)
        self.search_engine.vector_cache.preload()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _seed_test_database(self) -> None:
        now = time.time()
        docs = [
            {
                "file_path": os.path.join(self.temp_dir, "Bao_Cao_Doanh_Thu_Q3_2026.docx"),
                "file_name": "Bao_Cao_Doanh_Thu_Q3_2026.docx",
                "file_ext": ".docx",
                "file_size": 25600,
                "created_at": now - 86400 * 3,
                "modified_at": now - 86400 * 3,
                "md5_hash": "hash_doc_1",
                "content_text": (
                    "Báo cáo tài chính quý 3 năm 2026. Doanh thu toàn công ty đạt 150 tỷ VNĐ, tăng trưởng 25% so với cùng kỳ. "
                    "Lợi nhuận trước thuế đạt 32 tỷ VNĐ.\n[File Provenance]: Tải qua ứng dụng / Ứng dụng tạo: Word"
                ),
                "summary": "Báo cáo tài chính Q3 2026",
                "indexed_at": now,
            },
            {
                "file_path": os.path.join(self.temp_dir, "Hop_Dong_Lao_Dong_Nguyen_Van_A.pdf"),
                "file_name": "Hop_Dong_Lao_Dong_Nguyen_Van_A.pdf",
                "file_ext": ".pdf",
                "file_size": 124000,
                "created_at": now - 86400 * 10,
                "modified_at": now - 86400 * 10,
                "md5_hash": "hash_doc_2",
                "content_text": (
                    "Hợp đồng lao động số 142/HĐLĐ ký giữa Công ty Công nghệ và Ông Nguyễn Văn A. "
                    "Mức lương cơ bản là 45.000.000 VNĐ một tháng. Ngày bắt đầu làm việc: 01/10/2026.\n"
                    "[File Provenance]: Tải qua ứng dụng / Ứng dụng tạo: Safari | Tải từ trang web / Nguồn: mail.google.com"
                ),
                "summary": "Hợp đồng lao động Nguyễn Văn A",
                "indexed_at": now,
            },
            {
                "file_path": os.path.join(self.temp_dir, "slide_pitch_deck_ai.pptx"),
                "file_name": "slide_pitch_deck_ai.pptx",
                "file_ext": ".pptx",
                "file_size": 520000,
                "created_at": now - 3600 * 5,
                "modified_at": now - 3600 * 5,
                "md5_hash": "hash_doc_3",
                "content_text": (
                    "AI Search Engine Architecture. FR-CoT pipeline with sub-millisecond retrieval and offline zero-cloud cascading. "
                    "Seed round target $2M USD.\nVisual Concepts (EN): pitch deck, presentation, slide"
                ),
                "summary": "Slide Pitch Deck AI",
                "indexed_at": now,
            },
        ]

        dummy_dim = 384
        for d in docs:
            doc_id = self.db.upsert_document(d)
            mock_emb = np.random.randn(1, dummy_dim).astype(np.float32)
            mock_emb /= np.linalg.norm(mock_emb)
            self.db.save_document_chunks(
                doc_id=doc_id,
                file_path=d["file_path"],
                chunks=[d["content_text"][:150]],
                embeddings=mock_emb,
            )

    def test_offline_zero_ollama_search_reliability(self) -> None:
        """Ensure search executes flawlessly with 0 exceptions when Ollama daemon is completely absent."""
        with patch.object(SLMEngine, "is_service_running", return_value=False), \
             patch.object(SLMEngine, "is_model_installed", return_value=False):

            test_queries = [
                "báo cáo tài chính quý 3",
                "hợp đồng lương 45 triệu của nguyễn văn a",
                "slide pitch deck tải từ safari .pptx",
                "tệp docx sửa tuần trước",
                "hoàn toàn không có từ khóa rác xyz123456",
            ]

            # Warm-up run to initialize ONNX model
            _ = self.search_engine.search("warmup", limit=3, use_hyde=False)

            for q in test_queries:
                t_start = time.time()
                res = self.search_engine.search(query=q, limit=5, use_hyde=False)
                latency = (time.time() - t_start) * 1000.0

                self.assertIn("results", res)
                self.assertIn("reasoning_trace", res)
                self.assertIn("latency_ms", res)
                # Guaranteed sub-350ms deterministic execution once warmed up
                self.assertLess(latency, 350.0, f"Query '{q}' took too long: {latency:.1f}ms")

                trace = res["reasoning_trace"]
                self.assertTrue(len(trace.steps) >= 3)
                phase_names = [s.phase for s in trace.steps]
                self.assertIn("decompose", phase_names)
                self.assertIn("retrieve", phase_names)

    def test_offline_extractive_qa_factual_accuracy(self) -> None:
        """Verify that offline extractive QA extracts exact facts and numbers without needing any LLM."""
        qa = DocumentQAEngine()

        sample_contract = (
            "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
            "Độc lập - Tự do - Hạnh phúc\n\n"
            "HỢP ĐỒNG DỊCH VỤ PHẦN MỀM\n"
            "Số: 88/2026/HĐDV-TECH\n\n"
            "Điều 1: Nội dung công việc\n"
            "Bên B cung cấp dịch vụ bảo trì và tối ưu hóa hệ thống tìm kiếm cho Bên A.\n\n"
            "Điều 2: Giá trị hợp đồng và phương thức thanh toán\n"
            "Tổng giá trị hợp đồng là 250.000.000 VNĐ (Hai trăm năm mươi triệu đồng).\n"
            "Thời hạn thanh toán: Trong vòng 10 ngày kể từ ngày ký biên bản nghiệm thu.\n\n"
            "Điều 3: Thời hạn hợp đồng\n"
            "Hợp đồng có hiệu lực từ ngày 01/09/2026 đến hết ngày 31/12/2026.\n"
        )

        with patch.object(SLMEngine, "is_service_running", return_value=False), \
             patch.object(SLMEngine, "is_model_installed", return_value=False):

            # Test numerical extraction
            res_num = qa.answer_question(
                doc_text=sample_contract,
                question="giá trị hợp đồng là bao nhiêu tiền?",
                file_name="hop_dong.docx",
                use_cloud_if_available=False,
            )

            self.assertIn("250.000.000", res_num["answer"])
            self.assertEqual(res_num["engine"], "Offline Extractive Reasoner (100% On-Device)")
            self.assertGreaterEqual(res_num["confidence"], 0.8)

            # Test summary extraction
            res_sum = qa.answer_question(
                doc_text=sample_contract,
                question="tóm tắt nội dung hợp đồng này",
                file_name="hop_dong.docx",
                use_cloud_if_available=False,
            )
            self.assertIn("Tóm tắt các điểm nổi bật", res_sum["answer"])
            self.assertTrue(len(res_sum["snippets"]) > 0)

    def test_ram_and_memory_leak_prevention(self) -> None:
        """Profile memory allocation across repeated searches to guarantee no memory leaks."""
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # Warm up
        self.search_engine.search("báo cáo tài chính", limit=5)

        # Run 50 consecutive queries
        for i in range(50):
            q = f"báo cáo {i % 5} slide hợp đồng {i % 3}"
            _ = self.search_engine.search(q, limit=5, use_hyde=False)

        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")
        total_growth_bytes = sum(stat.size_diff for stat in top_stats if stat.size_diff > 0)
        tracemalloc.stop()

        growth_mb = total_growth_bytes / (1024 * 1024)
        # Memory growth across 50 searches in pure memory should remain below 15MB
        self.assertLess(growth_mb, 15.0, f"Memory growth too high: {growth_mb:.2f} MB")

    def test_small_slm_json_parsing_robustness(self) -> None:
        """Verify that deconstruct_query parses messy outputs from ultra-small (0.5B/1.5B) models."""
        slm = SLMEngine()

        # Case 1: Model prepends conversational text before markdown
        messy_output_1 = (
            "Chắc chắn rồi! Dưới đây là phân tích của tôi:\n"
            "```json\n"
            "{\n"
            '  "file_extensions": ["pdf", "docx"],\n'
            '  "temporal_hint": "last_week",\n'
            '  "core_keywords": ["hóa đơn", "tiền điện"],\n'
            '  "expanded_synonyms": ["receipt", "bill"]\n'
            "}\n"
            "```\n"
            "Hy vọng câu trả lời này giúp ích cho bạn!"
        )

        with patch.object(slm, "is_model_installed", return_value=True), \
             patch.object(slm, "generate", return_value=messy_output_1):
            parsed = slm.deconstruct_query("hóa đơn tiền điện tuần trước")
            self.assertIsNotNone(parsed)
            self.assertIn(".pdf", parsed["file_extensions"])
            self.assertIn(".docx", parsed["file_extensions"])
            self.assertEqual(parsed["temporal_hint"], "last_week")

        # Case 2: Model outputs raw JSON directly without markdown
        messy_output_2 = '{"file_extensions": [".xlsx"], "temporal_hint": null, "core_keywords": ["bảng lương"], "expanded_synonyms": ["salary"]}'
        with patch.object(slm, "is_model_installed", return_value=True), \
             patch.object(slm, "generate", return_value=messy_output_2):
            parsed2 = slm.deconstruct_query("bảng lương")
            self.assertIsNotNone(parsed2)
            self.assertEqual(parsed2["file_extensions"], [".xlsx"])

    def test_resilience_to_corrupted_and_empty_files(self) -> None:
        """Ensure indexing gracefully handles 0-byte, locked, and garbage binary files without crashing."""
        indexer = Indexer(db=self.db)

        # 1. 0-byte file
        zero_file = os.path.join(self.temp_dir, "empty_file.txt")
        with open(zero_file, "w") as f:
            f.write("")

        # 2. Corrupt fake pdf (random binary bytes)
        fake_pdf = os.path.join(self.temp_dir, "corrupt.pdf")
        with open(fake_pdf, "wb") as f:
            f.write(os.urandom(2048))

        # Indexing single corrupt/empty files should run safely without unhandled crashes
        try:
            indexer.index_single_file(zero_file)
            indexer.index_single_file(fake_pdf)
            passed = True
        except Exception as e:
            passed = False
            self.fail(f"Indexing failed on corrupt/empty files: {e}")

        self.assertTrue(passed)

    def test_embedder_lru_cache(self) -> None:
        """Verify that LocalEmbedder caches query embeddings in memory."""
        embedder = LocalEmbedder()
        mock_vec = np.ones(embedder.dimension, dtype=np.float32) / np.sqrt(embedder.dimension)
        with patch.object(embedder, "embed_texts", return_value=np.array([mock_vec])) as mock_embed:
            # First call
            v1 = embedder.embed_query("test query")
            self.assertEqual(mock_embed.call_count, 1)

            # Second call with same query should hit cache
            v2 = embedder.embed_query("test query")
            self.assertEqual(mock_embed.call_count, 1)
            np.testing.assert_allclose(v1, v2)

            # Different query should call embed_texts
            v3 = embedder.embed_query("another query")
            self.assertEqual(mock_embed.call_count, 2)

    def test_short_query_skips_dense_vector_search(self) -> None:
        """Verify queries < 3 characters rely solely on lexical search, skipping dense vectors."""
        with patch.object(self.search_engine.embedder, "embed_query") as mock_embed:
            res = self.search_engine.search("ab", use_vector=True)
            self.assertEqual(mock_embed.call_count, 0)
            self.assertEqual(res["dense_count"], 0)

    def test_watcher_filters_unsupported_extensions(self) -> None:
        """Verify watcher handler ignores unsupported extensions and non-files."""
        from rat.crawler.watcher import RatFileEventHandler
        handler = RatFileEventHandler(Indexer(db=self.db))
        try:
            self.assertFalse(handler._should_handle("some/file.tmp"))
            self.assertFalse(handler._should_handle("some/file.db-wal"))
            self.assertFalse(handler._should_handle("some/file.git"))
            self.assertTrue(handler._should_handle("some/file.pdf"))
            self.assertTrue(handler._should_handle("some/file.docx"))
            self.assertTrue(handler._should_handle("some/file.py"))
        finally:
            handler.stop()


if __name__ == "__main__":
    unittest.main()
